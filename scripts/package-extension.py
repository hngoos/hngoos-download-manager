"""Package runtime files only; do not ship development tests or package metadata."""

import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
files = ("manifest.json", "background.js", "retired-features.js", "options.html", "options.js",
         "popup.html", "popup.js", "connection.js", "ui-text.js", "style.css", "video.js", "takeover.js", "capture-settings.js", "capture-insert.js", "icons.js",
         "licenses/morphicons.txt", "licenses/lucide.txt", "media-capture.js",
         "assets/icons/hdm-16.png", "assets/icons/hdm-32.png", "assets/icons/hdm-48.png", "assets/icons/hdm-128.png")
runtime = root/"dist/extension"
if runtime.exists():
    assert runtime.resolve().parent == (root/"dist").resolve()
    shutil.rmtree(runtime)
for name in files:
    target = runtime/name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(root/"browser-extension"/name, target)
print("Packaged ready-to-load Chromium extension with", len(files), "runtime files")
