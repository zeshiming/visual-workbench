import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from src.models import settings
from src.models.settings import WorkspaceRecord
from src.routers import workspaces
from src.services.workspace_commit import commit_workspace


class WorkspaceVersionConflictTests(unittest.TestCase):
    def test_stale_commit_is_rejected(self):
        pixel = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGNsSHBgYGBgYgADAA3qASRmXGo7AAAAAElFTkSuQmCC'
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
        SQLModel.metadata.create_all(engine)
        with patch.object(settings, 'WORKSPACE_IMAGES_DIR', folder.name):
            with Session(engine) as db:
                record = WorkspaceRecord(id='w', title='w')
                commit_workspace(db, record, image=pixel, replace_image=True)
                current = record.current_version_id
            app = FastAPI()
            app.include_router(workspaces.router)
            with patch.object(workspaces, 'get_session', side_effect=lambda: Session(engine)):
                with TestClient(app) as client:
                    response = client.put('/api/v1/workspaces/w/commit', json={
                        'title': 'stale', 'createdAt': 1, 'updatedAt': 2,
                        'image': pixel, 'expectedVersionId': 'old-version',
                    })
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()['detail']['code'], 'WORKSPACE_VERSION_CONFLICT')
            with Session(engine) as db:
                self.assertEqual(db.get(WorkspaceRecord, 'w').current_version_id, current)
