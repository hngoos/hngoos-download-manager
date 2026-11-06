$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
& npm.cmd ci --prefix browser-extension --ignore-scripts
if ($LASTEXITCODE -ne 0) { throw 'Could not install pinned extension build dependencies.' }
node scripts/build-icons.mjs
if ($LASTEXITCODE -ne 0) { throw 'Morphicons bundle build failed.' }
$taskEnvironment = Join-Path (Get-Location) '.venv-build'
$taskPython = Join-Path $taskEnvironment 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    python -m venv $taskEnvironment
    if ($LASTEXITCODE -ne 0) { throw 'Could not create isolated build environment.' }
}
& $taskPython -m pip install '.[media,processing,pdf,web,tray,torrent,updates,excel,build]'
if ($LASTEXITCODE -ne 0) { throw 'Could not install build dependencies.' }
& $taskPython scripts/collect-notices.py
if ($LASTEXITCODE -ne 0) { throw 'Notice collection failed.' }
& $taskPython scripts/version-info.py
if ($LASTEXITCODE -ne 0) { throw 'Windows version resource generation failed.' }
& $taskPython scripts/fetch-archive-tools.py
if ($LASTEXITCODE -ne 0) { throw 'Could not verify and prepare archive inspection tools.' }
& $taskPython -m PyInstaller --noconfirm --clean --onefile --windowed --name HDM --icon src/hngoos_dm/assets/branding/hdm.ico --version-file dist/HDM-version.txt --paths src --collect-data hngoos_dm --collect-all yt_dlp --collect-all openpyxl --collect-all imageio_ffmpeg --collect-all pypdfium2 --collect-all playwright --copy-metadata yt-dlp --copy-metadata imageio-ffmpeg --copy-metadata pypdfium2 --copy-metadata libtorrent src/hngoos_dm/launcher.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
& $taskPython -m PyInstaller --noconfirm --clean --onefile --console --name HDMBridge --icon src/hngoos_dm/assets/branding/hdm.ico --version-file dist/HDMBridge-version.txt --paths src src/hngoos_dm/bridge_launcher.py
if ($LASTEXITCODE -ne 0) { throw 'Native bridge build failed.' }
& $taskPython scripts/package-extension.py
if ($LASTEXITCODE -ne 0) { throw 'Browser extension packaging failed.' }
Write-Output 'Portable application: dist\HDM.exe'
