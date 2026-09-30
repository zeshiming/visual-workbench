from src.services.ai_client import _extract_image_edit_input, _is_qwen_image_model, _qwen_image_endpoint


def test_qwen_image_endpoint_and_model_detection() -> None:
    assert _is_qwen_image_model("qwen-image-3.0")
    assert _is_qwen_image_model("qwen-image-3.0-pro")
    assert not _is_qwen_image_model("gpt-image-2")
    assert _qwen_image_endpoint("https://workspace.cn-beijing.maas.aliyuncs.com/compatible-mode/v1") == (
        "https://workspace.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/images/generations"
    )


def test_extract_qwen_edit_prompt_and_image() -> None:
    prompt, images = _extract_image_edit_input([
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
                {"type": "text", "text": "提高人物面部光线，保持构图"},
            ],
        },
    ])
    assert prompt == "提高人物面部光线，保持构图"
    assert images == ["data:image/png;base64,abc"]
