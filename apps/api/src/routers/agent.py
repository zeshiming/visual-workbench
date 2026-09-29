"""Thin HTTP layer for the Agent workflow.

Delegates all business logic to core.orchestration.run_agent().
Uses StreamingResponse so the frontend gets real-time progress.
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..core.orchestration import run_agent
from ..models.schemas import AgentRunRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


async def _agent_event_stream(request: AgentRunRequest):
    """Async generator that yields JSON lines:

    {"type":"progress","phase":"analysis"}
    {"type":"progress","phase":"edit"}
    {"type":"result","analysis":...,"analysis_raw":...,"images":...,"text":...}
    {"type":"error","message":"..."}
    """
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def _on_progress(phase: str) -> None:
        """Async callback — called from run_agent via await on_progress(...)."""
        await queue.put(json.dumps({"type": "progress", "phase": phase}) + "\n")

    async def _run():
        try:
            analysis, analysis_raw, images, text = await run_agent(
                analysis_host=request.config.analysis.host,
                analysis_api_key=request.config.analysis.key,
                analysis_model=request.config.analysis.model,
                edit_host=request.config.edit.host,
                edit_api_key=request.config.edit.key,
                edit_model=request.config.edit.model,
                image_data_url=request.content.image,
                user_prompt=request.content.content,
                on_progress=_on_progress,
            )

            await queue.put(
                json.dumps({
                    "type": "result",
                    "analysis": analysis.to_dict(),
                    "analysis_raw": analysis_raw,
                    "images": images,
                    "text": text,
                }) + "\n"
            )
        except Exception as exc:
            logger.exception("Agent run failed")
            await queue.put(json.dumps({"type": "error", "message": str(exc)}) + "\n")
        finally:
            # Signal end of stream
            await queue.put(None)

    # Start the agent run in background
    task = asyncio.create_task(_run())

    # Yield events as they come in
    while True:
        event = await queue.get()
        if event is None:
            break
        yield event

    await task


@router.post("/run")
async def handle_agent_run(request: AgentRunRequest):
    return StreamingResponse(
        _agent_event_stream(request),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
