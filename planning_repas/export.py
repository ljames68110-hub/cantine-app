# -*- coding: utf-8 -*-
"""Exports : CSV pour l'appli cantine, PDF pour l'impression."""
import csv
import datetime as dt
import os

MOIS_FR = ["", "janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet",
           "aout", "septembre", "octobre", "novembre", "decembre"]


def _fr(x):
    return f"{x:.2f}".replace(".", ",")


def csv_bon_de_cantine(lignes, chemin):
    """CSV minimal a importer dans Gestion Cantine : code, designation, quantite."""
    with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Code", "Designation", "Quantite"])
        for l in lignes:
            w.writerow([l["code"], l["designation"], l["quantite"]])
    return chemin


def csv_detaille(lignes, totaux, chemin):
    """CSV complet avec prix, plafonds et alertes."""
    with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Lot", "Categorie", "Code", "Designation", "Quantite",
                    "Prix unitaire", "Prix total", "Qte max", "Alerte"])
        for l in lignes:
            w.writerow([l["lot"], l["categorie"], l["code"], l["designation"],
                        l["quantite"], _fr(l["prix_unitaire"]), _fr(l["prix_total"]),
                        l["qte_max"], "DEPASSE LE PLAFOND" if l["depassement"] else ""])
        w.writerow([])
        for cle, val in totaux.items():
            w.writerow([cle, "", "", "", "", "", _fr(val), "", ""])
    return chemin


def texte_planning(jours, nb_personnes, lignes, totaux, budget_cible=0):
    """Rendu texte, utilise pour l'apercu a l'ecran et comme repli si pas de PDF."""
    out = []
    out.append(f"PLANNING DES REPAS DU SOIR - {len(jours)} jours - "
               f"{nb_personnes} personne(s)")
    out.append("=" * 70)
    out.append("")
    for j in jours:
        d = j["date"]
        entete = f'{j["jour_nom"].capitalize()} {d.day} {MOIS_FR[d.month]}'
        out.append(entete)
        out.append("-" * len(entete))
        out.append(f'  Plat    : {j["plat"]["nom"] if j["plat"] else "-"}')
        if j["dessert"]:
            etiquette = "Gateau " if j["dessert"]["type"] == "gateau" else "Dessert"
            out.append(f'  {etiquette} : {j["dessert"]["nom"]}')
        out.append("")
    out.append("")
    out.append("LISTE DE COURSES")
    out.append("=" * 70)
    lot_courant = None
    for l in lignes:
        if l["lot"] != lot_courant:
            lot_courant = l["lot"]
            out.append("")
            out.append(f"-- {lot_courant} --")
        alerte = "  << PLAFOND DEPASSE" if l["depassement"] else ""
        out.append(f'{l["code"]:<7} {l["designation"][:44]:<44} '
                   f'{l["quantite"]:>3}  {_fr(l["prix_total"]):>8} EUR{alerte}')
    out.append("")
    out.append("=" * 70)
    for cle, val in totaux.items():
        out.append(f'{cle:<20} {_fr(val):>10} EUR')
    if budget_cible:
        ecart = totaux.get("TOTAL", 0) - budget_cible
        mot = "depassement" if ecart > 0 else "marge"
        out.append(f'Budget cible {_fr(budget_cible)} EUR - {mot} '
                   f'{_fr(abs(ecart))} EUR')
    return "\n".join(out)


def texte_recettes(jours):
    out = ["RECETTES", "=" * 70, ""]
    vues = set()
    for j in jours:
        for rec in (j["plat"], j["dessert"]):
            if not rec or rec["id"] in vues:
                continue
            vues.add(rec["id"])
            out.append(rec["nom"].upper())
            out.append("-" * len(rec["nom"]))
            out.append(rec["instructions"] or "(pas d'instructions saisies)")
            out.append("")
    return "\n".join(out)


def pdf(jours, nb_personnes, lignes, totaux, chemin, budget_cible=0,
        avec_recettes=True):
    """PDF via reportlab. Si reportlab est absent, ecrit un .txt et retourne
    son chemin : l'appelant verifie l'extension du retour."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except ImportError:
        repli = os.path.splitext(chemin)[0] + ".txt"
        contenu = texte_planning(jours, nb_personnes, lignes, totaux, budget_cible)
        if avec_recettes:
            contenu += "\n\n" + texte_recettes(jours)
        with open(repli, "w", encoding="utf-8") as f:
            f.write(contenu)
        return repli

    c = canvas.Canvas(chemin, pagesize=A4)
    largeur, hauteur = A4
    marge, y = 18 * mm, hauteur - 20 * mm

    def saut(besoin=12):
        nonlocal y
        if y < besoin * mm:
            c.showPage()
            y = hauteur - 20 * mm

    def ligne(txt, taille=9, gras=False, saut_apres=4.6):
        nonlocal y
        saut()
        c.setFont("Helvetica-Bold" if gras else "Helvetica", taille)
        c.drawString(marge, y, txt[:110])
        y -= saut_apres * mm

    ligne(f"Planning des repas du soir - {len(jours)} jours - "
          f"{nb_personnes} personne(s)", 14, True, 8)
    ligne(f"Edite le {dt.date.today().strftime('%d/%m/%Y')}", 8, False, 7)

    for j in jours:
        d = j["date"]
        ligne(f'{j["jour_nom"].capitalize()} {d.day} {MOIS_FR[d.month]}', 10, True, 5)
        ligne(f'    Plat : {j["plat"]["nom"] if j["plat"] else "-"}', 9)
        if j["dessert"]:
            etq = "Gateau" if j["dessert"]["type"] == "gateau" else "Dessert"
            ligne(f'    {etq} : {j["dessert"]["nom"]}', 9)

    c.showPage()
    y = hauteur - 20 * mm
    ligne("Liste de courses", 14, True, 8)
    lot = None
    for l in lignes:
        if l["lot"] != lot:
            lot = l["lot"]
            ligne(lot, 11, True, 5.5)
        suffixe = "   ! plafond depasse" if l["depassement"] else ""
        ligne(f'{l["code"]:<7} {l["designation"][:52]:<52} x{l["quantite"]:<3} '
              f'{_fr(l["prix_total"]):>8} EUR{suffixe}', 8.5, False, 4.2)
    y -= 3 * mm
    for cle, val in totaux.items():
        ligne(f'{cle} : {_fr(val)} EUR', 10, True, 5)
    if budget_cible:
        ecart = totaux.get("TOTAL", 0) - budget_cible
        mot = "Depassement" if ecart > 0 else "Marge"
        ligne(f'Budget cible {_fr(budget_cible)} EUR - {mot} {_fr(abs(ecart))} EUR',
              9, False, 5)

    if avec_recettes:
        c.showPage()
        y = hauteur - 20 * mm
        ligne("Recettes", 14, True, 8)
        vues = set()
        for j in jours:
            for rec in (j["plat"], j["dessert"]):
                if not rec or rec["id"] in vues:
                    continue
                vues.add(rec["id"])
                saut(30)
                ligne(rec["nom"], 11, True, 5)
                for l in (rec["instructions"] or "").splitlines():
                    if l.strip():
                        ligne("   " + l.strip(), 8.5, False, 4.2)
                y -= 2 * mm

    c.save()
    return chemin
