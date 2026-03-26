"""
Bons de cantine - fond coloré par catégorie, IDs sans préfixe lettre.
AC14→14, B3→3, HY20→20, F12→12, etc.
"""
import os, re
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas as pdfcanvas

W, H = A4

BG = {
    "Accidentelle":    (0.60, 0.74, 0.60),
    "Tabac":           (0.80, 0.80, 0.80),
    "Hallal":          (0.74, 0.68, 0.88),
    "Alimentaire":     (0.68, 0.74, 0.86),
    "Boissons":        (0.91, 0.66, 0.72),
    "Hygiène":         (0.87, 0.62, 0.58),
    "Patisserie":      (0.92, 0.86, 0.68),
    "Fruits & Légumes":(0.62, 0.82, 0.62),
}
DEFAULT_BG = (0.82, 0.82, 0.82)

TOTAL_ROWS = 35
BOLD = "Helvetica-Bold"
NORM = "Helvetica"


def _num_id(prod_id):
    """Enlève le(s) préfixe(s) lettre(s) : 'AC14'→'14', 'B3'→'3', 'HY20'→'20'."""
    return re.sub(r'^[A-Za-z]+', '', str(prod_id))


def generer_bon_pdf(categorie, nom, prenom, ecrou, batiment, cellule,
                    lignes, total, date_str, output_path, signature_path=None):

    c = pdfcanvas.Canvas(output_path, pagesize=A4)
    bg = BG.get(categorie, DEFAULT_BG)

    # Fond coloré pleine page
    c.setFillColorRGB(*bg)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColorRGB(0, 0, 0)

    ML = 1.75 * cm
    PW = W - 2 * ML

    X_NOM      = ML
    X_ECROU    = ML + PW * 0.55
    X_PRENOM   = ML
    X_BATIMENT = ML + PW * 0.36
    X_CELLULE  = ML + PW * 0.62

    LBL = 16
    VAL = 13

    y = H - 1.55 * cm

    # ── LIGNE 1 : NOM [val]   ECROU [val] ───────────────────────────────────
    c.setFont(BOLD, LBL)
    c.drawString(X_NOM,   y, "NOM")
    c.drawString(X_ECROU, y, "ECROU")
    c.setFont(NORM, VAL)
    c.drawString(X_NOM   + c.stringWidth("NOM",   BOLD, LBL) + 8, y, (nom   or "").upper())
    c.drawString(X_ECROU + c.stringWidth("ECROU", BOLD, LBL) + 8, y, str(ecrou or ""))

    y -= 1.10 * cm

    # ── LIGNE 2 : PRENOM [val]  BATIMENT [val]  CELLULE [val] ───────────────
    c.setFont(BOLD, LBL)
    c.drawString(X_PRENOM,   y, "PRENOM")
    c.drawString(X_BATIMENT, y, "BATIMENT")
    c.drawString(X_CELLULE,  y, "CELLULE")
    c.setFont(NORM, VAL)
    c.drawString(X_PRENOM   + c.stringWidth("PRENOM",   BOLD, LBL) + 8, y, str(prenom   or ""))
    c.drawString(X_BATIMENT + c.stringWidth("BATIMENT", BOLD, LBL) + 8, y, str(batiment or ""))
    c.drawString(X_CELLULE  + c.stringWidth("CELLULE",  BOLD, LBL) + 8, y, str(cellule  or ""))

    y -= 1.05 * cm

    # ── ENCADRÉ CATÉGORIE — même couleur que le fond ─────────────────────────
    BOX_H = 1.30 * cm
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
    ROW_H   = (y - 1.80 * cm) / (TOTAL_ROWS + 1)

    # En-tête
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

    # Lignes — même couleur de fond partout
    for i in range(TOTAL_ROWS):
        _cell(c, ML,                    y, COL_NO,  ROW_H, bg)
        _cell(c, ML + COL_NO,           y, COL_QTE, ROW_H, bg)
        _cell(c, ML + COL_NO + COL_QTE, y, COL_DES, ROW_H, bg)

        if i < len(lignes):
            ligne  = lignes[i]
            text_y = y - ROW_H * 0.5 - 0.12 * cm
            c.setFillColorRGB(0, 0, 0)
            c.setFont(NORM, 8)
            # ID sans lettres
            c.drawCentredString(ML + COL_NO / 2,
                                text_y, _num_id(ligne.get("id", str(i + 1))))
            c.drawCentredString(ML + COL_NO + COL_QTE / 2,
                                text_y, str(ligne.get("qte", "")))
            txt = _trunc(c, str(ligne.get("nom", "")),
                         COL_DES - 0.4 * cm, NORM, 8)
            c.drawString(ML + COL_NO + COL_QTE + 0.18 * cm, text_y, txt)

        y -= ROW_H

    # ── DATE / SIGNATURE ─────────────────────────────────────────────────────
    DATE_Y = 0.85 * cm     # ligne texte en bas
    SIG_X  = ML + PW * 0.42
    SIG_H  = 2.0 * cm

    # Signature AU-DESSUS du label "Date / Signature"
    if signature_path and os.path.isfile(signature_path):
        try:
            c.drawImage(signature_path,
                        SIG_X + 2.8 * cm,
                        DATE_Y - 0.3 * cm,
                        width=8.0 * cm, height=SIG_H,
                        preserveAspectRatio=True, mask="auto")
        except Exception:
            pass

    # Texte tout en bas
    c.setFillColorRGB(0, 0, 0)
    c.setFont(NORM, 10)
    c.drawString(ML,    DATE_Y, f"Date:   {date_str}")
    c.drawString(SIG_X, DATE_Y, "Signature:")

    c.save()
    return output_path


def _cell(c, x, y, w, h, bg):
    c.setFillColorRGB(*bg)
    c.setStrokeColorRGB(0, 0, 0)
    c.rect(x, y - h, w, h, fill=1, stroke=1)

def _trunc(c, text, max_pts, font, size):
    c.setFont(font, size)
    while text and c.stringWidth(text, font, size) > max_pts:
        text = text[:-1]
    return text
