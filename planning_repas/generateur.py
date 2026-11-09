# -*- coding: utf-8 -*-
"""
Moteur : filtrage par regles alimentaires, composition du planning,
agregation de la liste de courses.
"""
import datetime as dt
import math
import random
import unicodedata

JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def _norm(txt):
    """Minuscules sans accents, pour comparer les mots-cles."""
    txt = unicodedata.normalize("NFD", txt or "")
    txt = "".join(c for c in txt if unicodedata.category(c) != "Mn")
    return txt.lower()


# --------------------------------------------------------------------------
# Regles
# --------------------------------------------------------------------------

def charger_regles(con):
    codes, motcles = set(), []
    for r in con.execute("SELECT type, valeur FROM pr_regle WHERE actif = 1"):
        if r["type"] == "code":
            codes.add(r["valeur"].strip().upper())
        else:
            motcles.append(_norm(r["valeur"]))
    return codes, motcles


def produit_interdit(code, designation, codes_interdits, motcles):
    if code.upper() in codes_interdits:
        return True
    d = _norm(designation)
    return any(m and m in d for m in motcles)


def recettes_autorisees(con, type_recette=None):
    """Retourne les recettes actives dont aucun ingredient n'est interdit."""
    codes_interdits, motcles = charger_regles(con)
    sql = "SELECT * FROM pr_recette WHERE actif = 1"
    params = []
    if type_recette:
        sql += " AND type = ?"
        params.append(type_recette)
    resultat = []
    for rec in con.execute(sql + " ORDER BY nom", params).fetchall():
        ings = con.execute(
            "SELECT i.code, i.qte, i.fixe, p.designation "
            "FROM pr_recette_ingredient i "
            "LEFT JOIN pr_produit p ON p.code = i.code "
            "WHERE i.recette_id = ?", (rec["id"],)).fetchall()
        if any(produit_interdit(i["code"], i["designation"] or "",
                                codes_interdits, motcles) for i in ings):
            continue
        if produit_interdit("", rec["nom"], set(), motcles):
            continue
        resultat.append({"id": rec["id"], "nom": rec["nom"], "type": rec["type"],
                         "instructions": rec["instructions"],
                         "ingredients": [dict(i) for i in ings]})
    return resultat


# --------------------------------------------------------------------------
# Composition du planning
# --------------------------------------------------------------------------

def _tirage_sans_repetition(source, n, graine=None):
    """Tire n elements en epuisant la source avant de recommencer."""
    rnd = random.Random(graine)
    sortie, reserve = [], []
    while len(sortie) < n:
        if not reserve:
            reserve = list(source)
            rnd.shuffle(reserve)
        sortie.append(reserve.pop())
    return sortie


def composer(con, date_debut, nb_jours=15, nb_personnes=2,
             desserts_semaine=1, gateaux_weekend=2, graine=None):
    """Compose le planning. Retourne une liste de dicts jour par jour."""
    plats = recettes_autorisees(con, "plat")
    gateaux = recettes_autorisees(con, "gateau")
    desserts = recettes_autorisees(con, "dessert")
    if not plats:
        raise ValueError("Aucun plat autorise : les regles excluent tout.")

    choix_plats = _tirage_sans_repetition(plats, nb_jours, graine)
    jours = []
    for i in range(nb_jours):
        d = date_debut + dt.timedelta(days=i)
        jours.append({"index": i, "date": d, "jour_nom": JOURS_FR[d.weekday()],
                      "weekend": d.weekday() >= 5, "nb_personnes": nb_personnes,
                      "plat": choix_plats[i], "dessert": None})

    # Gateaux du week-end : les `gateaux_weekend` premiers jours de chaque week-end
    if gateaux:
        idx_we = [j["index"] for j in jours if j["weekend"]]
        besoin = 0
        semaine_vue = {}
        for i in idx_we:
            cle = jours[i]["date"].isocalendar()[:2]
            semaine_vue.setdefault(cle, [])
            if len(semaine_vue[cle]) < gateaux_weekend:
                semaine_vue[cle].append(i)
                besoin += 1
        tirage = _tirage_sans_repetition(gateaux, besoin, graine)
        k = 0
        for liste in semaine_vue.values():
            for i in liste:
                jours[i]["dessert"] = tirage[k]
                k += 1

    # Desserts de semaine : `desserts_semaine` par semaine calendaire
    if desserts and desserts_semaine > 0:
        par_semaine = {}
        for j in jours:
            if not j["weekend"]:
                par_semaine.setdefault(j["date"].isocalendar()[:2], []).append(j["index"])
        cibles = []
        rnd = random.Random(graine)
        for indices in par_semaine.values():
            rnd.shuffle(indices)
            cibles.extend(indices[:desserts_semaine])
        tirage = _tirage_sans_repetition(desserts, len(cibles), graine)
        for k, i in enumerate(sorted(cibles)):
            jours[i]["dessert"] = tirage[k]

    return jours


# --------------------------------------------------------------------------
# Liste de courses
# --------------------------------------------------------------------------

def liste_de_courses(con, jours, nb_personnes, extras=None):
    """Agrege les ingredients de tous les jours + les extras manuels.

    extras : liste de (code, quantite, libelle_lot)
    Retourne (lignes, totaux) ; lignes triees par categorie puis code.
    """
    besoin = {}

    def ajoute(code, qte):
        besoin[code] = besoin.get(code, 0.0) + qte

    for j in jours:
        # Chaque jour peut avoir son propre nombre de convives ; a defaut on
        # retombe sur la valeur globale du planning.
        convives = j.get("nb_personnes") or nb_personnes
        for rec in (j["plat"], j["dessert"]):
            if not rec:
                continue
            for i in rec["ingredients"]:
                ajoute(i["code"], i["qte"] * (1 if i["fixe"] else convives))

    lignes = []
    for code, qte_reelle in besoin.items():
        p = con.execute("SELECT * FROM pr_produit WHERE code = ?", (code,)).fetchone()
        if p is None:
            continue
        qte = max(1, math.ceil(round(qte_reelle, 3)))
        lignes.append({
            "code": code, "designation": p["designation"], "categorie": p["categorie"],
            "quantite": qte, "prix_unitaire": p["prix"],
            "prix_total": round(qte * p["prix"], 2),
            "qte_max": p["qte_max"], "depassement": qte > p["qte_max"],
            "lot": "Repas",
        })

    for code, qte, lot in (extras or []):
        p = con.execute("SELECT * FROM pr_produit WHERE code = ?", (code,)).fetchone()
        if p is None:
            continue
        lignes.append({
            "code": code, "designation": p["designation"], "categorie": p["categorie"],
            "quantite": int(qte), "prix_unitaire": p["prix"],
            "prix_total": round(int(qte) * p["prix"], 2),
            "qte_max": p["qte_max"], "depassement": int(qte) > p["qte_max"],
            "lot": lot or "Extra",
        })

    lignes.sort(key=lambda l: (l["lot"], l["categorie"], l["code"]))
    totaux = {}
    for l in lignes:
        totaux[l["lot"]] = round(totaux.get(l["lot"], 0) + l["prix_total"], 2)
    totaux["TOTAL"] = round(sum(l["prix_total"] for l in lignes), 2)
    return lignes, totaux


def suggestions_economies(con, lignes, budget_cible):
    """Propose des remplacements moins chers dans la meme categorie de viande."""
    total = sum(l["prix_total"] for l in lignes)
    if not budget_cible or total <= budget_cible:
        return []
    codes_interdits, motcles = charger_regles(con)
    suggestions = []
    for l in sorted(lignes, key=lambda x: -x["prix_total"])[:10]:
        p = con.execute("SELECT * FROM pr_produit WHERE code = ?", (l["code"],)).fetchone()
        if not p or p["categorie"] not in ("Hallal", "Fruits & Légumes"):
            continue
        alt = con.execute(
            "SELECT * FROM pr_produit WHERE categorie = ? AND prix < ? AND actif = 1 "
            "ORDER BY prix DESC LIMIT 5", (p["categorie"], p["prix"])).fetchall()
        for a in alt:
            if produit_interdit(a["code"], a["designation"], codes_interdits, motcles):
                continue
            gain = round((p["prix"] - a["prix"]) * l["quantite"], 2)
            if gain >= 2:
                suggestions.append({
                    "remplacer": f'{l["code"]} {l["designation"]}',
                    "par": f'{a["code"]} {a["designation"]}',
                    "quantite": l["quantite"], "gain": gain})
                break
    suggestions.sort(key=lambda s: -s["gain"])
    return suggestions[:8]


# --------------------------------------------------------------------------
# Persistance
# --------------------------------------------------------------------------

def enregistrer(con, libelle, date_debut, jours, nb_personnes, budget_cible=0,
                extras=None, planning_id=None):
    if planning_id:
        con.execute("DELETE FROM pr_planning_jour WHERE planning_id = ?", (planning_id,))
        con.execute("DELETE FROM pr_extra WHERE planning_id = ?", (planning_id,))
        con.execute("UPDATE pr_planning SET libelle=?, date_debut=?, nb_jours=?, "
                    "nb_personnes=?, budget_cible=? WHERE id=?",
                    (libelle, date_debut.isoformat(), len(jours), nb_personnes,
                     budget_cible, planning_id))
    else:
        cur = con.execute(
            "INSERT INTO pr_planning (libelle, date_debut, nb_jours, nb_personnes, "
            "budget_cible) VALUES (?,?,?,?,?)",
            (libelle, date_debut.isoformat(), len(jours), nb_personnes, budget_cible))
        planning_id = cur.lastrowid
    for j in jours:
        con.execute(
            "INSERT INTO pr_planning_jour (planning_id, jour_index, date_jour, "
            "plat_id, dessert_id, nb_personnes) VALUES (?,?,?,?,?,?)",
            (planning_id, j["index"], j["date"].isoformat(),
             j["plat"]["id"] if j["plat"] else None,
             j["dessert"]["id"] if j["dessert"] else None,
             j.get("nb_personnes") or nb_personnes))
    for code, qte, lot in (extras or []):
        con.execute("INSERT INTO pr_extra (planning_id, code, qte, libelle_lot) "
                    "VALUES (?,?,?,?)", (planning_id, code, int(qte), lot))
    con.commit()
    return planning_id


def _recette(con, rid):
    if not rid:
        return None
    rec = con.execute("SELECT * FROM pr_recette WHERE id = ?", (rid,)).fetchone()
    if not rec:
        return None
    ings = con.execute(
        "SELECT i.code, i.qte, i.fixe, p.designation FROM pr_recette_ingredient i "
        "LEFT JOIN pr_produit p ON p.code = i.code WHERE i.recette_id = ?",
        (rid,)).fetchall()
    return {"id": rec["id"], "nom": rec["nom"], "type": rec["type"],
            "instructions": rec["instructions"], "ingredients": [dict(i) for i in ings]}


def charger(con, planning_id):
    p = con.execute("SELECT * FROM pr_planning WHERE id = ?", (planning_id,)).fetchone()
    if not p:
        return None, [], []
    jours = []
    for r in con.execute("SELECT * FROM pr_planning_jour WHERE planning_id = ? "
                         "ORDER BY jour_index", (planning_id,)):
        d = dt.date.fromisoformat(r["date_jour"])
        jours.append({"index": r["jour_index"], "date": d,
                      "jour_nom": JOURS_FR[d.weekday()], "weekend": d.weekday() >= 5,
                      "nb_personnes": r["nb_personnes"] or p["nb_personnes"],
                      "plat": _recette(con, r["plat_id"]),
                      "dessert": _recette(con, r["dessert_id"])})
    extras = [(r["code"], r["qte"], r["libelle_lot"])
              for r in con.execute("SELECT * FROM pr_extra WHERE planning_id = ?",
                                   (planning_id,))]
    return dict(p), jours, extras


# --------------------------------------------------------------------------
# Lecture rapide pour le widget de bureau
# --------------------------------------------------------------------------

def planning_courant(con, date_ref=None):
    """Identifiant du planning qui couvre la date donnee (aujourd'hui par defaut).

    Si plusieurs plannings se chevauchent, le plus recemment cree gagne.
    Retourne None si aucun planning ne couvre cette date.
    """
    date_ref = date_ref or dt.date.today()
    r = con.execute(
        "SELECT p.id FROM pr_planning p "
        "JOIN pr_planning_jour j ON j.planning_id = p.id "
        "WHERE j.date_jour = ? ORDER BY p.id DESC LIMIT 1",
        (date_ref.isoformat(),)).fetchone()
    return r["id"] if r else None


def repas_du_jour(con, date_ref=None):
    """Retourne le repas prevu pour une date, ou None.

    Dict : date, jour_nom, weekend, nb_personnes, plat, dessert, planning_id,
    libelle. `plat` et `dessert` sont des recettes completes, ingredients et
    instructions compris : le widget n'a rien d'autre a interroger.
    """
    date_ref = date_ref or dt.date.today()
    r = con.execute(
        "SELECT j.*, p.libelle, p.nb_personnes AS pers_planning "
        "FROM pr_planning_jour j JOIN pr_planning p ON p.id = j.planning_id "
        "WHERE j.date_jour = ? ORDER BY p.id DESC LIMIT 1",
        (date_ref.isoformat(),)).fetchone()
    if not r:
        return None
    return {"date": date_ref, "jour_nom": JOURS_FR[date_ref.weekday()],
            "weekend": date_ref.weekday() >= 5,
            "nb_personnes": r["nb_personnes"] or r["pers_planning"],
            "plat": _recette(con, r["plat_id"]),
            "dessert": _recette(con, r["dessert_id"]),
            "planning_id": r["planning_id"], "libelle": r["libelle"]}


def ingredients_calcules(con, recette, nb_personnes):
    """Ingredients d'une recette ramenes au nombre de convives reel.

    Retourne une liste de dicts : code, designation, qte (arrondie a l'unite
    superieure comme dans la liste de courses), qte_reelle, fixe.
    """
    if not recette:
        return []
    sortie = []
    for i in recette["ingredients"]:
        reelle = i["qte"] * (1 if i["fixe"] else nb_personnes)
        sortie.append({
            "code": i["code"],
            "designation": i["designation"] or i["code"],
            "qte_reelle": round(reelle, 2),
            "qte": max(1, math.ceil(round(reelle, 3))),
            "fixe": bool(i["fixe"]),
        })
    sortie.sort(key=lambda x: x["code"])
    return sortie
