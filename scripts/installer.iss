#define AppVersion "0.1.13"
[Setup]
AppId={{E82104D8-7840-4C75-9E28-3229D109FD13}
AppName=Hngoos Download Manager
AppVersion={#AppVersion}
AppPublisher=hngoos
AppPublisherURL=https://github.com/hngoos/hngoos-download-manager
DefaultDirName={localappdata}\Programs\HDM
DefaultGroupName=HDM
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist
OutputBaseFilename=HDM-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\src\hngoos_dm\assets\branding\hdm.ico
UninstallDisplayIcon={app}\HDM.exe
[Files]
Source: "..\dist\HDM.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\HDMBridge.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\browser-extension\*"; DestDir: "{app}\browser-extension"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\third-party-notices\*"; DestDir: "{app}\third-party-notices"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\archive-tools\*"; DestDir: "{app}\archive-tools"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\HDM"; Filename: "{app}\HDM.exe"
Name: "{autodesktop}\HDM"; Filename: "{app}\HDM.exe"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "HDM"; Flags: uninsdeletevalue dontcreatekey
[Run]
Filename: "{app}\HDM.exe"; Description: "Open HDM"; Flags: nowait postinstall skipifsilent runascurrentuser

[Code]
function SetEnvironmentVariable(Name, Value: String): Boolean;
  external 'SetEnvironmentVariableW@kernel32.dll stdcall';

function InitializeSetup(): Boolean;
begin
  { Also protect upgrades started by older HDM versions that inherit _PYI_* state. }
  Result := SetEnvironmentVariable('PYINSTALLER_RESET_ENVIRONMENT', '1');
  if not Result then
    MsgBox('Unable to prepare the application runtime. Close HDM and run this installer again.', mbError, MB_OK);
end;
