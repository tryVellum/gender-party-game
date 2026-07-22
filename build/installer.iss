#define MyAppName "Gender Party Game"
#ifndef MyAppVersion
  #define MyAppVersion "1.2.0"
#endif
#define MyAppPublisher "tryVellum"
#define MyAppExeName "GenderPartyGame.exe"
#define FirewallRuleName "Gender Party Game (Private Network)"

[Setup]
AppId={{F0E9B88F-66D9-4A22-BA05-7E48189E54A7}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppMutex=Local\GenderPartyGameDesktopLauncher
MinVersion=10.0
DefaultDirName={autopf}\Gender Party Game
DefaultGroupName=Gender Party Game
DisableProgramGroupPage=yes
OutputDir=..\release
OutputBaseFilename=GenderPartyGame-Setup-{#MyAppVersion}
SetupIconFile=..\assets\gender-party.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
ChangesAssociations=no
ChangesEnvironment=no
AllowNoIcons=yes
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Gender Party Game installer
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные значки:"

[Files]
Source: "..\dist\GenderPartyGame\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Gender Party Game"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Gender Party Game"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""{#FirewallRuleName}"""; Flags: runhidden waituntilterminated
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""{#FirewallRuleName}"" dir=in action=allow program=""{app}\{#MyAppExeName}"" enable=yes profile=private protocol=TCP localport=5000"; Flags: runhidden waituntilterminated
Filename: "{app}\{#MyAppExeName}"; Description: "Запустить Gender Party Game"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""{#FirewallRuleName}"""; Flags: runhidden waituntilterminated; RunOnceId: "RemoveFirewallRule"

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
