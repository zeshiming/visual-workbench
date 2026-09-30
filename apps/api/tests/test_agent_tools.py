from src.core.agent_plan import build_plan_from_analysis
from src.core.agent_tools import execute_plan
from src.core.types import AgentImageAnalysis, ImageDeficiency


PIXEL = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="


def test_execute_plan_reports_deferred_local_tools_and_validates_output() -> None:
    analysis = AgentImageAnalysis(
        imageType="landscape",
        imageTypeReason="scene",
        deficiencies=[ImageDeficiency(category="lighting", description="dark", severity="low")],
        summary="balance",
        editPrompt="local edit",
    )

    result = execute_plan(build_plan_from_analysis(analysis), source_image=PIXEL, output_image=PIXEL)

    assert result.has_failures is False
    assert [run.status for run in result.runs] == ["executed", "executed", "executed"]
    assert result.runs[-1].tool == "validate_result"
