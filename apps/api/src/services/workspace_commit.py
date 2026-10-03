"""Publish immutable image files via a pointer committed with workspace metadata."""

import json
import os
import uuid
from pathlib import Path

from sqlmodel import Session

from ..models import settings
from ..models.settings import WorkspaceRecord, WorkspaceImagePointer, WorkspaceVersionRecord, EditorRunRecord


def read_image(db: Session, workspace_id: str) -> str | None:
    pointer = db.get(WorkspaceImagePointer, workspace_id)
    if pointer is None:
        return settings.load_workspace_image_file(workspace_id)
    if pointer.artifact_id is None:
        return None
    path = Path(settings.WORKSPACE_IMAGES_DIR) / 'committed' / f'{pointer.artifact_id}.json'
    return json.loads(path.read_text(encoding='utf-8'))['dataUrl']


def read_version_image(db: Session, version_id: str) -> str | None:
    version = db.get(WorkspaceVersionRecord, version_id)
    if version is None or version.artifact_id is None:
        return None
    path = Path(settings.WORKSPACE_IMAGES_DIR) / 'committed' / f'{version.artifact_id}.json'
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding='utf-8'))['dataUrl']


def commit_workspace(db: Session, record: WorkspaceRecord, *, image: str | None, replace_image: bool,
                     parent_version_id: str | None = None, editor_run_id: str | None = None,
                     asset_id: str | None = None) -> None:
    artifact = None
    try:
        if replace_image:
            artifact_id = None
            if image is not None:
                artifact_id = uuid.uuid4().hex
                directory = Path(settings.WORKSPACE_IMAGES_DIR) / 'committed'
                directory.mkdir(parents=True, exist_ok=True)
                artifact = directory / f'{artifact_id}.json'
                with artifact.open('x', encoding='utf-8') as output:
                    json.dump({'dataUrl': image}, output)
                    output.flush()
                    os.fsync(output.fileno())
            pointer = db.get(WorkspaceImagePointer, record.id) or WorkspaceImagePointer(workspace_id=record.id)
            parent_id = parent_version_id or record.current_version_id
            version_id = uuid.uuid4().hex
            db.add(WorkspaceVersionRecord(id=version_id, workspace_id=record.id, parent_id=parent_id,
                                          artifact_id=artifact_id, asset_id=asset_id,
                                          operation='editor' if editor_run_id else 'image_commit'))
            pointer.artifact_id = artifact_id
            record.current_version_id = version_id
            if editor_run_id:
                editor_run = db.get(EditorRunRecord, editor_run_id)
                if editor_run is None or editor_run.workspace_id != record.id:
                    raise ValueError('EditorRun 不属于当前 Workspace')
                editor_run.output_version_id = version_id
                db.add(editor_run)
            record.has_source_image = image is not None
            db.add(pointer)
        db.add(record)
        db.commit()
    except BaseException:
        db.rollback()
        # Retain an orphan rather than risk deleting a file after an ambiguous
        # commit outcome. A later reference-aware collector can reclaim it.
        raise
