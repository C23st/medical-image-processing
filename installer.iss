; ============================================================
; 医学图像处理平台 - 安装包脚本 (Inno Setup 6)
; 前置: 已生成 dist\MedImg\ (PyInstaller), 由 build_installer.bat 自动完成
; 用法: build_installer.bat  (或 ISCC.exe installer.iss)
; 产物: dist\MedImg-Setup.exe
; ============================================================

#define MyAppName "医学图像处理平台"
#define MyAppVersion "1.0.0"
#define MyAppExeName "MedImg.exe"
#define MyAppPublisher "MedImg"

[Setup]
; 稳定的 AppId, 升级安装可覆盖
AppId={{8F4E2C1A-6B3D-4E5F-9A2C-0D7E1B5F3A96}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\MedImg
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=MedImg-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; 绿色版软件, 安装目录由用户自选, 不写系统注册表 (除卸载信息)

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"; Flags: unchecked

[Files]
Source: "dist\MedImg\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent
