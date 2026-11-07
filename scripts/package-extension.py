"""Package runtime files only; do not ship development tests or package metadata."""

import shutil
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parents[1]
files = ("manifest.json", "background.js", "filters.js", "options.html", "options.js",
         "popup.html", "popup.js", "style.css", "video.js", "takeover.js", "capture-settings.js", "capture-insert.js", "icons.js", "invoice-capture.js",
         "licenses/morphicons.txt", "licenses/lucide.txt", "media-capture.js", "site-protection.js",
         "assets/icons/hdm-16.png", "assets/icons/hdm-32.png", "assets/icons/hdm-48.png", "assets/icons/hdm-128.png")
destination = root/"dist/HDM-Browser-Extension.zip"
destination.parent.mkdir(parents=True, exist_ok=True)
runtime = root/"dist/browser-extension"
if runtime.exists():
    assert runtime.resolve().parent == (root/"dist").resolve()
    shutil.rmtree(runtime)
with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
    for name in files:
        archive.write(root/"browser-extension"/name, name)
        target = root/"dist/browser-extension"/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root/"browser-extension"/name, target)
print("Packaged Chromium extension with", len(files), "runtime files at ZIP root")
