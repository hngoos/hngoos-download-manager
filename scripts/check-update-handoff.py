"""Reproduce a stale onefile runtime and verify installer handoff without installing HDM."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from hngoos_dm.platforms import launch_installer

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--iscc", type=Path, default=Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"))
args = parser.parse_args()
assert os.name == "nt", "Windows packaging check"
repository = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="hdm-update-check-") as directory:
    folder = Path(directory)
    source = folder/"probe.py"
    source.write_text('import json,sys\nfrom pathlib import Path\n'
                      'Path(sys.argv[1]).write_text(json.dumps({"runtime":sys._MEIPASS}))\n', encoding="utf-8")
    build = subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--console",
        "--name", "HDMRuntimeProbe", "--distpath", str(folder/"dist"), "--workpath", str(folder/"build"),
        "--specpath", str(folder), str(source)], check=False, capture_output=True, text=True, timeout=180)
    assert build.returncode == 0, build.stderr
    executable = folder/"dist/HDMRuntimeProbe.exe"
    report = folder/"runtime.json"
    clean = {key: value for key, value in os.environ.items() if not key.startswith("_PYI_")}
    clean["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    baseline = subprocess.run([str(executable), str(report)], check=False, env=clean, capture_output=True,
                              timeout=30, creationflags=0x08000000)
    assert baseline.returncode == 0, baseline.stderr
    old_runtime = json.loads(report.read_text())["runtime"]
    assert not Path(old_runtime).exists(), "Probe's previous runtime must already be removed"
    stale = {key: value for key, value in clean.items() if key != "PYINSTALLER_RESET_ENVIRONMENT"}
    stale.update(_PYI_ARCHIVE_FILE=str(executable), _PYI_APPLICATION_HOME_DIR=old_runtime,
                 _PYI_PARENT_PROCESS_LEVEL="1")
    report.unlink()
    broken = subprocess.run([str(executable), str(report)], check=False, env=stale, capture_output=True,
                            timeout=30, creationflags=0x08000000)
    assert broken.returncode != 0 and b"Failed to load Python DLL" in broken.stderr, broken.stderr
    assert not report.exists()
    print("Reproduced the reported Python DLL error with a removed parent runtime.", flush=True)
    with patch.dict(os.environ, stale, clear=True):
        process = launch_installer(executable, [report])
        assert process.wait(timeout=30) == 0
    assert report.exists() and json.loads(report.read_text())["runtime"] != old_runtime
    report.unlink()
    print("New updater starts an independent runtime.", flush=True)

    # This installer has no files, shortcuts, uninstall registration or application data.
    # It executes the production InitializeSetup code, then starts only the probe.
    def quote(value):
        return '"'+str(value).replace('"', '""')+'"'
    installer_code = (repository/"scripts/installer.iss").read_text(encoding="utf-8").split("[Code]", 1)[1]
    harness = folder/"handoff.iss"
    harness.write_text("[Setup]\nAppName=HDM Runtime Handoff Check\nAppVersion=1\n"
        "CreateAppDir=no\nUninstallable=no\nPrivilegesRequired=lowest\n"
        "OutputBaseFilename=HDMRuntimeSetup\nOutputDir="+str(folder/"dist")+"\n[Run]\nFilename: "
        +quote(executable)+"; Parameters: "+quote('"'+str(report)+'"')
        +"; Flags: runhidden waituntilterminated runascurrentuser\n[Code]\n"+installer_code, encoding="utf-8")
    compiled = subprocess.run([str(args.iscc.resolve()), str(harness)], check=False, capture_output=True, text=True, timeout=60)
    assert compiled.returncode == 0, compiled.stdout+compiled.stderr
    installed = subprocess.run([str(folder/"dist/HDMRuntimeSetup.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES",
                               "/SP-", "/NORESTART"], check=False, env=stale, timeout=60, creationflags=0x08000000)
    assert installed.returncode == 0 and report.exists(), "Installer did not start the isolated runtime"
    assert json.loads(report.read_text())["runtime"] != old_runtime
    print("Installer launched from an old updater starts a fresh runtime after setup.", flush=True)
