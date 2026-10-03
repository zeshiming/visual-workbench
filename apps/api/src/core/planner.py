"""LLM-backed structured planner with deterministic fallback support."""

from __future__ import annotations

import json
from typing import Any

from ..services.ai_client import litellm_completion
from ..skills.registry import skill_registry
from .tool_registry import tool_registry
from .agent_plan import AgentPlan
from .analysis import strip_markdown_fence
from .prompts import build_agent_planner_prompt, get_agent_planner_system_prompt
from .types import AgentImageAnalysis


def parse_agent_plan(text: str) -> AgentPlan:
    cleaned = strip_markdown_fence(text)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Agent 计划不是有效 JSON：{exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Agent 计划必须是 JSON 对象")
    return AgentPlan.model_validate(payload)


async def generate_agent_plan(
    *,
    host: str,
    api_key: str,
    model: str,
    analysis: AgentImageAnalysis,
    user_prompt: str,
) -> tuple[AgentPlan, dict[str, Any]]:
    result = await litellm_completion(
        host=host,
        api_key=api_key,
        model=model,
        messages=[
            {"role": "system", "content": get_agent_planner_system_prompt()},
            {
                "role": "user",
                "content": build_agent_planner_prompt(
                    analysis, user_prompt, skill_registry.planner_context(), tool_registry.planner_context(),
                ),
            },
        ],
    )
    raw = result.get("text") or ""
    if not raw:
        raise ValueError("Planner 未返回计划")
    return parse_agent_plan(raw), result.get("trace", {})
