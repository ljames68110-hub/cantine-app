; Script Inno Setup - Installateur Gestion Cantine
; Genere CantineSetup.exe (nom compatible avec le systeme de mise a jour
; de l'application : Paramètres > Mises à jour > source locale/réseau).
;
; Pré-requis : Inno Setup 6 installé (https://jrsoftware.org/isinfo.php)
; Compilation : ouvrir ce fichier dans Inno Setup puis "Compile",
;               ou en ligne de commande : ISCC.exe installer.iss
;
; Pense à mettre à jour MyAppVersion ci-dessous avant chaque nouvelle
; version, pour qu'elle corresponde à APP_VERSION dans updater.py.

#define MyAppName "Gestion Cantine"
#define MyAppVersion "5.2"
#define MyAppExeName "Cantine.exe"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Yoann Lutz
DefaultDirName={localappdata}\CantineApp
DefaultGroupName=Gestion Cantine
DisableProgramGroupPage=yes
; Installation utilisateur uniquement, pas besoin des droits administrateur
PrivilegesRequired=lowest
OutputBaseFilename=CantineSetup
OutputDir=.
SetupIconFile=cantine.ico
UninstallDisplayIcon={app}\cantine.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Files]
; Le .exe doit avoir été compilé au préalable (PyInstaller -> dist\Cantine.exe)
Source: "dist\Cantine.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "cantine.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Gestion Cantine"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\cantine.ico"
Name: "{group}\Désinstaller Gestion Cantine"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Cantine"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\cantine.ico"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Lancer {#MyAppName} maintenant"; Flags: nowait postinstall skipifsilent

[Messages]
french.FinishedLabel=%nL'installation de [name] est terminée.%n%nMot de passe par défaut : 1234%n%nVous pouvez lancer l'application via le raccourci créé.
