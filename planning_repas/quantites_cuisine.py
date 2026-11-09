# -*- coding: utf-8 -*-
"""
quantites_cuisine.py — Convertit les ingrédients d'une recette en quantités
de cuisine réelles et lisibles (grammes, ml, pièces, cuillères).

Chaque produit du catalogue a :
  - une quantité par personne (ou fixe), dans l'unité de cuisine
  - une unité affichée

Le module ne modifie PAS le calcul de la liste de courses (qui reste en unités
du catalogue) : il sert uniquement à AFFICHER les recettes de façon lisible.
"""

# code -> (quantité par personne, unité, "fixe" ?)
# fixe=True : quantité pour tout le plat, pas multipliée par le nombre de personnes.
QTE = {
    # ── Viandes / protéines (par personne) ──
    "H23": (130, "g", False),          # steak haché
    "H16": (250, "g", False),          # poulet cru
    "H5":  (1,   "cuisse", False),     # cuisse de poulet
    "H10": (1,   "escalope", False),   # escalope de poulet
    "H12": (150, "g", False),          # faux filet
    "H6":  (180, "g", False),          # boeuf bourguignon
    "H13": (50,  "g", False),          # lardons volaille
    "H14": (2,   "merguez", False),    # merguez
    "H19": (1,   "saucisse", False),   # saucisse boeuf
    "H20": (1,   "saucisse", False),   # saucisse veau
    "H25": (1,   "tranche", False),    # gigot
    "H2":  (1,   "tranche", False),    # dinde
    "H34": (1,   "tranche", False),    # toastinette
    "F70": (60,  "g", False),          # surimi
    "F13": (1,   "œuf", False),        # œufs (par personne par défaut)

    # ── Féculents (par personne) ──
    "A126": (80,  "g", False),         # spaghetti
    "A125": (80,  "g", False),         # penne
    "A131": (70,  "g", False),         # riz
    "A132": (80,  "g", False),         # couscous
    "H60":  (60,  "g", False),         # semoule
    "F42":  (200, "g", False),         # pommes de terre
    "A31":  (2,   "tranches", False),  # pain de mie
    "H31":  (1,   "pâte", True),       # pâte brisée (1 pour le plat)
    "H32":  (1,   "pâte", True),       # pâte feuilletée

    # ── Légumes (souvent fixes pour le plat, ou par pers pour accompagnement) ──
    "F41":  (0.5, "oignon", True),     # oignon (fixe : ~1/2 par plat de base)
    "F48":  (1,   "gousse d'ail", True),
    "F39":  (100, "g", False),         # carottes
    "F43":  (150, "g", False),         # tomates
    "F30":  (150, "g", False),         # courgettes
    "F49":  (60,  "g", False),         # champignons
    "A89":  (150, "g", False),         # haricots verts
    "A99":  (150, "g", False),         # légumes couscous
    "F29":  (0.5, "concombre", False), # concombre
    "F28":  (0.5, "avocat", False),    # avocat
    "F47":  (60,  "g", False),         # betterave
    "F31":  (2,   "endives", False),   # endives
    "F50":  (0.25,"batavia", True),    # salade (1/4 par plat)

    # ── Fruits ──
    "F45":  (1,   "pomme", False),
    "F33":  (0.5, "banane", False),
    "F35":  (1,   "orange", False),
    "F34":  (1,   "kiwi", False),
    "F44":  (0.5, "citron", False),

    # ── Produits laitiers / œufs base gâteaux ──
    "F12":  (100, "ml", False),        # lait
    "F15":  (30,  "ml", False),        # crème (par pers en sauce)
    "F1":   (20,  "g", False),         # beurre
    "F8":   (20,  "g", False),         # emmental râpé
    "F11":  (1,   "yaourt", False),    # yaourt
    "F20":  (0.5, "boule", False),     # mozzarella
    "F16":  (40,  "g", False),         # bûche chèvre

    # ── Épicerie / assaisonnement (fixe pour le plat) ──
    "A117": (1,   "boîte de sauce tomate", True),
    "A116": (1,   "c. à soupe de concentré", True),
    "A102": (2,   "c. à soupe d'huile", True),
    "A110": (1,   "c. à café de moutarde", True),
    "A113": (1,   "cube de bouillon", True),
    "A78":  (100, "g de farine", False),
    "A79":  (200, "g de farine à gâteau", True),
    "A19":  (80,  "g de sucre", True),
    "A67":  (1,   "sachet de sucre vanillé", True),
    "A68":  (2,   "c. à soupe de cacao", True),
    "A69":  (80,  "g de poudre d'amande", True),
    "A34":  (100, "g de chocolat", True),

    # ── Épices (fixe, petite quantité) ──
    "H46":  (1,   "pincée d'herbes", True),
    "H40":  (1,   "c. à café de cumin", True),
    "H41":  (1,   "c. à café de curry", True),
    "H52":  (1,   "poignée de persil", True),
    "H53":  (1,   "pincée de piment doux", True),

    # ── Boissons (base pour recettes boisson, par personne) ──
    "B20":  (200, "ml de jus d'orange", False),
    "B18":  (150, "ml de cocktail multivitaminé", False),
    "B12":  (250, "ml de thé", False),
    "B22":  (30,  "ml de sirop", False),
}


def _formater(q, unite):
    """Formate une quantité + unité de façon lisible."""
    # Arrondis raisonnables
    if unite in ("g", "ml"):
        # arrondir au multiple de 10 pour la lisibilité
        q = int(round(q / 10.0) * 10) if q >= 20 else int(round(q))
        return f"{q} {unite}"
    # pièces / cuillères : gérer le pluriel et les demis
    entier = int(q)
    reste = q - entier
    if abs(reste - 0.5) < 0.15:
        txt = f"{entier},5" if entier else "½"
        nombre = entier + 0.5
    elif reste < 0.15:
        txt = str(entier) if entier else "un peu"
        nombre = entier
    else:
        txt = str(round(q, 1)).replace(".", ",")
        nombre = q
    # Pluriel simple sur les unités "pièce" (œuf, oignon, pomme, banane...)
    unite_aff = unite
    unites_pluralisables = ("œuf", "oignon", "pomme", "banane", "orange", "kiwi",
                            "citron", "avocat", "concombre", "endives", "cuisse",
                            "escalope", "merguez", "saucisse", "tranche", "tranches",
                            "gousse d'ail", "yaourt", "boule")
    if nombre >= 2 and unite in unites_pluralisables and not unite.endswith("s"):
        unite_aff = unite + "s"
    return f"{txt} {unite_aff}".strip()


def ingredient_lisible(code, qte_recette, fixe_recette, nb_personnes):
    """
    Retourne (texte_quantité, connu?).
    code : code produit ; qte_recette/fixe_recette : valeurs stockées dans la
    recette (non utilisées pour le calcul cuisine, on se base sur QTE) ;
    nb_personnes : nombre de convives.
    Si le code n'est pas dans QTE, retombe sur une estimation générique.
    """
    if code in QTE:
        q, unite, fixe = QTE[code]
        total = q if fixe else q * nb_personnes
        return _formater(total, unite), True
    # inconnu : on ne sait pas convertir -> quantité générique
    return "selon goût", False
