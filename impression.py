"""
Bons de cantine - fond coloré par catégorie, IDs sans préfixe lettre.
AC14→14, B3→3, HY20→20, F12→12, etc.
"""
import os, re
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas as pdfcanvas

W, H = A4

# Couleurs de fond (mode couleur) reprises du nouveau catalogue, avec repli.
try:
    import catalogue_data as _cd
    BG = {nom: bg for (nom, _p, _j, _band, bg, _e) in _cd.CATEGORIES_META}
except Exception:
    BG = {
        "BOISSONS":          (0.95, 0.78, 0.85),
        "PRODUITS LAITIERS": (0.96, 0.84, 0.82),
        "FRUITS & LEGUMES":  (0.97, 0.93, 0.55),
        "CASHER":            (0.93, 0.62, 0.58),
        "ALIMENTAIRE":       (0.97, 0.73, 0.52),
        "PRODUITS FRAIS":    (0.63, 0.84, 0.95),
        "HALAL":             (0.88, 0.80, 0.90),
        "ENTRETIEN HYGIENE": (0.80, 0.92, 0.80),
        "PATISSERIES":       (0.96, 0.84, 0.52),
        "TABAC":             (0.96, 0.94, 0.86),
        "REVUES":            (0.68, 0.86, 0.42),
    }
DEFAULT_BG = (0.82, 0.82, 0.82)

TOTAL_ROWS = 35
BOLD = "Helvetica-Bold"
NORM = "Helvetica"

# Catégories dont le bon pré-imprimé N'A PAS de ligne « Date: / Signature: »
# sous le tableau (tableau rallongé). Pour celles-ci, en mode papier, l'appli
# imprime elle-même les libellés + la date dans la zone vierge du bas.
CATS_SANS_PIED = {"ENTRETIEN HYGIENE"}


def _num_id(prod_id):
    """Enlève le(s) préfixe(s) lettre(s) : 'AC14'→'14', 'B3'→'3', 'HY20'→'20'."""
    return re.sub(r'^[A-Za-z]+', '', str(prod_id))


def _cat_slug(categorie):
    """Slug ASCII d'une catégorie pour la clé de décalage vertical."""
    s = (categorie or "").lower()
    for a, b in [("é", "e"), ("è", "e"), ("ê", "e"), ("&", ""),
                 ("à", "a"), ("â", "a"), ("î", "i"), ("ï", "i")]:
        s = s.replace(a, b)
    s = re.sub(r"[^a-z]+", "_", s).strip("_")
    # "fruits_legumes" attendu pour "Fruits & Légumes"
    return s


def _dy_categorie(params, categorie):
    """Décalage vertical (mm) propre à la catégorie. Positif = descend."""
    try:
        return float(params.get(f"impr_dy_{_cat_slug(categorie)}", "0") or 0)
    except Exception:
        return 0.0


def _colonnes_categorie(categorie):
    """(N° centre, Qté centre, Désignation début, bord droit) en mm, propres à
    la catégorie. Repli sur les colonnes standard si catalogue_data absent."""
    try:
        import catalogue_data as _cd
        return _cd.colonnes_categorie(categorie)
    except Exception:
        return (24.0, 41.4, 55.3, 183.2)


def generer_bon_pdf(categorie, nom, prenom, ecrou, batiment, cellule,
                    lignes, total, date_str, output_path, signature_path=None):

    c = pdfcanvas.Canvas(output_path, pagesize=A4)
    # Empêche les lecteurs PDF de mettre le bon à l'échelle à l'impression
    # (« Ajuster à la page ») : indispensable pour que le calage sur le papier
    # pré-imprimé reste exact. Le lecteur imprimera à 100 % (taille réelle).
    try:
        c.setViewerPreference("PrintScaling", "None")
    except Exception:
        pass

    # ── Mode d'impression + calage (lus en DB) ───────────────────────────────
    mode_noir = False
    off_x = off_y = 0.0
    try:
        import database as _dbm
        _p = _dbm.get_parametres()
        mode_noir = _p.get("impression_mode", "couleur") == "noir"
        off_x = float(_p.get("impression_offset_x", "0") or 0) * cm / 10.0  # mm -> pts
        off_y = float(_p.get("impression_offset_y", "0") or 0) * cm / 10.0
    except Exception:
        pass

    # Calage de base du mode noir (papier pré-imprimé de l'administration) :
    # décalage constaté sur le terrain. Le calage manuel (off_x / off_y) de
    # Paramètres > Impression s'ajoute par-dessus pour affiner.
    if mode_noir:
        off_x += 5.0 * cm / 10.0        # +5 mm à droite (identité OK à cette valeur)
        off_y += -4.5 * cm / 10.0       # ~4,5 mm vers le bas (calé sur le papier)

    # Couleur personnalisée stockée en DB ?
    try:
        import database as _db
        params = _db.get_parametres()
        custom = params.get(f"couleur_{categorie}", "")
        if custom and custom.startswith("#") and len(custom) in (4,7):
            h = custom.lstrip("#")
            if len(h) == 3:
                h = h[0]*2 + h[1]*2 + h[2]*2
            r = int(h[0:2],16)/255
            g = int(h[2:4],16)/255
            b2 = int(h[4:6],16)/255
            bg = (r, g, b2)
        else:
            bg = BG.get(categorie, DEFAULT_BG)
    except Exception:
        bg = BG.get(categorie, DEFAULT_BG)

    # En mode noir, le papier pré-imprimé fournit déjà les fonds/cadres/libellés :
    # on n'imprime que les valeurs (économie d'encre couleur).
    if not mode_noir:
        # Fond coloré pleine page
        c.setFillColorRGB(*bg)
        c.rect(0, 0, W, H, fill=1, stroke=0)
        c.setFillColorRGB(0, 0, 0)

    ML = 1.75 * cm + off_x
    PW = W - 2 * (1.75 * cm)

    X_NOM      = ML
    X_ECROU    = ML + PW * 0.55
    X_PRENOM   = ML
    X_BATIMENT = ML + PW * 0.36
    X_CELLULE  = ML + PW * 0.62

    LBL = 16
    VAL = 13

    y = H - 1.55 * cm + off_y

    # Décalages fixes alignés
    OFF_NOM      = c.stringWidth("NOM",      BOLD, LBL) + 10
    OFF_ECROU    = c.stringWidth("ECROU",    BOLD, LBL) + 10
    OFF_PRENOM   = c.stringWidth("PRENOM",   BOLD, LBL) + 10
    OFF_BATIMENT = c.stringWidth("BATIMENT", BOLD, LBL) + 10
    OFF_CELLULE  = c.stringWidth("CELLULE",  BOLD, LBL) + 10

    # ── LIGNE 1 : NOM [val]   ECROU [val] ────────────────────────────────────
    if not mode_noir:
        c.setFont(BOLD, LBL)
        c.drawString(X_NOM,   y, "NOM")
        c.drawString(X_ECROU, y, "ECROU")
        c.setFillColorRGB(0, 0, 0)
        c.setFont(NORM, VAL)
        c.drawString(X_NOM   + OFF_NOM,   y, (nom   or "").upper())
        c.drawString(X_ECROU + OFF_ECROU, y, str(ecrou or ""))

    y -= 1.10 * cm

    # ── LIGNE 2 : PRENOM [val]  BATIMENT [val]  CELLULE [val] ────────────────
    if not mode_noir:
        c.setFont(BOLD, LBL)
        c.drawString(X_PRENOM,   y, "PRENOM")
        c.drawString(X_BATIMENT, y, "BATIMENT")
        c.drawString(X_CELLULE,  y, "CELLULE")
        c.setFont(NORM, VAL)
        c.drawString(X_PRENOM   + OFF_PRENOM,   y, str(prenom   or ""))
        c.drawString(X_BATIMENT + OFF_BATIMENT, y, str(batiment or ""))
        c.drawString(X_CELLULE  + OFF_CELLULE,  y, str(cellule  or ""))

    y -= 1.05 * cm

    # ── ENCADRÉ CATÉGORIE ────────────────────────────────────────────────────
    BOX_H = 1.30 * cm
    if not mode_noir:
        c.setFillColorRGB(*bg)
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(1.5)
        c.rect(ML, y - BOX_H, PW, BOX_H, fill=1, stroke=1)
        c.setFillColorRGB(0, 0, 0)
        c.setFont(BOLD, 22)
        c.drawCentredString(W / 2, y - BOX_H + 0.30 * cm, categorie.upper())
    y -= BOX_H + 0.45 * cm

    # ── TABLEAU ──────────────────────────────────────────────────────────────
    COL_NO  = 1.30 * cm
    COL_QTE = 1.80 * cm
    COL_DES = PW - COL_NO - COL_QTE

    if mode_noir:
        # ── IDENTITÉ (mode papier pré-imprimé) ───────────────────────────────
        # Sur une créance (nom/prenom/etc. déjà vidés en amont), rien n'est
        # dessiné. Sinon, valeurs placées juste après les libellés du papier.
        Y_L1 = H - (21.0 * cm / 10.0) + off_y   # ligne NOM / ECROU
        Y_L2 = H - (35.0 * cm / 10.0) + off_y   # ligne PRENOM / BAT / CELL
        c.setFillColorRGB(0, 0, 0)
        c.setFont(NORM, 12)
        if nom:      c.drawString(37.0 * cm / 10.0 + off_x,  Y_L1, str(nom).upper())
        if ecrou:    c.drawString(145.0 * cm / 10.0 + off_x, Y_L1, str(ecrou))
        if prenom:   c.drawString(48.0 * cm / 10.0 + off_x,  Y_L2, str(prenom))
        if batiment: c.drawString(111.0 * cm / 10.0 + off_x, Y_L2, str(batiment))
        if cellule:  c.drawString(148.0 * cm / 10.0 + off_x, Y_L2, str(cellule))

        # ── TABLEAU (mode papier pré-imprimé) ────────────────────────────────
        # Géométrie mesurée sur les 8 bons vierges (scans nets, à plat) :
        #   pas ≈ 5,15 mm | centre N° ≈ 24 mm | centre Qté ≈ 41,4 mm
        #   début Désignation ≈ 55,3 mm | 1re ligne de données ≈ 76 mm du haut
        try:
            import database as _dbg
            _pg = _dbg.get_parametres()
            y1_mm  = float(_pg.get("impr_y1", "79") or 79)
            pas_mm = float(_pg.get("impr_pas", "5.15") or 5.15)
        except Exception:
            _pg = {}
            y1_mm, pas_mm = 79.0, 5.15
        # Décalage vertical propre à la catégorie (ex : Hygiène descend de 4 mm)
        y1_mm += _dy_categorie(_pg, categorie)

        # Colonnes propres à la catégorie (certains bons pré-imprimés ont des
        # colonnes décalées ou de largeur différente : CASHER, ALIMENTAIRE, TABAC)
        no_c, qte_c, des_d, bord_d = _colonnes_categorie(categorie)
        # Décalage horizontal propre AUX ARTICLES uniquement (N°/Qté/Désignation),
        # sans toucher à l'identité : -2 mm demandé (articles trop à droite).
        DX_ART = -2.0 * cm / 10.0
        X_NO_CENTRE  = no_c  * cm / 10.0 + off_x + DX_ART
        X_QTE_CENTRE = qte_c * cm / 10.0 + off_x + DX_ART
        X_DES_DEBUT  = des_d * cm / 10.0 + off_x + DX_ART
        ROW_H = pas_mm * cm / 10.0
        y_ligne1 = H - (y1_mm * cm / 10.0) + off_y
        LARG_DES = (bord_d - des_d) * cm / 10.0

        c.setFillColorRGB(0, 0, 0)
        for i, ligne in enumerate(lignes):
            ty = y_ligne1 - i * ROW_H
            c.setFont(NORM, 10)
            c.drawCentredString(X_NO_CENTRE, ty,
                                _num_id(ligne.get("id", str(i + 1))))
            c.drawCentredString(X_QTE_CENTRE, ty,
                                str(ligne.get("qte", "")))
            txt = _trunc(c, str(ligne.get("nom", "")), LARG_DES - 0.3 * cm, NORM, 10)
            c.drawString(X_DES_DEBUT, ty, txt)

        _dessiner_date_signature(c, ML, PW, date_str, signature_path,
                                 mode_noir=True, categorie=categorie)
        c.save()
        return output_path

    ROW_H   = (y - 1.80 * cm) / (TOTAL_ROWS + 1)

    # En-tête
    if not mode_noir:
        c.setLineWidth(1.0)
        _cell(c, ML,                    y, COL_NO,  ROW_H, bg)
        _cell(c, ML + COL_NO,           y, COL_QTE, ROW_H, bg)
        _cell(c, ML + COL_NO + COL_QTE, y, COL_DES, ROW_H, bg)
        mid_y = y - ROW_H * 0.5 - 0.13 * cm
        c.setFillColorRGB(0, 0, 0)
        c.setFont(BOLD, 9)
        c.drawCentredString(ML + COL_NO / 2,                      mid_y, "N°")
        c.drawCentredString(ML + COL_NO + COL_QTE / 2,            mid_y, "Qté")
        c.setFont(NORM, 8)
        c.drawCentredString(ML + COL_NO + COL_QTE + COL_DES / 2, mid_y, "DESIGNATION")

    y -= ROW_H
    c.setLineWidth(0.5)

    # Lignes
    for i in range(TOTAL_ROWS):
        if not mode_noir:
            _cell(c, ML,                    y, COL_NO,  ROW_H, bg)
            _cell(c, ML + COL_NO,           y, COL_QTE, ROW_H, bg)
            _cell(c, ML + COL_NO + COL_QTE, y, COL_DES, ROW_H, bg)

        if i < len(lignes):
            ligne  = lignes[i]
            text_y = y - ROW_H * 0.5 - 0.14 * cm
            c.setFillColorRGB(0, 0, 0)
            c.setFont(NORM, 10)
            # ID sans lettres
            c.drawCentredString(ML + COL_NO / 2,
                                text_y, _num_id(ligne.get("id", str(i + 1))))
            c.drawCentredString(ML + COL_NO + COL_QTE / 2,
                                text_y, str(ligne.get("qte", "")))
            txt = _trunc(c, str(ligne.get("nom", "")),
                         COL_DES - 0.4 * cm, NORM, 10)
            c.drawString(ML + COL_NO + COL_QTE + 0.18 * cm, text_y, txt)

        y -= ROW_H

    # ── DATE / SIGNATURE ─────────────────────────────────────────────────────
    _dessiner_date_signature(c, ML, PW, date_str, signature_path,
                             mode_noir=False, categorie=categorie)

    c.save()
    return output_path


def _dessiner_date_signature(c, ML, PW, date_str, signature_path,
                             mode_noir=False, categorie=None):
    """Dessine la date et la signature en bas du bon. En mode noir, les
    libellés « Date: » / « Signature: » sont déjà pré-imprimés sur le papier :
    on ne place que la valeur de la date, à sa position mesurée (~24 mm du bas,
    juste après le libellé « Date: »)."""
    SIG_X  = ML + PW * 0.42

    try:
        import database as _db2
        _sz   = float(_db2.get_parametres().get("signature_taille", "8.0"))
        SIG_W = max(3.0, min(15.0, _sz)) * cm
    except Exception:
        SIG_W = 8.0 * cm
    SIG_H = SIG_W * 0.28

    if mode_noir:
        # Créance/signature déjà gérées en amont : signature_path est None sur
        # une créance, donc rien n'est dessiné ici pour la signature.
        sans_pied = categorie in CATS_SANS_PIED
        if sans_pied:
            # Le papier n'a pas de ligne Date/Signature : on l'imprime nous-mêmes
            # dans la zone vierge, SOUS le tableau (qui descend plus bas ici).
            DATE_Y = H - (286.0 * cm / 10.0)   # ~286 mm du haut = ~11 mm du bas
            c.setFillColorRGB(0, 0, 0)
            c.setFont(NORM, 11)
            c.drawString(ML, DATE_Y, "Date:")
            c.drawString(SIG_X, DATE_Y, "Signature:")
        else:
            DATE_Y = H - (273.0 * cm / 10.0)   # ~273 mm du haut = ~24 mm du bas
        if signature_path and os.path.isfile(signature_path):
            try:
                c.drawImage(signature_path, SIG_X + 2.8 * cm, DATE_Y - 0.3 * cm,
                            width=SIG_W, height=SIG_H,
                            preserveAspectRatio=True, mask="auto")
            except Exception:
                pass
        c.setFillColorRGB(0, 0, 0)
        c.setFont(NORM, 11)
        # Valeur de la date : après le libellé « Date: » (pré-imprimé, ou que
        # l'on vient d'imprimer pour les catégories sans pied de page).
        c.drawString(41.0 * cm / 10.0, DATE_Y, str(date_str))
        return

    DATE_Y = 0.85 * cm
    if signature_path and os.path.isfile(signature_path):
        try:
            c.drawImage(signature_path, SIG_X + 2.8 * cm, DATE_Y - 0.3 * cm,
                        width=SIG_W, height=SIG_H,
                        preserveAspectRatio=True, mask="auto")
        except Exception:
            pass
    c.setFillColorRGB(0, 0, 0)
    c.setFont(NORM, 10)
    c.drawString(ML,    DATE_Y, f"Date:   {date_str}")
    c.drawString(SIG_X, DATE_Y, "Signature:")


def _cell(c, x, y, w, h, bg):
    c.setFillColorRGB(*bg)
    c.setStrokeColorRGB(0, 0, 0)
    c.rect(x, y - h, w, h, fill=1, stroke=1)

def _trunc(c, text, max_pts, font, size):
    c.setFont(font, size)
    while text and c.stringWidth(text, font, size) > max_pts:
        text = text[:-1]
    return text


# ═════════════════════════════════════════════════════════════════════════
#  RÉCAPITULATIF DE CRÉANCE — tableau noir sur blanc, tous bons regroupés
# ═════════════════════════════════════════════════════════════════════════
def generer_recap_creance_pdf(nom_personne, bons, output_path):
    """
    Génère un PDF récapitulatif noir sur blanc pour une personne débitrice.

    nom_personne : nom affiché en tête du récapitulatif.
    bons : liste de dicts, un par bon-créance :
        {
          "categorie": str,
          "date": str,
          "soldee": bool,
          "lignes": [ {"id","nom","qte","prix","total"}, ... ]
        }
    output_path : chemin du PDF à créer.
    """
    c = pdfcanvas.Canvas(output_path, pagesize=A4)
    ML = 1.5 * cm          # marge gauche
    MR = 1.5 * cm          # marge droite
    PW = W - ML - MR       # largeur utile

    # Colonnes : Code | Catégorie | Désignation | Qté | P.U. | Total
    COL_CODE = 1.6 * cm
    COL_CAT  = 2.8 * cm
    COL_QTE  = 1.2 * cm
    COL_PU   = 2.0 * cm
    COL_TOT  = 2.2 * cm
    COL_DES  = PW - COL_CODE - COL_CAT - COL_QTE - COL_PU - COL_TOT
    ROW_H    = 0.62 * cm
    HEADER_H = 0.7 * cm

    x_code = ML
    x_cat  = x_code + COL_CODE
    x_des  = x_cat + COL_CAT
    x_qte  = x_des + COL_DES
    x_pu   = x_qte + COL_QTE
    x_tot  = x_pu + COL_PU

    def entete_page(premier=False):
        """Dessine le titre (1re page) et l'en-tête de tableau. Retourne y courant."""
        y = H - 1.5 * cm
        if premier:
            c.setFillColorRGB(0, 0, 0)
            c.setFont(BOLD, 16)
            c.drawString(ML, y, "RÉCAPITULATIF DE CRÉANCE")
            y -= 0.75 * cm
            c.setFont(BOLD, 12)
            c.drawString(ML, y, f"Débiteur : {nom_personne}")
            c.setFont(NORM, 9)
            from datetime import datetime as _dt
            c.drawRightString(W - MR, y, f"Édité le {_dt.now().strftime('%d/%m/%Y')}")
            y -= 0.85 * cm
        # En-tête de tableau
        c.setLineWidth(1.0)
        c.setStrokeColorRGB(0, 0, 0)
        c.setFillColorRGB(0, 0, 0)
        for x, w in [(x_code,COL_CODE),(x_cat,COL_CAT),(x_des,COL_DES),
                     (x_qte,COL_QTE),(x_pu,COL_PU),(x_tot,COL_TOT)]:
            c.rect(x, y - HEADER_H, w, HEADER_H, fill=0, stroke=1)
        ty = y - HEADER_H + 0.22 * cm
        c.setFont(BOLD, 8)
        c.drawCentredString(x_code + COL_CODE/2, ty, "Code")
        c.drawCentredString(x_cat  + COL_CAT/2,  ty, "Catégorie")
        c.drawString       (x_des  + 0.15*cm,    ty, "Désignation")
        c.drawCentredString(x_qte  + COL_QTE/2,  ty, "Qté")
        c.drawCentredString(x_pu   + COL_PU/2,   ty, "P.U.")
        c.drawCentredString(x_tot  + COL_TOT/2,  ty, "Total")
        return y - HEADER_H

    def ligne_cells(y):
        for x, w in [(x_code,COL_CODE),(x_cat,COL_CAT),(x_des,COL_DES),
                     (x_qte,COL_QTE),(x_pu,COL_PU),(x_tot,COL_TOT)]:
            c.rect(x, y - ROW_H, w, ROW_H, fill=0, stroke=1)

    y = entete_page(premier=True)
    c.setLineWidth(0.5)
    total_general = 0.0

    for bon in bons:
        cat  = bon.get("categorie", "")
        date = bon.get("date", "")
        for l in bon.get("lignes", []):
            # Saut de page si nécessaire
            if y - ROW_H < 2.2 * cm:
                c.showPage()
                y = entete_page(premier=False)
                c.setLineWidth(0.5)

            ligne_cells(y)
            ty = y - ROW_H + 0.20 * cm
            qte  = l.get("qte", 0) or 0
            prix = float(l.get("prix", 0) or 0)
            tot_l = float(l.get("total", prix * qte) or 0)
            total_general += tot_l

            c.setFillColorRGB(0, 0, 0)
            c.setFont(NORM, 8)
            c.drawCentredString(x_code + COL_CODE/2, ty, _num_id(l.get("id","")))
            c.drawCentredString(x_cat  + COL_CAT/2,  ty, _trunc(c, cat, COL_CAT-0.2*cm, NORM, 7))
            c.drawString       (x_des  + 0.15*cm,    ty, _trunc(c, str(l.get("nom","")), COL_DES-0.3*cm, NORM, 8))
            c.drawCentredString(x_qte  + COL_QTE/2,  ty, str(qte))
            c.drawRightString  (x_pu   + COL_PU-0.15*cm, ty, f"{prix:.2f} €")
            c.drawRightString  (x_tot  + COL_TOT-0.15*cm, ty, f"{tot_l:.2f} €")
            y -= ROW_H

    # ── Ligne TOTAL GÉNÉRAL ──────────────────────────────────────────────
    if y - ROW_H < 2.2 * cm:
        c.showPage()
        y = entete_page(premier=False)
    c.setLineWidth(1.2)
    label_x = x_code
    label_w = COL_CODE + COL_CAT + COL_DES + COL_QTE + COL_PU
    c.rect(label_x, y - ROW_H, label_w, ROW_H, fill=0, stroke=1)
    c.rect(x_tot, y - ROW_H, COL_TOT, ROW_H, fill=0, stroke=1)
    ty = y - ROW_H + 0.20 * cm
    c.setFillColorRGB(0, 0, 0)
    c.setFont(BOLD, 10)
    c.drawRightString(x_pu + COL_PU - 0.15*cm, ty, "TOTAL GÉNÉRAL :")
    c.drawRightString(x_tot + COL_TOT - 0.15*cm, ty, f"{total_general:.2f} €")

    c.showPage()
    c.save()
    return output_path


def generer_recap_multi_pdf(groupes, output_path):
    """
    Récapitulatif de créances groupé par personne, noir sur blanc.

    groupes : liste ordonnée de dicts, un par personne :
        {
          "nom": str,
          "bons": [ {"categorie","date","lignes":[{id,nom,qte,prix,total}]}, ... ]
        }
    Chaque personne a son sous-total ; un total général clôt le document.
    """
    c = pdfcanvas.Canvas(output_path, pagesize=A4)
    ML = 1.5 * cm
    MR = 1.5 * cm
    PW = W - ML - MR

    COL_CODE = 1.6 * cm
    COL_CAT  = 2.8 * cm
    COL_QTE  = 1.2 * cm
    COL_PU   = 2.0 * cm
    COL_TOT  = 2.2 * cm
    COL_DES  = PW - COL_CODE - COL_CAT - COL_QTE - COL_PU - COL_TOT
    ROW_H    = 0.62 * cm
    HEADER_H = 0.7 * cm

    x_code = ML
    x_cat  = x_code + COL_CODE
    x_des  = x_cat + COL_CAT
    x_qte  = x_des + COL_DES
    x_pu   = x_qte + COL_QTE
    x_tot  = x_pu + COL_PU

    def titre_page(y):
        c.setFillColorRGB(0, 0, 0)
        c.setFont(BOLD, 16)
        c.drawString(ML, y, "RÉCAPITULATIF DE CRÉANCES")
        c.setFont(NORM, 9)
        from datetime import datetime as _dt
        c.drawRightString(W - MR, y, f"Édité le {_dt.now().strftime('%d/%m/%Y')}")
        return y - 0.85 * cm

    def entete_tableau(y):
        c.setLineWidth(1.0)
        c.setStrokeColorRGB(0, 0, 0)
        c.setFillColorRGB(0, 0, 0)
        for x, w in [(x_code,COL_CODE),(x_cat,COL_CAT),(x_des,COL_DES),
                     (x_qte,COL_QTE),(x_pu,COL_PU),(x_tot,COL_TOT)]:
            c.rect(x, y - HEADER_H, w, HEADER_H, fill=0, stroke=1)
        ty = y - HEADER_H + 0.22 * cm
        c.setFont(BOLD, 8)
        c.drawCentredString(x_code + COL_CODE/2, ty, "Code")
        c.drawCentredString(x_cat  + COL_CAT/2,  ty, "Catégorie")
        c.drawString       (x_des  + 0.15*cm,    ty, "Désignation")
        c.drawCentredString(x_qte  + COL_QTE/2,  ty, "Qté")
        c.drawCentredString(x_pu   + COL_PU/2,   ty, "P.U.")
        c.drawCentredString(x_tot  + COL_TOT/2,  ty, "Total")
        return y - HEADER_H

    def ligne_cells(y):
        for x, w in [(x_code,COL_CODE),(x_cat,COL_CAT),(x_des,COL_DES),
                     (x_qte,COL_QTE),(x_pu,COL_PU),(x_tot,COL_TOT)]:
            c.rect(x, y - ROW_H, w, ROW_H, fill=0, stroke=1)

    def saut_si_besoin(y, besoin=2.2*cm):
        if y - ROW_H < besoin:
            c.showPage()
            yy = titre_page(H - 1.5 * cm)
            return entete_tableau(yy), True
        return y, False

    y = titre_page(H - 1.5 * cm)
    y = entete_tableau(y)
    c.setLineWidth(0.5)
    total_general = 0.0

    for grp in groupes:
        nom = grp.get("nom", "") or "?"
        bons = grp.get("bons", [])

        # Bandeau nom de la personne
        y, _ = saut_si_besoin(y)
        c.setFont(BOLD, 10)
        c.setFillColorRGB(0, 0, 0)
        # ligne fine au-dessus du nom
        c.drawString(x_code, y - ROW_H + 0.20*cm, f"▸ {nom}")
        y -= ROW_H

        sous_total = 0.0
        for bon in bons:
            cat = bon.get("categorie", "")
            for l in bon.get("lignes", []):
                y, _ = saut_si_besoin(y)
                ligne_cells(y)
                ty = y - ROW_H + 0.20 * cm
                qte  = l.get("qte", 0) or 0
                prix = float(l.get("prix", 0) or 0)
                tot_l = float(l.get("total", prix * qte) or 0)
                sous_total += tot_l
                total_general += tot_l
                c.setFillColorRGB(0, 0, 0)
                c.setFont(NORM, 8)
                c.drawCentredString(x_code + COL_CODE/2, ty, _num_id(l.get("id","")))
                c.drawCentredString(x_cat  + COL_CAT/2,  ty, _trunc(c, cat, COL_CAT-0.2*cm, NORM, 7))
                c.drawString       (x_des  + 0.15*cm,    ty, _trunc(c, str(l.get("nom","")), COL_DES-0.3*cm, NORM, 8))
                c.drawCentredString(x_qte  + COL_QTE/2,  ty, str(qte))
                c.drawRightString  (x_pu   + COL_PU-0.15*cm, ty, f"{prix:.2f} €")
                c.drawRightString  (x_tot  + COL_TOT-0.15*cm, ty, f"{tot_l:.2f} €")
                y -= ROW_H

        # Sous-total de la personne
        y, _ = saut_si_besoin(y)
        c.setLineWidth(0.8)
        c.rect(x_code, y - ROW_H, COL_CODE+COL_CAT+COL_DES+COL_QTE+COL_PU, ROW_H, fill=0, stroke=1)
        c.rect(x_tot, y - ROW_H, COL_TOT, ROW_H, fill=0, stroke=1)
        ty = y - ROW_H + 0.20 * cm
        c.setFont(BOLD, 9)
        c.drawRightString(x_pu + COL_PU - 0.15*cm, ty, f"Sous-total {nom} :")
        c.drawRightString(x_tot + COL_TOT - 0.15*cm, ty, f"{sous_total:.2f} €")
        y -= ROW_H + 0.15*cm
        c.setLineWidth(0.5)

    # Total général
    y, _ = saut_si_besoin(y)
    c.setLineWidth(1.3)
    c.rect(x_code, y - ROW_H, COL_CODE+COL_CAT+COL_DES+COL_QTE+COL_PU, ROW_H, fill=0, stroke=1)
    c.rect(x_tot, y - ROW_H, COL_TOT, ROW_H, fill=0, stroke=1)
    ty = y - ROW_H + 0.20 * cm
    c.setFont(BOLD, 11)
    c.drawRightString(x_pu + COL_PU - 0.15*cm, ty, "TOTAL GÉNÉRAL :")
    c.drawRightString(x_tot + COL_TOT - 0.15*cm, ty, f"{total_general:.2f} €")

    c.showPage()
    c.save()
    return output_path


def generer_test_alignement(output_path, nb_lignes=41):
    """Imprime une page de test pour caler le mode noir sur le papier
    pré-imprimé : un numéro d'ordre (1, 2, 3...) dans la colonne N° à chaque
    position de ligne calculée. À poser sur le papier de l'administration
    pour vérifier que chaque numéro tombe dans une case ; sinon ajuster
    « position 1re ligne » et « espacement » dans Paramètres > Impression."""
    try:
        import database as _dbt
        _p = _dbt.get_parametres()
        y1_mm  = float(_p.get("impr_y1", "79") or 79)
        pas_mm = float(_p.get("impr_pas", "5.15") or 5.15)
        off_x  = float(_p.get("impression_offset_x", "0") or 0) * cm / 10.0
        off_y  = float(_p.get("impression_offset_y", "0") or 0) * cm / 10.0
    except Exception:
        y1_mm, pas_mm, off_x, off_y = 79.0, 5.15, 0.0, 0.0

    c = pdfcanvas.Canvas(output_path, pagesize=A4)
    try:
        c.setViewerPreference("PrintScaling", "None")
    except Exception:
        pass
    X_NO_CENTRE  = 24.0 * cm / 10.0
    X_QTE_CENTRE = 41.4 * cm / 10.0
    ROW_H = pas_mm * cm / 10.0
    y_ligne1 = H - (y1_mm * cm / 10.0) + off_y

    c.setFillColorRGB(0, 0, 0)
    c.setFont(NORM, 10)
    for i in range(nb_lignes):
        ty = y_ligne1 - i * ROW_H
        c.drawCentredString(X_NO_CENTRE + off_x, ty, str(i + 1))
        c.drawCentredString(X_QTE_CENTRE + off_x, ty, "•")
    c.save()
    return output_path


def generer_liste_ration_pdf(resultat, nb_personnes, nb_jours, output_path):
    """PDF de la ration équilibrée : liste groupée avec codes, quantités, prix."""
    from datetime import datetime as _dt
    c = pdfcanvas.Canvas(output_path, pagesize=A4)
    ML = 1.5 * cm; MR = 1.5 * cm
    PW = W - ML - MR
    y = H - 1.5 * cm

    c.setFillColorRGB(0, 0, 0)
    c.setFont(BOLD, 16)
    c.drawString(ML, y, "LISTE DE PROVISIONS")
    c.setFont(NORM, 9)
    c.drawRightString(W - MR, y, f"Édité le {_dt.now().strftime('%d/%m/%Y')}")
    y -= 0.7 * cm
    c.setFont(NORM, 11)
    c.drawString(ML, y, f"{nb_personnes} personne(s)  ·  {nb_jours} jours  ·  "
                        f"ration équilibrée")
    y -= 0.9 * cm

    COL_CODE = 1.8 * cm
    COL_QTE  = 1.5 * cm
    COL_PU   = 2.2 * cm
    COL_TOT  = 2.4 * cm
    COL_NOM  = PW - COL_CODE - COL_QTE - COL_PU - COL_TOT
    ROW_H = 0.58 * cm

    par_groupe = {}
    for l in resultat["lignes"]:
        par_groupe.setdefault(l["groupe"], []).append(l)

    for groupe, lignes in par_groupe.items():
        if y < 3 * cm:
            c.showPage(); y = H - 1.5 * cm
        # Bandeau groupe
        c.setFillColorRGB(0.12, 0.16, 0.23)
        c.rect(ML, y - ROW_H, PW, ROW_H, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont(BOLD, 10)
        c.drawString(ML + 0.2*cm, y - ROW_H + 0.18*cm, groupe)
        sous_total = sum(l["total"] for l in lignes)
        c.drawRightString(W - MR - 0.2*cm, y - ROW_H + 0.18*cm, f"{sous_total:.2f} €")
        y -= ROW_H

        for l in lignes:
            if y < 2 * cm:
                c.showPage(); y = H - 1.5 * cm
            c.setStrokeColorRGB(0.85, 0.85, 0.85)
            c.setLineWidth(0.4)
            c.line(ML, y - ROW_H, W - MR, y - ROW_H)
            ty = y - ROW_H + 0.18*cm
            c.setFillColorRGB(0, 0, 0)
            c.setFont(NORM, 9)
            c.drawString(ML + 0.2*cm, ty, _num_id(l["code"]))
            c.drawString(ML + COL_CODE, ty, _trunc(c, l["nom"], COL_NOM-0.2*cm, NORM, 9))
            c.drawCentredString(ML + COL_CODE + COL_NOM + COL_QTE/2, ty, str(l["qte"]))
            c.drawRightString(ML + COL_CODE + COL_NOM + COL_QTE + COL_PU - 0.2*cm, ty,
                              f"{l['prix']:.2f} €")
            c.drawRightString(W - MR - 0.2*cm, ty, f"{l['total']:.2f} €")
            y -= ROW_H
        y -= 0.15 * cm

    # Total général
    if y < 2.5 * cm:
        c.showPage(); y = H - 1.5 * cm
    c.setLineWidth(1.2); c.setStrokeColorRGB(0, 0, 0)
    c.rect(ML, y - ROW_H, PW, ROW_H, fill=0, stroke=1)
    c.setFont(BOLD, 12)
    c.drawString(ML + 0.2*cm, y - ROW_H + 0.18*cm, "TOTAL GÉNÉRAL")
    c.drawRightString(W - MR - 0.2*cm, y - ROW_H + 0.18*cm, f"{resultat['total']:.2f} €")

    c.showPage(); c.save()
    return output_path


def generer_liste_hygiene_pdf(lignes, nb_personnes, output_path):
    """PDF de la liste hygiène : groupée corporelle / cellule."""
    from datetime import datetime as _dt
    c = pdfcanvas.Canvas(output_path, pagesize=A4)
    ML = 1.5 * cm; MR = 1.5 * cm; PW = W - ML - MR
    y = H - 1.6 * cm
    c.setFillColorRGB(0.03, 0.57, 0.70)
    c.setFont(BOLD, 17)
    c.drawString(ML, y, "LISTE HYGIÈNE MENSUELLE")
    c.setFillColorRGB(0.4,0.4,0.4); c.setFont(NORM, 10)
    c.drawRightString(W-MR, y, f"Édité le {_dt.now().strftime('%d/%m/%Y')}")
    y -= 0.65*cm
    c.setFillColorRGB(0,0,0); c.setFont(NORM, 11)
    c.drawString(ML, y, f"{nb_personnes} personne(s)  ·  1 mois")
    y -= 1.0*cm

    ROW = 0.55*cm
    total_g = 0.0
    for grp, titre, accent in [("corporelle","HYGIÈNE CORPORELLE  (× personnes)",(0.03,0.57,0.70)),
                               ("cellule","HYGIÈNE DE LA CELLULE  (fixe)",(0.49,0.23,0.93))]:
        items = [l for l in lignes if l["groupe"] == grp]
        if not items: continue
        c.setFillColorRGB(*accent); c.rect(ML, y-ROW, PW, ROW, fill=1, stroke=0)
        c.setFillColorRGB(1,1,1); c.setFont(BOLD, 11)
        c.drawString(ML+0.2*cm, y-ROW+0.16*cm, titre)
        y -= ROW
        c.setFillColorRGB(0.2,0.25,0.33); c.rect(ML, y-ROW, PW, ROW, fill=1, stroke=0)
        c.setFillColorRGB(1,1,1); c.setFont(BOLD, 8.5)
        c.drawString(ML+0.2*cm, y-ROW+0.16*cm, "Code")
        c.drawString(ML+2.0*cm, y-ROW+0.16*cm, "Produit")
        c.drawRightString(ML+13.0*cm, y-ROW+0.16*cm, "Qté")
        c.drawRightString(ML+15.0*cm, y-ROW+0.16*cm, "P.U.")
        c.drawRightString(W-MR-0.1*cm, y-ROW+0.16*cm, "Total")
        y -= ROW
        st = 0.0
        for i, l in enumerate(items):
            if y < 2.5*cm:
                c.showPage(); y = H - 1.6*cm
            if i % 2 == 0:
                c.setFillColorRGB(0.95,0.96,0.98); c.rect(ML, y-ROW, PW, ROW, fill=1, stroke=0)
            c.setFillColorRGB(0,0,0); c.setFont(NORM, 9)
            c.drawString(ML+0.2*cm, y-ROW+0.16*cm, _num_id(l["id"]))
            c.drawString(ML+2.0*cm, y-ROW+0.16*cm, _trunc(c, l["nom"], 10.5*cm, NORM, 9))
            c.drawRightString(ML+13.0*cm, y-ROW+0.16*cm, str(l["qte"]))
            c.drawRightString(ML+15.0*cm, y-ROW+0.16*cm, f"{l['prix']:.2f}€")
            c.drawRightString(W-MR-0.1*cm, y-ROW+0.16*cm, f"{l['total']:.2f}€")
            st += l["total"]; y -= ROW
        total_g += st
        c.setFont(BOLD, 10); c.setFillColorRGB(0,0,0)
        c.drawRightString(W-MR-0.1*cm, y-0.36*cm, f"Sous-total : {st:.2f}€")
        y -= 0.85*cm

    if y < 2.5*cm:
        c.showPage(); y = H - 1.6*cm
    c.setLineWidth(1.3); c.setStrokeColorRGB(0,0,0)
    c.rect(ML, y-0.7*cm, PW, 0.7*cm, fill=0, stroke=1)
    c.setFont(BOLD, 13)
    c.drawString(ML+0.2*cm, y-0.48*cm, "TOTAL MENSUEL")
    c.drawRightString(W-MR-0.1*cm, y-0.48*cm, f"{total_g:.2f} €")
    c.showPage(); c.save()
    return output_path
