import errno
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hngoos_dm.files import deliver, publish


class DeliveryTests(unittest.TestCase):
    def test_cross_volume_copy_preserves_content_and_never_exposes_partial_final_name(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source = folder/"local.bin"
            source.write_bytes(b"finished and verified"*1000)
            expected = source.read_bytes()
            destination = folder/"cloud"
            attempts = []
            def cross_device(staged, target, name):
                attempts.append(Path(staged))
                if len(attempts) == 1:
                    self.assertFalse((destination/name).exists())
                    raise OSError(errno.EXDEV, "different device")
                self.assertTrue(Path(staged).name.endswith(".tmp"))
                self.assertFalse((destination/name).exists())
                return publish(staged, target, name)
            with patch("hngoos_dm.files.publish", side_effect=cross_device):
                result = deliver(source, destination, "file.bin")
            self.assertEqual(result.read_bytes(), expected)
            self.assertFalse(source.exists())
            self.assertEqual([p.name for p in destination.iterdir() if ":" not in p.name], ["file.bin"])
