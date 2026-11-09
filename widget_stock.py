# -*- coding: utf-8 -*-
"""
StockWidget — vrai widget de bureau pour gérer « Mon stock » de cantine
(produits en cellule) sans ouvrir toute l'application.

- Agit sur « Mon stock » (base cantine.db partagée) : rempli automatiquement
  par les bons au nom de l'utilisateur + les créances, et ajustable ici.
- Vrai widget : sans barre de titre, absent de la barre des tâches, posé sur
  le bureau DERRIÈRE les autres fenêtres (comme un gadget), déplaçable.
- Retrait quotidien en un clic, ajout manuel de ce qu'on a déjà en cellule,
  journal des retraits, annulation.

Intégré à l'application : lancé par « Cantine.exe --widget » (plus de
StockWidget.exe séparé). Voir main.py (point d'entrée) et TOUT_FAIRE.bat.
"""
import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog
import database as db

# ── Thème ─────────────────────────────────────────────────────────────────────
DARK_BG   = "#1a1f2e"
PANEL_BG  = "#232838"
CARD_BG   = "#2d3347"
ACCENT    = "#2563eb"
SUCCESS   = "#16a34a"
DANGER    = "#dc2626"
GOLD      = "#f59e0b"
TEXT      = "#f1f5f9"
TEXT_MUTED = "#94a3b8"
HEADER_BG = "#0e7490"
BORDER    = "#0b4a5c"


class StockWidget(tk.Tk):
    def __init__(self):
        super().__init__()
        self.configure(bg=BORDER)
        self.overrideredirect(True)          # pas de barre de titre -> look widget
        self.attributes("-topmost", False)   # surtout pas au-dessus

        geo = ""
        try:
            geo = db.get_parametres().get("widget_geometry", "")
        except Exception:
            pass
        self.geometry(geo if geo else "370x620+40+40")
        self.minsize(300, 300)

        self.recherche_var = tk.StringVar()
        self.recherche_var.trace_add("write", lambda *_: self._afficher_liste())
        self._apres_id = None
        self._bottom_id = None
        self._drag = {"x": 0, "y": 0}
        self._alertes_vues = set()      # ids déjà signalés en pop-up cette session
        self._perem_vus = set()         # ids péremption déjà signalés
        self._reception_ouverte = False
        self._reportes = set()          # réceptions « plus tard » cette session
        self._manuel_courant = False    # réception ouverte manuellement ?
        self._bas_courant = []          # dernière liste « stock bas » (clic bandeau)
        self._perem_courant = []        # dernière liste péremption (clic bandeau)

        try:
            self.seuil = int(db.get_parametres().get("stock_seuil_bas", "2") or 2)
        except Exception:
            self.seuil = 2

        self._construire()
        self._afficher_liste()
        self._planifier_refresh()
        # Comportement « derrière les fenêtres » (Windows) : après la 1re carte
        self.after(300, self._mode_bureau)
        # Demande de réception des livraisons prévues : UNE SEULE fois par jour
        self.after(700, self._auto_receptions)
        self.protocol("WM_DELETE_WINDOW", self._fermer)

    # ── Vrai widget de bureau : derrière les fenêtres, hors barre des tâches ──
    def _mode_bureau(self):
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = self.winfo_id()
            # remonte au vrai top-level (overrideredirect)
            parent = user32.GetParent(hwnd)
            if parent:
                hwnd = parent
            GWL_EXSTYLE = -20
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_APPWINDOW  = 0x00040000
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = (style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            self._hwnd = hwnd
            self._user32 = user32
            self._vers_le_fond()
        except Exception:
            # Hors Windows ou échec : au moins ne pas rester au-dessus
            try:
                self.lower()
            except Exception:
                pass

    def _vers_le_fond(self):
        """Repousse la fenêtre tout au fond (derrière les autres), sans l'activer."""
        try:
            HWND_BOTTOM = 1
            SWP_NOSIZE = 0x0001; SWP_NOMOVE = 0x0002; SWP_NOACTIVATE = 0x0010
            self._user32.SetWindowPos(self._hwnd, HWND_BOTTOM, 0, 0, 0, 0,
                                      SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)
        except Exception:
            try:
                self.lower()
            except Exception:
                pass
        # réassure régulièrement qu'on reste au fond
        self._bottom_id = self.after(2500, self._vers_le_fond)

    # ── Interface ─────────────────────────────────────────────────────────────
    def _construire(self):
        # cadre interne (le BORDER sert de fine bordure)
        cont = tk.Frame(self, bg=DARK_BG)
        cont.pack(fill="both", expand=True, padx=2, pady=2)

        # Barre de titre custom (déplacement + fermeture)
        bar = tk.Frame(cont, bg=HEADER_BG, height=34)
        bar.pack(fill="x")
        titre = tk.Label(bar, text="📦  Mon stock", font=("Helvetica", 12, "bold"),
                         bg=HEADER_BG, fg="white")
        titre.pack(side="left", padx=10, pady=6)
        self.total_lbl = tk.Label(bar, text="", font=("Helvetica", 10, "bold"),
                                  bg=HEADER_BG, fg="white")
        self.total_lbl.pack(side="right", padx=4)
        fermer = tk.Label(bar, text="✕", font=("Helvetica", 12, "bold"),
                          bg=HEADER_BG, fg="white", cursor="hand2")
        fermer.pack(side="right", padx=8)
        fermer.bind("<Button-1>", lambda e: self._fermer())
        # déplacement du widget en tirant la barre
        for w in (bar, titre):
            w.bind("<Button-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)

        # Outils
        outils = tk.Frame(cont, bg=PANEL_BG)
        outils.pack(fill="x")
        tk.Button(outils, text="➕ Ajouter", command=self._ajouter_manuel,
                  font=("Helvetica", 9, "bold"), bg=SUCCESS, fg="white", bd=0,
                  cursor="hand2", pady=5).pack(side="left", padx=(8, 4), pady=6)
        tk.Button(outils, text="⟳", command=self._rafraichir_manuel,
                  font=("Helvetica", 10), bg=CARD_BG, fg=TEXT, bd=0,
                  cursor="hand2", width=3, pady=4).pack(side="left", padx=2, pady=6)
        tk.Button(outils, text="↶", command=self._annuler,
                  font=("Helvetica", 10), bg=CARD_BG, fg=GOLD, bd=0,
                  cursor="hand2", width=3, pady=4).pack(side="left", padx=2, pady=6)
        tk.Button(outils, text="📅", command=self._voir_jour,
                  font=("Helvetica", 10), bg=CARD_BG, fg=TEXT, bd=0,
                  cursor="hand2", width=3, pady=4).pack(side="left", padx=2, pady=6)
        tk.Button(outils, text="⚙", command=self._regler_seuil,
                  font=("Helvetica", 10), bg=CARD_BG, fg=TEXT, bd=0,
                  cursor="hand2", width=3, pady=4).pack(side="left", padx=2, pady=6)
        # Bouton « Livraisons à réceptionner » (ouvre les réceptions à la demande)
        self.btn_recept = tk.Button(outils, text="📦 Livraisons",
                  command=self._ouvrir_receptions_manuel,
                  font=("Helvetica", 9, "bold"), bg=GOLD, fg="white", bd=0,
                  cursor="hand2", pady=5)
        # packé/masqué dynamiquement par _maj_bouton_receptions()

        # 2e ligne d'outils : effacer de la liste
        outils2 = tk.Frame(cont, bg=PANEL_BG)
        outils2.pack(fill="x")
        tk.Button(outils2, text="✖ Effacer des articles", command=self._effacer_selection,
                  font=("Helvetica", 9, "bold"), bg="#b45309", fg="white", bd=0,
                  cursor="hand2", pady=5).pack(side="left", padx=(8, 4), pady=(0, 6))
        tk.Button(outils2, text="🗑 Tout effacer", command=self._tout_effacer,
                  font=("Helvetica", 9, "bold"), bg=DANGER, fg="white", bd=0,
                  cursor="hand2", pady=5).pack(side="left", padx=4, pady=(0, 6))

        # 3e ligne d'outils : transfert entre les 2 postes (clé USB)
        outils3 = tk.Frame(cont, bg=PANEL_BG)
        outils3.pack(fill="x")
        tk.Button(outils3, text="📤 Exporter", command=self._exporter,
                  font=("Helvetica", 9, "bold"), bg="#0e7490", fg="white", bd=0,
                  cursor="hand2", pady=5).pack(side="left", padx=(8, 4), pady=(0, 6))
        tk.Button(outils3, text="📥 Importer", command=self._importer,
                  font=("Helvetica", 9, "bold"), bg="#0e7490", fg="white", bd=0,
                  cursor="hand2", pady=5).pack(side="left", padx=4, pady=(0, 6))

        # Bandeau d'alerte stock bas (masqué si rien) — CLIQUABLE pour le détail
        self.banniere = tk.Label(cont, text="", font=("Helvetica", 9, "bold"),
                                 bg=DANGER, fg="white", anchor="w", justify="left",
                                 wraplength=330, padx=8, pady=4, cursor="hand2")
        self.banniere.bind("<Button-1>",
                           lambda e: self._popup_stock_bas(self._bas_courant))
        # Bandeau d'alerte péremption (masqué si rien) — CLIQUABLE pour le détail
        self.banniere_perem = tk.Label(cont, text="", font=("Helvetica", 9, "bold"),
                                       bg="#b45309", fg="white", anchor="w",
                                       justify="left", wraplength=330, padx=8, pady=4,
                                       cursor="hand2")
        self.banniere_perem.bind("<Button-1>",
                           lambda e: self._popup_peremption(self._perem_courant))
        # packés dynamiquement dans _afficher_liste

        # Recherche
        rech = tk.Frame(cont, bg=DARK_BG)
        self._rech_frame = rech
        rech.pack(fill="x", padx=8, pady=(2, 4))
        tk.Label(rech, text="🔎", bg=DARK_BG, fg=TEXT_MUTED).pack(side="left")
        tk.Entry(rech, textvariable=self.recherche_var, font=("Helvetica", 11),
                 bg=CARD_BG, fg=TEXT, bd=0, insertbackground=TEXT).pack(
                 side="left", fill="x", expand=True, padx=6, ipady=4)

        # ── Pied (statut + poignée de redimensionnement) — packé AVANT la liste
        #    pour qu'il réserve le bas et que la liste se coupe proprement. ──
        pied = tk.Frame(cont, bg=PANEL_BG)
        pied.pack(fill="x", side="bottom")
        grip = tk.Label(pied, text="◢", font=("Helvetica", 11, "bold"),
                        bg=PANEL_BG, fg=TEXT_MUTED, cursor="bottom_right_corner")
        grip.pack(side="right", padx=(2, 4))
        grip.bind("<Button-1>", self._resize_start)
        grip.bind("<B1-Motion>", self._resize_move)
        self.statut = tk.Label(pied, text="", font=("Helvetica", 9),
                               bg=PANEL_BG, fg=TEXT_MUTED, anchor="w")
        self.statut.pack(fill="x", side="left")

        # ── Liste défilante (avec barre déroulante bien visible) ──
        corps = tk.Frame(cont, bg=DARK_BG)
        corps.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        self.canvas = tk.Canvas(corps, bg=DARK_BG, highlightthickness=0)
        sb = tk.Scrollbar(corps, orient="vertical", command=self.canvas.yview,
                          width=16, troughcolor=PANEL_BG, bg=CARD_BG,
                          activebackground=ACCENT, bd=0)
        self.liste = tk.Frame(self.canvas, bg=DARK_BG)
        self.liste.bind("<Configure>",
                        lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._win = self.canvas.create_window((0, 0), window=self.liste, anchor="nw")
        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfig(self._win, width=e.width))
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        # molette : rebindée sur cette liste à chaque entrée de souris (sinon un
        # dialogue qui l'a prise la garderait)
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all(
            "<MouseWheel>", lambda ev: self.canvas.yview_scroll(int(-ev.delta / 120), "units")))

    # ── Déplacement ──────────────────────────────────────────────────────────
    def _drag_start(self, e):
        self._drag = {"x": e.x_root - self.winfo_x(), "y": e.y_root - self.winfo_y()}

    def _drag_move(self, e):
        self.geometry(f"+{e.x_root - self._drag['x']}+{e.y_root - self._drag['y']}")

    # ── Redimensionnement (poignée en bas à droite) ──────────────────────────
    def _resize_start(self, e):
        self._rsz = {"x": e.x_root, "y": e.y_root,
                     "w": self.winfo_width(), "h": self.winfo_height()}

    def _resize_move(self, e):
        w = max(300, self._rsz["w"] + (e.x_root - self._rsz["x"]))
        h = max(300, self._rsz["h"] + (e.y_root - self._rsz["y"]))
        self.geometry(f"{w}x{h}")

    # ── Affichage de la liste ────────────────────────────────────────────────
    def _afficher_liste(self):
        for w in self.liste.winfo_children():
            w.destroy()
        filtre = self.recherche_var.get().strip().lower()
        try:
            articles = db.mon_stock_get()
            # On n'affiche QUE le stock consommable : les objets durables
            # (balai, boîtes, économe, casserole, ventilateur, revues…) sont exclus.
            articles = [a for a in articles
                        if not db.est_durable(a.get("nom", ""), a.get("categorie", ""))]
            total = sum(float(a.get("prix", 0) or 0) * int(a.get("qte", 0))
                        for a in articles)
        except Exception as ex:
            tk.Label(self.liste, text=f"Erreur base : {ex}", bg=DARK_BG,
                     fg=DANGER, wraplength=320, justify="left").pack(pady=20)
            return
        self.total_lbl.config(text=f"{total:.2f} €")

        articles.sort(key=lambda a: (a.get("categorie", ""), a.get("nom", "")))
        if filtre:
            articles = [a for a in articles
                        if filtre in a.get("nom", "").lower()
                        or filtre in str(a.get("id", "")).lower()]

        if not articles:
            msg = "Stock vide.\nUtilisez « ➕ Ajouter »." if not filtre else "Aucun article trouvé."
            tk.Label(self.liste, text=msg, bg=DARK_BG, fg=TEXT_MUTED,
                     font=("Helvetica", 10), justify="center").pack(pady=20)
        else:
            for a in articles:
                self._ligne_article(a)

        # ── Alerte stock bas : BANDEAU discret uniquement (plus de pop-up auto).
        #    Clique le bandeau pour voir le détail. ───────────────────────────
        try:
            bas = db.get_stock_bas(self.seuil)
        except Exception:
            bas = []
        self._bas_courant = bas
        if bas:
            noms = ", ".join(f"{b['nom']} ({b['qte']})" for b in bas[:6])
            suite = "…" if len(bas) > 6 else ""
            self.banniere.config(
                text=f"⚠ Stock bas — à racheter : {noms}{suite}   (clic = détail)")
            try:
                self.banniere.pack(fill="x", before=self._rech_frame)
            except Exception:
                self.banniere.pack(fill="x")
        else:
            self.banniere.pack_forget()

        # ── Alerte péremption : BANDEAU discret uniquement (clic = détail) ────
        try:
            perims = db.get_peremptions_proches(7)
        except Exception:
            perims = []
        self._perem_courant = perims
        if perims:
            def _lib(p):
                r = p["jours_restants"]
                if r < 0:
                    return f"{p['nom']} (périmé)"
                if r == 0:
                    return f"{p['nom']} (aujourd'hui)"
                return f"{p['nom']} ({r} j)"
            txt = ", ".join(_lib(p) for p in perims[:6]) + ("…" if len(perims) > 6 else "")
            self.banniere_perem.config(text=f"⏰ Péremption : {txt}   (clic = détail)")
            try:
                self.banniere_perem.pack(fill="x", before=self._rech_frame)
            except Exception:
                self.banniere_perem.pack(fill="x")
        else:
            self.banniere_perem.pack_forget()

        try:
            import datetime as _dt
            jour = _dt.date.today().strftime("%Y-%m-%d")
            retr = db.get_retraits(jour=jour)
            n = sum(int(x["quantite"]) for x in retr)
            self.statut.config(text=f"  Aujourd'hui : {n} retrait(s)  —  "
                                    f"{len(articles)} référence(s)")
        except Exception:
            self.statut.config(text="")

    def _ligne_article(self, a):
        pid = a["id"]
        nom = a.get("nom", pid)
        qte = int(a.get("qte", 0))
        row = tk.Frame(self.liste, bg=CARD_BG)
        row.pack(fill="x", pady=2)

        gauche = tk.Frame(row, bg=CARD_BG)
        gauche.pack(side="left", fill="x", expand=True, padx=(8, 4), pady=5)
        tk.Label(gauche, text=nom, font=("Helvetica", 10, "bold"), bg=CARD_BG,
                 fg=TEXT, anchor="w", justify="left", wraplength=170).pack(anchor="w")
        bas = qte <= self.seuil
        coul = DANGER if bas else (GOLD if qte <= self.seuil + 2 else SUCCESS)
        ligne_reste = tk.Frame(gauche, bg=CARD_BG); ligne_reste.pack(anchor="w", fill="x")
        suffixe = "  ⚠" if bas else ""
        tk.Label(ligne_reste, text=f"reste : {qte}{suffixe}", font=("Helvetica", 9),
                 bg=CARD_BG, fg=coul).pack(side="left")
        # Rappel intelligent : petit bouton pour (dés)activer le rappel de rachat
        if bas:
            try:
                rappel = db.est_consommable(pid, nom, a.get("categorie", ""))
            except Exception:
                rappel = True
            txt = "🔕 ne plus rappeler" if rappel else "🔔 me rappeler"
            lbl = tk.Label(ligne_reste, text=txt, font=("Helvetica", 8),
                           bg=CARD_BG, fg=TEXT_MUTED, cursor="hand2")
            lbl.pack(side="left", padx=8)
            lbl.bind("<Button-1>",
                     lambda e, p=pid, v=(not rappel): self._toggle_rappel(p, v))

        # Ligne péremption (cliquable pour saisir/modifier)
        perem = (a.get("peremption") or "").strip()
        txt_p, coul_p = self._perem_affichage(perem)
        lp = tk.Label(gauche, text=txt_p, font=("Helvetica", 8), bg=CARD_BG,
                      fg=coul_p, cursor="hand2", anchor="w")
        lp.pack(anchor="w")
        lp.bind("<Button-1>", lambda e, p=pid, n=nom, d=perem: self._editer_peremption(p, n, d))

        droite = tk.Frame(row, bg=CARD_BG)
        droite.pack(side="right", padx=(2, 8))
        spin = tk.Spinbox(droite, from_=1, to=max(1, qte), width=3,
                          font=("Helvetica", 10), bg=DARK_BG, fg=TEXT, bd=0,
                          buttonbackground=CARD_BG, insertbackground=TEXT,
                          justify="center")
        spin.delete(0, "end"); spin.insert(0, "1")
        spin.pack(side="left", padx=(0, 4))
        tk.Button(droite, text="Retirer", font=("Helvetica", 9, "bold"),
                  bg=ACCENT, fg="white", bd=0, cursor="hand2", padx=6, pady=4,
                  command=lambda p=pid, s=spin: self._retirer(p, s.get())).pack(side="left")
        tk.Button(droite, text="−1", font=("Helvetica", 10, "bold"),
                  bg=DANGER, fg="white", bd=0, cursor="hand2", padx=8, pady=4,
                  command=lambda p=pid: self._retirer(p, 1)).pack(side="left", padx=(4, 0))

    def _popup_peremption(self, articles):
        win = tk.Toplevel(self)
        win.title("Péremption")
        win.configure(bg=DARK_BG)
        win.attributes("-topmost", True)
        win.geometry("360x360")
        tk.Label(win, text="⏰ Attention aux dates", font=("Helvetica", 13, "bold"),
                 bg=DARK_BG, fg=GOLD).pack(pady=(12, 2))
        tk.Label(win, text="Articles périmés ou bientôt périmés :",
                 font=("Helvetica", 9), bg=DARK_BG, fg=TEXT_MUTED).pack()
        cadre = tk.Frame(win, bg=DARK_BG); cadre.pack(fill="both", expand=True, padx=14, pady=8)
        import datetime as _dt
        for a in articles:
            r = a["jours_restants"]
            try:
                jj = _dt.datetime.strptime(a["peremption"], "%Y-%m-%d").strftime("%d/%m/%Y")
            except Exception:
                jj = a["peremption"]
            if r < 0:
                t, col = f"•  {a['nom']}  —  PÉRIMÉ le {jj}", DANGER
            elif r == 0:
                t, col = f"•  {a['nom']}  —  périme aujourd'hui", DANGER
            else:
                t, col = f"•  {a['nom']}  —  le {jj} (dans {r} j)", GOLD
            tk.Label(cadre, text=t, font=("Helvetica", 10, "bold"), bg=DARK_BG,
                     fg=col, anchor="w", wraplength=320, justify="left").pack(anchor="w", pady=1)
        tk.Button(win, text="OK", command=win.destroy, font=("Helvetica", 10, "bold"),
                  bg=ACCENT, fg="white", bd=0, cursor="hand2", padx=20, pady=6).pack(pady=8)

    # ── Péremption ────────────────────────────────────────────────────────────
    def _perem_affichage(self, perem):
        """(texte, couleur) pour la ligne de péremption d'un article."""
        if not perem:
            return ("📅 + date de péremption", TEXT_MUTED)
        import datetime as _dt
        try:
            d = _dt.datetime.strptime(perem, "%Y-%m-%d").date()
        except Exception:
            return ("📅 + date de péremption", TEXT_MUTED)
        reste = (d - _dt.date.today()).days
        jj = d.strftime("%d/%m/%Y")
        if reste < 0:
            return (f"⏰ PÉRIMÉ le {jj}", DANGER)
        if reste == 0:
            return (f"⏰ périme aujourd'hui ({jj})", DANGER)
        if reste <= 7:
            return (f"⏰ périme le {jj} (dans {reste} j)", GOLD)
        return (f"📅 {jj}", TEXT_MUTED)

    def _editer_peremption(self, pid, nom, courant):
        win = tk.Toplevel(self)
        win.title("Date de péremption")
        win.configure(bg=DARK_BG)
        win.attributes("-topmost", True)
        win.geometry("320x210")
        tk.Label(win, text="📅 Date de péremption", font=("Helvetica", 12, "bold"),
                 bg=DARK_BG, fg=TEXT).pack(pady=(12, 2))
        tk.Label(win, text=nom, font=("Helvetica", 9), bg=DARK_BG, fg=TEXT_MUTED,
                 wraplength=290).pack()
        tk.Label(win, text="Format : JJ/MM/AAAA", font=("Helvetica", 8),
                 bg=DARK_BG, fg=TEXT_MUTED).pack(pady=(8, 2))
        var = tk.StringVar()
        if courant:
            import datetime as _dt
            try:
                var.set(_dt.datetime.strptime(courant, "%Y-%m-%d").strftime("%d/%m/%Y"))
            except Exception:
                pass
        e = tk.Entry(win, textvariable=var, font=("Helvetica", 13), justify="center",
                     bg=CARD_BG, fg=TEXT, bd=0, insertbackground=TEXT)
        e.pack(ipady=5, padx=40, fill="x"); e.focus_set()

        def enregistrer():
            txt = var.get().strip()
            iso = ""
            if txt:
                import datetime as _dt
                ok = None
                for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
                    try:
                        ok = _dt.datetime.strptime(txt, fmt).date()
                        break
                    except Exception:
                        ok = None
                if not ok:
                    messagebox.showerror("Date", "Date invalide. Utilise JJ/MM/AAAA.",
                                         parent=win)
                    return
                iso = ok.strftime("%Y-%m-%d")
            try:
                db.mon_stock_definir_peremption(pid, iso)
            except Exception as ex:
                messagebox.showerror("Date", f"Échec : {ex}", parent=win)
                return
            win.destroy()
            self._afficher_liste()

        barre = tk.Frame(win, bg=DARK_BG); barre.pack(fill="x", padx=16, pady=14)
        tk.Button(barre, text="Effacer la date", command=lambda: (var.set(""), enregistrer()),
                  font=("Helvetica", 9), bg=CARD_BG, fg=GOLD, bd=0, cursor="hand2",
                  padx=8, pady=6).pack(side="left")
        tk.Button(barre, text="Enregistrer", command=enregistrer,
                  font=("Helvetica", 10, "bold"), bg=SUCCESS, fg="white", bd=0,
                  cursor="hand2", padx=12, pady=6).pack(side="right")
        e.bind("<Return>", lambda ev: enregistrer())

    # ── Actions stock ────────────────────────────────────────────────────────
    def _retirer(self, pid, qte):
        try:
            retire = db.retirer_du_stock(pid, int(qte))
        except Exception as ex:
            messagebox.showerror("Retrait", f"Échec : {ex}", parent=self)
            return
        if retire <= 0:
            messagebox.showinfo("Retrait", "Plus de stock pour cet article.", parent=self)
        self._afficher_liste()

    def _annuler(self):
        try:
            res = db.annuler_dernier_retrait()
        except Exception as ex:
            messagebox.showerror("Annuler", f"Échec : {ex}", parent=self)
            return
        if res:
            nom, q = res
            self.statut.config(text=f"  Annulé : +{q} « {nom} » remis en stock")
        else:
            messagebox.showinfo("Annuler", "Aucun retrait à annuler.", parent=self)
        self._afficher_liste()

    def _ajouter_manuel(self):
        AjoutStockDialog(self, on_ajout=self._afficher_liste)

    def _tout_effacer(self):
        if not messagebox.askyesno(
                "Tout effacer",
                "Vider TOUT le stock ?\n\nTous les articles seront retirés de la "
                "liste. Cette action est irréversible.", parent=self):
            return
        try:
            db.mon_stock_vider()
        except Exception as ex:
            messagebox.showerror("Tout effacer", f"Échec : {ex}", parent=self)
            return
        self._afficher_liste()

    def _effacer_selection(self):
        EffacerStockDialog(self, on_fini=self._afficher_liste)

    def _exporter(self):
        import datetime as _dt
        nom_def = "mon_stock_" + _dt.date.today().strftime("%Y-%m-%d") + ".json"
        chemin = filedialog.asksaveasfilename(
            parent=self, title="Exporter le stock",
            defaultextension=".json", initialfile=nom_def,
            filetypes=[("Fichier stock", "*.json")])
        if not chemin:
            return
        try:
            n = db.exporter_mon_stock(chemin)
        except Exception as ex:
            messagebox.showerror("Exporter", f"Échec : {ex}", parent=self)
            return
        messagebox.showinfo("Exporter",
            f"{n} article(s) exporté(s).\n\nCopie ce fichier sur l'autre poste "
            "(clé USB) puis utilise « 📥 Importer ».", parent=self)

    def _importer(self):
        chemin = filedialog.askopenfilename(
            parent=self, title="Importer un stock",
            filetypes=[("Fichier stock", "*.json"), ("Tous", "*.*")])
        if not chemin:
            return
        rep = messagebox.askyesnocancel(
            "Importer le stock",
            "Oui  = REMPLACER le stock actuel par le fichier\n"
            "Non  = AJOUTER au stock actuel (cumuler les quantités)\n"
            "Annuler = ne rien faire", parent=self)
        if rep is None:
            return
        try:
            n = db.importer_mon_stock(chemin, remplacer=bool(rep))
        except Exception as ex:
            messagebox.showerror("Importer", f"Échec : {ex}", parent=self)
            return
        self._alertes_vues.clear()
        self._afficher_liste()
        messagebox.showinfo("Importer", f"{n} article(s) importé(s).", parent=self)

    def _toggle_rappel(self, pid, actif):
        try:
            db.definir_rappel(pid, actif)
        except Exception:
            pass
        # réinitialise les alertes pop-up pour refléter le changement
        self._alertes_vues.discard(pid)
        self._afficher_liste()

    def _popup_stock_bas(self, articles):
        win = tk.Toplevel(self)
        win.title("Stock bas")
        win.configure(bg=DARK_BG)
        win.attributes("-topmost", True)
        win.geometry("360x420")
        tk.Label(win, text="⚠ Bientôt en rupture", font=("Helvetica", 13, "bold"),
                 bg=DARK_BG, fg=DANGER).pack(pady=(12, 2))
        tk.Label(win, text="À racheter lors de ta prochaine cantine :",
                 font=("Helvetica", 9), bg=DARK_BG, fg=TEXT_MUTED).pack()
        # Zone défilante (barre déroulante) pour les listes longues
        cadre = tk.Frame(win, bg=DARK_BG); cadre.pack(fill="both", expand=True,
                                                      padx=12, pady=8)
        cv = tk.Canvas(cadre, bg=DARK_BG, highlightthickness=0)
        sb = tk.Scrollbar(cadre, orient="vertical", command=cv.yview)
        inner = tk.Frame(cv, bg=DARK_BG)
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        iw = cv.create_window((0, 0), window=inner, anchor="nw")
        cv.bind("<Configure>", lambda e: cv.itemconfig(iw, width=e.width))
        cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        cv.bind_all("<MouseWheel>",
                    lambda e: cv.yview_scroll(int(-e.delta / 120), "units"))
        for a in articles:
            tk.Label(inner, text=f"•  {a['nom']}  —  reste {a['qte']}",
                     font=("Helvetica", 10, "bold"), bg=DARK_BG, fg=TEXT,
                     anchor="w", wraplength=300, justify="left").pack(anchor="w", pady=1)
        tk.Button(win, text="OK", command=win.destroy, font=("Helvetica", 10, "bold"),
                  bg=ACCENT, fg="white", bd=0, cursor="hand2", padx=20, pady=6).pack(pady=8)

    # ── Réceptions des livraisons prévues ─────────────────────────────────────
    def _receptions_dues_filtrees(self):
        """Réceptions à traiter, SANS celles reportées (« plus tard ») cette
        session — pour ne jamais reboucler sur la même."""
        try:
            dues = db.get_receptions_dues()
        except Exception:
            dues = []
        return [d for d in dues if d["id"] not in self._reportes]

    def _maj_bouton_receptions(self):
        """Affiche/masque le bouton « 📦 Livraisons (N) » selon le nombre en
        attente."""
        try:
            n = len(self._receptions_dues_filtrees())
        except Exception:
            n = 0
        if not hasattr(self, "btn_recept"):
            return
        if n > 0:
            self.btn_recept.config(text=f"📦 Livraisons ({n})")
            if not self.btn_recept.winfo_ismapped():
                self.btn_recept.pack(side="left", padx=2, pady=6)
        else:
            if self.btn_recept.winfo_ismapped():
                self.btn_recept.pack_forget()

    def _auto_receptions(self):
        """Ouverture AUTOMATIQUE au plus une fois par jour. Ensuite, c'est au
        bouton « 📦 Livraisons » de les rouvrir à la demande."""
        self._maj_bouton_receptions()
        import datetime as _dt
        today = _dt.date.today().strftime("%Y-%m-%d")
        try:
            last = db.get_parametres().get("reception_auto_date", "")
        except Exception:
            last = ""
        if last == today:
            return                      # déjà proposé aujourd'hui
        dues = self._receptions_dues_filtrees()
        if not dues:
            return
        try:
            db.set_parametre("reception_auto_date", today)
        except Exception:
            pass
        self._ouvrir_reception(dues[0], manuel=False)

    def _ouvrir_receptions_manuel(self):
        """Bouton : ouvre les réceptions à la demande (enchaîne sur les
        suivantes au fur et à mesure)."""
        dues = self._receptions_dues_filtrees()
        if not dues:
            messagebox.showinfo("Livraisons",
                                "Aucune livraison à réceptionner pour le moment.",
                                parent=self)
            return
        self._ouvrir_reception(dues[0], manuel=True)

    def _ouvrir_reception(self, reception, manuel):
        if self._reception_ouverte:
            return
        self._reception_ouverte = True
        self._manuel_courant = manuel
        ReceptionDialog(self, reception, on_fini=self._reception_terminee)

    def _reception_terminee(self, reporte_id=None):
        """Appelé à la fermeture d'une réception.
        - reporte_id non None : « plus tard » → on l'ignore le reste de la
          session (plus de reboucle)."""
        self._reception_ouverte = False
        if reporte_id is not None:
            self._reportes.add(reporte_id)
        self._afficher_liste()
        self._maj_bouton_receptions()
        # En mode MANUEL seulement, on enchaîne sur la suivante non reportée.
        if self._manuel_courant:
            dues = self._receptions_dues_filtrees()
            if dues:
                self.after(200, lambda: self._ouvrir_reception(dues[0], manuel=True))

    def _voir_jour(self):
        import datetime as _dt
        jour = _dt.date.today().strftime("%Y-%m-%d")
        try:
            retr = db.get_retraits(jour=jour)
        except Exception as ex:
            messagebox.showerror("Aujourd'hui", f"Échec : {ex}", parent=self)
            return
        win = tk.Toplevel(self)
        win.title("Retraits du jour")
        win.configure(bg=DARK_BG)
        win.attributes("-topmost", True)
        win.geometry("360x420")
        tk.Label(win, text=f"📅 Retraits du {_dt.date.today().strftime('%d/%m/%Y')}",
                 font=("Helvetica", 12, "bold"), bg=DARK_BG, fg=TEXT).pack(pady=8)
        if not retr:
            tk.Label(win, text="Aucun retrait aujourd'hui.", bg=DARK_BG,
                     fg=TEXT_MUTED).pack(pady=10)
            return
        cadre = tk.Frame(win, bg=DARK_BG); cadre.pack(fill="both", expand=True, padx=10)
        total = 0.0
        for x in retr:
            h = x["date"][11:16]
            tk.Label(cadre, text=f"{h}  ×{x['quantite']}  {x['nom']}", bg=DARK_BG,
                     fg=TEXT, anchor="w", font=("Helvetica", 9),
                     wraplength=330, justify="left").pack(anchor="w")
            total += float(x["prix"] or 0) * int(x["quantite"])
        tk.Label(win, text=f"Total retiré : {total:.2f} €",
                 font=("Helvetica", 10, "bold"), bg=DARK_BG, fg=GOLD).pack(pady=8)

    # ── Cycle de vie ─────────────────────────────────────────────────────────
    def _planifier_refresh(self):
        # Rafraîchissement rare (12 h) : le widget ne clignote plus. Le bouton ⟳
        # force une mise à jour immédiate quand on en a besoin.
        self._apres_id = self.after(12 * 60 * 60 * 1000, self._tick)

    def _rafraichir_manuel(self):
        self._afficher_liste()
        self._maj_bouton_receptions()

    def _regler_seuil(self):
        """Réglage du seuil d'alerte « stock bas » (quand prévenir d'un rachat)."""
        try:
            actuel = int(db.get_parametres().get("stock_seuil_bas", "2") or 2)
        except Exception:
            actuel = 2
        n = simpledialog.askinteger(
            "Seuil d'alerte",
            "Me prévenir de racheter un produit quand il en reste :\n"
            "(ex. 2 = alerte quand il reste 2 ou moins)",
            parent=self, initialvalue=actuel, minvalue=0, maxvalue=99)
        if n is None:
            return
        try:
            db.set_parametre("stock_seuil_bas", str(n))
        except Exception:
            pass
        self.seuil = n
        self._afficher_liste()

    def _tick(self):
        self._afficher_liste()
        self._maj_bouton_receptions()
        self._planifier_refresh()

    def _fermer(self):
        try:
            db.set_parametre("widget_geometry", self.geometry())
        except Exception:
            pass
        for aid in (self._apres_id, self._bottom_id):
            if aid:
                try:
                    self.after_cancel(aid)
                except Exception:
                    pass
        self.destroy()


class AjoutStockDialog(tk.Toplevel):
    """Ajout manuel au stock : ce qu'on a déjà en cellule (choisi au catalogue)."""
    def __init__(self, parent, on_ajout=None):
        super().__init__(parent)
        self.on_ajout = on_ajout
        self.title("Ajouter au stock")
        self.configure(bg=DARK_BG)
        self.attributes("-topmost", True)
        self.geometry("380x460")
        try:
            self.produits = db.get_produits()   # (id,nom,categorie,prix,qte_max,actif,...)
        except Exception:
            self.produits = []

        tk.Label(self, text="➕ Ajouter ce que j'ai en cellule",
                 font=("Helvetica", 12, "bold"), bg=DARK_BG, fg=TEXT).pack(pady=(10, 4))
        tk.Label(self, text="Cherchez l'article, choisissez-le, puis la quantité.",
                 font=("Helvetica", 9), bg=DARK_BG, fg=TEXT_MUTED).pack()

        self.rech = tk.StringVar()
        self.rech.trace_add("write", lambda *_: self._filtrer())
        bar = tk.Frame(self, bg=DARK_BG); bar.pack(fill="x", padx=12, pady=8)
        tk.Label(bar, text="🔎", bg=DARK_BG, fg=TEXT_MUTED).pack(side="left")
        e = tk.Entry(bar, textvariable=self.rech, font=("Helvetica", 11),
                     bg=CARD_BG, fg=TEXT, bd=0, insertbackground=TEXT)
        e.pack(side="left", fill="x", expand=True, padx=6, ipady=4)
        e.focus_set()

        cadre = tk.Frame(self, bg=DARK_BG); cadre.pack(fill="both", expand=True, padx=12)
        self.lb = tk.Listbox(cadre, font=("Helvetica", 10), bg=CARD_BG, fg=TEXT,
                             bd=0, highlightthickness=0, activestyle="none",
                             selectbackground=ACCENT)
        sb = tk.Scrollbar(cadre, orient="vertical", command=self.lb.yview)
        self.lb.configure(yscrollcommand=sb.set)
        self.lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        bas = tk.Frame(self, bg=DARK_BG); bas.pack(fill="x", padx=12, pady=10)
        tk.Label(bas, text="Quantité :", bg=DARK_BG, fg=TEXT,
                 font=("Helvetica", 10)).pack(side="left")
        self.qte = tk.Spinbox(bas, from_=1, to=999, width=5, font=("Helvetica", 11),
                              bg=CARD_BG, fg=TEXT, bd=0, buttonbackground=CARD_BG,
                              insertbackground=TEXT, justify="center")
        self.qte.delete(0, "end"); self.qte.insert(0, "1")
        self.qte.pack(side="left", padx=8)
        tk.Button(bas, text="Ajouter au stock", command=self._valider,
                  font=("Helvetica", 10, "bold"), bg=SUCCESS, fg="white", bd=0,
                  cursor="hand2", padx=10, pady=6).pack(side="right")

        self._filtrer()
        self.lb.bind("<Double-Button-1>", lambda e: self._valider())

    def _filtrer(self):
        f = self.rech.get().strip().lower()
        self.lb.delete(0, "end")
        self._map = []
        for p in self.produits:
            pid, nom, cat, prix = p[0], p[1], p[2], p[3]
            if f and f not in str(nom).lower() and f not in str(pid).lower():
                continue
            self._map.append(p)
            self.lb.insert("end", f"{nom}   ({cat}) — {prix:.2f} €")
            if len(self._map) >= 400:
                break

    def _valider(self):
        sel = self.lb.curselection()
        if not sel:
            messagebox.showinfo("Ajouter", "Choisissez d'abord un article dans la liste.",
                                parent=self)
            return
        p = self._map[sel[0]]
        try:
            q = int(self.qte.get())
        except ValueError:
            q = 1
        if q <= 0:
            return
        try:
            db.mon_stock_ajouter([{"id": p[0], "nom": p[1], "categorie": p[2],
                                   "prix": float(p[3] or 0), "qte": q}])
        except Exception as ex:
            messagebox.showerror("Ajouter", f"Échec : {ex}", parent=self)
            return
        if self.on_ajout:
            self.on_ajout()
        # garde la fenêtre ouverte pour enchaîner les ajouts
        self.rech.set("")
        self.qte.delete(0, "end"); self.qte.insert(0, "1")


class ReceptionDialog(tk.Toplevel):
    """Demande de confirmation de réception d'une livraison prévue (cantine ou
    créance). Quantités reçues ajustables ; le non-livré est oublié ; possibilité
    de reporter (« pas encore livré »)."""
    def __init__(self, parent, reception, on_fini=None):
        super().__init__(parent)
        self.reception = reception
        self.on_fini = on_fini
        self.configure(bg=DARK_BG)
        self.attributes("-topmost", True)
        self.geometry("420x520")
        self.title("Réception de livraison")
        self.protocol("WM_DELETE_WINDOW", self._reporter)  # fermer = reporter

        typ = reception.get("type")
        cat = reception.get("categorie", "")
        pers = reception.get("personne", "")
        dprev = reception.get("date_prevue", "")
        try:
            import datetime as _dt
            dprev_fr = _dt.datetime.strptime(dprev, "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            dprev_fr = dprev

        if typ == "creance":
            titre = f"Créance de {pers}"
            sous = f"Créance ({cat}) prévue le {dprev_fr}"
            q = f"As-tu bien réceptionné la créance de {pers} ?"
            note = "Ce qui n'est pas reçu restera dû par le client et te sera redemandé."
        else:
            titre = f"Cantine {cat}"
            sous = f"Ta cantine {cat} prévue le {dprev_fr}"
            q = "As-tu bien été livré ?"
            note = "Ce qui n'est pas reçu sera oublié (non livré)."

        tk.Label(self, text="📦 Livraison prévue", font=("Helvetica", 13, "bold"),
                 bg=DARK_BG, fg=TEXT).pack(pady=(12, 0))
        tk.Label(self, text=titre, font=("Helvetica", 12, "bold"),
                 bg=DARK_BG, fg=GOLD).pack()
        tk.Label(self, text=sous, font=("Helvetica", 9), bg=DARK_BG,
                 fg=TEXT_MUTED).pack()
        tk.Label(self, text=q + "  Ajuste les quantités réellement reçues :",
                 font=("Helvetica", 9), bg=DARK_BG, fg=TEXT_MUTED,
                 wraplength=380, justify="center").pack(pady=(6, 1))
        tk.Label(self, text=note, font=("Helvetica", 8, "italic"), bg=DARK_BG,
                 fg=GOLD, wraplength=380, justify="center").pack(pady=(0, 4))

        cadre = tk.Frame(self, bg=DARK_BG); cadre.pack(fill="both", expand=True, padx=12)
        cv = tk.Canvas(cadre, bg=DARK_BG, highlightthickness=0)
        sb = tk.Scrollbar(cadre, orient="vertical", command=cv.yview)
        inner = tk.Frame(cv, bg=DARK_BG)
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        w = cv.create_window((0, 0), window=inner, anchor="nw")
        cv.bind("<Configure>", lambda e: cv.itemconfig(w, width=e.width))
        cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.spins = {}
        for l in reception["lignes"]:
            row = tk.Frame(inner, bg=CARD_BG); row.pack(fill="x", pady=2)
            tk.Label(row, text=f"{l['nom']}", font=("Helvetica", 10, "bold"),
                     bg=CARD_BG, fg=TEXT, anchor="w", wraplength=230,
                     justify="left").pack(side="left", fill="x", expand=True,
                                          padx=(8, 4), pady=6)
            tk.Label(row, text=f"prévu {l['qte_attendue']}", font=("Helvetica", 9),
                     bg=CARD_BG, fg=TEXT_MUTED).pack(side="left", padx=4)
            sp = tk.Spinbox(row, from_=0, to=int(l['qte_attendue']), width=4,
                            font=("Helvetica", 10), bg=DARK_BG, fg=TEXT, bd=0,
                            buttonbackground=CARD_BG, insertbackground=TEXT,
                            justify="center")
            sp.delete(0, "end"); sp.insert(0, str(int(l['qte_attendue'])))
            sp.pack(side="right", padx=8)
            self.spins[l["ligne_id"]] = sp

        btns = tk.Frame(self, bg=DARK_BG); btns.pack(fill="x", padx=12, pady=10)
        tk.Button(btns, text="⏳ Pas encore livré", command=self._reporter,
                  font=("Helvetica", 9), bg=CARD_BG, fg=GOLD, bd=0,
                  cursor="hand2", padx=8, pady=6).pack(side="left")
        tk.Button(btns, text="Valider la réception", command=self._valider,
                  font=("Helvetica", 10, "bold"), bg=SUCCESS, fg="white", bd=0,
                  cursor="hand2", padx=10, pady=6).pack(side="right")
        tk.Button(btns, text="✅ Tout reçu", command=self._tout_recu,
                  font=("Helvetica", 9, "bold"), bg=ACCENT, fg="white", bd=0,
                  cursor="hand2", padx=8, pady=6).pack(side="right", padx=6)

    def _tout_recu(self):
        for l in self.reception["lignes"]:
            sp = self.spins[l["ligne_id"]]
            sp.delete(0, "end"); sp.insert(0, str(int(l["qte_attendue"])))
        self._valider()

    def _valider(self):
        recu = {}
        for lid, sp in self.spins.items():
            try:
                recu[lid] = int(sp.get())
            except ValueError:
                recu[lid] = 0
        try:
            db.confirmer_reception(self.reception["id"], recu)
        except Exception as ex:
            messagebox.showerror("Réception", f"Échec : {ex}", parent=self)
            return
        self._fini(None)                # validée : plus à redemander

    def _reporter(self):
        # « Pas encore livré » : on la reporte. Elle reste en attente en base
        # mais n'est PLUS redemandée automatiquement cette session (fini la
        # boucle) ; elle réapparaîtra au prochain démarrage du widget.
        self._fini(self.reception["id"])

    def _fini(self, reporte_id):
        cb = self.on_fini
        self.destroy()
        if cb:
            try:
                cb(reporte_id)
            except TypeError:
                cb()                    # compat ancienne signature


class EffacerStockDialog(tk.Toplevel):
    """Cocher les articles à EFFACER de la liste (suppression, pas un retrait)."""
    def __init__(self, parent, on_fini=None):
        super().__init__(parent)
        self.on_fini = on_fini
        self.title("Effacer des articles")
        self.configure(bg=DARK_BG)
        self.attributes("-topmost", True)
        self.geometry("380x500")
        try:
            self.articles = db.mon_stock_get()
        except Exception:
            self.articles = []

        tk.Label(self, text="✖ Effacer des articles de la liste",
                 font=("Helvetica", 12, "bold"), bg=DARK_BG, fg=TEXT).pack(pady=(10, 2))
        tk.Label(self, text="Coche les articles à retirer complètement de ton stock.",
                 font=("Helvetica", 9), bg=DARK_BG, fg=TEXT_MUTED,
                 wraplength=340, justify="center").pack(pady=(0, 6))

        if not self.articles:
            tk.Label(self, text="Le stock est vide.", bg=DARK_BG, fg=TEXT_MUTED,
                     font=("Helvetica", 11)).pack(pady=30)
            return

        cadre = tk.Frame(self, bg=DARK_BG); cadre.pack(fill="both", expand=True, padx=12)
        cv = tk.Canvas(cadre, bg=DARK_BG, highlightthickness=0)
        sb = tk.Scrollbar(cadre, orient="vertical", command=cv.yview)
        inner = tk.Frame(cv, bg=DARK_BG)
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        iw = cv.create_window((0, 0), window=inner, anchor="nw")
        cv.bind("<Configure>", lambda e: cv.itemconfig(iw, width=e.width))
        cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        cv.bind_all("<MouseWheel>", lambda e: cv.yview_scroll(int(-e.delta / 120), "units"))

        self.vars = []
        for a in sorted(self.articles, key=lambda x: (x.get("categorie", ""), x.get("nom", ""))):
            row = tk.Frame(inner, bg=CARD_BG); row.pack(fill="x", pady=2)
            v = tk.BooleanVar(value=False)
            tk.Checkbutton(row, variable=v, bg=CARD_BG, activebackground=CARD_BG,
                           selectcolor=DARK_BG, bd=0, highlightthickness=0).pack(side="left", padx=4)
            tk.Label(row, text=f"{a['nom']}  (x{a['qte']})", font=("Helvetica", 10),
                     bg=CARD_BG, fg=TEXT, anchor="w", wraplength=280,
                     justify="left").pack(side="left", fill="x", expand=True, pady=6)
            self.vars.append((v, a["id"], a["nom"]))

        barre = tk.Frame(self, bg=DARK_BG); barre.pack(fill="x", padx=12, pady=10)
        tk.Button(barre, text="Annuler", command=self.destroy, font=("Helvetica", 9),
                  bg=CARD_BG, fg=TEXT, bd=0, cursor="hand2", padx=10, pady=6).pack(side="left")
        tk.Button(barre, text="✖ Effacer la sélection", command=self._valider,
                  font=("Helvetica", 10, "bold"), bg=DANGER, fg="white", bd=0,
                  cursor="hand2", padx=10, pady=6).pack(side="right")

    def _valider(self):
        sel = [(pid, nom) for v, pid, nom in self.vars if v.get()]
        if not sel:
            messagebox.showinfo("Effacer", "Coche au moins un article.", parent=self)
            return
        if not messagebox.askyesno("Effacer",
                f"Effacer {len(sel)} article(s) de la liste ?", parent=self):
            return
        try:
            for pid, _ in sel:
                db.mon_stock_modifier_qte(pid, 0)   # 0 -> supprime la ligne
        except Exception as ex:
            messagebox.showerror("Effacer", f"Échec : {ex}", parent=self)
            return
        if self.on_fini:
            self.on_fini()
        self.destroy()


def main():
    try:
        db.init_db()
    except Exception:
        pass
    StockWidget().mainloop()


if __name__ == "__main__":
    main()
