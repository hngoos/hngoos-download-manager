import hashlib
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from hngoos_dm.files import assemble_parts
from hngoos_dm.policy import TransferCancelled


class AssemblyTests(unittest.TestCase):
    def test_assembly_preserves_order_and_hashes_without_rereading_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pieces = [b"first"*200000, b"second"*150000, b"last"]
            paths = [root/f"{index}.part" for index in range(len(pieces))]
            for path, piece in zip(paths, pieces):
                path.write_bytes(piece)
            output = root/"assembled.tmp"
            original = Path.open
            opened = []
            def record(path, mode="r", *args, **kwargs):
                opened.append((path, mode))
                return original(path, mode, *args, **kwargs)
            with patch.object(Path, "open", autospec=True, side_effect=record):
                actual = assemble_parts(paths, output, threading.Event())
            content = b"".join(pieces)
            self.assertEqual(output.read_bytes(), content)
            self.assertEqual(actual, {name: hashlib.new(name, content).hexdigest()
                                      for name in ("md5", "sha1", "sha256", "sha512")})
            self.assertEqual(opened, [(output, "wb")]+[(path, "rb") for path in paths])

    def test_assembly_honors_cancellation_before_copying(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            part = root/"0.part"
            part.write_bytes(b"original")
            stop = threading.Event()
            stop.set()
            with self.assertRaises(TransferCancelled):
                assemble_parts([part], root/"assembled.tmp", stop)
            self.assertEqual(part.read_bytes(), b"original")
