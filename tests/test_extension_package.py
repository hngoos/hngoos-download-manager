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
