"""Thin HTTP layer for the Agent workflow.

Delegates all business logic to core.orchestration.run_agent().
Uses StreamingResponse so the frontend gets real-time progress.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from ..core.orchestration import run_agent
from ..models.schemas import AgentRunRequest, BatchToolRequest
from ..models.settings import BatchJobRecord, AssetRecord, WORKSPACE_IMAGES_DIR, WorkspaceRecord, get_session
from ..services.color_match import match_reference_color
from ..services.image_utils import apply_basic_image_adjustments, estimate_auto_white_balance
from ..services.style_tools import apply_style

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


@dataclass
class _BatchJob:
    id: str
    workspace_id: str
    request: BatchToolRequest
    queue: asyncio.Queue[dict[str, object] | None] = field(default_factory=asyncio.Queue)
    pause_event: asyncio.Event = field(default_factory=asyncio.Event)
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task[None] | None = None
    status: str = "queued"
    failures: list[str] = field(default_factory=list)
    processed_ids: list[str] = field(default_factory=list)
    processed: int = 0
    total: int = 0


_BATCH_JOBS: dict[str, _BatchJob] = {}
_BATCH_QUEUE: asyncio.PriorityQueue[tuple[int, int, str]] | None = None
_BATCH_WORKERS: list[asyncio.Task[None]] = []
_BATCH_WORKER_COUNT = 2


def _priority_rank(priority: str) -> int:
    return {"high": 0, "normal": 1, "low": 2}.get(priority, 1)


def _ensure_batch_workers() -> None:
    global _BATCH_QUEUE
    if _BATCH_QUEUE is None:
        _BATCH_QUEUE = asyncio.PriorityQueue()
    active = [worker for worker in _BATCH_WORKERS if not worker.done()]
    _BATCH_WORKERS[:] = active
    while len(_BATCH_WORKERS) < _BATCH_WORKER_COUNT:
        _BATCH_WORKERS.append(asyncio.create_task(_batch_worker()))


async def _batch_worker() -> None:
    assert _BATCH_QUEUE is not None
    while True:
        _, _, job_id = await _BATCH_QUEUE.get()
        job = _BATCH_JOBS.get(job_id)
        try:
            if job is None:
                continue
            if job.cancel_event.is_set() or job.status == "cancelling":
                job.status = "cancelled"
                await _emit_batch_event(job, {"type": "cancelled", "jobId": job.id, "processed": job.processed, "total": job.total})
                await job.queue.put(None)
                continue
            if job.status not in {"queued", "paused"}:
                continue
            await _run_batch_job(job)
        finally:
            _BATCH_QUEUE.task_done()


def _persist_batch_job(db: Session, job: _BatchJob) -> None:
    record = db.get(BatchJobRecord, job.id)
    if record is None:
        return
    record.status = job.status
    record.total = job.total
    record.processed = job.processed
    record.processed_asset_ids_json = json.dumps(job.processed_ids)
    record.failure_ids_json = json.dumps(job.failures)
    record.updated_at = int(time.time() * 1000)
    db.add(record)
    db.commit()


def _asset_path(item: AssetRecord) -> str:
    extension = os.path.splitext(item.filename)[1].lower().lstrip(".") or item.media_type.split("/")[-1]
    return os.path.join(WORKSPACE_IMAGES_DIR, "assets", f"{item.id}.{extension}")


def _asset_preview_path(item: AssetRecord) -> str:
    return f"{_asset_path(item)}.preview.jpg"


def _load_asset_data_url(item: AssetRecord) -> str:
    is_raw = os.path.splitext(item.filename)[1].lower() in {
        ".arw", ".cr2", ".cr3", ".dng", ".nef", ".orf", ".pef", ".raf", ".rw2", ".srw",
    }
    path = _asset_preview_path(item) if is_raw else _asset_path(item)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"素材文件不存在: {item.filename}")
    with open(path, "rb") as source:
        content_type = "image/jpeg" if is_raw else item.media_type
        return f"data:{content_type};base64,{base64.b64encode(source.read()).decode('ascii')}"


def _save_batch_output(
    db: Session,
    workspace_id: str,
    source: AssetRecord,
    output_data_url: str,
) -> AssetRecord:
    prefix = os.path.splitext(os.path.basename(source.filename))[0]
    filename = f"{prefix}-agent.png"
    item = AssetRecord(
        id=uuid.uuid4().hex,
        workspace_id=workspace_id,
        filename=filename,
        media_type="image/png",
        kind="edit",
        created_at=int(time.time() * 1000),
        size_bytes=len(base64.b64decode(output_data_url.split(",", 1)[1])),
    )
    path = _asset_path(item)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as output:
        output.write(base64.b64decode(output_data_url.split(",", 1)[1]))
    try:
        db.add(item)
        db.commit()
        db.refresh(item)
    except Exception:
        if os.path.isfile(path):
            os.remove(path)
        raise
    return item


async def _emit_batch_event(job: _BatchJob, event: dict[str, object]) -> None:
    await job.queue.put(event)


async def _run_batch_job(job: _BatchJob) -> None:
    workspace_id = job.workspace_id
    request = job.request
    try:
        while not job.pause_event.is_set():
            job.status = "paused"
            with get_session() as paused_db:
                _persist_batch_job(paused_db, job)
            if job.cancel_event.is_set():
                job.status = "cancelled"
                with get_session() as cancelled_db:
                    _persist_batch_job(cancelled_db, job)
                await _emit_batch_event(job, {"type": "cancelled", "jobId": job.id, "processed": job.processed, "total": job.total})
                await job.queue.put(None)
                return
            await asyncio.sleep(0.05)

        with get_session() as db:
            if db.get(WorkspaceRecord, workspace_id) is None:
                raise ValueError("Workspace not found")

            all_items = db.exec(
                select(AssetRecord).where(AssetRecord.workspace_id == workspace_id)
            ).all()
            by_id = {item.id: item for item in all_items}
            if request.feedbackId and request.feedbackId.strip():
                needle = request.feedbackId.strip().lower()
                selected = [item for item in all_items if needle in item.filename.lower()]
            else:
                selected = [by_id[item_id] for item_id in dict.fromkeys(request.assetIds) if item_id in by_id]
            excluded = set(request.excludeAssetIds)
            selected = [item for item in selected if item.id not in excluded]
            selected = selected[:200]
            if not selected:
                raise ValueError("没有找到可处理的照片")

            reference_data_url = None
            if request.operation == "reference_color":
                if request.referenceImage:
                    reference_data_url = request.referenceImage
                elif not request.referenceAssetId or request.referenceAssetId not in by_id:
                    raise ValueError("参考图不存在")
                else:
                    reference_data_url = _load_asset_data_url(by_id[request.referenceAssetId])

            if request.operation == "style" and not request.styleId:
                raise ValueError("风格化操作需要 styleId")

            job.status = "running"
            job.total = len(selected)
            _persist_batch_job(db, job)
            await _emit_batch_event(job, {"type": "start", "jobId": job.id, "total": len(selected)})
            for source in selected:
                while not job.pause_event.is_set():
                    job.status = "paused"
                    if job.cancel_event.is_set():
                        job.status = "cancelled"
                        _persist_batch_job(db, job)
                        await _emit_batch_event(job, {"type": "cancelled", "processed": job.processed, "total": len(selected)})
                        return
                    await asyncio.sleep(0.05)
                if job.cancel_event.is_set():
                    job.status = "cancelled"
                    _persist_batch_job(db, job)
                    await _emit_batch_event(job, {"type": "cancelled", "processed": job.processed, "total": len(selected)})
                    return
                job.status = "running"
                try:
                    source_data_url = _load_asset_data_url(source)
                    if request.operation == "adjustments":
                        output_data_url = apply_basic_image_adjustments(source_data_url, request.adjustments)
                    elif request.operation == "white_balance":
                        adjustments = {**request.adjustments, **estimate_auto_white_balance(source_data_url)}
                        output_data_url = apply_basic_image_adjustments(source_data_url, adjustments)
                    elif request.operation == "style":
                        output_data_url = apply_style(source_data_url, style_id=request.styleId)
                    else:
                        output_data_url = match_reference_color(source_data_url, reference_data_url or "")
                    output = _save_batch_output(db, workspace_id, source, output_data_url)
                    job.processed += 1
                    job.processed_ids.append(source.id)
                    _persist_batch_job(db, job)
                    await _emit_batch_event(job, {
                        "type": "progress",
                        "jobId": job.id,
                        "processed": job.processed,
                        "total": len(selected),
                        "sourceId": source.id,
                        "outputId": output.id,
                        "filename": output.filename,
                    })
                except Exception as exc:
                    job.failures.append(source.id)
                    job.processed += 1
                    _persist_batch_job(db, job)
                    await _emit_batch_event(job, {
                        "type": "error",
                        "jobId": job.id,
                        "processed": job.processed,
                        "total": len(selected),
                        "sourceId": source.id,
                        "filename": source.filename,
                        "message": str(exc),
                    })

            job.status = "completed"
            _persist_batch_job(db, job)
            await _emit_batch_event(job, {"type": "done", "jobId": job.id, "processed": job.processed, "total": len(selected)})
    except Exception as exc:
        logger.exception("Batch tool run failed")
        job.status = "failed"
        with get_session() as db:
            _persist_batch_job(db, job)
        await _emit_batch_event(job, {"type": "error", "jobId": job.id, "message": str(exc)})
    finally:
        await job.queue.put(None)


def _start_batch_job(workspace_id: str, request: BatchToolRequest) -> _BatchJob:
    job = _BatchJob(id=uuid.uuid4().hex, workspace_id=workspace_id, request=request)
    job.pause_event.set()
    now = int(time.time() * 1000)
    with get_session() as db:
        db.add(BatchJobRecord(
            id=job.id,
            workspace_id=workspace_id,
            request_json=request.model_dump_json(),
            status=job.status,
            created_at=now,
            updated_at=now,
        ))
        db.commit()
    _BATCH_JOBS[job.id] = job
    _ensure_batch_workers()
    assert _BATCH_QUEUE is not None
    _BATCH_QUEUE.put_nowait((_priority_rank(request.priority), now, job.id))
    return job


async def _batch_job_event_stream(job: _BatchJob):
    while True:
        event = await job.queue.get()
        if event is None:
            break
        yield json.dumps(event) + "\n"


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
            analysis, analysis_raw, images, text, plan, tool_trace = await run_agent(
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
                    "plan": plan,
                    "tool_trace": tool_trace,
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


@router.post("/batch/{workspace_id}")
async def handle_batch_tool_run(workspace_id: str, request: BatchToolRequest):
    """Start one deterministic tool operation over selected workspace assets."""

    job = _start_batch_job(workspace_id, request)
    return {"jobId": job.id, "status": job.status}


@router.get("/batch/queue")
async def get_batch_queue():
    active = [
        {
            "jobId": job.id,
            "workspaceId": job.workspace_id,
            "status": job.status,
            "priority": job.request.priority,
            "processed": job.processed,
            "total": job.total,
        }
        for job in _BATCH_JOBS.values()
        if job.status in {"queued", "running", "paused", "cancelling"}
    ]
    return {"workerCount": _BATCH_WORKER_COUNT, "jobs": active}


@router.get("/batch/jobs/{job_id}/events")
async def handle_batch_job_events(job_id: str):
    job = _BATCH_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Batch job not found")

    return StreamingResponse(
        _batch_job_event_stream(job),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/batch/jobs/{job_id}")
async def get_batch_job(job_id: str):
    job = _BATCH_JOBS.get(job_id)
    if job is not None:
        return {
            "jobId": job.id,
            "status": job.status,
            "processed": job.processed,
            "total": job.total,
            "failureIds": job.failures,
        }
    with get_session() as db:
        record = db.get(BatchJobRecord, job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Batch job not found")
        return {
            "jobId": record.id,
            "status": record.status,
            "processed": record.processed,
            "total": record.total,
            "failureIds": json.loads(record.failure_ids_json),
        }


@router.post("/batch/jobs/{job_id}/pause")
async def pause_batch_job(job_id: str):
    job = _BATCH_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Batch job not found")
    if job.status in {"completed", "failed", "cancelled"}:
        return {"jobId": job.id, "status": job.status}
    job.pause_event.clear()
    job.status = "paused"
    await _emit_batch_event(job, {"type": "status", "jobId": job.id, "status": "paused"})
    return {"jobId": job.id, "status": job.status}


@router.post("/batch/jobs/{job_id}/resume")
async def resume_batch_job(job_id: str):
    job = _BATCH_JOBS.get(job_id)
    if job is None:
        with get_session() as db:
            record = db.get(BatchJobRecord, job_id)
            if record is None:
                raise HTTPException(status_code=404, detail="Batch job not found")
            if record.status != "interrupted":
                return {"jobId": record.id, "status": record.status}
            request = BatchToolRequest.model_validate_json(record.request_json)
            excluded = set(request.excludeAssetIds)
            excluded.update(json.loads(record.processed_asset_ids_json))
            resumed = _start_batch_job(
                record.workspace_id,
                request.model_copy(update={"excludeAssetIds": sorted(excluded)}),
            )
            return {"jobId": resumed.id, "status": resumed.status, "resumedFrom": record.id}
    if job.status not in {"paused", "running"}:
        return {"jobId": job.id, "status": job.status}
    job.pause_event.set()
    job.status = "running"
    await _emit_batch_event(job, {"type": "status", "jobId": job.id, "status": "running"})
    return {"jobId": job.id, "status": job.status}


@router.post("/batch/jobs/{job_id}/cancel")
async def cancel_batch_job(job_id: str):
    job = _BATCH_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Batch job not found")
    if job.status not in {"completed", "failed", "cancelled"}:
        job.cancel_event.set()
        job.pause_event.set()
        job.status = "cancelling"
        await _emit_batch_event(job, {"type": "status", "jobId": job.id, "status": "cancelling"})
    return {"jobId": job.id, "status": job.status}


@router.post("/batch/jobs/{job_id}/retry")
async def retry_batch_job(job_id: str):
    job = _BATCH_JOBS.get(job_id)
    if job is not None:
        workspace_id = job.workspace_id
        failures = job.failures
        request = job.request
    else:
        with get_session() as db:
            record = db.get(BatchJobRecord, job_id)
            if record is None:
                raise HTTPException(status_code=404, detail="Batch job not found")
            workspace_id = record.workspace_id
            failures = json.loads(record.failure_ids_json)
            request = BatchToolRequest.model_validate_json(record.request_json)
    if not failures:
        raise HTTPException(status_code=409, detail="没有可重试的失败素材")
    retry_request = request.model_copy(
        update={"assetIds": list(dict.fromkeys(failures)), "feedbackId": None, "excludeAssetIds": []},
    )
    retry_job = _start_batch_job(workspace_id, retry_request)
    return {"jobId": retry_job.id, "status": retry_job.status, "retryOf": job_id}
