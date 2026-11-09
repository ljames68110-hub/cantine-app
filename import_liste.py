"""
import_liste.py — Lecture d'un fichier de liste de cantine (Excel, CSV ou TXT)
et association aux produits du catalogue.

Format attendu (colonnes, dans cet ordre ou avec en-têtes) :
    Personne | Produit | Quantité
  - Personne : nom du destinataire (vide = bon pour soi / une seule personne)
  - Produit  : code (ex: A5) OU nom (ex: Nescafé boite 200g)
  - Quantité : entier

Séparateurs CSV/TXT acceptés : tabulation, point-virgule ou virgule.
La 1re ligne peut être un en-tête (Personne/Produit/Quantité) — détecté et ignoré.
"""
import os
import csv
import unicodedata


def _norm(txt):
    """Normalise pour comparaison : minuscules, sans accents, espaces réduits."""
    if txt is None:
        return ""
    txt = str(txt).strip().lower()
    txt = unicodedata.normalize("NFD", txt)
    txt = "".join(ch for ch in txt if unicodedata.category(ch) != "Mn")
    return " ".join(txt.split())


def _lire_lignes_brutes(chemin):
    """Retourne une liste de lignes, chaque ligne = liste de cellules (str)."""
    ext = os.path.splitext(chemin)[1].lower()

    if ext in (".xlsx", ".xlsm", ".xls"):
        import openpyxl
        wb = openpyxl.load_workbook(chemin, read_only=True, data_only=True)
        ws = wb.active
        lignes = []
        for row in ws.iter_rows(values_only=True):
            cellules = ["" if v is None else str(v) for v in row]
            if any(c.strip() for c in cellules):
                lignes.append(cellules)
        wb.close()
        return lignes

    # CSV / TXT : lecture tolérante à l'encodage (Excel FR = souvent cp1252)
    contenu = None
    donnees = open(chemin, "rb").read()
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            contenu = donnees.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if contenu is None:
        contenu = donnees.decode("utf-8", errors="replace")

    if not contenu.strip():
        return []
    # Choisir le séparateur le plus présent sur la 1re ligne non vide
    premiere = next((l for l in contenu.splitlines() if l.strip()), "")
    sep = "\t"
    if premiere.count(";") >= premiere.count(sep) and premiere.count(";") > 0:
        sep = ";"
    elif premiere.count(",") > premiere.count(sep) and premiere.count(",") > 0:
        sep = ","
    lignes = []
    for row in csv.reader(contenu.splitlines(), delimiter=sep):
        if any((c or "").strip() for c in row):
            lignes.append([c or "" for c in row])
    return lignes


def _est_entete(cellules):
    """Détecte si la ligne est un en-tête (contient Personne/Produit/Quantité)."""
    joined = _norm(" ".join(cellules))
    mots = ("personne", "produit", "quantite", "qte", "nom", "code", "article")
    return sum(1 for m in mots if m in joined) >= 2


def analyser_fichier(chemin, produits):
    """
    Lit le fichier et associe chaque ligne à un produit du catalogue.

    produits : liste de tuples (id, nom, categorie, prix, qte_max, actif, ...)

    Retourne un dict :
      {
        "personnes": [
           {"nom": str,
            "lignes": [ {"id","nom","categorie","prix","qte","qte_max","total"} ],
           }, ...
        ],
        "erreurs": [ "Ligne 3 : produit « X » introuvable", ... ],
        "avertissements": [ "Ligne 5 : quantité 20 > max 10 pour ...", ... ],
      }
    Lève ValueError si le fichier est illisible ou vide.
    """
    lignes = _lire_lignes_brutes(chemin)
    if not lignes:
        raise ValueError("Le fichier est vide ou illisible.")

    # Index de recherche : par code et par nom normalisé
    par_code = {}
    par_nom = {}
    for p in produits:
        pid, nom, cat, prix, qmax = p[0], p[1], p[2], p[3], p[4]
        par_code[_norm(pid)] = p
        par_nom[_norm(nom)] = p

    if _est_entete(lignes[0]):
        lignes = lignes[1:]

    personnes = []
    index_pers = {}
    erreurs = []
    avert = []

    def get_personne(nom):
        cle = nom or "(sans nom)"
        if cle not in index_pers:
            index_pers[cle] = len(personnes)
            personnes.append({"nom": nom, "lignes": []})
        return personnes[index_pers[cle]]

    # Détermine le nombre de colonnes utiles à partir des lignes de données
    # (hors en-tête déjà retiré) : si aucune ligne n'a de 3e cellule remplie,
    # on est en format 2 colonnes « Produit | Quantité » (pas de personne).
    max_cols = 0
    for cel in lignes:
        remplies = len([c for c in cel if str(c).strip()])
        max_cols = max(max_cols, remplies)
    deux_colonnes = max_cols <= 2

    for i, cellules in enumerate(lignes, start=1):
        cel = list(cellules) + ["", "", ""]
        if deux_colonnes:
            personne = ""
            produit_ref = cel[0].strip()
            qte_txt = cel[1].strip()
        else:
            personne = cel[0].strip()
            produit_ref = cel[1].strip()
            qte_txt = cel[2].strip()

        if produit_ref == "":
            continue

        # Quantité
        try:
            qte = int(float(qte_txt.replace(",", "."))) if qte_txt else 1
        except ValueError:
            qte = 1
        if qte <= 0:
            qte = 1

        # Recherche produit (code d'abord, puis nom)
        p = par_code.get(_norm(produit_ref)) or par_nom.get(_norm(produit_ref))
        if p is None:
            erreurs.append(f"Ligne {i} : produit « {produit_ref} » introuvable "
                           f"(ni code ni nom).")
            continue

        pid, nom, cat, prix, qmax = p[0], p[1], p[2], p[3], p[4]
        if qmax and qte > qmax:
            avert.append(f"« {nom} » : quantité {qte} dépasse le maximum "
                         f"autorisé ({qmax}).")

        get_personne(personne)["lignes"].append({
            "id": pid, "nom": nom, "categorie": cat, "prix": prix,
            "qte": qte, "qte_max": qmax, "total": prix * qte,
        })

    return {"personnes": personnes, "erreurs": erreurs, "avertissements": avert}
