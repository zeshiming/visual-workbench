"""Execution boundary for Agent tools.

The runner deliberately distinguishes executed tools from deferred tools. That
keeps the Agent honest while local color/style executors are added incrementally
and gives the UI a trace it can display later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .agent_plan import AgentPlan
from ..services.color_match import match_reference_color
from ..services.image_utils import apply_basic_image_adjustments, read_image_dimensions_from_data_url
from ..services.style_tools import apply_style


ToolStatus = Literal["executed", "deferred", "failed"]


@dataclass(frozen=True)
class ToolRun:
    step_id: str
    tool: str
    status: ToolStatus
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "stepId": self.step_id,
            "tool": self.tool,
            "status": self.status,
            "message": self.message,
        }


@dataclass(frozen=True)
class PlanExecution:
    runs: list[ToolRun]
    output_image: str

    @property
    def has_failures(self) -> bool:
        return any(run.status == "failed" for run in self.runs)

    def to_dict(self) -> dict[str, object]:
        return {
            "runs": [run.to_dict() for run in self.runs],
            "hasFailures": self.has_failures,
        }


def execute_plan(
    plan: AgentPlan,
    *,
    source_image: str,
    output_image: str,
) -> PlanExecution:
    """Execute the currently supported part of a plan.

    The image model call remains owned by ``orchestration.run_agent``. The
    runner records it as ``apply_ai_edit`` and performs the final deterministic
    validation. Local adjustment/style/reference tools are explicitly deferred
    until their image processors are wired into this boundary.
    """

    source_dimensions = read_image_dimensions_from_data_url(source_image)
    output_dimensions = read_image_dimensions_from_data_url(output_image)
    runs: list[ToolRun] = []
    current_image = output_image

    for step in plan.steps:
        if step.tool in {"apply_adjustments", "apply_style", "match_reference_color"}:
            if step.tool == "apply_adjustments" and isinstance(step.params.get("adjustments"), dict):
                current_image = apply_basic_image_adjustments(
                    current_image,
                    step.params["adjustments"],
                )
                runs.append(
                    ToolRun(
                        step_id=step.id,
                        tool=step.tool,
                        status="executed",
                        message="已使用本地确定性算法完成基础调色。",
                    ),
                )
                continue
            if step.tool == "apply_style" and (
                isinstance(step.params.get("style_id"), str)
                or isinstance(step.params.get("lut_contents"), str)
            ):
                current_image = apply_style(
                    current_image,
                    style_id=step.params.get("style_id"),
                    lut_contents=step.params.get("lut_contents"),
                )
                runs.append(
                    ToolRun(
                        step_id=step.id,
                        tool=step.tool,
                        status="executed",
                        message="已使用本地风格预设或 .cube LUT 完成风格化。",
                    ),
                )
                continue
            if step.tool == "match_reference_color" and isinstance(
                step.params.get("reference_image"), str,
            ):
                current_image = match_reference_color(
                    current_image,
                    step.params["reference_image"],
                )
                runs.append(
                    ToolRun(
                        step_id=step.id,
                        tool=step.tool,
                        status="executed",
                        message="已使用参考图完成本地 RGB 统计追色。",
                    ),
                )
                continue
            runs.append(
                ToolRun(
                    step_id=step.id,
                    tool=step.tool,
                    status="deferred",
                    message="该本地工具已进入计划，等待对应图像处理器接入。",
                ),
            )
            continue

        if step.tool == "apply_ai_edit":
            runs.append(
                ToolRun(
                    step_id=step.id,
                    tool=step.tool,
                    status="executed",
                    message="已使用当前配置的修图模型处理原始图像。",
                ),
            )
            continue

        if step.tool == "validate_result":
            if source_dimensions != output_dimensions:
                runs.append(
                    ToolRun(
                        step_id=step.id,
                        tool=step.tool,
                        status="failed",
                        message=(
                            f"输出尺寸 {output_dimensions[0]}×{output_dimensions[1]} "
                            f"与原图 {source_dimensions[0]}×{source_dimensions[1]} 不一致。"
                        ),
                    ),
                )
            else:
                runs.append(
                    ToolRun(
                        step_id=step.id,
                        tool=step.tool,
                        status="executed",
                        message="已通过输出存在性和像素尺寸校验。",
                    ),
                )

    return PlanExecution(runs=runs, output_image=current_image)
