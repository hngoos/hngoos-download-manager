import os
import re
import sqlite3
import subprocess
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

ISCC = Path(os.environ.get("HDM_ISCC", "C:/Program Files (x86)/Inno Setup 6/ISCC.exe"))


@unittest.skipUnless(os.name == "nt" and ISCC.is_file(), "Windows with Inno Setup")
class InstallerLifecycleTests(unittest.TestCase):
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
            rules = section.replace("{localappdata}", str(app_data))
            self.assertNotIn("{localappdata}", rules)
            for target in re.findall(r'Name:\s*"([^"]+)"', rules):
                self.assertTrue(Path(target).resolve().is_relative_to(app_data.resolve()))
            harness = root/"lifecycle.iss"
            harness.write_text(
                '[Setup]\nAppName=HDM lifecycle check\nAppVersion=1\n'
                'AppId=HDM-isolated-lifecycle-check\nPrivilegesRequired=lowest\n'
                'CreateUninstallRegKey=no\n'
                f'DefaultDirName={root / "app"}\nOutputDir={root}\n'
                'OutputBaseFilename=LifecycleSetup\n[Files]\n'
                f'Source: "{payload}"; DestDir: "{{app}}"\n'
                f'[UninstallDelete]\n{rules}', encoding="utf-8")
            compiled = subprocess.run([str(ISCC), str(harness)], check=False, capture_output=True, timeout=60)
            self.assertEqual(compiled.returncode, 0, compiled.stdout+compiled.stderr)
            flags = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/SP-", "/NORESTART"]
            for _ in range(2):
                installed = subprocess.run([str(root/"LifecycleSetup.exe"), *flags], check=False, timeout=60)
                self.assertEqual(installed.returncode, 0)
                for database in databases:
                    # Read immutable snapshots so intentionally stale sidecars are ignored.
                    with closing(sqlite3.connect(database.as_uri()+"?immutable=1", uri=True)) as connection:
                        self.assertEqual(connection.execute("SELECT name FROM history").fetchall(),
                                         [("example.zip",)])
            removed = subprocess.run([str(root/"app/unins000.exe"), *flags], check=False, timeout=60)
            self.assertEqual(removed.returncode, 0)
            for database in databases:
                self.assertFalse(database.exists(), "Uninstall left download history behind")
                for suffix in ("-wal", "-shm", "-journal"):
                    self.assertFalse(database.with_name(database.name+suffix).exists())
            for path in kept_files:
                self.assertEqual(path.read_bytes(), b"keep downloaded bytes")
