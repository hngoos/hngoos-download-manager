"""Sign release assets with an Ed25519 key provided only through the environment."""

import base64
import hashlib
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from hngoos_dm import __version__
from hngoos_dm.updater import MANIFEST_END, MANIFEST_START, canonical

folder = Path("dist")
paths = [folder/name for name in (f"HDM-Setup-{__version__}.exe", "HDM-Browser-Extension.zip")]
for pattern in (f"HDM-{__version__}-macOS-*.dmg", f"HDM-{__version__}-Linux-*.deb",
                f"HDM-{__version__}-Linux-*.AppImage"):
    paths.extend(sorted(folder.glob(pattern)))
assets = [{"name": path.name, "size": path.stat().st_size,
           "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in paths]
key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(os.environ["HNGOOS_RELEASE_SIGNING_KEY"], validate=True))
payload = {"version": __version__, "assets": assets}
envelope = {"payload": payload, "signature": base64.b64encode(key.sign(canonical(payload))).decode("ascii")}
(folder/"update-manifest.json").write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
notes = Path(f"docs/releases/v{__version__}.md").read_text(encoding="utf-8")
notes += "\n\n<details>\n<summary>Verify SHA-256</summary>\n\n| Package | SHA-256 |\n| --- | --- |\n"
notes += "".join(f"| {item['name']} | `{item['sha256']}` |\n" for item in assets)
notes += "\n</details>\n\n"+MANIFEST_START+json.dumps(envelope, ensure_ascii=False)+MANIFEST_END+"\n"
(folder/"release-notes.md").write_text(notes, encoding="utf-8")
print("Signed release manifest for", __version__)
