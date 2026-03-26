# Desinstallation forcee Gestion Cantine
Write-Host "Desinstallation en cours..." -ForegroundColor Yellow

# Fermer l'application
Stop-Process -Name "pythonw" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "python"  -Force -ErrorAction SilentlyContinue

# Supprimer les dossiers
$dossiers = @(
    "$env:LOCALAPPDATA\CantineApp",
    "$env:APPDATA\CantineApp",
    "$env:USERPROFILE\CantineApp",
    "$env:USERPROFILE\Documents\CantineApp"
)
foreach ($d in $dossiers) {
    if (Test-Path $d) {
        Remove-Item $d -Recurse -Force
        Write-Host "Supprime : $d" -ForegroundColor Green
    }
}

# Supprimer les raccourcis Bureau
$raccourcis = @(
    "$env:USERPROFILE\Desktop\Cantine.lnk",
    "$env:PUBLIC\Desktop\Cantine.lnk",
    "$env:USERPROFILE\Desktop\Gestion Cantine.lnk"
)
foreach ($r in $raccourcis) {
    if (Test-Path $r) {
        Remove-Item $r -Force
        Write-Host "Supprime : $r" -ForegroundColor Green
    }
}

# Supprimer les raccourcis Menu Demarrer
$menu = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs"
@("Cantine.lnk","Gestion Cantine.lnk","Desinstaller Cantine.lnk") | ForEach-Object {
    $f = "$menu\$_"
    if (Test-Path $f) { Remove-Item $f -Force; Write-Host "Supprime : $f" -ForegroundColor Green }
}

Write-Host ""
Write-Host "Desinstallation terminee !" -ForegroundColor Green
Read-Host "Appuyez sur Entree pour fermer"
