"""Typed planning contracts for the photography Agent.

The current runtime still uses the existing analysis -> image-edit flow. This
module gives that flow a stable, validated plan representation so local tools,
AI tools, and result validation can be added without changing the public API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .types import AgentImageAnalysis


ToolName = Literal[
    "apply_adjustments",
    "apply_style",
    "match_reference_color",
    "apply_ai_edit",
    "validate_result",
]


class AgentPlanStep(BaseModel):
    """One executable unit in an Agent plan."""

    id: str = Field(min_length=1, max_length=64)
    tool: ToolName
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

    name: ToolName
    description: str
    execution: Literal["local", "ai"]


TOOL_CATALOG: tuple[ToolDescriptor, ...] = (
    ToolDescriptor(
        name="apply_adjustments",
        description="Apply deterministic exposure, contrast, color, or white-balance adjustments.",
        execution="local",
    ),
    ToolDescriptor(
        name="apply_style",
        description="Apply a saved style preset or LUT to one or more assets.",
        execution="local",
    ),
    ToolDescriptor(
        name="match_reference_color",
        description="Match an asset to a selected reference image using deterministic color statistics.",
        execution="local",
    ),
    ToolDescriptor(
        name="apply_ai_edit",
        description="Run a constrained generative edit on the original image plate.",
        execution="ai",
    ),
    ToolDescriptor(
        name="validate_result",
        description="Check dimensions, output presence, and requested operation constraints.",
        execution="local",
    ),
)


def build_plan_from_analysis(analysis: AgentImageAnalysis) -> AgentPlan:
    """Build a conservative hybrid plan from the existing analysis result.

    This is intentionally deterministic. A future PydanticAI planner can
    replace this function while returning the same AgentPlan contract.
    """

    steps: list[AgentPlanStep] = []
    issue_categories = {item.category for item in analysis.deficiencies}
    local_categories = sorted(issue_categories & {"color", "lighting"})

    if local_categories:
        steps.append(
            AgentPlanStep(
                id="local_balance",
                tool="apply_adjustments",
                params={"categories": local_categories, "strength": "conservative"},
                rationale="Use deterministic local adjustments for color and lighting issues first.",
            ),
        )

    edit_dependencies = [steps[-1].id] if steps else []
    steps.append(
        AgentPlanStep(
            id="ai_edit",
            tool="apply_ai_edit",
            depends_on=edit_dependencies,
            params={"preserve_original_plate": True, "edit_prompt": analysis.editPrompt},
            rationale="Use the configured edit model only for the remaining semantic or local edit.",
        ),
    )
    steps.append(
        AgentPlanStep(
            id="validate",
            tool="validate_result",
            depends_on=[steps[-1].id],
            params={"preserve_dimensions": True, "preserve_composition": True},
            rationale="Verify the edited output before returning it to the workspace.",
        ),
    )

    execution = "hybrid" if local_categories else "ai"
    return AgentPlan(goal=analysis.summary, execution=execution, steps=steps)


def tool_catalog_as_dicts() -> list[dict[str, str]]:
    """Return JSON-friendly tool metadata for API responses and tracing."""

    return [
        {"name": tool.name, "description": tool.description, "execution": tool.execution}
        for tool in TOOL_CATALOG
    ]
