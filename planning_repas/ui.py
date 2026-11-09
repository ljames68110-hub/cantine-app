# -*- coding: utf-8 -*-
"""
Interface Tkinter du module Planning Repas.

S'integre dans Gestion Cantine sous forme d'un simple Frame :

    from planning_repas import CadrePlanningRepas
    notebook.add(CadrePlanningRepas(notebook, chemin_db="cantine.db"),
                 text="Planning repas")
"""
import datetime as dt
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from . import db as dbmod
from . import generateur as gen
from . import export as exp


class CadrePlanningRepas(ttk.Frame):
    def __init__(self, parent, chemin_db="cantine.db", dossier_export=None, **kw):
        super().__init__(parent, **kw)
        self.chemin_db = chemin_db
        self.con = dbmod.initialiser(chemin_db)
        self._widget = None
        self.dossier_export = dossier_export or os.path.dirname(
            os.path.abspath(chemin_db)) or "."
        self.jours = []
        self.extras = []
        self.planning_id = None
        self._construire()
        self._rafraichir_catalogue()
        self._rafraichir_recettes()
        self._rafraichir_regles()
        self._rafraichir_plannings()

    # ------------------------------------------------------------------ UI
    def _construire(self):
        self.onglets = ttk.Notebook(self)
        self.onglets.pack(fill="both", expand=True, padx=6, pady=6)
        self._onglet_planning()
        self._onglet_courses()
        self._onglet_catalogue()
        self._onglet_recettes()
        self._onglet_regles()

    # -------------------------------------------------------- onglet 1
    def _onglet_planning(self):
        f = ttk.Frame(self.onglets)
        self.onglets.add(f, text="Planning")

        barre = ttk.LabelFrame(f, text="Parametres")
        barre.pack(fill="x", padx=4, pady=4)

        self.v_date = tk.StringVar(value=dt.date.today().isoformat())
        self.v_jours = tk.IntVar(value=15)
        self.v_pers = tk.IntVar(value=2)
        self.v_budget = tk.StringVar(value="200")
        self.v_dess = tk.IntVar(value=1)
        self.v_gat = tk.IntVar(value=2)

        champs = [("Debut (AAAA-MM-JJ)", self.v_date, 12),
                  ("Jours", self.v_jours, 4),
                  ("Personnes", self.v_pers, 4),
                  ("Budget cible EUR", self.v_budget, 7),
                  ("Desserts / semaine", self.v_dess, 4),
                  ("Gateaux / week-end", self.v_gat, 4)]
        for i, (lib, var, w) in enumerate(champs):
            ttk.Label(barre, text=lib).grid(row=0, column=i * 2, sticky="e",
                                            padx=(8, 2), pady=6)
            if var in (self.v_pers, self.v_jours, self.v_dess, self.v_gat):
                haut = {id(self.v_jours): 60, id(self.v_pers): 12,
                        id(self.v_dess): 7, id(self.v_gat): 7}[id(var)]
                ttk.Spinbox(barre, from_=0 if var is not self.v_pers else 1,
                            to=haut, width=w, textvariable=var,
                            command=self._maj_apercu_personnes).grid(
                    row=0, column=i * 2 + 1, sticky="w")
            else:
                ttk.Entry(barre, textvariable=var, width=w).grid(
                    row=0, column=i * 2 + 1, sticky="w")

        boutons = ttk.Frame(f)
        boutons.pack(fill="x", padx=4)
        ttk.Button(boutons, text="Generer", command=self.generer).pack(side="left", padx=3)
        ttk.Button(boutons, text="Remplacer le plat du jour",
                   command=lambda: self.remplacer("plat")).pack(side="left", padx=3)
        ttk.Button(boutons, text="Remplacer le dessert",
                   command=lambda: self.remplacer("dessert")).pack(side="left", padx=3)
        ttk.Button(boutons, text="Retirer le dessert",
                   command=self.retirer_dessert).pack(side="left", padx=3)
        ttk.Button(boutons, text="Personnes pour ce jour",
                   command=self.personnes_du_jour).pack(side="left", padx=3)
        ttk.Button(boutons, text="Appliquer a tous les jours",
                   command=self.appliquer_personnes_a_tous).pack(side="left", padx=3)
        ttk.Button(boutons, text="Widget bureau",
                   command=self.ouvrir_widget).pack(side="left", padx=3)
        ttk.Button(boutons, text="Enregistrer", command=self.enregistrer).pack(side="left", padx=3)

        self.lb_astuce = ttk.Label(f, text="", foreground="#8a6d1f")
        self.lb_astuce.pack(fill="x", padx=8, pady=(4, 0))

        corps = ttk.Frame(f)
        corps.pack(fill="both", expand=True, padx=4, pady=4)

        self.tv_jours = ttk.Treeview(
            corps, columns=("date", "jour", "pers", "plat", "dessert"),
            show="headings", height=16)
        for col, lib, w in (("date", "Date", 90), ("jour", "Jour", 80),
                            ("pers", "Pers.", 50),
                            ("plat", "Plat", 290), ("dessert", "Dessert", 210)):
            self.tv_jours.heading(col, text=lib)
            self.tv_jours.column(col, width=w, anchor="w")
        self.tv_jours.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(corps, orient="vertical", command=self.tv_jours.yview)
        sb.pack(side="left", fill="y")
        self.tv_jours.configure(yscrollcommand=sb.set)
        self.tv_jours.bind("<Double-1>", lambda e: self.remplacer("plat"))

        droite = ttk.LabelFrame(corps, text="Plannings enregistres")
        droite.pack(side="left", fill="y", padx=(8, 0))
        self.lb_plannings = tk.Listbox(droite, width=34, height=14)
        self.lb_plannings.pack(padx=4, pady=4, fill="y", expand=True)
        ttk.Button(droite, text="Ouvrir", command=self.ouvrir_planning).pack(fill="x", padx=4)
        ttk.Button(droite, text="Supprimer", command=self.supprimer_planning).pack(
            fill="x", padx=4, pady=(2, 6))

    # -------------------------------------------------------- onglet 2
    def _onglet_courses(self):
        f = ttk.Frame(self.onglets)
        self.onglets.add(f, text="Liste de courses")

        haut = ttk.Frame(f)
        haut.pack(fill="x", padx=4, pady=4)
        ttk.Button(haut, text="Calculer", command=self.calculer_courses).pack(side="left", padx=3)
        ttk.Button(haut, text="Ajouter un produit hors repas",
                   command=self.ajouter_extra).pack(side="left", padx=3)
        ttk.Button(haut, text="Retirer la ligne", command=self.retirer_extra).pack(side="left", padx=3)
        ttk.Button(haut, text="Export CSV bon de cantine",
                   command=self.export_csv_bon).pack(side="left", padx=3)
        ttk.Button(haut, text="Export CSV detaille",
                   command=self.export_csv_detaille).pack(side="left", padx=3)
        ttk.Button(haut, text="Export PDF", command=self.export_pdf).pack(side="left", padx=3)

        self.tv_courses = ttk.Treeview(
            f, columns=("lot", "cat", "code", "des", "qte", "pu", "pt", "max", "alerte"),
            show="headings", height=18)
        entetes = (("lot", "Lot", 90), ("cat", "Categorie", 110), ("code", "Code", 60),
                   ("des", "Designation", 300), ("qte", "Qte", 50),
                   ("pu", "PU", 60), ("pt", "Total", 70), ("max", "Max", 50),
                   ("alerte", "Alerte", 130))
        for col, lib, w in entetes:
            self.tv_courses.heading(col, text=lib)
            self.tv_courses.column(col, width=w, anchor="w")
        self.tv_courses.tag_configure("alerte", background="#ffe0e0")
        self.tv_courses.pack(fill="both", expand=True, padx=4)

        bas = ttk.Frame(f)
        bas.pack(fill="x", padx=4, pady=4)
        self.lb_total = ttk.Label(bas, text="Total : -", font=("TkDefaultFont", 10, "bold"))
        self.lb_total.pack(side="left")
        self.lb_conseil = ttk.Label(bas, text="", foreground="#8a4b00")
        self.lb_conseil.pack(side="left", padx=16)

    # -------------------------------------------------------- onglet 3
    def _onglet_catalogue(self):
        f = ttk.Frame(self.onglets)
        self.onglets.add(f, text="Catalogue")

        haut = ttk.Frame(f)
        haut.pack(fill="x", padx=4, pady=4)
        self.v_filtre = tk.StringVar()
        ttk.Label(haut, text="Recherche").pack(side="left")
        e = ttk.Entry(haut, textvariable=self.v_filtre, width=30)
        e.pack(side="left", padx=4)
        e.bind("<KeyRelease>", lambda ev: self._rafraichir_catalogue())
        ttk.Button(haut, text="Modifier la ligne", command=self.modifier_produit).pack(side="left", padx=3)
        ttk.Button(haut, text="Ajouter un produit", command=self.ajouter_produit).pack(side="left", padx=3)
        ttk.Button(haut, text="Activer / desactiver", command=self.basculer_produit).pack(side="left", padx=3)
        ttk.Button(haut, text="Recharger le catalogue livre",
                   command=self.recharger_catalogue).pack(side="right", padx=3)

        self.tv_cat = ttk.Treeview(f, columns=("code", "des", "prix", "max", "cat", "actif"),
                                   show="headings", height=20)
        for col, lib, w in (("code", "Code", 70), ("des", "Designation", 330),
                            ("prix", "Prix", 70), ("max", "Qte max", 70),
                            ("cat", "Categorie", 130), ("actif", "Actif", 60)):
            self.tv_cat.heading(col, text=lib)
            self.tv_cat.column(col, width=w, anchor="w")
        self.tv_cat.pack(fill="both", expand=True, padx=4, pady=(0, 6))
        self.tv_cat.bind("<Double-1>", lambda e: self.modifier_produit())

    # -------------------------------------------------------- onglet 4
    def _onglet_recettes(self):
        f = ttk.Frame(self.onglets)
        self.onglets.add(f, text="Recettes")

        gauche = ttk.Frame(f)
        gauche.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        self.tv_rec = ttk.Treeview(gauche, columns=("nom", "type", "actif"),
                                   show="headings", height=20)
        for col, lib, w in (("nom", "Nom", 280), ("type", "Type", 90), ("actif", "Actif", 60)):
            self.tv_rec.heading(col, text=lib)
            self.tv_rec.column(col, width=w, anchor="w")
        self.tv_rec.pack(fill="both", expand=True)
        self.tv_rec.bind("<<TreeviewSelect>>", lambda e: self._afficher_recette())

        barre = ttk.Frame(gauche)
        barre.pack(fill="x", pady=4)
        ttk.Button(barre, text="Activer / desactiver",
                   command=self.basculer_recette).pack(side="left", padx=3)
        ttk.Button(barre, text="Ajouter un ingredient",
                   command=self.ajouter_ingredient).pack(side="left", padx=3)
        ttk.Button(barre, text="Retirer l'ingredient",
                   command=self.retirer_ingredient).pack(side="left", padx=3)

        droite = ttk.Frame(f)
        droite.pack(side="left", fill="both", expand=True, padx=4, pady=4)

        # Sélecteur "pour X personnes"
        sel = ttk.Frame(droite); sel.pack(fill="x", pady=(0, 4))
        ttk.Label(sel, text="Ingrédients pour ").pack(side="left")
        self.v_rec_pers = tk.IntVar(value=2)
        ttk.Spinbox(sel, from_=1, to=20, width=4, textvariable=self.v_rec_pers,
                    command=self._afficher_recette).pack(side="left")
        ttk.Label(sel, text=" personne(s)").pack(side="left")
        self.v_rec_pers.trace_add("write", lambda *_: self._afficher_recette())

        self.tv_ing = ttk.Treeview(droite, columns=("des", "qte"),
                                   show="headings", height=9)
        for col, lib, w in (("des", "Ingrédient", 300), ("qte", "Quantité", 130)):
            self.tv_ing.heading(col, text=lib)
            self.tv_ing.column(col, width=w, anchor="w")
        self.tv_ing.pack(fill="x")
        ttk.Label(droite, text="Instructions").pack(anchor="w", pady=(8, 0))
        self.txt_rec = tk.Text(droite, height=14, wrap="word")
        self.txt_rec.pack(fill="both", expand=True)
        ttk.Button(droite, text="Enregistrer les instructions",
                   command=self.enregistrer_instructions).pack(anchor="e", pady=4)
        ttk.Button(droite, text="▶  Voir la video de la recette (YouTube)",
                   command=self.voir_video).pack(anchor="e", pady=2)

    # -------------------------------------------------------- onglet 5
    def _onglet_regles(self):
        f = ttk.Frame(self.onglets)
        self.onglets.add(f, text="Regles alimentaires")

        ttk.Label(f, text="Une regle exclut un produit par son code, ou tout produit "
                          "dont la designation contient le mot-cle.",
                  foreground="#444").pack(anchor="w", padx=6, pady=(8, 4))

        self.tv_reg = ttk.Treeview(f, columns=("type", "valeur", "motif", "actif"),
                                   show="headings", height=18)
        for col, lib, w in (("type", "Type", 90), ("valeur", "Valeur", 180),
                            ("motif", "Motif", 320), ("actif", "Actif", 60)):
            self.tv_reg.heading(col, text=lib)
            self.tv_reg.column(col, width=w, anchor="w")
        self.tv_reg.pack(fill="both", expand=True, padx=6)

        barre = ttk.Frame(f)
        barre.pack(fill="x", padx=6, pady=6)
        self.v_rtype = tk.StringVar(value="motcle")
        ttk.Combobox(barre, textvariable=self.v_rtype, values=["motcle", "code"],
                     width=8, state="readonly").pack(side="left")
        self.v_rval = tk.StringVar()
        ttk.Entry(barre, textvariable=self.v_rval, width=20).pack(side="left", padx=4)
        self.v_rmotif = tk.StringVar()
        ttk.Entry(barre, textvariable=self.v_rmotif, width=34).pack(side="left", padx=4)
        ttk.Button(barre, text="Ajouter", command=self.ajouter_regle).pack(side="left", padx=3)
        ttk.Button(barre, text="Activer / desactiver",
                   command=self.basculer_regle).pack(side="left", padx=3)
        ttk.Button(barre, text="Supprimer", command=self.supprimer_regle).pack(side="left", padx=3)

    # ------------------------------------------------------------ actions
    def generer(self):
        try:
            date_debut = dt.date.fromisoformat(self.v_date.get().strip())
        except ValueError:
            messagebox.showerror("Date", "Format attendu : AAAA-MM-JJ")
            return
        try:
            self.jours = gen.composer(
                self.con, date_debut, nb_jours=max(1, self.v_jours.get()),
                nb_personnes=max(1, self.v_pers.get()),
                desserts_semaine=max(0, self.v_dess.get()),
                gateaux_weekend=max(0, self.v_gat.get()))
        except ValueError as e:
            messagebox.showerror("Generation", str(e))
            return
        self.planning_id = None
        self.extras = []
        self._afficher_jours()
        self.calculer_courses()

    def _afficher_jours(self):
        self.tv_jours.delete(*self.tv_jours.get_children())
        for j in self.jours:
            dessert = j["dessert"]["nom"] if j["dessert"] else ""
            if j["dessert"] and j["dessert"]["type"] == "gateau":
                dessert = "[gateau] " + dessert
            self.tv_jours.insert("", "end", iid=str(j["index"]), values=(
                j["date"].strftime("%d/%m/%Y"), j["jour_nom"].capitalize(),
                j.get("nb_personnes") or self.v_pers.get(),
                j["plat"]["nom"] if j["plat"] else "", dessert))

    def _maj_apercu_personnes(self):
        """Le compteur global ne modifie pas un planning deja genere : il faut
        soit regenerer, soit cliquer sur 'Appliquer a tous les jours'."""
        if self.jours:
            self.lb_astuce.config(
                text="Valeur globale modifiee : clique sur "
                     "'Appliquer a tous les jours' pour la repercuter.")

    def personnes_du_jour(self):
        """Change le nombre de convives d'un seul soir.

        Utile quand on est deux la semaine et trois le week-end : la liste de
        courses recalcule chaque jour avec sa propre valeur.
        """
        j = self._jour_selectionne()
        if not j:
            return
        actuel = j.get("nb_personnes") or self.v_pers.get()
        n = self._demander_nombre(
            f'Personnes le {j["jour_nom"]} {j["date"].strftime("%d/%m")}', actuel)
        if n is None:
            return
        j["nb_personnes"] = max(1, int(n))
        self._afficher_jours()
        self.tv_jours.selection_set(str(j["index"]))
        self.calculer_courses()

    def appliquer_personnes_a_tous(self):
        """Repercute la valeur globale sur tous les jours du planning."""
        n = max(1, int(self.v_pers.get()))
        for j in self.jours:
            j["nb_personnes"] = n
        self.lb_astuce.config(text="")
        self._afficher_jours()
        self.calculer_courses()

    def ouvrir_widget(self):
        """Ouvre le widget de bureau sur la base courante."""
        from .widget import WidgetRepasDuJour
        if getattr(self, "_widget", None) is not None:
            try:
                self._widget.deiconify()
                self._widget.lift()
                return
            except tk.TclError:
                self._widget = None
        self._widget = WidgetRepasDuJour(self.winfo_toplevel(),
                                         chemin_db=self.chemin_db, con=self.con)

    def _jour_selectionne(self):
        sel = self.tv_jours.selection()
        if not sel:
            messagebox.showinfo("Selection", "Choisis d'abord un jour dans la liste.")
            return None
        return self.jours[int(sel[0])]

    def remplacer(self, quoi):
        j = self._jour_selectionne()
        if not j:
            return
        if quoi == "plat":
            choix = gen.recettes_autorisees(self.con, "plat")
        else:
            choix = (gen.recettes_autorisees(self.con, "gateau") +
                     gen.recettes_autorisees(self.con, "dessert"))
        if not choix:
            messagebox.showwarning("Recettes", "Aucune recette autorisee disponible.")
            return
        rec = self._dialogue_choix([c["nom"] for c in choix], "Choisir une recette")
        if rec is None:
            return
        j["plat" if quoi == "plat" else "dessert"] = choix[rec]
        self._afficher_jours()
        self.tv_jours.selection_set(str(j["index"]))
        self.calculer_courses()

    def retirer_dessert(self):
        j = self._jour_selectionne()
        if not j:
            return
        j["dessert"] = None
        self._afficher_jours()
        self.calculer_courses()

    def _dialogue_choix(self, valeurs, titre):
        """Petite boite modale de selection. Retourne l'index ou None."""
        top = tk.Toplevel(self)
        top.title(titre)
        top.transient(self.winfo_toplevel())
        top.grab_set()
        lb = tk.Listbox(top, width=52, height=18)
        for v in valeurs:
            lb.insert("end", v)
        lb.pack(padx=8, pady=8)
        resultat = {"i": None}

        def valider():
            if lb.curselection():
                resultat["i"] = lb.curselection()[0]
            top.destroy()

        lb.bind("<Double-1>", lambda e: valider())
        ttk.Button(top, text="Valider", command=valider).pack(pady=(0, 8))
        top.wait_window()
        return resultat["i"]

    # ------------------------------------------------------------ courses
    def calculer_courses(self):
        if not self.jours:
            return
        lignes, totaux = gen.liste_de_courses(
            self.con, self.jours, max(1, self.v_pers.get()), self.extras)
        self.lignes_courses, self.totaux_courses = lignes, totaux
        self.tv_courses.delete(*self.tv_courses.get_children())
        for i, l in enumerate(lignes):
            self.tv_courses.insert(
                "", "end", iid=str(i),
                values=(l["lot"], l["categorie"], l["code"], l["designation"],
                        l["quantite"], f'{l["prix_unitaire"]:.2f}',
                        f'{l["prix_total"]:.2f}', l["qte_max"],
                        "Plafond depasse" if l["depassement"] else ""),
                tags=("alerte",) if l["depassement"] else ())
        try:
            budget = float(self.v_budget.get().replace(",", "."))
        except ValueError:
            budget = 0
        total = totaux.get("TOTAL", 0)
        txt = f'Total : {total:.2f} EUR'
        if budget:
            ecart = total - budget
            txt += (f'  -  depassement de {ecart:.2f} EUR' if ecart > 0
                    else f'  -  marge de {abs(ecart):.2f} EUR')
        self.lb_total.config(text=txt)
        sugg = gen.suggestions_economies(self.con, lignes, budget)
        self.lb_conseil.config(
            text=(f'Piste : {sugg[0]["remplacer"]} -> {sugg[0]["par"]} '
                  f'({sugg[0]["gain"]:.2f} EUR)') if sugg else "")

    def ajouter_extra(self):
        produits = self.con.execute(
            "SELECT code, designation FROM pr_produit WHERE actif = 1 "
            "ORDER BY categorie, code").fetchall()
        libelles = [f'{p["code"]} - {p["designation"]}' for p in produits]
        i = self._dialogue_choix(libelles, "Produit hors repas")
        if i is None:
            return
        qte = self._demander_nombre("Quantite", 1)
        if not qte:
            return
        lot = self._demander_texte("Lot (Boissons, Hygiene, ...)", "Extra")
        self.extras.append((produits[i]["code"], int(qte), lot or "Extra"))
        self.calculer_courses()

    def retirer_extra(self):
        sel = self.tv_courses.selection()
        if not sel:
            return
        l = self.lignes_courses[int(sel[0])]
        if l["lot"] == "Repas":
            messagebox.showinfo(
                "Ligne repas",
                "Cette ligne vient d'une recette. Retire le plat du planning "
                "ou modifie la recette pour la faire disparaitre.")
            return
        self.extras = [e for e in self.extras if e[0] != l["code"] or e[2] != l["lot"]]
        self.calculer_courses()

    def _demander_nombre(self, titre, defaut=1):
        from tkinter.simpledialog import askinteger
        return askinteger(titre, titre, initialvalue=defaut, parent=self)

    def _demander_texte(self, titre, defaut=""):
        from tkinter.simpledialog import askstring
        return askstring(titre, titre, initialvalue=defaut, parent=self)

    # ------------------------------------------------------------ exports
    def _verifier_liste(self):
        if not getattr(self, "lignes_courses", None):
            messagebox.showinfo("Liste vide", "Genere d'abord un planning.")
            return False
        return True

    def _chemin_sortie(self, defaut, extensions):
        return filedialog.asksaveasfilename(
            initialdir=self.dossier_export, initialfile=defaut,
            defaultextension=extensions[0][1], filetypes=extensions)

    def export_csv_bon(self):
        if not self._verifier_liste():
            return
        c = self._chemin_sortie("bon_cantine.csv", [("CSV", ".csv")])
        if c:
            exp.csv_bon_de_cantine(self.lignes_courses, c)
            messagebox.showinfo("Export", f"Fichier ecrit :\n{c}")

    def export_csv_detaille(self):
        if not self._verifier_liste():
            return
        c = self._chemin_sortie("liste_detaillee.csv", [("CSV", ".csv")])
        if c:
            exp.csv_detaille(self.lignes_courses, self.totaux_courses, c)
            messagebox.showinfo("Export", f"Fichier ecrit :\n{c}")

    def export_pdf(self):
        if not self._verifier_liste():
            return
        c = self._chemin_sortie("planning_repas.pdf", [("PDF", ".pdf")])
        if not c:
            return
        try:
            budget = float(self.v_budget.get().replace(",", "."))
        except ValueError:
            budget = 0
        reel = exp.pdf(self.jours, self.v_pers.get(), self.lignes_courses,
                       self.totaux_courses, c, budget)
        if reel.endswith(".txt"):
            messagebox.showwarning(
                "PDF indisponible",
                "reportlab n'est pas installe : un fichier texte a ete ecrit a la "
                f"place.\n{reel}\n\nPour le PDF : pip install reportlab")
        else:
            messagebox.showinfo("Export", f"PDF ecrit :\n{reel}")

    # ------------------------------------------------------------ plannings
    def enregistrer(self):
        if not self.jours:
            messagebox.showinfo("Rien a enregistrer", "Genere d'abord un planning.")
            return
        libelle = self._demander_texte(
            "Nom du planning",
            f'Planning du {self.jours[0]["date"].strftime("%d/%m/%Y")}')
        if not libelle:
            return
        try:
            budget = float(self.v_budget.get().replace(",", "."))
        except ValueError:
            budget = 0
        self.planning_id = gen.enregistrer(
            self.con, libelle, self.jours[0]["date"], self.jours,
            self.v_pers.get(), budget, self.extras, self.planning_id)
        self._rafraichir_plannings()
        messagebox.showinfo("Enregistre", "Planning enregistre.")

    def _rafraichir_plannings(self):
        self.lb_plannings.delete(0, "end")
        self._ids_plannings = []
        for p in self.con.execute(
                "SELECT id, libelle, date_debut FROM pr_planning ORDER BY id DESC"):
            self.lb_plannings.insert("end", f'{p["libelle"]} ({p["date_debut"]})')
            self._ids_plannings.append(p["id"])

    def ouvrir_planning(self):
        sel = self.lb_plannings.curselection()
        if not sel:
            return
        pid = self._ids_plannings[sel[0]]
        p, jours, extras = gen.charger(self.con, pid)
        if not p:
            return
        self.planning_id, self.jours, self.extras = pid, jours, extras
        self.v_date.set(p["date_debut"])
        self.v_jours.set(p["nb_jours"])
        self.v_pers.set(p["nb_personnes"])
        self.v_budget.set(f'{p["budget_cible"]:.0f}')
        self._afficher_jours()
        self.calculer_courses()

    def supprimer_planning(self):
        sel = self.lb_plannings.curselection()
        if not sel or not messagebox.askyesno("Supprimer", "Supprimer ce planning ?"):
            return
        self.con.execute("DELETE FROM pr_planning WHERE id = ?",
                         (self._ids_plannings[sel[0]],))
        self.con.commit()
        self._rafraichir_plannings()

    # ------------------------------------------------------------ catalogue
    def _rafraichir_catalogue(self):
        f = f'%{self.v_filtre.get().strip()}%'
        self.tv_cat.delete(*self.tv_cat.get_children())
        for p in self.con.execute(
                "SELECT * FROM pr_produit WHERE code LIKE ? OR designation LIKE ? "
                "OR categorie LIKE ? ORDER BY categorie, code", (f, f, f)):
            self.tv_cat.insert("", "end", iid=p["code"], values=(
                p["code"], p["designation"], f'{p["prix"]:.2f}', p["qte_max"],
                p["categorie"], "oui" if p["actif"] else "non"))

    def modifier_produit(self):
        sel = self.tv_cat.selection()
        if not sel:
            return
        code = sel[0]
        p = self.con.execute("SELECT * FROM pr_produit WHERE code = ?", (code,)).fetchone()
        des = self._demander_texte("Designation", p["designation"])
        if des is None:
            return
        prix = self._demander_texte("Prix", f'{p["prix"]:.2f}')
        qmax = self._demander_texte("Quantite max", str(p["qte_max"]))
        try:
            prix_v = float((prix or "0").replace(",", "."))
            qmax_v = int(qmax or p["qte_max"])
        except ValueError:
            messagebox.showerror("Valeur", "Prix ou quantite invalide.")
            return
        self.con.execute("UPDATE pr_produit SET designation=?, prix=?, qte_max=? "
                         "WHERE code=?", (des, prix_v, qmax_v, code))
        self.con.commit()
        self._rafraichir_catalogue()
        self.calculer_courses()

    def ajouter_produit(self):
        code = self._demander_texte("Code produit")
        if not code:
            return
        if self.con.execute("SELECT 1 FROM pr_produit WHERE code = ?",
                            (code.upper(),)).fetchone():
            messagebox.showerror("Code", "Ce code existe deja.")
            return
        des = self._demander_texte("Designation") or code
        prix = self._demander_texte("Prix", "0")
        qmax = self._demander_texte("Quantite max", "10")
        cat = self._demander_texte("Categorie", "Alimentaire")
        try:
            self.con.execute(
                "INSERT INTO pr_produit (code, designation, prix, qte_max, actif, "
                "categorie) VALUES (?,?,?,?,1,?)",
                (code.upper(), des, float((prix or "0").replace(",", ".")),
                 int(qmax or 10), cat))
            self.con.commit()
        except (ValueError, Exception) as e:
            messagebox.showerror("Ajout", str(e))
            return
        self._rafraichir_catalogue()

    def basculer_produit(self):
        sel = self.tv_cat.selection()
        if not sel:
            return
        self.con.execute("UPDATE pr_produit SET actif = 1 - actif WHERE code = ?", (sel[0],))
        self.con.commit()
        self._rafraichir_catalogue()

    def recharger_catalogue(self):
        if not messagebox.askyesno(
                "Recharger",
                "Les prix et libelles du catalogue livre vont ecraser tes "
                "modifications. Continuer ?"):
            return
        n = dbmod.charger_catalogue(self.con, remplacer=True)
        self._rafraichir_catalogue()
        messagebox.showinfo("Catalogue", f"{n} produits recharges.")

    # ------------------------------------------------------------ recettes
    def _rafraichir_recettes(self):
        self.tv_rec.delete(*self.tv_rec.get_children())
        for r in self.con.execute("SELECT * FROM pr_recette ORDER BY type, nom"):
            self.tv_rec.insert("", "end", iid=str(r["id"]), values=(
                r["nom"], r["type"], "oui" if r["actif"] else "non"))

    def _recette_selectionnee(self):
        sel = self.tv_rec.selection()
        return int(sel[0]) if sel else None

    def _afficher_recette(self):
        rid = self._recette_selectionnee()
        if not rid:
            return
        try:
            nb = max(1, int(self.v_rec_pers.get()))
        except Exception:
            nb = 2
        r = self.con.execute("SELECT * FROM pr_recette WHERE id = ?", (rid,)).fetchone()

        ings = self.con.execute(
            "SELECT i.code, i.qte, i.fixe, p.designation "
            "FROM pr_recette_ingredient i LEFT JOIN pr_produit p ON p.code = i.code "
            "WHERE i.recette_id = ?", (rid,)).fetchall()

        try:
            from . import quantites_cuisine as qc
        except Exception:
            import quantites_cuisine as qc

        # Tableau des ingrédients (quantités de cuisine réelles)
        self.tv_ing.delete(*self.tv_ing.get_children())
        lignes_txt = []
        for i in ings:
            nom = (i["designation"] or f"({i['code']})")
            nom_court = self._nom_court_ingredient(nom)
            q_txt, _connu = qc.ingredient_lisible(i["code"], i["qte"], i["fixe"], nb)
            # Éviter les répétitions :
            #  - "1 boîte de sauce tomate" contient déjà "de ..." -> tel quel
            #  - "4 œufs", "½ oignon", "4 pommes" : l'unité est déjà l'aliment
            #    (le 1er mot de l'unité correspond au nom) -> tel quel
            def _sansacc(s):
                return (s.lower().replace("œ","oe").replace("é","e")
                        .replace("è","e").replace("ê","e").replace("à","a"))
            ql = _sansacc(q_txt)
            ncl = _sansacc(nom_court)
            unite_est_aliment = any(
                mot in ql for mot in [ncl.rstrip("s"), ncl.split()[0].rstrip("s")]
                if len(mot) > 2)
            if " de " in q_txt or " d'" in q_txt or unite_est_aliment:
                affiche = q_txt
            else:
                affiche = f"{q_txt} de {nom_court}"
            self.tv_ing.insert("", "end", values=(nom_court, q_txt))
            lignes_txt.append(f"• {affiche}")

        entete = (f"🛒 INGRÉDIENTS  (pour {nb} personne(s))\n"
                  + "\n".join(lignes_txt)
                  + "\n\n" + "─" * 40 + "\n\n")
        self.txt_rec.delete("1.0", "end")
        self.txt_rec.insert("1.0", entete + (r["instructions"] or ""))

    def _nom_court_ingredient(self, nom):
        """Retire la partie conditionnement du nom (ex: 'Riz thai 500g' -> 'Riz thai')."""
        import re
        # Coupe à partir du 1er nombre suivi d'une unité de conditionnement
        nom = re.split(r"\s+\d+[.,]?\d*\s*(?:g|kg|l|cl|ml|Kg|G|L|CL|ML)\b", nom)[0]
        nom = re.split(r"\s+environ\b", nom)[0]
        nom = re.split(r"\s+\d+\s*\*", nom)[0]
        return nom.strip()

    def enregistrer_instructions(self):
        rid = self._recette_selectionnee()
        if not rid:
            return
        contenu = self.txt_rec.get("1.0", "end")
        # Retirer la section INGRÉDIENTS ajoutée dynamiquement (avant le séparateur)
        sep = "─" * 40
        if contenu.lstrip().startswith("🛒 INGRÉDIENTS") and sep in contenu:
            contenu = contenu.split(sep, 1)[1].lstrip("\n")
        self.con.execute("UPDATE pr_recette SET instructions = ? WHERE id = ?",
                         (contenu.strip(), rid))
        self.con.commit()
        messagebox.showinfo("Recette", "Instructions enregistrees.")

    def voir_video(self):
        """Ouvre une recherche YouTube de la recette dans le navigateur."""
        rid = self._recette_selectionnee()
        if not rid:
            messagebox.showinfo("Video", "Selectionnez d'abord une recette.")
            return
        r = self.con.execute("SELECT nom FROM pr_recette WHERE id = ?", (rid,)).fetchone()
        if not r:
            return
        import urllib.parse, webbrowser
        requete = urllib.parse.quote(f"{r['nom']} recette facile")
        url = f"https://www.youtube.com/results?search_query={requete}"
        try:
            ouvert = webbrowser.open(url)
            if not ouvert:
                raise RuntimeError("navigateur indisponible")
        except Exception:
            messagebox.showinfo("Video",
                "Impossible d'ouvrir le navigateur.\n\n"
                "Cet ordinateur n'a peut-etre pas d'acces Internet.\n"
                "Sur un poste connecte, recherchez sur YouTube :\n\n"
                f"« {r['nom']} recette facile »")

    def basculer_recette(self):
        rid = self._recette_selectionnee()
        if not rid:
            return
        self.con.execute("UPDATE pr_recette SET actif = 1 - actif WHERE id = ?", (rid,))
        self.con.commit()
        self._rafraichir_recettes()

    def ajouter_ingredient(self):
        rid = self._recette_selectionnee()
        if not rid:
            return
        produits = self.con.execute(
            "SELECT code, designation FROM pr_produit WHERE actif = 1 "
            "ORDER BY categorie, code").fetchall()
        i = self._dialogue_choix([f'{p["code"]} - {p["designation"]}' for p in produits],
                                 "Ingredient")
        if i is None:
            return
        qte = self._demander_texte("Quantite (par personne)", "1")
        fixe = messagebox.askyesno(
            "Type de quantite",
            "Quantite fixe par repas ?\n\nOui = ne change pas avec le nombre de "
            "personnes (epices, huile)\nNon = multipliee par le nombre de personnes")
        try:
            self.con.execute(
                "INSERT INTO pr_recette_ingredient (recette_id, code, qte, fixe) "
                "VALUES (?,?,?,?)",
                (rid, produits[i]["code"], float((qte or "1").replace(",", ".")),
                 1 if fixe else 0))
            self.con.commit()
        except ValueError:
            messagebox.showerror("Quantite", "Valeur invalide.")
            return
        self._afficher_recette()

    def retirer_ingredient(self):
        sel = self.tv_ing.selection()
        if not sel:
            return
        self.con.execute("DELETE FROM pr_recette_ingredient WHERE id = ?", (int(sel[0]),))
        self.con.commit()
        self._afficher_recette()

    # ------------------------------------------------------------ regles
    def _rafraichir_regles(self):
        self.tv_reg.delete(*self.tv_reg.get_children())
        for r in self.con.execute("SELECT * FROM pr_regle ORDER BY type, valeur"):
            self.tv_reg.insert("", "end", iid=str(r["id"]), values=(
                r["type"], r["valeur"], r["motif"], "oui" if r["actif"] else "non"))

    def ajouter_regle(self):
        val = self.v_rval.get().strip()
        if not val:
            return
        self.con.execute("INSERT INTO pr_regle (type, valeur, motif) VALUES (?,?,?)",
                         (self.v_rtype.get(), val, self.v_rmotif.get().strip()))
        self.con.commit()
        self.v_rval.set("")
        self.v_rmotif.set("")
        self._rafraichir_regles()

    def basculer_regle(self):
        sel = self.tv_reg.selection()
        if not sel:
            return
        self.con.execute("UPDATE pr_regle SET actif = 1 - actif WHERE id = ?", (int(sel[0]),))
        self.con.commit()
        self._rafraichir_regles()

    def supprimer_regle(self):
        sel = self.tv_reg.selection()
        if not sel:
            return
        self.con.execute("DELETE FROM pr_regle WHERE id = ?", (int(sel[0]),))
        self.con.commit()
        self._rafraichir_regles()
