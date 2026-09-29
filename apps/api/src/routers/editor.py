"""Thin HTTP layer for the Editor workflow.

Delegates all business logic to core.orchestration.generate_image().
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from ..core.orchestration import generate_image
from ..models.schemas import EditorRunRequest, EditorRunResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/editor", tags=["editor"])


@router.post("/run", response_model=EditorRunResponse)
async def handle_editor_run(request: EditorRunRequest):
    marks = [m.model_dump() for m in request.marks]

    images, text = await generate_image(
        edit_host=request.config.edit.host,
        edit_api_key=request.config.edit.key,
        edit_model=request.config.edit.model,
        image_data_url=request.image,
        marks=marks,
        image_config=request.image_config,
    )

    return EditorRunResponse(images=images, text=text)
