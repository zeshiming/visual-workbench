"""Contracts and prompts for the contextual photography Assistant."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field


ASSISTANT_SYSTEM_PROMPT = """你是摄影创作工作台里的 AI 助理，不是客服机器人，也不是直接修图模型。

你的职责是理解当前照片和用户任务，回答问题、解释后期建议，并判断是否应该把任务交给已有的 Agent 修图流程。

你可以处理三类事情：
1. answer：分析当前照片、解释问题、解释工具选择或给出摄影后期建议；不要求修改图片。
2. edit：用户明确要求修改当前照片，例如提亮脸部、降低高光、保留背景；请生成一条可交给 Agent 修图的简洁指令。
3. workflow：用户要求查找照片、批量处理、追色、恢复版本或导出；请说明建议的下一步工作流。

规则：
- 当前对话不直接调用图片生成模型，不假装已经修改成功。
- edit 必须保持原图身份、构图、主体和尺寸不变，除非用户明确要求改变。
- 对不确定的问题要诚实说明，不要虚构图片中看不到的内容。
- 用户的后续消息可能使用“再自然一点”“刚才那张”“恢复上一版”等省略表达，要结合当前照片和历史理解。
- 只输出一个 JSON 对象，不要 Markdown 代码块：
{
  "reply": "给用户看的简洁中文回复",
  "intent": "answer | edit | workflow",
  "action": "none | preview_edit | workflow",
  "suggested_prompt": "当 intent=edit 时，给 Agent 的完整修图指令；否则为空"
}

当 intent=edit 时 action 必须是 preview_edit；当 intent=answer 时 action 是 none；当 intent=workflow 时 action 是 workflow。"""


class ParsedAssistantReply(BaseModel):
    reply: str = Field(min_length=1, max_length=12_000)
    intent: Literal["answer", "edit", "workflow"] = "answer"
    action: Literal["none", "preview_edit", "workflow"] = "none"
    suggested_prompt: str = Field(default="", max_length=12_000)


def _strip_json_fence(text: str) -> str:
    value = text.strip()
    if value.startswith("```"):
        value = value.removeprefix("```json").removeprefix("```").strip()
        value = value.removesuffix("```").strip()
    return value


def parse_assistant_reply(raw: str, *, fallback_prompt: str = "") -> ParsedAssistantReply:
    """Parse structured output while keeping the Assistant useful on weak gateways."""

    cleaned = _strip_json_fence(raw)
    try:
        payload = json.loads(cleaned)
        parsed = ParsedAssistantReply.model_validate(payload)
    except (json.JSONDecodeError, ValueError):
        return ParsedAssistantReply(
            reply=raw.strip() or "我暂时无法理解这条请求，请换一种方式描述。",
            intent="answer",
            action="none",
            suggested_prompt="",
        )

    if parsed.intent == "edit":
        parsed.action = "preview_edit"
        if not parsed.suggested_prompt:
            parsed.suggested_prompt = fallback_prompt
    elif parsed.intent == "answer":
        parsed.action = "none"
        parsed.suggested_prompt = ""
    else:
        parsed.action = "workflow"
        parsed.suggested_prompt = ""
    return parsed
