from src.core.agent_plan import AgentPlan, AgentPlanStep, build_plan_from_analysis
from src.core.types import AgentImageAnalysis, ImageDeficiency


def test_build_plan_adds_local_balance_before_ai_edit() -> None:
    analysis = AgentImageAnalysis(
        imageType="landscape",
        imageTypeReason="A scene-focused image.",
        deficiencies=[
            ImageDeficiency(category="color", description="Warm cast", severity="medium"),
        ],
        summary="The image needs a restrained color correction.",
        editPrompt="Apply a subtle local correction while preserving the original plate.",
    )

    plan = build_plan_from_analysis(analysis)

    assert plan.execution == "hybrid"
    assert [step.tool for step in plan.steps] == [
        "apply_adjustments",
        "apply_ai_edit",
        "validate_result",
    ]
    assert plan.steps[1].depends_on == ["local_balance"]
    assert plan.steps[-1].depends_on == ["ai_edit"]


def test_plan_rejects_dependencies_on_later_steps() -> None:
    try:
        AgentPlan(
            goal="Test plan",
            steps=[
                AgentPlanStep(id="validate", tool="validate_result", depends_on=["edit"]),
                AgentPlanStep(id="edit", tool="apply_ai_edit"),
            ],
        )
    except ValueError as exc:
        assert "earlier steps" in str(exc)
    else:
        raise AssertionError("expected dependency validation to fail")
