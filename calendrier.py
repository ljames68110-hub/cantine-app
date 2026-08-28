"""
calendrier.py — Génération d'un fichier iCalendar (.ics) pour les créances.

Le fichier .ics produit est un standard universel : il s'importe (ou se
"souscrit" via une URL) dans One Calendar, Google Agenda, Outlook, etc.

Pour chaque créance, deux événements « journée entière » sont créés :
  - 🛒 Livraison des articles (à la date de distribution estimée)
  - 💰 Récupération de l'argent (à la même date, par défaut)

Aucune dépendance externe : le format .ics est du texte simple.
"""
from datetime import datetime


def _echapper(texte):
    """Échappe les caractères spéciaux iCalendar."""
    if texte is None:
        return ""
    return (str(texte)
            .replace("\\", "\\\\")
            .replace(";", "\\;")
            .replace(",", "\\,")
            .replace("\n", "\\n"))


def _date_ics(date_str):
    """Convertit 'jj/mm/aaaa' en 'AAAAMMJJ' (format date iCalendar).
    Retourne None si la date est invalide/absente."""
    try:
        d = datetime.strptime(date_str.strip(), "%d/%m/%Y")
        return d.strftime("%Y%m%d")
    except (ValueError, AttributeError):
        return None


def _plier_ligne(ligne):
    """iCalendar impose des lignes <= 75 octets ; plie les longues lignes."""
    encoded = ligne.encode("utf-8")
    if len(encoded) <= 75:
        return ligne
    morceaux = []
    courant = ""
    for ch in ligne:
        if len((courant + ch).encode("utf-8")) > 73:
            morceaux.append(courant)
            courant = " " + ch  # espace de continuation
        else:
            courant += ch
    if courant:
        morceaux.append(courant)
    return "\r\n".join(morceaux)


def generer_ics_creances(creances, chemin_fichier, inclure_recuperation=True,
                          inclure_livraison=True):
    """
    Génère un fichier .ics à partir d'une liste de créances (dicts renvoyés
    par database.get_creances_calendrier).

    Retourne le nombre d'événements écrits.
    """
    now_stamp = datetime.now().strftime("%Y%m%dT%H%M%SZ")
    lignes = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Gestion Cantine//Creances//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Créances Cantine",
    ]

    nb_events = 0
    for cr in creances:
        date_ics = _date_ics(cr.get("date_creance", ""))
        if not date_ics:
            continue  # sans date exploitable, on ne crée pas d'événement
        nom     = cr.get("nom", "") or "?"
        montant = float(cr.get("montant", 0) or 0)
        cat     = cr.get("categorie", "")
        uid_base = cr.get("uid", "") or f"{nom}-{date_ics}"

        desc = (f"Créance de {nom}\\n"
                f"Montant : {montant:.2f} EUR\\n"
                f"Catégorie : {cat}\\n"
                f"Bon posé le {cr.get('date_bon','')}")

        if inclure_livraison:
            lignes += [
                "BEGIN:VEVENT",
                f"UID:{_echapper(uid_base)}-livraison@cantine",
                f"DTSTAMP:{now_stamp}",
                f"DTSTART;VALUE=DATE:{date_ics}",
                _plier_ligne(f"SUMMARY:🛒 Livraison {_echapper(nom)} ({_echapper(cat)})"),
                _plier_ligne(f"DESCRIPTION:{desc}"),
                "TRANSP:TRANSPARENT",
                "END:VEVENT",
            ]
            nb_events += 1

        if inclure_recuperation:
            lignes += [
                "BEGIN:VEVENT",
                f"UID:{_echapper(uid_base)}-recup@cantine",
                f"DTSTAMP:{now_stamp}",
                f"DTSTART;VALUE=DATE:{date_ics}",
                _plier_ligne(f"SUMMARY:💰 Récupérer {montant:.2f}€ - {_echapper(nom)}"),
                _plier_ligne(f"DESCRIPTION:{desc}"),
                "TRANSP:TRANSPARENT",
                "END:VEVENT",
            ]
            nb_events += 1

    lignes.append("END:VCALENDAR")

    with open(chemin_fichier, "w", encoding="utf-8", newline="") as f:
        f.write("\r\n".join(lignes) + "\r\n")

    return nb_events


def ecrire_feed_auto(chemin_dossier):
    """Écrit/met à jour le fichier 'creances_cantine.ics' dans le dossier
    indiqué (typiquement un dossier OneDrive synchronisé), à partir des
    créances actives. Retourne le chemin du fichier écrit, ou None si le
    dossier n'est pas configuré ou introuvable.

    Sert de "flux" auquel One Calendar peut s'abonner : à chaque appel, le
    fichier est régénéré, et OneDrive le synchronise automatiquement."""
    import os
    import database as db
    if not chemin_dossier:
        return None
    if not os.path.isdir(chemin_dossier):
        return None
    creances = db.get_creances_calendrier(uniquement_actives=True)
    chemin_fichier = os.path.join(chemin_dossier, "creances_cantine.ics")
    try:
        generer_ics_creances(creances, chemin_fichier)
        return chemin_fichier
    except Exception:
        return None
