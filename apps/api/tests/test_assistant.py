from src.core.assistant import parse_assistant_reply
from src.models.schemas import AssistantRequest


def test_assistant_parser_routes_edit_to_agent_preview() -> None:
    parsed = parse_assistant_reply(
        '{"reply":"我建议先预览一个保守的局部提亮计划。",'
        '"intent":"edit","action":"none","suggested_prompt":"只提亮人物面部"}'
    )
    assert parsed.intent == "edit"
    assert parsed.action == "preview_edit"
    assert parsed.suggested_prompt == "只提亮人物面部"


def test_assistant_parser_falls_back_for_plain_gateway_text() -> None:
    parsed = parse_assistant_reply("这张照片的前景偏暗。")
    assert parsed.intent == "answer"
    assert parsed.action == "none"
    assert parsed.reply == "这张照片的前景偏暗。"


def test_assistant_request_has_bounded_history() -> None:
    request = AssistantRequest(
        config={
            "analysis": {"host": "https://example.com/v1", "key": "", "model": "analysis"},
            "edit": {"host": "https://example.com/v1", "key": "", "model": "edit"},
        },
        content={"image": "data:image/png;base64,abc", "content": "分析这张图"},
        history=[{"role": "user", "content": "上一轮"}],
    )
    assert request.history[0].role == "user"
