@echo off
chcp 65001 >nul
echo ============================================
echo   COMPILATION - Gestion Cantine (.exe)
echo ============================================
echo.

pip install pyinstaller --quiet
if errorlevel 1 (
    echo [ERREUR] PyInstaller non disponible.
    pause
    exit /b 1
)

set SCRIPT_DIR=%~dp0

pyinstaller --noconfirm --onefile --windowed ^
    --name "Cantine" ^
    --add-data "database.py;." ^
    --add-data "impression.py;." ^
    --hidden-import reportlab ^
    --hidden-import reportlab.lib ^
    --hidden-import reportlab.platypus ^
    "%SCRIPT_DIR%main.py"

if errorlevel 1 (
    echo [ERREUR] Compilation echouee.
    pause
    exit /b 1
)

echo.
echo [OK] Compilation reussie !
echo Executable : %SCRIPT_DIR%dist\Cantine.exe
echo.
pause
