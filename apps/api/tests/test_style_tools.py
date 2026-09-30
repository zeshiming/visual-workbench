from src.core.agent_plan import AgentPlan, AgentPlanStep
from src.core.agent_tools import execute_plan
from src.services.style_tools import parse_cube_lut


PIXEL = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
IDENTITY_LUT = """LUT_3D_SIZE 2
0 0 0
1 0 0
0 1 0
1 1 0
0 0 1
1 0 1
0 1 1
1 1 1
"""


def test_cube_parser_accepts_identity_lut() -> None:
    lut = parse_cube_lut(IDENTITY_LUT)
    assert lut.size == 2
    assert len(lut.values) == 24


def test_style_tool_executes_builtin_style() -> None:
    plan = AgentPlan(
        goal="Apply a warm film look",
        execution="local",
        steps=[
            AgentPlanStep(id="style", tool="apply_style", params={"style_id": "warm-film"}),
            AgentPlanStep(id="validate", tool="validate_result", depends_on=["style"]),
        ],
    )

    result = execute_plan(plan, source_image=PIXEL, output_image=PIXEL)

    assert result.has_failures is False
    assert [run.status for run in result.runs] == ["executed", "executed"]
