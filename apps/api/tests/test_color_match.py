from src.core.agent_plan import AgentPlan, AgentPlanStep
from src.core.agent_tools import execute_plan


PIXEL = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="


def test_reference_color_tool_executes_and_preserves_dimensions() -> None:
    plan = AgentPlan(
        goal="Match the selected reference",
        execution="local",
        steps=[
            AgentPlanStep(
                id="match",
                tool="match_reference_color",
                params={"reference_image": PIXEL},
            ),
            AgentPlanStep(id="validate", tool="validate_result", depends_on=["match"]),
        ],
    )

    result = execute_plan(plan, source_image=PIXEL, output_image=PIXEL)

    assert result.has_failures is False
    assert [run.status for run in result.runs] == ["executed", "executed"]
