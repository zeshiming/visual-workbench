from src.core.agent_plan import AgentPlan, AgentPlanStep
from src.core.policy import validate_agent_plan, validate_agent_plan_shape, validate_agent_status_transition


def _plan(*tools: str) -> AgentPlan:
    steps = [AgentPlanStep(id=f"step-{index}", tool=tool, params={"edit_prompt": "局部调整"} if tool == "apply_ai_edit" else {}) for index, tool in enumerate(tools)]
    return AgentPlan(goal="test", steps=steps)


def test_agent_plan_requires_one_ai_edit_and_validates_native_params() -> None:
    try:
        validate_agent_plan_shape(_plan("validate_result"))
    except ValueError as exc:
        assert "execution=local" in str(exc)
    else:
        raise AssertionError("plan without an AI edit should be rejected")
    try:
        validate_agent_plan_shape(_plan("apply_ai_edit", "apply_adjustments", "validate_result"))
    except ValueError as exc:
        assert "需要 adjustments 对象" in str(exc)
    else:
        raise AssertionError("malformed local tool params should be rejected")


def test_agent_plan_requires_explicit_approval() -> None:
    try:
        validate_agent_plan(_plan("apply_ai_edit", "validate_result"), approved=False)
    except ValueError as exc:
        assert "尚未获得用户确认" in str(exc)
    else:
        raise AssertionError("unapproved plan should be rejected")


def test_agent_status_transition_rejects_terminal_reuse() -> None:
    validate_agent_status_transition("running", "completed")
    validate_agent_status_transition("paused", "completed")
    try:
        validate_agent_status_transition("completed", "running")
    except ValueError:
        pass
    else:
        raise AssertionError("terminal run cannot return to running")
