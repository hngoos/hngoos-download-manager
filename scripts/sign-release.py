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
paths = [folder/f"HDM-Setup-{__version__}.exe", folder/"HDM-FFmpeg-9.0.2-Sources.tar.gz"]
for pattern in (f"HDM-{__version__}-macOS-*.dmg",):
    paths.extend(sorted(folder.glob(pattern)))
assets = [{"name": path.name, "size": path.stat().st_size,
           "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in paths]
key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(os.environ["HNGOOS_RELEASE_SIGNING_KEY"], validate=True))
payload = {"version": __version__, "assets": assets}
envelope = {"payload": payload, "signature": base64.b64encode(key.sign(canonical(payload))).decode("ascii")}
(folder/"update-manifest.json").write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
notes = f"""# Hngoos Download Manager v{__version__}

Browser integration and audio export fixes for Windows and macOS.

- The video download button is an on/off switch that persists across reloads and browser restarts.
- Browser download requests restore and activate the HDM window automatically.
- Received media links open filename, format, and quality choices without pasting again.
- Export the audio from supported videos as PCM WAV, preserving the source sample rate.

After updating HDM, reload its extension on your browser's extensions page,
then refresh existing video tabs to load the updated content script.

Choose the Windows x64 installer or the macOS DMG matching your processor.
Windows packages are not Authenticode-signed; macOS packages are not notarized.
Update metadata is signed with Ed25519.

The separate FFmpeg sources archive contains the exact codec sources and build
recipe used by the Windows package. It is provided for redistribution and is
not needed to install or use HDM.

Some sources require permission or a current download URL. DRM-protected
content is unsupported. Speed depends on the server, network, and disk.
"""
notes += "\n\n<details>\n<summary>Verify SHA-256</summary>\n\n| Package | SHA-256 |\n| --- | --- |\n"
notes += "".join(f"| {item['name']} | `{item['sha256']}` |\n" for item in assets)
notes += "\n</details>\n\n"+MANIFEST_START+json.dumps(envelope, ensure_ascii=False)+MANIFEST_END+"\n"
(folder/"release-notes.md").write_text(notes, encoding="utf-8")
print("Signed release manifest for", __version__)
