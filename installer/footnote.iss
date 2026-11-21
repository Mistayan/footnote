; Footnote One for Windows (#125): the engine (footnote.exe) and the tray launcher (footnote-launcher.exe), installed per user
; in %LOCALAPPDATA%\Programs\footnote, with no administrator rights. Unsigned on purpose: see installer/README.md.
;
; Build (Inno Setup 6.7):
;   ISCC /DAppVersion=0.1.0-alpha.3 /DEngine=<path>\footnote.exe /DLauncher=<path>\footnote-launcher.exe
;        /DRuntimeDir=<folder> installer\footnote.iss
; RuntimeDir holds the Visual C++ runtime the engine links against (vcruntime140, vcruntime140_1, msvcp140, msvcp140_1,
; vcomp140), copied beside footnote.exe so it runs on a fresh Windows without the VC++ Redistributable (app-local deployment).
;
; Decisions (#125, 2026-11-21): desktop shortcut is an opt-in checkbox; starting with Windows in the tray is on by default and
; can be unchecked. Data (memories, indexes, settings) lives in the state folder, apart from the program: neither an upgrade
; nor an uninstall touches it.

#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif
#ifndef Engine
  #define Engine "..\target\release\footnote.exe"
#endif
#ifndef Launcher
  #define Launcher "..\apps\launcher\src-tauri\target\release\footnote-launcher.exe"
#endif
#ifndef OutDir
  #define OutDir "out"
#endif

[Setup]
AppId={{6F1D2C4B-8E57-4C1A-9B3E-2D7F0A5C9E41}
AppName=Footnote One
AppVersion={#AppVersion}
AppVerName=Footnote One {#AppVersion}
AppPublisher=Footnote (open source)
AppPublisherURL=https://github.com/bobcat88/footnote
AppSupportURL=https://github.com/bobcat88/footnote/issues
AppUpdatesURL=https://github.com/bobcat88/footnote/releases
; Agents' hooks and MCP configs point at this folder, so it is fixed.
DefaultDirName={localappdata}\Programs\footnote
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=no
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Windows 10 1809 or later (WebView2).
MinVersion=10.0.17763
OutputDir={#OutDir}
OutputBaseFilename=Footnote-Setup-{#AppVersion}-x64
SetupIconFile=..\apps\launcher\src-tauri\icons\icon.ico
UninstallDisplayIcon={app}\footnote-launcher.exe
UninstallDisplayName=Footnote One
WizardStyle=modern dynamic
Compression=lzma2/max
SolidCompression=yes
; Never close the agents' running MCP servers: a footnote.exe in use is renamed aside instead (see CurStepChanged).
CloseApplications=no
RestartApplications=no
ChangesEnvironment=yes

[Messages]
WelcomeLabel2=This installs Footnote One [ver]: local memory, docs search, code graph and leaner tool output for your coding agents.%n%nEverything runs on this computer. No account, no telemetry. No administrator rights needed.

[Tasks]
Name: "startup"; Description: "Start Footnote with Windows, in the tray (notification area)"
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
Name: "addtopath"; Description: "Add footnote to PATH, so terminals and agents can run it"
Name: "agents"; Description: "Connect the coding agents found on this computer now (footnote install: Memory and Lean hooks, MCP server)"; Flags: unchecked

[Files]
Source: "{#Engine}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Launcher}"; DestDir: "{app}"; Flags: ignoreversion
#ifdef RuntimeDir
Source: "{#RuntimeDir}\vcruntime140.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RuntimeDir}\vcruntime140_1.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RuntimeDir}\msvcp140.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RuntimeDir}\msvcp140_1.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RuntimeDir}\vcomp140.dll"; DestDir: "{app}"; Flags: ignoreversion
#endif
Source: "README.md"; DestDir: "{app}"; DestName: "INSTALLER-README.md"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\Footnote"; Filename: "{app}\footnote-launcher.exe"; Comment: "Footnote One"
Name: "{userdesktop}\Footnote"; Filename: "{app}\footnote-launcher.exe"; Comment: "Footnote One"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Footnote"; ValueData: """{app}\footnote-launcher.exe"" --tray"; Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{app}\footnote.exe"; Parameters: "install"; StatusMsg: "Connecting your coding agents..."; Flags: runhidden waituntilterminated; Tasks: agents
Filename: "{app}\footnote-launcher.exe"; Description: "Open Footnote"; Flags: nowait postinstall skipifsilent
Filename: "{app}\footnote-launcher.exe"; Parameters: "--tray"; Flags: nowait skipifnotsilent; Tasks: startup

[UninstallRun]
; Take Footnote out of the agents first, so their hooks do not point at a missing program. Data and settings are kept.
Filename: "{app}\footnote.exe"; Parameters: "uninstall --memory --lean"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveAgentHooks"
Filename: "{sys}\taskkill.exe"; Parameters: "/IM footnote-launcher.exe /F"; Flags: runhidden waituntilterminated; RunOnceId: "StopLauncher"

[UninstallDelete]
; Copies set aside by an upgrade or by `footnote update`.
Type: files; Name: "{app}\*.replaced-*"

[Code]
const
  EnvKey = 'Environment';

function Stamp: String;
begin
  Result := GetDateTimeString('yyyymmddhhnnss', #0, #0);
end;

{ Windows lets a running program be renamed, not overwritten. The agents keep footnote.exe open (MCP server, daemon), so the
  old one is renamed aside, the way `footnote update` does it, and the new one is copied in its place. }
procedure SetAside(const Name: String);
var
  Path: String;
begin
  Path := ExpandConstant('{app}\' + Name);
  if FileExists(Path) then
    if not RenameFile(Path, Path + '.replaced-' + Stamp) then
      Log('Could not set aside ' + Path);
end;

{ The launcher is ours: close it for an upgrade, so the new one starts clean. }
procedure StopLauncher;
var
  Code: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/IM footnote-launcher.exe /F', '', SW_HIDE, ewWaitUntilTerminated, Code);
end;

function PathHas(const Paths, Dir: String): Boolean;
begin
  Result := Pos(';' + Uppercase(Dir) + ';', ';' + Uppercase(Paths) + ';') > 0;
end;

procedure AddToPath(const Dir: String);
var
  Paths: String;
begin
  if not RegQueryStringValue(HKCU, EnvKey, 'Path', Paths) then Paths := '';
  if PathHas(Paths, Dir) then exit;
  if (Paths <> '') and (Copy(Paths, Length(Paths), 1) <> ';') then Paths := Paths + ';';
  RegWriteExpandStringValue(HKCU, EnvKey, 'Path', Paths + Dir);
end;

procedure RemoveFromPath(const Dir: String);
var
  Paths: String;
  P: Integer;
begin
  if not RegQueryStringValue(HKCU, EnvKey, 'Path', Paths) then exit;
  Paths := ';' + Paths + ';';
  P := Pos(';' + Uppercase(Dir) + ';', Uppercase(Paths));
  if P = 0 then exit;
  Delete(Paths, P, Length(Dir) + 1);
  Paths := Copy(Paths, 2, Length(Paths) - 2);
  RegWriteExpandStringValue(HKCU, EnvKey, 'Path', Paths);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    StopLauncher;
    SetAside('footnote.exe');
    SetAside('footnote-launcher.exe');
    { A running footnote.exe also holds its runtime DLLs. }
    SetAside('vcruntime140.dll');
    SetAside('vcruntime140_1.dll');
    SetAside('msvcp140.dll');
    SetAside('msvcp140_1.dll');
    SetAside('vcomp140.dll');
  end;
  if CurStep = ssPostInstall then
  begin
    if WizardIsTaskSelected('addtopath') then AddToPath(ExpandConstant('{app}'));
    { Unchecking "start with Windows" on a reinstall removes the entry a previous install made. }
    if not WizardIsTaskSelected('startup') then
      RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'Footnote');
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then RemoveFromPath(ExpandConstant('{app}'));
end;
