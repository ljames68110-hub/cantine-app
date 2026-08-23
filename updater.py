"""
updater.py — Gestion des mises à jour de Gestion Cantine.

Trois sources possibles (configurables dans Paramètres > Mises à jour) :
  - "github" : dernière release GitHub du dépôt (Internet requis)
  - "reseau" : dossier réseau partagé (ex: \\\\SERVEUR\\partage\\cantine_maj)
  - "local"  : dossier local / clé USB (ex: D:\\cantine_maj)

Pour "reseau" et "local", le dossier doit contenir :
  - version.txt      : la version disponible, ex. "5.1"
  - CantineSetup.exe : l'installeur à jour (généré par le workflow GitHub Actions)
  - notes.txt        : (optionnel) description des nouveautés, affichée à l'utilisateur

La mise à jour réutilise l'installeur NSIS existant (CantineSetup.exe) en mode
silencieux (/S), ce qui évite de dupliquer la logique d'installation/raccourcis.
"""
import os
import sys
import json
import shutil
import tempfile
import subprocess
import urllib.request
import urllib.error

# ─────────────────────────────────────────────
# Version actuelle de l'application
# À incrémenter à chaque nouvelle release (doit correspondre au tag "vX.Y")
# ─────────────────────────────────────────────
APP_VERSION = "5.8"

GITHUB_REPO = "ljames68110-hub/cantine-app"
GITHUB_API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
NOM_INSTALLEUR = "CantineSetup.exe"
NOM_PROCESSUS = "Cantine.exe"

TIMEOUT_RESEAU = 8  # secondes, pour ne pas bloquer l'UI si le serveur/Internet ne répond pas


class UpdaterError(Exception):
    """Erreur lisible à afficher directement à l'utilisateur."""
    pass


# ─────────────────────────────────────────────
# Comparaison de versions ("5.10" > "5.9", etc.)
# ─────────────────────────────────────────────
def _parse_version(v):
    v = (v or "").strip().lstrip("vV")
    parts = []
    for p in v.split("."):
        p = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(p) if p else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def version_plus_recente(candidate, actuelle):
    try:
        return _parse_version(candidate) > _parse_version(actuelle)
    except Exception:
        return False


# ─────────────────────────────────────────────
# Vérification — GitHub
# ─────────────────────────────────────────────
def _verifier_github():
    req = urllib.request.Request(
        GITHUB_API_LATEST,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "CantineApp-Updater"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_RESEAU) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise UpdaterError(
            "Impossible de contacter GitHub pour vérifier les mises à jour.\n"
            "Vérifiez la connexion Internet.\n\nDétail : " + str(e)
        )
    except Exception as e:
        raise UpdaterError("Réponse GitHub invalide : " + str(e))

    tag = data.get("tag_name", "")
    assets = data.get("assets", [])
    asset_url = None
    for a in assets:
        if a.get("name", "").lower().endswith(".exe"):
            asset_url = a.get("browser_download_url")
            break
    if not asset_url:
        raise UpdaterError("La dernière release GitHub ne contient pas d'installeur (.exe).")

    return {
        "version": tag,
        "source": "github",
        "url": asset_url,
        "notes": data.get("body", "") or "",
    }


# ─────────────────────────────────────────────
# Vérification — Dossier réseau / local
# ─────────────────────────────────────────────
def _verifier_dossier(chemin, source_label):
    if not chemin:
        raise UpdaterError("Aucun dossier de mise à jour configuré.")
    if not os.path.isdir(chemin):
        raise UpdaterError(f"Dossier introuvable :\n{chemin}")

    version_path = os.path.join(chemin, "version.txt")
    installeur_path = os.path.join(chemin, NOM_INSTALLEUR)

    if not os.path.isfile(version_path):
        raise UpdaterError(f"Fichier version.txt introuvable dans :\n{chemin}")
    if not os.path.isfile(installeur_path):
        raise UpdaterError(f"Fichier {NOM_INSTALLEUR} introuvable dans :\n{chemin}")

    try:
        with open(version_path, "r", encoding="utf-8") as f:
            version = f.read().strip()
    except Exception as e:
        raise UpdaterError("Impossible de lire version.txt : " + str(e))

    notes = ""
    notes_path = os.path.join(chemin, "notes.txt")
    if os.path.isfile(notes_path):
        try:
            with open(notes_path, "r", encoding="utf-8") as f:
                notes = f.read().strip()
        except Exception:
            pass

    return {
        "version": version,
        "source": source_label,
        "url": installeur_path,
        "notes": notes,
    }


# ─────────────────────────────────────────────
# Vérification — Fichier .exe sélectionné directement (source locale)
# ─────────────────────────────────────────────
def _verifier_fichier_local(chemin_exe):
    if not chemin_exe:
        raise UpdaterError("Aucun fichier d'installation sélectionné.\n"
                           "Choisissez un fichier .exe dans Paramètres > Mises à jour.")
    if not os.path.isfile(chemin_exe):
        raise UpdaterError(f"Fichier introuvable :\n{chemin_exe}")
    if not chemin_exe.lower().endswith(".exe"):
        raise UpdaterError("Le fichier sélectionné n'est pas un .exe.")
    return {
        "version": "?",           # pas de comparaison de version : sélection manuelle assumée
        "source": "local_fichier",
        "url": chemin_exe,
        "notes": "",
    }


# ─────────────────────────────────────────────
# API principale — vérification
# ─────────────────────────────────────────────
def verifier_maj(source, chemin=None, version_actuelle=APP_VERSION):
    """
    Retourne None si aucune mise à jour disponible, sinon un dict :
    {version, source, url, notes}
    Lève UpdaterError en cas de problème (réseau, dossier absent, etc.)

    Pour source="local", chemin est le chemin complet d'un fichier .exe
    choisi directement par l'utilisateur : aucune comparaison de version
    n'est faite, l'installation est toujours proposée (sélection manuelle
    assumée volontaire).
    """
    if source == "github":
        info = _verifier_github()
    elif source == "reseau":
        info = _verifier_dossier(chemin, source)
    elif source == "local":
        return _verifier_fichier_local(chemin)
    else:
        raise UpdaterError(f"Source de mise à jour inconnue : {source}")

    if version_plus_recente(info["version"], version_actuelle):
        return info
    return None


# ─────────────────────────────────────────────
# Téléchargement / copie de l'installeur
# ─────────────────────────────────────────────
def obtenir_installeur(info, dest_dir=None):
    """
    Récupère l'installeur (téléchargement HTTP pour github, copie pour
    reseau/local) et retourne le chemin local du fichier .exe téléchargé.
    """
    dest_dir = dest_dir or tempfile.mkdtemp(prefix="cantine_maj_")
    dest_path = os.path.join(dest_dir, NOM_INSTALLEUR)

    if info["source"] == "github":
        req = urllib.request.Request(info["url"], headers={"User-Agent": "CantineApp-Updater"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp, open(dest_path, "wb") as out:
                shutil.copyfileobj(resp, out)
        except urllib.error.URLError as e:
            raise UpdaterError("Échec du téléchargement de la mise à jour.\n\nDétail : " + str(e))
    else:
        try:
            shutil.copy2(info["url"], dest_path)
        except Exception as e:
            raise UpdaterError("Échec de la copie de l'installeur.\n\nDétail : " + str(e))

    if not os.path.isfile(dest_path) or os.path.getsize(dest_path) < 1024:
        raise UpdaterError("Le fichier de mise à jour téléchargé semble invalide.")

    return dest_path


# ─────────────────────────────────────────────
# Application de la mise à jour
# ─────────────────────────────────────────────
def appliquer_maj(installeur_path):
    """
    Lance un script qui attend la fermeture de Cantine.exe, exécute
    l'installeur en silencieux (/S), puis relance l'application.
    Cette fonction ne ferme PAS le processus courant : à l'appelant de le
    faire juste après (ex: os._exit(0)) pour libérer le fichier .exe verrouillé.
    """
    exe_courant = sys.executable if getattr(sys, "frozen", False) else None
    if not exe_courant:
        raise UpdaterError(
            "La mise à jour automatique n'est disponible que pour la version "
            "installée (.exe), pas en mode développement."
        )

    bat_path = os.path.join(tempfile.mkdtemp(prefix="cantine_maj_run_"), "appliquer_maj.bat")
    bat_content = f"""@echo off
setlocal
set "INSTALLER={installeur_path}"
set "EXECIBLE={exe_courant}"

:wait
tasklist /FI "IMAGENAME eq {NOM_PROCESSUS}" 2>NUL | find /I "{NOM_PROCESSUS}" >NUL
if "%ERRORLEVEL%"=="0" (
    timeout /t 1 /nobreak >nul
    goto wait
)

"%INSTALLER%" /S
timeout /t 3 /nobreak >nul
start "" "%EXECIBLE%"
del "%INSTALLER%" >nul 2>&1
(goto) 2>nul & del "%~f0"
"""
    with open(bat_path, "w", encoding="cp1252", errors="ignore") as f:
        f.write(bat_content)

    flags = 0
    if hasattr(subprocess, "DETACHED_PROCESS"):
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(["cmd", "/c", bat_path], creationflags=flags, close_fds=True)
