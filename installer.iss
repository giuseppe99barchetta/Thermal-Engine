; Inno Setup Script for ThermalEngine
; This script is used by GitHub Actions to create the installer

#define MyAppName "ThermalEngine"
#define MyAppPublisher "Thermal Engine"
#define MyAppExeName "ThermalEngine.exe"
#define MyAppURL "https://github.com/giuseppe99barchetta/Thermal-Engine"
#define MyAppId "{{8B5F3F3E-8C4D-4F3E-8B5F-3F3E8C4D4F3E}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=.
OutputBaseFilename=ThermalEngine-{#MyAppVersion}-Setup
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
LZMADictionarySize=1048576
LZMANumFastBytes=273
WizardStyle=modern
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
MinVersion=10.0
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
; Update/upgrade support
UsePreviousAppDir=yes
CloseApplications=force
CloseApplicationsFilter=*.exe
RestartApplications=no
DisableWelcomePage=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "pawnio"; Description: "Install PawnIO 2.2.0 for hardware temperature access"; GroupDescription: "Hardware monitoring:"

[Files]
; Main application files
Source: "dist\ThermalEngine\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "third_party\PawnIO_setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Tasks: pawnio

; Presets - from project root (only install if they don't exist to preserve user customizations)
Source: "presets\*"; DestDir: "{app}\presets"; Flags: onlyifdoesntexist recursesubdirs createallsubdirs

[Icons]
; Start Menu shortcut
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"

; Desktop shortcut (if selected)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[InstallDelete]
; Remove the startup shortcut created by older installers. Preferences owns autostart.
Type: files; Name: "{userstartup}\{#MyAppName}.lnk"

[Run]
; Option to launch after installation
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Kill any running instances before uninstall
Filename: "{cmd}"; Parameters: "/c taskkill /f /im {#MyAppExeName} >nul 2>&1"; Flags: runhidden; RunOnceId: "KillApp"

[Code]
function PawnIOInstalled: Boolean;
begin
  Result :=
    RegKeyExists(HKLM, 'SYSTEM\CurrentControlSet\Services\PawnIO') or
    RegKeyExists(HKLM64, 'SYSTEM\CurrentControlSet\Services\PawnIO') or
    RegKeyExists(HKLM64, 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\PawnIO');
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if (CurStep = ssPostInstall) and
     WizardIsTaskSelected('pawnio') and
     (not PawnIOInstalled) then
  begin
    ResultCode := -1;
    if (not Exec(
      ExpandConstant('{tmp}\PawnIO_setup.exe'),
      '-install -silent',
      '',
      SW_HIDE,
      ewWaitUntilTerminated,
      ResultCode
    )) or (ResultCode <> 0) or (not PawnIOInstalled) then
      MsgBox(
        'ThermalEngine was installed, but PawnIO could not be installed. ' +
        'Temperature sensors may remain unavailable. You can retry PawnIO ' +
        'later from its official installer.',
        mbError,
        MB_OK
      );
  end;
end;
