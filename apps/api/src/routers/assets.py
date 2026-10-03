"""Workspace image library. Originals are stored as files, with metadata in SQLite."""

from __future__ import annotations

import os
import re
import time
import uuid
import zipfile
from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from PIL import Image, UnidentifiedImageError
from PIL.ExifTags import TAGS
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlmodel import Session, select

from ..models.settings import AssetRecord, FeedbackRecord, WorkspaceRecord, get_session
from ..models.settings import WORKSPACE_IMAGES_DIR

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/assets", tags=["assets"])
MAX_ASSET_BYTES = 100 * 1024 * 1024
SUPPORTED_FORMATS = {"JPEG": ("jpg", "image/jpeg"), "PNG": ("png", "image/png"), "WEBP": ("webp", "image/webp")}
RAW_EXTENSIONS = {
    ".arw": "image/x-sony-arw", ".cr2": "image/x-canon-cr2", ".cr3": "image/x-canon-cr3",
    ".dng": "image/x-adobe-dng", ".nef": "image/x-nikon-nef", ".orf": "image/x-olympus-orf",
    ".pef": "image/x-pentax-pef", ".raf": "image/x-fuji-raf", ".rw2": "image/x-panasonic-rw2",
    ".srw": "image/x-samsung-srw",
}


class AssetOut(BaseModel):
    id: str
    filename: str
    mediaType: str
    kind: str
    createdAt: int
    sizeBytes: int
    width: int | None = None
    height: int | None = None
    metadata: dict[str, str | int | float] = {}
    pairGroup: str | None = None
    pairRole: str | None = None
    feedbackId: str | None = None


class FeedbackCreate(BaseModel):
    feedbackId: str = Field(min_length=1, max_length=128)
    customerId: str = Field(default="", max_length=200)
    message: str = Field(default="", max_length=12_000)
    status: str = Field(default="open", max_length=32)


class FeedbackUpdate(BaseModel):
    customerId: str | None = Field(default=None, max_length=200)
    message: str | None = Field(default=None, max_length=12_000)
    status: str | None = Field(default=None, max_length=32)


class FeedbackOut(FeedbackCreate):
    id: str
    workspaceId: str
    createdAt: int
    updatedAt: int


class AssetExportRequest(BaseModel):
    assetIds: list[str]


class AssetContextRequest(BaseModel):
    """Selection context passed from the photo library to an Agent run."""

    assetIds: list[str] = Field(default_factory=list)
    feedbackId: str | None = None
    referenceAssetId: str | None = None


class AssetContextItem(AssetOut):
    imageUrl: str


class AssetContextResponse(BaseModel):
    selectionSource: str
    assets: list[AssetContextItem]
    reference: AssetContextItem | None = None
    missingIds: list[str] = Field(default_factory=list)


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
    extension = os.path.splitext(item.filename)[1].lower().lstrip(".") or item.media_type.split("/")[-1]
    return os.path.join(WORKSPACE_IMAGES_DIR, "assets", f"{item.id}.{extension}")


def _preview_path(item: AssetRecord) -> str:
    return f"{_path(item)}.preview.jpg"


def _is_raw(item: AssetRecord) -> bool:
    return os.path.splitext(item.filename)[1].lower() in RAW_EXTENSIONS


def _pair_key(filename: str) -> str:
    stem = os.path.splitext(os.path.basename(filename))[0].lower()
    return re.sub(r"(?:[_-](?:raw|jpg|jpeg|edit|edited))$", "", stem)


def _pair_role(item: AssetRecord) -> str:
    if _is_raw(item):
        return "raw"
    return "jpeg" if os.path.splitext(item.filename)[1].lower() in {".jpg", ".jpeg"} else "other"


def _safe_metadata_value(value):
    return value if isinstance(value, (str, int, float)) else str(value)


def _asset_info(item: AssetRecord) -> tuple[int | None, int | None, dict[str, str | int | float]]:
    path = _path(item)
    if _is_raw(item):
        try:
            import rawpy  # type: ignore[import-untyped]
            with rawpy.imread(path) as raw:
                other = raw.other
                lens = raw.lens
                return raw.sizes.width, raw.sizes.height, {
                    "camera": "",
                    "lens": str(getattr(lens, "model", "") or ""),
                    "iso": _safe_metadata_value(other.iso_speed),
                    "shutter": _safe_metadata_value(other.shutter_speed),
                    "aperture": _safe_metadata_value(other.aperture),
                    "focalLength": _safe_metadata_value(other.focal_length),
                }
        except (ImportError, OSError, ValueError, AttributeError):
            return None, None, {}

    try:
        with Image.open(path) as image:
            metadata: dict[str, str | int | float] = {}
            for tag_id, value in image.getexif().items():
                tag = TAGS.get(tag_id, str(tag_id))
                if tag in {"Make", "Model", "LensModel", "ISOSpeedRatings", "ExposureTime", "FNumber", "FocalLength", "DateTimeOriginal"}:
                    metadata[tag] = _safe_metadata_value(value)
            return image.width, image.height, metadata
    except (OSError, UnidentifiedImageError):
        return None, None, {}


def _generate_raw_preview(item: AssetRecord) -> None:
    try:
        import rawpy  # type: ignore[import-untyped]
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="RAW 预览需要安装 rawpy 依赖") from exc
    try:
        with rawpy.imread(_path(item)) as raw:
            rgb = raw.postprocess(use_camera_wb=True, output_bps=8, half_size=True)
        Image.fromarray(rgb).save(_preview_path(item), format="JPEG", quality=88)
    except Exception as exc:
        raise HTTPException(status_code=415, detail=f"RAW 文件无法生成预览: {exc}") from exc


def _out(item: AssetRecord, pair_group: str | None = None) -> AssetOut:
    width, height, metadata = _asset_info(item)
    return AssetOut(id=item.id, filename=item.filename, mediaType=item.media_type,
                    kind=item.kind, createdAt=item.created_at, sizeBytes=item.size_bytes,
                    width=width, height=height, metadata=metadata,
                    pairGroup=pair_group, pairRole=_pair_role(item), feedbackId=item.feedback_id)


def _context_item(workspace_id: str, item: AssetRecord) -> AssetContextItem:
    basic = _out(item, _pair_key(item.filename))
    return AssetContextItem(
        **basic.model_dump(),
        imageUrl=f"/api/v1/workspaces/{workspace_id}/assets/{item.id}/image",
    )


def _feedback_out(item: FeedbackRecord) -> FeedbackOut:
    return FeedbackOut(
        id=item.id,
        workspaceId=item.workspace_id,
        feedbackId=item.feedback_id,
        customerId=item.customer_id,
        message=item.message,
        status=item.status,
        createdAt=item.created_at,
        updatedAt=item.updated_at,
    )


@router.get("/feedback", response_model=list[FeedbackOut])
def list_feedback(
    workspace_id: str,
    query: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    _workspace(db, workspace_id)
    items = db.exec(select(FeedbackRecord).where(
        FeedbackRecord.workspace_id == workspace_id,
    ).order_by(desc(FeedbackRecord.updated_at))).all()
    if query and query.strip():
        needle = query.strip().lower()
        items = [item for item in items if needle in item.feedback_id.lower()
                 or needle in item.customer_id.lower()
                 or needle in item.message.lower()]
    return [_feedback_out(item) for item in items]


@router.post("/feedback", response_model=FeedbackOut, status_code=201)
def create_feedback(workspace_id: str, body: FeedbackCreate, db: Session = Depends(get_db)):
    _workspace(db, workspace_id)
    status = body.status.strip() or "open"
    if status not in {"open", "processing", "resolved", "archived"}:
        raise HTTPException(status_code=422, detail="Invalid feedback status")
    now = int(time.time() * 1000)
    item = FeedbackRecord(
        id=uuid.uuid4().hex,
        workspace_id=workspace_id,
        feedback_id=body.feedbackId.strip(),
        customer_id=body.customerId.strip(),
        message=body.message.strip(),
        status=status,
        created_at=now,
        updated_at=now,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _feedback_out(item)


@router.put("/feedback/{feedback_record_id}", response_model=FeedbackOut)
def update_feedback(
    workspace_id: str,
    feedback_record_id: str,
    body: FeedbackUpdate,
    db: Session = Depends(get_db),
):
    _workspace(db, workspace_id)
    item = db.get(FeedbackRecord, feedback_record_id)
    if item is None or item.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Feedback record not found")
    if body.customerId is not None:
        item.customer_id = body.customerId.strip()
    if body.message is not None:
        item.message = body.message.strip()
    if body.status is not None:
        status = body.status.strip()
        if status not in {"open", "processing", "resolved", "archived"}:
            raise HTTPException(status_code=422, detail="Invalid feedback status")
        item.status = status
    item.updated_at = int(time.time() * 1000)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _feedback_out(item)


@router.delete("/feedback/{feedback_record_id}")
def delete_feedback(workspace_id: str, feedback_record_id: str, db: Session = Depends(get_db)):
    _workspace(db, workspace_id)
    item = db.get(FeedbackRecord, feedback_record_id)
    if item is None or item.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Feedback record not found")
    db.delete(item)
    db.commit()
    return {"id": feedback_record_id, "removed": True}


@router.get("", response_model=list[AssetOut])
def list_assets(
    workspace_id: str,
    feedback_id: str | None = Query(default=None, alias="feedbackId"),
    query: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    _workspace(db, workspace_id)
    items = db.exec(select(AssetRecord).where(AssetRecord.workspace_id == workspace_id)
                    .order_by(desc(AssetRecord.created_at))).all()
    if feedback_id:
        needle = feedback_id.strip().lower()
        items = [item for item in items if needle in (item.feedback_id or '').lower() or needle in item.filename.lower()]
    if query:
        needle = query.strip().lower()
        items = [item for item in items if needle in item.filename.lower()]
    groups: dict[str, list[AssetRecord]] = {}
    for item in items:
        groups.setdefault(_pair_key(item.filename), []).append(item)
    return [
        _out(item, _pair_key(item.filename) if len(groups[_pair_key(item.filename)]) > 1 else None)
        for item in items
    ]


@router.post("/context", response_model=AssetContextResponse)
def resolve_asset_context(
    workspace_id: str,
    body: AssetContextRequest,
    db: Session = Depends(get_db),
):
    """Resolve selected assets and an optional reference into Agent context."""

    _workspace(db, workspace_id)
    all_items = db.exec(
        select(AssetRecord).where(AssetRecord.workspace_id == workspace_id)
    ).all()
    by_id = {item.id: item for item in all_items}
    selected: list[AssetRecord] = []
    missing: list[str] = []

    if body.feedbackId and body.feedbackId.strip():
        needle = body.feedbackId.strip().lower()
        selected = [item for item in all_items if needle in (item.feedback_id or '').lower() or needle in item.filename.lower()]
        source = "feedback_id"
    else:
        source = "selected_assets"
        for asset_id in dict.fromkeys(body.assetIds):
            item = by_id.get(asset_id)
            if item is None:
                missing.append(asset_id)
            else:
                selected.append(item)

    reference = by_id.get(body.referenceAssetId) if body.referenceAssetId else None
    if body.referenceAssetId and reference is None:
        missing.append(body.referenceAssetId)

    selected = selected[:200]
    return AssetContextResponse(
        selectionSource=source,
        assets=[_context_item(workspace_id, item) for item in selected],
        reference=_context_item(workspace_id, reference) if reference else None,
        missingIds=list(dict.fromkeys(missing)),
    )


@router.post("", response_model=AssetOut, status_code=201)
async def upload_asset(workspace_id: str, file: UploadFile = File(...),
                       kind: str = Form("import"), feedback_id: str = Form(""), db: Session = Depends(get_db)):
    _workspace(db, workspace_id)
    if kind not in {"import", "edit", "generated"}:
        raise HTTPException(status_code=422, detail="Invalid asset kind")
    feedback_id = feedback_id.strip()
    if len(feedback_id) > 128:
        raise HTTPException(status_code=422, detail="Feedback ID too long")
    data = await file.read(MAX_ASSET_BYTES + 1)
    if len(data) > MAX_ASSET_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds 100 MB")
    filename = os.path.basename((file.filename or "image").strip())[:255]
    extension_from_name = os.path.splitext(filename)[1].lower()
    is_raw_upload = extension_from_name in RAW_EXTENSIONS
    try:
        with Image.open(BytesIO(data)) as img:
            image_format = img.format
            img.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        if not is_raw_upload:
            raise HTTPException(status_code=415, detail="Invalid image") from exc
        image_format = None
    if not is_raw_upload and image_format not in SUPPORTED_FORMATS:
        raise HTTPException(status_code=415, detail="Use JPEG, PNG, or WebP")

    if is_raw_upload:
        media_type = RAW_EXTENSIONS[extension_from_name]
        extension = extension_from_name.lstrip(".")
    else:
        extension, media_type = SUPPORTED_FORMATS[image_format]
    item = AssetRecord(id=uuid.uuid4().hex, workspace_id=workspace_id,
                       filename=filename or f"image.{extension}",
                       media_type=media_type, kind=kind, feedback_id=feedback_id or None,
                       created_at=int(time.time() * 1000),
                       size_bytes=len(data))
    path = _path(item)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as output:
        output.write(data)
    try:
        db.add(item)
        if feedback_id:
            existing_feedback = db.exec(select(FeedbackRecord).where(
                FeedbackRecord.workspace_id == workspace_id,
                FeedbackRecord.feedback_id == feedback_id,
            )).first()
            if existing_feedback is None:
                now = int(time.time() * 1000)
                db.add(FeedbackRecord(
                    id=uuid.uuid4().hex,
                    workspace_id=workspace_id,
                    feedback_id=feedback_id,
                    created_at=now,
                    updated_at=now,
                ))
        db.commit()
    except Exception:
        os.remove(path)
        raise
    if is_raw_upload:
        try:
            _generate_raw_preview(item)
        except Exception:
            db.delete(item)
            db.commit()
            if os.path.isfile(path):
                os.remove(path)
            raise
    return _out(item, _pair_key(item.filename))


@router.get("/{asset_id}/image")
def get_asset_image(workspace_id: str, asset_id: str, db: Session = Depends(get_db)):
    _workspace(db, workspace_id)
    item = _asset(db, workspace_id, asset_id)
    path = _preview_path(item) if _is_raw(item) else _path(item)
    media_type = "image/jpeg" if _is_raw(item) else item.media_type
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Asset image missing")
    return FileResponse(path, media_type=media_type)


@router.post("/export")
def export_assets(workspace_id: str, body: AssetExportRequest, db: Session = Depends(get_db)):
    """Export selected originals/edits as a ZIP without modifying the library."""
    _workspace(db, workspace_id)
    selected_ids = list(dict.fromkeys(body.assetIds))[:200]
    items = [
        _asset(db, workspace_id, asset_id)
        for asset_id in selected_ids
    ]

    archive = BytesIO()
    with zipfile.ZipFile(archive, mode="w", compression=zipfile.ZIP_DEFLATED) as bundle:
        used_names: set[str] = set()
        for item in items:
            path = _path(item)
            if not os.path.isfile(path):
                continue
            filename = os.path.basename(item.filename) or f"{item.id}.bin"
            if filename in used_names:
                stem, extension = os.path.splitext(filename)
                filename = f"{stem}-{item.id[:8]}{extension}"
            used_names.add(filename)
            bundle.write(path, arcname=filename)

    archive.seek(0)
    return Response(
        content=archive.read(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=photo-library-export.zip"},
    )


@router.delete("/{asset_id}")
def delete_asset(workspace_id: str, asset_id: str, db: Session = Depends(get_db)):
    _workspace(db, workspace_id)
    item = _asset(db, workspace_id, asset_id)
    path = _path(item)
    db.delete(item)
    db.commit()
    if os.path.isfile(path):
        os.remove(path)
    if os.path.isfile(_preview_path(item)):
        os.remove(_preview_path(item))
    return {"ok": True}


def delete_workspace_assets(workspace_id: str, db: Session) -> None:
    """Remove assets while deleting a workspace."""
    items = db.exec(select(AssetRecord).where(AssetRecord.workspace_id == workspace_id)).all()
    for item in items:
        path = _path(item)
        if os.path.isfile(path):
            os.remove(path)
        if os.path.isfile(_preview_path(item)):
            os.remove(_preview_path(item))
        db.delete(item)
    db.commit()
