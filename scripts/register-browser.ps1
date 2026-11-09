param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-p]{32}$')][string]$ExtensionId,
    [string]$BridgePath = (Join-Path $PSScriptRoot '..\dist\HDMBridge.exe')
)
$ErrorActionPreference = 'Stop'
$taskBridge = (Resolve-Path -LiteralPath $BridgePath).Path
$taskManifestDirectory = Join-Path $env:LOCALAPPDATA 'HDM\native-messaging'
New-Item -ItemType Directory -Force -Path $taskManifestDirectory | Out-Null
$taskManifestPath = Join-Path $taskManifestDirectory 'com.hngoos.download_manager.json'
$taskManifest = @{
    name = 'com.hngoos.download_manager'
    description = 'HDM browser bridge'
    path = $taskBridge
    type = 'stdio'
    allowed_origins = @("chrome-extension://$ExtensionId/")
}
$taskManifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $taskManifestPath -Encoding utf8
$taskBrowserKeys = @('Google\Chrome','Microsoft\Edge','BraveSoftware\Brave-Browser','Chromium','CocCoc\Browser','Opera Software')
foreach ($taskBrowserKey in $taskBrowserKeys) {
    $taskRegistryPath = "HKCU:\Software\$taskBrowserKey\NativeMessagingHosts\com.hngoos.download_manager"
    New-Item -Path $taskRegistryPath -Force | Out-Null
    Set-Item -LiteralPath $taskRegistryPath -Value $taskManifestPath
}
Write-Output "Registered native messaging for extension $ExtensionId. The extension connects automatically when loaded."
