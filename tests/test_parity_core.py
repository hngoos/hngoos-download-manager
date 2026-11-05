import io
import struct
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path

from hngoos_dm.bridge import MAX_MESSAGE, handle_message, read_message, write_message
from hngoos_dm.cloud import resolve
from hngoos_dm.files import checksums
from hngoos_dm.media import MediaOptions, ydl_options
from hngoos_dm.policy import BandwidthBudget, HostPolicy, TransferCancelled
from hngoos_dm.safety import inspect_file
from hngoos_dm.store import Store


class ArchiveTests(unittest.TestCase):
    def inspect(self, entries):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"archive.zip"
            with zipfile.ZipFile(path, "w") as archive:
                for name, data in entries:
                    archive.writestr(name, data)
            return inspect_file(path, "archive.zip")

    def test_archive_shortcut_and_masquerading_program(self):
        reasons = self.inspect([("film/movie.mp4", b"video"), ("film/play.lnk", b"link"), ("photo.jpg", b"MZprogram")])
        self.assertTrue(any("lối tắt" in reason for reason in reasons))
        self.assertTrue(any("Windows" in reason for reason in reasons))

    def test_macro_renamed_to_docx(self):
        self.assertTrue(any("vbaProject" in reason for reason in self.inspect([("word/vbaProject.bin", b"macro")])) )

    def test_zip_path_traversal(self):
        self.assertTrue(any("đường dẫn" in reason for reason in self.inspect([("../../evil.txt", b"x")])))

    def test_nested_zip(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("ransomware.exe", b"MZsynthetic")
        self.assertTrue(any("ransomware.exe" in reason for reason in self.inspect([("nested.zip", buffer.getvalue())])))

    def test_ordinary_archive_is_not_flagged(self):
        self.assertEqual(self.inspect([("document.txt", b"hello"), ("images/photo.png", b"PNG")]), [])

    def test_encrypted_zip_is_not_treated_as_scanned(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("private.txt", b"private")
        data = bytearray(buffer.getvalue())
        local, central = data.find(b"PK\x03\x04"), data.find(b"PK\x01\x02")
        data[local+6] |= 1
        data[central+8] |= 1
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"locked.zip"
            path.write_bytes(data)
            self.assertTrue(any("mật khẩu" in reason for reason in inspect_file(path, path.name)))


class BridgeTests(unittest.TestCase):
    @unittest.skipUnless(__import__("os").name == "nt", "Windows DPAPI")
    def test_browser_session_scope_encryption_and_cleanup(self):
        from hngoos_dm.vault import decrypt
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder)/"db")
            message = {"id": "session", "action": "download", "kind": "video", "url": "https://www.example.com/video",
                       "cookies": [{"domain": ".example.com", "name": "session", "value": "private-value", "path": "/"}]}
            handle_message(message, store)
            data = store.inbox()[0][1]
            self.assertNotIn("private-value", str(data))
            self.assertEqual(decrypt(data["session_dpapi"])[0]["value"], "private-value")
            store.acknowledge("session")
            with store.connect() as db:
                self.assertNotIn("session_dpapi", db.execute("SELECT data FROM inbox").fetchone()[0])
            message["id"] = "wrong-domain"
            message["cookies"][0]["domain"] = "different.example"
            with self.assertRaises(ValueError):
                handle_message(message, store)
    def test_native_protocol_framing_handles_unicode(self):
        stream = io.BytesIO()
        value = {"filename": "Ảnh kỷ niệm.jpg", "ok": True}
        write_message(stream, value)
        stream.seek(0)
        self.assertEqual(read_message(stream), value)

    def test_native_message_bounds(self):
        for data in (b"xx", struct.pack("<I", MAX_MESSAGE+1), struct.pack("<I", 10)+b"{}"):
            with self.assertRaises(ValueError):
                read_message(io.BytesIO(data))
        self.assertIsNone(read_message(io.BytesIO()))

    def test_native_host_rejects_command_and_local_file(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder)/"db")
            for message in ({"action": "exec", "command": "calc"}, {"action": "download", "url": "file:///C:/secrets"}):
                with self.assertRaises(ValueError):
                    handle_message(message, store)

    def test_inbox_deduplication_and_no_cookie_storage(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder)/"db")
            message = {"id": "once", "action": "download", "url": "https://example.com/file", "cookies": "never-store"}
            self.assertFalse(handle_message(message, store)["duplicate"])
            self.assertTrue(handle_message(message, store)["duplicate"])
            self.assertNotIn("cookies", store.inbox()[0][1])
            store.acknowledge("once")
            self.assertEqual(store.inbox(), [])


class PolicyTests(unittest.TestCase):
    def test_host_penalty_persists_and_limits_inflight(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder)/"db")
            policy = HostPolicy(store, default_limit=4)
            policy.penalize("https://example.com/x", retry_after=0)
            self.assertEqual(HostPolicy(store).limits["example.com:443"], 2)
            stop = threading.Event()
            with policy.connection("https://example.com/a", stop), policy.connection("https://example.com/b", stop):
                stop.set()
                with self.assertRaises(TransferCancelled), policy.connection("https://example.com/c", stop):
                    self.fail("Exceeded limit")

    def test_shared_bandwidth_can_be_cancelled_while_waiting(self):
        budget = BandwidthBudget()
        budget.configure(bytes_per_second=100)
        stop = threading.Event()
        budget.consume(1000, stop)
        stop.set()
        began = time.monotonic()
        with self.assertRaises(TransferCancelled):
            budget.consume(1000, stop)
        self.assertLess(time.monotonic()-began, 0.1)

    def test_cloud_urls_use_official_hosts(self):
        self.assertIn("drive.usercontent.google.com", resolve("https://drive.google.com/file/d/abc123/view"))
        self.assertIn("raw=1", resolve("https://www.dropbox.com/s/abc/file.jpg?dl=0"))
        self.assertTrue(resolve("https://1drv.ms/u/s!abc").startswith("https://api.onedrive.com/"))
        self.assertEqual(resolve("https://example.com/file"), "https://example.com/file")

    def test_all_hash_algorithms(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"hello"
            path.write_bytes(b"hello")
            digests = checksums(path)
            self.assertEqual(digests["md5"], "5d41402abc4b2a76b9719d911017c592")
            self.assertEqual(len(digests["sha512"]), 128)

    def test_media_choice_subtitles_and_audio_are_explicit(self):
        settings = ydl_options("out", MediaOptions(height=720, playlist=True, subtitles=True), ffmpeg="ffmpeg")
        self.assertIn("height<=720", settings["format"])
        self.assertFalse(settings["noplaylist"])
        self.assertEqual(settings["subtitleslangs"], ["vi", "en"])
        audio = ydl_options("out", MediaOptions(audio="m4a"), ffmpeg="ffmpeg")
        self.assertEqual(audio["postprocessors"][0]["preferredcodec"], "m4a")
        with self.assertRaises(ValueError):
            ydl_options("out", MediaOptions(audio="mp3"))
