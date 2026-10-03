from src.core.agent_plan import AgentPlan, AgentPlanStep
from src.core.agent_tools import execute_plan


PIXEL = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="


def test_apply_adjustments_runs_local_processor_and_preserves_dimensions() -> None:
    plan = AgentPlan(
        goal="Apply a small exposure correction",
        execution="local",
        steps=[
            AgentPlanStep(
                id="adjust",
                tool="apply_adjustments",
                params={"adjustments": {"exposure": 12, "temperature": 4}},
            ),
            AgentPlanStep(id="validate", tool="validate_result", depends_on=["adjust"]),
        ],
    )

    result = execute_plan(plan, source_image=PIXEL, output_image=PIXEL)

    assert result.has_failures is False
    assert result.runs[0].status == "executed"
    assert result.runs[-1].status == "executed"
