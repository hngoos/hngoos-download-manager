import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hngoos_dm.guard import DirectoryGuard
from hngoos_dm.store import Store
from hngoos_dm.updater import canonical, verify_manifest


class UpdateTests(unittest.TestCase):
    @patch("hngoos_dm.updater.__version__", "0.1.0")
    def test_signed_release_body_accepts_valid_and_rejects_tampered_updates(self):
        import json

        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

        from hngoos_dm.updater import MANIFEST_END, MANIFEST_START, check_update

        key = Ed25519PrivateKey.generate()
        public = base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
        payload = {"version": "0.1.1", "assets": [{"name": "HDM-Setup-0.1.1.exe", "size": 10,
                                                  "sha256": "a"*64}]}
        envelope = {"payload": payload, "signature": base64.b64encode(key.sign(canonical(payload))).decode()}
        release = {"tag_name": "v0.1.1", "assets": [],
                   "body": "HDM release\n"+MANIFEST_START+json.dumps(envelope)+MANIFEST_END}
        with patch("hngoos_dm.updater.fetch_json", return_value=release), patch("hngoos_dm.updater.PUBLIC_KEY", public):
            self.assertEqual(check_update(), payload)
            envelope["payload"]["assets"][0]["sha256"] = "b"*64
            release["body"] = MANIFEST_START+json.dumps(envelope)+MANIFEST_END
            with self.assertRaisesRegex(ValueError, "Chữ ký"):
                check_update()
            release["body"] = "No signed update metadata"
            with self.assertRaisesRegex(ValueError, "manifest"):
                check_update()

    def test_download_accepts_hdm_installer_and_verifies_bytes(self):
        import hashlib
        import io
        from unittest.mock import patch

        from hngoos_dm.updater import download_installer
        content = b"HDM installer acceptance fixture"
        payload = {"version": "0.1.0", "assets": [{"name": "HDM-Setup-0.1.0.exe", "size": len(content),
                    "sha256": hashlib.sha256(content).hexdigest()}]}
        with tempfile.TemporaryDirectory() as folder, patch("hngoos_dm.updater.urllib.request.urlopen",
                return_value=io.BytesIO(content)) as request:
            output = download_installer(payload, folder, asset=payload["assets"][0])
            self.assertEqual(output.name, "HDM-Setup-0.1.0.exe")
            self.assertEqual(output.read_bytes(), content)
            self.assertEqual(request.call_args.args[0].full_url,
                "https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.0/HDM-Setup-0.1.0.exe")

    def test_selects_exact_native_package_and_rejects_missing_or_ambiguous_assets(self):
        from hngoos_dm.updater import select_installer
        names = ["HDM-Setup-0.1.3.exe", "HDM-0.1.3-macOS-arm64.dmg", "HDM-0.1.3-macOS-x64.dmg",
                 "HDM-0.1.3-Linux-x64.deb", "HDM-0.1.3-Linux-x64.AppImage", "HDM-Browser-Extension.zip"]
        payload = {"version": "0.1.3", "assets": [{"name": name} for name in names]}
        cases = [("Windows", "AMD64", None, names[0]), ("Darwin", "arm64", None, names[1]),
                 ("Darwin", "x86_64", None, names[2]), ("Linux", "x86_64", True, names[3]),
                 ("Linux", "x86_64", False, names[4])]
        for system, machine, debian, expected in cases:
            with self.subTest(system=system, machine=machine, debian=debian):
                self.assertEqual(select_installer(payload, system, machine, debian)["name"], expected)
        with self.assertRaises(ValueError):
            select_installer(payload, "Linux", "aarch64")
        payload["assets"].append({"name": names[0]})
        with self.assertRaises(ValueError):
            select_installer(payload, "Windows", "AMD64")

    def test_download_cancellation_and_corruption_never_publish_partial_packages(self):
        import hashlib
        import io
        import threading

        from hngoos_dm.updater import DownloadCancelled, download_installer
        content = b"verified update package"
        asset = {"name": "HDM-Setup-0.1.3.exe", "size": len(content),
                 "sha256": hashlib.sha256(content).hexdigest()}
        payload = {"version": "0.1.3", "assets": [asset]}
        for data in (content[:-1], content+b"extra", b"X"*len(content)):
            with self.subTest(data=data), tempfile.TemporaryDirectory() as folder:
                with (patch("hngoos_dm.updater.urllib.request.urlopen", return_value=io.BytesIO(data)),
                      self.assertRaises(ValueError)):
                    download_installer(payload, folder, asset=asset)
                self.assertEqual(list(Path(folder).iterdir()), [])
        cancel = threading.Event()
        with tempfile.TemporaryDirectory() as folder, patch("hngoos_dm.updater.urllib.request.urlopen",
                                                           return_value=io.BytesIO(content)):
            def progress(done, total):
                self.assertEqual((done, total), (len(content), len(content)))
                cancel.set()
            with self.assertRaises(DownloadCancelled):
                download_installer(payload, folder, progress=progress, cancel=cancel, asset=asset)
            self.assertEqual(list(Path(folder).iterdir()), [])
        with tempfile.TemporaryDirectory() as folder, patch("hngoos_dm.updater.urllib.request.urlopen") as request:
            with self.assertRaises(DownloadCancelled):
                download_installer(payload, folder, cancel=cancel, asset=asset)
            request.assert_not_called()
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_install_handoff_rechecks_modified_package(self):
        import hashlib

        from hngoos_dm.updater import verify_package
        content = b"verified package"
        asset = {"size": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"HDM.exe"
            path.write_bytes(content)
            self.assertEqual(verify_package(path, asset), path)
            path.write_bytes(b"X"*len(content))
            with self.assertRaises(ValueError):
                verify_package(path, asset)

    def test_rejects_unsigned_tampered_and_untrusted_manifests(self):
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        except ImportError as exc:
            raise unittest.SkipTest("updates extras not installed") from exc
        key = Ed25519PrivateKey.generate()
        public = base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
        payload = {"version": "0.1.0", "assets": [{"name": "HDM-Setup-0.1.0.exe", "size": 10, "sha256": "a"*64}]}
        envelope = {"payload": payload, "signature": base64.b64encode(key.sign(canonical(payload))).decode()}
        self.assertEqual(verify_manifest(envelope, public)["version"], "0.1.0")
        envelope["payload"]["assets"][0]["sha256"] = "b"*64
        with self.assertRaises(ValueError):
            verify_manifest(envelope, public)
        with self.assertRaises(ValueError):
            verify_manifest({"payload": payload}, public)
        other = Ed25519PrivateKey.generate()
        envelope["signature"] = base64.b64encode(other.sign(canonical(payload))).decode()
        with self.assertRaises(ValueError):
            verify_manifest(envelope, public)


class GuardTests(unittest.TestCase):
    def test_only_new_stable_risky_files_are_quarantined(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            downloads = root/"downloads"
            downloads.mkdir()
            (downloads/"old.exe").write_bytes(b"MZold")
            store = Store(root/"db")
            guard = DirectoryGuard(downloads, store, interval=60)
            try:
                risky = downloads/"new-photo.jpg"
                risky.write_bytes(b"MZsynthetic-program")
                safe = downloads/"notes.txt"
                safe.write_text("hello")
                partial = downloads/"not-done.exe.crdownload"
                partial.write_bytes(b"MZpartial")
                for _ in range(3):
                    guard.scan_once()
                self.assertFalse(risky.exists())
                self.assertTrue(risky.with_name(risky.name+".chuakiemtra").exists())
                self.assertTrue(safe.exists())
                self.assertTrue(partial.exists())
                self.assertTrue((downloads/"old.exe").exists())
                self.assertEqual(len(store.setting("guard_log")), 1)
                risky.with_name(risky.name+".chuakiemtra").rename(risky)
                guard.accept_restored(risky)
                for _ in range(3):
                    guard.scan_once()
                self.assertTrue(risky.exists())
            finally:
                guard.close()
