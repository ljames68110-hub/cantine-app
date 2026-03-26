# 🏛️ Gestion Cantine — Logiciel Native

Application de bureau Python/Tkinter pour la gestion de cantine.

## 📋 Contenu
```
cantine_app/
├── main.py          ← Application principale
├── database.py      ← Base de données SQLite (toutes les données)
├── impression.py    ← Génération de bons PDF
├── requirements.txt ← Dépendances Python
├── installer.bat    ← Installation Windows (1 clic)
├── build_exe.bat    ← Compiler en .exe autonome
└── README.md        ← Ce fichier
```

## 🚀 Installation rapide (Windows)

### Option 1 — Script d'installation (recommandé)
1. Installez Python 3.10+ depuis https://www.python.org (**cocher "Add to PATH"**)
2. Double-cliquez sur **`installer.bat`**
3. Un raccourci "Cantine" sera créé sur le Bureau

### Option 2 — Lancement direct
```batch
pip install -r requirements.txt
python main.py
```

### Option 3 — Créer un .exe autonome (aucune dépendance)
```batch
build_exe.bat
```
→ Génère `dist/Cantine.exe` qu'on peut copier n'importe où.

## 🔐 Connexion par défaut
- **Identifiant :** `admin`
- **Mot de passe :** `1234`

*(Changeable dans l'application via le bouton 🔑 MDP)*

## 📦 Fonctionnalités

| Fonctionnalité | Description |
|---|---|
| **Menu Principal** | 8 catégories de commande |
| **Bon de commande** | Sélection produits, quantités, total automatique |
| **Impression PDF** | Bon formaté avec signature |
| **Catalogue** | 400+ produits, modification prix/max/statut |
| **Paramètres** | Nom, Prénom, Écrou, Bâtiment, Cellule |
| **Historique** | Tous les bons sauvegardés, réimpression |
| **Base de données** | SQLite local (`cantine.db`) |

## 📁 Fichiers générés
- **`cantine.db`** — Base de données (ne pas supprimer)
- **`bons_pdf/`** — PDFs des bons générés

## 🖨️ Format du bon PDF
- En-tête : Nom, Prénom, Écrou, Bâtiment, Cellule, Date
- Tableau produits avec code, désignation, quantité, prix, total
- Total général
- Zone de signature

## ⚙️ Configuration requise
- Windows 7/8/10/11
- Python 3.8+ (si lancement via .py)
- **Aucune dépendance** si utilisation du .exe compilé

## 🔧 Base de données
La base SQLite `cantine.db` est créée automatiquement au premier lancement 
dans le même dossier que l'application. Elle contient :
- Tous les produits du catalogue original
- Les paramètres du détenu
- L'historique de tous les bons créés
