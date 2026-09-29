"""Business orchestration for agent and editor workflows.

Migrated from packages/core/src/agent.ts and packages/core/src/model.ts.
Uses litellm for AI provider calls.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from ..services.ai_client import litellm_completion, litellm_image_completion
from ..services.image_utils import (
    prepare_image_for_api,
    read_image_dimensions_from_data_url,
    resize_image_to_dimensions,
)
from .analysis import parse_agent_analysis
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
    on_progress: Callable[[str], Awaitable[None]] | None = None,
) -> tuple[AgentImageAnalysis, str, list[str], str | None]:
    """Two-phase agent workflow: analysis → edit.

    Returns (analysis, analysis_raw, images, edit_text).
    """
    # ── Prepare image ──────────────────────────────────────
    source_w, source_h = read_image_dimensions_from_data_url(image_data_url)
    api_image = prepare_image_for_api(image_data_url)

    # ── Phase 1: Analysis ──────────────────────────────────
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

    # ── Phase 2: Edit ──────────────────────────────────────
    edit_prompt = _build_edit_prompt(analysis, source_w, source_h)

    logger.info("Starting edit phase (model=%s)", edit_model)
    if on_progress:
        await on_progress("edit")

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

    edit_result = await litellm_image_completion(
        host=edit_host,
        api_key=edit_api_key,
        model=edit_model,
        messages=edit_messages,
    )

    images = edit_result.get("images", [])
    if not images:
        raise RuntimeError("修图模型未返回图片")

    # Normalize to source dimensions
    normalized_image = resize_image_to_dimensions(images[0], source_w, source_h)

    return analysis, analysis_raw, [normalized_image], edit_result.get("text")


async def generate_image(
    *,
    edit_host: str,
    edit_api_key: str,
    edit_model: str,
    image_data_url: str,
    marks: list[dict] | None = None,
    image_config: dict | None = None,
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
    )

    images = result.get("images", [])
    if not images:
        raise RuntimeError("修图模型未返回图片")

    # Normalize to source dimensions
    normalized = resize_image_to_dimensions(images[0], source_w, source_h)

    return [normalized], result.get("text")
