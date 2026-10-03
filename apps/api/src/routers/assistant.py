"""Contextual AI Assistant API.

The Assistant is intentionally separate from image generation: it can inspect
the current image, answer, and propose an Agent action without spending an edit
model call. The frontend may then hand ``suggested_prompt`` to Agent preview.
"""

from __future__ import annotations

import json
import time
import uuid

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from ..core.assistant import ASSISTANT_SYSTEM_PROMPT, parse_assistant_reply
from ..core.policy import validate_agent_input
from ..models.schemas import AssistantRequest, AssistantResponse, AssistantSessionCreate
from ..models.settings import AssistantMessageRecord, AssistantSessionRecord, get_session
from ..services.ai_client import litellm_completion

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


@router.post("/sessions")
async def create_session(request: AssistantSessionCreate):
    now = int(time.time() * 1000)
    record = AssistantSessionRecord(id=uuid.uuid4().hex, workspace_id=request.workspace_id,
                                    asset_id=request.asset_id, current_version=request.current_version,
                                    created_at=now, updated_at=now)
    with get_session() as db:
        db.add(record)
        db.commit()
        return {"sessionId": record.id, "workspaceId": record.workspace_id, "currentVersion": record.current_version}


@router.get("/sessions/{session_id}")
async def get_session_history(session_id: str):
    with get_session() as db:
        session = db.get(AssistantSessionRecord, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Assistant session not found")
        messages = db.exec(select(AssistantMessageRecord).where(
            AssistantMessageRecord.session_id == session_id,
        ).order_by(AssistantMessageRecord.created_at)).all()
        return {"sessionId": session.id, "workspaceId": session.workspace_id, "currentVersion": session.current_version,
                "messages": [m.model_dump() for m in messages]}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    with get_session() as db:
        session = db.get(AssistantSessionRecord, session_id)
        if session is not None:
            db.delete(session)
            for message in db.exec(select(AssistantMessageRecord).where(AssistantMessageRecord.session_id == session_id)).all():
                db.delete(message)
            db.commit()
    return {"ok": True}


@router.post("/respond", response_model=AssistantResponse)
async def respond_to_assistant(request: AssistantRequest) -> AssistantResponse:
    try:
        validate_agent_input(prompt=request.content.content, image_data_url=request.content.image)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "INVALID_ASSISTANT_INPUT", "message": str(exc)}) from exc

    stored_history = request.history
    if request.session_id:
        with get_session() as db:
            session = db.get(AssistantSessionRecord, request.session_id)
            if session is None or (request.workspace_id and session.workspace_id != request.workspace_id):
                raise HTTPException(status_code=404, detail="Assistant session not found")
            stored_history = [
                {"role": item.role, "content": item.content}
                for item in db.exec(select(AssistantMessageRecord).where(
                    AssistantMessageRecord.session_id == request.session_id,
                ).order_by(AssistantMessageRecord.created_at)).all()
            ]
    def history_line(item: object) -> str:
        if isinstance(item, dict):
            role, content = item.get("role", "assistant"), item.get("content", "")
        else:
            role, content = item.role, item.content
        return f"{('用户' if role == 'user' else 'AI 助理')}：{content}"
    history_text = "\n".join(history_line(item) for item in stored_history[-10:]) or "（这是当前任务的第一轮）"
    messages: list[dict[str, object]] = [{"role": "system", "content": ASSISTANT_SYSTEM_PROMPT}]
    messages.append({
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": request.content.image, "detail": "high"}},
            {"type": "text", "text": json.dumps({
                "current_version": request.current_version,
                "conversation_history": history_text,
                "request": request.content.content,
            }, ensure_ascii=False)},
        ],
    })

    result = await litellm_completion(
        host=request.config.analysis.host,
        api_key=request.config.analysis.key,
        model=request.config.analysis.model,
        messages=messages,
    )
    parsed = parse_assistant_reply(result.get("text") or "", fallback_prompt=request.content.content)
    message_id = None
    if request.session_id:
        now = int(time.time() * 1000)
        message_id = uuid.uuid4().hex
        with get_session() as db:
            session = db.get(AssistantSessionRecord, request.session_id)
            db.add(AssistantMessageRecord(id=uuid.uuid4().hex, session_id=request.session_id, role="user",
                                          content=request.content.content, version=request.current_version, created_at=now))
            db.add(AssistantMessageRecord(id=message_id, session_id=request.session_id, role="assistant",
                                          content=parsed.reply, intent=parsed.intent, action=parsed.action,
                                          suggested_prompt=parsed.suggested_prompt, version=request.current_version,
                                          created_at=now + 1))
            session.current_version = request.current_version
            session.updated_at = now + 1
            db.add(session)
            db.commit()
    return AssistantResponse(
        session_id=request.session_id,
        message_id=message_id,
        reply=parsed.reply,
        intent=parsed.intent,
        action=parsed.action,
        suggested_prompt=parsed.suggested_prompt,
        trace=result.get("trace") or {},
    )
