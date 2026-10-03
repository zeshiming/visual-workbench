import asyncio

from src.core.agent_loop import AgentLoopError, run_agent_loop
from src.core.agent_plan import AgentPlan, AgentPlanStep
from src.services.ai_client import ProviderResultUnknown


PIXEL = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGNsSHBgYGBgYgADAA3qASRmXGo7AAAAAElFTkSuQmCC"


def test_agent_loop_replans_after_failed_execution() -> None:
    plan = AgentPlan(
        goal="Test loop",
        execution="ai",
        steps=[
            AgentPlanStep(id="ai_edit", tool="apply_ai_edit", params={"edit_prompt": "edit"}),
            AgentPlanStep(id="validate", tool="validate_result", depends_on=["ai_edit"]),
        ],
    )
    outputs = iter(["data:image/png;base64,invalid", PIXEL])

    async def edit_step(_step: AgentPlanStep) -> str:
        return next(outputs)

    result = asyncio.run(
        run_agent_loop(plan=plan, source_image=PIXEL, edit_step=edit_step, max_attempts=2),
    )

    assert result.attempts == 2
    assert result.replans == 1
    assert result.output_image == PIXEL


def test_agent_loop_error_keeps_attempt_trace() -> None:
    plan = AgentPlan(
        goal="Test terminal failure",
        execution="ai",
        steps=[
            AgentPlanStep(id="ai_edit", tool="apply_ai_edit", params={"edit_prompt": "edit"}),
            AgentPlanStep(id="validate", tool="validate_result", depends_on=["ai_edit"]),
        ],
    )

    async def edit_step(_step: AgentPlanStep) -> str:
        return "data:image/png;base64,invalid"

    try:
        asyncio.run(run_agent_loop(plan=plan, source_image=PIXEL, edit_step=edit_step, max_attempts=2))
    except AgentLoopError as exc:
        assert exc.trace["hasFailures"] is True
        assert len(exc.trace["attemptHistory"]) == 2
    else:
        raise AssertionError("terminal loop failure should carry trace")


def test_unknown_provider_result_stops_without_automatic_retry() -> None:
    plan = AgentPlan(
        goal="Unknown provider result",
        execution="ai",
        steps=[
            AgentPlanStep(id="ai_edit", tool="apply_ai_edit", params={"edit_prompt": "edit"}),
            AgentPlanStep(id="validate", tool="validate_result", depends_on=["ai_edit"]),
        ],
    )

    async def edit_step(_step: AgentPlanStep) -> str:
        raise ProviderResultUnknown("provider timeout after request", provider="test", request_id="req-1")

    try:
        import asyncio
        asyncio.run(run_agent_loop(plan=plan, source_image=PIXEL, edit_step=edit_step, max_attempts=2))
    except AgentLoopError as exc:
        assert exc.trace["loop"]["status"] == "needs_review"
        assert exc.trace["resultState"] == "unknown"
        assert len(exc.trace["attemptHistory"]) == 1
    else:
        raise AssertionError("unknown provider result must not be retried")
