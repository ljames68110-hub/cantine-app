"""
ration.py — Calcul d'une liste de provisions équilibrée « sans recette ».

À partir d'un nombre de personnes et d'un nombre de jours, produit la liste
des articles à acheter (avec codes du catalogue), selon une ration type
équilibrée par personne et par jour : protéines, féculents, légumes, laitages,
pain, fruits. Aucune recette : c'est un simple calcul de quantités.

Les quantités sont exprimées en « part d'unité du catalogue par personne et par
jour ». Exemple : 0.25 pour un paquet de pâtes = 1 paquet pour 4 personnes-jour.

Règles respectées : aucun porc (viandes Halal / volaille), produits du
catalogue uniquement.
"""
import math


# Ration type : (code_produit, part par personne et par jour, groupe)
# Ajustable ici. Les codes correspondent au catalogue de la cantine.
RATION_TYPE = [
    # Protéines (rotation viande / œufs / poisson) — Halal / sans porc
    ("HA23", 0.35, "Protéines"),  # Steack haché halal ~120g
    ("HA10", 0.20, "Protéines"),  # Escalope de poulet halal ~160g
    ("PL22", 0.20, "Protéines"),  # Œufs frais x6
    ("AL83", 0.15, "Protéines"),  # Miette de thon à la tomate 80g

    # Féculents
    ("AL124", 0.18, "Féculents"), # Coquillettes 500g
    ("AL125", 0.10, "Féculents"), # Penne 500g
    ("FL11",  0.10, "Féculents"), # Pommes de terre 2,5Kg
    ("HA60",  0.08, "Féculents"), # Semoule de blé fine 500g

    # Légumes
    ("FL4",  0.12, "Légumes"),    # Carotte 1Kg
    ("FL14", 0.08, "Légumes"),    # Oignon 1Kg
    ("FL8",  0.10, "Légumes"),    # Tomates 1Kg
    ("AL96", 0.15, "Légumes"),    # Petit pois carottes 400g

    # Laitages
    ("PL5",  0.20, "Laitages"),   # Lait 1/2 écrémé 1L
    ("PL16", 0.10, "Laitages"),   # Emmental râpé 100g
    ("PL1",  0.06, "Laitages"),   # Beurre doux 250g

    # Pain / petit-déjeuner
    ("AL31", 0.14, "Pain"),       # Pain de mie 500g
    ("AL27", 0.08, "Pain"),       # Pain grillé 300g

    # Fruits
    ("FL21", 0.12, "Fruits"),     # Orange 1Kg
    ("FL17", 0.10, "Fruits"),     # Banane 1Kg
]


def calculer_ration(produits_catalogue, nb_personnes, nb_jours,
                     respecter_plafond=True):
    """
    produits_catalogue : liste de tuples produits
        (id, nom, categorie, prix, qte_max, actif, ...)
    nb_personnes, nb_jours : entiers.

    Retourne un dict :
      {
        "lignes": [ {code, nom, categorie, groupe, prix, qte, total, depasse} ],
        "groupes": { "Protéines": total_€, ... },
        "total": total_€,
        "avertissements": [ ... ],
      }
    Les quantités sont arrondies à l'unité supérieure. Si respecter_plafond,
    toute quantité dépassant qte_max est plafonnée et signalée.
    """
    par_code = {p[0]: p for p in produits_catalogue}
    facteur = max(0, int(nb_personnes)) * max(0, int(nb_jours))

    lignes = []
    groupes = {}
    avert = []

    for code, part, groupe in RATION_TYPE:
        p = par_code.get(code)
        if p is None:
            continue  # produit absent/inactif du catalogue : on ignore
        nom, cat, prix, qmax = p[1], p[2], p[3], p[4]
        actif = p[5] if len(p) > 5 else "Oui"
        if actif != "Oui":
            continue

        brut = part * facteur
        qte = int(math.ceil(brut)) if brut > 0 else 0
        if qte <= 0:
            continue

        depasse = False
        if respecter_plafond and qmax and qte > qmax:
            avert.append(f"« {nom} » : besoin de {qte} mais plafond catalogue "
                         f"{qmax} — plafonné.")
            qte = qmax
            depasse = True

        total = prix * qte
        lignes.append({"code": code, "nom": nom, "categorie": cat,
                       "groupe": groupe, "prix": prix, "qte": qte,
                       "total": total, "depasse": depasse})
        groupes[groupe] = groupes.get(groupe, 0.0) + total

    total_general = sum(l["total"] for l in lignes)
    # Trier par groupe puis par nom
    ordre_groupes = ["Protéines", "Féculents", "Légumes", "Laitages", "Pain", "Fruits"]
    lignes.sort(key=lambda l: (ordre_groupes.index(l["groupe"])
                               if l["groupe"] in ordre_groupes else 99, l["nom"]))
    return {"lignes": lignes, "groupes": groupes,
            "total": total_general, "avertissements": avert}
