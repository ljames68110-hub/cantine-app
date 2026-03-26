@echo off
echo Recherche de Python sur le disque...
echo.

for /f "delims=" %%P in ('where python 2^>nul') do (
    echo Python trouve : %%P
    goto found
)

for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
    if exist "%%D\python.exe" (
        echo Python trouve dans : %%D
        setx PATH "%PATH%;%%D;%%D\Scripts"
        echo PATH mis a jour. Relancez CMD puis retentez.
        pause
        exit /b
    )
)

echo Python introuvable automatiquement.
echo.
echo Installez Python depuis : https://www.python.org/downloads/
echo Cochez bien : Add Python to PATH
pause
exit /b

:found
echo Python est deja dans le PATH.
echo Relancez compiler_et_installer.bat
pause
