import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.models import settings


class AtomicImageWriteTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        override = patch.object(settings, 'WORKSPACE_IMAGES_DIR', directory.name)
        override.start()
        self.addCleanup(override.stop)
        settings.save_workspace_image_file('photo', 'original')

    def test_failed_replace_preserves_readable_original(self):
        with patch.object(settings.os, 'replace', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                settings.save_workspace_image_file('photo', 'edited')
        self.assertEqual(settings.load_workspace_image_file('photo'), 'original')
        self.assertEqual([p.name for p in self.root.iterdir()], ['photo.json'])

    def test_failed_flush_preserves_original_then_retry_succeeds(self):
        with patch.object(settings.os, 'fsync', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                settings.save_workspace_image_file('photo', 'edited')
        self.assertEqual(settings.load_workspace_image_file('photo'), 'original')
        settings.save_workspace_image_file('photo', 'edited')
        self.assertEqual(settings.load_workspace_image_file('photo'), 'edited')

    def test_readers_see_old_file_until_atomic_publish(self):
        original_replace = settings.os.replace
        def replace(source, destination):
            self.assertEqual(settings.load_workspace_image_file('photo'), 'original')
            original_replace(source, destination)
        with patch.object(settings.os, 'replace', side_effect=replace):
            settings.save_workspace_image_file('photo', 'edited')
        self.assertEqual(settings.load_workspace_image_file('photo'), 'edited')
