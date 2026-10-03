"""Typed planning contracts for the photography Agent.

The current runtime still uses the existing analysis -> image-edit flow. This
module gives that flow a stable, validated plan representation so local tools,
AI tools, and result validation can be added without changing the public API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .types import AgentImageAnalysis


ToolName = str


class AgentPlanStep(BaseModel):
    """One executable unit in an Agent plan."""

    id: str = Field(min_length=1, max_length=64)
    tool: str = Field(min_length=1, max_length=128)
    params: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    rationale: str = Field(default="", max_length=500)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.replace("_", "").replace("-", "").isalnum():
            raise ValueError("step id must contain only letters, numbers, hyphens, or underscores")
        return normalized

    @field_validator("tool")
    @classmethod
    def validate_tool_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.replace("_", "").replace("-", "").replace(":", "").replace(".", "").isalnum():
            raise ValueError("tool name contains unsupported characters")
        return normalized


class AgentPlan(BaseModel):
    """Validated plan shared by the planner, tool runner, and validator."""

    version: Literal["1"] = "1"
    goal: str = Field(min_length=1, max_length=1000)
    execution: Literal["local", "ai", "hybrid"] = "hybrid"
    steps: list[AgentPlanStep] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def validate_dependencies(self) -> "AgentPlan":
        ids = [step.id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("plan step ids must be unique")

        seen: set[str] = set()
        for step in self.steps:
            missing = set(step.depends_on) - set(ids)
            if missing:
                raise ValueError(f"step {step.id!r} depends on unknown step(s): {sorted(missing)}")
            if step.id in step.depends_on:
                raise ValueError(f"step {step.id!r} cannot depend on itself")
            if not set(step.depends_on).issubset(seen):
                raise ValueError(f"step {step.id!r} must depend only on earlier steps")
            seen.add(step.id)

        if self.steps[-1].tool != "validate_result":
            raise ValueError("the final plan step must validate_result")
        return self


@dataclass(frozen=True)
class ToolDescriptor:
    """Tool metadata exposed to a future planner or MCP adapter."""

    name: str
    description: str
    execution: Literal["local", "ai", "mcp", "skill"]
    risk_level: Literal["low", "medium", "high"] = "low"
    timeout_seconds: int = 120
    idempotent: bool = True
    input_schema: dict[str, Any] = field(default_factory=dict)


TOOL_CATALOG: tuple[ToolDescriptor, ...] = (
    ToolDescriptor(
        name="apply_adjustments",
        description="Apply deterministic exposure, contrast, color, or white-balance adjustments.",
        execution="local",
        input_schema={"adjustments": "object"},
    ),
    ToolDescriptor(
        name="apply_style",
        description="Apply a saved style preset or LUT to one or more assets.",
        execution="local",
        input_schema={"style_id": "string", "lut_contents": "string"},
    ),
    ToolDescriptor(
        name="match_reference_color",
        description="Match an asset to a selected reference image using deterministic color statistics.",
        execution="local",
        input_schema={"reference_image": "data_url|string"},
    ),
    ToolDescriptor(
        name="apply_ai_edit",
        description="Run a constrained generative edit on the original image plate.",
        execution="ai",
        risk_level="medium",
        timeout_seconds=600,
        idempotent=False,
        input_schema={"preserve_original_plate": "boolean", "edit_prompt": "string"},
    ),
    ToolDescriptor(
        name="validate_result",
        description="Check dimensions, output presence, and requested operation constraints.",
        execution="local",
        input_schema={"preserve_dimensions": "boolean"},
    ),
)


def build_plan_from_analysis(analysis: AgentImageAnalysis) -> AgentPlan:
    """Build a conservative hybrid plan from the existing analysis result.

    This is intentionally deterministic. A future PydanticAI planner can
    replace this function while returning the same AgentPlan contract.
    """

    adjustments = infer_adjustments_from_analysis(analysis)
    steps: list[AgentPlanStep] = [
        AgentPlanStep(
            id="ai_edit",
            tool="apply_ai_edit",
            depends_on=[],
            params={"preserve_original_plate": True, "edit_prompt": analysis.editPrompt},
            rationale="使用已配置的修图模型，在原图基础上执行语义或局部编辑。",
        ),
    ]
    if adjustments:
        steps.append(
            AgentPlanStep(
                id="local_balance",
                tool="apply_adjustments",
                depends_on=["ai_edit"],
                params={"adjustments": adjustments, "strength": "conservative"},
                rationale="在 AI 修图后，用保守的本地算法完成最后的色彩平衡。",
            ),
        )

    steps.append(
        AgentPlanStep(
            id="validate",
            tool="validate_result",
            depends_on=[steps[-1].id],
            params={"preserve_dimensions": True, "preserve_composition": True},
            rationale="在结果返回工作区前，检查输出是否存在并确认尺寸保持不变。",
        ),
    )

    execution = "hybrid" if adjustments else "ai"
    return AgentPlan(goal=analysis.summary, execution=execution, steps=steps)


def infer_adjustments_from_analysis(analysis: AgentImageAnalysis) -> dict[str, int]:
    """Infer only obvious, conservative numeric adjustments from descriptions.

    Directional color corrections are skipped when the model does not provide
    a clear cue. This prevents the planner from inventing a white-balance
    direction merely because an image was classified as having a color issue.
    """

    adjustments: dict[str, int] = {}
    for item in analysis.deficiencies:
        text = f"{item.description} {analysis.summary}".lower()

        if item.category == "lighting":
            if any(word in text for word in ("dark", "underexposed", "dim", "crushed", "too low")):
                adjustments["exposure"] = 8
                adjustments["shadows"] = 10
            elif any(word in text for word in ("bright", "overexposed", "blown", "too high")):
                adjustments["exposure"] = -6
                adjustments["highlights"] = -10

        if item.category == "color":
            if any(word in text for word in ("warm cast", "yellow cast", "too warm", "orange cast")):
                adjustments["temperature"] = -6
            elif any(word in text for word in ("cool cast", "blue cast", "too cool")):
                adjustments["temperature"] = 6

            if any(word in text for word in ("green cast", "green tint")):
                adjustments["tint"] = -6
            elif any(word in text for word in ("magenta cast", "purple cast")):
                adjustments["tint"] = 6

            if any(word in text for word in ("desaturated", "low saturation", "washed out")):
                adjustments["saturation"] = 6
            elif any(word in text for word in ("oversaturated", "too saturated")):
                adjustments["saturation"] = -6

        if item.category in {"color", "lighting"}:
            if any(word in text for word in ("flat", "low contrast", "hazy")):
                adjustments["contrast"] = 6
            elif any(word in text for word in ("harsh contrast", "high contrast")):
                adjustments["contrast"] = -5

    return adjustments


def tool_catalog_as_dicts() -> list[dict[str, object]]:
    """Return JSON-friendly tool metadata for API responses and tracing."""

    return [
        {
            "name": tool.name,
            "description": tool.description,
            "execution": tool.execution,
            "riskLevel": tool.risk_level,
            "timeoutSeconds": str(tool.timeout_seconds),
            "idempotent": str(tool.idempotent).lower(),
        }
        for tool in TOOL_CATALOG
    ]


def get_tool_descriptor(name: str) -> ToolDescriptor:
    for tool in TOOL_CATALOG:
        if tool.name == name:
            return tool
    raise ValueError(f"未知 Agent 工具: {name}")


def validate_tool_policy(plan: AgentPlan, *, allow_high_risk: bool = False) -> None:
    for step in plan.steps:
        try:
            descriptor = get_tool_descriptor(step.tool)
        except ValueError:
            if step.tool.startswith("mcp:") or step.tool.startswith("skill:"):
                continue
            raise
        if descriptor.risk_level == "high" and not allow_high_risk:
            raise ValueError(f"工具 {step.tool} 需要人工确认")
        _validate_tool_params(step.tool, step.params)


def _validate_tool_params(tool: str, params: dict[str, Any]) -> None:
    """Validate the small native-tool contract before a step reaches a runner."""

    if tool == "apply_adjustments" and not isinstance(params.get("adjustments"), dict):
        raise ValueError("apply_adjustments 需要 adjustments 对象")
    if tool == "apply_style":
        if not isinstance(params.get("style_id"), str) and not isinstance(params.get("lut_contents"), str):
            raise ValueError("apply_style 需要 style_id 或 lut_contents")
    if tool == "match_reference_color" and not isinstance(params.get("reference_image"), str):
        raise ValueError("match_reference_color 需要 reference_image")
    if tool == "apply_ai_edit" and not isinstance(params.get("edit_prompt"), str):
        raise ValueError("apply_ai_edit 需要 edit_prompt")
