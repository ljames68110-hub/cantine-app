import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import os, sys, subprocess, platform, shutil, threading
from datetime import datetime, timedelta
import database as db
import impression
import updater
import calendrier
import import_liste
import repartition
import ration
import catalogue_data

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

# Catégories du nouveau catalogue (ordre par jour de livraison, lundi→vendredi).
# (nom, emoji, couleur de bande) construites depuis catalogue_data.
try:
    CATEGORIES = [(nom, emoji, bande)
                  for (nom, _pref, _jour, bande, _bg, emoji)
                  in catalogue_data.CATEGORIES_META]
except Exception:
    CATEGORIES = [
        ("BOISSONS", "🥤", "#e86a92"), ("PRODUITS LAITIERS", "🧀", "#e39a90"),
        ("FRUITS & LEGUMES", "🍎", "#e6cf2e"), ("CASHER", "🍽", "#e23b2e"),
        ("ALIMENTAIRE", "🛒", "#ef9433"), ("PRODUITS FRAIS", "🥩", "#3fa9e0"),
        ("HALAL", "🍖", "#b58fc9"), ("ENTRETIEN HYGIENE", "🧴", "#7cc47e"),
        ("PATISSERIES", "🥐", "#e0a93a"), ("TABAC", "🚬", "#d8cba0"),
        ("REVUES", "📖", "#78c92e"),
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


def _identite_bon(nom, prenom, ecrou, batiment, cellule, date_str):
    """Retourne les champs d'identité/date tels quels, ou vides si le mode
    'bon sans info détenu' est actif dans les paramètres. Le contenu du bon
    (articles, quantités, total) n'est jamais affecté par ce mode."""
    if db.get_parametres().get("bon_sans_identite", "0") == "1":
        return "", "", "", "", "", ""
    return nom, prenom, ecrou, batiment, cellule, date_str


JOURS_SEMAINE = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def _rafraichir_feed_calendrier():
    """Met à jour le fichier .ics OneDrive si l'option auto est activée.
    Silencieux : n'interrompt jamais l'utilisateur en cas d'échec."""
    try:
        params = db.get_parametres()
        if params.get("calendrier_auto", "0") == "1":
            calendrier.ecrire_feed_auto(params.get("calendrier_dossier", ""))
    except Exception:
        pass


def _jour_livraison_categorie(categorie):
    """Jour de livraison par défaut d'une catégorie (configuré dans
    Paramètres > Livraison), '' si non défini."""
    return db.get_parametres().get(f"livraison_cat_{categorie}", "")


def _prochain_jour_semaine(date_ref, jour_idx):
    """Retourne la première date >= date_ref tombant sur jour_idx (0=Lundi...6=Dimanche)."""
    ecart = (jour_idx - date_ref.weekday()) % 7
    return date_ref + timedelta(days=ecart)


def _date_ramassage(date_creation):
    """Date du prochain ramassage des bons (mercredi matin par défaut,
    configurable dans Paramètres > Livraison)."""
    params = db.get_parametres()
    jour_nom = params.get("ramassage_jour", "Mercredi")
    jour_idx = JOURS_SEMAINE.index(jour_nom) if jour_nom in JOURS_SEMAINE else 2
    return _prochain_jour_semaine(date_creation, jour_idx)


def _date_debut_distribution(date_creation):
    """Date à partir de laquelle la distribution commence pour un bon créé
    le date_creation : le lundi de la semaine du ramassage + le délai en
    semaines (ex: ramassage mercredi + délai=2 -> lundi 12 jours plus tard,
    soit la 3ème semaine)."""
    params = db.get_parametres()
    try:
        delai = int(params.get("distribution_delai_semaines", "2") or 0)
    except ValueError:
        delai = 2
    ramassage = _date_ramassage(date_creation)
    lundi_semaine_ramassage = ramassage - timedelta(days=ramassage.weekday())
    return lundi_semaine_ramassage + timedelta(weeks=delai)

def _date_distribution_categorie(date_creation, jour_cat=None):
    """Date estimée à laquelle le détenu recevra sa commande : début de la
    période de distribution, ajusté sur le jour hebdo de la catégorie si connu."""
    debut = _date_debut_distribution(date_creation)
    if jour_cat and jour_cat in JOURS_SEMAINE:
        return _prochain_jour_semaine(debut, JOURS_SEMAINE.index(jour_cat))
    return debut


def _infos_livraison_commande(commande, produits_ref, categorie, date_creation=None):
    """Retourne une liste de (jour_semaine_ou_'', date) uniques pour les
    produits d'une commande, triée par date réelle la plus proche en premier.
    jour_livraison du produit prioritaire, sinon jour par défaut de la
    catégorie. Si aucun jour n'est défini, retourne quand même le début de
    la période de distribution."""
    date_creation = date_creation or datetime.now()
    jours_par_produit = {p[0]: (p[6] if len(p) > 6 else "") for p in produits_ref}
    defaut_cat = _jour_livraison_categorie(categorie)
    jours = []
    for pid in commande:
        j = jours_par_produit.get(pid, "") or defaut_cat
        if j and j not in jours:
            jours.append(j)
    if not jours:
        return [("", _date_debut_distribution(date_creation))]
    infos = [(j, _date_distribution_categorie(date_creation, j)) for j in jours]
    infos.sort(key=lambda t: t[1])  # tri chronologique réel (pas alphabétique)
    return infos


def _formater_infos_livraison(infos):
    """Formate une liste [(jour, date), ...] en texte lisible, ex:
    'Mardi 18/08/2026, Mercredi 19/08/2026' ou juste '19/08/2026' si aucun jour."""
    parts = []
    for jour, date in infos:
        d = date.strftime("%d/%m/%Y")
        parts.append(f"{jour} {d}" if jour else d)
    return ", ".join(parts)


# ─────────────────────────────────────────────
# MISES À JOUR — fonctions partagées (Paramètres + bouton rapide)
# ─────────────────────────────────────────────
def _verifier_maj_async(parent, source, chemin, status_cb=None, silencieux=False):
    """Lance la vérification de mise à jour en tâche de fond (ne bloque pas l'UI)."""
    def worker():
        try:
            info = updater.verifier_maj(source, chemin)
        except updater.UpdaterError as e:
            if not silencieux:
                parent.after(0, lambda: _maj_signaler_erreur(parent, status_cb, str(e)))
            return
        except Exception as e:
            if not silencieux:
                parent.after(0, lambda: _maj_signaler_erreur(parent, status_cb, f"Erreur inattendue : {e}"))
            return
        parent.after(0, lambda: _maj_traiter_resultat(parent, info, status_cb, silencieux))
    threading.Thread(target=worker, daemon=True).start()


def _maj_signaler_erreur(parent, status_cb, msg):
    if status_cb:
        status_cb("❌ " + msg, DANGER)
    else:
        messagebox.showerror("Mise à jour", msg, parent=parent)


def _maj_traiter_resultat(parent, info, status_cb, silencieux=False):
    if info is None:
        txt = f"Vous avez déjà la dernière version (v{updater.APP_VERSION})."
        if status_cb:
            status_cb("✅ " + txt, SUCCESS)
        elif not silencieux:
            messagebox.showinfo("Mise à jour", txt, parent=parent)
        return

    version_connue = info.get("version") and info["version"] != "?"
    # Normalise l'affichage : le tag GitHub contient déjà un « v » (ex. "v6.1"),
    # on enlève les v/V en tête pour ne pas afficher « vv6.1 ».
    version_aff = str(info.get("version", "")).lstrip("vV")

    if status_cb:
        label = (f"🆕 Nouvelle version disponible : v{version_aff}" if version_connue
                 else "📦  Fichier d'installation prêt à installer")
        status_cb(label, GOLD)

    notes = (info.get("notes") or "").strip()
    if version_connue:
        msg = f"Une nouvelle version (v{version_aff}) est disponible.\n"
    else:
        msg = "Installer le fichier d'installation sélectionné ?\n"
    if notes:
        msg += "\n" + notes[:400] + "\n"
    msg += "\nMettre à jour maintenant ?\nL'application va se fermer puis redémarrer."
    if messagebox.askyesno("Mise à jour", msg, parent=parent):
        _maj_telecharger_installer(parent, info, status_cb)


def _maj_telecharger_installer(parent, info, status_cb):
    if status_cb:
        status_cb("⬇️  Téléchargement en cours...", TEXT_MUTED)

    def worker():
        try:
            chemin_installeur = updater.obtenir_installeur(info)
            updater.appliquer_maj(chemin_installeur)
        except updater.UpdaterError as e:
            parent.after(0, lambda: _maj_signaler_erreur(parent, status_cb, str(e)))
            return
        except Exception as e:
            parent.after(0, lambda: _maj_signaler_erreur(parent, status_cb, f"Erreur inattendue : {e}"))
            return
        parent.after(0, lambda: _maj_fermer_pour_installer(parent))
    threading.Thread(target=worker, daemon=True).start()


def _maj_fermer_pour_installer(parent):
    messagebox.showinfo("Mise à jour",
        "L'application va se fermer pour terminer la mise à jour.\n"
        "Elle redémarrera automatiquement dans quelques secondes.",
        parent=parent)
    os._exit(0)


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
        db.set_parametre("bon_sans_identite", "0")
        self._demander_budget()
        self.destroy()

    def _login_invite(self):
        win = InviteInfoWindow(self)
        win.grab_set()
        self.wait_window(win)
        if win.result:
            self.user_type = "invite"
            self.user_info = win.result
            db.set_parametre("bon_sans_identite", "1" if win.anonyme else "0")
            self._demander_budget()
            self.destroy()


class InviteInfoWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.result = None
        self.anonyme = False
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

        tk.Button(frm, text="🕶️  Annuler — remplir un bon sans information détenu",
                  command=self._annuler,
                  font=("Helvetica",9), bg="#374151", fg=TEXT,
                  bd=0, cursor="hand2", pady=7,
                  activebackground="#4b5563", activeforeground="white").pack(fill="x", pady=(8,0))

        # Focus on first field
        self.after(100, lambda: list(frm.winfo_children())[0].winfo_children()[-1].focus())

    def _valider(self):
        for key, var in self.vars.items():
            if not var.get().strip():
                messagebox.showwarning("Champ manquant",
                    f"Veuillez renseigner le champ « {key} ».", parent=self)
                return
        self.result = {k: v.get().strip() for k, v in self.vars.items()}
        self.anonyme = False
        self.destroy()

    def _annuler(self):
        self.result = {"nom":"", "prenom":"", "ecrou":"", "batiment":"", "cellule":""}
        self.anonyme = True
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
        if self.user_type == "yoann":
            self.after(2500, self._verifier_maj_demarrage)

    def _verifier_maj_demarrage(self):
        """Vérification silencieuse au démarrage : ne dérange que si une
        mise à jour est réellement disponible (aucun message si tout va bien
        ou si la source de mise à jour est injoignable). La source "locale"
        (fichier .exe choisi manuellement) n'est jamais vérifiée automatiquement
        au démarrage, sinon elle redemanderait à chaque lancement."""
        params = db.get_parametres()
        source = params.get("maj_source", "github")
        if source == "local":
            return
        _verifier_maj_async(self, source, params.get("maj_chemin", ""), silencieux=True)

    def _verifier_maj_manuelle(self):
        """Vérification déclenchée depuis le bouton de l'en-tête."""
        params = db.get_parametres()
        _verifier_maj_async(self, params.get("maj_source", "github"),
                             params.get("maj_chemin", ""))

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

        # ── Barre d'outils (sous le titre) : tous les boutons, sur 2 rangées ──
        toolbar = tk.Frame(self, bg=PANEL_BG)
        toolbar.pack(fill="x")

        def mk(parent, text, cmd, bg=HEADER_BG, fg="white"):
            return tk.Button(parent, text=text, command=cmd,
                             font=("Helvetica", 9), bg=bg, fg=fg,
                             bd=0, relief="flat", cursor="hand2",
                             activebackground=ACCENT, activeforeground="white",
                             pady=5, padx=8)

        specs = []
        if self.user_type == "yoann":
            specs += [
                ("✍️ Signature", self._gerer_signature, HEADER_BG, "white"),
                ("⚙️ Paramètres", self._ouvrir_parametres, HEADER_BG, "white"),
                ("📋 Catalogue", self._ouvrir_catalogue, HEADER_BG, "white"),
                ("🔑 MDP", self._changer_mdp, HEADER_BG, "white"),
                ("🔄 Mises à jour", self._verifier_maj_manuelle, HEADER_BG, "white"),
                ("💰 Créances", lambda: CreancesWindow(self), HEADER_BG, "white"),
                ("🎯 Répartir dettes", self._repartir_dettes, "#7c3aed", "white"),
                ("📦 Réserve", self._ouvrir_reserve, "#0e7490", "white"),
                ("📊 Widget stock", self._ouvrir_widget_stock, "#0e7490", "white"),
                ("🚚 Livraisons", lambda: LivraisonsWindow(self), "#0e7490", "white"),
                ("💶 Remboursements", lambda: RemboursementsWindow(self), "#b45309", "white"),
                ("🍽️ Planning repas", self._ouvrir_planning, "#059669", "white"),
                ("🥗 Ration 15j", self._ouvrir_ration, "#059669", "white"),
                ("🧼 Hygiène", self._ouvrir_hygiene, "#0891b2", "white"),
            ]
        specs += [
            ("💰 Budget", self._modifier_budget, HEADER_BG, "white"),
            ("🏦 Compte", self._ouvrir_compte, HEADER_BG, "white"),
            ("📁 Historique", self._ouvrir_historique, HEADER_BG, "white"),
            ("🖨️ Tout imprimer", self._imprimer_tous_bons, "#7c3aed", "white"),
            ("⏻ Quitter", self._on_close, DANGER, "white"),
        ]

        # Répartition sur 2 rangées équilibrées
        import math as _math
        par_rangee = _math.ceil(len(specs) / 2)
        for i, (text, cmd, bg, fg) in enumerate(specs):
            r, c = divmod(i, par_rangee)
            mk(toolbar, text, cmd, bg, fg).grid(row=r, column=c, padx=2, pady=3,
                                                sticky="ew")
        for c in range(par_rangee):
            toolbar.columnconfigure(c, weight=1)

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

    # ── Import d'une liste de cantine ────────
    def _importer_liste(self):
        chemin = filedialog.askopenfilename(
            parent=self, title="Choisir le fichier de liste de cantine",
            filetypes=[("Fichiers pris en charge", "*.xlsx *.xls *.csv *.txt"),
                       ("Excel", "*.xlsx *.xls"), ("CSV", "*.csv"),
                       ("Texte", "*.txt"), ("Tous les fichiers", "*.*")])
        if not chemin:
            return
        produits = db.get_produits(actif_only=False)
        try:
            resultat = import_liste.analyser_fichier(chemin, produits)
        except Exception as e:
            messagebox.showerror("Import",
                f"Impossible de lire le fichier :\n{e}", parent=self)
            return
        if not resultat["personnes"] or all(
                not p["lignes"] for p in resultat["personnes"]):
            msg = "Aucun produit reconnu dans le fichier."
            if resultat["erreurs"]:
                msg += "\n\n" + "\n".join(resultat["erreurs"][:10])
            messagebox.showwarning("Import", msg, parent=self)
            return
        try:
            ImportListeWindow(self, resultat, self.user_info, self.user_type,
                              None)
        except Exception as e:
            import traceback
            messagebox.showerror("Import",
                f"Erreur à l'ouverture de l'aperçu :\n{e}\n\n{traceback.format_exc()}",
                parent=self)

    # ── Répartition d'articles par dette ─────
    def _repartir_dettes(self):
        # 1) Choix de la source des articles
        total_reserve = db.reserve_total()
        source = SourceRepartitionDialog(self, total_reserve).resultat
        if source is None:
            return

        if source == "reserve":
            articles = db.get_reserve()
            if not articles:
                messagebox.showinfo("Réserve vide",
                    "Votre réserve est vide.\n\nUtilisez « 📦 Réserve » pour y "
                    "importer une liste de cantine d'abord.", parent=self)
                return
            mode = "reserve"
        else:
            # Catalogue : chaque produit actif jusqu'à sa quantité max
            produits = db.get_produits(actif_only=True)
            articles = [{"id":p[0], "nom":p[1], "categorie":p[2],
                         "prix":p[3], "qte":p[4]} for p in produits if p[4] and p[3]>0]
            mode = "catalogue"

        # 2) Saisie des dettes (nom + montant)
        dettes = SaisieDettesDialog(self).resultat
        if not dettes:
            return

        # 3) Calcul de la répartition
        try:
            resultat = repartition.repartir(articles, dettes, marge_euros=3.0)
        except Exception as e:
            import traceback
            messagebox.showerror("Répartition",
                f"Erreur de calcul :\n{e}\n\n{traceback.format_exc()}", parent=self)
            return

        # 4) Prévisualisation + validation
        try:
            RepartitionWindow(self, resultat, mode, self.user_info,
                              self.user_type, None)
        except Exception as e:
            import traceback
            messagebox.showerror("Répartition",
                f"Erreur à l'affichage :\n{e}\n\n{traceback.format_exc()}", parent=self)

    # ── Gestion de la réserve ────────────────
    def _ouvrir_reserve(self):
        ReserveWindow(self)

    def _ouvrir_widget_stock(self):
        """Ouvre le widget de stock. Il est maintenant INTÉGRÉ à l'application :
        on relance le même programme (Cantine.exe) avec l'option « --widget »,
        plus besoin d'un StockWidget.exe séparé."""
        try:
            if getattr(sys, "frozen", False):
                # En .exe : relance Cantine.exe en mode widget
                subprocess.Popen([sys.executable, "--widget"])
            else:
                # En script : relance main.py en mode widget
                base = os.path.dirname(os.path.abspath(__file__))
                subprocess.Popen([sys.executable,
                                  os.path.join(base, "main.py"), "--widget"])
        except Exception as e:
            messagebox.showerror("Widget stock", f"Impossible d'ouvrir : {e}",
                                 parent=self)

    # ── Planning repas ───────────────────────
    def _ouvrir_ration(self):
        RationWindow(self)

    def _ouvrir_hygiene(self):
        HygieneWindow(self)

    def _ouvrir_planning(self):
        try:
            from planning_repas import CadrePlanningRepas
        except Exception as e:
            messagebox.showerror("Planning repas",
                f"Module Planning repas introuvable :\n{e}", parent=self)
            return
        fen = tk.Toplevel(self)
        fen.title("Planning repas")
        fen.geometry("1180x740")
        fen.configure(bg=DARK_BG)
        try:
            dossier_export = os.path.join(APP_DIR, "planning_exports")
            os.makedirs(dossier_export, exist_ok=True)
            CadrePlanningRepas(fen, chemin_db=db.DB_PATH,
                               dossier_export=dossier_export).pack(fill="both", expand=True)
        except Exception as e:
            import traceback
            fen.destroy()
            messagebox.showerror("Planning repas",
                f"Erreur à l'ouverture :\n{e}\n\n{traceback.format_exc()}", parent=self)

    # ── Compte cantinable ────────────────────
    def _ouvrir_compte(self):
        win = CompteWindow(self)
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
            utype       = rest[0] if len(rest) > 0 else "invite"
            est_creance = rest[1] if len(rest) > 1 else 0
            lig_raw  = db.get_lignes_bon(bid)
            lignes   = [{"id":l[2],"nom":l[3],"prix":l[4],"qte":l[5],"total":l[6],"qte_max":0}
                        for l in lig_raw]
            sp       = (sig_path if utype == "yoann" else None) if not est_creance else None
            pdf_path = os.path.join(pdf_dir, f"bon_{bid}_{cat}.pdf")
            try:
                if est_creance:
                    nom_p = prenom_p = ecrou_p = bat_p = cell_p = ""
                    date_p = date
                else:
                    nom_p, prenom_p, ecrou_p, bat_p, cell_p, date_p = _identite_bon(
                        nom, prenom, ecrou, bat, cell, date)
                impression.generer_bon_pdf(cat, nom_p, prenom_p, ecrou_p, bat_p, cell_p,
                                           lignes, total, date_p, pdf_path,
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
class ModifierIdentiteDialog(tk.Toplevel):
    """Dialogue pour modifier les informations détenu d'un bon spécifique,
    sans affecter la session (Yoann ou Invité) ni les autres bons."""
    def __init__(self, master, info_actuelle):
        super().__init__(master)
        self.result = None
        self.title("Modifier les informations détenu")
        self.configure(bg=DARK_BG)
        self.resizable(False, False)
        self.geometry("380x350")
        self._center()
        self._build(info_actuelle)

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - self.winfo_width())  // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build(self, info):
        bar = tk.Frame(self, bg=HEADER_BG, height=44); bar.pack(fill="x"); bar.pack_propagate(False)
        tk.Label(bar, text="✏️  Informations détenu (ce bon uniquement)",
                 font=("Helvetica",11,"bold"), bg=HEADER_BG, fg="white").pack(side="left", padx=12, pady=8)
        frm = tk.Frame(self, bg=DARK_BG, padx=24, pady=16); frm.pack(fill="both", expand=True)
        tk.Label(frm, text="Ces informations ne s'appliquent qu'à ce bon —\n"
                            "elles ne changent ni votre session, ni Paramètres.",
                 font=("Helvetica",8), bg=DARK_BG, fg=TEXT_MUTED,
                 justify="left").pack(anchor="w", pady=(0,10))
        fields = [("Nom","nom"),("Prénom","prenom"),("Écrou","ecrou"),
                  ("Bâtiment","batiment"),("Cellule","cellule")]
        self.vars = {}
        for label, key in fields:
            row = tk.Frame(frm, bg=DARK_BG); row.pack(fill="x", pady=4)
            tk.Label(row, text=label+" :", width=12, anchor="e",
                     font=("Helvetica",10), bg=DARK_BG, fg=TEXT_MUTED).pack(side="left", padx=(0,8))
            v = tk.StringVar(value=info.get(key,"")); self.vars[key] = v
            e = tk.Entry(row, textvariable=v, font=("Helvetica",10),
                     bg=CARD_BG, fg=TEXT, insertbackground=TEXT, bd=0,
                     relief="flat", highlightthickness=1, highlightbackground=BORDER,
                     highlightcolor=ACCENT)
            e.pack(side="left", fill="x", expand=True, ipady=6)
        tk.Button(frm, text="✓  Appliquer à ce bon", command=self._valider,
                  font=("Helvetica",11,"bold"), bg=SUCCESS, fg="white", bd=0,
                  cursor="hand2", pady=8, activebackground="#15803d").pack(fill="x", pady=(14,0))
        self.after(100, lambda: list(frm.winfo_children())[1].winfo_children()[-1].focus())

    def _valider(self):
        self.result = {k: v.get().strip() for k, v in self.vars.items()}
        self.destroy()


class CommandeWindow(tk.Toplevel):
    def __init__(self, master, categorie, user_info, user_type, sig_path,
                 commande_init=None):
        super().__init__(master)
        self.categorie = categorie
        self.user_info = dict(user_info)  # copie locale : ne modifie pas la session
        self.user_type = user_type
        self.mode_anonyme = db.get_parametres().get("bon_sans_identite", "0") == "1"
        self.sig_path  = None if self.mode_anonyme else sig_path
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

        date_frm = tk.Frame(bar, bg=HEADER_BG)
        date_frm.pack(side="right", padx=(0,8), pady=8)
        tk.Label(date_frm, text="📅  Date du bon :", font=("Helvetica",9),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=(0,6))
        self.date_var = tk.StringVar(value=datetime.now().strftime("%d/%m/%Y"))
        tk.Entry(date_frm, textvariable=self.date_var, font=("Helvetica",10),
                 width=11, justify="center", bg=CARD_BG, fg=TEXT,
                 insertbackground=TEXT, bd=0, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT).pack(side="left", ipady=4)
        self.date_var.trace_add("write", lambda *_: self._refresh_bon())

        # ── Bandeau identité ─────────────────────────────────────────────
        id_bar  = tk.Frame(self, bg="#0f172a")
        id_bar.pack(fill="x")
        self.id_bar_var = tk.StringVar()
        tk.Label(id_bar, textvariable=self.id_bar_var,
                 font=("Helvetica",9), bg="#0f172a",
                 fg=GOLD if self.user_type=="yoann" else "#a5b4fc",
                 pady=5).pack(side="left", padx=12)
        self.modifier_id_btn = tk.Button(id_bar, text="✏️  Modifier",
                  command=self._modifier_identite,
                  font=("Helvetica",8), bg="#1e293b", fg=TEXT, bd=0,
                  cursor="hand2", padx=8, pady=2)
        self.modifier_id_btn.pack(side="left", padx=(0,12))
        if self.mode_anonyme:
            self.modifier_id_btn.config(state="disabled")
        self._refresh_id_bar()

        if self.mode_anonyme:
            tk.Label(self, text="🕶️  Mode bon sans information détenu actif — "
                                "signature désactivée, ce bon sera enregistré comme créance",
                     font=("Helvetica",9,"bold"), bg="#78350f", fg="#fef3c7",
                     pady=5).pack(fill="x")

        # ── Rappel stock bas (à racheter) ────────────────────────────────
        try:
            bas = db.get_stock_bas()
        except Exception:
            bas = []
        if bas:
            ici = [b for b in bas if b.get("categorie") == self.categorie]
            autres = [b for b in bas if b.get("categorie") != self.categorie]
            parts = []
            if ici:
                parts.append("dans cette catégorie : "
                             + ", ".join(f"{b['nom']} (reste {b['qte']})" for b in ici))
            if autres:
                parts.append("autres : "
                             + ", ".join(f"{b['nom']} ({b['qte']})" for b in autres[:6])
                             + ("…" if len(autres) > 6 else ""))
            txt = "🛒  À racheter — bientôt en rupture dans ton stock → " + "  |  ".join(parts)
            tk.Label(self, text=txt, font=("Helvetica", 9, "bold"),
                     bg="#7c2d12", fg="#fed7aa", anchor="w", justify="left",
                     wraplength=1100, pady=6, padx=12).pack(fill="x")

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
        self.livraison_var = tk.StringVar(value="")
        self.livraison_lbl = tk.Label(tot_frm, textvariable=self.livraison_var,
                 font=("Helvetica",9,"bold"), bg=ACCENT, fg="#fef3c7")

        # Créance (la personne me doit de l'argent)
        creance_frm = tk.Frame(right, bg="#111827")
        creance_frm.grid(row=4, column=0, sticky="ew", padx=8, pady=(0,4))
        self.creance_var = tk.BooleanVar(value=self.mode_anonyme)
        self.creance_chk = tk.Checkbutton(creance_frm,
                       text="💰  Cette personne me doit de l'argent (créance)",
                       variable=self.creance_var, command=self._toggle_creance,
                       bg="#111827", fg=TEXT, activebackground="#111827",
                       activeforeground=TEXT, selectcolor=CARD_BG,
                       font=("Helvetica",9,"bold"), anchor="w")
        self.creance_chk.pack(fill="x")
        if self.mode_anonyme:
            self.creance_chk.config(state="disabled",
                text="💰  Créance (obligatoire — bon sans information détenu)")
        self.creance_nom_frm = tk.Frame(creance_frm, bg="#111827")
        tk.Label(self.creance_nom_frm, text="Nom :", font=("Helvetica",9),
                 bg="#111827", fg=TEXT_MUTED).pack(side="left", padx=(0,6))
        self.creance_nom_var = tk.StringVar()
        tk.Entry(self.creance_nom_frm, textvariable=self.creance_nom_var,
                 font=("Helvetica",9), bg=CARD_BG, fg=TEXT, insertbackground=TEXT,
                 bd=0, relief="flat", highlightthickness=1,
                 highlightbackground=BORDER, highlightcolor=ACCENT).pack(
                     side="left", fill="x", expand=True, ipady=4)
        if self.mode_anonyme:
            self.creance_nom_frm.pack(fill="x", pady=(4,0))

        # Boutons actions
        btn_frm = tk.Frame(right, bg="#111827")
        btn_frm.grid(row=5, column=0, sticky="ew", padx=8, pady=(0,8))
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

    def _refresh_id_bar(self):
        ui = self.user_info
        badge   = "👤" if self.user_type == "yoann" else "👥"
        sig_lbl = "   ✍️ Signature activée" if self.sig_path else ""
        self.id_bar_var.set(
            f"  {badge}  {ui.get('nom','').upper()} {ui.get('prenom','')}   "
            f"│  Écrou : {ui.get('ecrou','')}   "
            f"│  Bât. {ui.get('batiment','')} / Cell. {ui.get('cellule','')}"
            f"{sig_lbl}")

    def _modifier_identite(self):
        win = ModifierIdentiteDialog(self, self.user_info)
        win.grab_set()
        self.wait_window(win)
        if win.result:
            self.user_info = win.result
            self._refresh_id_bar()

    def _load_products(self, filtre=""):
        import re as _re
        self.produits = db.get_produits(self.categorie)
        # Tri numérique : AC1, AC2, AC3... pas AC1, AC10, AC11
        self.produits = sorted(self.produits,
            key=lambda p: int(_re.sub(r"[^0-9]", "", p[0]) or "0"))
        self.tree_prod.delete(*self.tree_prod.get_children())
        for p in self.produits:
            pid, nom, _, prix, qmax, _, _jour = p
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
        _, nom, _, prix, qmax, _, _jour = prod
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
            if not self.mode_anonyme:
                self.creance_var.set(False)
                self.creance_nom_var.set("")
                self.creance_nom_frm.pack_forget()

    def _toggle_creance(self):
        if self.creance_var.get():
            self.creance_nom_frm.pack(fill="x", pady=(4,0))
        else:
            self.creance_nom_frm.pack_forget()

    def _parse_date_bon(self):
        """Date choisie pour le bon (anti-datation possible). Retourne un
        datetime, ou celui d'aujourd'hui si le champ est vide/invalide."""
        try:
            return datetime.strptime(self.date_var.get().strip(), "%d/%m/%Y")
        except (ValueError, AttributeError):
            return None

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

        if self.commande:
            date_ref = self._parse_date_bon() or datetime.now()
            infos = _infos_livraison_commande(self.commande, self.produits,
                                              self.categorie, date_creation=date_ref)
            self.livraison_var.set(f"🚚  Livraison estimée : {_formater_infos_livraison(infos)}")
            self.livraison_lbl.pack(pady=(0,8))
        else:
            self.livraison_var.set("")
            self.livraison_lbl.pack_forget()

    def _sauvegarder(self):
        if not self.commande:
            messagebox.showwarning("Bon vide",
                "Ajoutez au moins un produit avant de sauvegarder.", parent=self)
            return

        if self.date_var.get().strip() and self._parse_date_bon() is None:
            messagebox.showwarning("Date invalide",
                "La date du bon doit être au format jj/mm/aaaa (ex: 15/07/2026).",
                parent=self)
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

        date_creation = self._parse_date_bon() or datetime.now()
        date_str = date_creation.strftime("%d/%m/%Y")
        lignes, total = [], 0.0
        for pid, d in self.commande.items():
            st = d["prix"] * d["qte"]
            total += st
            lignes.append({"id":pid, "nom":d["nom"], "prix":d["prix"],
                           "qte":d["qte"], "total":st, "qte_max":d["qte_max"]})
        ui = self.user_info

        est_creance  = self.creance_var.get() or self.mode_anonyme
        nom_creance  = self.creance_nom_var.get().strip() if est_creance else ""
        jour_creance = ""
        date_creance = ""
        if est_creance:
            infos = _infos_livraison_commande(self.commande, self.produits,
                                              self.categorie, date_creation=date_creation)
            jour_creance = ", ".join(j for j, _ in infos if j)
            date_creance = infos[0][1].strftime("%d/%m/%Y")  # date la plus proche
        if est_creance and not nom_creance:
            messagebox.showwarning("Nom manquant",
                "Indiquez le nom de la personne pour la créance.", parent=self)
            return

        bon_id = db.sauvegarder_bon(
            self.categorie, ui["nom"], ui["prenom"], ui["ecrou"],
            ui["batiment"], ui["cellule"], lignes, total, date_str, self.user_type,
            est_creance=est_creance, nom_creance=nom_creance, jour_creance=jour_creance,
            date_creance=date_creance)

        if est_creance:
            _rafraichir_feed_calendrier()

        # ── Auto-enregistrement dans le compte cantinable ──
        try:
            db.compte_ajouter_transaction(
                date_str,
                f"Cantine {self.categorie} — Bon #{bon_id}",
                -round(total, 2),
                "Cantine",
                bon_id)
        except Exception:
            pass

        pdf_dir = os.path.join(APP_DIR, "bons_pdf")
        os.makedirs(pdf_dir, exist_ok=True)
        fname    = f"bon_{self.categorie}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = os.path.join(pdf_dir, fname)
        try:
            if est_creance:
                # Créance : ni identité ni signature sur le bon imprimé
                nom_p = prenom_p = ecrou_p = bat_p = cell_p = ""
                date_p = date_str
                sig_pdf = None
            else:
                nom_p, prenom_p, ecrou_p, bat_p, cell_p, date_p = _identite_bon(
                    ui["nom"], ui["prenom"], ui["ecrou"], ui["batiment"], ui["cellule"], date_str)
                sig_pdf = self.sig_path
            impression.generer_bon_pdf(
                self.categorie, nom_p, prenom_p, ecrou_p, bat_p, cell_p, lignes, total, date_p,
                pdf_path, signature_path=sig_pdf)
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
        self.livraison_var.set("")
        self.livraison_lbl.pack_forget()
        self.creance_nom_var.set("")
        if self.mode_anonyme:
            self.creance_var.set(True)
            self.creance_nom_frm.pack(fill="x", pady=(4,0))
        else:
            self.creance_var.set(False)
            self.creance_nom_frm.pack_forget()


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

        # ── Onglet 4 : Mises à jour ───────────────────────────────────────
        tab_maj = tk.Frame(nb, bg=DARK_BG)
        nb.add(tab_maj, text="  🔄  Mises à jour  ")
        self._build_maj(tab_maj, params)

        # ── Onglet 5 : Impression ───────────────────────────────────────
        tab_impr = tk.Frame(nb, bg=DARK_BG)
        nb.add(tab_impr, text="  🖨️  Impression  ")
        self._build_impression(tab_impr, params)

        # ── Onglet 6 : Livraison ────────────────────────────────────────
        tab_livr = tk.Frame(nb, bg=DARK_BG)
        nb.add(tab_livr, text="  🚚  Livraison  ")
        self._build_livraison(tab_livr, params)

        # ── Onglet 7 : Calendrier ───────────────────────────────────────
        tab_cal = tk.Frame(nb, bg=DARK_BG)
        nb.add(tab_cal, text="  📆  Calendrier  ")
        self._build_calendrier(tab_cal, params)

        # ── Onglet 8 : Données partagées ────────────────────────────────
        tab_part = tk.Frame(nb, bg=DARK_BG)
        nb.add(tab_part, text="  🔗  Données partagées  ")
        self._build_donnees_partagees(tab_part)

    def _build_donnees_partagees(self, parent):
        """Onglet : stocker la base sur un disque partagé (ex. D:\\) pour que
        les 2 systèmes d'un même PC (double boot) aient les mêmes données,
        sans jamais rien importer."""
        frm = tk.Frame(parent, bg=DARK_BG, padx=24, pady=16)
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text="🔗  Partager les données entre mes systèmes",
                 font=("Helvetica", 13, "bold"), bg=DARK_BG, fg=TEXT).pack(anchor="w")
        tk.Label(frm,
                 text=("Place toute la base de données (dettes, historique, stock, "
                       "catalogue…) sur un disque partagé comme D:\\.\n"
                       "Les deux systèmes utiliseront alors le MÊME fichier : "
                       "tout ce que tu ajoutes d'un côté est déjà là de l'autre, "
                       "plus aucun import.\n\n"
                       "⚠️ Fais-le d'abord sur le système qui a tes données à jour "
                       "(il sera recopié). L'autre système détectera ensuite le "
                       "dossier tout seul."),
                 font=("Helvetica", 9), bg=DARK_BG, fg=TEXT_MUTED,
                 justify="left", wraplength=520).pack(anchor="w", pady=(6, 14))

        # État actuel
        etat = tk.Frame(frm, bg=CARD_BG, padx=14, pady=12)
        etat.pack(fill="x")
        self._lbl_part_etat = tk.Label(etat, text="", font=("Helvetica", 10, "bold"),
                                       bg=CARD_BG, fg=TEXT, justify="left", anchor="w",
                                       wraplength=500)
        self._lbl_part_etat.pack(anchor="w")
        self._lbl_part_chemin = tk.Label(etat, text="", font=("Consolas", 9),
                                         bg=CARD_BG, fg=TEXT_MUTED, justify="left",
                                         anchor="w", wraplength=500)
        self._lbl_part_chemin.pack(anchor="w", pady=(4, 0))
        self._rafraichir_etat_partage()

        # Boutons
        btns = tk.Frame(frm, bg=DARK_BG)
        btns.pack(fill="x", pady=(16, 0))
        tk.Button(btns, text="📂  Choisir le dossier partagé (ex : D:\\)",
                  command=self._choisir_dossier_partage,
                  font=("Helvetica", 11, "bold"), bg=ACCENT, fg="white", bd=0,
                  cursor="hand2", pady=8).pack(fill="x")
        tk.Button(btns, text="↩  Revenir à une base locale (ce système seulement)",
                  command=self._desactiver_partage,
                  font=("Helvetica", 9), bg=CARD_BG, fg=TEXT_MUTED, bd=0,
                  cursor="hand2", pady=6).pack(fill="x", pady=(8, 0))

    def _rafraichir_etat_partage(self):
        try:
            dossier = db.dossier_partage_actuel()
        except Exception:
            dossier = ""
        if dossier:
            self._lbl_part_etat.config(text="✅  Données PARTAGÉES", fg=SUCCESS)
            self._lbl_part_chemin.config(
                text="Base de données : %s" % os.path.join(dossier, "cantine.db"))
        else:
            self._lbl_part_etat.config(text="📍  Données LOCALES (propres à ce système)",
                                       fg=GOLD)
            self._lbl_part_chemin.config(text="Base de données : %s" % db.DB_PATH)

    def _choisir_dossier_partage(self):
        dossier = filedialog.askdirectory(
            title="Choisis le disque/dossier partagé (ex : D:\\)",
            parent=self)
        if not dossier:
            return
        try:
            nouveau = db.definir_dossier_partage(dossier)
        except Exception as e:
            messagebox.showerror("Partage impossible", str(e), parent=self)
            return
        if messagebox.askyesno(
                "Redémarrage nécessaire",
                "C'est prêt ! La base sera partagée ici :\n\n%s\n\n"
                "L'application doit redémarrer pour l'utiliser.\n"
                "Redémarrer maintenant ?" % nouveau, parent=self):
            self._redemarrer_app()
        else:
            self._rafraichir_etat_partage()

    def _desactiver_partage(self):
        if not messagebox.askyesno(
                "Revenir en local",
                "Ce système utilisera à nouveau sa propre base locale "
                "(les données partagées sur le disque ne sont pas supprimées).\n\n"
                "Continuer ?", parent=self):
            return
        try:
            db.desactiver_dossier_partage()
        except Exception as e:
            messagebox.showerror("Erreur", str(e), parent=self)
            return
        if messagebox.askyesno("Redémarrage nécessaire",
                               "Enregistré. Redémarrer l'application maintenant ?",
                               parent=self):
            self._redemarrer_app()
        else:
            self._rafraichir_etat_partage()

    def _redemarrer_app(self):
        """Relance l'application puis ferme l'instance actuelle."""
        try:
            if getattr(sys, "frozen", False):
                subprocess.Popen([sys.executable])
            else:
                base = os.path.dirname(os.path.abspath(__file__))
                subprocess.Popen([sys.executable, os.path.join(base, "main.py")])
        except Exception as e:
            messagebox.showerror("Redémarrage",
                                 "Ferme et rouvre l'application manuellement.\n%s" % e,
                                 parent=self)
            return
        # Ferme toute l'application
        try:
            self.master.destroy()
        except Exception:
            try:
                self.destroy()
            except Exception:
                pass
        os._exit(0)

    def _build_calendrier(self, parent, params):
        """Onglet de configuration de la synchronisation calendrier (.ics)
        vers un dossier OneDrive, auquel One Calendar peut s'abonner."""
        frm = tk.Frame(parent, bg=DARK_BG, padx=24, pady=16)
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text="Synchronisation calendrier (One Calendar / OneDrive)",
                 font=("Helvetica",12,"bold"), bg=DARK_BG, fg=TEXT).pack(anchor="w", pady=(0,8))

        self.cal_auto_var = tk.BooleanVar(
            value=params.get("calendrier_auto","0") == "1")
        tk.Checkbutton(frm,
            text="Mettre à jour automatiquement un fichier calendrier des créances",
            variable=self.cal_auto_var,
            bg=DARK_BG, fg=TEXT, activebackground=DARK_BG, activeforeground=TEXT,
            selectcolor=CARD_BG, font=("Helvetica",10,"bold"),
            anchor="w").pack(fill="x", pady=(0,8))

        row = tk.Frame(frm, bg=DARK_BG); row.pack(fill="x", pady=(4,4))
        tk.Label(row, text="Dossier OneDrive :", width=16, anchor="e",
                 font=("Helvetica",10), bg=DARK_BG, fg=TEXT_MUTED).pack(side="left", padx=(0,8))
        self.cal_dossier_var = tk.StringVar(value=params.get("calendrier_dossier",""))
        tk.Entry(row, textvariable=self.cal_dossier_var,
                 font=("Helvetica",10), bg=CARD_BG, fg=TEXT, insertbackground=TEXT, bd=0,
                 relief="flat", highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT).pack(side="left", fill="x", expand=True, ipady=6)
        tk.Button(row, text="…", command=self._choisir_dossier_cal,
                  font=("Helvetica",10,"bold"), bg=CARD_BG, fg=TEXT, bd=0,
                  cursor="hand2", padx=10).pack(side="left", padx=(6,0))

        tk.Label(frm,
            text="Choisissez un dossier de votre OneDrive (ex : Documents\\Cantine). "
                 "L'appli y écrit et met à jour le fichier « creances_cantine.ics » "
                 "à chaque changement de créance. OneDrive le synchronise, et vous "
                 "abonnez One Calendar à ce fichier une seule fois.",
            font=("Helvetica",8), bg=DARK_BG, fg=TEXT_MUTED,
            wraplength=580, justify="left").pack(anchor="w", pady=(6,10))

        btns = tk.Frame(frm, bg=DARK_BG); btns.pack(fill="x", pady=(4,4))
        tk.Button(btns, text="💾  Enregistrer", command=self._sauvegarder_calendrier,
                  font=("Helvetica",10,"bold"), bg=SUCCESS, fg="white", bd=0,
                  cursor="hand2", pady=8).pack(side="left", fill="x", expand=True, padx=(0,4))
        tk.Button(btns, text="🔄  Générer maintenant", command=self._generer_feed_maintenant,
                  font=("Helvetica",10,"bold"), bg=ACCENT, fg="white", bd=0,
                  cursor="hand2", pady=8).pack(side="left", fill="x", expand=True, padx=(4,0))

        self.cal_status_lbl = tk.Label(frm, text="", font=("Helvetica",9),
                 bg=DARK_BG, fg=TEXT_MUTED, wraplength=580, justify="left")
        self.cal_status_lbl.pack(anchor="w", pady=(12,10))

        tk.Frame(frm, bg=BORDER, height=1).pack(fill="x", pady=(0,10))
        tk.Label(frm, text="Comment s'abonner dans One Calendar (à faire une fois) :",
                 font=("Helvetica",9,"bold"), bg=DARK_BG, fg=TEXT).pack(anchor="w")
        tk.Label(frm,
            text="1. Sur onedrive.com, ouvrez le dossier choisi, clic droit sur "
                 "« creances_cantine.ics » → Partager → Copier le lien.\n"
                 "2. Dans One Calendar : Réglages → Comptes → Ajouter → "
                 "« Abonnement à un calendrier (URL/ICS) », collez le lien.\n"
                 "3. One Calendar rafraîchit ensuite les créances automatiquement.",
            font=("Helvetica",8), bg=DARK_BG, fg=TEXT_MUTED,
            wraplength=580, justify="left").pack(anchor="w", pady=(2,0))

    def _choisir_dossier_cal(self):
        dossier = filedialog.askdirectory(parent=self,
                    title="Choisir le dossier OneDrive pour le calendrier")
        if dossier:
            self.cal_dossier_var.set(dossier)

    def _sauvegarder_calendrier(self):
        db.set_parametre("calendrier_auto", "1" if self.cal_auto_var.get() else "0")
        db.set_parametre("calendrier_dossier", self.cal_dossier_var.get().strip())
        messagebox.showinfo("Enregistré",
            "Paramètres calendrier enregistrés.", parent=self)

    def _generer_feed_maintenant(self):
        dossier = self.cal_dossier_var.get().strip()
        if not dossier:
            self.cal_status_lbl.config(text="❌ Indiquez d'abord un dossier.", fg=DANGER)
            return
        chemin = calendrier.ecrire_feed_auto(dossier)
        if chemin:
            self.cal_status_lbl.config(
                text=f"✅ Fichier calendrier écrit :\n{chemin}", fg=SUCCESS)
        else:
            self.cal_status_lbl.config(
                text="❌ Dossier introuvable ou erreur d'écriture.", fg=DANGER)

    def _build_livraison(self, parent, params):
        """Onglet de configuration du cycle ramassage/distribution et du
        jour de livraison par défaut de chaque catégorie."""
        frm = tk.Frame(parent, bg=DARK_BG, padx=24, pady=16)
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text="Cycle de ramassage et distribution",
                 font=("Helvetica",12,"bold"), bg=DARK_BG, fg=TEXT).pack(anchor="w", pady=(0,8))

        row_r = tk.Frame(frm, bg=DARK_BG); row_r.pack(fill="x", pady=3)
        tk.Label(row_r, text="Jour de ramassage des bons :", width=28, anchor="w",
                 font=("Helvetica",9), bg=DARK_BG, fg=TEXT_MUTED).pack(side="left")
        self.ramassage_jour_var = tk.StringVar(value=params.get("ramassage_jour","Mercredi"))
        ttk.Combobox(row_r, textvariable=self.ramassage_jour_var, values=JOURS_SEMAINE,
                    state="readonly", width=14).pack(side="left")

        row_d = tk.Frame(frm, bg=DARK_BG); row_d.pack(fill="x", pady=3)
        tk.Label(row_d, text="Délai avant distribution (semaines) :", width=28, anchor="w",
                 font=("Helvetica",9), bg=DARK_BG, fg=TEXT_MUTED).pack(side="left")
        self.delai_var = tk.StringVar(value=params.get("distribution_delai_semaines","2"))
        tk.Spinbox(row_d, from_=0, to=12, textvariable=self.delai_var, width=5,
                  font=("Helvetica",9), bg=CARD_BG, fg=TEXT, bd=0,
                  buttonbackground=CARD_BG, insertbackground=TEXT).pack(side="left", ipady=2)

        tk.Label(frm,
            text="Ex : ramassage le mercredi + délai de 2 semaines = distribution\n"
                 "à partir du lundi de la 3ème semaine suivant le ramassage\n"
                 "(soit 12 jours après un ramassage du mercredi).",
            font=("Helvetica",8), bg=DARK_BG, fg=TEXT_MUTED,
            wraplength=580, justify="left").pack(anchor="w", pady=(4,16))

        tk.Frame(frm, bg=BORDER, height=1).pack(fill="x", pady=(0,14))

        tk.Label(frm, text="Jour de livraison par défaut, par catégorie",
                 font=("Helvetica",12,"bold"), bg=DARK_BG, fg=TEXT).pack(anchor="w", pady=(0,4))
        tk.Label(frm,
            text="Laissez sur « Non défini » si la catégorie n'a pas de jour fixe.\n"
                 "Pour une exception au sein d'une catégorie (ex : les fromages livrés\n"
                 "un autre jour que le reste des Fruits & Légumes), utilisez la colonne\n"
                 "Livraison du Catalogue, produit par produit — elle prend le dessus.",
            font=("Helvetica",8), bg=DARK_BG, fg=TEXT_MUTED,
            wraplength=580, justify="left").pack(anchor="w", pady=(0,10))

        self.livraison_cat_vars = {}
        for cat_nom, emoji, _ in CATEGORIES:
            row = tk.Frame(frm, bg=DARK_BG); row.pack(fill="x", pady=2)
            tk.Label(row, text=f"{emoji}  {cat_nom} :", width=24, anchor="w",
                     font=("Helvetica",9), bg=DARK_BG, fg=TEXT).pack(side="left")
            v = tk.StringVar(value=params.get(f"livraison_cat_{cat_nom}","") or "(Non défini)")
            self.livraison_cat_vars[cat_nom] = v
            ttk.Combobox(row, textvariable=v, values=["(Non défini)"] + JOURS_SEMAINE,
                        state="readonly", width=14).pack(side="left")

        tk.Button(frm, text="💾  Enregistrer", command=self._sauvegarder_livraison,
                  font=("Helvetica",11,"bold"), bg=SUCCESS, fg="white", bd=0,
                  cursor="hand2", pady=8).pack(fill="x", pady=(16,0))

    def _sauvegarder_livraison(self):
        db.set_parametre("ramassage_jour", self.ramassage_jour_var.get())
        try:
            delai = int(self.delai_var.get())
        except ValueError:
            delai = 2
        db.set_parametre("distribution_delai_semaines", str(delai))
        for cat_nom, var in self.livraison_cat_vars.items():
            v = var.get()
            v = "" if v == "(Non défini)" else v
            db.set_parametre(f"livraison_cat_{cat_nom}", v)
        messagebox.showinfo("Enregistré",
            "Paramètres de livraison enregistrés.", parent=self)

    def _build_impression(self, parent, params):
        """Onglet pour activer le mode d'impression des bons sans info détenu."""
        # Zone défilable (l'onglet a beaucoup de réglages)
        canvas = tk.Canvas(parent, bg=DARK_BG, highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        frm = tk.Frame(canvas, bg=DARK_BG, padx=30, pady=24)
        win_id = canvas.create_window((0, 0), window=frm, anchor="nw")
        def _maj_scroll(_=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(win_id, width=canvas.winfo_width())
        frm.bind("<Configure>", _maj_scroll)
        canvas.bind("<Configure>", _maj_scroll)
        # Molette souris
        def _molette(e):
            try:
                canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
            except tk.TclError:
                pass
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _molette))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        tk.Label(frm, text="Confidentialité des bons imprimés",
                 font=("Helvetica",13,"bold"), bg=DARK_BG, fg=TEXT).pack(anchor="w", pady=(0,12))

        self.sans_identite_var = tk.BooleanVar(
            value=params.get("bon_sans_identite","0") == "1")
        tk.Checkbutton(frm,
            text="Générer les bons sans informations détenu\n"
                 "(nom, prénom, écrou, bâtiment, cellule et date laissés vides)",
            variable=self.sans_identite_var,
            bg=DARK_BG, fg=TEXT, activebackground=DARK_BG, activeforeground=TEXT,
            selectcolor=CARD_BG, font=("Helvetica",10,"bold"),
            anchor="w", justify="left").pack(fill="x", pady=(0,10))

        tk.Label(frm,
            text="Le tableau des articles, les quantités et le total restent "
                 "toujours affichés normalement — seule l'identité est masquée "
                 "sur le PDF imprimé. Les enregistrements internes (historique, "
                 "budget, compte cantinable) ne sont pas affectés.\n\n"
                 "S'applique à tous les bons imprimés : nouveau bon, "
                 "\"Tout imprimer\" et réimpression depuis l'historique.\n\n"
                 "Quand ce mode est actif, la signature automatique est désactivée "
                 "et chaque nouveau bon est automatiquement enregistré comme "
                 "créance (avec demande du nom de la personne), puisqu'aucune "
                 "identité n'est associée au bon papier.\n\n"
                 "S'active aussi automatiquement si l'invité clique sur "
                 "« Annuler » à l'écran d'identification.",
            font=("Helvetica",8), bg=DARK_BG, fg=TEXT_MUTED,
            wraplength=560, justify="left").pack(anchor="w", pady=(0,14))

        tk.Frame(frm, bg=BORDER, height=1).pack(fill="x", pady=(0,12))

        # ── Mode d'impression : couleur ou noir sur papier pré-imprimé ───────
        tk.Label(frm, text="Mode d'impression",
                 font=("Helvetica",13,"bold"), bg=DARK_BG, fg=TEXT).pack(anchor="w", pady=(0,8))
        self.impression_mode_var = tk.StringVar(value=params.get("impression_mode","couleur"))
        tk.Radiobutton(frm,
            text="🎨  Bon complet en couleur (l'appli imprime tout, fond compris)",
            value="couleur", variable=self.impression_mode_var,
            bg=DARK_BG, fg=TEXT, activebackground=DARK_BG, activeforeground=TEXT,
            selectcolor=CARD_BG, font=("Helvetica",10), anchor="w").pack(fill="x", pady=2)
        tk.Radiobutton(frm,
            text="🖨️  Texte noir seul (sur papier pré-imprimé fourni) — économie d'encre",
            value="noir", variable=self.impression_mode_var,
            bg=DARK_BG, fg=TEXT, activebackground=DARK_BG, activeforeground=TEXT,
            selectcolor=CARD_BG, font=("Helvetica",10), anchor="w").pack(fill="x", pady=2)

        tk.Label(frm,
            text="En mode « texte noir seul », l'appli n'imprime que les valeurs "
                 "(nom, écrou, articles, date, signature) en noir — les fonds de "
                 "couleur, cadres et libellés du papier de l'administration ne sont "
                 "pas réimprimés. Zéro encre couleur.",
            font=("Helvetica",8), bg=DARK_BG, fg=TEXT_MUTED,
            wraplength=560, justify="left").pack(anchor="w", pady=(4,10))

        # ── Calage fin (offsets en mm) ───────────────────────────────────────
        cal = tk.Frame(frm, bg=DARK_BG); cal.pack(fill="x", pady=(0,4))
        tk.Label(cal, text="Calage (mm) — décalage horizontal :", anchor="w",
                 font=("Helvetica",9), bg=DARK_BG, fg=TEXT_MUTED).pack(side="left")
        self.offset_x_var = tk.StringVar(value=params.get("impression_offset_x","0"))
        tk.Spinbox(cal, from_=-30, to=30, increment=1, textvariable=self.offset_x_var,
                   width=5, font=("Helvetica",9), bg=CARD_BG, fg=TEXT, bd=0,
                   buttonbackground=CARD_BG, insertbackground=TEXT).pack(side="left", padx=6)
        tk.Label(cal, text="  vertical :", anchor="w",
                 font=("Helvetica",9), bg=DARK_BG, fg=TEXT_MUTED).pack(side="left")
        self.offset_y_var = tk.StringVar(value=params.get("impression_offset_y","0"))
        tk.Spinbox(cal, from_=-30, to=30, increment=1, textvariable=self.offset_y_var,
                   width=5, font=("Helvetica",9), bg=CARD_BG, fg=TEXT, bd=0,
                   buttonbackground=CARD_BG, insertbackground=TEXT).pack(side="left", padx=6)

        tk.Label(frm,
            text="Si le texte est légèrement décalé sur le papier pré-imprimé, ajustez "
                 "ici : + horizontal décale vers la droite, + vertical vers le haut. "
                 "Faites un test d'impression, puis ajustez de quelques mm si besoin.",
            font=("Helvetica",8), bg=DARK_BG, fg=TEXT_MUTED,
            wraplength=560, justify="left").pack(anchor="w", pady=(4,10))

        # ── Géométrie du tableau pré-imprimé (mode noir) ─────────────────────
        tk.Frame(frm, bg=BORDER, height=1).pack(fill="x", pady=(2,10))
        tk.Label(frm, text="Grille du papier pré-imprimé (mode noir)",
                 font=("Helvetica",11,"bold"), bg=DARK_BG, fg=TEXT).pack(anchor="w", pady=(0,6))

        geo = tk.Frame(frm, bg=DARK_BG); geo.pack(fill="x", pady=(0,4))
        tk.Label(geo, text="Position 1re ligne (mm du haut) :", width=30, anchor="w",
                 font=("Helvetica",9), bg=DARK_BG, fg=TEXT_MUTED).pack(side="left")
        self.impr_y1_var = tk.StringVar(value=params.get("impr_y1","79"))
        tk.Spinbox(geo, from_=30, to=120, increment=1, textvariable=self.impr_y1_var,
                   width=6, font=("Helvetica",9), bg=CARD_BG, fg=TEXT, bd=0,
                   buttonbackground=CARD_BG, insertbackground=TEXT).pack(side="left", padx=6)

        geo2 = tk.Frame(frm, bg=DARK_BG); geo2.pack(fill="x", pady=(0,4))
        tk.Label(geo2, text="Espacement entre lignes (mm) :", width=30, anchor="w",
                 font=("Helvetica",9), bg=DARK_BG, fg=TEXT_MUTED).pack(side="left")
        self.impr_pas_var = tk.StringVar(value=params.get("impr_pas","5.15"))
        tk.Spinbox(geo2, from_=3.0, to=8.0, increment=0.05, format="%.2f",
                   textvariable=self.impr_pas_var,
                   width=6, font=("Helvetica",9), bg=CARD_BG, fg=TEXT, bd=0,
                   buttonbackground=CARD_BG, insertbackground=TEXT).pack(side="left", padx=6)

        tk.Label(frm,
            text="Réglage crucial pour éviter que les valeurs « glissent » ligne après "
                 "ligne. Utilisez le bouton « Test d'alignement » ci-dessous : il imprime "
                 "les numéros 1, 2, 3… dans la colonne N°. Posez la feuille sur le papier "
                 "de l'administration : si les numéros glissent vers le bas au fil des "
                 "lignes, réduisez l'espacement ; s'ils remontent, augmentez-le. Ajustez "
                 "la position de la 1re ligne pour caler le début.",
            font=("Helvetica",8), bg=DARK_BG, fg=TEXT_MUTED,
            wraplength=560, justify="left").pack(anchor="w", pady=(4,10))

        # ── Décalage vertical par catégorie ──────────────────────────────────
        # Certains blocs pré-imprimés (ex : Hygiène) sont décalés par rapport
        # aux autres. On corrige UNE catégorie sans toucher aux autres.
        self._CATS_DY = [(nom, impression._cat_slug(nom))
                         for (nom, *_r) in catalogue_data.CATEGORIES_META]
        _premier_nom, _premier_slug = self._CATS_DY[0]
        catf = tk.Frame(frm, bg=DARK_BG); catf.pack(fill="x", pady=(0,4))
        tk.Label(catf, text="Décalage vertical d'une catégorie :", width=30,
                 anchor="w", font=("Helvetica",9), bg=DARK_BG,
                 fg=TEXT_MUTED).pack(side="left")
        self.dy_cat_var = tk.StringVar(value=_premier_nom)
        om = tk.OptionMenu(catf, self.dy_cat_var,
                           *[n for n, _ in self._CATS_DY],
                           command=lambda _=None: self._maj_dy_cat())
        om.config(font=("Helvetica",9), bg=CARD_BG, fg=TEXT, bd=0,
                  highlightthickness=0, activebackground=CARD_BG,
                  width=18); om.pack(side="left", padx=6)
        self._dy_values = {slug: params.get(f"impr_dy_{slug}", "0")
                           for _, slug in self._CATS_DY}
        self._dy_cat_current = _premier_slug
        self.dy_val_var = tk.StringVar(
            value=self._dy_values.get(_premier_slug, "0"))
        tk.Spinbox(catf, from_=-15, to=15, increment=0.5, format="%.1f",
                   textvariable=self.dy_val_var, width=6, font=("Helvetica",9),
                   bg=CARD_BG, fg=TEXT, bd=0, buttonbackground=CARD_BG,
                   insertbackground=TEXT).pack(side="left", padx=6)
        tk.Label(catf, text="mm", font=("Helvetica",9), bg=DARK_BG,
                 fg=TEXT_MUTED).pack(side="left")
        tk.Label(frm,
            text="Positif = descend le texte, négatif = le remonte, pour cette "
                 "catégorie uniquement. Ex. : l'Hygiène est réglée pour descendre "
                 "car son bloc papier est plus bas que les autres. Choisissez la "
                 "catégorie, ajustez, puis Enregistrer.",
            font=("Helvetica",8), bg=DARK_BG, fg=TEXT_MUTED,
            wraplength=560, justify="left").pack(anchor="w", pady=(2,10))

        tk.Button(frm, text="🎯  Test d'alignement (imprimer)", command=self._test_alignement,
                  font=("Helvetica",10,"bold"), bg=ACCENT, fg="white", bd=0,
                  cursor="hand2", pady=7).pack(fill="x", pady=(0,10))

        tk.Button(frm, text="💾  Enregistrer", command=self._sauvegarder_impression,
                  font=("Helvetica",11,"bold"), bg=SUCCESS, fg="white", bd=0,
                  cursor="hand2", pady=8).pack(fill="x")

    def _maj_dy_cat(self):
        """Change la catégorie affichée pour le décalage vertical."""
        # Mémorise la valeur en cours d'édition pour l'ancienne catégorie
        self._dy_values[self._dy_cat_current] = self.dy_val_var.get()
        nom = self.dy_cat_var.get()
        slug = dict(self._CATS_DY).get(nom, self._CATS_DY[0][1])
        self._dy_cat_current = slug
        self.dy_val_var.set(self._dy_values.get(slug, "0"))

    def _test_alignement(self):
        # Enregistre d'abord les valeurs courantes pour que le test les utilise
        self._sauvegarder_impression(silencieux=True)
        pdf_dir = os.path.join(APP_DIR, "bons_pdf")
        os.makedirs(pdf_dir, exist_ok=True)
        chemin = os.path.join(pdf_dir, "test_alignement.pdf")
        try:
            impression.generer_test_alignement(chemin)
        except Exception as e:
            messagebox.showerror("Test", f"Échec : {e}", parent=self)
            return
        _open_file(chemin)

    def _sauvegarder_impression(self, silencieux=False):
        db.set_parametre("bon_sans_identite",
                         "1" if self.sans_identite_var.get() else "0")
        db.set_parametre("impression_mode", self.impression_mode_var.get())
        for cle, var in [("impression_offset_x", self.offset_x_var),
                         ("impression_offset_y", self.offset_y_var)]:
            try:
                v = str(int(var.get()))
            except ValueError:
                v = "0"
            db.set_parametre(cle, v)
        # Géométrie papier
        try:
            db.set_parametre("impr_y1", str(float(self.impr_y1_var.get())))
        except ValueError:
            db.set_parametre("impr_y1", "79")
        try:
            db.set_parametre("impr_pas", str(float(self.impr_pas_var.get())))
        except ValueError:
            db.set_parametre("impr_pas", "5.15")
        # Décalages verticaux par catégorie
        if hasattr(self, "_dy_values"):
            self._dy_values[self._dy_cat_current] = self.dy_val_var.get()
            for slug, val in self._dy_values.items():
                try:
                    db.set_parametre(f"impr_dy_{slug}", str(float(val)))
                except (ValueError, TypeError):
                    db.set_parametre(f"impr_dy_{slug}", "0")
        if not silencieux:
            messagebox.showinfo("Enregistré",
                "Paramètres d'impression enregistrés.", parent=self)

    def _build_maj(self, parent, params):
        """Onglet de configuration et de vérification des mises à jour."""
        frm = tk.Frame(parent, bg=DARK_BG, padx=30, pady=20)
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text=f"Version installée : v{updater.APP_VERSION}",
                 font=("Helvetica",11,"bold"), bg=DARK_BG, fg=TEXT).pack(anchor="w", pady=(0,14))

        tk.Label(frm, text="Source de mise à jour",
                 font=("Helvetica",10,"bold"), bg=DARK_BG, fg=TEXT_MUTED).pack(anchor="w")

        self.maj_source_var = tk.StringVar(value=params.get("maj_source","github"))
        options = [
            ("github", "🌐  Internet (GitHub)"),
            ("reseau", "🖧  Dossier réseau partagé"),
            ("local",  "💾  Fichier .exe local / clé USB"),
        ]
        for val, label in options:
            tk.Radiobutton(frm, text=label, value=val, variable=self.maj_source_var,
                           command=self._maj_toggle_chemin,
                           bg=DARK_BG, fg=TEXT, activebackground=DARK_BG, activeforeground=TEXT,
                           selectcolor=CARD_BG, font=("Helvetica",10),
                           anchor="w").pack(fill="x", pady=2)

        row_chemin = tk.Frame(frm, bg=DARK_BG)
        row_chemin.pack(fill="x", pady=(10,4))
        self.maj_chemin_lbl_var = tk.StringVar(value="Dossier :")
        tk.Label(row_chemin, textvariable=self.maj_chemin_lbl_var, width=12, anchor="e",
                 font=("Helvetica",10), bg=DARK_BG, fg=TEXT_MUTED).pack(side="left", padx=(0,8))
        self.maj_chemin_var = tk.StringVar(value=params.get("maj_chemin",""))
        self.maj_chemin_entry = tk.Entry(row_chemin, textvariable=self.maj_chemin_var,
                 font=("Helvetica",10), bg=CARD_BG, fg=TEXT, insertbackground=TEXT, bd=0,
                 relief="flat", highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT)
        self.maj_chemin_entry.pack(side="left", fill="x", expand=True, ipady=6)
        tk.Button(row_chemin, text="…", command=self._choisir_chemin_maj,
                  font=("Helvetica",10,"bold"), bg=CARD_BG, fg=TEXT, bd=0,
                  cursor="hand2", padx=10).pack(side="left", padx=(6,0))

        self.maj_chemin_help_var = tk.StringVar(
            value="Le dossier réseau doit contenir : version.txt et CantineSetup.exe")
        tk.Label(frm, textvariable=self.maj_chemin_help_var,
                 font=("Helvetica",8), bg=DARK_BG, fg=TEXT_MUTED,
                 wraplength=560, justify="left").pack(anchor="w", pady=(0,14))

        btn_row = tk.Frame(frm, bg=DARK_BG)
        btn_row.pack(fill="x", pady=(6,4))
        tk.Button(btn_row, text="💾  Enregistrer", command=self._sauvegarder_maj,
                  font=("Helvetica",10,"bold"), bg=SUCCESS, fg="white", bd=0,
                  cursor="hand2", pady=8).pack(side="left", fill="x", expand=True, padx=(0,4))
        tk.Button(btn_row, text="🔎  Vérifier maintenant", command=self._verifier_maj_tab,
                  font=("Helvetica",10,"bold"), bg=ACCENT, fg="white", bd=0,
                  cursor="hand2", pady=8).pack(side="left", fill="x", expand=True, padx=(4,0))

        self.maj_status_lbl = tk.Label(frm, text="", font=("Helvetica",9),
                 bg=DARK_BG, fg=TEXT_MUTED, wraplength=560, justify="left")
        self.maj_status_lbl.pack(anchor="w", pady=(14,0))

        self._maj_toggle_chemin()

    def _maj_toggle_chemin(self):
        source = self.maj_source_var.get()
        etat = "disabled" if source == "github" else "normal"
        self.maj_chemin_entry.config(state=etat)
        if source == "local":
            self.maj_chemin_lbl_var.set("Fichier :")
            self.maj_chemin_help_var.set(
                "Sélectionnez directement le fichier CantineSetup.exe à installer "
                "(ex: sur une clé USB). Aucune vérification de version : le fichier "
                "choisi est toujours proposé à l'installation.")
        else:
            self.maj_chemin_lbl_var.set("Dossier :")
            self.maj_chemin_help_var.set(
                "Le dossier réseau doit contenir : version.txt et CantineSetup.exe")

    def _choisir_chemin_maj(self):
        if self.maj_source_var.get() == "local":
            fichier = filedialog.askopenfilename(
                parent=self, title="Choisir le fichier d'installation (.exe)",
                filetypes=[("Exécutable", "*.exe"), ("Tous les fichiers", "*.*")])
            if fichier:
                self.maj_chemin_var.set(fichier)
        else:
            dossier = filedialog.askdirectory(parent=self, title="Choisir le dossier de mise à jour")
            if dossier:
                self.maj_chemin_var.set(dossier)

    def _sauvegarder_maj(self):
        db.set_parametre("maj_source", self.maj_source_var.get())
        db.set_parametre("maj_chemin", self.maj_chemin_var.get().strip())
        messagebox.showinfo("Enregistré", "Paramètres de mise à jour enregistrés.", parent=self)

    def _verifier_maj_tab(self):
        source = self.maj_source_var.get()
        chemin = self.maj_chemin_var.get().strip()
        self.maj_status_lbl.config(text="⏳  Vérification en cours...", fg=TEXT_MUTED)
        _verifier_maj_async(self, source, chemin, status_cb=self._maj_set_status)

    def _maj_set_status(self, texte, couleur):
        self.maj_status_lbl.config(text=texte, fg=couleur)

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
def _demander_jour(parent, titre="Jour de livraison", valeur_init=""):
    """Petit dialogue modal avec une Combobox pour choisir un jour de la semaine.
    Retourne le jour choisi (str, '' pour non défini) ou None si annulé."""
    win = tk.Toplevel(parent)
    win.title(titre)
    win.configure(bg=DARK_BG)
    win.resizable(False, False)
    win.transient(parent)
    win.grab_set()
    tk.Label(win, text=titre, font=("Helvetica",11,"bold"),
             bg=DARK_BG, fg=TEXT).pack(padx=24, pady=(16,8))
    var = tk.StringVar(value=valeur_init or "(Non défini)")
    ttk.Combobox(win, textvariable=var, values=["(Non défini)"] + JOURS_SEMAINE,
                state="readonly", width=20, font=("Helvetica",10)).pack(padx=24, pady=4)
    result = {"value": None}
    def _valider():
        v = var.get()
        result["value"] = "" if v == "(Non défini)" else v
        win.destroy()
    btn_frm = tk.Frame(win, bg=DARK_BG)
    btn_frm.pack(fill="x", padx=24, pady=(12,16))
    tk.Button(btn_frm, text="Annuler", command=win.destroy,
              font=("Helvetica",9), bg="#374151", fg=TEXT, bd=0,
              cursor="hand2", pady=6).pack(side="left", fill="x", expand=True, padx=(0,4))
    tk.Button(btn_frm, text="✓ Valider", command=_valider,
              font=("Helvetica",9,"bold"), bg=SUCCESS, fg="white", bd=0,
              cursor="hand2", pady=6).pack(side="left", fill="x", expand=True, padx=(4,0))
    win.update_idletasks()
    x = parent.winfo_rootx() + (parent.winfo_width()-win.winfo_width())//2
    y = parent.winfo_rooty() + (parent.winfo_height()-win.winfo_height())//2
    win.geometry(f"+{x}+{y}")
    win.wait_window()
    return result["value"]


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

        cols = ("id","nom","categorie","prix","max","actif","livraison")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        for col, txt, w, anc in [("id","Code",70,"center"),("nom","Produit",380,"w"),
                                   ("categorie","Catégorie",120,"center"),("prix","Prix",70,"center"),
                                   ("max","Max",50,"center"),("actif","Actif",55,"center"),
                                   ("livraison","Livraison",100,"center")]:
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
        tk.Button(bbar, text="📅 Jour de livraison", command=self._definir_livraison,
                  font=("Helvetica",9), bg="#374151", fg=TEXT, bd=0,
                  cursor="hand2", pady=5, padx=10).pack(side="right", padx=8, pady=6)
        tk.Label(bbar, text="(sélection multiple : Ctrl+clic / Shift+clic)",
                 bg=PANEL_BG, fg=TEXT_MUTED, font=("Helvetica",8,"italic")).pack(side="right", padx=4)

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
            pid, nom, cat2, prix, qmax, actif, jour = p
            if f and f not in nom.lower() and f not in pid.lower(): continue
            tag = "" if actif == "Oui" else "inactive"
            self.tree.insert("", "end", iid=pid,
                             values=(pid, nom, cat2, f"{prix:.2f} €", qmax, actif,
                                     jour or "—"),
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

    def _definir_livraison(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Sélection",
                "Sélectionnez un ou plusieurs produits dans la liste\n"
                "(Ctrl+clic ou Shift+clic pour une sélection multiple).", parent=self)
            return
        jour = _demander_jour(self, f"Jour de livraison — {len(sel)} produit(s)")
        if jour is None:
            return
        db.set_jour_livraison(list(sel), jour)
        self._load()

class EditProduitWindow(tk.Toplevel):
    def __init__(self, master, prod, callback):
        super().__init__(master)
        self.prod = prod; self.callback = callback
        self.title(f"Modifier — {prod[0]}")
        self.configure(bg=DARK_BG)
        self.resizable(False, False)
        self.geometry("400x330")
        self._center()
        self._build()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - self.winfo_width())  // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build(self):
        pid, nom, _, prix, qmax, actif, jour = self.prod
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
        row_j = tk.Frame(frm, bg=DARK_BG); row_j.pack(fill="x", pady=4)
        tk.Label(row_j, text="Livraison:", width=14, anchor="e",
                 font=("Helvetica",10), bg=DARK_BG, fg=TEXT_MUTED).pack(side="left", padx=(0,8))
        self.v_jour = tk.StringVar(value=jour or "(Non défini)")
        ttk.Combobox(row_j, textvariable=self.v_jour,
                     values=["(Non défini)"] + JOURS_SEMAINE,
                     state="readonly", width=16).pack(side="left")
        tk.Button(frm, text="💾 Enregistrer", command=self._save,
                  font=("Helvetica",11,"bold"), bg=SUCCESS, fg="white", bd=0,
                  cursor="hand2", pady=8, activebackground="#15803d").pack(fill="x", pady=(12,0))

    def _save(self):
        try:
            prix = float(self.vars["prix"].get().replace(",","."))
            qmax = int(self.vars["max"].get())
        except:
            messagebox.showerror("Erreur","Prix et Max doivent être des nombres.",parent=self); return
        jour = self.v_jour.get()
        jour = "" if jour == "(Non défini)" else jour
        db.update_produit(self.prod[0], self.vars["nom"].get().strip(), prix, qmax,
                          self.v_actif.get(), jour_livraison=jour)
        self.callback(); self.destroy()


# ─────────────────────────────────────────────
# COMPTE CANTINABLE
# ─────────────────────────────────────────────
class CompteWindow(tk.Toplevel):
    """Gestion complète du compte cantinable."""

    CATS_DEPENSE = ["Cantine", "Dépense fixe", "Autre"]
    CATS_REVENU  = ["Revenu"]

    def __init__(self, master):
        super().__init__(master)
        self.title("🏦  Compte Cantinable")
        self.configure(bg=DARK_BG)
        self.state("zoomed")
        self._center()
        self._current_view = "transactions"
        self._build()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - self.winfo_width())  // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build(self):
        bar = tk.Frame(self, bg="#0c2340", height=56)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        tk.Label(bar, text="🏦  COMPTE CANTINABLE",
                 font=("Helvetica",14,"bold"), bg="#0c2340", fg="white").pack(side="left", padx=18)

        solde = db.compte_get_solde()
        s_color = SUCCESS if solde >= 0 else DANGER
        self.solde_header_lbl = tk.Label(bar, text=f"Solde : {solde:.2f} €",
                 font=("Helvetica",14,"bold"), bg="#0c2340", fg=s_color)
        self.solde_header_lbl.pack(side="left", padx=30)

        tk.Button(bar, text="✕  Fermer", command=self.destroy,
                  font=("Helvetica",10), bg=DANGER, fg="white", bd=0,
                  cursor="hand2", pady=6, padx=14,
                  activebackground="#b91c1c").pack(side="right", padx=12, pady=10)

        self.toggle_btn = tk.Button(bar, text="⚙️  Dépenses fixes",
                  command=self._toggle_view,
                  font=("Helvetica",10), bg="#374151", fg="white", bd=0,
                  cursor="hand2", pady=6, padx=12)
        self.toggle_btn.pack(side="right", padx=4, pady=10)

        self.main_frame = tk.Frame(self, bg=DARK_BG)
        self.main_frame.pack(fill="both", expand=True)
        self._build_transactions_view()

    def _toggle_view(self):
        if self._current_view == "transactions":
            self._current_view = "parametres"
            self.toggle_btn.config(text="📊  Transactions")
            self._clear_main()
            self._build_parametres_view()
        else:
            self._current_view = "transactions"
            self.toggle_btn.config(text="⚙️  Dépenses fixes")
            self._clear_main()
            self._build_transactions_view()

    def _clear_main(self):
        for w in self.main_frame.winfo_children():
            w.destroy()

    def _refresh_solde(self):
        solde = db.compte_get_solde()
        s_color = SUCCESS if solde >= 0 else DANGER
        self.solde_header_lbl.config(text=f"Solde : {solde:.2f} €", fg=s_color)

    def _build_transactions_view(self):
        container = self.main_frame

        stats_frm = tk.Frame(container, bg=DARK_BG)
        stats_frm.pack(fill="x", padx=16, pady=(12,6))
        solde, revenus, depenses, cantines, fixes = db.compte_get_stats()

        for label, val, color in [
            ("💰  Revenus",  abs(revenus),  SUCCESS),
            ("📉  Dépenses", abs(depenses), DANGER),
            ("🛒  Cantines", abs(cantines), ACCENT),
            ("📌  Fixes",    abs(fixes),    GOLD),
        ]:
            card = tk.Frame(stats_frm, bg=CARD_BG, bd=0,
                            highlightthickness=1, highlightbackground=BORDER)
            card.pack(side="left", fill="x", expand=True, padx=4)
            tk.Label(card, text=label, font=("Helvetica",9),
                     bg=CARD_BG, fg=TEXT_MUTED, anchor="w").pack(fill="x", padx=12, pady=(8,0))
            tk.Label(card, text=f"{val:.2f} €",
                     font=("Helvetica",16,"bold"), bg=CARD_BG, fg=color,
                     anchor="w").pack(fill="x", padx=12, pady=(0,8))

        if revenus > 0:
            prog_frm = tk.Frame(container, bg=CARD_BG, bd=0,
                                highlightthickness=1, highlightbackground=BORDER)
            prog_frm.pack(fill="x", padx=20, pady=(4,8))
            pct = min(100, (abs(depenses) / revenus) * 100)
            info_bar = tk.Frame(prog_frm, bg=CARD_BG)
            info_bar.pack(fill="x", padx=12, pady=(8,2))
            tk.Label(info_bar, text=f"Dépensé : {abs(depenses):.2f} €",
                     font=("Helvetica",9), bg=CARD_BG, fg=DANGER).pack(side="left")
            tk.Label(info_bar, text=f"Disponible : {max(0,solde):.2f} €",
                     font=("Helvetica",9), bg=CARD_BG, fg=SUCCESS).pack(side="right")
            bar_outer = tk.Frame(prog_frm, bg="#374151", height=10)
            bar_outer.pack(fill="x", padx=12, pady=(2,10))
            bar_outer.pack_propagate(False)
            bar_color = DANGER if pct > 90 else (GOLD if pct > 70 else ACCENT)
            bar_inner = tk.Frame(bar_outer, bg=bar_color)
            bar_inner.place(relx=0, rely=0, relheight=1.0, relwidth=pct/100)

        action_bar = tk.Frame(container, bg=DARK_BG)
        action_bar.pack(fill="x", padx=16, pady=(4,4))
        tk.Button(action_bar, text="➕  Nouveau revenu",
                  command=lambda: self._ouvrir_form("revenu"),
                  font=("Helvetica",10,"bold"), bg=SUCCESS, fg="white", bd=0,
                  cursor="hand2", pady=8, padx=14).pack(side="left", padx=(0,6))
        tk.Button(action_bar, text="➖  Nouvelle dépense",
                  command=lambda: self._ouvrir_form("depense"),
                  font=("Helvetica",10,"bold"), bg=DANGER, fg="white", bd=0,
                  cursor="hand2", pady=8, padx=14).pack(side="left", padx=(0,6))
        tk.Button(action_bar, text="📌  Passer les dépenses fixes du mois",
                  command=self._ajouter_fixes_mois,
                  font=("Helvetica",10,"bold"), bg=GOLD, fg="#000", bd=0,
                  cursor="hand2", pady=8, padx=14).pack(side="left", padx=(0,6))

        self.filtre_var = tk.StringVar(value="Tout")
        for f in ["Tout", "Cantine", "Revenu", "Dépense fixe", "Autre"]:
            tk.Radiobutton(action_bar, text=f, variable=self.filtre_var, value=f,
                           command=self._load_transactions,
                           bg=DARK_BG, fg=TEXT_MUTED, activebackground=DARK_BG,
                           selectcolor=CARD_BG, font=("Helvetica",9),
                           indicatoron=0, bd=0, padx=10, pady=6,
                           relief="flat").pack(side="right", padx=1)

        tree_frm = tk.Frame(container, bg=DARK_BG)
        tree_frm.pack(fill="both", expand=True, padx=16, pady=(4,8))
        tree_frm.rowconfigure(0, weight=1)
        tree_frm.columnconfigure(0, weight=1)

        cols = ("id", "date", "label", "categorie", "montant")
        self.tree = ttk.Treeview(tree_frm, columns=cols, show="headings", selectmode="browse")
        for col, txt, w, anc in [
            ("id","#",50,"center"), ("date","Date",100,"center"),
            ("label","Libellé",400,"w"), ("categorie","Catégorie",130,"center"),
            ("montant","Montant",120,"center"),
        ]:
            self.tree.heading(col, text=txt, anchor=anc)
            self.tree.column(col, width=w, anchor=anc, stretch=(col=="label"))
        sb = ttk.Scrollbar(tree_frm, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")

        bot_bar = tk.Frame(container, bg=PANEL_BG)
        bot_bar.pack(fill="x")
        self.count_lbl = tk.Label(bot_bar, text="", font=("Helvetica",9),
                                   bg=PANEL_BG, fg=TEXT_MUTED)
        self.count_lbl.pack(side="left", padx=14, pady=8)
        tk.Button(bot_bar, text="✏️  Modifier", command=self._modifier_tx,
                  font=("Helvetica",10), bg=ACCENT, fg="white", bd=0,
                  cursor="hand2", pady=6, padx=12).pack(side="right", padx=6, pady=6)
        tk.Button(bot_bar, text="🗑️  Supprimer", command=self._supprimer_tx,
                  font=("Helvetica",10), bg=DANGER, fg="white", bd=0,
                  cursor="hand2", pady=6, padx=12).pack(side="right", padx=2, pady=6)

        s = ttk.Style(); s.theme_use("clam")
        s.configure("Treeview", background=CARD_BG, foreground=TEXT,
                    fieldbackground=CARD_BG, rowheight=26, font=("Helvetica",9))
        s.configure("Treeview.Heading", background=HEADER_BG, foreground="white",
                    font=("Helvetica",9,"bold"))
        s.map("Treeview", background=[("selected", ACCENT)])
        self._load_transactions()

    def _load_transactions(self):
        filtre = self.filtre_var.get()
        all_tx = db.compte_get_transactions(500)
        self.tree.delete(*self.tree.get_children())
        n = 0
        for tx in all_tx:
            tid, date, label, montant, categorie, bon_id = tx
            if filtre != "Tout" and categorie != filtre:
                continue
            signe = "+" if montant >= 0 else ""
            tag = "revenu" if montant >= 0 else "depense"
            self.tree.insert("", "end", iid=str(tid),
                             values=(tid, date, label, categorie, f"{signe}{montant:.2f} €"),
                             tags=(tag,))
            n += 1
        self.tree.tag_configure("revenu",  foreground="#4ade80")
        self.tree.tag_configure("depense", foreground="#f87171")
        self.count_lbl.config(text=f"{n} transaction(s)")
        self._refresh_solde()

    def _ouvrir_form(self, mode, tx_data=None):
        win = CompteTransactionForm(self, mode, tx_data)
        win.grab_set()
        self.wait_window(win)
        self._clear_main()
        self._build_transactions_view()

    def _modifier_tx(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Sélection", "Sélectionnez une transaction.", parent=self)
            return
        tid = int(sel[0])
        all_tx = db.compte_get_transactions(500)
        tx = next((t for t in all_tx if t[0] == tid), None)
        if not tx: return
        mode = "revenu" if tx[3] >= 0 else "depense"
        self._ouvrir_form(mode, tx)

    def _supprimer_tx(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Sélection", "Sélectionnez une transaction.", parent=self)
            return
        if messagebox.askyesno("Confirmer", "Supprimer cette transaction ?", parent=self):
            db.compte_supprimer_transaction(int(sel[0]))
            self._clear_main()
            self._build_transactions_view()

    def _ajouter_fixes_mois(self):
        fixes = db.get_depenses_fixes()
        actives = [f for f in fixes if f[3] == 1]
        if not actives:
            messagebox.showinfo("Aucune",
                "Aucune dépense fixe active.\nConfigurez-les dans ⚙️ Dépenses fixes.", parent=self)
            return
        mois_noms = ["Janvier","Février","Mars","Avril","Mai","Juin",
                     "Juillet","Août","Septembre","Octobre","Novembre","Décembre"]
        mois   = mois_noms[datetime.now().month - 1]
        annee  = datetime.now().year
        date_s = datetime.now().strftime("%d/%m/%Y")
        all_tx = db.compte_get_transactions(500)
        deja = any(f"{mois} {annee}" in (t[2] or "") and t[4] == "Dépense fixe"
                   for t in all_tx)
        if deja:
            if not messagebox.askyesno("Attention",
                    f"Des dépenses fixes pour {mois} {annee} semblent déjà exister.\n"
                    "Les ajouter quand même ?", parent=self):
                return
        for f in actives:
            fid, flabel, fmontant, _ = f
            db.compte_ajouter_transaction(date_s, f"{flabel} — {mois} {annee}",
                                          -abs(fmontant), "Dépense fixe")
        total = sum(f[2] for f in actives)
        messagebox.showinfo("✅ Dépenses fixes",
            f"{len(actives)} dépense(s) fixe(s) ajoutée(s) pour {mois} {annee}\n"
            f"Total : -{total:.2f} €", parent=self)
        self._clear_main()
        self._build_transactions_view()

    def _build_parametres_view(self):
        container = self.main_frame
        tk.Label(container, text="⚙️  Gestion des dépenses fixes mensuelles",
                 font=("Helvetica",14,"bold"), bg=DARK_BG, fg=TEXT).pack(pady=(16,4))
        tk.Label(container, text="Active ou désactive chaque poste et ajuste le montant.",
                 font=("Helvetica",10), bg=DARK_BG, fg=TEXT_MUTED).pack(pady=(0,12))

        fixes = db.get_depenses_fixes()
        self.fix_widgets = {}
        icons = {"tv":"📺","frigo":"❄️","telephone":"📞"}

        for f in fixes:
            fid, flabel, fmontant, factif = f
            row = tk.Frame(container, bg=CARD_BG, bd=0,
                           highlightthickness=1, highlightbackground=BORDER)
            row.pack(fill="x", padx=40, pady=4)
            tk.Label(row, text=icons.get(fid,"📌"), font=("Segoe UI Emoji",20),
                     bg=CARD_BG, fg=TEXT).pack(side="left", padx=(12,8), pady=10)
            info_frm = tk.Frame(row, bg=CARD_BG)
            info_frm.pack(side="left", fill="x", expand=True, pady=8)
            lbl_var = tk.StringVar(value=flabel)
            tk.Entry(info_frm, textvariable=lbl_var, font=("Helvetica",11,"bold"),
                     bg=CARD_BG, fg=TEXT, insertbackground=TEXT, bd=0,
                     highlightthickness=0).pack(fill="x")
            mnt_frm = tk.Frame(info_frm, bg=CARD_BG)
            mnt_frm.pack(fill="x", pady=(2,0))
            mnt_var = tk.StringVar(value=f"{fmontant:.2f}")
            tk.Entry(mnt_frm, textvariable=mnt_var, width=8,
                     font=("Helvetica",11), bg="#1a1f2e", fg=GOLD,
                     insertbackground=GOLD, bd=0, highlightthickness=1,
                     highlightbackground=BORDER).pack(side="left", ipady=4)
            tk.Label(mnt_frm, text="€ / mois", font=("Helvetica",9),
                     bg=CARD_BG, fg=TEXT_MUTED).pack(side="left", padx=6)
            actif_var = tk.BooleanVar(value=bool(factif))
            tk.Checkbutton(row, text="Actif", variable=actif_var,
                           bg=CARD_BG, fg=GOLD, activebackground=CARD_BG,
                           selectcolor="#1a1f2e", font=("Helvetica",10,"bold")).pack(side="right", padx=16)
            self.fix_widgets[fid] = (lbl_var, mnt_var, actif_var)

        add_frm = tk.Frame(container, bg=DARK_BG)
        add_frm.pack(fill="x", padx=40, pady=(12,4))
        tk.Label(add_frm, text="Ajouter :", font=("Helvetica",10,"bold"),
                 bg=DARK_BG, fg=TEXT).pack(side="left", padx=(0,8))
        self.new_fix_id = tk.StringVar()
        tk.Entry(add_frm, textvariable=self.new_fix_id, width=10,
                 font=("Helvetica",10), bg=CARD_BG, fg=TEXT, insertbackground=TEXT,
                 bd=0, highlightthickness=1, highlightbackground=BORDER).pack(side="left", padx=2, ipady=5)
        tk.Label(add_frm, text="ID", font=("Helvetica",8),
                 bg=DARK_BG, fg=TEXT_MUTED).pack(side="left", padx=(2,8))
        self.new_fix_label = tk.StringVar()
        tk.Entry(add_frm, textvariable=self.new_fix_label, width=20,
                 font=("Helvetica",10), bg=CARD_BG, fg=TEXT, insertbackground=TEXT,
                 bd=0, highlightthickness=1, highlightbackground=BORDER).pack(side="left", padx=2, ipady=5)
        tk.Label(add_frm, text="Libellé", font=("Helvetica",8),
                 bg=DARK_BG, fg=TEXT_MUTED).pack(side="left", padx=(2,8))
        self.new_fix_mnt = tk.StringVar(value="0.00")
        tk.Entry(add_frm, textvariable=self.new_fix_mnt, width=8,
                 font=("Helvetica",10), bg=CARD_BG, fg=TEXT, insertbackground=TEXT,
                 bd=0, highlightthickness=1, highlightbackground=BORDER).pack(side="left", padx=2, ipady=5)
        tk.Label(add_frm, text="€", font=("Helvetica",8),
                 bg=DARK_BG, fg=TEXT_MUTED).pack(side="left", padx=(2,8))
        tk.Button(add_frm, text="➕ Ajouter", command=self._ajouter_fixe,
                  font=("Helvetica",9), bg=SUCCESS, fg="white", bd=0,
                  cursor="hand2", pady=5, padx=10).pack(side="left", padx=6)

        total_fixes = sum(f[2] for f in fixes if f[3])
        tk.Label(container, text=f"Total dépenses fixes actives : {total_fixes:.2f} € / mois",
                 font=("Helvetica",12,"bold"), bg=DARK_BG, fg=GOLD).pack(pady=(16,8))
        btn_frm = tk.Frame(container, bg=DARK_BG)
        btn_frm.pack(pady=6)
        tk.Button(btn_frm, text="💾  Enregistrer les modifications",
                  command=self._sauvegarder_fixes,
                  font=("Helvetica",11,"bold"), bg=SUCCESS, fg="white", bd=0,
                  cursor="hand2", pady=10, padx=24).pack(side="left", padx=8)
        tk.Button(btn_frm, text="↩️  Retour aux transactions",
                  command=self._toggle_view,
                  font=("Helvetica",10), bg="#374151", fg=TEXT, bd=0,
                  cursor="hand2", pady=8, padx=16).pack(side="left", padx=4)

    def _sauvegarder_fixes(self):
        for fid, (lbl_var, mnt_var, actif_var) in self.fix_widgets.items():
            try:
                mnt = float(mnt_var.get().replace(",","."))
            except:
                mnt = 0.0
            db.update_depense_fixe(fid, lbl_var.get().strip(), mnt, 1 if actif_var.get() else 0)
        messagebox.showinfo("✅ Enregistré", "Dépenses fixes mises à jour.", parent=self)

    def _ajouter_fixe(self):
        fid = self.new_fix_id.get().strip().lower()
        flabel = self.new_fix_label.get().strip()
        try:
            fmnt = float(self.new_fix_mnt.get().replace(",","."))
        except:
            messagebox.showwarning("Erreur", "Montant invalide.", parent=self)
            return
        if not fid or not flabel:
            messagebox.showwarning("Champs manquants", "Renseignez l'ID et le libellé.", parent=self)
            return
        db.ajouter_depense_fixe(fid, flabel, fmnt)
        messagebox.showinfo("Ajouté", f"Dépense fixe « {flabel} » ajoutée.", parent=self)
        self._clear_main()
        self._build_parametres_view()


class CompteTransactionForm(tk.Toplevel):
    """Formulaire ajout / modification d'une transaction du compte."""
    def __init__(self, master, mode, tx_data=None):
        super().__init__(master)
        self.mode = mode
        self.tx_data = tx_data
        self.is_edit = tx_data is not None
        title = "Modifier la transaction" if self.is_edit else (
            "💰  Nouveau revenu" if mode == "revenu" else "➖  Nouvelle dépense")
        self.title(title)
        self.configure(bg=DARK_BG)
        self.resizable(False, False)
        self.geometry("460x380")
        self._center()
        self._build()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - self.winfo_width())  // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build(self):
        accent = SUCCESS if self.mode == "revenu" else DANGER
        tk.Frame(self, bg=accent, height=4).pack(fill="x")
        hdr = tk.Frame(self, bg=HEADER_BG, height=46)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        icon = "💰" if self.mode == "revenu" else "➖"
        hdr_text = "Modifier la transaction" if self.is_edit else (
            f"{icon}  {'Nouveau revenu' if self.mode == 'revenu' else 'Nouvelle dépense'}")
        tk.Label(hdr, text=hdr_text, font=("Helvetica",12,"bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=14, pady=10)

        frm = tk.Frame(self, bg=DARK_BG, padx=30, pady=20)
        frm.pack(fill="both", expand=True)

        row_d = tk.Frame(frm, bg=DARK_BG); row_d.pack(fill="x", pady=6)
        tk.Label(row_d, text="Date :", width=12, anchor="e",
                 font=("Helvetica",10), bg=DARK_BG, fg=TEXT_MUTED).pack(side="left", padx=(0,8))
        self.date_var = tk.StringVar(
            value=self.tx_data[1] if self.is_edit else datetime.now().strftime("%d/%m/%Y"))
        tk.Entry(row_d, textvariable=self.date_var, font=("Helvetica",11),
                 bg=CARD_BG, fg=TEXT, insertbackground=TEXT, bd=0,
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT).pack(side="left", fill="x", expand=True, ipady=7)

        row_l = tk.Frame(frm, bg=DARK_BG); row_l.pack(fill="x", pady=6)
        tk.Label(row_l, text="Libellé :", width=12, anchor="e",
                 font=("Helvetica",10), bg=DARK_BG, fg=TEXT_MUTED).pack(side="left", padx=(0,8))
        self.label_var = tk.StringVar(value=self.tx_data[2] if self.is_edit else "")
        tk.Entry(row_l, textvariable=self.label_var, font=("Helvetica",11),
                 bg=CARD_BG, fg=TEXT, insertbackground=TEXT, bd=0,
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT).pack(side="left", fill="x", expand=True, ipady=7)

        row_c = tk.Frame(frm, bg=DARK_BG); row_c.pack(fill="x", pady=6)
        tk.Label(row_c, text="Catégorie :", width=12, anchor="e",
                 font=("Helvetica",10), bg=DARK_BG, fg=TEXT_MUTED).pack(side="left", padx=(0,8))
        cats = CompteWindow.CATS_REVENU if self.mode == "revenu" else CompteWindow.CATS_DEPENSE
        self.cat_var = tk.StringVar(value=self.tx_data[4] if self.is_edit else cats[0])
        ttk.Combobox(row_c, textvariable=self.cat_var, values=cats,
                     state="readonly", font=("Helvetica",10)).pack(side="left", fill="x", expand=True)

        row_m = tk.Frame(frm, bg=DARK_BG); row_m.pack(fill="x", pady=6)
        tk.Label(row_m, text="Montant (€) :", width=12, anchor="e",
                 font=("Helvetica",10), bg=DARK_BG, fg=TEXT_MUTED).pack(side="left", padx=(0,8))
        self.mnt_var = tk.StringVar(
            value=f"{abs(self.tx_data[3]):.2f}" if self.is_edit else "")
        e = tk.Entry(row_m, textvariable=self.mnt_var, font=("Helvetica",14,"bold"),
                 bg=CARD_BG, fg=accent, insertbackground=accent, bd=0,
                 highlightthickness=2, highlightbackground=accent,
                 highlightcolor=accent, justify="center")
        e.pack(side="left", fill="x", expand=True, ipady=8)
        e.focus_set()

        btn_frm = tk.Frame(frm, bg=DARK_BG); btn_frm.pack(fill="x", pady=(16,0))
        tk.Button(btn_frm, text="Annuler", command=self.destroy,
                  font=("Helvetica",10), bg="#374151", fg=TEXT, bd=0,
                  cursor="hand2", pady=8, padx=16).pack(side="left", fill="x", expand=True, padx=(0,4))
        tk.Button(btn_frm, text="💾  Enregistrer" if self.is_edit else "✓  Ajouter",
                  command=self._sauvegarder,
                  font=("Helvetica",11,"bold"), bg=accent, fg="white", bd=0,
                  cursor="hand2", pady=8, padx=16).pack(side="left", fill="x", expand=True, padx=(4,0))

    def _sauvegarder(self):
        label = self.label_var.get().strip()
        if not label:
            messagebox.showwarning("Champ manquant", "Renseignez le libellé.", parent=self)
            return
        try:
            montant = float(self.mnt_var.get().replace(",","."))
            if montant <= 0: raise ValueError
        except:
            messagebox.showwarning("Montant invalide", "Entrez un montant positif.", parent=self)
            return
        if self.mode == "depense":
            montant = -abs(montant)
        else:
            montant = abs(montant)
        date = self.date_var.get().strip()
        cat  = self.cat_var.get()
        if self.is_edit:
            db.compte_modifier_transaction(self.tx_data[0], date, label, montant, cat)
        else:
            db.compte_ajouter_transaction(date, label, montant, cat)
        self.destroy()


# ─────────────────────────────────────────────
# HISTORIQUE
# ─────────────────────────────────────────────
class HygieneWindow(tk.Toplevel):
    """Cantine hygiène mensuelle (corporelle + cellule), entièrement modifiable."""
    def __init__(self, master):
        super().__init__(master)
        self.title("Cantine hygiène du mois")
        self.configure(bg=DARK_BG)
        self.geometry("880x660")
        self._center()
        self._build()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth()-self.winfo_width())//2
        y = (self.winfo_screenheight()-self.winfo_height())//2
        self.geometry(f"+{x}+{y}")

    def _build(self):
        bar = tk.Frame(self, bg=HEADER_BG, height=48); bar.pack(fill="x"); bar.pack_propagate(False)
        tk.Label(bar, text="🧼  Cantine hygiène du mois",
                 font=("Helvetica",13,"bold"), bg=HEADER_BG, fg="white").pack(side="left", padx=14)
        tk.Button(bar, text="✕ Fermer", command=self.destroy,
                  font=("Helvetica",9), bg=DANGER, fg="white", bd=0,
                  cursor="hand2", pady=4, padx=10).pack(side="right", padx=10)

        par = tk.Frame(self, bg=PANEL_BG); par.pack(fill="x")
        tk.Label(par, text="Nombre de personnes :", font=("Helvetica",10),
                 bg=PANEL_BG, fg=TEXT).pack(side="left", padx=(12,4), pady=8)
        self.pers_var = tk.StringVar(value="2")
        sp = tk.Spinbox(par, from_=1, to=10, textvariable=self.pers_var, width=5,
                   font=("Helvetica",10), bg=CARD_BG, fg=TEXT, bd=0,
                   buttonbackground=CARD_BG, insertbackground=TEXT,
                   command=self._load)
        sp.pack(side="left", ipady=2)
        self.pers_var.trace_add("write", lambda *_: self._load())
        tk.Label(par, text="  (corporelle × personnes, cellule = fixe/mois)",
                 font=("Helvetica",8), bg=PANEL_BG, fg=TEXT_MUTED).pack(side="left")

        # Barre modif
        act = tk.Frame(self, bg=PANEL_BG); act.pack(fill="x")
        tk.Button(act, text="✏️ Modifier quantité", command=self._modifier,
                  font=("Helvetica",9), bg=ACCENT, fg="white", bd=0,
                  cursor="hand2", pady=5, padx=10).pack(side="left", padx=6, pady=5)
        tk.Button(act, text="❌ Supprimer", command=self._supprimer,
                  font=("Helvetica",9), bg="#b45309", fg="white", bd=0,
                  cursor="hand2", pady=5, padx=10).pack(side="left", padx=4, pady=5)
        tk.Button(act, text="➕ Ajouter un produit", command=self._ajouter,
                  font=("Helvetica",9), bg=SUCCESS, fg="white", bd=0,
                  cursor="hand2", pady=5, padx=10).pack(side="left", padx=4, pady=5)

        cols = ("code","qte1","qte","prix","total")
        self.tree = ttk.Treeview(self, columns=cols, show="tree headings", height=15)
        self.tree.heading("#0", text="Groupe / Produit")
        self.tree.heading("code", text="Code")
        self.tree.heading("qte1", text="Qté/pers")
        self.tree.heading("qte", text="Qté totale")
        self.tree.heading("prix", text="P.U.")
        self.tree.heading("total", text="Total")
        self.tree.column("#0", width=330)
        self.tree.column("code", width=70, anchor="center")
        self.tree.column("qte1", width=70, anchor="center")
        self.tree.column("qte", width=80, anchor="center")
        self.tree.column("prix", width=80, anchor="center")
        self.tree.column("total", width=90, anchor="center")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True, padx=8, pady=(8,4))

        s = ttk.Style(); s.theme_use("clam")
        s.configure("Treeview", background=CARD_BG, foreground=TEXT,
                    fieldbackground=CARD_BG, rowheight=24, font=("Helvetica",9))
        s.configure("Treeview.Heading", background=HEADER_BG, foreground="white",
                    font=("Helvetica",9,"bold"))

        bbar = tk.Frame(self, bg=PANEL_BG); bbar.pack(fill="x")
        self.total_lbl = tk.Label(bbar, text="", bg=PANEL_BG, fg=GOLD,
                                  font=("Helvetica",11,"bold"))
        self.total_lbl.pack(side="left", padx=14, pady=8)
        tk.Button(bbar, text="📦  Ajouter à la réserve", command=self._vers_reserve,
                  font=("Helvetica",9,"bold"), bg="#0e7490", fg="white", bd=0,
                  cursor="hand2", pady=6, padx=12).pack(side="right", padx=8, pady=6)
        tk.Button(bbar, text="📄  Exporter PDF", command=self._exporter_pdf,
                  font=("Helvetica",9), bg="#7c3aed", fg="white", bd=0,
                  cursor="hand2", pady=6, padx=12).pack(side="right", padx=4, pady=6)

        self._load()

    def _nb_pers(self):
        try: return max(1, int(self.pers_var.get()))
        except ValueError: return 1

    def _lignes_calculees(self):
        """Retourne la liste avec quantités calculées selon le groupe."""
        nb = self._nb_pers()
        out = []
        for h in db.get_hygiene_liste():
            mult = nb if h["groupe"] == "corporelle" else 1
            qte = h["qte_par_pers"] * mult
            out.append({**h, "qte": qte, "total": h["prix"]*qte})
        return out

    def _load(self):
        self.tree.delete(*self.tree.get_children())
        lignes = self._lignes_calculees()
        total = 0.0
        for grp, titre in [("corporelle","🧼 Hygiène corporelle (× personnes)"),
                           ("cellule","🧹 Hygiène de la cellule (fixe)")]:
            items = [l for l in lignes if l["groupe"] == grp]
            if not items: continue
            st = sum(l["total"] for l in items)
            total += st
            g = self.tree.insert("", "end", open=True, text=titre,
                values=("","","","", f"{st:.2f} €"))
            for l in items:
                self.tree.insert(g, "end", iid=l["id"], text=f"   {l['nom']}",
                    values=(l["id"], l["qte_par_pers"], l["qte"],
                            f"{l['prix']:.2f} €", f"{l['total']:.2f} €"))
        self.total_lbl.config(
            text=f"Total : {total:.2f} €   ({self._nb_pers()} pers. / mois)")

    def _sel_produit(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Sélection",
                "Sélectionnez d'abord un produit.", parent=self); return None
        pid = sel[0]
        # ignorer les nœuds de groupe (pas d'iid produit)
        if not self.tree.item(pid, "values") or not self.tree.item(pid,"values")[0]:
            messagebox.showinfo("Sélection",
                "Sélectionnez un produit, pas un titre de groupe.", parent=self)
            return None
        return pid

    def _modifier(self):
        pid = self._sel_produit()
        if not pid: return
        nom = self.tree.item(pid, "text").strip()
        actuelle = self.tree.item(pid, "values")[1]
        rep = simpledialog.askstring("Modifier",
            f"Quantité par personne pour :\n{nom}\n(0 pour supprimer)",
            initialvalue=str(actuelle), parent=self)
        if rep is None: return
        try: q = int(float(rep.strip().replace(",", ".")))
        except ValueError:
            messagebox.showwarning("Invalide","Entrez un entier.",parent=self); return
        db.hygiene_definir_qte(pid, q)
        self._load()

    def _supprimer(self):
        pid = self._sel_produit()
        if not pid: return
        nom = self.tree.item(pid, "text").strip()
        if messagebox.askyesno("Supprimer",
                f"Retirer « {nom} » de la liste hygiène ?", parent=self):
            db.hygiene_supprimer(pid)
            self._load()

    def _ajouter(self):
        AjoutHygieneDialog(self, self._load)

    def _vers_reserve(self):
        lignes = self._lignes_calculees()
        articles = [{"id":l["id"], "nom":l["nom"], "categorie":l["categorie"],
                     "prix":l["prix"], "qte":l["qte"]} for l in lignes]
        db.ajouter_a_reserve(articles)
        messagebox.showinfo("Réserve",
            f"{len(articles)} article(s) hygiène ajouté(s) à la réserve.",
            parent=self)

    def _exporter_pdf(self):
        lignes = self._lignes_calculees()
        nom = f"hygiene_{self._nb_pers()}pers_mois.pdf"
        chemin = filedialog.asksaveasfilename(
            parent=self, title="Exporter la liste hygiène",
            defaultextension=".pdf", initialfile=nom,
            filetypes=[("PDF", "*.pdf")])
        if not chemin: return
        try:
            impression.generer_liste_hygiene_pdf(lignes, self._nb_pers(), chemin)
        except Exception as e:
            messagebox.showerror("PDF", f"Échec : {e}", parent=self); return
        _open_file(chemin)


class AjoutHygieneDialog(tk.Toplevel):
    """Ajoute un produit du catalogue à la liste hygiène."""
    def __init__(self, master, callback):
        super().__init__(master)
        self.callback = callback
        self.title("Ajouter un produit")
        self.configure(bg=DARK_BG)
        self.geometry("560x480")
        self.grab_set()
        self.produits = db.get_produits(actif_only=True)
        self._build()

    def _build(self):
        tk.Label(self, text="Rechercher un produit (code ou nom) :",
                 font=("Helvetica",10), bg=DARK_BG, fg=TEXT).pack(anchor="w", padx=14, pady=(12,4))
        self.rech_var = tk.StringVar()
        e = tk.Entry(self, textvariable=self.rech_var, font=("Helvetica",10),
                 bg=CARD_BG, fg=TEXT, insertbackground=TEXT, bd=0, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT)
        e.pack(fill="x", padx=14, ipady=5)
        self.rech_var.trace_add("write", lambda *_: self._filtrer())

        self.lst = ttk.Treeview(self, columns=("code","cat","prix"), show="headings", height=12)
        for c,t,w in [("code","Code",70),("cat","Catégorie",120),("prix","Prix",70)]:
            self.lst.heading(c, text=t); self.lst.column(c, width=w, anchor="center")
        self.lst.heading("#0", text=""); self.lst["show"]="tree headings"
        self.lst.heading("#0", text="Produit"); self.lst.column("#0", width=260)
        self.lst.pack(fill="both", expand=True, padx=14, pady=6)

        opt = tk.Frame(self, bg=DARK_BG); opt.pack(fill="x", padx=14)
        tk.Label(opt, text="Groupe :", bg=DARK_BG, fg=TEXT_MUTED,
                 font=("Helvetica",9)).pack(side="left")
        self.grp_var = tk.StringVar(value="corporelle")
        ttk.Combobox(opt, textvariable=self.grp_var, values=["corporelle","cellule"],
                     state="readonly", width=12).pack(side="left", padx=6)
        tk.Label(opt, text="  Qté/pers :", bg=DARK_BG, fg=TEXT_MUTED,
                 font=("Helvetica",9)).pack(side="left")
        self.qte_var = tk.StringVar(value="1")
        tk.Spinbox(opt, from_=1, to=30, textvariable=self.qte_var, width=5,
                   bg=CARD_BG, fg=TEXT, bd=0, insertbackground=TEXT).pack(side="left", padx=4)

        bb = tk.Frame(self, bg=PANEL_BG); bb.pack(fill="x")
        tk.Button(bb, text="✓ Ajouter", command=self._ajouter,
                  font=("Helvetica",10,"bold"), bg=SUCCESS, fg="white", bd=0,
                  cursor="hand2", pady=7, padx=14).pack(side="right", padx=8, pady=8)
        tk.Button(bb, text="Fermer", command=self.destroy,
                  font=("Helvetica",9), bg="#374151", fg=TEXT, bd=0,
                  cursor="hand2", pady=7, padx=12).pack(side="right", pady=8)

        s = ttk.Style(); s.theme_use("clam")
        s.configure("Treeview", background=CARD_BG, foreground=TEXT,
                    fieldbackground=CARD_BG, rowheight=22, font=("Helvetica",9))
        self._filtrer()

    def _filtrer(self):
        f = self.rech_var.get().lower().strip()
        self.lst.delete(*self.lst.get_children())
        n = 0
        for p in self.produits:
            if n >= 200: break
            if f and f not in p[0].lower() and f not in p[1].lower(): continue
            self.lst.insert("", "end", iid=p[0], text=p[1],
                values=(p[0], p[2], f"{p[3]:.2f} €"))
            n += 1

    def _ajouter(self):
        sel = self.lst.selection()
        if not sel:
            messagebox.showinfo("Sélection","Choisissez un produit.",parent=self); return
        try: q = int(self.qte_var.get())
        except ValueError: q = 1
        db.hygiene_ajouter(sel[0], self.grp_var.get(), q)
        if self.callback: self.callback()
        messagebox.showinfo("Ajouté",
            f"« {self.lst.item(sel[0],'text')} » ajouté à la liste hygiène.",
            parent=self)


class RationWindow(tk.Toplevel):
    """Liste de provisions équilibrée « sans recette » : X personnes sur N jours."""
    def __init__(self, master):
        super().__init__(master)
        self.title("Ration équilibrée (sans recette)")
        self.configure(bg=DARK_BG)
        self.geometry("820x620")
        self._center()
        self.dernier_resultat = None
        self._build()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth()-self.winfo_width())//2
        y = (self.winfo_screenheight()-self.winfo_height())//2
        self.geometry(f"+{x}+{y}")

    def _build(self):
        bar = tk.Frame(self, bg=HEADER_BG, height=48); bar.pack(fill="x"); bar.pack_propagate(False)
        tk.Label(bar, text="🥗  Ration équilibrée (sans recette)",
                 font=("Helvetica",13,"bold"), bg=HEADER_BG, fg="white").pack(side="left", padx=14)
        tk.Button(bar, text="✕ Fermer", command=self.destroy,
                  font=("Helvetica",9), bg=DANGER, fg="white", bd=0,
                  cursor="hand2", pady=4, padx=10).pack(side="right", padx=10)

        # Paramètres
        par = tk.Frame(self, bg=PANEL_BG); par.pack(fill="x")
        tk.Label(par, text="Nombre de personnes :", font=("Helvetica",10),
                 bg=PANEL_BG, fg=TEXT).pack(side="left", padx=(12,4), pady=8)
        self.pers_var = tk.StringVar(value="2")
        tk.Spinbox(par, from_=1, to=20, textvariable=self.pers_var, width=5,
                   font=("Helvetica",10), bg=CARD_BG, fg=TEXT, bd=0,
                   buttonbackground=CARD_BG, insertbackground=TEXT).pack(side="left", ipady=2)
        tk.Label(par, text="   Nombre de jours :", font=("Helvetica",10),
                 bg=PANEL_BG, fg=TEXT).pack(side="left", padx=(12,4))
        self.jours_var = tk.StringVar(value="15")
        tk.Spinbox(par, from_=1, to=60, textvariable=self.jours_var, width=5,
                   font=("Helvetica",10), bg=CARD_BG, fg=TEXT, bd=0,
                   buttonbackground=CARD_BG, insertbackground=TEXT).pack(side="left", ipady=2)
        tk.Button(par, text="🧮  Calculer", command=self._calculer,
                  font=("Helvetica",10,"bold"), bg=ACCENT, fg="white", bd=0,
                  cursor="hand2", pady=6, padx=14).pack(side="left", padx=12, pady=6)

        cols = ("code","qte","prix","total")
        self.tree = ttk.Treeview(self, columns=cols, show="tree headings", height=16)
        self.tree.heading("#0", text="Groupe / Produit")
        self.tree.heading("code", text="Code")
        self.tree.heading("qte", text="Qté")
        self.tree.heading("prix", text="P.U.")
        self.tree.heading("total", text="Total")
        self.tree.column("#0", width=380)
        self.tree.column("code", width=80, anchor="center")
        self.tree.column("qte", width=60, anchor="center")
        self.tree.column("prix", width=90, anchor="center")
        self.tree.column("total", width=100, anchor="center")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True, padx=8, pady=(8,4))
        self.tree.tag_configure("depasse", foreground="#fca5a5")

        s = ttk.Style(); s.theme_use("clam")
        s.configure("Treeview", background=CARD_BG, foreground=TEXT,
                    fieldbackground=CARD_BG, rowheight=24, font=("Helvetica",9))
        s.configure("Treeview.Heading", background=HEADER_BG, foreground="white",
                    font=("Helvetica",9,"bold"))

        bbar = tk.Frame(self, bg=PANEL_BG); bbar.pack(fill="x")
        self.total_lbl = tk.Label(bbar, text="", bg=PANEL_BG, fg=GOLD,
                                  font=("Helvetica",11,"bold"))
        self.total_lbl.pack(side="left", padx=14, pady=8)
        tk.Button(bbar, text="📦  Ajouter à la réserve", command=self._vers_reserve,
                  font=("Helvetica",9,"bold"), bg="#0e7490", fg="white", bd=0,
                  cursor="hand2", pady=6, padx=12).pack(side="right", padx=8, pady=6)
        tk.Button(bbar, text="📄  Exporter en PDF", command=self._exporter_pdf,
                  font=("Helvetica",9), bg="#7c3aed", fg="white", bd=0,
                  cursor="hand2", pady=6, padx=12).pack(side="right", padx=4, pady=6)

        self._calculer()

    def _calculer(self):
        try:
            nb_p = int(self.pers_var.get()); nb_j = int(self.jours_var.get())
        except ValueError:
            messagebox.showwarning("Valeurs", "Entrez des nombres valides.", parent=self)
            return
        produits = db.get_produits(actif_only=True)
        r = ration.calculer_ration(produits, nb_p, nb_j)
        self.dernier_resultat = r
        self.tree.delete(*self.tree.get_children())
        # Grouper
        par_groupe = {}
        for l in r["lignes"]:
            par_groupe.setdefault(l["groupe"], []).append(l)
        for groupe, lignes in par_groupe.items():
            sous_total = sum(l["total"] for l in lignes)
            g_node = self.tree.insert("", "end", open=True,
                text=f"▸ {groupe}", values=("","","", f"{sous_total:.2f} €"))
            for l in lignes:
                tag = "depasse" if l["depasse"] else ""
                self.tree.insert(g_node, "end", text=f"   {l['nom']}",
                    values=(l["code"], l["qte"], f"{l['prix']:.2f} €",
                            f"{l['total']:.2f} €"), tags=(tag,))
        av = f"   ·   ⚠️ {len(r['avertissements'])} plafond(s)" if r["avertissements"] else ""
        self.total_lbl.config(text=f"Total : {r['total']:.2f} €   "
                              f"({nb_p} pers. × {nb_j} j){av}")

    def _vers_reserve(self):
        if not self.dernier_resultat:
            return
        articles = [{"id":l["code"], "nom":l["nom"], "categorie":l["categorie"],
                     "prix":l["prix"], "qte":l["qte"]}
                    for l in self.dernier_resultat["lignes"]]
        db.ajouter_a_reserve(articles)
        messagebox.showinfo("Réserve",
            f"{len(articles)} article(s) ajouté(s) à la réserve.\n\n"
            "Vous pouvez maintenant les répartir par dette ou les gérer "
            "dans « 📦 Réserve ».", parent=self)

    def _exporter_pdf(self):
        if not self.dernier_resultat:
            return
        from datetime import datetime as _dt
        nom = f"ration_{self.pers_var.get()}pers_{self.jours_var.get()}j.pdf"
        chemin = filedialog.asksaveasfilename(
            parent=self, title="Exporter la ration en PDF",
            defaultextension=".pdf", initialfile=nom,
            filetypes=[("PDF", "*.pdf")])
        if not chemin:
            return
        try:
            impression.generer_liste_ration_pdf(
                self.dernier_resultat,
                int(self.pers_var.get()), int(self.jours_var.get()), chemin)
        except Exception as e:
            messagebox.showerror("PDF", f"Échec : {e}", parent=self)
            return
        _open_file(chemin)


class ReserveWindow(tk.Toplevel):
    """Gestion de la réserve de cantine (stock persistant pour la répartition)."""
    def __init__(self, master):
        super().__init__(master)
        self.title("Réserve de cantine")
        self.configure(bg=DARK_BG)
        self.geometry("820x580")
        self._center()
        self._build()
        self._load()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth()-self.winfo_width())//2
        y = (self.winfo_screenheight()-self.winfo_height())//2
        self.geometry(f"+{x}+{y}")

    def _build(self):
        bar = tk.Frame(self, bg=HEADER_BG, height=48); bar.pack(fill="x"); bar.pack_propagate(False)
        tk.Label(bar, text="📦  Réserve de cantine",
                 font=("Helvetica",13,"bold"), bg=HEADER_BG, fg="white").pack(side="left", padx=14)
        tk.Button(bar, text="✕ Fermer", command=self.destroy,
                  font=("Helvetica",9), bg=DANGER, fg="white", bd=0,
                  cursor="hand2", pady=4, padx=10).pack(side="right", padx=10)

        info = tk.Frame(self, bg=PANEL_BG); info.pack(fill="x")
        tk.Label(info, text="Stock de cantine conservé d'une répartition à l'autre. "
                 "Importez vos listes ici : les quantités s'additionnent. "
                 "Lors d'une répartition « depuis la réserve », les articles "
                 "distribués en sont automatiquement déduits.",
                 font=("Helvetica",8), bg=PANEL_BG, fg=TEXT_MUTED,
                 wraplength=780, justify="left").pack(anchor="w", padx=12, pady=6)

        # Barre d'actions
        act = tk.Frame(self, bg=PANEL_BG); act.pack(fill="x")
        tk.Button(act, text="📥  Importer une liste (ajouter au stock)",
                  command=self._importer, font=("Helvetica",9,"bold"),
                  bg="#0e7490", fg="white", bd=0, cursor="hand2",
                  pady=6, padx=12).pack(side="left", padx=8, pady=6)
        tk.Button(act, text="✏️  Modifier la quantité", command=self._modifier_qte,
                  font=("Helvetica",9), bg=ACCENT, fg="white", bd=0,
                  cursor="hand2", pady=6, padx=12).pack(side="left", padx=4, pady=6)
        tk.Button(act, text="❌  Supprimer l'article", command=self._supprimer,
                  font=("Helvetica",9), bg="#b45309", fg="white", bd=0,
                  cursor="hand2", pady=6, padx=12).pack(side="left", padx=4, pady=6)
        tk.Button(act, text="🗑  Vider la réserve", command=self._vider,
                  font=("Helvetica",9), bg=DANGER, fg="white", bd=0,
                  cursor="hand2", pady=6, padx=12).pack(side="right", padx=8, pady=6)

        cols = ("code","cat","prix","qte","valeur")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=16)
        for col,txt,w,anc in [("code","Code",80,"center"),("cat","Catégorie",130,"center"),
                              ("prix","Prix unit.",90,"center"),("qte","Quantité",80,"center"),
                              ("valeur","Valeur",100,"center")]:
            self.tree.heading(col, text=txt); self.tree.column(col, width=w, anchor=anc)
        # colonne nom via #0 ? on ajoute une colonne nom en tête
        self.tree.heading("#0", text="")
        self.tree["show"] = "tree headings"
        self.tree.heading("#0", text="Produit"); self.tree.column("#0", width=300)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True, padx=8, pady=(6,4))

        s = ttk.Style(); s.theme_use("clam")
        s.configure("Treeview", background=CARD_BG, foreground=TEXT,
                    fieldbackground=CARD_BG, rowheight=24, font=("Helvetica",9))
        s.configure("Treeview.Heading", background=HEADER_BG, foreground="white",
                    font=("Helvetica",9,"bold"))

        bbar = tk.Frame(self, bg=PANEL_BG); bbar.pack(fill="x")
        self.total_lbl = tk.Label(bbar, text="", bg=PANEL_BG, fg=GOLD,
                                  font=("Helvetica",11,"bold"))
        self.total_lbl.pack(side="left", padx=14, pady=8)

    def _load(self):
        self.tree.delete(*self.tree.get_children())
        reserve = db.get_reserve()
        for a in sorted(reserve, key=lambda x: (x["categorie"], x["id"])):
            self.tree.insert("", "end", iid=a["id"], text=a["nom"],
                values=(a["id"], a["categorie"], f"{a['prix']:.2f} €",
                        a["qte"], f"{a['prix']*a['qte']:.2f} €"))
        total = db.reserve_total()
        n = len(reserve)
        self.total_lbl.config(
            text=f"Total réserve : {total:.2f} €   ·   {n} produit(s) différent(s)")

    def _modifier_qte(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Sélection",
                "Sélectionnez d'abord un article dans la liste.", parent=self)
            return
        pid = sel[0]
        vals = self.tree.item(pid, "values")
        nom = self.tree.item(pid, "text")
        qte_actuelle = vals[3] if len(vals) > 3 else ""
        rep = simpledialog.askstring("Modifier la quantité",
            f"Nouvelle quantité pour :\n{nom}\n\n(0 pour supprimer l'article)",
            initialvalue=str(qte_actuelle), parent=self)
        if rep is None:
            return
        try:
            q = int(float(rep.strip().replace(",", ".")))
        except ValueError:
            messagebox.showwarning("Quantité invalide",
                "Entrez un nombre entier.", parent=self)
            return
        db.modifier_qte_reserve(pid, q)
        self._load()

    def _supprimer(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Sélection",
                "Sélectionnez d'abord un article dans la liste.", parent=self)
            return
        pid = sel[0]
        nom = self.tree.item(pid, "text")
        if messagebox.askyesno("Supprimer",
                f"Retirer « {nom} » de la réserve ?", parent=self):
            db.supprimer_de_reserve(pid)
            self._load()

    def _importer(self):
        chemin = filedialog.askopenfilename(
            parent=self, title="Importer une liste dans la réserve",
            filetypes=[("Fichiers pris en charge", "*.xlsx *.xls *.csv *.txt"),
                       ("Tous les fichiers", "*.*")])
        if not chemin:
            return
        produits = db.get_produits(actif_only=False)
        try:
            res = import_liste.analyser_fichier(chemin, produits)
        except Exception as e:
            messagebox.showerror("Import", f"Impossible de lire le fichier :\n{e}",
                                 parent=self)
            return
        articles = []
        for pers in res["personnes"]:
            for l in pers["lignes"]:
                articles.append(l)
        if not articles:
            msg = "Aucun produit reconnu dans le fichier."
            if res["erreurs"]:
                msg += "\n\n" + "\n".join(res["erreurs"][:8])
            messagebox.showwarning("Import", msg, parent=self)
            return
        db.ajouter_a_reserve(articles)
        self._load()
        msg = f"{len(articles)} ligne(s) ajoutée(s) à la réserve."
        if res["erreurs"]:
            msg += f"\n\n⚠️ {len(res['erreurs'])} produit(s) introuvable(s), ignoré(s)."
        messagebox.showinfo("Réserve", msg, parent=self)

    def _vider(self):
        if messagebox.askyesno("Vider la réserve",
                "Vider entièrement la réserve ? Cette action est définitive.",
                parent=self):
            db.vider_reserve()
            self._load()


class SourceRepartitionDialog(tk.Toplevel):
    """Demande la source des articles à répartir : réserve ou catalogue."""
    def __init__(self, master, total_reserve=0.0):
        super().__init__(master)
        self.resultat = None
        self.total_reserve = total_reserve
        self.title("Répartir les dettes")
        self.configure(bg=DARK_BG)
        self.resizable(False, False)
        self.grab_set()
        self._build()
        self._center()
        self.wait_window()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth()-self.winfo_width())//2
        y = (self.winfo_screenheight()-self.winfo_height())//2
        self.geometry(f"+{x}+{y}")

    def _build(self):
        frm = tk.Frame(self, bg=DARK_BG, padx=28, pady=22); frm.pack()
        tk.Label(frm, text="🎯  Répartir les articles par dette",
                 font=("Helvetica",13,"bold"), bg=DARK_BG, fg=TEXT).pack(pady=(0,6))
        tk.Label(frm, text="Où l'appli doit-elle piocher les articles à distribuer ?",
                 font=("Helvetica",9), bg=DARK_BG, fg=TEXT_MUTED).pack(pady=(0,16))
        libelle_res = f"📦  Ma réserve  ({self.total_reserve:.2f} € en stock)"
        tk.Button(frm, text=libelle_res,
                  command=lambda: self._choisir("reserve"),
                  font=("Helvetica",10,"bold"), bg="#0e7490", fg="white", bd=0,
                  cursor="hand2", pady=10, width=34).pack(pady=4)
        tk.Button(frm, text="📋  Laisser l'appli choisir dans le catalogue",
                  command=lambda: self._choisir("catalogue"),
                  font=("Helvetica",10,"bold"), bg=ACCENT, fg="white", bd=0,
                  cursor="hand2", pady=10, width=34).pack(pady=4)
        tk.Button(frm, text="Annuler", command=self.destroy,
                  font=("Helvetica",9), bg="#374151", fg=TEXT, bd=0,
                  cursor="hand2", pady=6, width=34).pack(pady=(10,0))

    def _choisir(self, val):
        self.resultat = val
        self.destroy()


class SaisieDettesDialog(tk.Toplevel):
    """Saisie des personnes et des montants dus (tableau éditable)."""
    def __init__(self, master):
        super().__init__(master)
        self.resultat = None
        self.title("Qui doit combien ?")
        self.configure(bg=DARK_BG)
        self.geometry("440x460")
        self.grab_set()
        self.rows = []
        self._build()
        self._center()
        self.wait_window()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth()-self.winfo_width())//2
        y = (self.winfo_screenheight()-self.winfo_height())//2
        self.geometry(f"+{x}+{y}")

    def _build(self):
        bar = tk.Frame(self, bg=HEADER_BG, height=44); bar.pack(fill="x"); bar.pack_propagate(False)
        tk.Label(bar, text="💰  Qui vous doit de l'argent ?",
                 font=("Helvetica",12,"bold"), bg=HEADER_BG, fg="white").pack(side="left", padx=12)
        tk.Label(self, text="Indiquez le nom de chaque personne et le montant "
                 "qu'elle vous doit.", font=("Helvetica",8), bg=DARK_BG,
                 fg=TEXT_MUTED, wraplength=400, justify="left").pack(anchor="w", padx=16, pady=(8,4))

        # En-têtes
        head = tk.Frame(self, bg=DARK_BG); head.pack(fill="x", padx=16)
        tk.Label(head, text="Nom", width=22, anchor="w", font=("Helvetica",9,"bold"),
                 bg=DARK_BG, fg=TEXT_MUTED).pack(side="left")
        tk.Label(head, text="Montant dû (€)", anchor="w", font=("Helvetica",9,"bold"),
                 bg=DARK_BG, fg=TEXT_MUTED).pack(side="left")

        self.rows_frm = tk.Frame(self, bg=DARK_BG); self.rows_frm.pack(fill="x", padx=16, pady=4)
        for _ in range(4):
            self._ajouter_ligne()

        tk.Button(self, text="＋  Ajouter une personne", command=self._ajouter_ligne,
                  font=("Helvetica",9), bg="#374151", fg=TEXT, bd=0,
                  cursor="hand2", pady=5).pack(padx=16, pady=(4,0), anchor="w")

        bbar = tk.Frame(self, bg=PANEL_BG); bbar.pack(side="bottom", fill="x")
        tk.Button(bbar, text="✓  Calculer la répartition", command=self._valider,
                  font=("Helvetica",10,"bold"), bg=SUCCESS, fg="white", bd=0,
                  cursor="hand2", pady=8).pack(side="right", padx=8, pady=8)
        tk.Button(bbar, text="Annuler", command=self.destroy,
                  font=("Helvetica",9), bg="#374151", fg=TEXT, bd=0,
                  cursor="hand2", pady=8, padx=12).pack(side="right", pady=8)

    def _ajouter_ligne(self):
        row = tk.Frame(self.rows_frm, bg=DARK_BG); row.pack(fill="x", pady=2)
        v_nom = tk.StringVar(); v_montant = tk.StringVar()
        tk.Entry(row, textvariable=v_nom, width=22, font=("Helvetica",10),
                 bg=CARD_BG, fg=TEXT, insertbackground=TEXT, bd=0, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT).pack(side="left", ipady=4, padx=(0,8))
        tk.Entry(row, textvariable=v_montant, width=12, font=("Helvetica",10),
                 bg=CARD_BG, fg=TEXT, insertbackground=TEXT, bd=0, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT).pack(side="left", ipady=4)
        self.rows.append((v_nom, v_montant))

    def _valider(self):
        dettes = []
        for v_nom, v_montant in self.rows:
            nom = v_nom.get().strip()
            mtxt = v_montant.get().strip().replace(",", ".").replace("€", "")
            if not nom or not mtxt:
                continue
            try:
                montant = float(mtxt)
            except ValueError:
                messagebox.showwarning("Montant invalide",
                    f"Le montant de « {nom} » n'est pas un nombre.", parent=self)
                return
            if montant > 0:
                dettes.append((nom, montant))
        if not dettes:
            messagebox.showwarning("Aucune dette",
                "Indiquez au moins une personne et un montant.", parent=self)
            return
        self.resultat = dettes
        self.destroy()


class RepartitionWindow(tk.Toplevel):
    """Prévisualisation de la répartition, avant création des bons-créance."""
    def __init__(self, master, resultat, mode, user_info, user_type, sig_path):
        super().__init__(master)
        self.resultat  = resultat
        self.mode      = mode
        self.user_info = user_info
        self.user_type = user_type
        self.sig_path  = sig_path
        self.produits  = db.get_produits(actif_only=False)
        self.title("Répartition proposée")
        self.configure(bg=DARK_BG)
        self.geometry("960x640")
        self._center()
        self._build()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth()-self.winfo_width())//2
        y = (self.winfo_screenheight()-self.winfo_height())//2
        self.geometry(f"+{x}+{y}")

    def _build(self):
        bar = tk.Frame(self, bg=HEADER_BG, height=48); bar.pack(fill="x"); bar.pack_propagate(False)
        tk.Label(bar, text="🎯  Répartition proposée par l'application",
                 font=("Helvetica",13,"bold"), bg=HEADER_BG, fg="white").pack(side="left", padx=14)
        tk.Button(bar, text="✕ Fermer", command=self.destroy,
                  font=("Helvetica",9), bg=DANGER, fg="white", bd=0,
                  cursor="hand2", pady=4, padx=10).pack(side="right", padx=10)

        cols = ("info","qte","prix","total")
        self.tree = ttk.Treeview(self, columns=cols, show="tree headings", height=16)
        self.tree.heading("#0", text="Personne / Catégorie / Article")
        self.tree.heading("info", text="Code")
        self.tree.heading("qte", text="Qté")
        self.tree.heading("prix", text="P.U.")
        self.tree.heading("total", text="Total")
        self.tree.column("#0", width=420)
        self.tree.column("info", width=90, anchor="center")
        self.tree.column("qte", width=60, anchor="center")
        self.tree.column("prix", width=90, anchor="center")
        self.tree.column("total", width=100, anchor="center")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True, padx=8, pady=(8,4))

        s = ttk.Style(); s.theme_use("clam")
        s.configure("Treeview", background=CARD_BG, foreground=TEXT,
                    fieldbackground=CARD_BG, rowheight=24, font=("Helvetica",9))
        s.configure("Treeview.Heading", background=HEADER_BG, foreground="white",
                    font=("Helvetica",9,"bold"))

        for p in self.resultat["personnes"]:
            ecart = p["ecart"]
            signe = "pile" if abs(ecart) < 0.005 else (f"+{ecart:.2f}€" if ecart>0 else f"{ecart:.2f}€")
            par_cat = {}
            for l in p["lignes"]:
                par_cat.setdefault(l["categorie"], []).append(l)
            p_node = self.tree.insert("", "end", open=True,
                text=f"👤 {p['nom']} — doit {p['cible']:.2f}€ → attribué "
                     f"{p['atteint']:.2f}€ ({signe})")
            for cat, lignes in par_cat.items():
                c_node = self.tree.insert(p_node, "end", open=True,
                    text=f"   📄 {cat}",
                    values=("","","", f"{sum(l['total'] for l in lignes):.2f} €"))
                for l in lignes:
                    self.tree.insert(c_node, "end", text=f"      {l['nom']}",
                        values=(l["id"], l["qte"], f"{l['prix']:.2f} €",
                                f"{l['total']:.2f} €"))

        # Reliquat (mode réserve)
        if self.mode == "reserve" and self.resultat["reste"]:
            r_node = self.tree.insert("", "end", open=False,
                text=f"📦 Restera en réserve ({self.resultat['reste_total']:.2f}€)")
            for l in self.resultat["reste"]:
                self.tree.insert(r_node, "end", text=f"      {l['nom']}",
                    values=(l["id"], l["qte"], f"{l['prix']:.2f} €",
                            f"{l['total']:.2f} €"))

        bbar = tk.Frame(self, bg=PANEL_BG); bbar.pack(fill="x")
        total_du  = sum(p["cible"] for p in self.resultat["personnes"])
        total_att = sum(p["atteint"] for p in self.resultat["personnes"])
        tk.Label(bbar,
            text=f"Total dû : {total_du:.2f} €   ·   distribué : {total_att:.2f} €",
            bg=PANEL_BG, fg=GOLD, font=("Helvetica",10,"bold")).pack(side="left", padx=14, pady=8)
        tk.Button(bbar, text="✓  Créer les bons (créances)", command=self._creer_bons,
                  font=("Helvetica",10,"bold"), bg=SUCCESS, fg="white", bd=0,
                  cursor="hand2", pady=7, padx=14).pack(side="right", padx=8, pady=6)

    def _creer_bons(self):
        date_str = datetime.now().strftime("%d/%m/%Y")
        date_creation = datetime.now()
        ui = self.user_info
        nb = 0
        for p in self.resultat["personnes"]:
            if not p["lignes"]:
                continue
            par_cat = {}
            for l in p["lignes"]:
                par_cat.setdefault(l["categorie"], []).append(l)
            for cat, lignes_cat in par_cat.items():
                total = sum(l["total"] for l in lignes_cat)
                lignes_bon = [{"id":l["id"], "nom":l["nom"], "prix":l["prix"],
                               "qte":l["qte"], "total":l["total"],
                               "qte_max":0} for l in lignes_cat]
                commande = {l["id"]: {} for l in lignes_cat}
                infos = _infos_livraison_commande(commande, self.produits, cat,
                                                  date_creation=date_creation)
                jour_creance = ", ".join(j for j, _ in infos if j)
                date_creance_val = infos[0][1].strftime("%d/%m/%Y")
                db.sauvegarder_bon(
                    cat, ui["nom"], ui["prenom"], ui["ecrou"], ui["batiment"],
                    ui["cellule"], lignes_bon, total, date_str, self.user_type,
                    est_creance=True, nom_creance=p["nom"],
                    jour_creance=jour_creance, date_creance=date_creance_val)
                nb += 1
        _rafraichir_feed_calendrier()

        # En mode réserve : le reliquat devient la nouvelle réserve
        if self.mode == "reserve":
            db.definir_reserve(self.resultat["reste"])
            reste_txt = (f"\n\nRéserve restante : {self.resultat['reste_total']:.2f} € "
                         "(conservée pour la prochaine fois).")
        else:
            reste_txt = ""

        messagebox.showinfo("Répartition terminée",
            f"{nb} bon(s)-créance créé(s).{reste_txt}\n\nRetrouvez-les dans "
            "« 💰 Créances » et l'Historique, prêts à imprimer.", parent=self)
        self.destroy()


class ImportListeWindow(tk.Toplevel):
    """Prévisualisation d'une liste de cantine importée, avant création des bons.
    Regroupe par personne puis par catégorie (un bon = une catégorie)."""
    def __init__(self, master, resultat, user_info, user_type, sig_path):
        super().__init__(master)
        self.master_app = master
        self.resultat   = resultat
        self.user_info  = user_info
        self.user_type  = user_type
        self.sig_path   = sig_path
        self.produits   = db.get_produits(actif_only=False)
        self.title("Importer une liste de cantine")
        self.configure(bg=DARK_BG)
        self.geometry("960x640")
        self._center()
        self._build()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - self.winfo_width())  // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build(self):
        bar = tk.Frame(self, bg=HEADER_BG, height=48); bar.pack(fill="x"); bar.pack_propagate(False)
        tk.Label(bar, text="📥  Aperçu de la liste importée",
                 font=("Helvetica",13,"bold"), bg=HEADER_BG, fg="white").pack(side="left", padx=14)
        tk.Button(bar, text="✕ Fermer", command=self.destroy,
                  font=("Helvetica",9), bg=DANGER, fg="white", bd=0,
                  cursor="hand2", pady=4, padx=10).pack(side="right", padx=10)

        # Option créance globale
        opt = tk.Frame(self, bg=PANEL_BG); opt.pack(fill="x")
        self.creance_var = tk.BooleanVar(value=False)
        tk.Checkbutton(opt, text="💰  Marquer tous ces bons comme créances "
                       "(dette — sans identité ni signature)",
                       variable=self.creance_var,
                       bg=PANEL_BG, fg=TEXT, activebackground=PANEL_BG,
                       activeforeground=TEXT, selectcolor=CARD_BG,
                       font=("Helvetica",9,"bold")).pack(side="left", padx=12, pady=8)

        # Zone de liste (arbre personne > catégorie > articles)
        cols = ("info","qte","prix","total")
        self.tree = ttk.Treeview(self, columns=cols, show="tree headings", height=16)
        self.tree.heading("#0", text="Personne / Catégorie / Article")
        self.tree.heading("info", text="Code")
        self.tree.heading("qte", text="Qté")
        self.tree.heading("prix", text="P.U.")
        self.tree.heading("total", text="Total")
        self.tree.column("#0", width=420)
        self.tree.column("info", width=90, anchor="center")
        self.tree.column("qte", width=60, anchor="center")
        self.tree.column("prix", width=90, anchor="center")
        self.tree.column("total", width=100, anchor="center")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True, padx=8, pady=(8,4))

        s = ttk.Style(); s.theme_use("clam")
        s.configure("Treeview", background=CARD_BG, foreground=TEXT,
                    fieldbackground=CARD_BG, rowheight=24, font=("Helvetica",9))
        s.configure("Treeview.Heading", background=HEADER_BG, foreground="white",
                    font=("Helvetica",9,"bold"))

        total_general = 0.0
        nb_bons = 0
        for pers in self.resultat["personnes"]:
            if not pers["lignes"]:
                continue
            nom_pers = pers["nom"] or "(pour vous)"
            # Regrouper par catégorie
            par_cat = {}
            for l in pers["lignes"]:
                par_cat.setdefault(l["categorie"], []).append(l)
            tot_pers = sum(l["total"] for l in pers["lignes"])
            total_general += tot_pers
            p_node = self.tree.insert("", "end",
                text=f"👤 {nom_pers}   ({len(par_cat)} bon(s) — {tot_pers:.2f} €)",
                open=True)
            for cat, lignes in par_cat.items():
                nb_bons += 1
                tot_cat = sum(l["total"] for l in lignes)
                c_node = self.tree.insert(p_node, "end",
                    text=f"   📄 {cat}", values=("", "", "", f"{tot_cat:.2f} €"), open=True)
                for l in lignes:
                    self.tree.insert(c_node, "end", text=f"      {l['nom']}",
                        values=(l["id"], l["qte"], f"{l['prix']:.2f} €",
                                f"{l['total']:.2f} €"))

        # Bandeau erreurs / avertissements
        msgs = []
        if self.resultat["erreurs"]:
            msgs.append(f"⚠️ {len(self.resultat['erreurs'])} produit(s) introuvable(s) "
                        "— ignoré(s).")
        if self.resultat["avertissements"]:
            msgs.append(f"⚠️ {len(self.resultat['avertissements'])} dépassement(s) "
                        "de quantité max.")
        if msgs:
            info = tk.Frame(self, bg="#78350f"); info.pack(fill="x")
            tk.Label(info, text="   ".join(msgs) + "  (voir détail)",
                     bg="#78350f", fg="#fef3c7", font=("Helvetica",8,"bold"),
                     cursor="hand2").pack(side="left", padx=12, pady=4)
            info.bind("<Button-1>", lambda e: self._voir_details())

        # Barre du bas
        bbar = tk.Frame(self, bg=PANEL_BG); bbar.pack(fill="x")
        self.total_lbl = tk.Label(bbar,
            text=f"Total : {total_general:.2f} €   ·   {nb_bons} bon(s) à créer",
            bg=PANEL_BG, fg=GOLD, font=("Helvetica",10,"bold"))
        self.total_lbl.pack(side="left", padx=14, pady=8)
        tk.Button(bbar, text="✓  Créer les bons", command=self._creer_bons,
                  font=("Helvetica",10,"bold"), bg=SUCCESS, fg="white", bd=0,
                  cursor="hand2", pady=7, padx=14).pack(side="right", padx=8, pady=6)

    def _voir_details(self):
        txt = ""
        if self.resultat["erreurs"]:
            txt += "Produits introuvables :\n" + "\n".join(
                "• " + e for e in self.resultat["erreurs"]) + "\n\n"
        if self.resultat["avertissements"]:
            txt += "Dépassements de quantité :\n" + "\n".join(
                "• " + a for a in self.resultat["avertissements"])
        messagebox.showinfo("Détails", txt or "Aucun problème.", parent=self)

    def _creer_bons(self):
        est_creance = self.creance_var.get()
        date_str = datetime.now().strftime("%d/%m/%Y")
        date_creation = datetime.now()
        ui = self.user_info
        nb = 0
        creance_touchee = False

        for pers in self.resultat["personnes"]:
            if not pers["lignes"]:
                continue
            nom_creance = pers["nom"] if (est_creance or pers["nom"]) else ""
            # Une personne nommée dans le fichier => créance auto à ce nom
            personne_creance = est_creance or bool(pers["nom"])

            par_cat = {}
            for l in pers["lignes"]:
                par_cat.setdefault(l["categorie"], []).append(l)

            for cat, lignes_cat in par_cat.items():
                total = sum(l["total"] for l in lignes_cat)
                lignes_bon = [{"id": l["id"], "nom": l["nom"], "prix": l["prix"],
                               "qte": l["qte"], "total": l["total"],
                               "qte_max": l["qte_max"]} for l in lignes_cat]
                jour_creance = date_creance_val = ""
                if personne_creance:
                    commande = {l["id"]: {} for l in lignes_cat}
                    infos = _infos_livraison_commande(commande, self.produits, cat,
                                                      date_creation=date_creation)
                    jour_creance = ", ".join(j for j, _ in infos if j)
                    date_creance_val = infos[0][1].strftime("%d/%m/%Y")
                    creance_touchee = True
                db.sauvegarder_bon(
                    cat, ui["nom"], ui["prenom"], ui["ecrou"], ui["batiment"],
                    ui["cellule"], lignes_bon, total, date_str, self.user_type,
                    est_creance=personne_creance,
                    nom_creance=(pers["nom"] or ""),
                    jour_creance=jour_creance, date_creance=date_creance_val)
                nb += 1

        if creance_touchee:
            _rafraichir_feed_calendrier()

        messagebox.showinfo("Import terminé",
            f"{nb} bon(s) créé(s) et enregistré(s) dans l'historique.\n\n"
            "Vous pouvez les imprimer depuis l'Historique ou « Tout imprimer ».",
            parent=self)
        self.destroy()


class ArticleNonLivreDialog(tk.Toplevel):
    """Coche les articles non livrés d'une créance : leur valeur reste due
    (nouvelle créance active), le reste est considéré récupéré."""
    def __init__(self, master, bon_id, lignes, nom_creance, callback):
        super().__init__(master)
        self.bon_id = bon_id
        self.lignes = lignes
        self.nom_creance = nom_creance
        self.callback = callback
        self.vars = []
        self.title("Article(s) non livré(s)")
        self.configure(bg=DARK_BG)
        self.geometry("560x520")
        self.grab_set()
        self._build()
        self._center()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth()-self.winfo_width())//2
        y = (self.winfo_screenheight()-self.winfo_height())//2
        self.geometry(f"+{x}+{y}")

    def _build(self):
        bar = tk.Frame(self, bg=HEADER_BG, height=46); bar.pack(fill="x"); bar.pack_propagate(False)
        tk.Label(bar, text="📦  Articles non livrés",
                 font=("Helvetica",12,"bold"), bg=HEADER_BG, fg="white").pack(side="left", padx=12)
        tk.Label(self,
            text=f"Créance de « {self.nom_creance} ».\nCochez le(s) article(s) qui "
                 "ne sont PAS arrivés : leur valeur restera en créance pour cette "
                 "personne, le reste sera marqué récupéré.",
            font=("Helvetica",9), bg=DARK_BG, fg=TEXT_MUTED,
            wraplength=520, justify="left").pack(anchor="w", padx=14, pady=(8,6))

        cadre = tk.Frame(self, bg=DARK_BG); cadre.pack(fill="both", expand=True, padx=14)
        canvas = tk.Canvas(cadre, bg=DARK_BG, highlightthickness=0)
        sb = ttk.Scrollbar(cadre, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=DARK_BG)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); canvas.pack(side="left", fill="both", expand=True)
        win = canvas.create_window((0,0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))

        for l in self.lignes:
            # l = (id, bon_id, produit_id, designation, prix, qte, total)
            pid, desig, prix, qte, total_l = l[2], l[3], l[4], l[5], l[6]
            v = tk.BooleanVar(value=False)
            self.vars.append((v, l))
            row = tk.Frame(inner, bg=CARD_BG); row.pack(fill="x", pady=2)
            tk.Checkbutton(row, variable=v, bg=CARD_BG, activebackground=CARD_BG,
                           selectcolor=DARK_BG).pack(side="left", padx=4)
            tk.Label(row, text=f"{pid}  {desig}", font=("Helvetica",9),
                     bg=CARD_BG, fg=TEXT, anchor="w").pack(side="left", fill="x",
                     expand=True, padx=4, pady=4)
            tk.Label(row, text=f"x{qte}   {total_l:.2f} €", font=("Helvetica",9),
                     bg=CARD_BG, fg=GOLD).pack(side="right", padx=8)

        bbar = tk.Frame(self, bg=PANEL_BG); bbar.pack(fill="x")
        tk.Button(bbar, text="✓  Valider", command=self._valider,
                  font=("Helvetica",10,"bold"), bg=SUCCESS, fg="white", bd=0,
                  cursor="hand2", pady=8, padx=16).pack(side="right", padx=8, pady=8)
        tk.Button(bbar, text="Annuler", command=self.destroy,
                  font=("Helvetica",9), bg="#374151", fg=TEXT, bd=0,
                  cursor="hand2", pady=8, padx=12).pack(side="right", pady=8)

    def _valider(self):
        non_livres = [l for v, l in self.vars if v.get()]
        if not non_livres:
            messagebox.showinfo("Aucun article",
                "Cochez au moins un article non livré, ou cliquez sur Annuler.",
                parent=self)
            return

        # Récupérer les infos de la créance d'origine
        info_bon = db.get_bon_complet(self.bon_id)
        if info_bon is None:
            messagebox.showerror("Erreur", "Créance introuvable.", parent=self)
            return

        # Nouvelle créance active avec seulement les articles non livrés
        lignes_bon = [{"id": l[2], "nom": l[3], "prix": l[4],
                       "qte": l[5], "total": l[6], "qte_max": 0}
                      for l in non_livres]
        total_restant = sum(l[6] for l in non_livres)

        db.sauvegarder_bon(
            info_bon["categorie"], info_bon["nom"], info_bon["prenom"],
            info_bon["ecrou"], info_bon["batiment"], info_bon["cellule"],
            lignes_bon, total_restant, info_bon["date"], info_bon["user_type"],
            est_creance=True, nom_creance=info_bon["nom_creance"],
            jour_creance=info_bon["jour_creance"], date_creance=info_bon["date_creance"])

        # L'originale : partie livrée payée -> marquée récupérée
        db.marquer_creance_soldee(self.bon_id, True)

        messagebox.showinfo("Enregistré",
            f"{len(non_livres)} article(s) non livré(s) : {total_restant:.2f} € "
            f"restent en créance pour « {info_bon['nom_creance']} ».\n\n"
            "L'ancienne créance a été marquée récupérée (partie livrée).",
            parent=self)
        self.destroy()
        if self.callback:
            self.callback()


class CreancesWindow(tk.Toplevel):
    """Liste des bons marqués comme créance (personnes qui doivent de l'argent)."""
    def __init__(self, master):
        super().__init__(master)
        self.title("Créances")
        self.configure(bg=DARK_BG)
        self.geometry("900x560")
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
        tk.Label(bar, text="💰  Créances — Personnes qui me doivent de l'argent",
                 font=("Helvetica",13,"bold"), bg=HEADER_BG, fg="white").pack(side="left", padx=14)
        tk.Button(bar, text="✕ Fermer", command=self.destroy,
                  font=("Helvetica",9), bg=DANGER, fg="white", bd=0,
                  cursor="hand2", pady=4, padx=10).pack(side="right", padx=10)

        fbar = tk.Frame(self, bg=PANEL_BG)
        fbar.pack(fill="x")
        self.afficher_soldees_var = tk.BooleanVar(value=False)
        tk.Checkbutton(fbar, text="Afficher aussi les créances déjà récupérées",
                       variable=self.afficher_soldees_var, command=self._load,
                       bg=PANEL_BG, activebackground=PANEL_BG, fg=TEXT_MUTED,
                       selectcolor=CARD_BG).pack(side="left", padx=10, pady=8)
        tk.Button(fbar, text="📥  Importer", command=self._importer,
                  font=("Helvetica",9), bg="#374151", fg=TEXT, bd=0,
                  cursor="hand2", pady=5, padx=12).pack(side="right", padx=8, pady=6)
        tk.Button(fbar, text="📤  Exporter", command=self._exporter,
                  font=("Helvetica",9), bg="#374151", fg=TEXT, bd=0,
                  cursor="hand2", pady=5, padx=12).pack(side="right", padx=4, pady=6)
        tk.Button(fbar, text="📆  Calendrier (.ics)", command=self._exporter_ics,
                  font=("Helvetica",9), bg="#0e7490", fg="white", bd=0,
                  cursor="hand2", pady=5, padx=12).pack(side="right", padx=4, pady=6)
        tk.Button(fbar, text="🧾  Récap PDF personne", command=self._recap_pdf,
                  font=("Helvetica",9,"bold"), bg="#7c3aed", fg="white", bd=0,
                  cursor="hand2", pady=5, padx=12).pack(side="right", padx=4, pady=6)

        cols = ("id","nom","montant","jour","date_recup","date_bon","categorie","statut")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="extended")
        for col, txt, w, anc in [
            ("id",         "#",            45,  "center"),
            ("nom",        "Nom",          190, "w"),
            ("montant",    "Montant",      80,  "center"),
            ("jour",       "Jour",         100, "center"),
            ("date_recup", "Date estimée", 100, "center"),
            ("date_bon",   "Date du bon",  95,  "center"),
            ("categorie",  "Catégorie",    120, "center"),
            ("statut",     "Statut",       95,  "center"),
        ]:
            self.tree.heading(col, text=txt, anchor=anc)
            self.tree.column(col, width=w, anchor=anc)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

        bbar = tk.Frame(self, bg=PANEL_BG)
        bbar.pack(fill="x")
        self.total_lbl = tk.Label(bbar, text="", bg=PANEL_BG, fg=GOLD,
                                  font=("Helvetica",10,"bold"))
        self.total_lbl.pack(side="left", padx=14, pady=8)
        tk.Button(bbar, text="✅  Marquer comme récupéré", command=self._marquer_soldee,
                  font=("Helvetica",9,"bold"), bg=SUCCESS, fg="white", bd=0,
                  cursor="hand2", pady=6, padx=10).pack(side="right", padx=8, pady=6)
        tk.Button(bbar, text="📦  Article non livré", command=self._article_non_livre,
                  font=("Helvetica",9), bg="#b45309", fg="white", bd=0,
                  cursor="hand2", pady=6, padx=10).pack(side="right", padx=4, pady=6)
        tk.Button(bbar, text="↩️  Remettre en attente", command=self._remettre_attente,
                  font=("Helvetica",9), bg="#374151", fg=TEXT, bd=0,
                  cursor="hand2", pady=6, padx=10).pack(side="right", padx=4, pady=6)
        tk.Button(bbar, text="📅  Modifier la date", command=self._modifier_date,
                  font=("Helvetica",9), bg="#b45309", fg="white", bd=0,
                  cursor="hand2", pady=6, padx=10).pack(side="right", padx=4, pady=6)

        s = ttk.Style(); s.theme_use("clam")
        s.configure("Treeview", background=CARD_BG, foreground=TEXT,
                    fieldbackground=CARD_BG, rowheight=26, font=("Helvetica",9))
        s.configure("Treeview.Heading", background=HEADER_BG, foreground="white",
                    font=("Helvetica",9,"bold"))
        s.map("Treeview", background=[("selected", ACCENT)])
        self._load()

    def _load(self):
        uniquement_actives = not self.afficher_soldees_var.get()
        rows = db.get_creances(uniquement_actives=uniquement_actives)
        self.tree.delete(*self.tree.get_children())
        total_du = 0.0
        for r in rows:
            bid, date, cat, nom, prenom, ecrou, bat, cell, total, *rest = r
            # rest = [user_type, est_creance, nom_creance, jour_creance, creance_soldee, date_creance]
            nom_creance  = rest[2] if len(rest) > 2 else ""
            jour_creance = rest[3] if len(rest) > 3 else ""
            soldee       = rest[4] if len(rest) > 4 else 0
            date_creance = rest[5] if len(rest) > 5 else ""
            statut = "✅ Récupéré" if soldee else "⏳ En attente"
            tag = "soldee" if soldee else "attente"
            self.tree.insert("", "end", iid=str(bid),
                             values=(bid, nom_creance, f"{total:.2f} €",
                                     jour_creance or "—", date_creance or "—",
                                     date, cat, statut),
                             tags=(tag,))
            if not soldee:
                total_du += total
        self.tree.tag_configure("attente", foreground=TEXT)
        self.tree.tag_configure("soldee", foreground=TEXT_MUTED)
        self.total_lbl.config(
            text=f"Total en attente : {total_du:.2f} €   ({len(rows)} créance(s) affichée(s))")

    def _marquer_soldee(self):
        sel = self.tree.selection()
        if not sel: return
        for iid in sel:
            db.marquer_creance_soldee(int(iid), True)
        _rafraichir_feed_calendrier()
        self._load()

    def _remettre_attente(self):
        sel = self.tree.selection()
        if not sel: return
        for iid in sel:
            db.marquer_creance_soldee(int(iid), False)
        _rafraichir_feed_calendrier()
        self._load()

    def _article_non_livre(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Sélection",
                "Sélectionnez d'abord la créance concernée.", parent=self)
            return
        if len(sel) > 1:
            messagebox.showinfo("Sélection",
                "Sélectionnez une seule créance à la fois pour signaler "
                "un article non livré.", parent=self)
            return
        bid = int(sel[0])
        lignes = db.get_lignes_bon(bid)  # (id, bon_id, produit_id, designation, prix, qte, total)
        if not lignes:
            messagebox.showinfo("Aucun article",
                "Cette créance ne contient aucun article.", parent=self)
            return
        info = db.get_bon_creance_info(bid)
        nom_creance = info[2] if info else ""
        ArticleNonLivreDialog(self, bid, lignes, nom_creance, self._apres_non_livre)

    def _apres_non_livre(self):
        _rafraichir_feed_calendrier()
        self._load()

    def _recap_pdf(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Sélection",
                "Sélectionnez une ou plusieurs créances dans la liste\n"
                "(Ctrl+clic ou Maj+clic pour en choisir plusieurs).",
                parent=self)
            return

        # Récupère exactement les bons sélectionnés (par id)
        bon_ids = [int(iid) for iid in sel]
        bons = db.get_bons_creance_par_ids(bon_ids)
        if not bons:
            messagebox.showinfo("Aucun article",
                "Aucun article trouvé pour la sélection.", parent=self)
            return

        # Groupe par personne, en conservant l'ordre d'apparition
        groupes = []
        index = {}
        for b in bons:
            nom = b.get("nom", "") or "(sans nom)"
            if nom not in index:
                index[nom] = len(groupes)
                groupes.append({"nom": nom, "bons": []})
            groupes[index[nom]]["bons"].append(b)

        noms = [g["nom"] for g in groupes]
        if len(noms) == 1:
            titre = noms[0]
            nom_fichier = "recap_creance_" + \
                "".join(ch if ch.isalnum() else "_" for ch in titre) + ".pdf"
        else:
            titre = f"{len(noms)} personnes"
            nom_fichier = "recap_creances_selection.pdf"

        chemin = filedialog.asksaveasfilename(
            parent=self, title=f"Enregistrer le récapitulatif — {titre}",
            defaultextension=".pdf", initialfile=nom_fichier,
            filetypes=[("PDF", "*.pdf"), ("Tous les fichiers", "*.*")])
        if not chemin:
            return
        try:
            impression.generer_recap_multi_pdf(groupes, chemin)
        except Exception as e:
            messagebox.showerror("Récapitulatif",
                f"Échec de la génération du PDF :\n{e}", parent=self)
            return
        _open_file(chemin)

    def _modifier_date(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Sélection",
                "Sélectionnez d'abord une ou plusieurs créances dans la liste.", parent=self)
            return
        vals = self.tree.item(sel[0], "values")
        date_actuelle = vals[5] if len(vals) > 5 else ""   # colonne "Date du bon"

        libelle = ("Nouvelle date de posage du bon (jj/mm/aaaa) :" if len(sel) == 1
                   else f"Nouvelle date de posage pour les {len(sel)} créances (jj/mm/aaaa) :")
        nouvelle = simpledialog.askstring(
            "Modifier la date de posage", libelle,
            initialvalue=date_actuelle, parent=self)
        if nouvelle is None:
            return
        nouvelle = nouvelle.strip()
        try:
            date_obj = datetime.strptime(nouvelle, "%d/%m/%Y")
        except ValueError:
            messagebox.showwarning("Date invalide",
                "Format attendu : jj/mm/aaaa (ex : 07/08/2026).", parent=self)
            return

        produits_ref = db.get_produits(actif_only=False)
        for iid in sel:
            bid = int(iid)
            infos_bon = db.get_bon_pour_recalcul(bid)
            jour_creance = date_creance = ""
            if infos_bon:
                categorie, pids = infos_bon
                commande = {pid: {} for pid in pids}
                infos = _infos_livraison_commande(commande, produits_ref, categorie,
                                                  date_creation=date_obj)
                jour_creance = ", ".join(j for j, _ in infos if j)
                date_creance = infos[0][1].strftime("%d/%m/%Y")
            db.modifier_date_bon(bid, nouvelle, jour_creance, date_creance)

        _rafraichir_feed_calendrier()
        self._load()
        messagebox.showinfo("Date modifiée",
            f"Date de posage mise à jour ({nouvelle}) pour "
            f"{len(sel)} créance(s).", parent=self)

    def _exporter_ics(self):
        from datetime import datetime as _dt
        # Inclut actives + soldées si la case est cochée, sinon actives seulement
        actives_seules = not self.afficher_soldees_var.get()
        creances = db.get_creances_calendrier(uniquement_actives=actives_seules)
        if not creances:
            messagebox.showinfo("Calendrier",
                "Aucune créance à exporter vers le calendrier.", parent=self)
            return
        nom_defaut = f"creances_calendrier_{_dt.now().strftime('%Y-%m-%d')}.ics"
        chemin = filedialog.asksaveasfilename(
            parent=self, title="Exporter vers le calendrier (.ics)",
            defaultextension=".ics", initialfile=nom_defaut,
            filetypes=[("Fichier calendrier", "*.ics"), ("Tous les fichiers", "*.*")])
        if not chemin:
            return
        try:
            n = calendrier.generer_ics_creances(creances, chemin)
        except Exception as e:
            messagebox.showerror("Calendrier",
                f"Échec de la génération du calendrier :\n{e}", parent=self)
            return
        if messagebox.askyesno("Calendrier créé",
                f"{n} événement(s) écrit(s) dans :\n{chemin}\n\n"
                "Voulez-vous ouvrir ce fichier maintenant pour l'importer "
                "dans votre agenda (One Calendar, Google, Outlook) ?", parent=self):
            _open_file(chemin)

    def _exporter(self):
        from datetime import datetime as _dt
        nom_defaut = f"creances_{_dt.now().strftime('%Y-%m-%d')}.json"
        chemin = filedialog.asksaveasfilename(
            parent=self, title="Exporter les créances",
            defaultextension=".json", initialfile=nom_defaut,
            filetypes=[("Fichier créances", "*.json"), ("Tous les fichiers", "*.*")])
        if not chemin:
            return
        try:
            n = db.exporter_creances(chemin)
        except Exception as e:
            messagebox.showerror("Export", f"Échec de l'export :\n{e}", parent=self)
            return
        messagebox.showinfo("Export réussi",
            f"{n} créance(s) exportée(s) vers :\n{chemin}\n\n"
            "Vous pouvez copier ce fichier sur une clé USB ou un dossier "
            "réseau, puis l'importer sur l'autre poste.", parent=self)

    def _importer(self):
        chemin = filedialog.askopenfilename(
            parent=self, title="Importer des créances",
            filetypes=[("Fichier créances", "*.json"), ("Tous les fichiers", "*.*")])
        if not chemin:
            return
        try:
            ajoutees, maj = db.importer_creances(chemin)
        except ValueError as e:
            messagebox.showerror("Import", str(e), parent=self)
            return
        except Exception as e:
            messagebox.showerror("Import", f"Échec de l'import :\n{e}", parent=self)
            return
        self._load()
        _rafraichir_feed_calendrier()
        messagebox.showinfo("Import réussi",
            f"{ajoutees} nouvelle(s) créance(s) ajoutée(s).\n"
            f"{maj} créance(s) existante(s) mise(s) à jour.", parent=self)


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
        cols = ("id","date","categorie","nom","ecrou","type","creance","total")
        self.tree = ttk.Treeview(self, columns=cols, show="headings",
                                 height=14, selectmode="browse")
        for col, txt, w, anc in [
            ("id",        "#",          45,  "center"),
            ("date",      "Date",       95,  "center"),
            ("categorie", "Catégorie", 130,  "center"),
            ("nom",       "Nom",       200,  "w"),
            ("ecrou",     "Écrou",      75,  "center"),
            ("type",      "Profil",     55,  "center"),
            ("creance",   "Créance",   110,  "center"),
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

        tk.Button(abar, text="💰  Basculer récupéré / en attente",
                  command=self._basculer_creance,
                  font=("Helvetica",10), bg="#b45309", fg="white", bd=0,
                  cursor="hand2", pady=7, padx=12).pack(side="left", padx=4, pady=6)

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
            # rest = [user_type, est_creance, nom_creance, jour_creance, creance_soldee, date_creance, uid]
            utype        = rest[0] if len(rest) > 0 else "?"
            est_creance  = rest[1] if len(rest) > 1 else 0
            nom_creance  = rest[2] if len(rest) > 2 else ""
            soldee       = rest[4] if len(rest) > 4 else 0
            badge = "👤" if utype == "yoann" else "👥"
            nom_affiche = f"💰 {nom_creance}" if est_creance and nom_creance else f"{nom} {prenom}"
            if est_creance:
                creance_txt = "✅ Récupéré" if soldee else "⏳ En attente"
                tag = "soldee" if soldee else "attente"
            else:
                creance_txt = "—"
                tag = ""
            self.tree.insert("", "end", iid=str(bid),
                             values=(bid, date, cat, nom_affiche,
                                     ecrou, badge, creance_txt, f"{total:.2f} €"),
                             tags=(tag,))
        self.tree.tag_configure("attente", foreground="#fbbf24")
        self.tree.tag_configure("soldee", foreground="#4ade80")
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

    def _basculer_creance(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Sélection",
                "Sélectionnez d'abord un bon dans la liste.", parent=self)
            return
        bid = int(sel[0])
        info = db.get_bon_creance_info(bid)
        if info is None:
            return
        est_creance, soldee, nom_creance = info
        if not est_creance:
            messagebox.showinfo("Pas une créance",
                "Ce bon n'est pas marqué comme créance, il n'y a pas d'état à basculer.",
                parent=self)
            return
        nouvel_etat = not soldee
        db.marquer_creance_soldee(bid, nouvel_etat)
        _rafraichir_feed_calendrier()
        self._load()
        self.tree.selection_set(str(bid))
        etat_txt = "récupéré" if nouvel_etat else "en attente"
        messagebox.showinfo("Créance mise à jour",
            f"La créance de « {nom_creance} » est maintenant : {etat_txt}.",
            parent=self)

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
        utype       = rest[0] if len(rest) > 0 else "invite"
        est_creance = rest[1] if len(rest) > 1 else 0
        lig_raw  = db.get_lignes_bon(bid)
        lignes   = [{"id":l[2],"nom":l[3],"prix":l[4],
                     "qte":l[5],"total":l[6],"qte_max":0} for l in lig_raw]
        sp       = None if est_creance else self._get_sig_path(utype)
        pdf_path = os.path.join(pdf_dir,
                                f"bon_{bid}_{cat.replace(' ','_').replace('&','et')}.pdf")
        if est_creance:
            nom_p = prenom_p = ecrou_p = bat_p = cell_p = ""
            date_p = date
        else:
            nom_p, prenom_p, ecrou_p, bat_p, cell_p, date_p = _identite_bon(
                nom, prenom, ecrou, bat, cell, date)
        impression.generer_bon_pdf(cat, nom_p, prenom_p, ecrou_p, bat_p, cell_p,
                                   lignes, total, date_p, pdf_path,
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


class RemboursementsWindow(tk.Toplevel):
    """Suivi des articles (de mes bons) à rembourser : ajout depuis un bon,
    conservation avec dates de commande/livraison, validation du remboursement."""
    def __init__(self, master):
        super().__init__(master)
        self.title("Remboursements")
        self.configure(bg=DARK_BG)
        self.geometry("760x600")

        bar = tk.Frame(self, bg="#b45309", height=50); bar.pack(fill="x"); bar.pack_propagate(False)
        tk.Label(bar, text="💶  Articles à rembourser", font=("Helvetica", 14, "bold"),
                 bg="#b45309", fg="white").pack(side="left", padx=18)
        tk.Button(bar, text="✕  Fermer", command=self.destroy, font=("Helvetica", 10),
                  bg=DANGER, fg="white", bd=0, cursor="hand2", pady=6, padx=14).pack(
                  side="right", padx=12, pady=8)

        outils = tk.Frame(self, bg=PANEL_BG); outils.pack(fill="x")
        tk.Button(outils, text="➕  Ajouter depuis un bon",
                  command=self._ajouter_depuis_bon, font=("Helvetica", 10, "bold"),
                  bg=SUCCESS, fg="white", bd=0, cursor="hand2", pady=7, padx=10).pack(
                  side="left", padx=10, pady=8)
        tk.Button(outils, text="⟳  Actualiser", command=self._charger,
                  font=("Helvetica", 10), bg=CARD_BG, fg=TEXT, bd=0, cursor="hand2",
                  pady=7, padx=10).pack(side="left", padx=4, pady=8)

        corps = tk.Frame(self, bg=DARK_BG); corps.pack(fill="both", expand=True, padx=10, pady=8)
        self.canvas = tk.Canvas(corps, bg=DARK_BG, highlightthickness=0)
        sb = tk.Scrollbar(corps, orient="vertical", command=self.canvas.yview)
        self.liste = tk.Frame(self.canvas, bg=DARK_BG)
        self.liste.bind("<Configure>",
                        lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._cv_item = self.canvas.create_window((0, 0), window=self.liste, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self._cv_item, width=e.width))
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        self._charger()

    def _fmt(self, d):
        import datetime as _dt
        for f in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return _dt.datetime.strptime((d or "").strip(), f).strftime("%d/%m/%Y")
            except Exception:
                pass
        return d or "?"

    def _charger(self):
        for w in self.liste.winfo_children():
            w.destroy()
        try:
            a_faire = db.get_remboursements("a_rembourser")
            faits = db.get_remboursements("rembourse")
        except Exception as e:
            tk.Label(self.liste, text=f"Erreur : {e}", bg=DARK_BG, fg=DANGER).pack(pady=20)
            return

        total = sum(float(r["prix"] or 0) * int(r["quantite"]) for r in a_faire)
        tk.Label(self.liste, text=f"À REMBOURSER  —  {len(a_faire)} article(s)  "
                 f"({total:.2f} €)", font=("Helvetica", 11, "bold"), bg=DARK_BG,
                 fg=GOLD, anchor="w").pack(fill="x", pady=(2, 6))
        if not a_faire:
            tk.Label(self.liste, text="Rien à rembourser pour l'instant.",
                     bg=DARK_BG, fg=TEXT_MUTED).pack(anchor="w", padx=6, pady=4)
        for r in a_faire:
            self._carte(r, en_attente=True)

        tk.Label(self.liste, text="DÉJÀ REMBOURSÉS", font=("Helvetica", 11, "bold"),
                 bg=DARK_BG, fg=TEXT_MUTED, anchor="w").pack(fill="x", pady=(16, 6))
        if not faits:
            tk.Label(self.liste, text="(aucun)", bg=DARK_BG, fg=TEXT_MUTED).pack(
                     anchor="w", padx=6)
        for r in faits:
            self._carte(r, en_attente=False)

    def _carte(self, r, en_attente):
        carte = tk.Frame(self.liste, bg=CARD_BG,
                         highlightbackground=(GOLD if en_attente else BORDER),
                         highlightthickness=1)
        carte.pack(fill="x", pady=3)
        haut = tk.Frame(carte, bg=CARD_BG); haut.pack(fill="x", padx=10, pady=(7, 1))
        tk.Label(haut, text=f"{r['nom']}  ×{r['quantite']}", font=("Helvetica", 11, "bold"),
                 bg=CARD_BG, fg=TEXT).pack(side="left")
        montant = float(r["prix"] or 0) * int(r["quantite"])
        tk.Label(haut, text=f"{montant:.2f} €", font=("Helvetica", 10, "bold"),
                 bg=CARD_BG, fg=GOLD).pack(side="left", padx=10)
        if en_attente:
            tk.Button(haut, text="🗑", command=lambda i=r["id"]: self._supprimer(i),
                      font=("Helvetica", 9), bg=DANGER, fg="white", bd=0, cursor="hand2",
                      padx=8, pady=3).pack(side="right")
            tk.Button(haut, text="✓ Remboursé", command=lambda i=r["id"]: self._valider(i),
                      font=("Helvetica", 9, "bold"), bg=SUCCESS, fg="white", bd=0,
                      cursor="hand2", padx=8, pady=3).pack(side="right", padx=6)
        else:
            tk.Label(haut, text=f"remboursé le {self._fmt(r['date_remboursement'])}",
                     font=("Helvetica", 9), bg=CARD_BG, fg=SUCCESS).pack(side="right")
        info = (f"{r['categorie']}  •  commandé le {self._fmt(r['date_commande'])}"
                f"  •  livraison prévue {self._fmt(r['date_livraison'])}")
        tk.Label(carte, text=info, font=("Helvetica", 9), bg=CARD_BG, fg=TEXT_MUTED,
                 anchor="w").pack(fill="x", padx=10, pady=(0, 7))

    def _valider(self, rid):
        db.valider_remboursement(rid)
        self._charger()

    def _supprimer(self, rid):
        if messagebox.askyesno("Supprimer", "Retirer cet article du suivi des "
                               "remboursements ?", parent=self):
            db.supprimer_remboursement(rid)
            self._charger()

    def _ajouter_depuis_bon(self):
        AjoutRemboursementDialog(self, on_ajout=self._charger)


class AjoutRemboursementDialog(tk.Toplevel):
    """Choisir un de mes bons, puis les articles (et quantités) à rembourser."""
    def __init__(self, parent, on_ajout=None):
        super().__init__(parent)
        self.on_ajout = on_ajout
        self.title("Ajouter un remboursement")
        self.configure(bg=DARK_BG)
        self.geometry("560x560")
        try:
            self.bons = db.get_bons_mon_nom()
        except Exception:
            self.bons = []

        tk.Label(self, text="➕ Articles à rembourser", font=("Helvetica", 13, "bold"),
                 bg=DARK_BG, fg=TEXT).pack(pady=(10, 2))
        tk.Label(self, text="Choisis un de tes bons, puis coche les articles non reçus "
                 "/ à rembourser et leur quantité.", font=("Helvetica", 9), bg=DARK_BG,
                 fg=TEXT_MUTED, wraplength=520, justify="center").pack(pady=(0, 6))

        if not self.bons:
            tk.Label(self, text="Aucun bon à ton nom trouvé.", bg=DARK_BG,
                     fg=TEXT_MUTED, font=("Helvetica", 11)).pack(pady=30)
            return

        sel = tk.Frame(self, bg=DARK_BG); sel.pack(fill="x", padx=14)
        tk.Label(sel, text="Bon :", bg=DARK_BG, fg=TEXT, font=("Helvetica", 10)).pack(side="left")
        self.bon_var = tk.StringVar()
        libelles = [f"{self._fmt(b['date'])} — {b['categorie']} "
                    f"({len(b['lignes'])} article(s))" for b in self.bons]
        self.bon_var.set(libelles[0])
        om = tk.OptionMenu(sel, self.bon_var, *libelles, command=lambda _=None: self._maj_articles())
        om.config(font=("Helvetica", 9), bg=CARD_BG, fg=TEXT, bd=0, highlightthickness=0,
                  activebackground=CARD_BG); om.pack(side="left", padx=8, fill="x", expand=True)
        self._libelles = libelles

        self.zone = tk.Frame(self, bg=DARK_BG); self.zone.pack(fill="both", expand=True,
                                                               padx=14, pady=8)
        tk.Button(self, text="Ajouter au suivi des remboursements", command=self._valider,
                  font=("Helvetica", 10, "bold"), bg=SUCCESS, fg="white", bd=0,
                  cursor="hand2", pady=8).pack(fill="x", padx=14, pady=(0, 12))
        self._maj_articles()

    def _fmt(self, d):
        import datetime as _dt
        for f in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return _dt.datetime.strptime((d or "").strip(), f).strftime("%d/%m/%Y")
            except Exception:
                pass
        return d or "?"

    def _bon_courant(self):
        try:
            return self.bons[self._libelles.index(self.bon_var.get())]
        except Exception:
            return self.bons[0]

    def _maj_articles(self):
        for w in self.zone.winfo_children():
            w.destroy()
        b = self._bon_courant()
        tk.Label(self.zone, text=f"Livraison prévue : {self._fmt(b['date_livraison'])}",
                 font=("Helvetica", 9, "italic"), bg=DARK_BG, fg=TEXT_MUTED).pack(anchor="w")
        self.rows = []
        for l in b["lignes"]:
            row = tk.Frame(self.zone, bg=CARD_BG); row.pack(fill="x", pady=2)
            v = tk.BooleanVar(value=False)
            tk.Checkbutton(row, variable=v, bg=CARD_BG, activebackground=CARD_BG,
                           selectcolor=DARK_BG, bd=0, highlightthickness=0).pack(side="left", padx=4)
            tk.Label(row, text=f"{l['nom']}", font=("Helvetica", 10, "bold"), bg=CARD_BG,
                     fg=TEXT, anchor="w", wraplength=300, justify="left").pack(
                     side="left", fill="x", expand=True, pady=6)
            tk.Label(row, text=f"commandé {l['qte']}", font=("Helvetica", 9),
                     bg=CARD_BG, fg=TEXT_MUTED).pack(side="left", padx=4)
            sp = tk.Spinbox(row, from_=1, to=max(1, l['qte']), width=4,
                            font=("Helvetica", 10), bg=DARK_BG, fg=TEXT, bd=0,
                            buttonbackground=CARD_BG, insertbackground=TEXT, justify="center")
            sp.delete(0, "end"); sp.insert(0, str(l['qte']))
            sp.pack(side="right", padx=8)
            self.rows.append((v, sp, l))

    def _valider(self):
        b = self._bon_courant()
        arts = []
        for v, sp, l in self.rows:
            if not v.get():
                continue
            try:
                q = int(sp.get())
            except ValueError:
                q = l['qte']
            arts.append({"id": l["id"], "nom": l["nom"], "categorie": b["categorie"],
                         "prix": l["prix"], "quantite": q,
                         "date_commande": b["date"], "date_livraison": b["date_livraison"],
                         "source_uid": b["uid"]})
        if not arts:
            messagebox.showinfo("Remboursement", "Coche au moins un article.", parent=self)
            return
        db.ajouter_remboursement(arts)
        if self.on_ajout:
            self.on_ajout()
        messagebox.showinfo("Remboursement", f"{len(arts)} article(s) ajouté(s) au "
                            "suivi des remboursements.", parent=self)
        self.destroy()


class LivraisonsWindow(tk.Toplevel):
    """Livraisons attendues (cantines à mon nom + créances) : voir, annuler,
    et récupérer rétroactivement les bons/créances déjà saisis."""
    def __init__(self, master):
        super().__init__(master)
        self.title("Livraisons à venir")
        self.configure(bg=DARK_BG)
        self.geometry("720x560")

        bar = tk.Frame(self, bg=HEADER_BG, height=50); bar.pack(fill="x"); bar.pack_propagate(False)
        tk.Label(bar, text="🚚  Livraisons attendues", font=("Helvetica", 14, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=18)
        tk.Button(bar, text="✕  Fermer", command=self.destroy, font=("Helvetica", 10),
                  bg=DANGER, fg="white", bd=0, cursor="hand2", pady=6, padx=14).pack(
                  side="right", padx=12, pady=8)

        outils = tk.Frame(self, bg=PANEL_BG); outils.pack(fill="x")
        tk.Button(outils, text="⟲  Récupérer les bons/créances déjà saisis",
                  command=self._retroactif, font=("Helvetica", 10, "bold"),
                  bg=SUCCESS, fg="white", bd=0, cursor="hand2", pady=7, padx=10).pack(
                  side="left", padx=10, pady=8)
        tk.Button(outils, text="⟳  Actualiser", command=self._charger,
                  font=("Helvetica", 10), bg=CARD_BG, fg=TEXT, bd=0, cursor="hand2",
                  pady=7, padx=10).pack(side="left", padx=4, pady=8)
        tk.Label(outils, text="La confirmation de réception se fait dans le widget 📦 Mon stock.",
                 font=("Helvetica", 8), bg=PANEL_BG, fg=TEXT_MUTED).pack(side="left", padx=10)

        corps = tk.Frame(self, bg=DARK_BG); corps.pack(fill="both", expand=True, padx=10, pady=8)
        self.canvas = tk.Canvas(corps, bg=DARK_BG, highlightthickness=0)
        sb = tk.Scrollbar(corps, orient="vertical", command=self.canvas.yview)
        self.liste = tk.Frame(self.canvas, bg=DARK_BG)
        self.liste.bind("<Configure>",
                        lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._cv_item = self.canvas.create_window((0, 0), window=self.liste, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self._cv_item, width=e.width))
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")

        self._charger()

    def _charger(self):
        for w in self.liste.winfo_children():
            w.destroy()
        try:
            recs = db.get_receptions()
        except Exception as e:
            tk.Label(self.liste, text=f"Erreur : {e}", bg=DARK_BG, fg=DANGER).pack(pady=20)
            return
        if not recs:
            tk.Label(self.liste, text="Aucune livraison attendue.\n\nUtilisez "
                     "« Récupérer les bons/créances déjà saisis » pour importer "
                     "l'existant.", bg=DARK_BG, fg=TEXT_MUTED, font=("Helvetica", 11),
                     justify="center").pack(pady=30)
            return
        import datetime as _dt
        today = _dt.date.today().strftime("%Y-%m-%d")
        for r in recs:
            due = r["date_prevue"] <= today
            carte = tk.Frame(self.liste, bg=CARD_BG,
                             highlightbackground=(GOLD if due else BORDER),
                             highlightthickness=1)
            carte.pack(fill="x", pady=4)
            haut = tk.Frame(carte, bg=CARD_BG); haut.pack(fill="x", padx=10, pady=(8, 2))
            try:
                dfr = _dt.datetime.strptime(r["date_prevue"], "%Y-%m-%d").strftime("%d/%m/%Y")
            except Exception:
                dfr = r["date_prevue"]
            if r["type"] == "creance":
                titre = f"💰 Créance de {r['personne']}  ({r['categorie']})"
            else:
                titre = f"🛒 Ma cantine  ({r['categorie']})"
            tk.Label(haut, text=titre, font=("Helvetica", 11, "bold"), bg=CARD_BG,
                     fg=TEXT).pack(side="left")
            etat = "à réceptionner" if due else "prévue"
            tk.Label(haut, text=f"{etat} le {dfr}", font=("Helvetica", 9),
                     bg=CARD_BG, fg=(GOLD if due else TEXT_MUTED)).pack(side="left", padx=10)
            tk.Button(haut, text="🗑 Annuler", command=lambda i=r["id"]: self._supprimer(i),
                      font=("Helvetica", 8), bg=DANGER, fg="white", bd=0, cursor="hand2",
                      padx=8, pady=3).pack(side="right")
            arts = ", ".join(f"{l['nom']} ×{l['qte_attendue']}" for l in r["lignes"])
            tk.Label(carte, text=arts, font=("Helvetica", 9), bg=CARD_BG, fg=TEXT_MUTED,
                     anchor="w", justify="left", wraplength=640).pack(fill="x", padx=10, pady=(0, 8))

    def _supprimer(self, rid):
        if not messagebox.askyesno("Annuler", "Supprimer cette livraison attendue ?",
                                   parent=self):
            return
        try:
            db.supprimer_reception(rid)
        except Exception as e:
            messagebox.showerror("Annuler", f"Échec : {e}", parent=self)
        self._charger()

    def _retroactif(self):
        try:
            n = db.creer_receptions_retroactives()
        except Exception as e:
            messagebox.showerror("Récupération", f"Échec : {e}", parent=self)
            return
        messagebox.showinfo("Récupération",
            f"{n} livraison(s) attendue(s) créée(s) à partir des bons/créances "
            f"déjà saisis." if n else
            "Aucune nouvelle livraison à récupérer (déjà à jour).", parent=self)
        self._charger()


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    # Mode widget intégré : « Cantine.exe --widget » lance directement le petit
    # widget de stock (gadget de bureau), sans login ni fenêtre principale.
    if "--widget" in sys.argv:
        import widget_stock
        widget_stock.main()
    else:
        db.init_db()
        login = LoginWindow()
        login.mainloop()
        if login.user_type:
            app = CantineApp(login.user_type, login.user_info)
            app.mainloop()
