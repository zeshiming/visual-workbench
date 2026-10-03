import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlmodel import Session, SQLModel, create_engine

from src.models import settings
from src.models.settings import WorkspaceRecord, WorkspaceVersionRecord
from src.services.workspace_commit import commit_workspace, read_version_image


class WorkspaceVersionTests(unittest.TestCase):
    def test_version_chain_and_readback(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        with patch.object(settings, 'WORKSPACE_IMAGES_DIR', folder.name):
            engine = create_engine('sqlite://')
            SQLModel.metadata.create_all(engine)
            with Session(engine) as db:
                record = WorkspaceRecord(id='w', title='w')
                commit_workspace(db, record, image='one', replace_image=True)
                first = record.current_version_id
                commit_workspace(db, record, image='two', replace_image=True)
                second = record.current_version_id
                commit_workspace(db, record, image='branch', replace_image=True, parent_version_id=first)
                branch = record.current_version_id
                assert first and second and first != second
                assert read_version_image(db, first) == 'one'
                assert read_version_image(db, second) == 'two'
                assert branch and read_version_image(db, branch) == 'branch'
                latest = db.get(WorkspaceRecord, 'w')
                assert latest.current_version_id == branch
                versions = db.query(WorkspaceVersionRecord).filter(WorkspaceVersionRecord.workspace_id == 'w').all()
                assert len(versions) == 3
                assert next(item for item in versions if item.id == second).parent_id == first
                assert next(item for item in versions if item.id == branch).parent_id == first
