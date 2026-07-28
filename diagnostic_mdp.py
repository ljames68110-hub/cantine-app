# -*- coding: utf-8 -*-
"""
Diagnostic + reinitialisation du mot de passe Yoann.
Usage : python diagnostic_mdp.py
"""
import os
import sqlite3

candidats = []

appdata = os.environ.get("APPDATA")
if appdata:
    candidats.append(os.path.join(appdata, "CantineApp", "cantine.db"))

localappdata = os.environ.get("LOCALAPPDATA")
if localappdata:
    candidats.append(os.path.join(localappdata, "CantineApp", "cantine.db"))

# Dossier courant (cas ou l'appli tourne en mode developpement, python main.py)
candidats.append(os.path.join(os.getcwd(), "cantine.db"))

print("=" * 60)
print("Recherche du fichier cantine.db...")
print("=" * 60)

trouves = []
for chemin in candidats:
    existe = os.path.isfile(chemin)
    print(f"{'[OK]  ' if existe else '[--]  '}{chemin}")
    if existe:
        trouves.append(chemin)

print()

if not trouves:
    print("Aucun fichier cantine.db trouve dans les emplacements habituels.")
    print("=> L'application ne s'est peut-etre jamais lancee avec succes sur")
    print("   ce compte Windows, ou la base est ailleurs. Dis-le moi.")
    input("\nAppuyez sur Entree pour fermer...")
    raise SystemExit

for chemin in trouves:
    print("-" * 60)
    print("Fichier :", chemin)
    try:
        conn = sqlite3.connect(chemin)
        c = conn.cursor()
        c.execute("SELECT login, mot_de_passe, role FROM utilisateurs")
        lignes = c.fetchall()
        print("Comptes trouves avant modification :")
        for l in lignes:
            print("  ", l)

        c.execute("UPDATE utilisateurs SET mot_de_passe='1234' WHERE login='yoann'")
        if c.rowcount == 0:
            print("  (!) Aucun compte 'yoann' trouve dans ce fichier - rien modifie.")
        else:
            conn.commit()
            print("  -> Mot de passe de 'yoann' remis a '1234'.")

        c.execute("SELECT login, mot_de_passe, role FROM utilisateurs")
        print("Comptes apres modification :")
        for l in c.fetchall():
            print("  ", l)
        conn.close()
    except Exception as e:
        print("  Erreur :", e)

print("-" * 60)
print("\nTermine. Relance l'application et essaie de te connecter avec : 1234")
input("\nAppuyez sur Entree pour fermer...")
