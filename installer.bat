@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   INSTALLATION - Gestion Cantine
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installe.
    echo Telechargez : https://www.python.org/downloads/
    echo Cochez "Add Python to PATH" pendant l'installation.
    pause
    exit /b 1
)
echo [OK] Python detecte.

echo Installation des dependances...
pip install reportlab pillow --quiet --disable-pip-version-check
if errorlevel 1 (
    echo [ERREUR] Impossible d'installer les dependances.
    pause
    exit /b 1
)
echo [OK] Dependances installees.

set INSTALL_DIR=%LOCALAPPDATA%\CantineApp
echo Copie dans %INSTALL_DIR%...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
xcopy /E /Y /Q "%~dp0*" "%INSTALL_DIR%\" >nul
echo [OK] Fichiers copies.

set TARGET=%INSTALL_DIR%\main.py
set ICON=%INSTALL_DIR%\cantine.ico

REM Raccourci Bureau
set SHORTCUT=%USERPROFILE%\Desktop\Cantine.lnk
powershell -NoProfile -Command "$ws=New-Object -ComObject WScript.Shell;$s=$ws.CreateShortcut('%SHORTCUT%');$s.TargetPath='pythonw';$s.Arguments='\"%TARGET%\"';$s.WorkingDirectory='%INSTALL_DIR%';$s.IconLocation='%ICON%';$s.Description='Gestion Cantine';$s.Save()"
echo [OK] Raccourci Bureau cree.

REM Raccourci Menu Demarrer
set STARTMENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Cantine.lnk
powershell -NoProfile -Command "$ws=New-Object -ComObject WScript.Shell;$s=$ws.CreateShortcut('%STARTMENU%');$s.TargetPath='pythonw';$s.Arguments='\"%TARGET%\"';$s.WorkingDirectory='%INSTALL_DIR%';$s.IconLocation='%ICON%';$s.Description='Gestion Cantine';$s.Save()"
echo [OK] Menu Demarrer cree.

REM Desinstallateur
set UNINSTALL=%INSTALL_DIR%\desinstaller.bat
(
echo @echo off
echo chcp 65001 ^>nul
echo echo Desinstallation de Gestion Cantine...
echo set /p CONFIRM=Confirmer ? [O/N] : 
echo if /i not "%%%%CONFIRM%%%%"=="O" exit /b
echo rmdir /S /Q "%INSTALL_DIR%"
echo del /Q "%USERPROFILE%\Desktop\Cantine.lnk" 2^>nul
echo del /Q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Cantine.lnk" 2^>nul
echo del /Q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Desinstaller Cantine.lnk" 2^>nul
echo echo [OK] Application desinstallee.
echo pause
) > "%UNINSTALL%"

set UNSSHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Desinstaller Cantine.lnk
powershell -NoProfile -Command "$ws=New-Object -ComObject WScript.Shell;$s=$ws.CreateShortcut('%UNSSHORTCUT%');$s.TargetPath='%UNINSTALL%';$s.Description='Desinstaller Gestion Cantine';$s.Save()"
echo [OK] Desinstallateur cree.

echo.
echo ============================================
echo   Installation terminee avec succes !
echo   Raccourci cree sur le Bureau
echo   Menu Demarrer : cherchez "Cantine"
echo   Pour desinstaller : "Desinstaller Cantine"
echo   Mot de passe : 1234
echo ============================================
echo.
timeout /t 2 >nul
start "" pythonw "%TARGET%"
