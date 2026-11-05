import tempfile
import unittest
import zipfile
from pathlib import Path

from hngoos_dm.extraction import extract_zip
from hngoos_dm.subtitles import movie_hash


class ExtractionTests(unittest.TestCase):
    def test_windows_ambiguous_paths_are_rejected_on_every_os(self):
        names = ("run.cmd ", "run.cmd.", "CON.txt", "LPT¹.txt", "CON .txt", "a/../b.txt",
                 "../", "folder. /notes.txt", "notes.txt:payload.cmd", "/absolute.txt",
                 "folder//notes.txt", "./notes.txt", "a\u202etxt.cmd")
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source = folder/"ambiguous.zip"
            for name in names:
                with self.subTest(name=name):
                    with zipfile.ZipFile(source, "w") as archive:
                        archive.writestr(name, b"synthetic")
                    with self.assertRaises(ValueError):
                        extract_zip(source, folder/"output")
                    self.assertFalse((folder/"output").exists())

    def test_safe_zip_is_extracted_but_program_and_traversal_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source = folder/"safe.zip"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("documents/readme.txt", "hello")
            result = extract_zip(source, folder/"output")
            self.assertEqual((result/"documents/readme.txt").read_text(), "hello")
            for name in ("evil.exe", "../../escape.txt"):
                with zipfile.ZipFile(source, "w") as archive:
                    archive.writestr(name, b"synthetic")
                with self.assertRaises(ValueError):
                    extract_zip(source, folder/"rejected")
                self.assertFalse((folder/"rejected").exists())


class SubtitleHashTests(unittest.TestCase):
    def test_hash_includes_size_and_two_64k_windows(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"movie.mp4"
            path.write_bytes(b"\x01\x00\x00\x00\x00\x00\x00\x00" * 16384)
            self.assertEqual(movie_hash(path), f"{131072+16384:016x}")
            path.write_bytes(b"small")
            with self.assertRaises(ValueError):
                movie_hash(path)
