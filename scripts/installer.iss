#define AppVersion "0.1.3"
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
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\src\hngoos_dm\assets\branding\hdm.ico
UninstallDisplayIcon={app}\HDM.exe
[Files]
Source: "..\dist\HDM\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\HDMBridge.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\extension\*"; DestDir: "{app}\extension"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\third-party-notices\*"; DestDir: "{app}\third-party-notices"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\archive-tools\*"; DestDir: "{app}\archive-tools"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\HDM"; Filename: "{app}\HDM.exe"
Name: "{autodesktop}\HDM"; Filename: "{app}\HDM.exe"; Tasks: desktopicon
[InstallDelete]
Type: files; Name: "{app}\HDM-Browser-Extension.zip"
; Replace managed runtime trees so an upgrade also releases their old disk space.
Type: filesandordirs; Name: "{app}\_internal\playwright"
Type: filesandordirs; Name: "{app}\_internal\imageio_ffmpeg"
Type: filesandordirs; Name: "{app}\_internal\greenlet"
Type: filesandordirs; Name: "{app}\_internal\pyee"
Type: filesandordirs; Name: "{app}\_internal\yt_dlp"
Type: filesandordirs; Name: "{app}\_internal\openpyxl"
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "HDM"; Flags: uninsdeletevalue dontcreatekey
[Run]
Filename: "{app}\HDM.exe"; Description: "Open HDM"; Flags: nowait postinstall skipifsilent runascurrentuser

[UninstallDelete]
; Older upgrades can leave this managed runtime parent outside the uninstall log.
; Remove it only when empty, preserving any untracked files.
Type: dirifempty; Name: "{app}\_internal"
Type: dirifempty; Name: "{app}"
; Remove application history/settings on uninstall, never user downloads or staging.
; Installing an update does not execute this section.
Type: files; Name: "{localappdata}\HDM\downloads.sqlite3"
Type: files; Name: "{localappdata}\HDM\downloads.sqlite3-wal"
Type: files; Name: "{localappdata}\HDM\downloads.sqlite3-shm"
Type: files; Name: "{localappdata}\HDM\downloads.sqlite3-journal"
Type: files; Name: "{localappdata}\HngoosDM\downloads.sqlite3"
Type: files; Name: "{localappdata}\HngoosDM\downloads.sqlite3-wal"
Type: files; Name: "{localappdata}\HngoosDM\downloads.sqlite3-shm"
Type: files; Name: "{localappdata}\HngoosDM\downloads.sqlite3-journal"

[Code]
function OpenApplicationFile(FileName: String; DesiredAccess, ShareMode,
  SecurityAttributes, CreationDisposition, FlagsAndAttributes, TemplateFile: LongWord): THandle;
  external 'CreateFileW@kernel32.dll stdcall';
function CloseApplicationFile(Handle: THandle): Boolean;
  external 'CloseHandle@kernel32.dll stdcall';

function InitializeUninstall(): Boolean;
var
  Names: array of String;
  Index: Integer;
  Handle: THandle;
  Path: String;
begin
  { Abort before removing any files if the app or bridge still holds its binary. }
  Result := True;
  Names := ['HDM.exe', 'HDMBridge.exe'];
  for Index := 0 to GetArrayLength(Names) - 1 do
  begin
    Path := ExpandConstant('{app}\') + Names[Index];
    if FileExists(Path) then
    begin
      Handle := OpenApplicationFile(Path, $C0000000, 0, 0, 3, $80, 0);
      if Handle = THandle(-1) then
      begin
        Log('Uninstall stopped: application binary is still in use: ' + Path);
        SuppressibleMsgBox('HDM is still running or its files are in use. Choose Exit from the HDM tray icon, then try again. If HDM is unresponsive, restart Windows before uninstalling.', mbError, MB_OK, IDOK);
        Result := False;
        Exit;
      end;
      CloseApplicationFile(Handle);
    end;
  end;
end;

function SetEnvironmentVariable(Name, Value: String): Boolean;
  external 'SetEnvironmentVariableW@kernel32.dll stdcall';

function InitializeSetup(): Boolean;
begin
  { Also protect upgrades started by older HDM versions that inherit _PYI_* state. }
  Result := SetEnvironmentVariable('PYINSTALLER_RESET_ENVIRONMENT', '1');
  if not Result then
    MsgBox('Unable to prepare the application runtime. Close HDM and run this installer again.', mbError, MB_OK);
end;
