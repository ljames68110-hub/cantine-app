@echo off
cd /d "%~dp0"
echo --- COMPILATION CANTINE ---
echo.

python --version >nul 2>&1
if errorlevel 1 goto nopython
echo Python OK

echo.
echo Installation librairies...
python -m pip install reportlab pillow pyinstaller --disable-pip-version-check
if errorlevel 1 goto erreur

echo.
echo Compilation en cours (1-2 minutes)...
echo.
python -m PyInstaller --onefile --windowed --name "Cantine" --icon "cantine.ico" --add-data "cantine.db;." --add-data "cantine.ico;." main.py
if errorlevel 1 goto erreur
if not exist "dist\Cantine.exe" goto erreur

echo.
echo Copie Cantine.exe...
set D=%LOCALAPPDATA%\CantineApp
if not exist "%D%" mkdir "%D%"
copy /Y "dist\Cantine.exe" "%D%\Cantine.exe" >nul
copy /Y "cantine.ico" "%D%\cantine.ico" >nul
echo Installe dans %D%

echo.
echo Creation raccourcis...
powershell -NoProfile -Command "$ws=New-Object -ComObject WScript.Shell;$s=$ws.CreateShortcut($env:USERPROFILE+'\Desktop\Cantine.lnk');$s.TargetPath='%D%\Cantine.exe';$s.WorkingDirectory='%D%';$s.IconLocation='%D%\cantine.ico';$s.Save()"
echo Raccourci Bureau OK

set SM=%APPDATA%\Microsoft\Windows\Start Menu\Programs
powershell -NoProfile -Command "$ws=New-Object -ComObject WScript.Shell;$s=$ws.CreateShortcut('%SM%\Cantine.lnk');$s.TargetPath='%D%\Cantine.exe';$s.WorkingDirectory='%D%';$s.IconLocation='%D%\cantine.ico';$s.Save()"
echo Raccourci Menu Demarrer OK

set UNINST=%D%\desinstaller.bat
(
echo @echo off
echo set /p C=Desinstaller Cantine ? [O/N] : 
echo if /i not "%%%%C%%%%"=="O" exit /b
echo taskkill /F /IM Cantine.exe ^>nul 2^>^&1
echo rmdir /S /Q "%D%"
echo del "%USERPROFILE%\Desktop\Cantine.lnk"
echo echo Desinstalle.
echo pause
) > "%UNINST%"

powershell -NoProfile -Command "$ws=New-Object -ComObject WScript.Shell;$s=$ws.CreateShortcut('%SM%\Desinstaller Cantine.lnk');$s.TargetPath='%UNINST%';$s.Save()"
echo Desinstallateur OK

echo.
echo --- INSTALLATION TERMINEE ---
echo Raccourci sur le Bureau : Cantine
echo Mot de passe : 1234
echo.
set /p L=Lancer maintenant ? [O/N] : 
if /i "%L%"=="O" start "" "%D%\Cantine.exe"
pause
exit /b 0

:nopython
echo ERREUR : Python non detecte dans le PATH.
echo Installez Python depuis python.org et cochez ADD TO PATH.
pause
exit /b 1

:erreur
echo.
echo ERREUR - voir message ci-dessus.
pause
exit /b 1
