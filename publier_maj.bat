@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo --- PUBLICATION D'UNE NOUVELLE VERSION ---
echo.
echo Version actuelle dans updater.py :
findstr "APP_VERSION = " updater.py
echo.
set /p VERSION="Numero de la NOUVELLE version (ex: 5.1) : "
if "%VERSION%"=="" (
    echo Aucune version saisie. Annulation.
    pause
    exit /b 1
)

echo.
echo Mise a jour de updater.py (APP_VERSION = "%VERSION%")...
powershell -NoProfile -Command "(Get-Content updater.py) -replace 'APP_VERSION = \".*\"', 'APP_VERSION = \"%VERSION%\"' | Set-Content updater.py"

findstr /C:"APP_VERSION = \"%VERSION%\"" updater.py >nul
if errorlevel 1 (
    echo ERREUR : la version n'a pas ete mise a jour dans updater.py.
    pause
    exit /b 1
)
echo OK.

echo.
echo Ajout et commit des changements...
git add -A
git commit -m "Version %VERSION%"

echo.
echo Creation du tag v%VERSION%...
git tag v%VERSION%
if errorlevel 1 (
    echo ERREUR : le tag v%VERSION% existe peut-etre deja.
    echo Choisissez un numero de version different.
    pause
    exit /b 1
)

echo.
echo Envoi vers GitHub (branche + tag)...
git push origin main
git push origin v%VERSION%

echo.
echo --- TERMINE ---
echo GitHub Actions va maintenant compiler CantineSetup.exe et publier la release v%VERSION%.
echo Suivi : https://github.com/ljames68110-hub/cantine-app/actions
echo (Comptez 2 a 5 minutes selon la disponibilite de NSIS sur le runner.)
echo.
pause
