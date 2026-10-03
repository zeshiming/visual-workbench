"""Plan → execute → validate → replan loop for Agent runs."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from .agent_plan import AgentPlan, AgentPlanStep, validate_tool_policy
from .agent_tools import ToolRun, execute_plan_async
from ..services.ai_client import ProviderResultUnknown


@dataclass(frozen=True)
class AgentLoopResult:
    output_image: str
    plan: AgentPlan
    tool_trace: dict[str, object]
    attempts: int
    replans: int


class AgentLoopError(RuntimeError):
    """Terminal loop failure carrying the attempts needed for diagnosis."""

    def __init__(self, message: str, *, trace: dict[str, object]):
        super().__init__(message)
        self.trace = trace


def _replan_after_failure(plan: AgentPlan, message: str) -> AgentPlan:
    """Create a conservative retry plan from the failed execution result."""

    steps = []
    for step in plan.steps:
        if step.tool == "apply_ai_edit":
            params = dict(step.params)
            params["edit_prompt"] = (
                f"{params.get('edit_prompt', '')}\n\n"
                f"上一次执行校验失败：{message}。请更保守地重试，只做必要的局部编辑，严格保持原图尺寸和构图。"
            )
            steps.append(
                step.model_copy(
                    update={
                        "params": params,
                        "rationale": "根据上一次校验失败信息重新执行更保守的 AI 修图。",
                    },
                ),
            )
        else:
            steps.append(step)
    return AgentPlan(goal=plan.goal, execution=plan.execution, steps=steps)


async def run_agent_loop(
    *,
    plan: AgentPlan,
    source_image: str,
    edit_step: Callable[[AgentPlanStep], Awaitable[str]],
    on_progress: Callable[[str], Awaitable[None]] | None = None,
    on_tool: Callable[[ToolRun, str, int], Awaitable[None]] | None = None,
    max_attempts: int = 2,
) -> AgentLoopResult:
    current_plan = plan
    attempts: list[dict[str, object]] = []

    for attempt in range(1, max_attempts + 1):
        if on_progress:
            await on_progress("edit")
        try:
            validate_tool_policy(current_plan)
            edit_step_config = next(step for step in current_plan.steps if step.tool == "apply_ai_edit")
            output_image = await edit_step(edit_step_config)
            execution = await execute_plan_async(
                current_plan,
                source_image=source_image,
                output_image=output_image,
                on_tool=(lambda run, image: on_tool(run, image, attempt)) if on_tool else None,
            )
            trace = execution.to_dict()
            attempts.append({
                "attempt": attempt,
                "status": "failed" if execution.has_failures else "completed",
                "runs": trace["runs"],
            })
            if not execution.has_failures:
                trace["loop"] = {
                    "attempts": attempt,
                    "replans": max(0, attempt - 1),
                    "status": "completed",
                }
                trace["attemptHistory"] = attempts
                return AgentLoopResult(
                    output_image=execution.output_image,
                    plan=current_plan,
                    tool_trace=trace,
                    attempts=attempt,
                    replans=max(0, attempt - 1),
                )
            failed = next(run for run in execution.runs if run.status == "failed")
            failure_message = failed.message
        except ProviderResultUnknown as exc:
            failure_message = str(exc)
            attempts.append({
                "attempt": attempt,
                "status": "needs_review",
                "resultState": "unknown",
                "provider": exc.provider,
                "requestId": exc.request_id,
                "runs": [ToolRun(
                    step_id="agent_loop",
                    tool="apply_ai_edit",
                    status="failed",
                    message=failure_message,
                ).to_dict()],
            })
            raise AgentLoopError(
                "图片模型请求结果未知，已停止自动重试，请核对供应商任务状态。",
                trace={
                    "runs": attempts[-1]["runs"],
                    "hasFailures": True,
                    "loop": {"attempts": attempt, "replans": 0, "status": "needs_review"},
                    "attemptHistory": attempts,
                    "resultState": "unknown",
                    "provider": exc.provider,
                    "requestId": exc.request_id,
                },
            ) from exc
        except Exception as exc:
            failure_message = str(exc)
            attempts.append({
                "attempt": attempt,
                "status": "failed",
                "runs": [ToolRun(
                    step_id="agent_loop",
                    tool="apply_ai_edit",
                    status="failed",
                    message=failure_message,
                ).to_dict()],
            })

        if attempt < max_attempts:
            current_plan = _replan_after_failure(current_plan, failure_message)

    raise AgentLoopError(
        f"Agent 执行失败，已重规划并重试 {max_attempts} 次：{failure_message}",
        trace={
            "runs": attempts[-1].get("runs", []) if attempts else [],
            "hasFailures": True,
            "loop": {
                "attempts": max_attempts,
                "replans": max(0, max_attempts - 1),
                "status": "failed",
            },
            "attemptHistory": attempts,
        },
    )
