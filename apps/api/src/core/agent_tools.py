"""Synchronous local and asynchronous extension tool execution."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from .agent_plan import AgentPlan, AgentPlanStep, get_tool_descriptor
from .tool_registry import ToolExecutionContext, ToolExecutionResult, ToolRegistryError, tool_registry
from ..services.color_match import match_reference_color
from ..services.image_utils import apply_basic_image_adjustments
from ..services.style_tools import apply_style
from ..services.image_validation import validate_image_result

ToolStatus = Literal["executed", "deferred", "failed", "skipped"]


@dataclass(frozen=True)
class ToolRun:
    step_id: str
    tool: str
    status: ToolStatus
    message: str
    details: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return {"stepId": self.step_id, "tool": self.tool, "status": self.status,
                "message": self.message, "details": self.details or {}}


@dataclass(frozen=True)
class PlanExecution:
    runs: list[ToolRun]
    output_image: str

    @property
    def has_failures(self) -> bool:
        return any(run.status == "failed" for run in self.runs)

    def to_dict(self) -> dict[str, object]:
        return {"runs": [run.to_dict() for run in self.runs], "hasFailures": self.has_failures}


def _adjustments(step: AgentPlanStep, context: ToolExecutionContext) -> ToolExecutionResult:
    return ToolExecutionResult("已使用本地确定性算法完成基础调色。",
                               apply_basic_image_adjustments(context.current_image, step.params["adjustments"]))


def _style(step: AgentPlanStep, context: ToolExecutionContext) -> ToolExecutionResult:
    return ToolExecutionResult("已使用本地风格预设或 .cube LUT 完成风格化。",
                               apply_style(context.current_image, style_id=step.params.get("style_id"), lut_contents=step.params.get("lut_contents")))


def _reference(step: AgentPlanStep, context: ToolExecutionContext) -> ToolExecutionResult:
    return ToolExecutionResult("已使用参考图完成本地 RGB 统计追色。",
                               match_reference_color(context.current_image, step.params["reference_image"]))


def _ai_edit(step: AgentPlanStep, context: ToolExecutionContext) -> ToolExecutionResult:
    return ToolExecutionResult("已使用当前配置的修图模型处理原始图像。", context.current_image)


def _validate(step: AgentPlanStep, context: ToolExecutionContext) -> ToolExecutionResult:
    report = validate_image_result(context.source_image, context.current_image)
    if not report.ok:
        raise ValueError("；".join(report.issues))
    return ToolExecutionResult("已通过图片解码、输出尺寸和基础像素异常校验。", details=report.to_dict())


tool_registry.register_sync(get_tool_descriptor("apply_adjustments"), source="native", handler=_adjustments, replace=True)
tool_registry.register_sync(get_tool_descriptor("apply_style"), source="native", handler=_style, replace=True)
tool_registry.register_sync(get_tool_descriptor("match_reference_color"), source="native", handler=_reference, replace=True)
tool_registry.register_sync(get_tool_descriptor("apply_ai_edit"), source="model", handler=_ai_edit, replace=True)
tool_registry.register_sync(get_tool_descriptor("validate_result"), source="native", handler=_validate, replace=True)


def _failed(step: AgentPlanStep, message: str) -> ToolRun:
    return ToolRun(step.id, step.tool, "failed", message)


def _run_sync_step(step: AgentPlanStep, context: ToolExecutionContext) -> tuple[ToolRun, str]:
    try:
        result = tool_registry.execute_sync(step, context=context)
        return ToolRun(step.id, step.tool, "executed", result.message, result.details), result.output_image or context.current_image
    except (ToolRegistryError, Exception) as exc:
        return _failed(step, str(exc)), context.current_image


async def _run_async_step(step: AgentPlanStep, context: ToolExecutionContext) -> tuple[ToolRun, str]:
    try:
        registered = tool_registry.get(step.tool)
        if registered is None:
            raise ToolRegistryError(f"工具未注册: {step.tool}")
        if registered.handler is not None:
            result = await tool_registry.execute(step, context=context)
        elif registered.sync_handler is not None:
            result = registered.sync_handler(step, context)
        else:
            raise ToolRegistryError(f"工具尚未绑定执行器: {step.tool}")
        return ToolRun(step.id, step.tool, "executed", result.message, result.details), result.output_image or context.current_image
    except (ToolRegistryError, Exception) as exc:
        return _failed(step, str(exc)), context.current_image


def execute_plan(plan: AgentPlan, *, source_image: str, output_image: str) -> PlanExecution:
    runs: list[ToolRun] = []
    current_image = output_image
    for step in plan.steps:
        run, current_image = _run_sync_step(step, ToolExecutionContext(source_image, current_image))
        runs.append(run)
    return PlanExecution(runs, current_image)


async def execute_plan_async(plan: AgentPlan, *, source_image: str, output_image: str,
                             on_tool: Callable[[ToolRun, str], Awaitable[None]] | None = None,
                             skip_step_ids: set[str] | None = None) -> PlanExecution:
    runs: list[ToolRun] = []
    current_image = output_image
    for step in plan.steps:
        if skip_step_ids and step.id in skip_step_ids:
            run = ToolRun(step.id, step.tool, "skipped", "已从持久化 checkpoint 恢复，跳过已完成的本地步骤。")
            runs.append(run)
            continue
        run, current_image = await _run_async_step(step, ToolExecutionContext(source_image, current_image))
        runs.append(run)
        if on_tool:
            await on_tool(run, current_image)
    return PlanExecution(runs, current_image)
