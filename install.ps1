# HDM per-user installer. Compatible with Windows PowerShell 5.1 and PowerShell 7.
[CmdletBinding()]
param(
    [switch]$Interactive,
    [switch]$DownloadOnly,
    [string]$InstallerPath
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw 'Use install.sh on macOS or Linux.'
}
if (-not [Environment]::Is64BitOperatingSystem) { throw 'HDM requires 64-bit Windows 10 or later.' }
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$hdmVersion = '0.1.13'
$hdmHash = '26a44a3d6753612d4f92c4cb1643f8b7d13a5ccac6191f37557c3bf15b53d992'
$hdmSize = 137257437
$hdmUrl = "https://github.com/hngoos/hngoos-download-manager/releases/download/v$hdmVersion/HDM-Setup-$hdmVersion.exe"
if (-not $InstallerPath) {
    $hdmFolder = Join-Path ([IO.Path]::GetTempPath()) ('HDM-install-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $hdmFolder | Out-Null
    $InstallerPath = Join-Path $hdmFolder "HDM-Setup-$hdmVersion.exe"
    Write-Output "Downloading HDM $hdmVersion..."
    Invoke-WebRequest -Uri $hdmUrl -OutFile $InstallerPath -UseBasicParsing -TimeoutSec 300
}
$hdmInstaller = Get-Item -LiteralPath $InstallerPath
if ($hdmInstaller.Length -ne $hdmSize -or
    (Get-FileHash -LiteralPath $hdmInstaller.FullName -Algorithm SHA256).Hash.ToLowerInvariant() -ne $hdmHash) {
    throw 'Installer size or SHA-256 mismatch. Installation stopped.'
}
Write-Output "Verified HDM $hdmVersion (SHA-256)."
if ($DownloadOnly) { Write-Output $hdmInstaller.FullName; return }
$hdmArguments = @('/NORESTART')
if (-not $Interactive) { $hdmArguments += @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/SP-') }
$hdmStart = @{ FilePath = $hdmInstaller.FullName; ArgumentList = $hdmArguments; Wait = $true; PassThru = $true }
if (-not $Interactive) { $hdmStart.WindowStyle = 'Hidden' }
$hdmProcess = Start-Process @hdmStart
if ($hdmProcess.ExitCode -ne 0) { throw "HDM installer exited with code $($hdmProcess.ExitCode)." }
Write-Output 'HDM installed. Open HDM from the Start menu.'
