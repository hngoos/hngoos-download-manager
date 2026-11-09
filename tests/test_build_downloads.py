"""Build tool downloads recover from upstream outages without accepting changed bytes."""

import hashlib
import io
import runpy
import tarfile
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch


class BuildDownloadTests(unittest.TestCase):
    def test_changed_upstream_source_uses_only_identical_preserved_bytes(self):
        content = b"original pinned archive"
        for preserved in (content, b"changed preserved archive"):
            with self.subTest(valid_preserved=preserved == content), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                scripts = root/"scripts"
                scripts.mkdir()
                for name in ("prepare-ffmpeg.py", "build-ffmpeg.sh"):
                    (scripts/name).write_text("build fixture", encoding="utf-8")
                target = root/"tools/ffmpeg-build/zlib-1.4.tar.gz"
                (target.parent/"zlib-1.4").mkdir(parents=True)
                bundle = io.BytesIO()
                with tarfile.open(fileobj=bundle, mode="w:gz") as archive:
                    info = tarfile.TarInfo(target.name)
                    info.size = len(preserved)
                    archive.addfile(info, io.BytesIO(preserved))
                module = runpy.run_path(str(Path(__file__).resolve().parents[1]/"scripts/prepare-ffmpeg.py"))
                module["main"].__globals__.update({
                    "__file__": str(scripts/"prepare-ffmpeg.py"),
                    "SOURCES": {"zlib-1.4": ("https://zlib.net/zlib-1.4.tar.gz",
                                              hashlib.sha256(content).hexdigest())},
                })
                with patch("urllib.request.urlopen", side_effect=[
                        io.BytesIO(b"upstream changed"), io.BytesIO(bundle.getvalue())]) as opened:
                    if preserved == content:
                        module["main"]()
                        self.assertEqual(target.read_bytes(), content)
                    else:
                        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                            module["main"]()
                        self.assertFalse(target.exists())
                    self.assertEqual(opened.call_count, 2)

    def test_published_codec_source_fallback_verifies_individual_archive_bytes(self):
        module = runpy.run_path(str(Path(__file__).resolve().parents[1]/"scripts/prepare-ffmpeg.py"))
        content = b"original codec archive"
        bundle = io.BytesIO()
        with tarfile.open(fileobj=bundle, mode="w:gz") as archive:
            info = tarfile.TarInfo("ffmpeg.tar.xz")
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
        data = bundle.getvalue()
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/"ffmpeg.tar.xz"
            for expected, success in ((hashlib.sha256(content).hexdigest(), True), ("0"*64, False)):
                target.write_bytes(b"existing cache")
                with patch("urllib.request.urlopen", return_value=io.BytesIO(data)):
                    if success:
                        module["fetch_preserved_source"](target, expected)
                        self.assertEqual(target.read_bytes(), content)
                    else:
                        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                            module["fetch_preserved_source"](target, expected)
                        self.assertEqual(target.read_bytes(), b"existing cache")

    def test_codec_download_recovers_from_timeout_with_identical_verified_source(self):
        module = runpy.run_path(str(Path(__file__).resolve().parents[1]/"scripts/prepare-ffmpeg.py"))
        content = b"verified codec source"
        with tempfile.TemporaryDirectory() as folder, patch("urllib.request.urlopen", side_effect=[
                urllib.error.URLError(TimeoutError("connection timed out")), io.BytesIO(content)]) as opened:
            target = Path(folder)/"ffmpeg.tar.xz"
            module["fetch_verified"]("https://ffmpeg.org/releases/ffmpeg.tar.xz",
                                     hashlib.sha256(content).hexdigest(), target)
            self.assertEqual(target.read_bytes(), content)
            self.assertEqual(opened.call_args.args[0].full_url, "https://www.ffmpeg.org/releases/ffmpeg.tar.xz")

    def test_codec_download_failure_is_bounded_without_replacing_cache(self):
        module = runpy.run_path(str(Path(__file__).resolve().parents[1]/"scripts/prepare-ffmpeg.py"))
        with tempfile.TemporaryDirectory() as folder, patch("urllib.request.urlopen", side_effect=OSError("offline")) as opened, \
                patch("time.sleep"):
            target = Path(folder)/"ffmpeg.tar.xz"
            target.write_bytes(b"existing cache")
            with self.assertRaises(OSError):
                module["fetch_verified"]("https://ffmpeg.org/releases/ffmpeg.tar.xz", "0"*64, target)
            self.assertEqual(opened.call_count, 6)
            self.assertEqual(target.read_bytes(), b"existing cache")

    def test_codec_checksum_mismatch_never_retries_or_replaces_cache(self):
        module = runpy.run_path(str(Path(__file__).resolve().parents[1]/"scripts/prepare-ffmpeg.py"))
        with tempfile.TemporaryDirectory() as folder, patch("urllib.request.urlopen", return_value=io.BytesIO(b"tampered")) as opened:
            target = Path(folder)/"ffmpeg.tar.xz"
            target.write_bytes(b"existing cache")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                module["fetch_verified"]("https://ffmpeg.org/releases/ffmpeg.tar.xz", "0"*64, target)
            opened.assert_called_once()
            self.assertEqual(target.read_bytes(), b"existing cache")

    def test_gateway_failure_uses_official_mirror_and_checks_pinned_hash(self):
        module = runpy.run_path(str(Path(__file__).resolve().parents[1]/"scripts/fetch-archive-tools.py"))
        content = b"verified build fixture"
        with tempfile.TemporaryDirectory() as folder, patch("urllib.request.urlopen", side_effect=[
                urllib.error.HTTPError("https://github.com", 504, "Gateway timeout", {}, None),
                io.BytesIO(content)]) as opened:
            target = Path(folder)/"7zr.exe"
            module["fetch_verified"](target, hashlib.sha256(content).hexdigest())
            self.assertEqual(target.read_bytes(), content)
            self.assertEqual(opened.call_args.args[0].full_url,
                             "https://api.github.com/repos/ip7z/7zip/releases/assets/662536918")

    def test_mirror_hash_mismatch_never_replaces_an_existing_file(self):
        module = runpy.run_path(str(Path(__file__).resolve().parents[1]/"scripts/fetch-archive-tools.py"))
        with tempfile.TemporaryDirectory() as folder, patch("urllib.request.urlopen", return_value=io.BytesIO(b"changed")):
            target = Path(folder)/"7zr.exe"
            target.write_bytes(b"previous incomplete cache")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                module["fetch_verified"](target, hashlib.sha256(b"expected").hexdigest())
            self.assertEqual(target.read_bytes(), b"previous incomplete cache")

    def test_network_retries_are_bounded_and_leave_no_partial_download(self):
        module = runpy.run_path(str(Path(__file__).resolve().parents[1]/"scripts/fetch-archive-tools.py"))
        with tempfile.TemporaryDirectory() as folder, patch("urllib.request.urlopen", side_effect=OSError("offline")) as opened, \
                patch("time.sleep"):
            target = Path(folder)/"7zr.exe"
            with self.assertRaises(OSError):
                module["fetch_verified"](target, "0"*64)
            self.assertEqual(opened.call_count, 6)
            self.assertFalse(target.exists())
