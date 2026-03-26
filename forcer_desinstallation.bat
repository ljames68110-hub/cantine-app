@echo off
chcp 65001 >nul
echo ============================================
echo   DESINSTALLATION FORCEE - Gestion Cantine
echo ============================================
echo.
echo Ceci va supprimer TOUS les fichiers de l'application.
echo.
set /p CONFIRM=Confirmer ? [O/N] : 
if /i not "%CONFIRM%"=="O" (
    echo Annule.
    pause
    exit /b
)

echo.
echo Suppression en cours...

REM ── Tuer le processus si en cours ────────────
taskkill /F /IM pythonw.exe /FI "WINDOWTITLE eq Gestion Cantine*" >nul 2>&1
taskkill /F /IM python.exe   /FI "WINDOWTITLE eq Gestion Cantine*" >nul 2>&1

REM ── Supprimer les dossiers d'installation ────
set DIRS=^
  "%LOCALAPPDATA%\CantineApp" ^
  "%APPDATA%\CantineApp" ^
  "%PROGRAMFILES%\CantineApp" ^
  "%PROGRAMFILES(X86)%\CantineApp" ^
  "%USERPROFILE%\CantineApp" ^
  "%USERPROFILE%\Documents\CantineApp"

for %%D in (%DIRS%) do (
    if exist %%D (
        echo Suppression : %%D
        rmdir /S /Q %%D >nul 2>&1
    )
)

REM ── Supprimer les raccourcis Bureau ──────────
set SHORTCUTS=^
  "%USERPROFILE%\Desktop\Cantine.lnk" ^
  "%PUBLIC%\Desktop\Cantine.lnk" ^
  "%USERPROFILE%\Desktop\Gestion Cantine.lnk"

for %%S in (%SHORTCUTS%) do (
    if exist %%S (
        echo Suppression raccourci : %%S
        del /Q %%S >nul 2>&1
    )
)

REM ── Supprimer les raccourcis Menu Démarrer ───
set STARTMENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs
del /Q "%STARTMENU%\Cantine.lnk"             >nul 2>&1
del /Q "%STARTMENU%\Gestion Cantine.lnk"     >nul 2>&1
del /Q "%STARTMENU%\Desinstaller Cantine.lnk">nul 2>&1

REM ── Supprimer le dossier courant si c'est l'ancienne install ──
if exist "%~dp0main.py" (
    echo Suppression du dossier source : %~dp0
    REM on ne supprime pas le script lui-meme, on programme la suppression au reboot
    rd /S /Q "%~dp0" >nul 2>&1
)

echo.
echo ============================================
echo   Desinstallation terminee !
echo   Tous les fichiers et raccourcis supprimes.
echo ============================================
echo.
pause
