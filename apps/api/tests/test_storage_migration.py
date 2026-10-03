import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.services.storage_migration import migrate_legacy_images


class StorageMigrationTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.source = Path(folder.name) / 'old'
        self.target = Path(folder.name) / 'new'
        (self.source / 'assets').mkdir(parents=True)
        self.target.mkdir()
        (self.source / 'work.json').write_text('{"dataUrl":"old"}')
        (self.source / 'assets' / 'photo.jpg').write_bytes(b'photo')

    def test_copy_preserves_source_and_current_files(self):
        (self.target / 'work.json').write_text('{"dataUrl":"new"}')
        self.assertEqual(migrate_legacy_images(self.source, self.target), 1)
        self.assertEqual((self.target / 'assets/photo.jpg').read_bytes(), b'photo')
        self.assertIn('new', (self.target / 'work.json').read_text())
        self.assertIn('old', (self.source / 'work.json').read_text())

    def test_completed_migration_does_not_resurrect_deleted_files(self):
        migrate_legacy_images(self.source, self.target)
        (self.target / 'work.json').unlink()
        self.assertEqual(migrate_legacy_images(self.source, self.target), 0)
        self.assertFalse((self.target / 'work.json').exists())

    def test_copy_failure_is_retryable_and_never_publishes_partial_file(self):
        with patch('src.services.storage_migration.shutil.copyfileobj', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                migrate_legacy_images(self.source, self.target)
        self.assertFalse((self.target / '.legacy-images-v1.complete').exists())
        self.assertFalse((self.target / 'assets/photo.jpg').exists())
        self.assertEqual(migrate_legacy_images(self.source, self.target), 2)
