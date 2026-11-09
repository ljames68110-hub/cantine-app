# -*- coding: utf-8 -*-
"""
Base de données du module Planning Repas.

Toutes les tables sont préfixées par `pr_` pour cohabiter sans risque
avec les tables existantes de Gestion Cantine.
"""
import csv
import json
import os
import sqlite3
import sys


def _dossier_data():
    """Dossier des donnees livrees (catalogue.csv, recettes.json).

    Sous PyInstaller --onefile, les fichiers ajoutes par --add-data sont
    extraits dans un dossier temporaire expose par sys._MEIPASS : le chemin
    calcule depuis __file__ pointerait alors dans l'archive et echouerait.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base:
        candidat = os.path.join(base, "planning_repas", "data")
        if os.path.isdir(candidat):
            return candidat
        candidat = os.path.join(base, "data")
        if os.path.isdir(candidat):
            return candidat
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


DOSSIER_DATA = _dossier_data()

SCHEMA = """
CREATE TABLE IF NOT EXISTS pr_produit (
    code        TEXT PRIMARY KEY,
    designation TEXT NOT NULL,
    prix        REAL NOT NULL DEFAULT 0,
    qte_max     INTEGER NOT NULL DEFAULT 10,
    actif       INTEGER NOT NULL DEFAULT 1,
    categorie   TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS pr_recette (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    nom          TEXT NOT NULL UNIQUE,
    type         TEXT NOT NULL DEFAULT 'plat',   -- plat | dessert | gateau
    instructions TEXT NOT NULL DEFAULT '',
    actif        INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS pr_recette_ingredient (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    recette_id INTEGER NOT NULL,
    code       TEXT NOT NULL,
    qte        REAL NOT NULL DEFAULT 1,
    fixe       INTEGER NOT NULL DEFAULT 0,  -- 1 = quantite par repas, 0 = par personne
    FOREIGN KEY (recette_id) REFERENCES pr_recette(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pr_regle (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    type   TEXT NOT NULL,          -- code | motcle
    valeur TEXT NOT NULL,
    motif  TEXT NOT NULL DEFAULT '',
    actif  INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS pr_planning (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    libelle        TEXT NOT NULL,
    date_debut     TEXT NOT NULL,
    nb_jours       INTEGER NOT NULL DEFAULT 15,
    nb_personnes   INTEGER NOT NULL DEFAULT 2,
    budget_cible   REAL NOT NULL DEFAULT 0,
    cree_le        TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS pr_planning_jour (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    planning_id   INTEGER NOT NULL,
    jour_index    INTEGER NOT NULL,
    date_jour     TEXT NOT NULL,
    plat_id       INTEGER,
    dessert_id    INTEGER,
    nb_personnes  INTEGER,
    FOREIGN KEY (planning_id) REFERENCES pr_planning(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pr_extra (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    planning_id INTEGER NOT NULL,
    code        TEXT NOT NULL,
    qte         INTEGER NOT NULL DEFAULT 1,
    libelle_lot TEXT NOT NULL DEFAULT 'Extra',
    FOREIGN KEY (planning_id) REFERENCES pr_planning(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pr_ri ON pr_recette_ingredient(recette_id);
CREATE INDEX IF NOT EXISTS idx_pr_pj ON pr_planning_jour(planning_id);
"""


def _migrer(con):
    """Mises a jour de schema sur une base deja creee par une version anterieure."""
    colonnes = {r["name"] for r in con.execute("PRAGMA table_info(pr_planning_jour)")}
    if "nb_personnes" not in colonnes:
        con.execute("ALTER TABLE pr_planning_jour ADD COLUMN nb_personnes INTEGER")
        con.commit()


def connexion(chemin_db):
    """Ouvre la base et garantit que le schema du module existe."""
    con = sqlite3.connect(chemin_db)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA)
    con.commit()
    _migrer(con)
    return con


def catalogue_vide(con):
    return con.execute("SELECT COUNT(*) FROM pr_produit").fetchone()[0] == 0


def charger_catalogue(con, chemin_csv=None, remplacer=False):
    """Charge le catalogue livre avec le module. Les prix modifies a la main
    sont conserves sauf si remplacer=True."""
    chemin_csv = chemin_csv or os.path.join(DOSSIER_DATA, "catalogue.csv")
    with open(chemin_csv, encoding="utf-8-sig", newline="") as f:
        lignes = list(csv.DictReader(f, delimiter=";"))
    sql = ("INSERT INTO pr_produit (code, designation, prix, qte_max, actif, categorie) "
           "VALUES (?,?,?,?,?,?) ON CONFLICT(code) DO ")
    sql += ("UPDATE SET designation=excluded.designation, prix=excluded.prix, "
            "qte_max=excluded.qte_max, categorie=excluded.categorie"
            if remplacer else "NOTHING")
    for l in lignes:
        con.execute(sql, (l["code"].strip(), l["designation"].strip(),
                          float(l["prix"]), int(l["qte_max"]),
                          int(l["actif"]), l["categorie"].strip()))
    con.commit()
    return len(lignes)


RECETTES_VERSION = 2  # incrémenter pour forcer le rechargement des recettes livrées

def charger_recettes(con, chemin_json=None):
    """Charge (ou met à jour) les recettes livrées.
    - Table vide : chargement initial.
    - Nouvelle version livrée : remplace les recettes, mais conserve l'état
      actif/inactif et les recettes ajoutées par l'utilisateur (noms inconnus)."""
    # Version déjà en base ?
    version_actuelle = 0
    try:
        con.execute("CREATE TABLE IF NOT EXISTS pr_meta (cle TEXT PRIMARY KEY, valeur TEXT)")
        r2 = con.execute("SELECT valeur FROM pr_meta WHERE cle='recettes_version'").fetchone()
        if r2: version_actuelle = int(r2["valeur"])
    except Exception:
        version_actuelle = 0

    nb_existant = con.execute("SELECT COUNT(*) FROM pr_recette").fetchone()[0]
    if nb_existant > 0 and version_actuelle >= RECETTES_VERSION:
        return 0  # déjà à jour

    chemin_json = chemin_json or os.path.join(DOSSIER_DATA, "recettes.json")
    with open(chemin_json, encoding="utf-8") as f:
        recettes = json.load(f)

    # Mémoriser l'état actif des recettes existantes (pour le préserver)
    etats = {}
    for r in con.execute("SELECT nom, actif FROM pr_recette"):
        etats[r["nom"]] = r["actif"]
    noms_livres = {r["nom"] for r in recettes}

    # Supprimer les recettes livrées précédentes (celles présentes dans le JSON),
    # garder celles ajoutées à la main par l'utilisateur
    for r in con.execute("SELECT id, nom FROM pr_recette").fetchall():
        if r["nom"] in noms_livres:
            con.execute("DELETE FROM pr_recette_ingredient WHERE recette_id=?", (r["id"],))
            con.execute("DELETE FROM pr_recette WHERE id=?", (r["id"],))

    for r in recettes:
        actif = etats.get(r["nom"], 1)
        cur = con.execute(
            "INSERT INTO pr_recette (nom, type, instructions, actif) VALUES (?,?,?,?)",
            (r["nom"], r["type"], r.get("instructions", ""), actif))
        rid = cur.lastrowid
        for ing in r["ingredients"]:
            con.execute(
                "INSERT INTO pr_recette_ingredient (recette_id, code, qte, fixe) "
                "VALUES (?,?,?,?)",
                (rid, ing["code"], float(ing["qte"]), int(ing.get("fixe", 0))))

    con.execute("CREATE TABLE IF NOT EXISTS pr_meta (cle TEXT PRIMARY KEY, valeur TEXT)")
    con.execute("INSERT OR REPLACE INTO pr_meta VALUES ('recettes_version', ?)",
                (str(RECETTES_VERSION),))
    con.commit()
    return len(recettes)


def _table_a_colonne(con, table, colonne):
    try:
        cols = {r["name"] for r in con.execute(f"PRAGMA table_info({table})")}
        return colonne in cols
    except Exception:
        return False


REGLES_DEPART = [
    ("motcle", "porc", "Jamais de porc"),
    ("motcle", "jambon", "Jamais de porc"),
    ("motcle", "chorizo", "Jamais de porc"),
    ("motcle", "rosette", "Jamais de porc"),
    ("motcle", "francfort", "Jamais de porc"),
    ("motcle", "lorrain", "Jamais de porc"),
    ("motcle", "choucroute", "Jamais de porc"),
    ("motcle", "cassoulet", "Jamais de porc"),
    ("motcle", "thon", "Ne mange pas de thon cuit"),
    ("motcle", "cordon bleu", "N'aime pas"),
    ("motcle", "kebab", "N'aime pas"),
    ("motcle", "flan", "N'aime pas"),
    ("motcle", "tarte citron", "N'aime pas"),
    ("code", "A129", "Puree toujours maison, jamais en flocons"),
    ("code", "A130", "Riz thai uniquement"),
    ("code", "F56", "Lardons de porc"),
    ("code", "A85", "Pate de porc"),
    ("code", "A86", "Pate de porc"),
    ("code", "A87", "Rillettes de porc"),
]
# Desserts du commerce : tout le rayon patisserie sauf viennoiserie et pain
DESSERTS_COMMERCE = ["P11", "P12", "P13", "P14", "P15", "P16", "P17", "P18",
                     "P22", "P23", "P25", "P26"]


def charger_regles(con):
    if con.execute("SELECT COUNT(*) FROM pr_regle").fetchone()[0] > 0:
        return 0
    lignes = list(REGLES_DEPART) + [
        ("code", c, "Desserts uniquement faits maison") for c in DESSERTS_COMMERCE]
    con.executemany(
        "INSERT INTO pr_regle (type, valeur, motif) VALUES (?,?,?)", lignes)
    con.commit()
    return len(lignes)


def initialiser(chemin_db):
    """Point d'entree unique : ouvre la base et la peuple au premier lancement."""
    con = connexion(chemin_db)
    charger_catalogue(con)
    charger_recettes(con)
    charger_regles(con)
    return con
