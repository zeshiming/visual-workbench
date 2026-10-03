from src.services.ai_client import _responses_endpoint, _responses_input, _should_use_responses


def test_responses_analysis_routing() -> None:
    assert _should_use_responses("https://mirror.fufu666.top/v1", "gpt-6-astra")
    assert not _should_use_responses("https://api.openrouter.ai/v1", "gpt-6-astra")
    assert _responses_endpoint("https://mirror.fufu666.top/v1") == "https://mirror.fufu666.top/v1/responses"


def test_responses_input_converts_image_url_parts() -> None:
    instructions, items = _responses_input([
        {"role": "system", "content": "Analyze conservatively."},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc", "detail": "high"}},
                {"type": "text", "text": "分析这张照片"},
            ],
        },
    ])
    assert instructions == "Analyze conservatively."
    assert items[0]["type"] == "input_image"
    assert items[1] == {"type": "input_text", "text": "分析这张照片"}
