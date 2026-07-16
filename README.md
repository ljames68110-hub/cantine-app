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
- Mises a jour de l'application (Internet, dossier reseau ou dossier local/USB)

## Mises a jour

L'application (compte Yoann uniquement) peut verifier et installer les
mises a jour depuis 3 sources, configurables dans **Parametres > Mises a jour** :

| Source                     | Fonctionnement                                                        |
|-----------------------------|------------------------------------------------------------------------|
| Internet (GitHub)           | Verifie automatiquement la derniere release du depot GitHub            |
| Dossier reseau partage      | Lit `version.txt` + `CantineSetup.exe` dans un dossier reseau (ex: `\\SERVEUR\partage\cantine_maj`) |
| Dossier local / cle USB     | Meme principe, sur un dossier local ou une cle USB                     |

- Une verification silencieuse a lieu au demarrage (ne derange que si une
  mise a jour est reellement disponible).
- Le bouton **"🔄 Mises a jour"** dans l'en-tete permet une verification manuelle a tout moment.
- La mise a jour reutilise l'installeur `CantineSetup.exe` existant (mode silencieux `/S`) :
  l'application se ferme, s'installe, puis redemarre automatiquement.

### Publier une mise a jour (source Internet)

1. Mettre a jour la constante `APP_VERSION` dans `updater.py` (ex: `"5.1"`).
2. Committer, puis creer et pousser un tag correspondant : `git tag v5.1 && git push origin v5.1`.
3. Le workflow GitHub Actions (`.github/workflows/build.yml`) compile automatiquement
   `CantineSetup.exe` et publie une release — l'application le detectera ensuite toute seule.

### Publier une mise a jour (source reseau ou locale)

Deposer dans le dossier partage/USB configure :
- `version.txt` : la nouvelle version (ex: `5.1`)
- `CantineSetup.exe` : le nouvel installeur (recuperable depuis la release GitHub ou `compiler_et_installer.bat`)
- `notes.txt` *(optionnel)* : description des nouveautes affichee a l'utilisateur
