"""Only a signed, intact extension package can replace the user's saved ZIP."""

import base64
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from hngoos_dm.extension_package import download_extension


class DevelopmentExtensionTests(unittest.TestCase):
    def test_bundled_zip_location_matches_windows_mac_and_development_packages(self):
        import sys

        from hngoos_dm.extension_package import bundled_extension_path
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for platform, executable, expected in (
                ("win32", root/"HDM.exe", root/"HDM-Browser-Extension.zip"),
                ("darwin", root/"HDM.app/Contents/MacOS/HDM",
                 root/"HDM.app/Contents/Resources/HDM-Browser-Extension.zip"),
            ):
                with patch.object(sys, "frozen", True, create=True), \
                        patch.object(sys, "platform", platform), patch.object(sys, "executable", str(executable)):
                    self.assertEqual(bundled_extension_path(), expected)
            with patch.object(sys, "frozen", False, create=True):
                self.assertEqual(bundled_extension_path(),
                                 Path(__file__).resolve().parents[1]/"dist/HDM-Browser-Extension.zip")

    def test_installation_prepares_ready_to_load_folder_without_save_dialog(self):
        from hngoos_dm.extension_package import prepare_extension_folder
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder)/"browser-extension"
            result = prepare_extension_folder(destination)
            self.assertEqual(result, destination)
            manifest = json.loads((result/"manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["manifest_version"], 3)
            self.assertTrue((result/"background.js").is_file())
            self.assertTrue((result/"capture-insert.js").is_file())
            self.assertFalse((result/"test").exists())

    def test_installation_rejects_zip_traversal_and_preserves_existing_extension(self):
        from hngoos_dm.extension_package import prepare_extension_folder
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder)/"browser-extension"
            destination.mkdir()
            manifest = destination/"manifest.json"
            manifest.write_text("keep existing package")
            def malicious(target):
                with zipfile.ZipFile(target, "w") as archive:
                    archive.writestr("manifest.json", '{"manifest_version":3,"name":"HDM"}')
                    archive.writestr("../outside.js", "unexpected")
            with patch("hngoos_dm.extension_package.prepare_extension", side_effect=malicious), \
                    self.assertRaises(ValueError):
                prepare_extension_folder(destination)
            self.assertEqual(manifest.read_text(), "keep existing package")
            self.assertFalse((Path(folder)/"outside.js").exists())

    def test_development_package_contains_only_runtime_and_all_imported_modules(self):
        import zipfile

        from hngoos_dm.extension_package import build_development_extension
        source = Path(__file__).resolve().parents[1]/"browser-extension"
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/"HDM-Browser-Extension.zip"
            build_development_extension(target, source)
            with zipfile.ZipFile(target) as archive:
                names = archive.namelist()
                self.assertIn("capture-settings.js", names)
                self.assertIn("manifest.json", names)
                self.assertTrue(all(not name.startswith(("test/", "node_modules/")) for name in names))
                self.assertNotIn("package-lock.json", names)
                for name in names:
                    if name.endswith(".js"):
                        import re
                        for module in re.findall(r"from\s+['\"]\./([^'\"]+)['\"]", archive.read(name).decode()):
                            self.assertIn(module, names, (name, module))
from hngoos_dm.updater import MANIFEST_END, MANIFEST_START, canonical


class ExtensionPackageTests(unittest.TestCase):
    def test_verifies_signature_and_bytes_and_preserves_existing_file_on_failure(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        key = Ed25519PrivateKey.generate()
        public = base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("manifest.json", '{"manifest_version":3,"name":"HDM","version":"0.1.7"}')
        content = buffer.getvalue()
        asset = {"name": "HDM-Browser-Extension.zip", "size": len(content),
                 "sha256": hashlib.sha256(content).hexdigest()}
        payload = {"version": "0.1.7", "assets": [asset]}
        envelope = {"payload": payload, "signature": base64.b64encode(key.sign(canonical(payload))).decode()}
        release = {"tag_name": "v0.1.7", "body": MANIFEST_START+json.dumps(envelope)+MANIFEST_END}
        with tempfile.TemporaryDirectory() as folder, \
                patch("hngoos_dm.extension_package.fetch_json", return_value=release), \
                patch("hngoos_dm.updater.PUBLIC_KEY", public):
            target = Path(folder)/"extension.zip"
            with patch("hngoos_dm.updater.urllib.request.urlopen", return_value=io.BytesIO(content)):
                self.assertEqual(download_extension(target), target)
            self.assertEqual(target.read_bytes(), content)
            for data in (content[:-1], b"X"*len(content), content+b"extra"):
                with patch("hngoos_dm.updater.urllib.request.urlopen", return_value=io.BytesIO(data)), \
                        self.assertRaises(ValueError):
                    download_extension(target)
                self.assertEqual(target.read_bytes(), content)
                self.assertEqual(list(Path(folder).iterdir()), [target])
            envelope["payload"]["assets"][0]["sha256"] = "0"*64
            release["body"] = MANIFEST_START+json.dumps(envelope)+MANIFEST_END
            with patch("hngoos_dm.updater.urllib.request.urlopen") as network:
                with self.assertRaisesRegex(ValueError, "Chữ ký"):
                    download_extension(target)
                network.assert_not_called()
            self.assertEqual(target.read_bytes(), content)
