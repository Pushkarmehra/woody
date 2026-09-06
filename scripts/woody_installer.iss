; ==============================================================================
; Inno Setup Script for Woody v3.0 Windows Installer
; Compiles a professional single-file setup installer: Woody_Setup_v3.0.exe
; ==============================================================================

#define MyAppName "Woody AI Operating System"
#define MyAppVersion "3.0.0"
#define MyAppPublisher "Pushkar Mehra"
#define MyAppURL "https://github.com/Pushkarmehra/Wodi"
#define MyAppExeName "woody.exe"

[Setup]
AppId={{E57C3241-9F3A-4E38-B7CA-46A29C8B70DF}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\Woody
DefaultGroupName=Woody AI
AllowNoIcons=yes
OutputDir=..\dist
OutputBaseFilename=Woody_Setup_v3.0
SetupIconFile=..\assets\woody.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\assets\woody.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
Name: "peticon"; Description: "Create Desktop Shortcut for Woody AI Pet Companion"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
Name: "hudicon"; Description: "Create Desktop Shortcut for Woody Command Center HUD"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: "..\dist\woody\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\assets\woody.ico"; DestDir: "{app}\assets"; Flags: ignoreversion

[Icons]
; Start Menu entries
Name: "{group}\Woody AI Operating System"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\woody.ico"
Name: "{group}\Woody AI Desktop Pet"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--pet"; IconFilename: "{app}\assets\woody.ico"
Name: "{group}\Woody Command Center"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--web-ui"; IconFilename: "{app}\assets\woody.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"

; Desktop Shortcuts
Name: "{autodesktop}\Woody AI Operating System"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\woody.ico"; Tasks: desktopicon
Name: "{autodesktop}\Woody AI Desktop Pet"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--pet"; IconFilename: "{app}\assets\woody.ico"; Tasks: peticon
Name: "{autodesktop}\Woody Command Center"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--web-ui"; IconFilename: "{app}\assets\woody.ico"; Tasks: hudicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
