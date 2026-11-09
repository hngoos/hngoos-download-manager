"""Enforce decimal-MB Windows distribution budgets before publishing."""

from pathlib import Path

from hngoos_dm import __version__

root = Path(__file__).resolve().parents[1]
installer = root/f"dist/HDM-Setup-{__version__}.exe"
sources = (root/"dist/HDM", root/"dist/HDMBridge.exe", root/"dist/extension",
           root/"dist/third-party-notices", root/"dist/archive-tools",
           root/"LICENSE", root/"THIRD_PARTY_NOTICES.txt")
payload = 0
for source in sources:
    if not source.exists():
        raise SystemExit(f"Missing installer payload: {source.name}")
    payload += sum(path.stat().st_size for path in source.rglob("*") if path.is_file()) if source.is_dir() else source.stat().st_size
# Reserve more than Inno Setup's generated uninstaller/log and filesystem slack.
installed_ceiling = payload+20_000_000
size = installer.stat().st_size
print(f"Installer: {size:,} bytes; payload: {payload:,} bytes; installed budget including reserve: {installed_ceiling:,} bytes")
if size >= 60_000_000 or installed_ceiling >= 200_000_000:
    raise SystemExit("Windows package exceeds the 60 MB installer / 200 MB installed budget")
