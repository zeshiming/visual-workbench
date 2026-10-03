import tempfile
import unittest
from unittest.mock import patch

from sqlmodel import Session, SQLModel, create_engine
from src.models import settings
from src.models.settings import WorkspaceRecord
from src.services.workspace_commit import commit_workspace, read_image


class WorkspaceCommitTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        override = patch.object(settings, 'WORKSPACE_IMAGES_DIR', folder.name)
        override.start()
        self.addCleanup(override.stop)
        self.engine = create_engine('sqlite://')
        SQLModel.metadata.create_all(self.engine)
        self.addCleanup(self.engine.dispose)
        with Session(self.engine) as db:
            commit_workspace(db, WorkspaceRecord(id='a', title='old'), image='old-image', replace_image=True)

    def test_database_failure_preserves_old_image_and_metadata(self):
        with Session(self.engine) as db:
            record = db.get(WorkspaceRecord, 'a')
            record.title = 'new'
            with patch.object(db, 'commit', side_effect=RuntimeError('db unavailable')):
                with self.assertRaises(RuntimeError):
                    commit_workspace(db, record, image='new-image', replace_image=True)
        with Session(self.engine) as db:
            self.assertEqual(db.get(WorkspaceRecord, 'a').title, 'old')
            self.assertEqual(read_image(db, 'a'), 'old-image')

    def test_image_failure_preserves_old_metadata(self):
        with Session(self.engine) as db:
            record = db.get(WorkspaceRecord, 'a')
            record.title = 'new'
            with patch('src.services.workspace_commit.os.fsync', side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    commit_workspace(db, record, image='new-image', replace_image=True)
        with Session(self.engine) as db:
            self.assertEqual(db.get(WorkspaceRecord, 'a').title, 'old')
            self.assertEqual(read_image(db, 'a'), 'old-image')

    def test_success_and_metadata_only_update_survive_new_session(self):
        with Session(self.engine) as db:
            record = db.get(WorkspaceRecord, 'a')
            record.title = 'new'
            commit_workspace(db, record, image='new-image', replace_image=True)
        with Session(self.engine) as db:
            record = db.get(WorkspaceRecord, 'a')
            record.title = 'renamed'
            commit_workspace(db, record, image=None, replace_image=False)
        with Session(self.engine) as db:
            record = db.get(WorkspaceRecord, 'a')
            self.assertEqual(record.title, 'renamed')
            self.assertIsNotNone(record.current_version_id)
            self.assertEqual(read_image(db, 'a'), 'new-image')
