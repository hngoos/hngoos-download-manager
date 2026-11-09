import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path

ISCC = Path(os.environ.get("HDM_ISCC", "C:/Program Files (x86)/Inno Setup 6/ISCC.exe"))


@unittest.skipUnless(os.name == "nt" and ISCC.is_file(), "Windows with Inno Setup")
class InstallerLifecycleTests(unittest.TestCase):
    def assert_uninstaller_removed_itself(self, directory, keep_directory=False):
        # Inno's original process can exit before its temporary cleanup process
        # releases and removes unins000.exe. Verify the final directory too.
        deadline = time.monotonic()+20
        target = directory/"unins000.exe" if keep_directory else directory
        while target.exists() and time.monotonic() < deadline:
            time.sleep(.05)
        remaining = sorted(str(path.relative_to(directory)) for path in directory.rglob("*"))
        self.assertFalse(target.exists(), f"Uninstall left its managed files or empty directory: {remaining}")

    def test_locked_executable_aborts_uninstall_before_any_installed_file_is_removed(self):
        repository = Path(__file__).resolve().parents[1]
        code = (repository/"scripts/installer.iss").read_text(encoding="utf-8").split("[Code]", 1)[1]
        with tempfile.TemporaryDirectory(prefix="hdm-uninstall-lock-") as temporary:
            root = Path(temporary)
            payload = root/"HDM.exe"
            shutil.copy2(Path(os.environ["SystemRoot"])/"System32/ping.exe", payload)
            kept = root/"Downloads/user-file.bin"
            kept.parent.mkdir()
            kept.write_bytes(b"user download must survive")
            harness = root/"guard.iss"
            harness.write_text(
                '[Setup]\nAppName=HDM uninstall lock check\nAppVersion=1\n'
                'AppId=HDM-isolated-uninstall-lock-check\nPrivilegesRequired=lowest\n'
                'CreateUninstallRegKey=no\nCloseApplications=no\n'
                f'DefaultDirName={root/"app"}\nOutputDir={root}\nOutputBaseFilename=LockSetup\n'
                '[Files]\n'+f'Source: "{payload}"; DestDir: "{{app}}"\n'
                '[Code]\n'+code, encoding="utf-8")
            compiled = subprocess.run([str(ISCC), str(harness)], check=False, capture_output=True, timeout=60)
            self.assertEqual(compiled.returncode, 0, compiled.stdout+compiled.stderr)
            flags = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/SP-", "/NORESTART"]
            subprocess.run([str(root/"LockSetup.exe"), *flags], check=True, timeout=60)
            installed = root/"app/HDM.exe"
            process = subprocess.Popen([str(installed), "-t", "127.0.0.1"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
            try:
                self.assertIsNone(process.poll())
                removed = subprocess.run([str(root/"app/unins000.exe"), *flags], check=False, timeout=30)
                self.assertNotEqual(removed.returncode, 0, "Uninstaller deleted files while HDM was still running")
                self.assertTrue(installed.is_file())
                self.assertTrue((root/"app/unins000.dat").is_file())
            finally:
                process.terminate()
                process.wait(timeout=10)
            subprocess.run([str(root/"app/unins000.exe"), *flags], check=True, timeout=60)
            self.assertFalse(installed.exists())
            self.assert_uninstaller_removed_itself(root/"app")
            self.assertEqual(kept.read_bytes(), b"user download must survive")

    def test_upgrade_keeps_history_and_uninstall_removes_it_without_deleting_downloads(self):
        repository = Path(__file__).resolve().parents[1]
        source = (repository/"scripts/installer.iss").read_text(encoding="utf-8")
        # Execute the production uninstall rules against an isolated directory.
        section = ""
        if "[UninstallDelete]" in source:
            section = source.split("[UninstallDelete]", 1)[1].split("[", 1)[0]
        with tempfile.TemporaryDirectory(prefix="hdm-install-lifecycle-") as directory:
            root = Path(directory)
            app_data = root/"local-app-data"
            databases = []
            kept_files = []
            for name in ("HDM", "HngoosDM"):
                data = app_data/name
                data.mkdir(parents=True)
                database = data/"downloads.sqlite3"
                with closing(sqlite3.connect(database)) as connection, connection:
                    connection.execute("CREATE TABLE history (name TEXT)")
                    connection.execute("INSERT INTO history VALUES ('example.zip')")
                databases.append(database)
                for suffix in ("-wal", "-shm", "-journal"):
                    database.with_name(database.name+suffix).write_bytes(b"old SQLite sidecar")
                for path in (data/"user-download.zip", data/"staging/partial.bin"):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"keep downloaded bytes")
                    kept_files.append(path)
            external_download = root/"Downloads/example.zip"
            external_download.parent.mkdir()
            external_download.write_bytes(b"keep downloaded bytes")
            kept_files.append(external_download)
            payload = root/"payload.txt"
            payload.write_text("installer fixture", encoding="utf-8")
            old_components = []
            for name in ("playwright", "imageio_ffmpeg", "yt_dlp", "openpyxl"):
                old = root/"app/_internal"/name/"legacy-runtime.bin"
                old.parent.mkdir(parents=True)
                old.write_bytes(b"obsolete packaged component")
                old_components.append(old)
            upgrade_rules = source.split("[InstallDelete]", 1)[1].split("[", 1)[0]
            rules = section.replace("{localappdata}", str(app_data))
            self.assertNotIn("{localappdata}", rules)
            for kind, target in re.findall(r'Type:\s*(\w+);\s*Name:\s*"([^"]+)"', rules):
                if target.startswith("{app}"):
                    self.assertEqual(kind, "dirifempty", "Never recursively delete untracked application files")
                else:
                    self.assertTrue(Path(target).resolve().is_relative_to(app_data.resolve()))
            harness = root/"lifecycle.iss"
            harness.write_text(
                '[Setup]\nAppName=HDM lifecycle check\nAppVersion=1\n'
                'AppId=HDM-isolated-lifecycle-check\nPrivilegesRequired=lowest\n'
                'CreateUninstallRegKey=no\n'
                f'DefaultDirName={root / "app"}\nOutputDir={root}\n'
                'OutputBaseFilename=LifecycleSetup\n[Files]\n'
                f'Source: "{payload}"; DestDir: "{{app}}"\n'
                f'[InstallDelete]\n{upgrade_rules}\n[UninstallDelete]\n{rules}', encoding="utf-8")
            compiled = subprocess.run([str(ISCC), str(harness)], check=False, capture_output=True, timeout=60)
            self.assertEqual(compiled.returncode, 0, compiled.stdout+compiled.stderr)
            flags = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/SP-", "/NORESTART"]
            for _ in range(2):
                installed = subprocess.run([str(root/"LifecycleSetup.exe"), *flags], check=False, timeout=60)
                self.assertEqual(installed.returncode, 0)
                for old in old_components:
                    self.assertFalse(old.exists(), "Upgrade kept an obsolete runtime component")
                for database in databases:
                    # Read immutable snapshots so intentionally stale sidecars are ignored.
                    with closing(sqlite3.connect(database.as_uri()+"?immutable=1", uri=True)) as connection:
                        self.assertEqual(connection.execute("SELECT name FROM history").fetchall(),
                                         [("example.zip",)])
            removed = subprocess.run([str(root/"app/unins000.exe"), *flags], check=False, timeout=60)
            self.assertEqual(removed.returncode, 0)
            self.assert_uninstaller_removed_itself(root/"app")
            for database in databases:
                self.assertFalse(database.exists(), "Uninstall left download history behind")
                for suffix in ("-wal", "-shm", "-journal"):
                    self.assertFalse(database.with_name(database.name+suffix).exists())
            for path in kept_files:
                self.assertEqual(path.read_bytes(), b"keep downloaded bytes")
            # A user may choose the application folder as a download location.
            # Empty-directory cleanup must never delete those untracked files.
            subprocess.run([str(root/"LifecycleSetup.exe"), *flags], check=True, timeout=60)
            user_files = [root/"app/user-download.zip", root/"app/_internal/user-download.zip"]
            for path in user_files:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"preserve untracked user file")
            subprocess.run([str(root/"app/unins000.exe"), *flags], check=True, timeout=60)
            self.assert_uninstaller_removed_itself(root/"app", keep_directory=True)
            for path in user_files:
                self.assertEqual(path.read_bytes(), b"preserve untracked user file")
