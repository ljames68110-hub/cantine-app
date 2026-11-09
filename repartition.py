"""
repartition.py — Répartit des articles entre plusieurs personnes endettées,
de façon à ce que la valeur des articles attribués à chacun colle au plus près
du montant qu'elle doit.

Principe :
  - On étale les articles disponibles en « unités » (1 unité = 1 exemplaire, à
    son prix unitaire). Les quantités sont donc divisibles.
  - Pour chaque personne (traitée de la plus grosse dette à la plus petite), on
    cherche le sous-ensemble d'unités restantes dont la somme est la plus proche
    du montant dû (sous-sum / knapsack, calcul en centimes).
  - Les unités choisies sont retirées du pool, puis on passe à la personne
    suivante. Ce qui reste (mode « liste importée ») est le reliquat.

Aucune dépendance externe.
"""
import random


def _prix_cents(prix):
    return int(round(float(prix) * 100))


def etaler_unites(articles):
    """articles : liste de dicts {id, nom, categorie, prix, qte}.
    Retourne une liste d'unités : (prix_cents, {id,nom,categorie,prix})."""
    unites = []
    for a in articles:
        pc = _prix_cents(a["prix"])
        if pc <= 0:
            continue
        info = {"id": a["id"], "nom": a["nom"],
                "categorie": a.get("categorie", ""), "prix": float(a["prix"])}
        for _ in range(int(a.get("qte", 0) or 0)):
            unites.append((pc, info))
    return unites


def _sous_somme_plus_proche(unites, cible_cents, marge_cents):
    """Trouve le sous-ensemble d'unités dont la somme est la plus proche de
    cible_cents (peut dépasser jusqu'à marge_cents). Retourne (somme, indices).
    Programmation dynamique sur les centimes."""
    if not unites or cible_cents <= 0:
        return 0, []
    plafond = cible_cents + marge_cents
    atteignable = bytearray(plafond + 1)
    atteignable[0] = 1
    unite_de = [-1] * (plafond + 1)   # index de l'unité ayant permis d'atteindre s
    somme_prec = [-1] * (plafond + 1)

    for idx, (prix, _info) in enumerate(unites):
        if prix > plafond:
            continue
        for s in range(plafond, prix - 1, -1):
            if not atteignable[s] and atteignable[s - prix]:
                atteignable[s] = 1
                unite_de[s] = idx
                somme_prec[s] = s - prix

    # Meilleure somme atteignable, la plus proche de la cible
    meilleure = 0
    meilleur_ecart = cible_cents
    for s in range(plafond + 1):
        if atteignable[s]:
            ecart = abs(s - cible_cents)
            if ecart < meilleur_ecart or (ecart == meilleur_ecart and s > meilleure):
                meilleur_ecart = ecart
                meilleure = s

    # Reconstruction
    indices = []
    s = meilleure
    while s > 0 and unite_de[s] != -1:
        indices.append(unite_de[s])
        s = somme_prec[s]
    return meilleure, indices


def _regrouper_en_lignes(unites_choisies):
    """Regroupe une liste d'unités en lignes de bon {id,nom,categorie,prix,qte,total}."""
    par_produit = {}
    ordre = []
    for prix_cents, info in unites_choisies:
        pid = info["id"]
        if pid not in par_produit:
            par_produit[pid] = {"id": pid, "nom": info["nom"],
                                "categorie": info["categorie"],
                                "prix": info["prix"], "qte": 0, "total": 0.0}
            ordre.append(pid)
        par_produit[pid]["qte"] += 1
        par_produit[pid]["total"] += info["prix"]
    return [par_produit[pid] for pid in ordre]


def repartir(articles, dettes, marge_euros=3.0, melanger=True):
    """
    articles : pool disponible — liste de {id,nom,categorie,prix,qte}
    dettes   : liste de (nom, montant_du) — ex [("Michel",50),("Marc",20)]
    marge_euros : dépassement maximal autorisé au-dessus de la dette.

    Retourne :
      {
        "personnes": [
           {"nom", "cible", "atteint", "ecart", "lignes":[...]}, ...
        ],
        "reste": [lignes des articles non attribués],   # pool restant
        "reste_total": float,
      }
    Les personnes sont traitées de la plus grosse dette à la plus petite
    (meilleur ajustement global)."""
    unites = etaler_unites(articles)
    if melanger:
        random.shuffle(unites)   # variété dans les paniers
    marge_cents = int(round(marge_euros * 100))

    # Tri décroissant par montant dû
    dettes_triees = sorted(
        [(n, float(m)) for n, m in dettes if float(m) > 0],
        key=lambda t: t[1], reverse=True)

    personnes = []
    for nom, montant in dettes_triees:
        cible = _prix_cents(montant)
        somme, indices = _sous_somme_plus_proche(unites, cible, marge_cents)
        choisies = [unites[i] for i in indices]
        # Retirer les unités choisies du pool
        set_idx = set(indices)
        unites = [u for i, u in enumerate(unites) if i not in set_idx]
        lignes = _regrouper_en_lignes(choisies)
        personnes.append({
            "nom": nom,
            "cible": montant,
            "atteint": somme / 100.0,
            "ecart": (somme - cible) / 100.0,
            "lignes": lignes,
        })

    # Remettre les personnes dans l'ordre de saisie original
    ordre_saisie = {n: i for i, (n, _m) in enumerate(dettes)}
    personnes.sort(key=lambda p: ordre_saisie.get(p["nom"], 999))

    reste_lignes = _regrouper_en_lignes(unites)
    reste_total = sum(l["total"] for l in reste_lignes)
    return {"personnes": personnes, "reste": reste_lignes, "reste_total": reste_total}
