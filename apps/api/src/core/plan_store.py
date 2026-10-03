"""Bind approval to the exact server preview; never trust client plan edits."""

import hashlib
import json
import time
import uuid

from sqlalchemy import update
from sqlmodel import Session

from .agent_plan import AgentPlan
from ..models.schemas import AgentRunRequest
from ..models.settings import AgentPlanRecord


def context_hash(request: AgentRunRequest) -> str:
    # Credentials are neither persisted nor hashed. Credential rotation does not
    # alter the approved edit; provider endpoint/model changes do.
    data = {
        "workspace_id": request.workspaceId,
        "version_id": request.versionId,
        "image": hashlib.sha256(request.content.image.encode()).hexdigest(),
        "prompt": request.content.content,
        "styles": request.styles,
        "models": request.config.model_dump(exclude={"analysis": {"key"}, "edit": {"key"}}),
        "budget": request.budget.model_dump(),
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def save_preview(
    db: Session,
    request: AgentRunRequest,
    plan: AgentPlan,
    analysis: dict,
    *,
    analysis_raw: str = "",
) -> str:
    now = int(time.time())
    record = AgentPlanRecord(
        id=uuid.uuid4().hex, context_hash=context_hash(request),
        plan_json=plan.model_dump_json(), analysis_json=json.dumps(analysis, ensure_ascii=False),
        analysis_raw_json=analysis_raw,
        created_at=now, expires_at=now + 1800,
    )
    db.add(record)
    db.commit()
    return record.id


def claim_preview(db: Session, request: AgentRunRequest, run_id: str) -> AgentPlan:
    supplied = request.plan or {}
    plan_id = supplied.get("approval_id")
    if not request.approved or not isinstance(plan_id, str):
        raise ValueError("请重新预览并确认执行计划。")
    record = db.get(AgentPlanRecord, plan_id)
    now = int(time.time())
    if record is None or record.expires_at <= now:
        raise ValueError("执行计划不存在或已过期，请重新预览。")
    if record.context_hash != context_hash(request):
        raise ValueError("图片、需求或模型配置已变化，请重新预览计划。")
    plan = AgentPlan.model_validate_json(record.plan_json)
    if {k: v for k, v in supplied.items() if k != "approval_id"} != plan.model_dump():
        raise ValueError("执行计划内容已变化，请重新预览。")
    result = db.execute(update(AgentPlanRecord).where(
        AgentPlanRecord.id == plan_id, AgentPlanRecord.run_id == "",
        AgentPlanRecord.expires_at > now,
    ).values(run_id=run_id, approved_at=now))
    if result.rowcount != 1:
        db.rollback()
        raise ValueError("该计划已提交执行，请查看原任务或重新预览。")
    db.commit()
    return plan


def get_claimed_preview(db: Session, request: AgentRunRequest, run_id: str) -> tuple[AgentPlan, str]:
    """Read an already-claimed preview for an explicitly approved local resume."""
    supplied = request.plan or {}
    plan_id = supplied.get("approval_id")
    if not request.approved or not isinstance(plan_id, str):
        raise ValueError("请重新确认本地恢复计划。")
    record = db.get(AgentPlanRecord, plan_id)
    if record is None or record.run_id != run_id or record.expires_at <= int(time.time()):
        raise ValueError("该审批计划不属于此 Agent 运行。")
    if record.context_hash != context_hash(request):
        raise ValueError("图片、需求或模型配置已变化，请重新预览计划。")
    plan = AgentPlan.model_validate_json(record.plan_json)
    if {k: v for k, v in supplied.items() if k != "approval_id"} != plan.model_dump():
        raise ValueError("执行计划内容已变化，请重新预览。")
    return plan, record.analysis_raw_json
