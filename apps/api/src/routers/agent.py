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
import socket
import time
import uuid
from dataclasses import dataclass, field

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import update as sql_update
from sqlmodel import Session, select

from ..core.agent_loop import AgentLoopError
from ..core.agent_tools import ToolRun
from ..core.plan_store import claim_preview, context_hash, get_claimed_preview, save_preview
from ..core.orchestration import run_agent
from ..core.agent_plan import AgentPlan, build_plan_from_analysis
from ..core.analysis import parse_agent_analysis
from ..core.planner import generate_agent_plan
from ..core.prompts import get_analysis_system_prompt
from ..core.policy import (
    validate_agent_input,
    validate_agent_plan,
    validate_agent_plan_shape,
    validate_agent_status_transition,
)
from ..core.tool_registry import tool_registry
from ..services.ai_client import litellm_completion
from ..models.schemas import AgentRunRequest, BatchToolRequest
from ..models.settings import AgentEventRecord, AgentPlanRecord, AgentRunRecord, AgentStepRecord, BatchJobRecord, AssetRecord, WORKSPACE_IMAGES_DIR, WorkspaceRecord, get_session, load_agent_result_file, load_agent_step_file, save_agent_result_file, save_agent_step_file
from ..core.agent_plan import tool_catalog_as_dicts
from ..mcp.registry import McpServerConfig, mcp_server_registry
from ..mcp.adapter import discover_mcp_tools
from ..mcp.client import get_mcp_client
from ..skills.registry import SkillManifest, skill_registry
from ..services.color_match import match_reference_color
from ..services.image_utils import apply_basic_image_adjustments, estimate_auto_white_balance
from ..services.extension_store import delete_mcp_config, delete_skill_manifest, save_mcp_config, save_skill_manifest
from ..services.style_tools import apply_style

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


@router.get("/extensions")
async def list_agent_extensions():
    """Expose the extension catalog without enabling concrete external services."""

    return {
        "nativeTools": tool_catalog_as_dicts(),
        "toolRegistry": tool_registry.summaries(),
        "skills": skill_registry.summaries(),
        "mcpServers": mcp_server_registry.summaries(),
    }


@router.post("/extensions/mcp/{server_id}/discover")
async def discover_mcp_extension(server_id: str):
    try:
        tools = await discover_mcp_tools(server_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"code": "MCP_DISCOVERY_FAILED", "message": str(exc)}) from exc
    return {"serverId": server_id, "tools": tools}


@router.post("/extensions/mcp/{server_id}/check")
async def check_mcp_extension(server_id: str):
    try:
        client = get_mcp_client(server_id)
        result = await client.initialize()
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"code": "MCP_CONNECTION_FAILED", "message": str(exc)}) from exc
    return {
        "serverId": server_id,
        "reachable": True,
        "protocolVersion": result.get("protocolVersion") if isinstance(result, dict) else None,
    }


@router.post("/extensions/mcp")
async def add_mcp_extension(server: McpServerConfig):
    """Register a controlled MCP endpoint; registration never enables it."""
    server = server.model_copy(update={"enabled": False})
    mcp_server_registry.register(server)
    save_mcp_config(server)
    return {"server": server.model_dump(), "enabled": False}


@router.put("/extensions/mcp/{server_id}")
async def update_mcp_extension(server_id: str, server: McpServerConfig):
    if server.id != server_id:
        raise HTTPException(status_code=422, detail="路径 server_id 与配置 id 不一致")
    previous = mcp_server_registry.get(server_id)
    if previous is None:
        raise HTTPException(status_code=404, detail="MCP Server 不存在")
    updated = server.model_copy(update={"enabled": previous.enabled and server.enabled})
    mcp_server_registry.register(updated)
    save_mcp_config(updated)
    return {"server": updated.model_dump()}


@router.post("/extensions/mcp/{server_id}/enable")
async def enable_mcp_extension(server_id: str):
    try:
        server = mcp_server_registry.set_enabled(server_id, True)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="MCP Server 不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    save_mcp_config(server)
    return {"server": server.model_dump()}


@router.post("/extensions/mcp/{server_id}/disable")
async def disable_mcp_extension(server_id: str):
    try:
        server = mcp_server_registry.set_enabled(server_id, False)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="MCP Server 不存在") from exc
    save_mcp_config(server)
    return {"server": server.model_dump()}


@router.post("/extensions/mcp/{server_id}/allow-tool")
async def allow_mcp_tool(server_id: str, tool_name: str):
    server = mcp_server_registry.get(server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP Server 不存在")
    if not tool_name.strip() or len(tool_name) > 128:
        raise HTTPException(status_code=422, detail="工具名无效")
    allowed = list(dict.fromkeys([*server.allowed_tools, tool_name.strip()]))
    server = server.model_copy(update={"allowed_tools": allowed})
    mcp_server_registry.register(server)
    save_mcp_config(server)
    return {"server": server.model_dump()}


@router.post("/extensions/mcp/{server_id}/deny-tool")
async def deny_mcp_tool(server_id: str, tool_name: str):
    server = mcp_server_registry.get(server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP Server 不存在")
    server = server.model_copy(update={"allowed_tools": [name for name in server.allowed_tools if name != tool_name]})
    mcp_server_registry.register(server)
    save_mcp_config(server)
    return {"server": server.model_dump()}


@router.delete("/extensions/mcp/{server_id}")
async def remove_mcp_extension(server_id: str):
    if not mcp_server_registry.remove(server_id):
        raise HTTPException(status_code=404, detail="MCP Server 不存在")
    delete_mcp_config(server_id)
    return {"serverId": server_id, "removed": True}


@router.post("/extensions/skills")
async def add_skill_extension(skill: SkillManifest):
    skill = skill.model_copy(update={"enabled": False})
    skill_registry.register(skill)
    save_skill_manifest(skill)
    return {"skill": skill_registry.get(skill.id).model_dump(), "enabled": False}


@router.post("/extensions/skills/{skill_id}/enable")
async def enable_skill_extension(skill_id: str):
    try:
        skill = skill_registry.set_enabled(skill_id, True)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Skill 不存在") from exc
    save_skill_manifest(skill)
    return {"skill": skill.model_dump()}


@router.post("/extensions/skills/{skill_id}/disable")
async def disable_skill_extension(skill_id: str):
    try:
        skill = skill_registry.set_enabled(skill_id, False)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Skill 不存在") from exc
    save_skill_manifest(skill)
    return {"skill": skill.model_dump()}


@router.delete("/extensions/skills/{skill_id}")
async def remove_skill_extension(skill_id: str):
    if not skill_registry.remove(skill_id):
        raise HTTPException(status_code=404, detail="Skill 不存在")
    delete_skill_manifest(skill_id)
    return {"skillId": skill_id, "removed": True}


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
@dataclass
class _AgentControl:
    pause_event: asyncio.Event = field(default_factory=asyncio.Event)
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    status: str = "running"


_AGENT_CONTROLS: dict[str, _AgentControl] = {}
WORKER_ID = f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
LEASE_SECONDS = 60
TERMINAL_AGENT_STATUSES = {"completed", "failed", "cancelled", "needs_review", "interrupted"}


def _persist_agent_run(
    run_id: str,
    *,
    status: str,
    request_summary: dict | None = None,
    plan: dict | None = None,
    trace: dict | None = None,
    result: dict | None = None,
    error: str = "",
) -> None:
    with get_session() as db:
        record = db.get(AgentRunRecord, run_id)
        if record is None:
            now = int(time.time() * 1000)
            record = AgentRunRecord(id=run_id, created_at=now, updated_at=now)
        validate_agent_status_transition(record.status, status)
        record.status = status
        if request_summary is not None:
            record.request_summary_json = json.dumps(request_summary, ensure_ascii=False)
        if plan is not None:
            record.plan_json = json.dumps(plan, ensure_ascii=False)
        if trace is not None:
            record.trace_json = json.dumps(trace, ensure_ascii=False)
        if result is not None:
            record.result_path = save_agent_result_file(run_id, result)
        record.error = error
        record.updated_at = int(time.time() * 1000)
        if status in TERMINAL_AGENT_STATUSES:
            record.lease_owner = ""
            record.lease_expires_at = 0
        else:
            record.lease_owner = WORKER_ID
            record.lease_expires_at = int(time.time()) + LEASE_SECONDS
        db.add(record)
        last_event = db.exec(select(AgentEventRecord).where(
            AgentEventRecord.run_id == run_id,
        ).order_by(AgentEventRecord.sequence.desc())).first()
        db.add(AgentEventRecord(
            id=uuid.uuid4().hex,
            run_id=run_id,
            sequence=(last_event.sequence + 1) if last_event else 1,
            event_type="state",
            status=status,
            payload_json=json.dumps({"error": error} if error else {}, ensure_ascii=False),
            created_at=record.updated_at,
        ))
        db.commit()
        if trace is not None:
            attempts = trace.get("attemptHistory", []) if isinstance(trace, dict) else []
            trace_runs: list[tuple[int, dict]] = []
            if isinstance(attempts, list) and attempts:
                for attempt in attempts:
                    if not isinstance(attempt, dict):
                        continue
                    attempt_number = int(attempt.get("attempt", 1))
                    for run in attempt.get("runs", []):
                        if isinstance(run, dict):
                            trace_runs.append((attempt_number, run))
            else:
                runs = trace.get("runs", []) if isinstance(trace, dict) else []
                trace_runs = [(1, run) for run in runs if isinstance(run, dict)]
            for index, (attempt_number, run) in enumerate(trace_runs):
                if not isinstance(run, dict):
                    continue
                step_id = str(run.get("stepId", index))
                existing = db.exec(select(AgentStepRecord).where(
                    AgentStepRecord.run_id == run_id,
                    AgentStepRecord.step_id == step_id,
                    AgentStepRecord.attempt == attempt_number,
                )).first()
                # Tool callbacks persist a checkpoint immediately after each
                # step. The final trace is still persisted for older/replayed
                # runs, but must not create a second audit row for a checkpoint
                # that already exists (and must preserve its artifact path).
                if existing is not None:
                    continue
                db.add(AgentStepRecord(
                    id=f"{run_id}:{attempt_number}:{step_id}:{index}",
                    run_id=run_id,
                    step_id=step_id,
                    tool=str(run.get("tool", "unknown")),
                    status=str(run.get("status", "unknown")),
                    attempt=attempt_number,
                    output_json=json.dumps(run, ensure_ascii=False),
                    error=str(run.get("message", "")) if run.get("status") == "failed" else "",
                    started_at=record.updated_at,
                    ended_at=record.updated_at,
                ))
            db.commit()


def _persist_agent_event(run_id: str, *, event_type: str, status: str, payload: dict) -> int:
    with get_session() as db:
        if db.get(AgentRunRecord, run_id) is None:
            return 0
        record = db.get(AgentRunRecord, run_id)
        if record and record.lease_owner == WORKER_ID:
            record.lease_expires_at = int(time.time()) + LEASE_SECONDS
            db.add(record)
        last_event = db.exec(select(AgentEventRecord).where(
            AgentEventRecord.run_id == run_id,
        ).order_by(AgentEventRecord.sequence.desc())).first()
        sequence = (last_event.sequence + 1) if last_event else 1
        db.add(AgentEventRecord(
            id=uuid.uuid4().hex, run_id=run_id,
            sequence=sequence,
            event_type=event_type, status=status,
            payload_json=json.dumps(payload, ensure_ascii=False),
            created_at=int(time.time() * 1000),
        ))
        db.commit()
        return sequence
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


async def _agent_event_stream(
    request: AgentRunRequest,
    planned_plan: AgentPlan,
    planned_analysis=None,
    planned_analysis_raw: str | None = None,
    resume_output_image: str | None = None,
    resume_step_ids: set[str] | None = None,
):
    """Async generator that yields JSON lines:

    {"type":"progress","phase":"analysis"}
    {"type":"progress","phase":"edit"}
    {"type":"result","analysis":...,"analysis_raw":...,"images":...,"text":...}
    {"type":"error","message":"..."}
    """
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    run_id = request.runId or uuid.uuid4().hex
    control = _AGENT_CONTROLS.get(run_id)
    if control is None:
        control = _AgentControl()
        control.pause_event.set()
        _AGENT_CONTROLS[run_id] = control
    _persist_agent_run(
        run_id,
        status=control.status,
        plan=planned_plan.model_dump(),
        request_summary={
            "analysisModel": request.config.analysis.model,
            "analysisHost": request.config.analysis.host,
            "analysisHasKey": bool(request.config.analysis.key),
            "editModel": request.config.edit.model,
            "editHost": request.config.edit.host,
            "editHasKey": bool(request.config.edit.key),
            "budget": request.budget.model_dump(),
            "imagePresent": bool(request.content.image),
            "imageLength": len(request.content.image),
            "promptLength": len(request.content.content),
            "planProvided": request.plan is not None,
            "origin": request.origin,
            "workspaceId": request.workspaceId,
            "versionId": request.versionId,
        },
    )

    async def _wait_agent_control() -> None:
        if control.cancel_event.is_set():
            raise RuntimeError("Agent 任务已取消")
        if control.pause_event.is_set():
            return
        await queue.put(json.dumps({"type": "status", "run_id": run_id, "status": "paused"}) + "\n")
        while not control.pause_event.is_set():
            if control.cancel_event.is_set():
                raise RuntimeError("Agent 任务已取消")
            await asyncio.sleep(0.05)
        control.status = "running"
        await queue.put(json.dumps({"type": "status", "run_id": run_id, "status": "running"}) + "\n")

    async def _on_progress(phase: str) -> None:
        """Async callback — called from run_agent via await on_progress(...)."""
        await _wait_agent_control()
        sequence = _persist_agent_event(
            run_id,
            event_type="progress",
            status=phase,
            payload={"phase": phase},
        )
        await queue.put(json.dumps({"type": "progress", "phase": phase, "sequence": sequence}) + "\n")

    async def _on_tool(run: ToolRun, output_image: str, attempt: int) -> None:
        payload = run.to_dict()
        artifact_path = save_agent_step_file(run_id, attempt, run.step_id, output_image)
        payload["outputArtifactPath"] = artifact_path
        with get_session() as db:
            db.add(AgentStepRecord(
                id=f"{run_id}:checkpoint:{attempt}:{run.step_id}", run_id=run_id,
                step_id=run.step_id, tool=run.tool, status=run.status, attempt=attempt,
                output_json=json.dumps(payload, ensure_ascii=False),
                output_artifact_path=artifact_path, started_at=int(time.time() * 1000),
                ended_at=int(time.time() * 1000), error=run.message if run.status == 'failed' else '',
            ))
            db.commit()
        sequence = _persist_agent_event(run_id, event_type="tool", status=run.status, payload=payload)
        await queue.put(json.dumps({"type": "tool", "run": payload, "run_id": run_id, "sequence": sequence}) + "\n")

    async def _run():
        try:
            analysis, analysis_raw, images, text, plan, tool_trace = await asyncio.wait_for(run_agent(
                analysis_host=request.config.analysis.host,
                analysis_api_key=request.config.analysis.key,
                analysis_model=request.config.analysis.model,
                edit_host=request.config.edit.host,
                edit_api_key=request.config.edit.key,
                edit_model=request.config.edit.model,
                image_data_url=request.content.image,
                user_prompt=request.content.content,
                planned_plan=planned_plan,
                planned_analysis=planned_analysis,
                planned_analysis_raw=planned_analysis_raw,
                resume_output_image=resume_output_image,
                resume_step_ids=resume_step_ids,
                idempotency_key=f"doushabao-{run_id}-image-edit",
                max_image_calls=request.budget.max_image_calls,
                on_progress=_on_progress,
                on_tool=_on_tool,
            ), timeout=request.budget.deadline_seconds)

            # Cancellation can arrive while a provider request is in flight.
            # Do not publish a successful result after the user has cancelled.
            if control.cancel_event.is_set():
                raise RuntimeError("Agent 任务已取消")

            _persist_agent_run(
                run_id, status="completed", plan=plan, trace=tool_trace,
                result={
                    "analysis": analysis.to_dict(), "analysisRaw": analysis_raw,
                    "images": images, "text": text, "plan": plan, "toolTrace": tool_trace,
                },
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
                    "run_id": run_id,
                }) + "\n"
            )
        except Exception as exc:
            logger.exception("Agent run failed")
            event_type = "cancelled" if control.cancel_event.is_set() else "error"
            timed_out = isinstance(exc, asyncio.TimeoutError)
            failure_trace = exc.trace if isinstance(exc, AgentLoopError) else (
                {
                    "resultState": "unknown",
                    "loop": {"status": "needs_review"},
                    "errorCode": "DEADLINE_EXCEEDED",
                }
                if timed_out else None
            )
            needs_review = bool(
                isinstance(failure_trace, dict)
                and isinstance(failure_trace.get("loop"), dict)
                and failure_trace["loop"].get("status") == "needs_review"
            ) or timed_out
            terminal_status = "cancelled" if control.cancel_event.is_set() else ("needs_review" if needs_review else "failed")
            if needs_review:
                event_type = "needs_review"
            _persist_agent_run(
                run_id,
                status=terminal_status,
                trace=failure_trace,
                error=str(exc),
            )
            await queue.put(json.dumps({"type": event_type, "message": str(exc), "run_id": run_id}) + "\n")
        finally:
            # Signal end of stream
            await queue.put(None)
            _AGENT_CONTROLS.pop(run_id, None)

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
    try:
        validate_agent_input(prompt=request.content.content, image_data_url=request.content.image)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "INVALID_AGENT_INPUT", "message": str(exc)}) from exc

    if not request.plan or not request.approved:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "PLAN_APPROVAL_REQUIRED",
                "message": "请先预览并确认 Agent 执行计划。",
            },
        )
    try:
        planned_plan = AgentPlan.model_validate(request.plan)
        validate_agent_plan(planned_plan, approved=request.approved)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "INVALID_AGENT_PLAN", "message": str(exc)}) from exc

    # Register the control object before returning the stream. The frontend
    # exposes pause/resume/cancel as soon as fetch() returns, so creating it
    # only inside the lazy stream generator introduces a small but real race.
    run_id = request.runId or uuid.uuid4().hex
    if request.runId:
        if run_id in _AGENT_CONTROLS:
            raise HTTPException(status_code=409, detail={"code": "RUN_ALREADY_ACTIVE", "message": "该 Agent 运行正在执行中。"})
        with get_session() as db:
            if db.get(AgentRunRecord, run_id) is not None:
                raise HTTPException(status_code=409, detail={"code": "RUN_ID_EXISTS", "message": "该运行 ID 已存在，请重新发起任务。"})
    approved_analysis = None
    approved_analysis_raw = None
    try:
        with get_session() as db:
            planned_plan = claim_preview(db, request, run_id)
            approval_id = request.plan.get("approval_id") if request.plan else None
            preview_record = db.get(AgentPlanRecord, approval_id) if isinstance(approval_id, str) else None
            if preview_record is None:
                raise ValueError("执行计划快照不存在，请重新预览。")
            # Older local databases only stored the structured summary, not
            # the original model JSON. Preserve their one-time replay
            # compatibility; all new previews persist analysis_raw_json and
            # therefore take the frozen-snapshot path above.
            if preview_record.analysis_raw_json:
                approved_analysis = parse_agent_analysis(preview_record.analysis_raw_json)
                approved_analysis_raw = preview_record.analysis_raw_json
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"code": "PLAN_APPROVAL_STALE", "message": str(exc)}) from exc
    control = _AgentControl()
    control.pause_event.set()
    _AGENT_CONTROLS[run_id] = control
    return StreamingResponse(
        _agent_event_stream(
            request.model_copy(update={"runId": run_id}),
            planned_plan,
            approved_analysis,
            approved_analysis_raw,
        ),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/runs/{run_id}/pause")
async def pause_agent_run(run_id: str):
    control = _AGENT_CONTROLS.get(run_id)
    if control is None:
        raise HTTPException(status_code=404, detail="Agent 任务不存在或已结束")
    control.pause_event.clear()
    control.status = "paused"
    _persist_agent_run(run_id, status="paused")
    return {"runId": run_id, "status": control.status}


@router.get("/runs/{run_id}")
async def get_agent_run(run_id: str):
    with get_session() as db:
        record = db.get(AgentRunRecord, run_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Agent 运行不存在")
        steps = db.exec(select(AgentStepRecord).where(AgentStepRecord.run_id == run_id)).all()
        return {
            "runId": record.id,
            "status": record.status,
            "requestSummary": json.loads(record.request_summary_json),
            "plan": json.loads(record.plan_json),
            "trace": json.loads(record.trace_json),
            "result": load_agent_result_file(record.result_path) if record.result_path else None,
            "error": record.error,
            "steps": [
                {
                    "stepId": step.step_id,
                    "tool": step.tool,
                    "status": step.status,
                    "attempt": step.attempt,
                    "error": step.error,
                    "outputArtifactPath": step.output_artifact_path,
                }
                for step in steps
            ],
            "events": [
                {"sequence": event.sequence, "type": event.event_type, "status": event.status, "payload": json.loads(event.payload_json), "createdAt": event.created_at}
                for event in db.exec(select(AgentEventRecord).where(AgentEventRecord.run_id == run_id).order_by(AgentEventRecord.created_at)).all()
            ],
        }


@router.post("/runs/{run_id}/reconcile")
async def reconcile_agent_run(run_id: str):
    """Mark a process-interrupted run for explicit review without replaying it."""
    with get_session() as db:
        record = db.get(AgentRunRecord, run_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Agent 运行不存在")
        if record.status != "interrupted":
            return {"runId": run_id, "status": record.status, "replayed": False}
        validate_agent_status_transition(record.status, "needs_review")
        record.status = "needs_review"
        record.error = "进程中断，未自动重放模型调用；请检查检查点后重新确认任务。"
        record.updated_at = int(time.time() * 1000)
        db.add(record)
        last_event = db.exec(select(AgentEventRecord).where(
            AgentEventRecord.run_id == run_id,
        ).order_by(AgentEventRecord.sequence.desc())).first()
        db.add(AgentEventRecord(
            id=uuid.uuid4().hex,
            run_id=run_id,
            sequence=(last_event.sequence + 1) if last_event else 1,
            event_type="state",
            status="needs_review",
            payload_json=json.dumps({"reason": "process_interrupted", "replayed": False}, ensure_ascii=False),
            created_at=record.updated_at,
        ))
        db.commit()
        checkpoint_count = len(db.exec(select(AgentStepRecord).where(
            AgentStepRecord.run_id == run_id,
            AgentStepRecord.output_artifact_path != "",
        )).all())
        return {
            "runId": run_id,
            "status": record.status,
            "replayed": False,
            "checkpointCount": checkpoint_count,
        }


@router.get("/runs/{run_id}/events")
async def get_agent_run_events(run_id: str, after: int = 0):
    with get_session() as db:
        if db.get(AgentRunRecord, run_id) is None:
            raise HTTPException(status_code=404, detail="Agent 运行不存在")
        events = db.exec(select(AgentEventRecord).where(
            AgentEventRecord.run_id == run_id,
            AgentEventRecord.sequence > after,
        ).order_by(AgentEventRecord.sequence)).all()
        return {"runId": run_id, "events": [
            {"sequence": event.sequence, "type": event.event_type, "status": event.status,
             "payload": json.loads(event.payload_json), "createdAt": event.created_at}
            for event in events
        ]}


@router.post("/runs/{run_id}/resume-local")
async def resume_local_agent_run(run_id: str, request: AgentRunRequest):
    """Resume only the contiguous completed prefix of a local-only plan.

    The caller must resend the exact approved context. Any plan containing a
    model step is rejected so a process restart can never silently replay a
    paid image generation request.
    """
    try:
        validate_agent_input(prompt=request.content.content, image_data_url=request.content.image)
        with get_session() as db:
            record = db.get(AgentRunRecord, run_id)
            if record is None:
                raise ValueError("Agent 运行不存在")
            if record.status not in {"interrupted", "needs_review"}:
                raise ValueError("只有中断或待核对的运行可以本地恢复")
            plan, analysis_raw = get_claimed_preview(db, request, run_id)
            validate_agent_plan(plan, approved=True)
            if any(step.tool == "apply_ai_edit" for step in plan.steps):
                raise ValueError("包含图片模型步骤的运行不能自动本地续跑，请重新审批执行")
            persisted_plan = json.loads(record.plan_json or "{}")
            if persisted_plan and persisted_plan != plan.model_dump():
                raise ValueError("持久化计划与审批计划不一致，请重新预览")
            persisted_steps = db.exec(select(AgentStepRecord).where(
                AgentStepRecord.run_id == run_id,
            )).all()
            by_step = {step.step_id: step for step in persisted_steps}
            resume_step_ids: set[str] = set()
            resume_output_image = request.content.image
            for step in plan.steps:
                checkpoint = by_step.get(step.id)
                if checkpoint is None or checkpoint.status != "executed" or not checkpoint.output_artifact_path:
                    break
                checkpoint_image = load_agent_step_file(checkpoint.output_artifact_path)
                if not checkpoint_image:
                    break
                resume_step_ids.add(step.id)
                resume_output_image = checkpoint_image
            approved_analysis = parse_agent_analysis(analysis_raw) if analysis_raw else None
            lease_result = db.execute(sql_update(AgentRunRecord).where(
                AgentRunRecord.id == run_id,
                AgentRunRecord.status.in_(["interrupted", "needs_review"]),
                (AgentRunRecord.lease_owner == "") | (AgentRunRecord.lease_expires_at < int(time.time())),
            ).values(
                lease_owner=WORKER_ID,
                lease_expires_at=int(time.time()) + LEASE_SECONDS,
            ))
            if lease_result.rowcount != 1:
                raise ValueError("该运行已被其他 Worker 接管，请稍后查看运行记录")
            db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"code": "LOCAL_RESUME_REJECTED", "message": str(exc)}) from exc

    if run_id in _AGENT_CONTROLS:
        raise HTTPException(status_code=409, detail={"code": "RUN_ALREADY_ACTIVE", "message": "该 Agent 运行正在执行中。"})
    control = _AgentControl()
    control.pause_event.set()
    _AGENT_CONTROLS[run_id] = control
    resumed_request = request.model_copy(update={"runId": run_id, "approved": True})
    return StreamingResponse(
        _agent_event_stream(
            resumed_request,
            plan,
            approved_analysis,
            analysis_raw or None,
            resume_output_image,
            resume_step_ids,
        ),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/runs/{run_id}/resume")
async def resume_agent_run(run_id: str):
    control = _AGENT_CONTROLS.get(run_id)
    if control is None:
        raise HTTPException(status_code=404, detail="Agent 任务不存在或已结束")
    control.pause_event.set()
    control.status = "running"
    _persist_agent_run(run_id, status="running")
    return {"runId": run_id, "status": control.status}


@router.post("/runs/{run_id}/cancel")
async def cancel_agent_run(run_id: str):
    control = _AGENT_CONTROLS.get(run_id)
    if control is None:
        raise HTTPException(status_code=404, detail="Agent 任务不存在或已结束")
    control.cancel_event.set()
    control.pause_event.set()
    control.status = "cancelling"
    _persist_agent_run(run_id, status="cancelling")
    return {"runId": run_id, "status": control.status}


@router.post("/plan")
async def preview_agent_plan(request: AgentRunRequest):
    """Analyze and plan an Agent task without invoking the image-edit model."""

    try:
        validate_agent_input(prompt=request.content.content, image_data_url=request.content.image)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "INVALID_AGENT_INPUT", "message": str(exc)}) from exc

    analysis_result = await litellm_completion(
        host=request.config.analysis.host,
        api_key=request.config.analysis.key,
        model=request.config.analysis.model,
        messages=[
            {"role": "system", "content": get_analysis_system_prompt()},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": request.content.image}},
                    {"type": "text", "text": request.content.content or "Analyze this image for photo retouching."},
                ],
            },
        ],
    )
    analysis_raw = analysis_result.get("text") or ""
    analysis = parse_agent_analysis(analysis_raw)
    planner_trace = analysis_result.get("trace", {})
    try:
        plan, planner_trace = await generate_agent_plan(
            host=request.config.analysis.host,
            api_key=request.config.analysis.key,
            model=request.config.analysis.model,
            analysis=analysis,
            user_prompt=request.content.content,
        )
    except Exception:
        plan = build_plan_from_analysis(analysis)
    validate_agent_plan_shape(plan)
    with get_session() as db:
        approval_id = save_preview(
            db, request, plan, analysis.to_dict(), analysis_raw=analysis_raw,
        )
    return {
        "analysis": analysis.to_dict(),
        "analysis_raw": analysis_raw,
        "plan": {**plan.model_dump(), "approval_id": approval_id},
        "tool_trace": {"runs": [], "hasFailures": False, "aiCalls": [planner_trace]},
    }


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
