"""Workspace image library. Originals are stored as files, with metadata in SQLite."""

from __future__ import annotations

import os
import re
import time
import uuid
import zipfile
from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from PIL import Image, UnidentifiedImageError
from PIL.ExifTags import TAGS
from pydantic import BaseModel
from sqlalchemy import desc
from sqlmodel import Session, select

from ..models.settings import AssetRecord, WorkspaceRecord, get_session
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


class AssetExportRequest(BaseModel):
    assetIds: list[str]


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
                    pairGroup=pair_group, pairRole=_pair_role(item))


@router.get("", response_model=list[AssetOut])
def list_assets(workspace_id: str, db: Session = Depends(get_db)):
    _workspace(db, workspace_id)
    items = db.exec(select(AssetRecord).where(AssetRecord.workspace_id == workspace_id)
                    .order_by(desc(AssetRecord.created_at))).all()
    groups: dict[str, list[AssetRecord]] = {}
    for item in items:
        groups.setdefault(_pair_key(item.filename), []).append(item)
    return [
        _out(item, _pair_key(item.filename) if len(groups[_pair_key(item.filename)]) > 1 else None)
        for item in items
    ]


@router.post("", response_model=AssetOut, status_code=201)
async def upload_asset(workspace_id: str, file: UploadFile = File(...),
                       kind: str = Form("import"), db: Session = Depends(get_db)):
    _workspace(db, workspace_id)
    if kind not in {"import", "edit", "generated"}:
        raise HTTPException(status_code=422, detail="Invalid asset kind")
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
