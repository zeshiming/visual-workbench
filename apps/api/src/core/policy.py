"""Application-level guardrails for Agent requests and plans."""

from __future__ import annotations

import io

from PIL import Image, UnidentifiedImageError

from .agent_plan import AgentPlan, validate_tool_policy
from .tool_registry import tool_registry
from ..services.image_utils import decode_data_url


MAX_PROMPT_CHARS = 12_000
MAX_IMAGE_DATA_URL_CHARS = 25_000_000
MAX_PLAN_STEPS = 8
MAX_IMAGE_PIXELS = 100_000_000

_AGENT_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "created": {"running", "paused", "cancelling", "cancelled", "failed", "interrupted"},
    "running": {"running", "paused", "retrying", "replanning", "validating", "completed", "failed", "cancelling", "cancelled", "interrupted"},
    "paused": {"paused", "running", "cancelling", "completed", "failed", "cancelled", "interrupted"},
    "retrying": {"retrying", "running", "replanning", "failed", "cancelled", "interrupted"},
    "replanning": {"replanning", "running", "failed", "cancelled", "interrupted"},
    "validating": {"validating", "completed", "failed", "needs_review", "cancelled", "interrupted"},
    "cancelling": {"cancelling", "cancelled", "failed", "interrupted"},
    "completed": {"completed"},
    "failed": {"failed"},
    "cancelled": {"cancelled"},
    "needs_review": {"needs_review", "completed", "failed"},
    "interrupted": {"interrupted", "running", "failed", "needs_review"},
}


def validate_agent_input(*, prompt: str, image_data_url: str) -> None:
    if not image_data_url.startswith("data:image/"):
        raise ValueError("只允许使用图片 Data URL 作为 Agent 输入")
    if len(image_data_url) > MAX_IMAGE_DATA_URL_CHARS:
        raise ValueError("图片输入过大，请先压缩图片后重试")
    try:
        raw = decode_data_url(image_data_url)
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise ValueError("图片像素过大，请先压缩图片后重试")
    except (ValueError, UnidentifiedImageError, OSError) as exc:
        if isinstance(exc, ValueError) and str(exc) in {"图片像素过大，请先压缩图片后重试"}:
            raise
        raise ValueError("图片内容无法解码，请重新选择 JPG、PNG 或 WebP 图片") from exc
    if len(prompt) > MAX_PROMPT_CHARS:
        raise ValueError("修图需求过长，请压缩为 12000 个字符以内")


def validate_agent_status_transition(current: str, requested: str) -> None:
    allowed = _AGENT_STATUS_TRANSITIONS.get(current, set())
    if requested not in allowed:
        raise ValueError(f"Agent 状态不允许从 {current} 变更为 {requested}")


def validate_agent_plan(plan: AgentPlan, *, approved: bool) -> None:
    validate_agent_plan_shape(plan)
    if not approved:
        raise ValueError("Agent 计划尚未获得用户确认")
    validate_tool_policy(plan, allow_high_risk=approved)


def validate_agent_plan_shape(plan: AgentPlan) -> None:
    if len(plan.steps) > MAX_PLAN_STEPS:
        raise ValueError(f"Agent 计划最多允许 {MAX_PLAN_STEPS} 个步骤")
    ai_steps = [step for step in plan.steps if step.tool == "apply_ai_edit"]
    if len(ai_steps) > 1:
        raise ValueError("图片 Agent 计划最多包含一个 apply_ai_edit 步骤")
    if not ai_steps and plan.execution != "local":
        raise ValueError("不含 apply_ai_edit 的计划必须声明 execution=local")
    for step in plan.steps:
        if (step.tool.startswith("mcp:") or step.tool.startswith("skill:")) and tool_registry.get(step.tool) is None:
            raise ValueError(f"扩展工具尚未注册: {step.tool}")
    validate_tool_policy(plan)
