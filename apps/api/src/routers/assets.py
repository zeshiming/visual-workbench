"""Workspace image library. Originals are stored as files, with metadata in SQLite."""

from __future__ import annotations

import os
import time
import uuid
from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel
from sqlalchemy import desc
from sqlmodel import Session, select

from ..models.settings import AssetRecord, WorkspaceRecord, get_session
from ..models.settings import WORKSPACE_IMAGES_DIR

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/assets", tags=["assets"])
MAX_ASSET_BYTES = 20 * 1024 * 1024
SUPPORTED_FORMATS = {"JPEG": ("jpg", "image/jpeg"), "PNG": ("png", "image/png"), "WEBP": ("webp", "image/webp")}


class AssetOut(BaseModel):
    id: str
    filename: str
    mediaType: str
    kind: str
    createdAt: int
    sizeBytes: int


def get_db():
    with get_session() as db:
        yield db


def _workspace(db: Session, workspace_id: str) -> None:
    if db.get(WorkspaceRecord, workspace_id) is None:
        raise HTTPException(status_code=404, detail="Workspace not found")


def _asset(db: Session, workspace_id: str, asset_id: str) -> AssetRecord:
    item = db.get(AssetRecord, asset_id)
    if item is None or item.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Asset not found")
    return item


def _path(item: AssetRecord) -> str:
    # Only server-generated UUIDs are used as filenames.
    return os.path.join(WORKSPACE_IMAGES_DIR, "assets", f"{item.id}.{item.media_type.split('/')[-1]}")


def _out(item: AssetRecord) -> AssetOut:
    return AssetOut(id=item.id, filename=item.filename, mediaType=item.media_type,
                    kind=item.kind, createdAt=item.created_at, sizeBytes=item.size_bytes)


@router.get("", response_model=list[AssetOut])
def list_assets(workspace_id: str, db: Session = Depends(get_db)):
    _workspace(db, workspace_id)
    items = db.exec(select(AssetRecord).where(AssetRecord.workspace_id == workspace_id)
                    .order_by(desc(AssetRecord.created_at))).all()
    return [_out(item) for item in items]


@router.post("", response_model=AssetOut, status_code=201)
async def upload_asset(workspace_id: str, file: UploadFile = File(...),
                       kind: str = Form("import"), db: Session = Depends(get_db)):
    _workspace(db, workspace_id)
    if kind not in {"import", "edit", "generated"}:
        raise HTTPException(status_code=422, detail="Invalid asset kind")
    data = await file.read(MAX_ASSET_BYTES + 1)
    if len(data) > MAX_ASSET_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds 20 MB")
    try:
        with Image.open(BytesIO(data)) as img:
            image_format = img.format
            img.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(status_code=415, detail="Invalid image") from exc
    if image_format not in SUPPORTED_FORMATS:
        raise HTTPException(status_code=415, detail="Use JPEG, PNG, or WebP")

    extension, media_type = SUPPORTED_FORMATS[image_format]
    item = AssetRecord(id=uuid.uuid4().hex, workspace_id=workspace_id,
                       filename=(file.filename or f"image.{extension}")[:255],
                       media_type=media_type, kind=kind, created_at=int(time.time() * 1000),
                       size_bytes=len(data))
    path = _path(item)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as output:
        output.write(data)
    try:
        db.add(item)
        db.commit()
    except Exception:
        os.remove(path)
        raise
    return _out(item)


@router.get("/{asset_id}/image")
def get_asset_image(workspace_id: str, asset_id: str, db: Session = Depends(get_db)):
    _workspace(db, workspace_id)
    item = _asset(db, workspace_id, asset_id)
    path = _path(item)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Asset image missing")
    return FileResponse(path, media_type=item.media_type)


@router.delete("/{asset_id}")
def delete_asset(workspace_id: str, asset_id: str, db: Session = Depends(get_db)):
    _workspace(db, workspace_id)
    item = _asset(db, workspace_id, asset_id)
    path = _path(item)
    db.delete(item)
    db.commit()
    if os.path.isfile(path):
        os.remove(path)
    return {"ok": True}


def delete_workspace_assets(workspace_id: str, db: Session) -> None:
    """Remove assets while deleting a workspace."""
    items = db.exec(select(AssetRecord).where(AssetRecord.workspace_id == workspace_id)).all()
    for item in items:
        path = _path(item)
        if os.path.isfile(path):
            os.remove(path)
        db.delete(item)
    db.commit()
