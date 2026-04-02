import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import os, sys, subprocess, platform, shutil
from datetime import datetime
import database as db
import impression

# ─────────────────────────────────────────────
# THEME
# ─────────────────────────────────────────────
DARK_BG    = "#1a1f2e"
PANEL_BG   = "#232838"
CARD_BG    = "#2d3347"
ACCENT     = "#2563eb"
ACCENT_HOV = "#1d4ed8"
SUCCESS    = "#16a34a"
DANGER     = "#dc2626"
TEXT       = "#f1f5f9"
TEXT_MUTED = "#94a3b8"
BORDER     = "#374151"
HEADER_BG  = "#003366"
GOLD       = "#f59e0b"

CATEGORIES = [
    ("Patisserie",     "🥐", "#c2410c"),
    ("Tabac",          "🚬", "#4b5563"),
    ("Accidentelle",   "🏠", "#7c3aed"),
    ("Hygiène",        "🧴", "#0891b2"),
    ("Hallal",         "🥩", "#059669"),
    ("Alimentaire",    "🛒", "#d97706"),
    ("Fruits & Légumes","🍎","#16a34a"),
    ("Boissons",       "🥤", "#2563eb"),
]

def _app_dir():
    """Dossier données utilisateur — fonctionne en .py ET en .exe PyInstaller."""
    if getattr(sys, "frozen", False):
        base = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "CantineApp")
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(base, exist_ok=True)
    return base

APP_DIR = _app_dir()

def _open_file(path):
    try:
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])
    except:
        messagebox.showinfo("PDF généré", f"Fichier : {path}")


# ─────────────────────────────────────────────
# LOGIN — écran de choix
# ─────────────────────────────────────────────
class LoginWindow(tk.Tk):
    """Écran de bienvenue avec 2 boutons stables : Yoann / Invité."""
    def __init__(self):
        super().__init__()
        self.title("Gestion Cantine")
        self.configure(bg=DARK_BG)
        self.resizable(False, False)
        self.user_type = None
        self.user_info = {}
        self.geometry("500x520")
        self._center()
        self._build()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - self.winfo_width())  // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build(self):
        tk.Frame(self, bg=HEADER_BG, height=6).pack(fill="x")
        body = tk.Frame(self, bg=DARK_BG)
        body.pack(fill="both", expand=True, padx=40, pady=24)

        tk.Label(body, text="🏛️", font=("Segoe UI Emoji", 48),
                 bg=DARK_BG, fg=TEXT).pack()
        tk.Label(body, text="GESTION DE CANTINE",
                 font=("Helvetica", 17, "bold"), bg=DARK_BG, fg=TEXT).pack(pady=(4, 2))
        tk.Label(body, text="Choisissez votre profil pour continuer",
                 font=("Helvetica", 10), bg=DARK_BG, fg=TEXT_MUTED).pack(pady=(0, 22))

        params  = db.get_parametres()
        nom_aff = f"{params.get('nom','LUTZ')} {params.get('prenom','Yoann')}"
        info_y  = (f"Écrou {params.get('ecrou','9283')}  •  "
                   f"Bât. {params.get('batiment','C')}  •  "
                   f"Cell. {params.get('cellule','323')}")

        self._make_card(body,
            accent=GOLD, title="👤  "+nom_aff, subtitle=info_y,
            note="Accès complet  •  signature activée",
            title_fg=GOLD, hover_bg="#1e3a6e", command=self._login_yoann)

        self._make_card(body,
            accent="#6366f1", title="👥  Invité",
            subtitle="Saisie manuelle des informations",
            note="Accès commandes  •  sans signature",
            title_fg="#a5b4fc", hover_bg="#3730a3", command=self._login_invite)

        tk.Label(body, text="v2.0", font=("Helvetica", 8),
                 bg=DARK_BG, fg="#374151").pack(pady=(16, 0))

    def _make_card(self, parent, accent, title, subtitle, note,
                   title_fg, hover_bg, command):
        outer = tk.Frame(parent, bg=accent)
        outer.pack(fill="x", pady=6)
        tk.Frame(outer, bg=accent, height=4).pack(fill="x")
        inner = tk.Frame(outer, bg=CARD_BG)
        inner.pack(fill="x")

        lbl1 = tk.Label(inner, text=title,
                 font=("Helvetica", 12, "bold"),
                 bg=CARD_BG, fg=title_fg, anchor="w", padx=20, pady=0)
        lbl1.pack(fill="x", pady=(10,2))
        lbl2 = tk.Label(inner, text=subtitle,
                 font=("Helvetica", 9), bg=CARD_BG, fg=TEXT_MUTED, anchor="w", padx=20)
        lbl2.pack(fill="x")
        lbl3 = tk.Label(inner, text=note,
                 font=("Helvetica", 9, "italic"),
                 bg=CARD_BG, fg=TEXT_MUTED, anchor="w", padx=20)
        lbl3.pack(fill="x", pady=(2,10))

        all_widgets = [inner, lbl1, lbl2, lbl3]

        def _in(e):
            for w in all_widgets:
                try: w.config(bg=hover_bg)
                except: pass
        def _out(e):
            for w in all_widgets:
                try: w.config(bg=CARD_BG)
                except: pass
        for w in all_widgets:
            w.bind("<Enter>", _in)
            w.bind("<Leave>", _out)
            w.bind("<Button-1>", lambda e, cmd=command: cmd())
            w.config(cursor="hand2")

    def _demander_budget(self):
        """Demande le budget hebdomadaire si pas encore fait cette semaine."""
        if db.get_budget_demande():
            return  # déjà demandé cette semaine
        budget, _ = db.get_budget_semaine()
        win = BudgetWindow(self, budget)
        win.grab_set()
        self.wait_window(win)

    def _login_yoann(self):
        mdp = simpledialog.askstring("Connexion Yoann", "Mot de passe :",
                                     show="•", parent=self)
        if mdp is None:
            return
        role = db.verifier_utilisateur("yoann", mdp)
        if not role:
            messagebox.showerror("Erreur", "Mot de passe incorrect.", parent=self)
            return
        params = db.get_parametres()
        self.user_type = "yoann"
        self.user_info = {
            "nom":      params.get("nom","LUTZ"),
            "prenom":   params.get("prenom","Yoann"),
            "ecrou":    params.get("ecrou","9283"),
            "batiment": params.get("batiment","C"),
            "cellule":  params.get("cellule","323"),
        }
        self._demander_budget()
        self.destroy()

    def _login_invite(self):
        win = InviteInfoWindow(self)
        win.grab_set()
        self.wait_window(win)
        if win.result:
            self.user_type = "invite"
            self.user_info = win.result
            self._demander_budget()
            self.destroy()


class InviteInfoWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.result = None
        self.title("Informations Invité")
        self.configure(bg=DARK_BG)
        self.resizable(False, False)
        self.geometry("400x380")
        self._center()
        self._build()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - self.winfo_width())  // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build(self):
        bar = tk.Frame(self, bg="#6366f1", height=6)
        bar.pack(fill="x")
        hdr = tk.Frame(self, bg=HEADER_BG, height=46)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="👥  Identification Invité",
                 font=("Helvetica",12,"bold"), bg=HEADER_BG, fg="white").pack(side="left", padx=14, pady=10)

        frm = tk.Frame(self, bg=DARK_BG, padx=30, pady=20)
        frm.pack(fill="both", expand=True)

        fields = [
            ("Nom",       "nom",      ""),
            ("Prénom",    "prenom",   ""),
            ("Écrou",     "ecrou",    ""),
            ("Bâtiment",  "batiment", ""),
            ("Cellule",   "cellule",  ""),
        ]
        self.vars = {}
        for label, key, default in fields:
            row = tk.Frame(frm, bg=DARK_BG)
            row.pack(fill="x", pady=5)
            tk.Label(row, text=label+" :", width=12, anchor="e",
                     font=("Helvetica",10), bg=DARK_BG, fg=TEXT_MUTED).pack(side="left", padx=(0,8))
            v = tk.StringVar(value=default)
            self.vars[key] = v
            e = tk.Entry(row, textvariable=v, font=("Helvetica",11),
                         bg=CARD_BG, fg=TEXT, insertbackground=TEXT, bd=0,
                         relief="flat", highlightthickness=1,
                         highlightbackground=BORDER, highlightcolor=ACCENT)
            e.pack(side="left", fill="x", expand=True, ipady=7)

        tk.Button(frm, text="✓  Accéder à la cantine",
                  command=self._valider,
                  font=("Helvetica",11,"bold"), bg="#6366f1", fg="white",
                  bd=0, cursor="hand2", pady=9,
                  activebackground="#4f46e5", activeforeground="white").pack(fill="x", pady=(14,0))

        # Focus on first field
        self.after(100, lambda: list(frm.winfo_children())[0].winfo_children()[-1].focus())

    def _valider(self):
        for key, var in self.vars.items():
            if not var.get().strip():
                messagebox.showwarning("Champ manquant",
                    f"Veuillez renseigner le champ « {key} ».", parent=self)
                return
        self.result = {k: v.get().strip() for k, v in self.vars.items()}
        self.destroy()


# ─────────────────────────────────────────────
# FENÊTRE BUDGET HEBDOMADAIRE
# ─────────────────────────────────────────────
class BudgetWindow(tk.Toplevel):
    """Fenetre budget hebdomadaire : definir, modifier, supprimer."""
    def __init__(self, master, budget_actuel=0):
        super().__init__(master)
        self.title("Budget de la semaine")
        self.configure(bg=DARK_BG)
        self.resizable(False, False)
        self.geometry("420x340")
        self._center()
        self._build(budget_actuel)

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - self.winfo_width())  // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build(self, budget_actuel):
        from datetime import datetime, timedelta
        today   = datetime.now()
        lundi   = today - timedelta(days=today.weekday())
        dim     = lundi + timedelta(days=6)
        periode = f"{lundi.strftime('%d/%m')} — {dim.strftime('%d/%m/%Y')}"

        tk.Frame(self, bg=GOLD, height=4).pack(fill="x")
        hdr = tk.Frame(self, bg=HEADER_BG, height=48)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="💰  Budget de la semaine",
                 font=("Helvetica",13,"bold"), bg=HEADER_BG, fg="white").pack(side="left", padx=16, pady=10)

        body = tk.Frame(self, bg=DARK_BG, padx=30, pady=16)
        body.pack(fill="both", expand=True)

        tk.Label(body, text=f"Semaine du {periode}",
                 font=("Helvetica",10), bg=DARK_BG, fg=TEXT_MUTED).pack(pady=(0,10))

        # Budget actuel affiché
        if budget_actuel > 0:
            _, dep = db.get_budget_semaine()
            tk.Label(body,
                     text=f"Budget actuel : {budget_actuel:.2f} €  |  Dépensé : {dep:.2f} €",
                     font=("Helvetica",10,"bold"), bg=DARK_BG, fg=GOLD).pack(pady=(0,8))

        tk.Label(body, text="Nouveau budget (€) :",
                 font=("Helvetica",11,"bold"), bg=DARK_BG, fg=TEXT).pack()

        frm = tk.Frame(body, bg=DARK_BG)
        frm.pack(pady=10)
        self.budget_var = tk.StringVar(value=f"{budget_actuel:.2f}" if budget_actuel else "")
        e = tk.Entry(frm, textvariable=self.budget_var, width=10,
                     font=("Helvetica",14,"bold"), bg=CARD_BG, fg=GOLD,
                     insertbackground=GOLD, bd=0, relief="flat",
                     highlightthickness=2, highlightbackground=ACCENT,
                     justify="center")
        e.pack(ipady=6)
        e.focus_set()
        e.bind("<Return>", lambda ev: self._valider())

        tk.Button(body, text="✓  Valider le budget",
                  command=self._valider,
                  font=("Helvetica",12,"bold"), bg=GOLD, fg="#000",
                  bd=0, cursor="hand2", pady=9,
                  activebackground="#d97706").pack(fill="x", pady=(8,4))

        tk.Button(body, text="🗑️  Supprimer le budget",
                  command=self._supprimer,
                  font=("Helvetica",10), bg=DANGER, fg="white",
                  bd=0, cursor="hand2", pady=7,
                  activebackground="#b91c1c").pack(fill="x", pady=2)

        tk.Button(body, text="Fermer sans modifier",
                  command=self.destroy,
                  font=("Helvetica",9), bg=DARK_BG, fg=TEXT_MUTED,
                  bd=0, cursor="hand2").pack(pady=(6,0))

    def _valider(self):
        try:
            montant = float(self.budget_var.get().replace(",","."))
            if montant <= 0:
                raise ValueError
        except Exception:
            messagebox.showwarning("Valeur invalide",
                "Entrez un montant valide (ex: 50.00)", parent=self)
            return
        db.set_budget_semaine(montant)
        db.marquer_budget_demande()
        # Reset alertes seuil
        db.set_parametre("alerte_budget_25", "0")
        db.set_parametre("alerte_budget_5",  "0")
        self.destroy()

    def _supprimer(self):
        if messagebox.askyesno("Confirmer",
                "Supprimer le budget de la semaine ?", parent=self):
            db.set_budget_semaine(0)
            db.set_parametre("budget_semaine_lundi", "")
            db.set_parametre("alerte_budget_25", "0")
            db.set_parametre("alerte_budget_5",  "0")
            messagebox.showinfo("Supprime", "Budget supprime.", parent=self)
            self.destroy()

    def _passer(self):
        db.marquer_budget_demande()
        self.destroy()


# ─────────────────────────────────────────────
# APPLICATION PRINCIPALE
# ─────────────────────────────────────────────
class CantineApp(tk.Tk):
    def __init__(self, user_type, user_info):
        super().__init__()
        self.user_type = user_type          # "yoann" | "invite"
        self.user_info = user_info          # dict
        self.title("Gestion Cantine")
        self.configure(bg=DARK_BG)
        self.state("zoomed")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build()

    def _on_close(self):
        if messagebox.askyesno("Quitter", "Voulez-vous quitter ?", parent=self):
            self.destroy()

    def _modifier_budget(self):
        """Ouvre la fenêtre pour modifier le budget de la semaine."""
        budget, _ = db.get_budget_semaine()
        win = BudgetWindow(self, budget)
        win.grab_set()
        self.wait_window(win)
        self._update_budget_lbl()

    def _update_budget_lbl(self):
        """Met a jour l'affichage budget et declenche les alertes seuil."""
        try:
            budget, depense = db.get_budget_semaine()
            if budget > 0:
                restant = budget - depense
                couleur = GOLD if restant > 25 else ("#f97316" if restant > 5 else DANGER)
                self.budget_lbl.config(
                    text=f"💰 Semaine : {depense:.2f}€ / {budget:.2f}€  (reste {restant:.2f}€)",
                    fg=couleur)
                # Alertes seuil — on ne les affiche qu'une seule fois par seuil
                self._check_alerte_budget(restant, budget)
            else:
                self.budget_lbl.config(text="💰 Aucun budget defini")
        except Exception:
            pass

    def _check_alerte_budget(self, restant, budget):
        """Alerte a 25€ restants puis a 5€ restants."""
        params = db.get_parametres()
        alerte25 = params.get("alerte_budget_25", "0")
        alerte5  = params.get("alerte_budget_5",  "0")

        if restant <= 5 and alerte5 != "1":
            db.set_parametre("alerte_budget_5",  "1")
            db.set_parametre("alerte_budget_25", "1")
            messagebox.showwarning(
                "⚠️  Budget presque epuise !",
                f"Attention ! Il ne vous reste plus que {restant:.2f} € pour la semaine.",
                parent=self)
        elif restant <= 25 and alerte25 != "1":
            db.set_parametre("alerte_budget_25", "1")
            messagebox.showwarning(
                "⚠️  Budget bientot atteint",
                f"Il ne vous reste plus que {restant:.2f} € sur votre budget de {budget:.2f} €.",
                parent=self)

    # ── info badge couleur selon profil ───────
    def _badge_color(self):
        return GOLD if self.user_type == "yoann" else "#a5b4fc"

    def _build(self):
        # Barre supérieure
        bar = tk.Frame(self, bg=HEADER_BG, height=52)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        tk.Label(bar, text="🏛️  GESTION DE CANTINE",
                 font=("Helvetica",14,"bold"), bg=HEADER_BG, fg="white").pack(side="left", padx=20)

        right = tk.Frame(bar, bg=HEADER_BG)
        right.pack(side="right", padx=10)

        # Infos utilisateur
        ui = self.user_info
        badge = "👤" if self.user_type == "yoann" else "👥"
        info = f"{badge}  {ui.get('nom','').upper()} {ui.get('prenom','')}  |  Écrou: {ui.get('ecrou','')}  |  Bât. {ui.get('batiment','')} / Cell. {ui.get('cellule','')}"
        tk.Label(bar, text=info, font=("Helvetica",9),
                 bg=HEADER_BG, fg=self._badge_color()).pack(side="left", padx=16)

        # Bandeau budget
        self.budget_lbl = tk.Label(bar, text="",
                 font=("Helvetica",9,"bold"), bg=HEADER_BG, fg=GOLD)
        self.budget_lbl.pack(side="right", padx=16)
        self._update_budget_lbl()

        # Boutons header
        def hbtn(parent, text, cmd, bg=HEADER_BG, fg="white"):
            b = tk.Button(parent, text=text, command=cmd,
                          font=("Helvetica",9), bg=bg, fg=fg,
                          bd=0, relief="flat", cursor="hand2",
                          activebackground=ACCENT, activeforeground="white",
                          pady=4, padx=8)
            b.pack(side="left", padx=2)
            return b

        if self.user_type == "yoann":
            hbtn(right, "✍️ Signature", self._gerer_signature)
            hbtn(right, "⚙️ Paramètres", self._ouvrir_parametres)
            hbtn(right, "📋 Catalogue", self._ouvrir_catalogue)
            hbtn(right, "🔑 MDP", self._changer_mdp)

        hbtn(right, "💰 Budget", self._modifier_budget)
        hbtn(right, "📁 Historique", self._ouvrir_historique)
        hbtn(right, "🖨️ Tout imprimer", self._imprimer_tous_bons, bg="#7c3aed", fg="white")
        hbtn(right, "⏻ Quitter", self._on_close, bg=DANGER, fg="white")

        # Contenu
        self.content = tk.Frame(self, bg=DARK_BG)
        self.content.pack(fill="both", expand=True, padx=20, pady=20)
        self._show_menu()

    def _clear_content(self):
        for w in self.content.winfo_children():
            w.destroy()

    def _show_menu(self):
        self._clear_content()
        ui = self.user_info
        name = f"{ui.get('prenom','')} {ui.get('nom','').upper()}"
        greet = f"Bonjour {name} 👋" if self.user_type == "yoann" else f"Bienvenue, {name}"
        tk.Label(self.content, text=greet,
                 font=("Helvetica",18,"bold"), bg=DARK_BG,
                 fg=self._badge_color()).pack(pady=(0,4))
        tk.Label(self.content,
                 text="Sélectionnez une catégorie pour créer un bon de commande",
                 font=("Helvetica",10), bg=DARK_BG, fg=TEXT_MUTED).pack(pady=(0,18))

        grid = tk.Frame(self.content, bg=DARK_BG)
        grid.pack(anchor="center")
        for i, (cat, icon, color) in enumerate(CATEGORIES):
            self._cat_button(grid, cat, icon, color, i // 4, i % 4)

    def _cat_button(self, parent, cat, icon, color, r, c):
        """Bouton catégorie stable — tk.Button natif avec frame décorative."""
        cell = tk.Frame(parent, bg=DARK_BG)
        cell.grid(row=r, column=c, padx=8, pady=8)

        # Bande couleur en haut
        tk.Frame(cell, bg=color, height=4, width=175).pack(fill="x")

        # Bouton principal — stable, pas de hover frame
        btn = tk.Button(
            cell,
            text=f"{icon}\n{cat}",
            font=("Helvetica", 10, "bold"),
            fg=TEXT,
            bg=CARD_BG,
            activebackground=ACCENT,
            activeforeground="white",
            bd=0,
            relief="flat",
            cursor="hand2",
            width=17,
            height=5,
            wraplength=165,
            justify="center",
            command=lambda c=cat: self._ouvrir_commande(c),
        )
        btn.pack()

    # ── Ouvrir commande ───────────────────────
    def _ouvrir_commande(self, categorie):
        sig_path = None
        if self.user_type == "yoann":
            params = db.get_parametres()
            sig_path = params.get("signature_path", "")
            if sig_path and not os.path.isfile(sig_path):
                sig_path = None
        win = CommandeWindow(self, categorie, self.user_info,
                             self.user_type, sig_path)
        win.grab_set()

    # ── Signature ────────────────────────────
    def _gerer_signature(self):
        win = SignatureWindow(self)
        win.grab_set()

    # ── Paramètres ───────────────────────────
    def _ouvrir_parametres(self):
        win = ParametresWindow(self)
        win.grab_set()

    # ── Catalogue ────────────────────────────
    def _ouvrir_catalogue(self):
        win = CatalogueWindow(self)
        win.grab_set()

    # ── Historique ───────────────────────────
    def _ouvrir_historique(self):
        win = HistoriqueWindow(self, self.user_type, self.user_info)
        win.grab_set()

    # ── Imprimer tous les bons du jour ───────
    def _imprimer_tous_bons(self):
        today = datetime.now().strftime("%d/%m/%Y")
        bons  = db.get_historique_bons(200)
        bons_today = [b for b in bons if b[1] == today]
        if not bons_today:
            messagebox.showinfo("Aucun bon",
                f"Aucun bon enregistré aujourd'hui ({today}).\n"
                "Créez d'abord des bons via les catégories.", parent=self)
            return
        params   = db.get_parametres()
        sig_path = params.get("signature_path","") or None
        if sig_path and not os.path.isfile(sig_path): sig_path = None
        pdf_dir  = os.path.join(APP_DIR, "bons_pdf")
        os.makedirs(pdf_dir, exist_ok=True)
        pdfs, errors = [], []
        for bon in bons_today:
            bid, date, cat, nom, prenom, ecrou, bat, cell, total, *rest = bon
            utype    = rest[0] if rest else "invite"
            lig_raw  = db.get_lignes_bon(bid)
            lignes   = [{"id":l[2],"nom":l[3],"prix":l[4],"qte":l[5],"total":l[6],"qte_max":0}
                        for l in lig_raw]
            sp       = sig_path if utype == "yoann" else None
            pdf_path = os.path.join(pdf_dir, f"bon_{bid}_{cat}.pdf")
            try:
                impression.generer_bon_pdf(cat, nom, prenom, ecrou, bat, cell,
                                           lignes, total, date, pdf_path,
                                           signature_path=sp)
                pdfs.append(pdf_path)
            except Exception as ex:
                errors.append(str(ex))
        for p in pdfs:
            _open_file(p)
        msg = f"✅ {len(pdfs)} bon(s) ouvert(s) !"
        if errors:
            msg += f"\n⚠️ {len(errors)} erreur(s)"
        messagebox.showinfo("Impression terminée", msg, parent=self)

    # ── Changer MDP ──────────────────────────
    def _changer_mdp(self):
        mdp = simpledialog.askstring("Nouveau mot de passe",
                                     "Entrez le nouveau mot de passe :",
                                     show="•", parent=self)
        if mdp:
            db.changer_mot_de_passe("yoann", mdp)
            messagebox.showinfo("Succès", "Mot de passe modifié.", parent=self)


# ─────────────────────────────────────────────
# GESTION SIGNATURE
# ─────────────────────────────────────────────
class SignatureWindow(tk.Toplevel):
    """Import d'une image de signature (PNG/JPG) avec aperçu."""
    def __init__(self, master):
        super().__init__(master)
        self.title("Ma Signature")
        self.configure(bg=DARK_BG)
        self.resizable(False, False)
        self.geometry("520x520")
        self._center()
        self._build()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - self.winfo_width())  // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build(self):
        # Header
        bar = tk.Frame(self, bg=HEADER_BG, height=52)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Label(bar, text="✍️  Ma Signature",
                 font=("Helvetica",13,"bold"), bg=HEADER_BG, fg="white").pack(side="left", padx=16, pady=10)

        params = db.get_parametres()
        self.import_path = tk.StringVar(value=params.get("signature_path", ""))

        body = tk.Frame(self, bg=DARK_BG, padx=30, pady=20)
        body.pack(fill="both", expand=True)

        # Zone aperçu
        tk.Label(body, text="Aperçu :", font=("Helvetica",10,"bold"),
                 bg=DARK_BG, fg=TEXT_MUTED, anchor="w").pack(fill="x")

        preview_frm = tk.Frame(body, bg=CARD_BG, bd=1, relief="solid",
                               highlightthickness=1, highlightbackground=BORDER)
        preview_frm.pack(fill="x", pady=(6,16))
        self.preview_lbl = tk.Label(preview_frm, bg=CARD_BG,
                                    text="Aucune signature importée",
                                    font=("Helvetica",10), fg=TEXT_MUTED,
                                    height=5)
        self.preview_lbl.pack(fill="x", padx=10, pady=10)
        self._update_preview()

        # Bouton importer
        tk.Button(body, text="📁   Choisir une image de signature…",
                  command=self._choisir_image,
                  font=("Helvetica",11,"bold"), bg=ACCENT, fg="white", bd=0,
                  cursor="hand2", pady=10,
                  activebackground=ACCENT_HOV).pack(fill="x")

        tk.Label(body,
                 text="Formats acceptés : PNG, JPG, JPEG  •  Fond blanc ou transparent recommandé",
                 font=("Helvetica",8), bg=DARK_BG, fg=TEXT_MUTED,
                 justify="center").pack(pady=(8,0))

        # Bouton supprimer (conditionnel)
        self.del_btn = tk.Button(body, text="🗑️  Supprimer la signature",
                                 command=self._supprimer,
                                 font=("Helvetica",9), bg="#374151", fg=TEXT, bd=0,
                                 cursor="hand2", pady=6,
                                 activebackground=DANGER, activeforeground="white")
        if self.import_path.get() and os.path.isfile(self.import_path.get()):
            self.del_btn.pack(fill="x", pady=(8,0))

        # ── Taille de la signature ───────────────────────────────────────────
        params = db.get_parametres()
        taille_actuelle = float(params.get("signature_taille", "8.0"))

        sz_frm = tk.Frame(body, bg=DARK_BG)
        sz_frm.pack(fill="x", pady=(10,0))
        tk.Label(sz_frm, text="Taille sur le bon :",
                 font=("Helvetica",10,"bold"), bg=DARK_BG, fg=TEXT, anchor="w").pack(fill="x")

        slider_frm = tk.Frame(sz_frm, bg=DARK_BG)
        slider_frm.pack(fill="x", pady=4)
        tk.Label(slider_frm, text="Petite", font=("Helvetica",8),
                 bg=DARK_BG, fg=TEXT_MUTED).pack(side="left")

        self.sig_taille_var = tk.DoubleVar(value=taille_actuelle)
        slider = tk.Scale(slider_frm, from_=3.0, to=15.0,
                          resolution=0.5, orient="horizontal",
                          variable=self.sig_taille_var,
                          bg=DARK_BG, fg=TEXT, troughcolor=CARD_BG,
                          highlightthickness=0, length=260,
                          command=self._update_taille)
        slider.pack(side="left", padx=6)
        tk.Label(slider_frm, text="Grande", font=("Helvetica",8),
                 bg=DARK_BG, fg=TEXT_MUTED).pack(side="left")

        self.taille_lbl = tk.Label(sz_frm,
                 text=f"Largeur actuelle : {taille_actuelle:.1f} cm",
                 font=("Helvetica",9), bg=DARK_BG, fg=TEXT_MUTED)
        self.taille_lbl.pack(anchor="w")

        # Statut
        sig = self.import_path.get()
        status = f"✅  {os.path.basename(sig)}" if sig and os.path.isfile(sig) else "Aucune signature enregistrée"
        self.status_lbl = tk.Label(self, text=status, font=("Helvetica",9),
                                   bg=DARK_BG, fg=GOLD if "✅" in status else TEXT_MUTED)
        self.status_lbl.pack(pady=(0,8))

    def _update_preview(self):
        path = self.import_path.get()
        if path and os.path.isfile(path):
            try:
                from PIL import Image, ImageTk
                img = Image.open(path)
                img.thumbnail((420, 110))
                self._sig_img = ImageTk.PhotoImage(img)
                self.preview_lbl.config(image=self._sig_img, text="")
                return
            except Exception:
                pass
        self.preview_lbl.config(image="", text="Aucune signature importée")

    def _update_taille(self, val=None):
        """Sauvegarde la taille de signature et met à jour le label."""
        taille = self.sig_taille_var.get()
        db.set_parametre("signature_taille", str(round(taille, 1)))
        self.taille_lbl.config(text=f"Largeur actuelle : {taille:.1f} cm")

    def _choisir_image(self):
        path = filedialog.askopenfilename(
            title="Sélectionner votre signature",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp"), ("Tous", "*.*")],
            parent=self)
        if not path:
            return
        sig_dir = os.path.join(APP_DIR, "signature")
        os.makedirs(sig_dir, exist_ok=True)
        ext = os.path.splitext(path)[1].lower()
        dest = os.path.join(sig_dir, f"signature{ext}")
        shutil.copy2(path, dest)
        db.set_parametre("signature_path", dest)
        self.import_path.set(dest)
        self._update_preview()
        self.status_lbl.config(text=f"✅  {os.path.basename(dest)}", fg=GOLD)
        self.del_btn.pack(fill="x", pady=(8,0))
        messagebox.showinfo("Succès",
            "Signature importée !\nElle sera ajoutée automatiquement sur tous vos bons.", parent=self)

    def _supprimer(self):
        if messagebox.askyesno("Confirmer", "Supprimer la signature ?", parent=self):
            db.set_parametre("signature_path", "")
            self.import_path.set("")
            self._update_preview()
            self.status_lbl.config(text="Aucune signature enregistrée", fg=TEXT_MUTED)
            self.del_btn.pack_forget()


# ─────────────────────────────────────────────
# COMMANDE
# ─────────────────────────────────────────────
class CommandeWindow(tk.Toplevel):
    def __init__(self, master, categorie, user_info, user_type, sig_path,
                 commande_init=None):
        super().__init__(master)
        self.categorie = categorie
        self.user_info = user_info
        self.user_type = user_type
        self.sig_path  = sig_path
        self.commande  = dict(commande_init) if commande_init else {}
        self.produits  = []
        self.title(f"Bon de commande — {categorie}")
        self.configure(bg=DARK_BG)
        self.state("zoomed")
        self._build()

    def _build(self):
        self._apply_style()

        # ── Header ───────────────────────────────────────────────────────
        bar = tk.Frame(self, bg=HEADER_BG, height=50)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        cat_info = next((c for c in CATEGORIES if c[0]==self.categorie),
                        (self.categorie,"📋","#2563eb"))
        tk.Label(bar, text=f"{cat_info[1]}  Nouveau Bon — {self.categorie}",
                 font=("Helvetica",14,"bold"), bg=HEADER_BG, fg="white").pack(side="left", padx=18)
        tk.Button(bar, text="✕  Fermer", command=self.destroy,
                  font=("Helvetica",10), bg=DANGER, fg="white", bd=0, cursor="hand2",
                  pady=6, padx=14, activebackground="#b91c1c").pack(side="right", padx=12, pady=8)

        # ── Bandeau identité ─────────────────────────────────────────────
        ui = self.user_info
        badge   = "👤" if self.user_type == "yoann" else "👥"
        sig_lbl = "   ✍️ Signature activée" if self.sig_path else ""
        id_bar  = tk.Frame(self, bg="#0f172a")
        id_bar.pack(fill="x")
        tk.Label(id_bar,
                 text=(f"  {badge}  {ui.get('nom','').upper()} {ui.get('prenom','')}   "
                       f"│  Écrou : {ui.get('ecrou','')}   "
                       f"│  Bât. {ui.get('batiment','')} / Cell. {ui.get('cellule','')}"
                       f"{sig_lbl}"),
                 font=("Helvetica",9), bg="#0f172a",
                 fg=GOLD if self.user_type=="yoann" else "#a5b4fc",
                 pady=5).pack(side="left", padx=12)

        # ── Zone principale en GRID (2 colonnes fiables) ─────────────────
        main = tk.Frame(self, bg=DARK_BG)
        main.pack(fill="both", expand=True, padx=8, pady=8)
        main.columnconfigure(0, weight=3)   # catalogue : 60%
        main.columnconfigure(1, weight=2)   # bon       : 40%
        main.rowconfigure(0, weight=1)

        # ════════════════════════════════════════════
        # COLONNE 0 — CATALOGUE
        # ════════════════════════════════════════════
        left = tk.Frame(main, bg=PANEL_BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0,5))
        left.rowconfigure(2, weight=1)
        left.columnconfigure(0, weight=1)

        # En-tête catalogue
        hdr_l = tk.Frame(left, bg=cat_info[2], height=4)
        hdr_l.grid(row=0, column=0, sticky="ew")
        tk.Label(left, text=f"  {cat_info[1]}  Catalogue — {self.categorie}",
                 font=("Helvetica",12,"bold"), bg=PANEL_BG, fg=TEXT,
                 pady=8, anchor="w").grid(row=1, column=0, sticky="ew", padx=10)

        # Recherche
        sf = tk.Frame(left, bg=PANEL_BG)
        sf.grid(row=2, column=0, sticky="ew", padx=10, pady=(0,6))
        sf.columnconfigure(1, weight=1)
        tk.Label(sf, text="🔍", bg=PANEL_BG, fg=TEXT_MUTED,
                 font=("Helvetica",12)).grid(row=0, column=0, padx=(0,4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._filter())
        e = tk.Entry(sf, textvariable=self.search_var, font=("Helvetica",11),
                     bg=CARD_BG, fg=TEXT, insertbackground=TEXT, bd=0,
                     relief="flat", highlightthickness=1,
                     highlightbackground=BORDER, highlightcolor=ACCENT)
        e.grid(row=0, column=1, sticky="ew", ipady=7)
        e.focus_set()

        # Treeview produits
        tf = tk.Frame(left, bg=PANEL_BG)
        tf.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0,4))
        left.rowconfigure(3, weight=1)
        tf.rowconfigure(0, weight=1); tf.columnconfigure(0, weight=1)

        cols = ("code","produit","prix","max")
        self.tree_prod = ttk.Treeview(tf, columns=cols, show="headings",
                                      selectmode="browse")
        for col, txt, w, anc, stretch in [
            ("code",   "Code",    80,  "center", False),
            ("produit","Produit", 200, "w",      True),
            ("prix",   "Prix",    90,  "center", False),
            ("max",    "Max",     60,  "center", False),
        ]:
            self.tree_prod.heading(col, text=txt, anchor=anc)
            self.tree_prod.column(col, width=w, anchor=anc, stretch=stretch)
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree_prod.yview)
        self.tree_prod.configure(yscrollcommand=sb.set)
        self.tree_prod.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        self.tree_prod.bind("<Double-1>", lambda e: self._ajouter())
        self.tree_prod.bind("<Return>",   lambda e: self._ajouter())

        # Barre ajout
        af = tk.Frame(left, bg="#1e2538")
        af.grid(row=4, column=0, sticky="ew")
        tk.Label(af, text="Quantité :", bg="#1e2538", fg=TEXT,
                 font=("Helvetica",11)).pack(side="left", padx=(12,6), pady=10)
        self.qte_var = tk.StringVar(value="1")
        tk.Spinbox(af, from_=1, to=999, textvariable=self.qte_var, width=5,
                   font=("Helvetica",11), bg=CARD_BG, fg=TEXT, bd=0,
                   buttonbackground=CARD_BG, insertbackground=TEXT).pack(
                       side="left", padx=6, pady=8, ipady=4)
        tk.Button(af, text="➕  Ajouter au bon",
                  command=self._ajouter,
                  font=("Helvetica",11,"bold"), bg=SUCCESS, fg="white", bd=0,
                  cursor="hand2", pady=8, padx=18,
                  activebackground="#15803d").pack(side="left", padx=8, pady=8)
        tk.Label(af, text="ou double-clic sur le produit",
                 bg="#1e2538", fg=TEXT_MUTED,
                 font=("Helvetica",9,"italic")).pack(side="left")

        # ════════════════════════════════════════════
        # COLONNE 1 — BON DE COMMANDE
        # ════════════════════════════════════════════
        right = tk.Frame(main, bg="#111827")
        right.grid(row=0, column=1, sticky="nsew", padx=(5,0))
        right.rowconfigure(2, weight=1)
        right.columnconfigure(0, weight=1)

        # En-tête bon
        tk.Frame(right, bg=ACCENT, height=4).grid(row=0, column=0, sticky="ew")
        rttl = tk.Frame(right, bg="#111827")
        rttl.grid(row=1, column=0, sticky="ew")
        rttl.columnconfigure(0, weight=1)
        tk.Label(rttl, text="📋  BON DE COMMANDE",
                 font=("Helvetica",12,"bold"), bg="#111827", fg=TEXT,
                 pady=10, anchor="w").grid(row=0, column=0, sticky="w", padx=12)
        self.count_lbl = tk.Label(rttl, text="0 article(s)",
                                  font=("Helvetica",9), bg="#111827", fg=TEXT_MUTED)
        self.count_lbl.grid(row=0, column=1, sticky="e", padx=12)

        # Treeview bon
        bf = tk.Frame(right, bg="#111827")
        bf.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0,4))
        bf.rowconfigure(0, weight=1); bf.columnconfigure(0, weight=1)

        bcols = ("code","produit","qte","pu","total")
        self.tree_bon = ttk.Treeview(bf, columns=bcols, show="headings",
                                     selectmode="browse")
        for col, txt, w, anc, stretch in [
            ("code",   "Code",   65,  "center", False),
            ("produit","Produit", 80, "w",      True),
            ("qte",    "Qté",    45,  "center", False),
            ("pu",     "P.U.",   72,  "center", False),
            ("total",  "Total",  80,  "center", False),
        ]:
            self.tree_bon.heading(col, text=txt, anchor=anc)
            self.tree_bon.column(col, width=w, anchor=anc, stretch=stretch)
        sb2 = ttk.Scrollbar(bf, orient="vertical", command=self.tree_bon.yview)
        self.tree_bon.configure(yscrollcommand=sb2.set)
        self.tree_bon.grid(row=0, column=0, sticky="nsew")
        sb2.grid(row=0, column=1, sticky="ns")

        # Total
        tot_frm = tk.Frame(right, bg=ACCENT)
        tot_frm.grid(row=3, column=0, sticky="ew", padx=8, pady=4)
        self.total_var = tk.StringVar(value="TOTAL :   0,00 €")
        tk.Label(tot_frm, textvariable=self.total_var,
                 font=("Helvetica",15,"bold"), bg=ACCENT, fg="white",
                 pady=10).pack()

        # Boutons actions
        btn_frm = tk.Frame(right, bg="#111827")
        btn_frm.grid(row=4, column=0, sticky="ew", padx=8, pady=(0,8))
        btn_frm.columnconfigure(0, weight=1)
        btn_frm.columnconfigure(1, weight=1)

        tk.Button(btn_frm, text="🗑️ Retirer sélection",
                  command=self._retirer,
                  font=("Helvetica",10), bg="#374151", fg=TEXT, bd=0,
                  cursor="hand2", pady=8,
                  activebackground=DANGER, activeforeground="white").grid(
                      row=0, column=0, sticky="ew", padx=(0,3), pady=2)
        tk.Button(btn_frm, text="🔄 Vider le bon",
                  command=self._vider,
                  font=("Helvetica",10), bg="#374151", fg=TEXT, bd=0,
                  cursor="hand2", pady=8).grid(
                      row=0, column=1, sticky="ew", padx=(3,0), pady=2)

        tk.Button(btn_frm, text="💾  Sauvegarder & Imprimer le bon",
                  command=self._sauvegarder,
                  font=("Helvetica",12,"bold"), bg=ACCENT, fg="white", bd=0,
                  cursor="hand2", pady=12,
                  activebackground=ACCENT_HOV).grid(
                      row=1, column=0, columnspan=2, sticky="ew", pady=(6,2))

        self._load_products()
        if self.commande:
            self._refresh_bon()

    def _apply_style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("Treeview", background=CARD_BG, foreground=TEXT,
                    fieldbackground=CARD_BG, rowheight=26, font=("Helvetica",9))
        s.configure("Treeview.Heading", background=HEADER_BG, foreground="white",
                    font=("Helvetica",9,"bold"))
        s.map("Treeview", background=[("selected", ACCENT)])

    def _load_products(self, filtre=""):
        import re as _re
        self.produits = db.get_produits(self.categorie)
        # Tri numérique : AC1, AC2, AC3... pas AC1, AC10, AC11
        self.produits = sorted(self.produits,
            key=lambda p: int(_re.sub(r"[^0-9]", "", p[0]) or "0"))
        self.tree_prod.delete(*self.tree_prod.get_children())
        for p in self.produits:
            pid, nom, _, prix, qmax, _ = p
            if filtre and filtre.lower() not in nom.lower() and filtre.lower() not in pid.lower():
                continue
            self.tree_prod.insert("", "end", iid=pid,
                                  values=(pid, nom, f"{prix:.2f} €", qmax))

    def _filter(self, *_):
        self._load_products(self.search_var.get())

    def _ajouter(self):
        sel = self.tree_prod.selection()
        if not sel:
            messagebox.showinfo("Sélection", "Cliquez d'abord sur un produit dans la liste.", parent=self)
            return
        pid = sel[0]
        prod = next((p for p in self.produits if p[0] == pid), None)
        if not prod: return
        _, nom, _, prix, qmax, _ = prod
        try: qte = max(1, int(self.qte_var.get()))
        except: qte = 1
        new_qte = self.commande[pid]["qte"] + qte if pid in self.commande else qte
        if new_qte > qmax:
            messagebox.showwarning("Quantité max",
                f"Quantité maximum autorisée : {qmax}", parent=self)
            new_qte = qmax
        self.commande[pid] = {"nom":nom, "prix":prix, "qte":new_qte, "qte_max":qmax}
        self._refresh_bon()

    def _retirer(self):
        for pid in self.tree_bon.selection():
            self.commande.pop(pid, None)
        self._refresh_bon()

    def _vider(self):
        if self.commande and messagebox.askyesno(
                "Vider", "Vider tout le bon ?", parent=self):
            self.commande.clear()
            self._refresh_bon()

    def _refresh_bon(self):
        self.tree_bon.delete(*self.tree_bon.get_children())
        total = 0.0
        for i, (pid, d) in enumerate(self.commande.items()):
            st  = d["prix"] * d["qte"]
            total += st
            tag = "ligne_alt" if i % 2 else "ligne"
            self.tree_bon.insert("", "end", iid=pid,
                                 values=(pid, d["nom"], d["qte"],
                                         f"{d['prix']:.2f} €",
                                         f"{st:.2f} €"),
                                 tags=(tag,))
        self.tree_bon.tag_configure("ligne",     background=CARD_BG,   foreground=TEXT)
        self.tree_bon.tag_configure("ligne_alt", background="#252d42", foreground=TEXT)
        self.total_var.set(f"TOTAL :   {total:.2f} €")
        n = len(self.commande)
        self.count_lbl.config(text=f"{n} article{'s' if n>1 else ''}")

    def _sauvegarder(self):
        if not self.commande:
            messagebox.showwarning("Bon vide",
                "Ajoutez au moins un produit avant de sauvegarder.", parent=self)
            return

        # Vérification budget
        total_bon = sum(d["prix"]*d["qte"] for d in self.commande.values())
        budget, depense = db.get_budget_semaine()
        if budget > 0:
            restant = budget - depense
            if total_bon > restant:
                rep = messagebox.askyesno(
                    "⚠️  Budget dépassé !",
                    f"Ce bon coûte {total_bon:.2f} €\n"
                    f"Budget restant : {restant:.2f} €\n"
                    f"Dépassement : {total_bon - restant:.2f} €\n\n"
                    f"Voulez-vous quand même sauvegarder ?",
                    parent=self)
                if not rep:
                    return

        date_str = datetime.now().strftime("%d/%m/%Y")
        lignes, total = [], 0.0
        for pid, d in self.commande.items():
            st = d["prix"] * d["qte"]
            total += st
            lignes.append({"id":pid, "nom":d["nom"], "prix":d["prix"],
                           "qte":d["qte"], "total":st, "qte_max":d["qte_max"]})
        ui = self.user_info
        bon_id = db.sauvegarder_bon(
            self.categorie, ui["nom"], ui["prenom"], ui["ecrou"],
            ui["batiment"], ui["cellule"], lignes, total, date_str, self.user_type)

        pdf_dir = os.path.join(APP_DIR, "bons_pdf")
        os.makedirs(pdf_dir, exist_ok=True)
        fname    = f"bon_{self.categorie}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = os.path.join(pdf_dir, fname)
        try:
            impression.generer_bon_pdf(
                self.categorie, ui["nom"], ui["prenom"], ui["ecrou"],
                ui["batiment"], ui["cellule"], lignes, total, date_str,
                pdf_path, signature_path=self.sig_path)
            rep = messagebox.askyesno("✅  Bon sauvegardé",
                f"Bon #{bon_id} enregistré !\n\nOuvrir le PDF maintenant ?",
                parent=self)
            if rep:
                _open_file(pdf_path)
        except Exception as ex:
            messagebox.showerror("Erreur PDF", str(ex), parent=self)
        self._vider_sans_confirm()
        # Rafraîchir le budget dans la fenêtre principale
        try:
            self.master._update_budget_lbl()
        except Exception:
            pass

    def _vider_sans_confirm(self):
        self.commande.clear()
        self.tree_bon.delete(*self.tree_bon.get_children())
        self.total_var.set("TOTAL :   0,00 €")
        self.count_lbl.config(text="0 article")


class ParametresWindow(tk.Toplevel):
    # Palette 56 couleurs (8 colonnes x 7 lignes)
    PALETTE = [
        # Blancs / gris
        "#ffffff","#f0f0f0","#d0d0d0","#a0a0a0","#707070","#404040","#202020","#000000",
        # Rouges
        "#ffe0e0","#ffaaaa","#ff6666","#ff2222","#cc0000","#990000","#660000","#330000",
        # Oranges
        "#fff0d0","#ffcc88","#ffaa44","#ff8800","#cc6600","#993300","#662200","#331100",
        # Jaunes
        "#ffffe0","#ffff99","#ffee44","#ffcc00","#ccaa00","#997700","#664400","#332200",
        # Verts
        "#e0ffe0","#99ee99","#44cc44","#00aa00","#007700","#004400","#002200","#001100",
        # Bleus
        "#e0e8ff","#99aaff","#4466ff","#1133cc","#0022aa","#001177","#000055","#000033",
        # Cyans
        "#d0ffff","#88eeff","#22ccee","#00aacc","#007799","#005566","#003344","#001122",
        # Violets / roses
        "#ffe0ff","#ee99ee","#cc44cc","#aa00aa","#880066","#660044","#440033","#220022",
    ]

    def __init__(self, master):
        super().__init__(master)
        self.title("Paramètres")
        self.configure(bg=DARK_BG)
        self.resizable(False, False)
        self.geometry("680x700")
        self._center()
        self._build()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - self.winfo_width())  // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build(self):
        params = db.get_parametres()

        bar = tk.Frame(self, bg=HEADER_BG, height=44)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Label(bar, text="⚙️  Paramètres",
                 font=("Helvetica",12,"bold"), bg=HEADER_BG, fg="white").pack(side="left", padx=14, pady=8)

        # Notebook (onglets)
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        # ── Onglet 1 : Mes informations ───────────────────────────────────────
        tab1 = tk.Frame(nb, bg=DARK_BG)
        nb.add(tab1, text="  👤  Mes informations  ")

        frm = tk.Frame(tab1, bg=DARK_BG, padx=30, pady=20)
        frm.pack(fill="both", expand=True)
        fields = [("Nom","nom",params.get("nom","")),
                  ("Prénom","prenom",params.get("prenom","")),
                  ("Écrou","ecrou",params.get("ecrou","")),
                  ("Bâtiment","batiment",params.get("batiment","")),
                  ("Cellule","cellule",params.get("cellule",""))]
        self.vars = {}
        for label, key, val in fields:
            row = tk.Frame(frm, bg=DARK_BG)
            row.pack(fill="x", pady=5)
            tk.Label(row, text=label+":", width=12, anchor="e",
                     font=("Helvetica",10), bg=DARK_BG, fg=TEXT_MUTED).pack(side="left", padx=(0,8))
            v = tk.StringVar(value=val)
            self.vars[key] = v
            tk.Entry(row, textvariable=v, font=("Helvetica",10),
                     bg=CARD_BG, fg=TEXT, insertbackground=TEXT, bd=0,
                     relief="flat", highlightthickness=1, highlightbackground=BORDER,
                     highlightcolor=ACCENT).pack(side="left", fill="x", expand=True, ipady=6)
        tk.Button(frm, text="💾  Enregistrer",
                  command=self._sauvegarder,
                  font=("Helvetica",11,"bold"), bg=SUCCESS, fg="white", bd=0,
                  cursor="hand2", pady=8).pack(fill="x", pady=(20,0))

        # ── Onglet 2 : Mot de passe ──────────────────────────────────────────
        tab_mdp = tk.Frame(nb, bg=DARK_BG)
        nb.add(tab_mdp, text="  🔑  Mot de passe  ")
        self._build_mdp(tab_mdp)

        # ── Onglet 3 : Couleurs des bons ─────────────────────────────────────
        tab2 = tk.Frame(nb, bg=DARK_BG)
        nb.add(tab2, text="  🎨  Couleurs des bons  ")
        self._build_couleurs(tab2)

    def _build_mdp(self, parent):
        """Onglet modification/suppression mot de passe Yoann."""
        frm = tk.Frame(parent, bg=DARK_BG, padx=30, pady=24)
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text="Modifier le mot de passe",
                 font=("Helvetica",13,"bold"), bg=DARK_BG, fg=TEXT).pack(anchor="w", pady=(0,16))

        # Ancien MDP
        row1 = tk.Frame(frm, bg=DARK_BG)
        row1.pack(fill="x", pady=5)
        tk.Label(row1, text="Ancien MDP :", width=16, anchor="e",
                 font=("Helvetica",10), bg=DARK_BG, fg=TEXT_MUTED).pack(side="left", padx=(0,8))
        self.old_mdp_var = tk.StringVar()
        self.old_mdp_entry = tk.Entry(row1, textvariable=self.old_mdp_var,
                 show="•", font=("Helvetica",11), bg=CARD_BG, fg=TEXT,
                 insertbackground=TEXT, bd=0, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT)
        self.old_mdp_entry.pack(side="left", fill="x", expand=True, ipady=6)

        # Nouveau MDP
        row2 = tk.Frame(frm, bg=DARK_BG)
        row2.pack(fill="x", pady=5)
        tk.Label(row2, text="Nouveau MDP :", width=16, anchor="e",
                 font=("Helvetica",10), bg=DARK_BG, fg=TEXT_MUTED).pack(side="left", padx=(0,8))
        self.new_mdp_var = tk.StringVar()
        self.new_mdp_entry = tk.Entry(row2, textvariable=self.new_mdp_var,
                 show="•", font=("Helvetica",11), bg=CARD_BG, fg=TEXT,
                 insertbackground=TEXT, bd=0, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT)
        self.new_mdp_entry.pack(side="left", fill="x", expand=True, ipady=6)

        # Confirmer MDP
        row3 = tk.Frame(frm, bg=DARK_BG)
        row3.pack(fill="x", pady=5)
        tk.Label(row3, text="Confirmer MDP :", width=16, anchor="e",
                 font=("Helvetica",10), bg=DARK_BG, fg=TEXT_MUTED).pack(side="left", padx=(0,8))
        self.conf_mdp_var = tk.StringVar()
        self.conf_mdp_entry = tk.Entry(row3, textvariable=self.conf_mdp_var,
                 show="•", font=("Helvetica",11), bg=CARD_BG, fg=TEXT,
                 insertbackground=TEXT, bd=0, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT)
        self.conf_mdp_entry.pack(side="left", fill="x", expand=True, ipady=6)

        # Afficher/masquer
        self.show_mdp = tk.BooleanVar(value=False)
        tk.Checkbutton(frm, text="Afficher le mot de passe",
                       variable=self.show_mdp, command=self._toggle_show_mdp,
                       bg=DARK_BG, fg=TEXT_MUTED, activebackground=DARK_BG,
                       selectcolor=CARD_BG, font=("Helvetica",9)).pack(anchor="w", pady=(4,12))

        tk.Button(frm, text="💾  Modifier le mot de passe",
                  command=self._changer_mdp_params,
                  font=("Helvetica",11,"bold"), bg=ACCENT, fg="white", bd=0,
                  cursor="hand2", pady=8, activebackground=ACCENT_HOV).pack(fill="x", pady=2)

        tk.Frame(frm, bg=BORDER, height=1).pack(fill="x", pady=14)

        # Supprimer MDP (remettre à vide = aucun mot de passe)
        tk.Label(frm, text="Supprimer le mot de passe",
                 font=("Helvetica",11,"bold"), bg=DARK_BG, fg=TEXT).pack(anchor="w", pady=(0,6))
        tk.Label(frm,
                 text="Sans mot de passe, la connexion Yoann se fera directement.",
                 font=("Helvetica",9), bg=DARK_BG, fg=TEXT_MUTED, justify="left").pack(anchor="w")
        tk.Button(frm, text="🗑️  Supprimer le mot de passe",
                  command=self._supprimer_mdp,
                  font=("Helvetica",10), bg=DANGER, fg="white", bd=0,
                  cursor="hand2", pady=7, activebackground="#b91c1c").pack(fill="x", pady=(8,0))

    def _toggle_show_mdp(self):
        show = "" if self.show_mdp.get() else "•"
        self.old_mdp_entry.config(show=show)
        self.new_mdp_entry.config(show=show)
        self.conf_mdp_entry.config(show=show)

    def _changer_mdp_params(self):
        old = self.old_mdp_var.get()
        new = self.new_mdp_var.get()
        conf = self.conf_mdp_var.get()
        role = db.verifier_utilisateur("yoann", old)
        if not role:
            messagebox.showerror("Erreur", "Ancien mot de passe incorrect.", parent=self)
            return
        if not new:
            messagebox.showwarning("Vide", "Le nouveau mot de passe ne peut pas être vide.", parent=self)
            return
        if new != conf:
            messagebox.showerror("Erreur", "Les mots de passe ne correspondent pas.", parent=self)
            return
        db.changer_mot_de_passe("yoann", new)
        messagebox.showinfo("Succès", "Mot de passe modifié avec succès !", parent=self)
        self.old_mdp_var.set("")
        self.new_mdp_var.set("")
        self.conf_mdp_var.set("")

    def _supprimer_mdp(self):
        if messagebox.askyesno("Confirmer",
                "Supprimer le mot de passe ? La connexion Yoann se fera sans saisie.", parent=self):
            db.changer_mot_de_passe("yoann", "")
            messagebox.showinfo("Supprime", "Mot de passe supprime.", parent=self)

    def _build_couleurs(self, parent):
        """Palette de couleurs pour personnaliser chaque catégorie."""
        tk.Label(parent,
                 text="Choisissez la couleur de fond de chaque bon de cantine",
                 font=("Helvetica",10), bg=DARK_BG, fg=TEXT_MUTED).pack(pady=(12,6))

        # Sélecteur de catégorie
        top = tk.Frame(parent, bg=DARK_BG)
        top.pack(fill="x", padx=20, pady=4)

        tk.Label(top, text="Catégorie :", font=("Helvetica",10,"bold"),
                 bg=DARK_BG, fg=TEXT).pack(side="left")

        cats = [c[0] for c in CATEGORIES]
        self.cat_couleur_var = tk.StringVar(value=cats[0])
        cb = ttk.Combobox(top, textvariable=self.cat_couleur_var,
                          values=cats, state="readonly", width=22,
                          font=("Helvetica",10))
        cb.pack(side="left", padx=10)
        cb.bind("<<ComboboxSelected>>", lambda e: self._update_preview_couleur())

        # Aperçu couleur actuelle
        prev_frm = tk.Frame(parent, bg=DARK_BG)
        prev_frm.pack(pady=6)
        tk.Label(prev_frm, text="Couleur actuelle :",
                 font=("Helvetica",9), bg=DARK_BG, fg=TEXT_MUTED).pack(side="left")
        self.prev_lbl = tk.Label(prev_frm, text="       ",
                                 width=8, relief="solid", bd=1)
        self.prev_lbl.pack(side="left", padx=8)
        self.prev_hex = tk.Label(prev_frm, text="",
                                 font=("Helvetica",9), bg=DARK_BG, fg=TEXT_MUTED)
        self.prev_hex.pack(side="left")

        # Palette
        tk.Label(parent, text="Choisir une couleur :",
                 font=("Helvetica",10,"bold"), bg=DARK_BG, fg=TEXT).pack(pady=(8,4))

        palette_frm = tk.Frame(parent, bg=DARK_BG)
        palette_frm.pack()

        self._selected_color = tk.StringVar()
        COLS = 8
        for i, color in enumerate(self.PALETTE):
            r, c = divmod(i, COLS)
            btn = tk.Button(palette_frm, bg=color, width=3, height=1,
                            relief="flat", bd=2, cursor="hand2",
                            command=lambda col=color: self._choisir_couleur(col))
            btn.grid(row=r, column=c, padx=2, pady=2)
            btn.bind("<Enter>", lambda e, b=btn, col=color: b.config(relief="raised"))
            btn.bind("<Leave>", lambda e, b=btn: b.config(relief="flat"))

        # Couleur personnalisée
        custom_frm = tk.Frame(parent, bg=DARK_BG)
        custom_frm.pack(pady=8)
        tk.Label(custom_frm, text="Couleur personnalisée (#RRGGBB) :",
                 font=("Helvetica",9), bg=DARK_BG, fg=TEXT_MUTED).pack(side="left")
        self.custom_var = tk.StringVar()
        tk.Entry(custom_frm, textvariable=self.custom_var, width=10,
                 font=("Helvetica",10), bg=CARD_BG, fg=TEXT,
                 insertbackground=TEXT, bd=0, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER).pack(side="left", padx=6, ipady=4)
        tk.Button(custom_frm, text="Appliquer",
                  command=self._appliquer_custom,
                  font=("Helvetica",9), bg=ACCENT, fg="white", bd=0,
                  cursor="hand2", pady=4, padx=8).pack(side="left")

        # Bouton réinitialiser
        tk.Button(parent, text="↩️  Réinitialiser couleur par défaut",
                  command=self._reset_couleur,
                  font=("Helvetica",9), bg="#374151", fg=TEXT, bd=0,
                  cursor="hand2", pady=5, padx=10).pack(pady=4)

        self._update_preview_couleur()

    def _get_couleur_key(self):
        return f"couleur_{self.cat_couleur_var.get()}"

    def _update_preview_couleur(self):
        params = db.get_parametres()
        cat    = self.cat_couleur_var.get()
        key    = f"couleur_{cat}"
        # Couleur stockée ou défaut
        from impression import BG
        default_rgb = BG.get(cat, (0.82, 0.82, 0.82))
        default_hex = "#{:02x}{:02x}{:02x}".format(
            int(default_rgb[0]*255),
            int(default_rgb[1]*255),
            int(default_rgb[2]*255))
        couleur = params.get(key, default_hex)
        try:
            self.prev_lbl.config(bg=couleur)
            self.prev_hex.config(text=couleur)
        except:
            pass

    def _choisir_couleur(self, color):
        cat = self.cat_couleur_var.get()
        db.set_parametre(f"couleur_{cat}", color)
        self._update_preview_couleur()
        messagebox.showinfo("Couleur",
            f"Couleur du bon {cat} changée en {color} !", parent=self)

    def _appliquer_custom(self):
        color = self.custom_var.get().strip()
        if not color.startswith("#") or len(color) not in (4, 7):
            messagebox.showwarning("Format invalide",
                "Format attendu : #RRGGBB (ex: #ff8800)", parent=self)
            return
        try:
            self.prev_lbl.config(bg=color)
        except:
            messagebox.showwarning("Couleur invalide",
                "Cette couleur n'est pas valide.", parent=self)
            return
        cat = self.cat_couleur_var.get()
        db.set_parametre(f"couleur_{cat}", color)
        self._update_preview_couleur()
        messagebox.showinfo("Couleur",
            f"Couleur du bon {cat} changée en {color} !", parent=self)

    def _reset_couleur(self):
        cat = self.cat_couleur_var.get()
        db.set_parametre(f"couleur_{cat}", "")
        self._update_preview_couleur()
        messagebox.showinfo("Réinitialisation",
            f"Couleur du bon {cat} réinitialisée.", parent=self)

    def _sauvegarder(self):
        for key, var in self.vars.items():
            db.set_parametre(key, var.get().strip())
        messagebox.showinfo("Succès", "Informations enregistrées.", parent=self)
        self.destroy()


# ─────────────────────────────────────────────
# CATALOGUE
# ─────────────────────────────────────────────
class CatalogueWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Catalogue")
        self.configure(bg=DARK_BG)
        self.geometry("1100x680")
        self._center()
        self._build()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - self.winfo_width())  // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build(self):
        bar = tk.Frame(self, bg=HEADER_BG, height=48)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Label(bar, text="📋  Catalogue des Produits",
                 font=("Helvetica",13,"bold"), bg=HEADER_BG, fg="white").pack(side="left", padx=14)
        tk.Button(bar, text="✕ Fermer", command=self.destroy,
                  font=("Helvetica",9), bg=DANGER, fg="white", bd=0,
                  cursor="hand2", pady=4, padx=10).pack(side="right", padx=10)

        fbar = tk.Frame(self, bg=PANEL_BG)
        fbar.pack(fill="x")
        tk.Label(fbar, text="Catégorie:", bg=PANEL_BG, fg=TEXT_MUTED,
                 font=("Helvetica",10)).pack(side="left", padx=(14,4), pady=8)
        self.cat_var = tk.StringVar(value="Toutes")
        cats = ["Toutes"] + [c[0] for c in CATEGORIES]
        ttk.Combobox(fbar, textvariable=self.cat_var, values=cats,
                     state="readonly", width=20,
                     font=("Helvetica",10)).pack(side="left", padx=4)
        self.cat_var.trace_add("write", lambda *_: self._load())
        tk.Label(fbar, text="🔍", bg=PANEL_BG, fg=TEXT_MUTED).pack(side="left", padx=(14,2))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._load())
        tk.Entry(fbar, textvariable=self.search_var, font=("Helvetica",10),
                 bg=CARD_BG, fg=TEXT, insertbackground=TEXT, bd=0,
                 relief="flat", highlightthickness=1,
                 highlightbackground=BORDER).pack(side="left", ipady=5, padx=4, fill="x", expand=True)
        self.actif_var = tk.BooleanVar(value=False)
        tk.Checkbutton(fbar, text="Actifs seuls", variable=self.actif_var,
                       bg=PANEL_BG, activebackground=PANEL_BG, fg=TEXT_MUTED,
                       selectcolor=CARD_BG, command=self._load).pack(side="left", padx=8)

        cols = ("id","nom","categorie","prix","max","actif")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        for col, txt, w, anc in [("id","Code",70,"center"),("nom","Produit",420,"w"),
                                   ("categorie","Catégorie",130,"center"),("prix","Prix",80,"center"),
                                   ("max","Max",60,"center"),("actif","Actif",60,"center")]:
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=w, anchor=anc)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self._editer())

        bbar = tk.Frame(self, bg=PANEL_BG)
        bbar.pack(fill="x")
        self.count_lbl = tk.Label(bbar, text="", bg=PANEL_BG, fg=TEXT_MUTED, font=("Helvetica",9))
        self.count_lbl.pack(side="left", padx=14, pady=6)
        tk.Button(bbar, text="✏️ Modifier", command=self._editer,
                  font=("Helvetica",9), bg=ACCENT, fg="white", bd=0,
                  cursor="hand2", pady=5, padx=10).pack(side="right", padx=8, pady=6)

        s = ttk.Style(); s.theme_use("clam")
        s.configure("Treeview", background=CARD_BG, foreground=TEXT,
                    fieldbackground=CARD_BG, rowheight=26, font=("Helvetica",9))
        s.configure("Treeview.Heading", background=HEADER_BG, foreground="white",
                    font=("Helvetica",9,"bold"))
        s.map("Treeview", background=[("selected", ACCENT)])
        self._load()

    def _load(self):
        cat = self.cat_var.get()
        f   = self.search_var.get().lower()
        ao  = self.actif_var.get()
        prods = db.get_produits(None if cat == "Toutes" else cat, actif_only=ao)
        self.tree.delete(*self.tree.get_children())
        n = 0
        for p in prods:
            pid, nom, cat2, prix, qmax, actif = p
            if f and f not in nom.lower() and f not in pid.lower(): continue
            tag = "" if actif == "Oui" else "inactive"
            self.tree.insert("", "end", iid=pid,
                             values=(pid, nom, cat2, f"{prix:.2f} €", qmax, actif),
                             tags=(tag,))
            n += 1
        self.tree.tag_configure("inactive", foreground=TEXT_MUTED)
        self.count_lbl.config(text=f"{n} produit(s)")

    def _editer(self):
        sel = self.tree.selection()
        if not sel: return
        pid = sel[0]
        prod = next((p for p in db.get_produits(actif_only=False) if p[0] == pid), None)
        if prod:
            EditProduitWindow(self, prod, self._load)

class EditProduitWindow(tk.Toplevel):
    def __init__(self, master, prod, callback):
        super().__init__(master)
        self.prod = prod; self.callback = callback
        self.title(f"Modifier — {prod[0]}")
        self.configure(bg=DARK_BG)
        self.resizable(False, False)
        self.geometry("400x280")
        self._center()
        self._build()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - self.winfo_width())  // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build(self):
        pid, nom, _, prix, qmax, actif = self.prod
        bar = tk.Frame(self, bg=HEADER_BG, height=44); bar.pack(fill="x"); bar.pack_propagate(False)
        tk.Label(bar, text=f"✏️  {pid}", font=("Helvetica",11,"bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=12, pady=8)
        frm = tk.Frame(self, bg=DARK_BG, padx=24, pady=16); frm.pack(fill="both", expand=True)
        self.vars = {}
        for label, key, val in [("Produit","nom",nom),("Prix (€)","prix",f"{prix:.2f}"),("Qté max","max",str(qmax))]:
            row = tk.Frame(frm, bg=DARK_BG); row.pack(fill="x", pady=4)
            tk.Label(row, text=label+":", width=14, anchor="e",
                     font=("Helvetica",10), bg=DARK_BG, fg=TEXT_MUTED).pack(side="left", padx=(0,8))
            v = tk.StringVar(value=val); self.vars[key] = v
            tk.Entry(row, textvariable=v, font=("Helvetica",10),
                     bg=CARD_BG, fg=TEXT, insertbackground=TEXT, bd=0,
                     relief="flat", highlightthickness=1, highlightbackground=BORDER,
                     highlightcolor=ACCENT).pack(side="left", fill="x", expand=True, ipady=6)
        row_a = tk.Frame(frm, bg=DARK_BG); row_a.pack(fill="x", pady=4)
        tk.Label(row_a, text="Actif:", width=14, anchor="e",
                 font=("Helvetica",10), bg=DARK_BG, fg=TEXT_MUTED).pack(side="left", padx=(0,8))
        self.v_actif = tk.StringVar(value=actif)
        ttk.Combobox(row_a, textvariable=self.v_actif, values=["Oui","Non"],
                     state="readonly", width=8).pack(side="left")
        tk.Button(frm, text="💾 Enregistrer", command=self._save,
                  font=("Helvetica",11,"bold"), bg=SUCCESS, fg="white", bd=0,
                  cursor="hand2", pady=8, activebackground="#15803d").pack(fill="x", pady=(12,0))

    def _save(self):
        try:
            prix = float(self.vars["prix"].get().replace(",","."))
            qmax = int(self.vars["max"].get())
        except:
            messagebox.showerror("Erreur","Prix et Max doivent être des nombres.",parent=self); return
        db.update_produit(self.prod[0], self.vars["nom"].get().strip(), prix, qmax, self.v_actif.get())
        self.callback(); self.destroy()


# ─────────────────────────────────────────────
# HISTORIQUE
# ─────────────────────────────────────────────
class HistoriqueWindow(tk.Toplevel):
    def __init__(self, master, user_type, user_info):
        super().__init__(master)
        self.user_type = user_type
        self.user_info = user_info
        self.bons      = []
        self.title("Historique des Bons")
        self.configure(bg=DARK_BG)
        self.state("zoomed")
        self._center()
        self._build()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - self.winfo_width())  // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build(self):
        # ── Header ───────────────────────────────────────────────────────────
        bar = tk.Frame(self, bg=HEADER_BG, height=48)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Label(bar, text="📁  Historique des Bons de Commande",
                 font=("Helvetica",13,"bold"), bg=HEADER_BG, fg="white").pack(side="left", padx=14)
        tk.Button(bar, text="✕ Fermer", command=self.destroy,
                  font=("Helvetica",9), bg=DANGER, fg="white", bd=0,
                  cursor="hand2", pady=4, padx=10).pack(side="right", padx=10)

        # ── Treeview bons ─────────────────────────────────────────────────────
        cols = ("id","date","categorie","nom","ecrou","type","total")
        self.tree = ttk.Treeview(self, columns=cols, show="headings",
                                 height=14, selectmode="browse")
        for col, txt, w, anc in [
            ("id",        "#",          45,  "center"),
            ("date",      "Date",       95,  "center"),
            ("categorie", "Catégorie", 130,  "center"),
            ("nom",       "Nom",       220,  "w"),
            ("ecrou",     "Écrou",      80,  "center"),
            ("type",      "Profil",     60,  "center"),
            ("total",     "Total",      90,  "center"),
        ]:
            self.tree.heading(col, text=txt, anchor=anc)
            self.tree.column(col, width=w, anchor=anc)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._show_detail)

        # ── Détail du bon sélectionné ─────────────────────────────────────────
        df = tk.Frame(self, bg=PANEL_BG)
        df.pack(fill="x")

        hdr_df = tk.Frame(df, bg=PANEL_BG)
        hdr_df.pack(fill="x")
        tk.Label(hdr_df, text="Détail du bon sélectionné",
                 font=("Helvetica",10,"bold"), bg=PANEL_BG, fg=TEXT, pady=5).pack(side="left", padx=10)
        tk.Button(hdr_df, text="🗑️ Supprimer la ligne sélectionnée",
                  command=self._supprimer_ligne,
                  font=("Helvetica",9), bg=DANGER, fg="white", bd=0,
                  cursor="hand2", pady=3, padx=8).pack(side="right", padx=10, pady=5)

        dcols = ("code","produit","qte","prix","total_ligne")
        self.dtree = ttk.Treeview(df, columns=dcols, show="headings",
                                  height=6, selectmode="browse")
        for col, txt, w, anc in [
            ("code",        "Code",       80,  "center"),
            ("produit",     "Désignation",450, "w"),
            ("qte",         "Qté",        55,  "center"),
            ("prix",        "Prix unit.",  90,  "center"),
            ("total_ligne", "Total",       90,  "center"),
        ]:
            self.dtree.heading(col, text=txt, anchor=anc)
            self.dtree.column(col, width=w, anchor=anc)
        dsb = ttk.Scrollbar(df, orient="vertical", command=self.dtree.yview)
        self.dtree.configure(yscrollcommand=dsb.set)
        dsb.pack(side="right", fill="y")
        self.dtree.pack(fill="both", expand=True, padx=(0,0))

        # ── Barre actions ─────────────────────────────────────────────────────
        abar = tk.Frame(self, bg=PANEL_BG)
        abar.pack(fill="x")

        tk.Button(abar, text="🖨️  Réimprimer",
                  command=self._reimprimer,
                  font=("Helvetica",10), bg=ACCENT, fg="white", bd=0,
                  cursor="hand2", pady=7, padx=14).pack(side="left", padx=8, pady=6)

        tk.Button(abar, text="✏️  Rééditer le bon",
                  command=self._reediter,
                  font=("Helvetica",10), bg=SUCCESS, fg="white", bd=0,
                  cursor="hand2", pady=7, padx=14).pack(side="left", padx=4, pady=6)

        tk.Button(abar, text="🗑️  Supprimer ce bon",
                  command=self._supprimer_bon,
                  font=("Helvetica",10), bg=DANGER, fg="white", bd=0,
                  cursor="hand2", pady=7, padx=14).pack(side="left", pady=6)

        tk.Button(abar, text="🖨️  Imprimer TOUS les bons",
                  command=self._imprimer_tous,
                  font=("Helvetica",11,"bold"), bg="#7c3aed", fg="white", bd=0,
                  cursor="hand2", pady=7, padx=16).pack(side="right", padx=8, pady=6)

        tk.Button(abar, text="🖨️  Imprimer bons du jour",
                  command=self._imprimer_aujourd_hui,
                  font=("Helvetica",10), bg="#0891b2", fg="white", bd=0,
                  cursor="hand2", pady=7, padx=12).pack(side="right", pady=6)

        # Style
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("Treeview", background=CARD_BG, foreground=TEXT,
                    fieldbackground=CARD_BG, rowheight=24, font=("Helvetica",9))
        s.configure("Treeview.Heading", background=HEADER_BG, foreground="white",
                    font=("Helvetica",9,"bold"))
        s.map("Treeview", background=[("selected", ACCENT)])
        self._load()

    def _load(self):
        self.bons = db.get_historique_bons(200)
        self.tree.delete(*self.tree.get_children())
        for b in self.bons:
            bid, date, cat, nom, prenom, ecrou, bat, cell, total, *rest = b
            utype = rest[0] if rest else "?"
            badge = "👤" if utype == "yoann" else "👥"
            self.tree.insert("", "end", iid=str(bid),
                             values=(bid, date, cat, f"{nom} {prenom}",
                                     ecrou, badge, f"{total:.2f} €"))
        self.dtree.delete(*self.dtree.get_children())

    def _show_detail(self, _=None):
        sel = self.tree.selection()
        if not sel: return
        lignes = db.get_lignes_bon(int(sel[0]))
        self.dtree.delete(*self.dtree.get_children())
        for l in lignes:
            lid, _, pid, nom, prix, qte, total_l = l
            self.dtree.insert("", "end", iid=str(lid),
                              values=(pid, nom, qte,
                                      f"{prix:.2f} €", f"{total_l:.2f} €"))

    def _supprimer_ligne(self):
        """Supprime une ligne individuelle du bon dans la DB."""
        sel_ligne = self.dtree.selection()
        if not sel_ligne:
            messagebox.showinfo("Sélection",
                "Cliquez d'abord sur une ligne dans le détail.", parent=self)
            return
        if not messagebox.askyesno("Confirmer",
                "Supprimer cette ligne du bon ?", parent=self):
            return
        ligne_id = int(sel_ligne[0])
        conn = db.get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM lignes_bon WHERE id=?", (ligne_id,))
        conn.commit()
        conn.close()
        # Rafraîchir le détail
        self._show_detail()
        # Recalculer le total du bon
        sel_bon = self.tree.selection()
        if sel_bon:
            bon_id = int(sel_bon[0])
            lignes = db.get_lignes_bon(bon_id)
            nouveau_total = sum(l[6] for l in lignes)
            conn2 = db.get_connection()
            c2 = conn2.cursor()
            c2.execute("UPDATE bons SET total=? WHERE id=?", (nouveau_total, bon_id))
            conn2.commit()
            conn2.close()
        self._load()

    def _supprimer_bon(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Sélection",
                "Sélectionnez un bon à supprimer.", parent=self)
            return
        if messagebox.askyesno("Confirmer", "Supprimer ce bon entier ?", parent=self):
            db.delete_bon(int(sel[0]))
            self._load()

    def _get_sig_path(self, utype):
        if utype != "yoann":
            return None
        params   = db.get_parametres()
        sig_path = params.get("signature_path", "") or None
        if sig_path and not os.path.isfile(sig_path):
            sig_path = None
        return sig_path

    def _generer_pdf_bon(self, bon, pdf_dir):
        bid, date, cat, nom, prenom, ecrou, bat, cell, total, *rest = bon
        utype    = rest[0] if rest else "invite"
        lig_raw  = db.get_lignes_bon(bid)
        lignes   = [{"id":l[2],"nom":l[3],"prix":l[4],
                     "qte":l[5],"total":l[6],"qte_max":0} for l in lig_raw]
        sp       = self._get_sig_path(utype)
        pdf_path = os.path.join(pdf_dir,
                                f"bon_{bid}_{cat.replace(' ','_').replace('&','et')}.pdf")
        impression.generer_bon_pdf(cat, nom, prenom, ecrou, bat, cell,
                                   lignes, total, date, pdf_path,
                                   signature_path=sp)
        return pdf_path

    def _reediter(self):
        """Rouvre un bon existant dans la fenêtre de commande pour le modifier."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Sélection",
                "Sélectionnez un bon à rééditer.", parent=self)
            return
        bon_id = int(sel[0])
        bon    = next((b for b in self.bons if b[0] == bon_id), None)
        if not bon: return
        bid, date, cat, nom, prenom, ecrou, bat, cell, total, *rest = bon
        utype   = rest[0] if rest else "invite"
        lig_raw = db.get_lignes_bon(bon_id)
        # Reconstruit le dict commande
        commande_init = {}
        for l in lig_raw:
            lid, _, pid, pnom, prix, qte, total_l = l
            commande_init[pid] = {"nom": pnom, "prix": prix,
                                  "qte": qte, "qte_max": 99}
        user_info = {"nom": nom, "prenom": prenom, "ecrou": ecrou,
                     "batiment": bat, "cellule": cell}
        sp = self._get_sig_path(utype)
        # Supprime l'ancien bon puis ouvre la fenêtre en mode réédition
        if messagebox.askyesno("Rééditer",
            f"Le bon #{bon_id} sera supprimé et rouvert pour modification.\nContinuer ?",
            parent=self):
            db.delete_bon(bon_id)
            self._load()
            win = CommandeWindow(self.master, cat, user_info, utype, sp,
                                 commande_init=commande_init)
            win.grab_set()

    def _reimprimer(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Sélection",
                "Sélectionnez un bon à réimprimer.", parent=self)
            return
        bon_id = int(sel[0])
        bon    = next((b for b in self.bons if b[0] == bon_id), None)
        if not bon: return
        pdf_dir = os.path.join(APP_DIR, "bons_pdf")
        os.makedirs(pdf_dir, exist_ok=True)
        try:
            p = self._generer_pdf_bon(bon, pdf_dir)
            _open_file(p)
        except Exception as ex:
            messagebox.showerror("Erreur PDF", str(ex), parent=self)

    def _imprimer_aujourd_hui(self):
        today = datetime.now().strftime("%d/%m/%Y")
        bons  = [b for b in self.bons if b[1] == today]
        if not bons:
            messagebox.showinfo("Aucun bon",
                f"Aucun bon trouvé pour aujourd'hui ({today}).", parent=self)
            return
        self._generer_et_ouvrir(bons)

    def _imprimer_tous(self):
        if not self.bons:
            messagebox.showinfo("Aucun bon",
                "Aucun bon dans l'historique.", parent=self)
            return
        if not messagebox.askyesno("Confirmer",
                f"Imprimer les {len(self.bons)} bon(s) de l'historique ?",
                parent=self):
            return
        self._generer_et_ouvrir(self.bons)

    def _generer_et_ouvrir(self, bons):
        pdf_dir = os.path.join(APP_DIR, "bons_pdf")
        os.makedirs(pdf_dir, exist_ok=True)
        pdfs = []
        for bon in bons:
            try:
                p = self._generer_pdf_bon(bon, pdf_dir)
                pdfs.append(p)
            except Exception as ex:
                messagebox.showerror("Erreur PDF", str(ex), parent=self)
        for p in pdfs:
            _open_file(p)
        if pdfs:
            messagebox.showinfo("✅ Impression",
                f"{len(pdfs)} bon(s) ouvert(s) pour impression.", parent=self)


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    db.init_db()
    login = LoginWindow()
    login.mainloop()
    if login.user_type:
        app = CantineApp(login.user_type, login.user_info)
        app.mainloop()
