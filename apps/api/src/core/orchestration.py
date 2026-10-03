"""Business orchestration for agent and editor workflows.

Migrated from packages/core/src/agent.ts and packages/core/src/model.ts.
Uses litellm for AI provider calls.
"""

from __future__ import annotations

import logging
import json
from collections.abc import Awaitable, Callable
from typing import Any

from ..services.ai_client import litellm_completion, litellm_image_completion
from ..services.image_utils import (
    prepare_image_for_api,
    read_image_dimensions_from_data_url,
    resize_image_to_dimensions,
)
from ..services.image_validation import validate_image_result
from .analysis import parse_agent_analysis
from .agent_loop import run_agent_loop
from .agent_tools import ToolRun, execute_plan_async
from .agent_plan import AgentPlan, build_plan_from_analysis
from .planner import generate_agent_plan
from .prompts import get_analysis_system_prompt, get_edit_system_prompt, get_editor_system_prompt, build_editor_user_prompt
from .types import AgentImageAnalysis

logger = logging.getLogger(__name__)


def _build_edit_prompt(analysis: AgentImageAnalysis, source_w: int, source_h: int) -> str:
    """Build the final edit prompt from analysis output (matches TS buildEditPrompt)."""
    return "\n".join([
        "[Task] Edit the attached input image and return the edited same image—not a new similar image painted from text alone.",
        "The input is the plate: person identity, features, hair, clothing, object types and counts, composition, perspective, and background structure must match the input.",
        "No full redraw, no face swap, no scene or season replacement; only minimal photo post within the instructions.",
        "",
        "Edit instructions:",
        analysis.editPrompt.strip(),
        "",
        f"[Dimension requirement] Output must be exactly {source_w} × {source_h} pixels (identical to the original). No crop, border, stretch, compress, or any aspect ratio or resolution change.",
        "If instructions conflict with fidelity, prioritize fidelity and change as little as possible.",
    ])


async def run_agent(
    *,
    analysis_host: str,
    analysis_api_key: str,
    analysis_model: str,
    edit_host: str,
    edit_api_key: str,
    edit_model: str,
    image_data_url: str,
    user_prompt: str = "",
    planned_plan: AgentPlan | None = None,
    planned_analysis: AgentImageAnalysis | None = None,
    planned_analysis_raw: str | None = None,
    resume_output_image: str | None = None,
    resume_step_ids: set[str] | None = None,
    idempotency_key: str | None = None,
    max_image_calls: int = 2,
    on_progress: Callable[[str], Awaitable[None]] | None = None,
    on_tool: Callable[[ToolRun, str, int], Awaitable[None]] | None = None,
) -> tuple[AgentImageAnalysis, str, list[str], str | None, dict, dict]:
    """Two-phase agent workflow: analysis → edit.

    Returns (analysis, analysis_raw, images, edit_text, plan, tool_trace).
    """
    # ── Prepare image ──────────────────────────────────────
    source_w, source_h = read_image_dimensions_from_data_url(image_data_url)
    api_image = prepare_image_for_api(image_data_url)

    # ── Phase 1: Analysis ──────────────────────────────────
    # A preview is an approval boundary. Reuse the frozen server snapshot at
    # execution time so approval does not silently pay for a second, divergent
    # observation of the same image.
    if planned_analysis is not None:
        analysis = planned_analysis
        analysis_raw = planned_analysis_raw or json.dumps(analysis.to_dict(), ensure_ascii=False)
        analysis_result = {"trace": {"protocol": "approved-analysis", "reused": True}}
    else:
        logger.info("Starting analysis phase (model=%s)", analysis_model)
        if on_progress:
            await on_progress("analysis")

        analysis_messages = [
            {"role": "system", "content": get_analysis_system_prompt()},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": api_image}},
                    {"type": "text", "text": user_prompt or "Analyze this image for photo retouching."},
                ],
            },
        ]

        analysis_result = await litellm_completion(
            host=analysis_host,
            api_key=analysis_api_key,
            model=analysis_model,
            messages=analysis_messages,
        )

        analysis_raw = analysis_result.get("text") or ""
        if not analysis_raw:
            raise RuntimeError("分析模型未返回文本")

        analysis = parse_agent_analysis(analysis_raw)

    planner_trace: dict[str, Any] = {}
    planner_status = "approved" if planned_plan is not None else "completed"
    if planned_plan is not None:
        plan = planned_plan
        planner_trace = {
            "model": analysis_model,
            "protocol": "approved-plan",
            "status": "completed",
            "durationMs": 0,
        }
    else:
        try:
            plan, planner_trace = await generate_agent_plan(
                host=analysis_host,
                api_key=analysis_api_key,
                model=analysis_model,
                analysis=analysis,
                user_prompt=user_prompt,
            )
        except Exception as exc:
            logger.warning("Planner failed; using deterministic fallback: %s", exc)
            plan = build_plan_from_analysis(analysis)
            planner_status = "fallback"
            planner_trace = {
                "model": analysis_model,
                "protocol": "planner-fallback",
                "status": "failed",
                "durationMs": 0,
                "error": str(exc),
            }
    last_edit_result: dict[str, Any] = {}

    # A local plan is a real Agent run: analysis and planning may be model
    # assisted, but the execution phase must not spend an image-model call.
    if not any(step.tool == "apply_ai_edit" for step in plan.steps):
        if on_progress:
            await on_progress("edit")
        # Local plans do not enter the retry loop, so their first execution is
        # attempt 1. Normalize the callback shape shared with model-backed
        # plans instead of passing the three-argument callback directly to the
        # two-argument tool executor.
        local_on_tool = (
            (lambda run, image: on_tool(run, image, 1))
            if on_tool else None
        )
        execution = await execute_plan_async(
            plan,
            source_image=image_data_url,
            output_image=resume_output_image or image_data_url,
            on_tool=local_on_tool,
            skip_step_ids=resume_step_ids,
        )
        if execution.has_failures:
            failed = next(run for run in execution.runs if run.status == "failed")
            raise RuntimeError(f"本地 Agent 工具执行失败：{failed.message}")
        tool_trace = execution.to_dict()
        tool_trace["planner"] = {"status": planner_status}
        tool_trace["aiCalls"] = [
            trace for trace in (analysis_result.get("trace"), planner_trace) if trace
        ]
        return analysis, analysis_raw, [execution.output_image], None, plan.model_dump(), tool_trace

    async def edit_step(step) -> str:
        edit_prompt = _build_edit_prompt(analysis, source_w, source_h)
        planned_prompt = step.params.get("edit_prompt") if isinstance(step.params, dict) else None
        if isinstance(planned_prompt, str) and planned_prompt.strip():
            edit_prompt = _build_edit_prompt(
                analysis.__class__(
                    imageType=analysis.imageType,
                    imageTypeReason=analysis.imageTypeReason,
                    deficiencies=analysis.deficiencies,
                    summary=analysis.summary,
                    editPrompt=planned_prompt,
                ),
                source_w,
                source_h,
            )
        edit_messages = [
            {"role": "system", "content": get_edit_system_prompt()},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": api_image, "detail": "high"}},
                    {"type": "text", "text": edit_prompt},
                ],
            },
        ]
        logger.info("Starting edit phase (model=%s)", edit_model)
        result = await litellm_image_completion(
            host=edit_host,
            api_key=edit_api_key,
            model=edit_model,
            messages=edit_messages,
            idempotency_key=idempotency_key,
        )
        last_edit_result.clear()
        last_edit_result.update(result)
        images = result.get("images", [])
        if not images:
            raise RuntimeError("修图模型未返回图片")
        raw_report = validate_image_result(image_data_url, images[0], require_same_size=False)
        last_edit_result["rawValidation"] = raw_report.to_dict()
        last_edit_result["trace"] = {
            **(last_edit_result.get("trace") or {}),
            "rawValidation": raw_report.to_dict(),
        }
        if not raw_report.ok:
            raise RuntimeError("修图模型原始输出未通过图片校验：" + "；".join(raw_report.issues))
        return resize_image_to_dimensions(images[0], source_w, source_h)

    loop_result = await run_agent_loop(
        plan=plan,
        source_image=image_data_url,
        edit_step=edit_step,
        on_progress=on_progress,
        on_tool=on_tool,
        max_attempts=max_image_calls,
    )
    tool_trace = loop_result.tool_trace
    tool_trace["planner"] = {"status": planner_status}
    tool_trace["aiCalls"] = [
        trace for trace in (analysis_result.get("trace"), planner_trace, last_edit_result.get("trace")) if trace
    ]

    return (
        analysis,
        analysis_raw,
        [loop_result.output_image],
        last_edit_result.get("text"),
        loop_result.plan.model_dump(),
        tool_trace,
    )


async def generate_image(
    *,
    edit_host: str,
    edit_api_key: str,
    edit_model: str,
    image_data_url: str,
    marks: list[dict] | None = None,
    image_config: dict | None = None,
    validation_sink: dict[str, object] | None = None,
    idempotency_key: str | None = None,
) -> tuple[list[str], str | None]:
    """Single-phase image generation for the editor workflow.

    Builds the prompt from marks on the backend (frontend sends only mark data).
    Returns (images, text).
    """
    if not image_data_url:
        raise RuntimeError("Image is required")

    source_w, source_h = read_image_dimensions_from_data_url(image_data_url)

    # Build prompts on the backend
    user_prompt = build_editor_user_prompt(marks or [], source_w, source_h)
    system_prompt = get_editor_system_prompt()

    # Prepare image for API
    api_url = prepare_image_for_api(image_data_url)

    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": api_url, "detail": "high"}},
                {"type": "text", "text": user_prompt},
            ],
        },
    ]

    logger.info("Starting editor edit (model=%s)", edit_model)
    result = await litellm_image_completion(
        host=edit_host,
        api_key=edit_api_key,
        model=edit_model,
        messages=messages,
        image_config=image_config,
        idempotency_key=idempotency_key,
    )

    images = result.get("images", [])
    if not images:
        raise RuntimeError("修图模型未返回图片")

    raw_report = validate_image_result(image_data_url, images[0], require_same_size=False)
    if validation_sink is not None:
        validation_sink.clear()
        validation_sink.update(raw_report.to_dict())
    if not raw_report.ok:
        raise RuntimeError("修图模型原始输出未通过图片校验：" + "；".join(raw_report.issues))
    # Normalize to source dimensions
    normalized = resize_image_to_dimensions(images[0], source_w, source_h)

    return [normalized], result.get("text")
