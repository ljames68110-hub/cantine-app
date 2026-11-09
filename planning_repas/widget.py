# -*- coding: utf-8 -*-
"""Widget de bureau : le repas du soir, en petit, toujours visible.

Un clic sur le plat ou sur le dessert ouvre la recette complète, avec les
quantités déjà ramenées au nombre de convives prévu ce jour-là.

Lancement :
    python lancer_widget.py
    python lancer_widget.py C:\\chemin\\vers\\cantine.db

La fenêtre est sans bordure : on la déplace en la faisant glisser, et sa
position est retenue d'un lancement à l'autre.
"""
import ctypes
import datetime as dt
import json
import os
import sys
import tkinter as tk
from tkinter import ttk

from . import db as dbmod
from . import generateur as gen

FOND = "#1f2430"
FOND_CARTE = "#2a3040"
TEXTE = "#e8eaf0"
TEXTE_DOUX = "#9aa3b8"
ACCENT = "#e0a458"
ACCENT_DESSERT = "#7fb069"
SURVOL = "#333b4f"

# --- Win32 : garder le widget au fond, comme un gadget de bureau -----------
WINDOWS = sys.platform.startswith("win")
HWND_BOTTOM = 1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000   # un clic n'active pas la fenetre
WS_EX_TOOLWINDOW = 0x00000080   # absente de la barre des taches et d'Alt-Tab


def _fichier_config(chemin_db):
    return os.path.join(os.path.dirname(os.path.abspath(chemin_db)),
                        "widget_planning.json")


class WidgetRepasDuJour(tk.Toplevel):
    """Petite fenêtre flottante. Utilisable seule ou depuis l'application."""

    LARGEUR = 300

    def __init__(self, parent, chemin_db="cantine.db", con=None):
        super().__init__(parent)
        self.chemin_db = chemin_db
        self.con = con or dbmod.initialiser(chemin_db)
        self.decalage = 0          # 0 = aujourd'hui, +1 = demain...
        self._drag = (0, 0)
        self._fenetres_recette = []

        self.overrideredirect(True)
        self.configure(bg=FOND)
        self._placer()
        self._construire()
        self.rafraichir()
        self._programmer_rafraichissement()
        # Le widget vit derriere les autres fenetres : il ne passe jamais
        # devant une application et un clic dessus ne le fait pas remonter.
        self.after(60, self._appliquer_styles)
        self.after(120, self._boucle_arriere_plan)

    # ---------------------------------------------------------------- forme
    def _placer(self):
        cfg = {}
        try:
            with open(_fichier_config(self.chemin_db), encoding="utf-8") as f:
                cfg = json.load(f)
        except (OSError, ValueError):
            pass
        # true : renvoye au fond en permanence (defaut).
        # false : pile normale, le widget reste ou il est sans etre force.
        self.toujours_derriere = bool(cfg.get("toujours_derriere", True))
        x = cfg.get("x")
        y = cfg.get("y")
        if x is None or y is None:
            self.update_idletasks()
            x = self.winfo_screenwidth() - self.LARGEUR - 40
            y = self.winfo_screenheight() - 300
        # Si l'écran a changé de taille, on remet la fenêtre dans le cadre
        x = max(0, min(int(x), self.winfo_screenwidth() - 120))
        y = max(0, min(int(y), self.winfo_screenheight() - 80))
        self.geometry(f"{self.LARGEUR}x10+{x}+{y}")

    # ------------------------------------------------------- arriere-plan
    def _hwnd(self):
        """Identifiant Windows de la fenetre, ou None hors Windows."""
        if not WINDOWS:
            return None
        try:
            cadre = self.wm_frame()
            return int(cadre, 16) if cadre else self.winfo_id()
        except (tk.TclError, ValueError):
            try:
                return self.winfo_id()
            except tk.TclError:
                return None

    def _appliquer_styles(self):
        """Empeche le widget de prendre le focus et de figurer dans Alt-Tab.

        Sans cela, cliquer sur le widget pour ouvrir une recette le ferait
        passer devant l'application en cours.
        """
        hwnd = self._hwnd()
        if not hwnd:
            return
        try:
            u32 = ctypes.windll.user32
            actuel = u32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            u32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                               actuel | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
        except (AttributeError, OSError):
            pass
        self._envoyer_derriere()

    def _envoyer_derriere(self):
        """Renvoie la fenetre au fond de la pile."""
        if not self.toujours_derriere:
            return
        hwnd = self._hwnd()
        if hwnd:
            try:
                ctypes.windll.user32.SetWindowPos(
                    hwnd, HWND_BOTTOM, 0, 0, 0, 0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
                return
            except (AttributeError, OSError):
                pass
        try:
            self.lower()          # repli Tk, suffisant hors Windows
        except tk.TclError:
            pass

    def _boucle_arriere_plan(self):
        """Reapplique la position dans la pile toutes les trois secondes.

        Certaines applications remontent toutes les fenetres en s'ouvrant ;
        cette verification periodique remet le widget a sa place sans que tu
        aies a y penser.
        """
        self._envoyer_derriere()
        self.after(3000, self._boucle_arriere_plan)

    def _memoriser_position(self):
        try:
            with open(_fichier_config(self.chemin_db), "w", encoding="utf-8") as f:
                json.dump({"x": self.winfo_x(), "y": self.winfo_y(),
                           "toujours_derriere": self.toujours_derriere}, f)
        except OSError:
            pass

    def _construire(self):
        cadre = tk.Frame(self, bg=FOND, highlightthickness=1,
                         highlightbackground="#3a4054")
        cadre.pack(fill="both", expand=True)
        self.cadre = cadre

        # --- barre de titre : déplacement, navigation, fermeture
        barre = tk.Frame(cadre, bg=FOND)
        barre.pack(fill="x", padx=8, pady=(7, 2))

        self.lb_jour = tk.Label(barre, text="", bg=FOND, fg=TEXTE_DOUX,
                                font=("Segoe UI", 8, "bold"), anchor="w")
        self.lb_jour.pack(side="left")

        tk.Label(barre, text="✕", bg=FOND, fg=TEXTE_DOUX,
                 font=("Segoe UI", 9)).pack(side="right", padx=(6, 0))
        barre.winfo_children()[-1].bind("<Button-1>", lambda e: self.fermer())

        for texte, pas in (("›", 1), ("‹", -1)):
            b = tk.Label(barre, text=texte, bg=FOND, fg=TEXTE_DOUX,
                         font=("Segoe UI", 11))
            b.pack(side="right", padx=2)
            b.bind("<Button-1>", lambda e, p=pas: self.naviguer(p))

        for w in (barre, self.lb_jour, cadre):
            w.bind("<Button-1>", self._debut_drag)
            w.bind("<B1-Motion>", self._drag_motion)
            w.bind("<ButtonRelease-1>", lambda e: (self._memoriser_position(),
                                                   self._envoyer_derriere()))

        # --- carte du plat
        self.carte_plat = tk.Frame(cadre, bg=FOND_CARTE, cursor="hand2")
        self.carte_plat.pack(fill="x", padx=8, pady=(4, 4))
        self.lb_plat_titre = tk.Label(self.carte_plat, text="Plat", bg=FOND_CARTE,
                                      fg=ACCENT, font=("Segoe UI", 7, "bold"),
                                      anchor="w")
        self.lb_plat_titre.pack(fill="x", padx=10, pady=(7, 0))
        self.lb_plat = tk.Label(self.carte_plat, text="", bg=FOND_CARTE, fg=TEXTE,
                                font=("Segoe UI", 10, "bold"), anchor="w",
                                justify="left", wraplength=self.LARGEUR - 40)
        self.lb_plat.pack(fill="x", padx=10, pady=(0, 8))

        # --- carte du dessert
        self.carte_dessert = tk.Frame(cadre, bg=FOND_CARTE, cursor="hand2")
        self.lb_dessert_titre = tk.Label(self.carte_dessert, text="Dessert",
                                         bg=FOND_CARTE, fg=ACCENT_DESSERT,
                                         font=("Segoe UI", 7, "bold"), anchor="w")
        self.lb_dessert_titre.pack(fill="x", padx=10, pady=(7, 0))
        self.lb_dessert = tk.Label(self.carte_dessert, text="", bg=FOND_CARTE,
                                   fg=TEXTE, font=("Segoe UI", 9), anchor="w",
                                   justify="left", wraplength=self.LARGEUR - 40)
        self.lb_dessert.pack(fill="x", padx=10, pady=(0, 8))

        # --- pied : nombre de convives
        self.lb_pied = tk.Label(cadre, text="", bg=FOND, fg=TEXTE_DOUX,
                                font=("Segoe UI", 7), anchor="w")
        self.lb_pied.pack(fill="x", padx=10, pady=(0, 7))

        self._rendre_cliquable(self.carte_plat, lambda: self.ouvrir_recette("plat"))
        self._rendre_cliquable(self.carte_dessert, lambda: self.ouvrir_recette("dessert"))

    def _rendre_cliquable(self, carte, action):
        def survol(_, couleur):
            for w in [carte] + list(carte.winfo_children()):
                w.configure(bg=couleur)
        for w in [carte] + list(carte.winfo_children()):
            w.bind("<Button-1>", lambda e: action())
            w.bind("<Enter>", lambda e: survol(e, SURVOL))
            w.bind("<Leave>", lambda e: survol(e, FOND_CARTE))
            w.configure(cursor="hand2")

    # ------------------------------------------------------------ deplacement
    def _debut_drag(self, e):
        self._drag = (e.x_root - self.winfo_x(), e.y_root - self.winfo_y())

    def _drag_motion(self, e):
        self.geometry(f"+{e.x_root - self._drag[0]}+{e.y_root - self._drag[1]}")

    # -------------------------------------------------------------- contenu
    def naviguer(self, pas):
        self.decalage += pas
        self.rafraichir()

    def rafraichir(self):
        jour = dt.date.today() + dt.timedelta(days=self.decalage)
        self.repas = gen.repas_du_jour(self.con, jour)

        etiquette = {0: "Ce soir", 1: "Demain", -1: "Hier"}.get(
            self.decalage, jour.strftime("%d/%m"))
        self.lb_jour.configure(
            text=f"{etiquette} · {gen.JOURS_FR[jour.weekday()]} {jour.strftime('%d/%m')}".upper())

        if not self.repas or not self.repas["plat"]:
            self.lb_plat_titre.configure(text="Aucun planning")
            self.lb_plat.configure(text="Rien de prévu pour ce jour")
            self.carte_dessert.pack_forget()
            self.lb_pied.configure(text="Génère un planning dans l'application")
        else:
            self.lb_plat_titre.configure(text="PLAT")
            self.lb_plat.configure(text=self.repas["plat"]["nom"])
            if self.repas["dessert"]:
                self.carte_dessert.pack(fill="x", padx=8, pady=(0, 4))
                self.lb_dessert.configure(text=self.repas["dessert"]["nom"])
            else:
                self.carte_dessert.pack_forget()
            n = self.repas["nb_personnes"]
            self.lb_pied.configure(
                text=f"{n} personne{'s' if n > 1 else ''} · clic pour la recette")

        self.update_idletasks()
        self.geometry(f"{self.LARGEUR}x{self.cadre.winfo_reqheight()}")

    def _programmer_rafraichissement(self):
        """Recharge toutes les 10 minutes : le jour tourne, le planning peut
        être modifié dans l'application pendant que le widget est ouvert."""
        if self.decalage == 0:
            self.rafraichir()
        self.after(600000, self._programmer_rafraichissement)

    # -------------------------------------------------------------- recette
    def ouvrir_recette(self, quoi):
        if not getattr(self, "repas", None):
            return
        recette = self.repas.get(quoi)
        if not recette:
            return
        FenetreRecette(self, recette, self.repas["nb_personnes"], self.con)

    def fermer(self):
        self._memoriser_position()
        for f in self._fenetres_recette:
            try:
                f.destroy()
            except tk.TclError:
                pass
        self.destroy()
        if isinstance(self.master, tk.Tk):
            self.master.destroy()


class FenetreRecette(tk.Toplevel):
    """Recette complète : ingrédients calculés pour le nombre de convives."""

    def __init__(self, proprietaire, recette, nb_personnes, con):
        # Rattachee a la fenetre racine et non au widget : le widget ne prend
        # pas le focus, une fenetre fille n'aurait pas pu le prendre non plus.
        super().__init__(proprietaire.master)
        self.title(recette["nom"])
        self.configure(bg=FOND)
        self.geometry("520x560")
        self.minsize(420, 400)
        proprietaire._fenetres_recette.append(self)
        # Elle, en revanche, doit s'afficher devant : c'est ce qu'on vient
        # d'ouvrir. Mais sans rester collee au-dessus de tout le reste.
        self.after(30, self._au_premier_plan)

        tk.Label(self, text=recette["nom"], bg=FOND, fg=TEXTE,
                 font=("Segoe UI", 13, "bold"), wraplength=480,
                 justify="left", anchor="w").pack(fill="x", padx=16, pady=(14, 2))

        self.v_pers = tk.IntVar(value=nb_personnes)
        barre = tk.Frame(self, bg=FOND)
        barre.pack(fill="x", padx=16, pady=(0, 8))
        tk.Label(barre, text="Pour", bg=FOND, fg=TEXTE_DOUX,
                 font=("Segoe UI", 9)).pack(side="left")
        sp = ttk.Spinbox(barre, from_=1, to=12, width=3, textvariable=self.v_pers,
                         command=self._recalculer)
        sp.pack(side="left", padx=6)
        tk.Label(barre, text="personnes", bg=FOND, fg=TEXTE_DOUX,
                 font=("Segoe UI", 9)).pack(side="left")
        sp.bind("<Return>", lambda e: self._recalculer())

        tk.Label(self, text="INGRÉDIENTS", bg=FOND, fg=ACCENT,
                 font=("Segoe UI", 8, "bold"), anchor="w").pack(
            fill="x", padx=16, pady=(4, 2))

        cadre_ing = tk.Frame(self, bg=FOND_CARTE)
        cadre_ing.pack(fill="x", padx=16)
        self.txt_ing = tk.Text(cadre_ing, height=9, bg=FOND_CARTE, fg=TEXTE,
                               font=("Consolas", 9), relief="flat", wrap="none",
                               padx=10, pady=8)
        self.txt_ing.pack(fill="both", expand=True)

        tk.Label(self, text="PRÉPARATION", bg=FOND, fg=ACCENT,
                 font=("Segoe UI", 8, "bold"), anchor="w").pack(
            fill="x", padx=16, pady=(12, 2))

        cadre_prep = tk.Frame(self, bg=FOND_CARTE)
        cadre_prep.pack(fill="both", expand=True, padx=16, pady=(0, 14))
        txt = tk.Text(cadre_prep, bg=FOND_CARTE, fg=TEXTE, font=("Segoe UI", 10),
                      relief="flat", wrap="word", padx=12, pady=10)
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", recette["instructions"] or "Pas d'instructions saisies.")
        txt.configure(state="disabled")

        self.recette = recette
        self.con = con
        self._recalculer()
        self.bind("<Escape>", lambda e: self.destroy())

    def _au_premier_plan(self):
        """Amene la recette devant une seule fois, puis la laisse vivre
        normalement dans la pile des fenetres."""
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
        except tk.TclError:
            pass

    def _recalculer(self):
        try:
            n = max(1, int(self.v_pers.get()))
        except (tk.TclError, ValueError):
            return
        lignes = gen.ingredients_calcules(self.con, self.recette, n)
        self.txt_ing.configure(state="normal")
        self.txt_ing.delete("1.0", "end")
        for l in lignes:
            marque = " (par repas)" if l["fixe"] else ""
            self.txt_ing.insert(
                "end", f'{l["code"]:>5}  x{l["qte"]:<3} {l["designation"]}{marque}\n')
        self.txt_ing.configure(state="disabled")
