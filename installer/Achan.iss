#define AppName "Achan"
#ifndef AppVersion
  #define AppVersion "1.0.2"
#endif
#define AppPublisher "Made by Faraj"
#define AppExeName "Achan.exe"

[Setup]
AppId={{A3B1A75C-8A91-4C93-9B7C-7A61D061A3F2}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com/mahdisml/WebImmortalGuards
DefaultDirName={autopf}\Achan
DefaultGroupName=Achan
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
OutputDir=..\dist
OutputBaseFilename=Achan-Setup-{#AppVersion}
SetupIconFile=..\assets\achan.ico
WizardImageFile=..\assets\wizard-big.bmp
WizardSmallImageFile=..\assets\wizard-small.bmp
LicenseFile=..\LICENSE-ORIGINAL-MIT.txt
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\Achan.exe
UninstallDisplayName=Achan
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
ShowLanguageDialog=no

[Languages]
Name: "farsi"; MessagesFile: "Farsi.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
farsi.WelcomeLabel1=به نصب‌کننده آچان خوش آمدید
farsi.WelcomeLabel2=آچان اجزای لازم برای تونل شبکه و DNS امن را نصب می‌کند.%n%nهمه فایل‌های runtime همراه نصب‌کننده هستند؛ روی رایانه مقصد به Python نیازی نیست.
farsi.FinishedHeadingLabel=نصب آچان کامل شد
farsi.FinishedLabel=آچان با موفقیت نصب شد. می‌توانی آن را از دسکتاپ یا منوی شروع اجرا کنی.
english.WelcomeLabel1=Welcome to Achan Setup
english.WelcomeLabel2=Achan prepares your Windows network tunnel and secure DNS components.%n%nThe installer includes the application runtime. Python is not required on the target computer.
english.FinishedHeadingLabel=Installation complete
english.FinishedLabel=Achan has been installed. You can start it now from the desktop or Start menu.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\Achan\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE-ORIGINAL-MIT.txt"; DestDir: "{app}\licenses"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\build\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{autoprograms}\Achan"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\Achan.exe"
Name: "{autodesktop}\Achan"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\Achan.exe"; Tasks: desktopicon

[Run]
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "Preparing Windows runtime components..."; Flags: waituntilterminated runhidden; Check: not IsVCRedistInstalled
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: postinstall nowait skipifsilent

[Code]
function IsVCRedistInstalled(): Boolean;
var
  Installed: Cardinal;
begin
  Result := RegQueryDWordValue(HKLM64,
    'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64',
    'Installed', Installed) and (Installed = 1);
end;
