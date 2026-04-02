# Gestion de Cantine Penitentiaire

Application de gestion des bons de cantine.

## Installation rapide

### Prerequis
- Python 3.10+ depuis **https://www.python.org/downloads/**
- **IMPORTANT** : cocher "Add Python to PATH" pendant l installation

### Etapes
1. Telecharger et extraire le ZIP
2. Ouvrir CMD dans le dossier extrait
3. Lancer :
```
compiler_et_installer.bat
```
4. Attendre 1-2 minutes (compilation)
5. Un raccourci "Cantine" apparait sur le Bureau

### Connexion
- **Yoann** : mot de passe `1234`
- **Invite** : saisie manuelle des informations

## Desinstallation
Menu Demarrer -> "Desinstaller Cantine"

## Structure
```
cantine_app/
  main.py                    # Application principale
  database.py                # Base de donnees SQLite
  impression.py              # Generation PDF bons de cantine
  cantine.ico                # Icone application
  compiler_et_installer.bat  # Script installation Windows
```

## Fonctionnalites
- Connexion Yoann (avec signature sur les bons) ou Invite
- 8 categories : Alimentaire, Boissons, Hallal, Hygiene,
                  Accidentelle, Tabac, Patisserie, Fruits & Legumes
- Generation PDF identique aux bons originaux de la cantine
- Historique des commandes
- Gestion catalogue produits
- Signature numerique sur les bons
