from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import desc
from sqlmodel import Session, select

from ..models.settings import (
    AssetRecord,
    WorkspaceImagePointer,
    WorkspaceRecord,
    WorkspaceVersionRecord,
    delete_workspace_image_file,
    get_session,
    load_workspace_image_file,
    save_workspace_image_file,
)
from ..services.workspace_commit import commit_workspace, read_image, read_version_image
from ..core.policy import validate_agent_input
from fastapi import HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


# ── Schemas ─────────────────────────────────────────────────


class WorkspaceOut(BaseModel):
    id: str
    title: str
    createdAt: int
    updatedAt: int
    hasSourceImage: bool = False
    currentVersionId: str | None = None


class WorkspaceCreate(BaseModel):
    id: str
    title: str
    createdAt: int
    updatedAt: int
    hasSourceImage: bool = False


class WorkspaceUpdate(BaseModel):
    title: str | None = None
    updatedAt: int | None = None
    hasSourceImage: bool | None = None


class WorkspaceCommit(BaseModel):
    title: str
    createdAt: int
    updatedAt: int
    image: str | None = None
    expectedVersionId: str | None = None
    parentVersionId: str | None = None
    editorRunId: str | None = None
    assetId: str | None = None


class WorkspaceList(BaseModel):
    workspaces: list[WorkspaceOut]


class WorkspaceImageResponse(BaseModel):
    image: str | None = None


class WorkspaceVersionOut(BaseModel):
    id: str
    parentId: str | None = None
    operation: str
    createdAt: int
    artifactId: str | None = None
    isCurrent: bool = False
    assetId: str | None = None


# ── Helpers ────────────────────────────────────────────────────


def _to_out(record: WorkspaceRecord) -> WorkspaceOut:
    return WorkspaceOut(
        id=record.id,
        title=record.title,
        createdAt=record.created_at,
        updatedAt=record.updated_at,
        hasSourceImage=record.has_source_image,
        currentVersionId=record.current_version_id,
    )


def get_db():
    db = get_session()
    try:
        yield db
    finally:
        db.close()


# ── Routes ─────────────────────────────────────────────────────


@router.put("/{workspace_id}/commit", response_model=WorkspaceOut)
def save_workspace_commit(workspace_id: str, body: WorkspaceCommit, db: Session = Depends(get_db)):
    replace_image = 'image' in body.model_fields_set
    if replace_image and body.image is not None:
        try:
            validate_agent_input(prompt='', image_data_url=body.image)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    record = db.get(WorkspaceRecord, workspace_id) or WorkspaceRecord(id=workspace_id, created_at=body.createdAt)
    if record.current_version_id is not None and body.expectedVersionId != record.current_version_id:
        raise HTTPException(status_code=409, detail={
            "code": "WORKSPACE_VERSION_CONFLICT",
            "message": "工作区已经产生新版本，请重新加载后再保存。",
            "currentVersionId": record.current_version_id,
        })
    if body.parentVersionId is not None:
        parent = db.get(WorkspaceVersionRecord, body.parentVersionId)
        if parent is None or parent.workspace_id != workspace_id:
            raise HTTPException(status_code=422, detail="父版本不属于当前工作区")
    if body.assetId is not None:
        asset = db.get(AssetRecord, body.assetId)
        if asset is None or asset.workspace_id != workspace_id:
            raise HTTPException(status_code=422, detail="素材不属于当前工作区")
    record.title = body.title
    record.updated_at = body.updatedAt
    commit_workspace(db, record, image=body.image, replace_image=replace_image,
                     parent_version_id=body.parentVersionId, editor_run_id=body.editorRunId,
                     asset_id=body.assetId)
    return _to_out(record)


@router.get("", response_model=WorkspaceList)
def list_workspaces(db: Session = Depends(get_db)):
    records = db.exec(select(WorkspaceRecord).order_by(desc(WorkspaceRecord.updated_at))).all()  # pyright: ignore[reportArgumentType]
    return WorkspaceList(workspaces=[_to_out(r) for r in records])


@router.get("/{workspace_id}", response_model=WorkspaceOut)
def get_workspace(workspace_id: str, db: Session = Depends(get_db)):
    record = db.get(WorkspaceRecord, workspace_id)
    if record is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Workspace not found")
    return _to_out(record)


@router.get("/{workspace_id}/versions", response_model=list[WorkspaceVersionOut])
def list_workspace_versions(workspace_id: str, db: Session = Depends(get_db)):
    record = db.get(WorkspaceRecord, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    versions = db.exec(select(WorkspaceVersionRecord).where(
        WorkspaceVersionRecord.workspace_id == workspace_id,
    ).order_by(desc(WorkspaceVersionRecord.created_at))).all()
    return [WorkspaceVersionOut(
        id=item.id, parentId=item.parent_id, operation=item.operation,
        createdAt=item.created_at, artifactId=item.artifact_id,
        assetId=item.asset_id,
        isCurrent=item.id == record.current_version_id,
    ) for item in versions]


@router.get("/{workspace_id}/versions/{version_id}/image", response_model=WorkspaceImageResponse)
def get_workspace_version_image(workspace_id: str, version_id: str, db: Session = Depends(get_db)):
    version = db.get(WorkspaceVersionRecord, version_id)
    if version is None or version.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Workspace version not found")
    return WorkspaceImageResponse(image=read_version_image(db, version_id))


@router.post("", response_model=WorkspaceOut, status_code=201)
def create_workspace(body: WorkspaceCreate, db: Session = Depends(get_db)):
    record = WorkspaceRecord(
        id=body.id,
        title=body.title,
        created_at=body.createdAt,
        updated_at=body.updatedAt,
        has_source_image=body.hasSourceImage,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _to_out(record)


@router.put("/{workspace_id}", response_model=WorkspaceOut)
def update_workspace(
    workspace_id: str,
    body: WorkspaceUpdate,
    db: Session = Depends(get_db),
):
    record = db.get(WorkspaceRecord, workspace_id)
    if record is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Workspace not found")

    if body.title is not None:
        record.title = body.title
    if body.updatedAt is not None:
        record.updated_at = body.updatedAt
    if body.hasSourceImage is not None:
        record.has_source_image = body.hasSourceImage

    db.add(record)
    db.commit()
    db.refresh(record)
    return _to_out(record)


@router.delete("/{workspace_id}")
def delete_workspace(workspace_id: str, db: Session = Depends(get_db)):
    from .assets import delete_workspace_assets

    delete_workspace_assets(workspace_id, db)
    record = db.get(WorkspaceRecord, workspace_id)
    if record is not None:
        db.delete(record)
        pointer = db.get(WorkspaceImagePointer, workspace_id)
        if pointer is not None:
            db.delete(pointer)
        db.commit()
    delete_workspace_image_file(workspace_id)
    return {"ok": True}


# ── Image routes ───────────────────────────────────────────────


@router.get("/{workspace_id}/image", response_model=WorkspaceImageResponse)
def get_workspace_image(workspace_id: str, db: Session = Depends(get_db)):
    image = read_image(db, workspace_id)
    return WorkspaceImageResponse(image=image)


@router.put("/{workspace_id}/image")
def save_workspace_image(workspace_id: str, body: dict[str, Any], db: Session = Depends(get_db)):
    data_url = body.get("image")
    record = db.get(WorkspaceRecord, workspace_id)
    if record is not None:
        commit_workspace(db, record, image=data_url, replace_image=True)
        return {"ok": True}
    save_workspace_image_file(workspace_id, data_url)
    return {"ok": True}


@router.delete("/{workspace_id}/image")
def delete_workspace_image(workspace_id: str, db: Session = Depends(get_db)):
    record = db.get(WorkspaceRecord, workspace_id)
    if record is not None:
        commit_workspace(db, record, image=None, replace_image=True)
        return {"ok": True}
    delete_workspace_image_file(workspace_id)
    return {"ok": True}
