; Script NSIS - Installateur Gestion Cantine
; Genere CantineSetup.exe

Unicode True

!define APP_NAME "Gestion Cantine"
!define APP_VERSION "1.0"
!define APP_EXE "Cantine.exe"
!define INSTALL_DIR "$LOCALAPPDATA\CantineApp"
!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\CantineApp"

Name "${APP_NAME} ${APP_VERSION}"
OutFile "CantineSetup.exe"
InstallDir "${INSTALL_DIR}"
InstallDirRegKey HKCU "${UNINSTALL_KEY}" "InstallLocation"
RequestExecutionLevel user
SetCompressor /SOLID lzma

; Pages de l'installateur
!include "MUI2.nsh"

!define MUI_ABORTWARNING
!define MUI_ICON "cantine.ico"
!define MUI_UNICON "cantine.ico"
!define MUI_WELCOMEPAGE_TITLE "Bienvenue dans l'installation de ${APP_NAME}"
!define MUI_WELCOMEPAGE_TEXT "Cet assistant va installer ${APP_NAME} ${APP_VERSION} sur votre ordinateur.$\r$\n$\r$\nCliquez sur Suivant pour continuer."
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Lancer ${APP_NAME} maintenant"
!define MUI_FINISHPAGE_SHOWREADME ""
!define MUI_FINISHPAGE_TITLE "Installation terminee !"
!define MUI_FINISHPAGE_TEXT "${APP_NAME} a ete installe avec succes.$\r$\n$\r$\nMot de passe par defaut : 1234"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "French"

; Installation
Section "Installation" SecMain
    SetOutPath "$INSTDIR"
    
    ; Copie des fichiers
    File "dist\Cantine.exe"
    File "cantine.ico"
    
    ; Raccourci Bureau
    CreateShortcut "$DESKTOP\Cantine.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\cantine.ico"
    
    ; Raccourci Menu Demarrer
    CreateDirectory "$SMPROGRAMS\Gestion Cantine"
    CreateShortcut "$SMPROGRAMS\Gestion Cantine\Cantine.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\cantine.ico"
    CreateShortcut "$SMPROGRAMS\Gestion Cantine\Desinstaller.lnk" "$INSTDIR\Desinstaller.exe"
    
    ; Enregistrement desinstallateur
    WriteUninstaller "$INSTDIR\Desinstaller.exe"
    WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayName" "${APP_NAME}"
    WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayVersion" "${APP_VERSION}"
    WriteRegStr HKCU "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
    WriteRegStr HKCU "${UNINSTALL_KEY}" "UninstallString" "$INSTDIR\Desinstaller.exe"
    WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\cantine.ico"
    WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoModify" 1
    WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoRepair" 1
SectionEnd

; Desinstallation
Section "Uninstall"
    Delete "$INSTDIR\${APP_EXE}"
    Delete "$INSTDIR\cantine.ico"
    Delete "$INSTDIR\Desinstaller.exe"
    RMDir /r "$INSTDIR"
    
    Delete "$DESKTOP\Cantine.lnk"
    RMDir /r "$SMPROGRAMS\Gestion Cantine"
    
    DeleteRegKey HKCU "${UNINSTALL_KEY}"
SectionEnd
