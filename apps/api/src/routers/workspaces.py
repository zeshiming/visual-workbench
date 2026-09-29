from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import desc
from sqlmodel import Session, select

from ..models.settings import (
    WorkspaceRecord,
    delete_workspace_image_file,
    get_session,
    load_workspace_image_file,
    save_workspace_image_file,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


# ── Schemas ─────────────────────────────────────────────────


class WorkspaceOut(BaseModel):
    id: str
    title: str
    createdAt: int
    updatedAt: int
    hasSourceImage: bool = False


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


class WorkspaceList(BaseModel):
    workspaces: list[WorkspaceOut]


class WorkspaceImageResponse(BaseModel):
    image: str | None = None


# ── Helpers ────────────────────────────────────────────────────


def _to_out(record: WorkspaceRecord) -> WorkspaceOut:
    return WorkspaceOut(
        id=record.id,
        title=record.title,
        createdAt=record.created_at,
        updatedAt=record.updated_at,
        hasSourceImage=record.has_source_image,
    )


def get_db():
    db = get_session()
    try:
        yield db
    finally:
        db.close()


# ── Routes ─────────────────────────────────────────────────────


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
    record = db.get(WorkspaceRecord, workspace_id)
    if record is not None:
        db.delete(record)
        db.commit()
    delete_workspace_image_file(workspace_id)
    return {"ok": True}


# ── Image routes ───────────────────────────────────────────────


@router.get("/{workspace_id}/image", response_model=WorkspaceImageResponse)
def get_workspace_image(workspace_id: str):
    image = load_workspace_image_file(workspace_id)
    return WorkspaceImageResponse(image=image)


@router.put("/{workspace_id}/image")
def save_workspace_image(workspace_id: str, body: dict[str, Any]):
    data_url = body.get("image")
    save_workspace_image_file(workspace_id, data_url)
    return {"ok": True}


@router.delete("/{workspace_id}/image")
def delete_workspace_image(workspace_id: str):
    delete_workspace_image_file(workspace_id)
    return {"ok": True}
