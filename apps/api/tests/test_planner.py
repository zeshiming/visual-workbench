from src.core.planner import parse_agent_plan


def test_parse_agent_plan_validates_structured_steps() -> None:
    plan = parse_agent_plan(
        '{"version":"1","goal":"提亮人物","execution":"hybrid",'
        '"steps":[{"id":"edit","tool":"apply_ai_edit",'
        '"params":{"preserve_original_plate":true,"edit_prompt":"局部提亮"},'
        '"depends_on":[],"rationale":"处理局部光线"},'
        '{"id":"validate","tool":"validate_result","params":{},'
        '"depends_on":["edit"],"rationale":"检查结果"}]}'
    )

    assert plan.execution == "hybrid"
    assert plan.steps[-1].tool == "validate_result"
