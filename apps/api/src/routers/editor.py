"""Thin HTTP layer for the Editor workflow.

Delegates all business logic to core.orchestration.generate_image().
"""

from __future__ import annotations

import logging
import json
import time
import uuid

from fastapi import APIRouter, HTTPException

from ..core.orchestration import generate_image
from ..services.image_validation import validate_image_result
from ..services.image_utils import apply_editor_region_mask
from ..models.schemas import EditorRunRequest, EditorRunResponse
from ..models.settings import EditorRunRecord, get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/editor", tags=["editor"])


@router.post("/run", response_model=EditorRunResponse)
async def handle_editor_run(request: EditorRunRequest):
    run_id = request.run_id or uuid.uuid4().hex
    now = int(time.time() * 1000)
    with get_session() as db:
        db.add(EditorRunRecord(id=run_id, workspace_id=request.workspace_id or '',
                               input_version_id=request.version_id or '', asset_id=request.asset_id or '',
                               created_at=now, updated_at=now))
        db.commit()
    if not request.marks:
        with get_session() as db:
            record = db.get(EditorRunRecord, run_id)
            record.status = 'failed'; record.error = '至少需要一个圈选区域'; record.updated_at = int(time.time() * 1000)
            db.add(record); db.commit()
        raise HTTPException(status_code=422, detail="局部编辑至少需要一个圈选区域。")
    marks = [m.model_dump() for m in request.marks]
    raw_validation: dict[str, object] = {}

    try:
        images, text = await generate_image(
            edit_host=request.config.edit.host,
            edit_api_key=request.config.edit.key,
            edit_model=request.config.edit.model,
            image_data_url=request.image,
            marks=marks,
            image_config=request.image_config,
            validation_sink=raw_validation,
            idempotency_key=f"doushabao-{run_id}-editor",
        )
    except Exception as exc:
        with get_session() as db:
            record = db.get(EditorRunRecord, run_id)
            record.status = 'failed'; record.error = str(exc)
            record.raw_validation_json = json.dumps(raw_validation, ensure_ascii=False)
            record.updated_at = int(time.time() * 1000)
            db.add(record); db.commit()
        raise

    try:
        masked_image = apply_editor_region_mask(request.image, images[0], marks)
    except (ValueError, OSError) as exc:
        with get_session() as db:
            record = db.get(EditorRunRecord, run_id)
            record.status = 'failed'; record.error = str(exc); record.updated_at = int(time.time() * 1000)
            db.add(record); db.commit()
        raise HTTPException(status_code=502, detail={
            "code": "EDITOR_OUTPUT_INVALID",
            "message": "局部编辑模型输出无法读取或合成。",
        }) from exc
    report = validate_image_result(request.image, masked_image)
    validation = {"rawOutput": raw_validation, "finalOutput": report.to_dict()}
    if not report.ok:
        with get_session() as db:
            record = db.get(EditorRunRecord, run_id)
            record.status = 'failed'; record.validation_json = json.dumps(validation, ensure_ascii=False)
            record.raw_validation_json = json.dumps(raw_validation, ensure_ascii=False)
            record.updated_at = int(time.time() * 1000)
            db.add(record); db.commit()
        raise HTTPException(status_code=502, detail={
            "code": "EDITOR_OUTPUT_INVALID",
            "message": "局部编辑模型输出未通过图片校验。",
            "validation": validation,
        })
    with get_session() as db:
        record = db.get(EditorRunRecord, run_id)
        record.status = 'completed'; record.validation_json = json.dumps(validation, ensure_ascii=False)
        record.raw_validation_json = json.dumps(raw_validation, ensure_ascii=False)
        record.updated_at = int(time.time() * 1000)
        db.add(record); db.commit()
    return EditorRunResponse(run_id=run_id, images=[masked_image], text=text, validation=validation)
