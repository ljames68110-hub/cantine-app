@echo off
cd /d "%~dp0"
echo ============================================
echo   Compilation installateur (Inno Setup)
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 goto nopython
echo Python OK

echo.
echo Installation des librairies...
python -m pip install reportlab pillow pyinstaller --disable-pip-version-check
if errorlevel 1 goto erreur

echo.
echo Compilation de Cantine.exe (1-2 minutes)...
echo.
python -m PyInstaller --noconfirm --onefile --windowed --name "Cantine" --icon "cantine.ico" --add-data "cantine.ico;." main.py
if errorlevel 1 goto erreur
if not exist "dist\Cantine.exe" goto erreur

echo.
echo Recherche d'Inno Setup (ISCC.exe)...
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
if not exist %ISCC% goto noinno
echo Trouvé : %ISCC%

echo.
echo Compilation de l'installateur CantineSetup.exe...
%ISCC% installer.iss
if errorlevel 1 goto erreur

echo.
echo === TERMINE ===
echo Installateur genere : CantineSetup.exe
echo (dans ce meme dossier)
echo.
pause
exit /b 0

:nopython
echo ERREUR : Python non detecte dans le PATH.
echo Installez Python depuis python.org et cochez "Add to PATH".
pause
exit /b 1

:noinno
echo ERREUR : Inno Setup 6 non trouve sur cet ordinateur.
echo Telechargez-le (gratuit) depuis https://jrsoftware.org/isdl.php
echo puis relancez ce script.
pause
exit /b 1

:erreur
echo.
echo ERREUR - voir message ci-dessus.
pause
exit /b 1
