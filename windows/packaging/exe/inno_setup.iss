; Fastforge renders this template. It registers the Core service, which the
; release App needs to connect without a UAC prompt.
[Setup]
AppId={{APP_ID}}
AppName={{DISPLAY_NAME}}
AppVersion={{APP_VERSION}}
AppPublisher={{PUBLISHER_NAME}}
AppPublisherURL={{PUBLISHER_URL}}
AppSupportURL=https://github.com/pavru/OneXray/issues
AppUpdatesURL=https://github.com/pavru/OneXray
DefaultDirName={{INSTALL_DIR_NAME}}
DisableProgramGroupPage=yes
OutputDir=.
OutputBaseFilename={{OUTPUT_BASE_FILENAME}}
Compression=lzma2
SolidCompression=yes
SetupIconFile={{SETUP_ICON_FILE}}
UninstallDisplayIcon={app}\{{EXECUTABLE_NAME}}
WizardStyle=modern
PrivilegesRequired={{PRIVILEGES_REQUIRED}}
ArchitecturesAllowed={{ARCHITECTURES_ALLOWED}}
ArchitecturesInstallIn64BitMode={{ARCHITECTURES_INSTALL_IN_64BIT_MODE}}
MinVersion=10.0.19042
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: {% if CREATE_DESKTOP_ICON != true %}unchecked{% else %}checkedonce{% endif %}

[Files]
Source: "{{SOURCE_DIR}}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{{DISPLAY_NAME}}"; Filename: "{app}\{{EXECUTABLE_NAME}}"; WorkingDir: "{app}"
Name: "{autodesktop}\{{DISPLAY_NAME}}"; Filename: "{app}\{{EXECUTABLE_NAME}}"; WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\bhsxray"; ValueType: string; ValueName: ""; ValueData: "URL:BhsXRay Protocol"
Root: HKA; Subkey: "Software\Classes\bhsxray"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\bhsxray\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\{{EXECUTABLE_NAME}}"",0"
Root: HKA; Subkey: "Software\Classes\bhsxray\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{{EXECUTABLE_NAME}}"" ""%1"""

[Run]
Filename: "{app}\{{EXECUTABLE_NAME}}"; Description: "{cm:LaunchProgram,{{DISPLAY_NAME}}}"; Flags: nowait postinstall skipifsilent runasoriginaluser

[Code]
const
  { The App finds the service by these names; see lib/core/ffi/windows/core_service.dart. }
  CoreServiceName = '{{DISPLAY_NAME}}Core';
  CoreServiceArgs = ' -name {{DISPLAY_NAME}}Core';

function CoreExecutable: String;
begin
  Result := ExpandConstant('{app}\OneXrayCore.exe');
end;

{ Stop the running Core service so its files can be replaced. }
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Result := '';
  if not Exec(ExpandConstant('{sys}\net.exe'), 'stop ' + CoreServiceName, '',
      SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    Log('Unable to run net stop for the Core service.');
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep <> ssPostInstall then
    Exit;
  if not Exec(CoreExecutable, 'service install' + CoreServiceArgs +
      ' -display "{{DISPLAY_NAME}} Core" -pipe {{DISPLAY_NAME}}.Core' +
      ' -client {{EXECUTABLE_NAME}}', '', SW_HIDE, ewWaitUntilTerminated,
      ResultCode) or (ResultCode <> 0) then
    SuppressibleMsgBox('The {{DISPLAY_NAME}} Core service could not be ' +
      'registered (code ' + IntToStr(ResultCode) + '). Connecting will fail ' +
      'until {{DISPLAY_NAME}} is installed again.', mbError, MB_OK, IDOK);
end;

function StartupShortcutTargetsCurrentInstall(const ShortcutPath,
  ExpectedTarget: String): Boolean;
var
  Shell, Shortcut: Variant;
  TargetPath: String;
begin
  Result := False;
  if not FileExists(ShortcutPath) then
    Exit;
  try
    Shell := CreateOleObject('WScript.Shell');
    Shortcut := Shell.CreateShortcut(ShortcutPath);
    TargetPath := Shortcut.TargetPath;
    Result := (TargetPath <> '') and PathSame(TargetPath, ExpectedTarget);
  except
    Log('Unable to inspect the BhsXRay startup shortcut.');
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ExpectedTarget, ShortcutPath, CurrentCommand: String;
  ResultCode: Integer;
begin
  if CurUninstallStep <> usUninstall then
    Exit;
  if not Exec(CoreExecutable, 'service uninstall' + CoreServiceArgs, '',
      SW_HIDE, ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
    Log('Unable to remove the Core service.');
  ExpectedTarget := ExpandConstant('{app}\{{EXECUTABLE_NAME}}');
  ShortcutPath := ExpandConstant('{userstartup}\{{DISPLAY_NAME}}.lnk');
  if StartupShortcutTargetsCurrentInstall(ShortcutPath, ExpectedTarget) and
     not DeleteFile(ShortcutPath) then
    Log('Unable to remove the BhsXRay startup shortcut.');
  { Never remove another installation's protocol registration. }
  if RegQueryStringValue(HKA, 'Software\Classes\bhsxray\shell\open\command',
      '', CurrentCommand) and
     (CompareText(CurrentCommand, '"' + ExpectedTarget + '" "%1"') = 0) then
    RegDeleteKeyIncludingSubkeys(HKA, 'Software\Classes\bhsxray');
end;
