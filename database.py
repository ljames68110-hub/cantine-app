import sys
import sqlite3, os, uuid, json, shutil

def _app_data_dir():
    """Dossier données utilisateur LOCAL — fonctionne en .py ET en .exe PyInstaller."""
    if getattr(sys, "frozen", False):
        # Mode .exe : données dans %APPDATA%/CantineApp
        base = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "CantineApp")
    else:
        # Mode script : données à côté du .py
        base = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(base, exist_ok=True)
    return base

# ─── Partage de la base entre plusieurs systèmes (ex. PC en double boot) ──────
# La config (où se trouve la base) reste TOUJOURS locale : chaque système doit
# pouvoir la lire avant même de savoir où est la base partagée.
_CONFIG_PATH = os.path.join(_app_data_dir(), "config.json")
# Nom du sous-dossier créé sur le disque partagé (sert aussi à l'auto-détection).
_NOM_DOSSIER_PARTAGE = "CantineData"

def _lire_config():
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _ecrire_config(cfg):
    try:
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def _dossier_accessible(d):
    try:
        return bool(d) and os.path.isdir(d) and os.access(d, os.W_OK)
    except Exception:
        return False

def _resoudre_db_path():
    """Décide où vit la base :
    1) un dossier partagé explicitement choisi (config.json) s'il est accessible ;
    2) sinon, auto-détection d'une base déjà posée sur un disque (D:, E:, ...) ;
    3) sinon, la base locale (%APPDATA%/CantineApp) — comportement d'origine."""
    cfg = _lire_config()
    # 0) partage explicitement désactivé → on reste en local, sans auto-détection
    if cfg.get("partage_desactive"):
        return os.path.join(_app_data_dir(), "cantine.db")
    # 1) dossier partagé configuré
    d = cfg.get("dossier_partage")
    if d and _dossier_accessible(d):
        return os.path.join(d, "cantine.db")
    # 2) auto-détection : base déjà présente sur un autre disque
    if os.name == "nt":
        for lettre in "DEFGHIJKLMNOPQRSTUVWXYZ":
            cand = "%s:\\%s\\cantine.db" % (lettre, _NOM_DOSSIER_PARTAGE)
            try:
                if os.path.exists(cand):
                    return cand
            except Exception:
                pass
    # 3) base locale
    return os.path.join(_app_data_dir(), "cantine.db")

DB_PATH = _resoudre_db_path()

def dossier_partage_actuel():
    """Renvoie le dossier où vit la base SI elle est partagée (hors APPDATA local),
    sinon '' (base locale)."""
    try:
        d = os.path.dirname(DB_PATH)
        local = _app_data_dir()
        if os.path.normcase(os.path.normpath(d)) == os.path.normcase(os.path.normpath(local)):
            return ""
        return d
    except Exception:
        return ""

def definir_dossier_partage(dossier_racine):
    """Active le partage : la base vivra dans <dossier_racine>\\CantineData\\cantine.db.
    - Si la base cible n'existe pas encore mais qu'une base actuelle existe,
      on COPIE l'actuelle (amorçage) — aucune donnée perdue.
    - N'écrase jamais une base partagée déjà en place.
    Écrit la config locale. L'appli doit REDÉMARRER pour prendre le changement.
    Renvoie le nouveau chemin de base. Lève une exception en cas d'échec."""
    if not _dossier_accessible(dossier_racine):
        raise RuntimeError("Dossier inaccessible ou non inscriptible : %s" % dossier_racine)
    cible_dir = os.path.join(dossier_racine, _NOM_DOSSIER_PARTAGE)
    os.makedirs(cible_dir, exist_ok=True)
    cible_db = os.path.join(cible_dir, "cantine.db")
    # Amorçage : recopie la base actuelle si la cible n'existe pas encore.
    if not os.path.exists(cible_db) and os.path.exists(DB_PATH):
        shutil.copy2(DB_PATH, cible_db)
    cfg = _lire_config()
    cfg["dossier_partage"] = cible_dir
    cfg.pop("partage_desactive", None)
    if not _ecrire_config(cfg):
        raise RuntimeError("Impossible d'enregistrer la configuration.")
    return cible_db

def desactiver_dossier_partage():
    """Repasse la base en LOCAL (chaque système sa propre base). Redémarrage requis."""
    cfg = _lire_config()
    cfg.pop("dossier_partage", None)
    cfg["partage_desactive"] = True
    _ecrire_config(cfg)

PRODUITS_INITIAUX = [
    ("B1","Cristaline 1,5L","Boissons",0.20,18,"Oui"),("B2","Cristaline gazeuse 1,5L","Boissons",0.32,18,"Oui"),
    ("B3","Pepsi 33cl","Boissons",0.65,24,"Oui"),("B4","Limonade Blanche 1,5L","Boissons",0.43,12,"Oui"),
    ("B5","Sirop citron 1L","Boissons",2.56,6,"Oui"),("B6","Bavaria Sans Alcool 33cl","Boissons",0.41,24,"Oui"),
    ("B7","Carola rouge 1,25L","Boissons",0.71,12,"Oui"),("B8","Salvetat 1,15L","Boissons",0.65,12,"Oui"),
    ("B9","Saint Yorre 1,15L","Boissons",0.73,12,"Oui"),("B10","Orangina 33cl","Boissons",0.69,24,"Oui"),
    ("B11","Oasis Tropical 33cl","Boissons",0.67,24,"Oui"),("B12","Ica tea 33cl","Boissons",0.70,24,"Oui"),
    ("B13","Coca-cola light 33cl","Boissons",0.69,24,"Oui"),("B14","Coca-cola 1,25L","Boissons",1.96,12,"Oui"),
    ("B15","Coca-cola 33cl","Boissons",0.72,24,"Oui"),("B16","Sprite 33cl","Boissons",0.54,24,"Oui"),
    ("B18","Cocktail multivitaminé 1L","Boissons",1.11,12,"Oui"),("B19","Jus de raisin 1L","Boissons",1.01,12,"Oui"),
    ("B20","Jus d'orange 1L","Boissons",1.74,12,"Oui"),("B21","Jus de pomme 1L","Boissons",0.92,12,"Oui"),
    ("B22","Sirop de fraise 1L","Boissons",2.81,6,"Oui"),("B23","Sirop de grenadine","Boissons",2.59,6,"Oui"),
    ("B24","Sirop de menthe","Boissons",2.42,6,"Oui"),("B25","Vittel 1,5L","Boissons",0.90,12,"Oui"),
    ("F1","Beurre doux 250g","Fruits & Légumes",2.24,10,"Oui"),("F2","Beurre 1/2 sel 250g","Fruits & Légumes",2.24,10,"Oui"),
    ("F3","Liegeois maestro chocolat 4*100g","Fruits & Légumes",1.02,10,"Oui"),("F4","Crème onctueuse vanille 4*125g","Fruits & Légumes",1.04,10,"Oui"),
    ("F5","Camenbert 240g","Fruits & Légumes",1.61,10,"Oui"),("F6","Roquefort 100g","Fruits & Légumes",1.92,10,"Oui"),
    ("F7","Emmental bloc 250g","Fruits & Légumes",2.11,10,"Oui"),("F8","Emmental rapé 100g","Fruits & Légumes",0.86,10,"Oui"),
    ("F9","Fromage blanc 0% 4*100g","Fruits & Légumes",0.90,10,"Oui"),("F10","Yop fraise 825g","Fruits & Légumes",2.12,10,"Oui"),
    ("F11","Yaourt nature 4*115g","Fruits & Légumes",0.60,10,"Oui"),("F12","Lait UHT 1/2 écrémé 1L","Fruits & Légumes",0.86,12,"Oui"),
    ("F13","Oeufs frais par 6","Fruits & Légumes",1.09,10,"Oui"),("F14","Secret de crème uht 25% m,g, 3*20cl","Fruits & Légumes",3.78,10,"Oui"),
    ("F15","Crème fraiche 30% m,g, pot 20cl","Fruits & Légumes",1.25,10,"Oui"),("F16","Buche chèvre 180g","Fruits & Légumes",1.92,10,"Oui"),
    ("F17","Planta fin","Fruits & Légumes",2.78,10,"Oui"),("F18","Babybel","Fruits & Légumes",2.19,10,"Oui"),
    ("F19","Bleu de bresse","Fruits & Légumes",3.41,10,"Oui"),("F20","Mozzarella","Fruits & Légumes",1.32,10,"Oui"),
    ("F21","Lait entier 1L","Fruits & Légumes",1.36,12,"Oui"),("F22","Munster","Fruits & Légumes",3.25,10,"Oui"),
    ("F23","Carré de l'est","Fruits & Légumes",2.49,10,"Oui"),("F24","Coulommiers","Fruits & Légumes",2.89,10,"Oui"),
    ("F25","Pointe de brie","Fruits & Légumes",1.56,10,"Oui"),("F26","Rondelé ail et fines herbes","Fruits & Légumes",1.73,10,"Oui"),
    ("F27","Yaourt fruits 4*125g","Fruits & Légumes",0.98,10,"Oui"),("F28","Avocat","Fruits & Légumes",1.35,10,"Oui"),
    ("F29","Concombre pièce","Fruits & Légumes",1.27,10,"Oui"),("F30","Courgettes 1Kg","Fruits & Légumes",3.38,10,"Oui"),
    ("F31","Endives 1Kg","Fruits & Légumes",3.71,10,"Oui"),("F32","Piments verts","Fruits & Légumes",0.49,10,"Oui"),
    ("F33","Banane 1Kg","Fruits & Légumes",1.86,10,"Oui"),("F34","Kiwi pièce","Fruits & Légumes",0.54,10,"Oui"),
    ("F35","Orange 1Kg","Fruits & Légumes",2.53,10,"Oui"),("F36","Aubergines","Fruits & Légumes",5.40,10,"Oui"),
    ("F37","Poivrons verts","Fruits & Légumes",3.71,10,"Oui"),("F38","Ananas pièce","Fruits & Légumes",2.64,10,"Oui"),
    ("F39","Carotte 1Kg","Fruits & Légumes",1.69,10,"Oui"),("F40","Echalotes sachet 250g","Fruits & Légumes",0.63,10,"Oui"),
    ("F41","Oignon 1Kg","Fruits & Légumes",0.76,10,"Oui"),("F42","Pomme de terre 2,5Kg","Fruits & Légumes",1.69,10,"Oui"),
    ("F43","Tomates 1Kg","Fruits & Légumes",2.19,10,"Oui"),("F44","Citron 1Kg","Fruits & Légumes",3.71,10,"Oui"),
    ("F45","Pomme 1Kg","Fruits & Légumes",2.53,10,"Oui"),("F46","Poires 1Kg","Fruits & Légumes",3.55,10,"Oui"),
    ("F47","Betterave cuite 250g","Fruits & Légumes",0.95,10,"Oui"),("F48","Ail filet 250g","Fruits & Légumes",2.11,10,"Oui"),
    ("F49","Champignons barquette 500g","Fruits & Légumes",3.12,10,"Oui"),("F50","Batavia","Fruits & Légumes",1.27,10,"Oui"),
    ("F51","Mangue","Fruits & Légumes",5.06,10,"Oui"),("F52","Blanc de poulet 4 tranches","Fruits & Légumes",1.59,10,"Oui"),
    ("F53","Jambon cuit superieur 4 tranches","Fruits & Légumes",1.85,10,"Oui"),("F54","Chorizo pur porc fort 250g","Fruits & Légumes",1.70,10,"Oui"),
    ("F55","Jambon cru 4 tranches","Fruits & Légumes",1.61,10,"Oui"),("F56","Lardons fumés 250g","Fruits & Légumes",1.45,10,"Oui"),
    ("F57","Saucisses de francfort *5","Fruits & Légumes",1.30,10,"Oui"),("F58","Barquette rosette *10","Fruits & Légumes",1.11,10,"Oui"),
    ("F60","Liégeois maestro café 4*100g","Fruits & Légumes",1.02,10,"Oui"),("F61","Petit nova aux fruits 6*60g","Fruits & Légumes",0.89,10,"Oui"),
    ("F62","Petit nature (par 6)","Fruits & Légumes",1.03,10,"Oui"),("F63","Riz au lait nappé caramel 100g","Fruits & Légumes",0.31,10,"Oui"),
    ("F64","Parmesan 100g","Fruits & Légumes",2.09,10,"Oui"),("F65","Mascarpone 250g","Fruits & Légumes",2.19,10,"Oui"),
    ("F66","Kit pot au feu","Fruits & Légumes",3.11,10,"Oui"),("F67","Cheddar en tranches *8","Fruits & Légumes",1.84,10,"Oui"),
    ("F70","Surimi batonnet crabe 500g","Fruits & Légumes",5.40,10,"Oui"),("F71","Raclette en tranches env 400g","Fruits & Légumes",4.64,10,"Oui"),
    ("F72","Poulet fumé halal 1,1Kg","Fruits & Légumes",6.84,10,"Oui"),
    ("A1","Nescafé boite 200g","Alimentaire",11.26,12,"Oui"),("A2","Chicorée 200g","Alimentaire",2.83,12,"Oui"),
    ("A3","Ricoré 100g","Alimentaire",2.16,12,"Oui"),("A4","Café moulu 250g grand-mère","Alimentaire",3.22,12,"Oui"),
    ("A5","Senseo classique *40","Alimentaire",5.52,10,"Oui"),("A6","Senseo corsé *40","Alimentaire",6.03,10,"Oui"),
    ("A7","Chocolat en poudre 450g Poulain","Alimentaire",3.31,10,"Oui"),("A8","Thé ceylan 25 sachets","Alimentaire",0.55,10,"Oui"),
    ("A9","Thé vert menthe 25 sachets","Alimentaire",1.29,10,"Oui"),("A10","Infusion verveine menthe","Alimentaire",1.17,10,"Oui"),
    ("A11","Infusion fruits rouges","Alimentaire",1.11,10,"Oui"),("A12","Lait concentré sucré 300g","Alimentaire",2.60,10,"Oui"),
    ("A13","Lait écrémé en poudre 300g","Alimentaire",3.20,10,"Oui"),("A14","Confiture d'abricot 450g","Alimentaire",1.73,10,"Oui"),
    ("A15","Confiture de fraise 35% 450g","Alimentaire",1.73,10,"Oui"),("A16","Miel fleurs squeezer 500g","Alimentaire",2.68,10,"Oui"),
    ("A17","Nutella 400g","Alimentaire",4.02,10,"Oui"),("A18","Sucre en morceaux n°4 1Kg","Alimentaire",1.29,5,"Oui"),
    ("A19","Sucre en poudre 1Kg","Alimentaire",1.85,5,"Oui"),("A20","Edulcorant canderel *300","Alimentaire",7.36,10,"Oui"),
    ("A21","Miel pops 330g","Alimentaire",3.47,10,"Oui"),("A22","Extra fruits rouges 450g Kellogs","Alimentaire",4.64,10,"Oui"),
    ("A23","Corn flakes 750g","Alimentaire",3.47,10,"Oui"),("A24","Chocapic 375g","Alimentaire",3.45,10,"Oui"),
    ("A25","Quaker 550g","Alimentaire",4.38,10,"Oui"),("A26","Biscotte nature 300g","Alimentaire",1.15,10,"Oui"),
    ("A27","Pain grillé farine froment 300g","Alimentaire",2.89,10,"Oui"),("A28","Wasa bleu 230g","Alimentaire",1.77,10,"Oui"),
    ("A29","REM 3 paquets de 255g","Alimentaire",3.41,6,"Oui"),("A30","Brioche tranchée 18 tranches 500g","Alimentaire",3.28,10,"Oui"),
    ("A31","Pain de mie nature 500g","Alimentaire",1.52,10,"Oui"),("A32","Chocolat lait 30% 100g","Alimentaire",1.23,10,"Oui"),
    ("A33","Chocolat lait céréales 100g","Alimentaire",1.21,10,"Oui"),("A34","Chocolat noir 100g","Alimentaire",1.06,10,"Oui"),
    ("A35","Chocolat noisette 100g","Alimentaire",1.40,10,"Oui"),("A36","BN chocolat paquet 16 biscuits","Alimentaire",1.10,10,"Oui"),
    ("A37","Goûter fourré rond chocolat 300g","Alimentaire",0.87,10,"Oui"),("A38","Petit beurre LU 200g","Alimentaire",1.77,10,"Oui"),
    ("A39","Prince Granola 200g","Alimentaire",3.44,10,"Oui"),("A40","Cake aux fruits 250g","Alimentaire",1.44,10,"Oui"),
    ("A41","Cookie nougatine aux pépites de chocolat","Alimentaire",1.15,10,"Oui"),("A42","Galette bretonne 120g","Alimentaire",0.83,10,"Oui"),
    ("A43","Gateau marbré chocolat","Alimentaire",1.47,10,"Oui"),("A44","Madelaines longues 250g","Alimentaire",1.07,16,"Oui"),
    ("A45","Biscuit tablette chocolat sportchoc 125g","Alimentaire",0.94,10,"Oui"),("A46","Barre patisserie 800g","Alimentaire",1.99,10,"Oui"),
    ("A47","Pain d'épices sucré 500g","Alimentaire",1.70,10,"Oui"),("A48","Pain au chocolat par 8","Alimentaire",1.84,10,"Oui"),
    ("A49","Pain au lait par 10","Alimentaire",1.70,10,"Oui"),("A50","Palet breton 125g","Alimentaire",1.23,10,"Oui"),
    ("A51","Pain hamburger *4","Alimentaire",1.14,10,"Oui"),("A52","Bombon acidulé","Alimentaire",0.84,10,"Oui"),
    ("A53","Bombon fraise fondant halal 200g","Alimentaire",1.72,10,"Oui"),("A54","Menthe dur 150g","Alimentaire",0.84,10,"Oui"),
    ("A55","Tirlibibi Haribo 750g","Alimentaire",7.08,10,"Oui"),("A56","Tagada fraise 220g","Alimentaire",1.78,10,"Oui"),
    ("A57","Peanut 5*36g","Alimentaire",2.87,10,"Oui"),("A58","Nuts noisette 42g","Alimentaire",0.72,10,"Oui"),
    ("A59","Snickers sachet de 5*50g","Alimentaire",3.25,10,"Oui"),("A60","Mars sachet de 5*45g","Alimentaire",3.25,10,"Oui"),
    ("A61","Twix sachet de 5*50g","Alimentaire",3.32,10,"Oui"),("A62","Bounty sachet de 5*57g","Alimentaire",4.19,10,"Oui"),
    ("A63","Kit Kat sachet de 6*41,5g","Alimentaire",4.59,10,"Oui"),("A64","Lion sachet de 6*42g","Alimentaire",3.49,10,"Oui"),
    ("A65","Crème dessert chocolat 570g","Alimentaire",2.35,10,"Oui"),("A66","Crème dessert vanille 570g","Alimentaire",2.35,10,"Oui"),
    ("A67","Sucre vanillé 10*7,5g","Alimentaire",0.84,10,"Oui"),("A68","Cacao non sucré Van Houten","Alimentaire",3.62,5,"Oui"),
    ("A69","Poudre d'amande 125g","Alimentaire",2.26,10,"Oui"),("A70","Mr freeze 20*45ml","Alimentaire",3.46,10,"Oui"),
    ("A71","Cocktail de fruits 425g","Alimentaire",2.34,10,"Oui"),("A72","Ananas tranchée entière 565g","Alimentaire",1.65,10,"Oui"),
    ("A73","Oreillon d'abricot au sirop 820g","Alimentaire",2.58,10,"Oui"),("A74","Datte ravier 500g","Alimentaire",1.34,10,"Oui"),
    ("A75","Compote de pomme allégées en sucre 850g","Alimentaire",2.10,10,"Oui"),("A76","Cacahuète grillée salée 200g","Alimentaire",1.44,10,"Oui"),
    ("A77","Chips nature 90g","Alimentaire",0.82,10,"Oui"),("A78","Farine de blé type 55 1Kg","Alimentaire",0.70,10,"Oui"),
    ("A79","Farine à gateau avec poudre levante 1Kg","Alimentaire",1.84,10,"Oui"),("A80","Filet de maquereau 125g","Alimentaire",0.89,15,"Oui"),
    ("A81","Sardine à l'huile 125g","Alimentaire",0.71,15,"Oui"),("A82","Thon à l'huile 80g","Alimentaire",0.69,15,"Oui"),
    ("A83","Miette de thon à la tomate 80g","Alimentaire",0.65,15,"Oui"),("A84","Thon naturel 185g","Alimentaire",1.22,15,"Oui"),
    ("A85","Paté de campagne boite 3*78g","Alimentaire",2.51,10,"Oui"),("A86","Paté de foie boite 3*78g","Alimentaire",2.47,10,"Oui"),
    ("A87","Rillettes 125g","Alimentaire",1.19,10,"Oui"),("A88","Champignon de paris pied morceaux 390g","Alimentaire",1.11,10,"Oui"),
    ("A89","Haricots verts extra fins 800g","Alimentaire",2.16,10,"Oui"),("A90","Petits poids très fin 400g","Alimentaire",1.05,10,"Oui"),
    ("A91","Cassoulet 840g","Alimentaire",2.69,10,"Oui"),("A92","Ravioli boeuf 800g","Alimentaire",2.65,10,"Oui"),
    ("A93","Haricots blancs sauce tomate","Alimentaire",1.52,10,"Oui"),("A94","Lentilles cuisinés à l'auvergnate 820g","Alimentaire",2.19,10,"Oui"),
    ("A95","Petits pos très fins 800g","Alimentaire",2.04,10,"Oui"),("A96","Petits pois carottes très fins 400g","Alimentaire",1.47,10,"Oui"),
    ("A97","Mais 285g","Alimentaire",1.11,10,"Oui"),("A98","Macédoine de légumes 400g","Alimentaire",1.46,10,"Oui"),
    ("A99","Légumes pour couscous 800g","Alimentaire",2.58,10,"Oui"),("A100","Couscous royal poulet et boeuf 980g","Alimentaire",6.67,10,"Oui"),
    ("A101","Choucroute garnie 800g","Alimentaire",3.37,10,"Oui"),("A102","Huile de tournesol 1L","Alimentaire",1.75,1,"Oui"),
    ("A103","Huile d'olive 20% tournesol 80% 1L","Alimentaire",4.04,1,"Oui"),("A104","Vinaigre alcool coloré","Alimentaire",0.62,2,"Oui"),
    ("A105","Vinaigrette balsamique 50cl","Alimentaire",3.48,2,"Oui"),("A106","Vinaigrette nature alégée 50cl","Alimentaire",1.84,2,"Oui"),
    ("A107","Harissa tube 70g","Alimentaire",0.49,12,"Oui"),("A108","Tomato ketchup 560g","Alimentaire",1.18,10,"Oui"),
    ("A109","Mayonnaise 175g","Alimentaire",1.00,10,"Oui"),("A110","Moutarde 265g","Alimentaire",1.69,2,"Oui"),
    ("A111","Sel fin 750g","Alimentaire",0.49,2,"Oui"),("A112","Poivre noir 38g","Alimentaire",2.51,2,"Oui"),
    ("A113","Kub or 128g","Alimentaire",1.61,10,"Oui"),("A114","Cornichon extra fin 330g","Alimentaire",1.13,2,"Oui"),
    ("A115","Olive verte dénoyautées 180g","Alimentaire",0.80,10,"Oui"),("A116","Double concentré de tomates 150g","Alimentaire",1.10,10,"Oui"),
    ("A117","Sauce tomate fraiche 2*190g","Alimentaire",1.15,10,"Oui"),("A118","Tomate entière pelées 400g","Alimentaire",0.73,10,"Oui"),
    ("A119","Sauce bolognaise 100% boeuf 420g","Alimentaire",1.66,12,"Oui"),("A120","Nouilles instantanées boeuf halal 3*60g","Alimentaire",1.29,12,"Oui"),
    ("A121","Nouilles instantanées crevettes halal 3*60g","Alimentaire",1.42,12,"Oui"),("A122","Nouilles instantanées Curry halal 3*60g","Alimentaire",1.29,12,"Oui"),
    ("A123","Macaroni 500g","Alimentaire",1.21,12,"Oui"),("A124","Coquillettes 500","Alimentaire",1.21,12,"Oui"),
    ("A125","Penne 500g","Alimentaire",1.22,12,"Oui"),("A126","Spaghetti 500g","Alimentaire",1.26,12,"Oui"),
    ("A127","Tagliatelle 500g","Alimentaire",1.98,8,"Oui"),("A128","Torti 500g","Alimentaire",1.22,12,"Oui"),
    ("A129","Purée en flocon 500g","Alimentaire",2.00,10,"Oui"),("A130","Riz long étuvé 500g","Alimentaire",1.29,10,"Oui"),
    ("A131","Riz thai parfumé 500g","Alimentaire",2.45,12,"Oui"),("A132","Couscous moyen 500g","Alimentaire",1.35,10,"Oui"),
    ("A133","Potage poireau pomme de terre 54g","Alimentaire",1.94,10,"Oui"),("A134","Vinaigre Balsamique","Alimentaire",4.41,10,"Oui"),
    ("A135","Huile d'olive 1L","Alimentaire",6.32,10,"Oui"),("A136","Spéculos 250g","Alimentaire",0.99,2,"Oui"),
    ("H1","4 tranches de dinde fumées","Hallal",2.36,10,"Oui"),("H2","4 tranches de dinde nature","Hallal",2.36,10,"Oui"),
    ("H3","Cotes d'agneau *3 environ 240g","Hallal",5.76,10,"Oui"),("H4","Cordon bleu","Hallal",6.25,10,"Oui"),
    ("H5","Cuisse de poulet","Hallal",2.89,10,"Oui"),("H6","Boeuf bourgugnon","Hallal",6.25,10,"Oui"),
    ("H7","Collier d'agneau env 1Kg","Hallal",14.64,10,"Oui"),("H8","Emincé de kebab environ 500g","Hallal",6.25,10,"Oui"),
    ("H9","Entrecôte l'unité environ 200g","Hallal",5.24,10,"Oui"),("H10","Escalope de poulet environ 160g","Hallal",3.67,10,"Oui"),
    ("H11","Escalope de veau environ 150g","Hallal",5.24,10,"Oui"),("H12","Faux filet environ 150g","Hallal",4.19,10,"Oui"),
    ("H13","Lardons fumé volaille environ 200g","Hallal",3.67,10,"Oui"),("H14","Merguez douce *2 environ 100g","Hallal",3.13,10,"Oui"),
    ("H15","Merguez forte *2 environ 100g","Hallal",3.13,10,"Oui"),("H16","Poulet cru Halal","Hallal",9.18,10,"Oui"),
    ("H17","Saucisses blanches *2 environ 200g","Hallal",3.13,10,"Oui"),("H18","Saucisson boeuf olive","Hallal",3.13,10,"Oui"),
    ("H19","Saucisse boeuf","Hallal",3.13,10,"Oui"),("H20","Saucisse veau","Hallal",3.10,10,"Oui"),
    ("H21","Saucisson de volaille","Hallal",2.89,10,"Oui"),("H22","Saucisses knack *5","Hallal",7.34,10,"Oui"),
    ("H23","Steack haché environ 120g","Hallal",1.36,10,"Oui"),("H24","Saucisse sujuk environ 1Kg","Hallal",16.75,10,"Oui"),
    ("H25","Tranche gigot d'agneau environ 250g","Hallal",4.72,10,"Oui"),("H26","Viande couscous env 1Kk","Hallal",13.59,10,"Oui"),
    ("H27","Coriandre fraîche","Hallal",1.27,10,"Oui"),("H28","Feta environ 200g","Hallal",3.13,10,"Oui"),
    ("H29","Lait fermenté","Hallal",2.09,10,"Oui"),("H30","Menthe fraîche","Hallal",1.27,10,"Oui"),
    ("H31","Pâte brisée","Hallal",0.69,10,"Oui"),("H32","Pâte feuilletée","Hallal",0.83,10,"Oui"),
    ("H33","Feuille de brick","Hallal",0.99,10,"Oui"),("H34","Toastinette croque Mr 10 tranches","Hallal",1.84,10,"Oui"),
    ("H35","Amandes nature environ 300g","Hallal",4.19,10,"Oui"),("H36","Arôme maggi halal","Hallal",3.13,10,"Oui"),
    ("H37","Bombon hallal environ 70g","Hallal",1.56,10,"Oui"),("H38","Bouillon de boeuf *10","Hallal",4.19,10,"Oui"),
    ("H39","Boulgour environ 1Kg","Hallal",3.13,10,"Oui"),("H40","Cumin environ 70g","Hallal",2.09,10,"Oui"),
    ("H41","Curry environ 75g","Hallal",2.09,10,"Oui"),("H42","Dakatine 4/4","Hallal",5.24,10,"Oui"),
    ("H44","Graine de tournesol environ 250g","Hallal",2.63,10,"Oui"),("H45","Soupe harira","Hallal",2.05,10,"Oui"),
    ("H46","Herbe de provence tagine environ 50g","Hallal",1.84,10,"Oui"),("H47","Langue d'oiseau environ 500g","Hallal",1.56,10,"Oui"),
    ("H48","Lentilles corail","Hallal",2.09,10,"Oui"),("H49","Olives noires environ 400g","Hallal",5.24,10,"Oui"),
    ("H50","Pain tacos","Hallal",4.50,10,"Oui"),("H51","Pate de dattes","Hallal",2.89,10,"Oui"),
    ("H52","Persil environ 90g","Hallal",2.09,10,"Oui"),("H53","Piments doux moulu environ 85g","Hallal",2.33,10,"Oui"),
    ("H54","Pistaches environ 300g","Hallal",6.29,10,"Oui"),("H55","Pois chices sec environ 1Kg","Hallal",2.89,10,"Oui"),
    ("H56","Raisins secs environ 300g","Hallal",3.10,10,"Oui"),("H57","Sauce algérienne 500ml","Hallal",4.19,10,"Oui"),
    ("H58","Sauce andalouse 500ml","Hallal",4.19,10,"Oui"),("H59","Sauce samouraï","Hallal",4.19,10,"Oui"),
    ("H60","Semoule de blé fine 500g","Hallal",1.84,10,"Oui"),("H61","Thé noir ceylan","Hallal",4.19,10,"Oui"),
    ("H62","Thé vert","Hallal",3.67,10,"Oui"),("H63","Halva pistache environ 350g","Hallal",3.67,10,"Oui"),
    ("H64","Jus de citron","Hallal",1.56,10,"Oui"),("H65","Fleur d'oranger environ 245ml","Hallal",1.56,10,"Oui"),
    ("HY1","Crème à raser PALMOLIVE 100ml","Hygiène",1.21,10,"Oui"),("HY3","Savon à barbe en bol 125g MONSAVON","Hygiène",1.19,10,"Oui"),
    ("HY4","Savon CADUM 100g","Hygiène",1.93,1,"Oui"),("HY5","Blaireau en soie","Hygiène",1.49,1,"Oui"),
    ("HY6","Brosse à cheveux","Hygiène",0.52,10,"Oui"),("HY7","Dentifrice AQUAFRESH triple action 75ml","Hygiène",1.68,10,"Oui"),
    ("HY8","Shampoing anti pelliculaire DOP 500ml","Hygiène",3.04,10,"Oui"),("HY9","Fil dentaire ORAL B","Hygiène",5.94,10,"Oui"),
    ("HY10","Shampoing HEAD AND SHOULDERS 250ml","Hygiène",3.34,10,"Oui"),("HY12","Lime à ongle","Hygiène",0.79,1,"Oui"),
    ("HY13","Peigne sans étui","Hygiène",0.10,1,"Oui"),("HY14","Nettoyant lunettes vu *24 pochettes","Hygiène",2.36,10,"Oui"),
    ("HY15","Shampoing aux oeufs 750ml","Hygiène",0.86,10,"Oui"),("HY16","Tube PENTO 100ml","Hygiène",2.53,10,"Oui"),
    ("HY17","Lait corps NIVEA BODY peau sèche 250ml","Hygiène",4.62,10,"Oui"),("HY18","Brosse à dent dur SIGNAL","Hygiène",2.29,5,"Oui"),
    ("HY19","Nettoyant appareil dentaire polydent","Hygiène",2.43,10,"Oui"),("HY20","Recharge GILETTE MACH 3","Hygiène",16.39,1,"Oui"),
    ("HY21","Gel fixation extreme VIVEL DOP 150ml","Hygiène",5.40,10,"Oui"),("HY22","Dentifrice SENSODYNE tube 75ml","Hygiène",5.55,10,"Oui"),
    ("HY23","Gel à raser GILETTE 200ml","Hygiène",3.67,10,"Oui"),("HY24","Rasoir MACH 3 + 1 lame GILETTE","Hygiène",9.92,1,"Oui"),
    ("HY26","Pansements *20","Hygiène",0.89,10,"Oui"),("HY30","Coton tige","Hygiène",0.41,10,"Oui"),
    ("HY31","Crème hydratante NIVEA 100ml","Hygiène",2.24,10,"Oui"),("HY32","Dentifrice antitartre SIGNAL 75ml","Hygiène",1.08,10,"Oui"),
    ("HY33","Dentifrice protection caries SIGNAL 75ml","Hygiène",1.08,10,"Oui"),("HY34","Déo stick WILLIAMS 75ml","Hygiène",2.82,10,"Oui"),
    ("HY35","Déo bille unisex 50ml","Hygiène",0.76,10,"Oui"),("HY36","Gel coiffant 250ml","Hygiène",0.74,10,"Oui"),
    ("HY37","Gel douche FA 250ml","Hygiène",1.44,12,"Oui"),("HY38","Mouchoirs","Hygiène",0.08,15,"Oui"),
    ("HY39","Papier hygiènique 1 rouleau","Hygiène",0.20,18,"Oui"),("HY42","Savon de marseille 100g MONSAVON","Hygiène",0.39,10,"Oui"),
    ("HY43","Shampoing FL Amande","Hygiène",0.86,10,"Oui"),("HY44","Gel nettoyant anti imperfection NEUTROGENA","Hygiène",5.52,10,"Oui"),
    ("HY45","Bain de bouche COLGATE 500ml","Hygiène",3.66,10,"Oui"),("HY46","Gel doucha AXE 250ml","Hygiène",1.92,12,"Oui"),
    ("HY48","Mirroir 18*24","Hygiène",0.86,1,"Oui"),("HY49","Shampoing 2 en 1 FRUCTIS 250ml","Hygiène",2.34,10,"Oui"),
    ("HY50","Crème adhésive pour prothèse dentaire 40g","Hygiène",3.36,10,"Oui"),("HY51","Brosse à dent SIGNAL souple","Hygiène",0.60,5,"Oui"),
    ("HY52","Coupe ongle grand modèle","Hygiène",0.60,1,"Oui"),("HY54","Rasoir jetable","Hygiène",0.50,1,"Oui"),
    ("HY55","Stick lèvre 4g","Hygiène",0.95,10,"Oui"),("HY57","Rasoir + 21 lames","Hygiène",2.93,1,"Oui"),
    ("HY58","Brosse à dent médium 1er prix","Hygiène",0.14,5,"Oui"),("HY59","Baume après rasage sans alcool MENNEN 100ml","Hygiène",5.64,10,"Oui"),
    ("AC1","Papier à cigarettes OCB","Accidentelle",0.70,10,"Oui"),("AC2","Papier à cigarettes RIZLA","Accidentelle",0.70,10,"Oui"),
    ("AC3","Filtre à cigarettes OCB 6mm","Accidentelle",0.87,10,"Oui"),("AC4","Filtre à cigarettes RIZLA 8mm","Accidentelle",1.43,10,"Oui"),
    ("AC5","Tube à cigarettes OCB 100 Tubes","Accidentelle",0.92,10,"Oui"),("AC6","Machine à tube","Accidentelle",5.18,10,"Oui"),
    ("AC7","Rouleur petit modèle RIZLA","Accidentelle",2.48,10,"Oui"),("AC8","Briquet électronique","Accidentelle",0.16,10,"Oui"),
    ("AC9","Cendrier","Accidentelle",1.28,1,"Oui"),("AC10","Couteau bout rond","Accidentelle",0.80,2,"Oui"),
    ("AC11","Cuiller à café","Accidentelle",0.14,2,"Oui"),("AC12","Cuillère à soupe","Accidentelle",0.26,2,"Oui"),
    ("AC13","Fourchette","Accidentelle",0.26,2,"Oui"),("AC14","Verre transparent 16cl","Accidentelle",0.52,2,"Oui"),
    ("AC15","Assiette transparente creuse 23cm","Accidentelle",0.97,2,"Oui"),("AC16","Assiette transparente plate","Accidentelle",1.67,2,"Oui"),
    ("AC17","Bol transparent 51cl","Accidentelle",1.12,2,"Oui"),("AC18","Mug blanc","Accidentelle",1.87,2,"Oui"),
    ("AC19","Louche nylon","Accidentelle",1.51,1,"Oui"),("AC20","Spatule en bois","Accidentelle",0.65,2,"Oui"),
    ("AC21","Econome","Accidentelle",1.25,2,"Oui"),("AC22","Râpe fonction inox","Accidentelle",2.93,2,"Oui"),
    ("AC23","Ouvre boites","Accidentelle",0.62,2,"Oui"),("AC24","Passoire en plastique","Accidentelle",1.16,2,"Oui"),
    ("AC25","Saladier plastique","Accidentelle",0.99,2,"Oui"),("AC26","Presse agrume avec bec verseur","Accidentelle",1.38,2,"Oui"),
    ("AC27","Casserole inox 18cm","Accidentelle",6.94,2,"Oui"),("AC28","Poêle anti adhésive 22cm","Accidentelle",5.28,2,"Oui"),
    ("AC29","Couvercle inox 25cm","Accidentelle",3.99,2,"Oui"),("AC30","Boites hermétiques lot de 3","Accidentelle",2.18,2,"Oui"),
    ("AC31","Egouttoir vaisselle plastique","Accidentelle",3.28,2,"Oui"),("AC32","Cuvette plastique","Accidentelle",1.24,2,"Oui"),
    ("AC33","Seau 10L","Accidentelle",2.55,2,"Oui"),("AC34","Balai vinyl plastique","Accidentelle",2.00,2,"Oui"),
    ("AC35","Manche balai","Accidentelle",1.52,1,"Oui"),("AC36","Pelle + balayette plastique","Accidentelle",1.01,2,"Oui"),
    ("AC37","Poubelle plastique 25L","Accidentelle",7.24,2,"Oui"),("AC38","Kit WC brosse + socle","Accidentelle",1.32,2,"Oui"),
    ("AC40","Lessive génie gel tube 200ml","Accidentelle",2.66,10,"Oui"),("AC41","Lessive génie poudre 450g","Accidentelle",2.29,10,"Oui"),
    ("AC42","Lessive liquide LE CHAT 1,89L","Accidentelle",9.60,10,"Oui"),("AC43","Lessive OMO","Accidentelle",12.77,10,"Oui"),
    ("AC44","Assouplissant soupline 1,9L","Accidentelle",4.86,10,"Oui"),("AC45","Lingettes St MARC multi usages","Accidentelle",2.22,10,"Oui"),
    ("AC46","Nettoyant ménager Mr PROPRE 1,3L","Accidentelle",4.20,10,"Oui"),("AC47","Nettoyant ménager St MARC 1L","Accidentelle",3.00,10,"Oui"),
    ("AC48","Eau de javel 2,6% 250ml","Accidentelle",0.26,3,"Oui"),("AC50","Liquide vaisselle 1L","Accidentelle",0.72,10,"Oui"),
    ("AC51","Produit vaisselle Paic citron 750ml","Accidentelle",1.85,10,"Oui"),("AC52","Crème à récurer 750ml","Accidentelle",1.24,10,"Oui"),
    ("AC53","Gel WC 750ml","Accidentelle",1.01,10,"Oui"),("AC54","Bloc déo WC à accrocher","Accidentelle",1.82,10,"Oui"),
    ("AC55","Febreze textile 500ml","Accidentelle",4.92,10,"Oui"),("AC56","Diffuseur électrique AIR WICK","Accidentelle",5.07,1,"Oui"),
    ("AC57","Recharge pour diffuseur AIR WICK","Accidentelle",4.58,10,"Oui"),("AC60","Balai kit avec 8 recharge SWIFer","Accidentelle",21.05,10,"Oui"),
    ("AC61","Serpière 50*60cm","Accidentelle",0.70,10,"Oui"),("AC62","Brosse à laver le linge","Accidentelle",1.13,10,"Oui"),
    ("AC63","Pinces à linges *12","Accidentelle",0.72,10,"Oui"),("AC65","Chiffons microfibres","Accidentelle",1.04,10,"Oui"),
    ("AC66","Torchon de cuisine 50*70cm","Accidentelle",0.69,10,"Oui"),("AC67","Papier essui-tout *2","Accidentelle",0.84,10,"Oui"),
    ("AC68","Sac poubelle 30L","Accidentelle",0.54,10,"Oui"),("AC69","Piles LR03 *4","Accidentelle",0.57,10,"Oui"),
    ("AC70","Piles LR06 *4","Accidentelle",0.57,10,"Oui"),("AC71","Piles LR14 *2","Accidentelle",2.07,10,"Oui"),
    ("AC72","Piles LR 20 *2","Accidentelle",2.25,10,"Oui"),("AC73","Lampe de chevet à pince pour ampoule E27","Accidentelle",6.36,2,"Oui"),
    ("AC74","Ampoule LED E27","Accidentelle",0.78,10,"Oui"),("AC75","Ampoule LED E14","Accidentelle",1.81,10,"Oui"),
    ("AC76","Bloc 3 prises avec terre et rallonge","Accidentelle",2.16,1,"Oui"),("AC77","Rallonge avec terre","Accidentelle",4.08,1,"Oui"),
    ("AC79","Cordon HDMI 1,50m","Accidentelle",4.02,1,"Oui"),("AC80","Lacets noirs","Accidentelle",1.04,10,"Oui"),
    ("AC81","Cirage applicateur incolore","Accidentelle",1.42,10,"Oui"),("AC82","Nécessaire de couture","Accidentelle",1.20,10,"Oui"),
    ("AC83","Boule quies","Accidentelle",6.91,10,"Oui"),("AC85","Déodorisant stick *2","Accidentelle",1.14,10,"Oui"),
    ("AC86","Cintre plastique","Accidentelle",0.17,10,"Oui"),("AC87","Bouteille isolante 1L","Accidentelle",10.47,1,"Oui"),
    ("AC88","Porte filtre","Accidentelle",4.38,2,"Oui"),("AC89","Filtre à café N°4","Accidentelle",1.14,10,"Oui"),
    ("AC90","Cafetière italienne induction BIALETTI","Accidentelle",33.20,1,"Oui"),("AC91","Rouleau papier cuisson 15m","Accidentelle",1.59,1,"Oui"),
    ("AC92","Table de cuisson + faitout","Accidentelle",55.20,1,"Oui"),("AC93","Ventilateur","Accidentelle",21.00,1,"Oui"),
    ("AC94","Réveil matin","Accidentelle",2.53,2,"Oui"),("AC95","Tondeuse barbe, nez, oreille PHILIPS","Accidentelle",41.45,1,"Oui"),
    ("AC96","Tondeuse à barbe GILETTE","Accidentelle",40.28,1,"Oui"),("AC97","Tondeuse cheuveux pro BABYLISS","Accidentelle",31.88,1,"Oui"),
    ("AC98","Bloc correspondance ligné","Accidentelle",1.27,10,"Oui"),("AC99","Bloc correspondance uni","Accidentelle",1.26,10,"Oui"),
    ("AC100","Cahier de 96 pages","Accidentelle",0.46,10,"Oui"),("AC101","Stylo bleu","Accidentelle",0.09,10,"Oui"),
    ("AC102","Stylo noir","Accidentelle",0.09,10,"Oui"),("AC103","Stylo 4 couleurs","Accidentelle",1.99,10,"Oui"),
    ("AC104","Gomme","Accidentelle",0.53,10,"Oui"),("AC105","Crayon de papier","Accidentelle",0.13,10,"Oui"),
    ("AC106","Ramette papier 500 feuilles blanches","Accidentelle",6.97,10,"Oui"),("AC107","Chemise sans rabat à élastique","Accidentelle",0.53,10,"Oui"),
    ("AC108","Ciseaux bout rond","Accidentelle",0.41,10,"Oui"),("AC109","Batton de colle","Accidentelle",0.26,10,"Oui"),
    ("AC110","Rouleau ruban adhésif","Accidentelle",0.24,10,"Oui"),("AC111","Pochettes de 12 crayon de couleurs","Accidentelle",0.96,10,"Oui"),
    ("AC112","Enveloppes adhésive 110*220 paquet de 25","Accidentelle",0.53,10,"Oui"),("AC113","Enveloppes adhésive 114*162 paquet de 25","Accidentelle",0.45,10,"Oui"),
    ("AC114","Enveloppes Kraft 162*229 paquet de 25","Accidentelle",1.38,10,"Oui"),("AC115","Enveloppes kraft 229*324 paquet de 25","Accidentelle",2.21,10,"Oui"),
    ("AC116","Carte anniversaire","Accidentelle",1.07,10,"Oui"),("AC117","Carte bonne fête","Accidentelle",0.93,10,"Oui"),
    ("AC118","Carte de noël","Accidentelle",0.93,10,"Oui"),("AC119","Carte de vœux","Accidentelle",0.93,10,"Oui"),
    ("AC120","Jeux de tarot","Accidentelle",2.49,10,"Oui"),("AC121","Jeu de 54 cartes","Accidentelle",0.55,10,"Oui"),
    ("AC122","Bouilloire électrique 0,9L 500W BESTRON","Accidentelle",12.47,10,"Oui"),("AC123","Eponge végétale individuelle","Accidentelle",0.18,10,"Oui"),
    ("P1","Croissant","Patisserie",1.31,10,"Oui"),("P2","Pain au chocolat","Patisserie",1.31,10,"Oui"),
    ("P3","Escargot aux raisons","Patisserie",1.84,10,"Oui"),("P4","Brioche 6 personnes","Patisserie",9.61,10,"Oui"),
    ("P5","Grand pain viennois","Patisserie",2.89,10,"Oui"),("P6","Chausson aux pommes","Patisserie",1.84,10,"Oui"),
    ("P7","Quiche lorraine","Patisserie",3.31,10,"Oui"),("P8","Quiche au thon","Patisserie",3.31,10,"Oui"),
    ("P9","Baguette aux graines","Patisserie",1.63,10,"Oui"),("P10","Pain complet","Patisserie",3.10,10,"Oui"),
    ("P11","Gateau Paris-Brest (8 personnes)","Patisserie",33.34,10,"Oui"),("P12","Eclair vanille","Patisserie",3.26,10,"Oui"),
    ("P13","Eclair café","Patisserie",3.26,10,"Oui"),("P14","Eclair chocolat","Patisserie",3.26,10,"Oui"),
    ("P15","Millefeuilles","Patisserie",4.31,10,"Oui"),("P16","Flan","Patisserie",4.10,10,"Oui"),
    ("P17","Paris-Brest","Patisserie",4.31,10,"Oui"),("P18","Framboisier 6 personnes","Patisserie",26.62,10,"Oui"),
    ("P19","Escargot chocolat","Patisserie",1.84,10,"Oui"),("P20","Pâté lorrain","Patisserie",3.31,10,"Oui"),
    ("P21","Tourte lorraine","Patisserie",3.47,10,"Oui"),("P22","Fraisier (6 personnes)","Patisserie",26.62,10,"Oui"),
    ("P23","Royal","Patisserie",4.57,10,"Oui"),("P24","Pâté poulet curry","Patisserie",3.62,10,"Oui"),
    ("P25","Tarte citron","Patisserie",4.31,10,"Oui"),("P26","Royal (6 personnes)","Patisserie",26.62,10,"Oui"),
    ("T1","News","Tabac",12.40,20,"Oui"),("T2","News à rouler 30g","Tabac",17.40,10,"Oui"),
    ("T4","Pot News 30g","Tabac",17.40,10,"Oui"),("T5","Lucky strike","Tabac",12.50,20,"Oui"),
    ("T6","Camel filtre paquet rigide","Tabac",12.50,20,"Oui"),("T7","Winston light paquet de 20","Tabac",12.50,20,"Oui"),
    ("T8","Camel à rouler 30g","Tabac",18.15,20,"Oui"),("T9","Mehari's java","Tabac",14.00,20,"Oui"),
    ("T10","Winston filtre paquet rigide","Tabac",12.50,20,"Oui"),("T11","Malboro à rouler 30g","Tabac",18.25,20,"Oui"),
    ("T12","Mini java cigarillos *20","Tabac",12.40,20,"Oui"),("T13","Gauloise blonde paquet de 20","Tabac",12.50,20,"Oui"),
    ("T14","Intervalle blanc","Tabac",24.40,20,"Oui"),("T15","Intervalle Bleu","Tabac",24.55,20,"Oui"),
    ("T16","JPS american blend","Tabac",12.50,20,"Oui"),("T17","John player special","Tabac",12.50,20,"Oui"),
    ("T18","La paz cigarillos *5","Tabac",6.25,20,"Oui"),("T19","Malboro","Tabac",13.00,20,"Oui"),
    ("T20","Malboro light","Tabac",13.00,20,"Oui"),("T21","Malboro 100S","Tabac",13.00,20,"Oui"),
    ("T23","Winston à rouler blond","Tabac",18.25,20,"Oui"),("T24","Winston à rouler brun","Tabac",18.25,20,"Oui"),
    ("T25","Pall mall à rouler","Tabac",17.50,20,"Oui"),
]

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS produits (
        id TEXT PRIMARY KEY, nom TEXT, categorie TEXT, prix REAL, qte_max INTEGER, actif TEXT,
        jour_livraison TEXT DEFAULT '')""")
    c.execute("""CREATE TABLE IF NOT EXISTS parametres (cle TEXT PRIMARY KEY, valeur TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS bons (
        id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, categorie TEXT,
        nom TEXT, prenom TEXT, ecrou TEXT, batiment TEXT, cellule TEXT,
        total REAL, user_type TEXT DEFAULT 'invite',
        est_creance INTEGER DEFAULT 0, nom_creance TEXT DEFAULT '',
        jour_creance TEXT DEFAULT '', creance_soldee INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS lignes_bon (
        id INTEGER PRIMARY KEY AUTOINCREMENT, bon_id INTEGER,
        produit_id TEXT, designation TEXT, prix REAL, quantite INTEGER, total_ligne REAL,
        FOREIGN KEY(bon_id) REFERENCES bons(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS utilisateurs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, login TEXT UNIQUE,
        mot_de_passe TEXT, role TEXT)""")
    # ── Table compte cantinable ──────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS compte_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        label TEXT,
        montant REAL,
        categorie TEXT,
        bon_id INTEGER DEFAULT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS depenses_fixes (
        id TEXT PRIMARY KEY,
        label TEXT,
        montant REAL,
        actif INTEGER DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS reserve (
        produit_id TEXT PRIMARY KEY,
        nom TEXT,
        categorie TEXT,
        prix REAL,
        quantite INTEGER)""")
    # « Mon stock » : stock perso en cellule, alimenté automatiquement par les
    # bons au nom de l'utilisateur + les créances. Distinct de la réserve.
    c.execute("""CREATE TABLE IF NOT EXISTS mon_stock (
        produit_id TEXT PRIMARY KEY,
        nom TEXT,
        categorie TEXT,
        prix REAL,
        quantite INTEGER,
        peremption TEXT DEFAULT '')""")
    # Journal des retraits de « Mon stock » (widget de retrait quotidien)
    c.execute("""CREATE TABLE IF NOT EXISTS stock_retraits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        produit_id TEXT,
        nom TEXT,
        categorie TEXT,
        prix REAL,
        quantite INTEGER)""")
    # Livraisons attendues : une cantine à mon nom ou une créance crée une
    # réception prévue pour le jour de livraison. Le stock n'est alimenté qu'une
    # fois la réception CONFIRMÉE (via le widget), avec les quantités réellement
    # reçues (le non-livré est oublié).
    c.execute("""CREATE TABLE IF NOT EXISTS receptions_attendues (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT,                 -- 'cantine' ou 'creance'
        source_uid TEXT,
        personne TEXT,             -- nom (créance) ; vide pour une cantine perso
        categorie TEXT,
        date_prevue TEXT,          -- 'YYYY-MM-DD'
        statut TEXT,               -- 'attente' / 'recu'
        date_creation TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS receptions_lignes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reception_id INTEGER,
        produit_id TEXT,
        nom TEXT,
        prix REAL,
        qte_attendue INTEGER,
        qte_recue INTEGER DEFAULT 0)""")
    # Rappels de rachat : override manuel par article (1 = me rappeler,
    # 0 = ne plus rappeler). Sans entrée, la classification auto décide.
    c.execute("""CREATE TABLE IF NOT EXISTS stock_rappel (
        produit_id TEXT PRIMARY KEY,
        actif INTEGER)""")
    # Articles (de mes bons) à rembourser : suivis avec date de commande et de
    # livraison jusqu'à validation du remboursement.
    c.execute("""CREATE TABLE IF NOT EXISTS remboursements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        produit_id TEXT,
        nom TEXT,
        categorie TEXT,
        prix REAL,
        quantite INTEGER,
        date_commande TEXT,
        date_livraison TEXT,
        source_uid TEXT,
        statut TEXT,               -- 'a_rembourser' / 'rembourse'
        date_ajout TEXT,
        date_remboursement TEXT DEFAULT '')""")
    # Liste hygiène mensuelle personnalisable (corporelle + cellule)
    c.execute("""CREATE TABLE IF NOT EXISTS hygiene_liste (
        produit_id TEXT PRIMARY KEY,
        groupe TEXT,
        qte_par_pers INTEGER,
        ordre INTEGER)""")
    # Remplissage — codes du catalogue v2 (ENTRETIEN HYGIENE). Respecte les
    # règles : marques (pas de 1er prix), gel douche AXE, shampoing/dentifrice
    # de marque, lessive LIQUIDE ; SANS gel cheveux, rasoir/mousse à raser,
    # javel, papier WC, lessive poudre, sacs poubelle, savon mains, stick
    # lèvres, mouchoirs.
    #   groupe 'corporelle' = par personne (×pers)   |   'cellule' = fixe
    hyg_defaut = [
        # Corporelle (par personne)
        ("EH130", "corporelle", 1),  # Gel douche AXE 250mL
        ("EH134", "corporelle", 1),  # Shampoing 2 en 1 FRUCTIS 250mL
        ("EH136", "corporelle", 1),  # Dentifrice AQUAFRESH triple action
        ("EH141", "corporelle", 1),  # Brosse à dents SIGNAL souple
        ("EH155", "corporelle", 1),  # Déo stick WILLIAMS 75mL
        ("EH158", "corporelle", 1),  # Crème hydratante NIVEA 100mL
        ("EH169", "corporelle", 1),  # Cotons tiges ECO+
        # Cellule (fixe)
        ("EH45", "cellule", 1),      # Lessive liquide Le Chat 1,17L
        ("EH47", "cellule", 1),      # Assouplissant soupline 1,9L
        ("EH52", "cellule", 1),      # Liquide vaisselle 1L
        ("EH54", "cellule", 1),      # Crème à récurer 750mL
        ("EH55", "cellule", 1),      # Gel WC 750mL
        ("EH48", "cellule", 1),      # Lingettes St marc multi usages
        ("EH50", "cellule", 1),      # Nettoyant ménager Saint Marc 1L
        ("EH40", "cellule", 6),      # Eponge végétale abrasive
        ("EH68", "cellule", 2),      # Chiffons microfibres
    ]
    # Reset v2 : les anciens codes (HY*/AC*) n'existent plus dans le nouveau
    # catalogue. On recharge la liste une fois sur les codes EH*.
    c.execute("SELECT valeur FROM parametres WHERE cle='hygiene_init_v2'")
    if c.fetchone() is None:
        c.execute("DELETE FROM hygiene_liste")
        for i, (code, grp, q) in enumerate(hyg_defaut):
            c.execute("INSERT OR REPLACE INTO hygiene_liste VALUES (?,?,?,?)",
                      (code, grp, q, i))
        c.execute("INSERT OR REPLACE INTO parametres VALUES ('hygiene_init_v1','1')")
        c.execute("INSERT OR REPLACE INTO parametres VALUES ('hygiene_init_v2','1')")
    # Dépenses fixes par défaut
    for fid, flbl, fmnt in [("tv","Télévision",8.0),("frigo","Frigo",10.0),("telephone","Téléphone",20.0)]:
        c.execute("INSERT OR IGNORE INTO depenses_fixes VALUES (?,?,?,1)", (fid, flbl, fmnt))
    try:
        c.execute("ALTER TABLE bons ADD COLUMN user_type TEXT DEFAULT 'invite'")
    except: pass
    for ddl in [
        "ALTER TABLE produits ADD COLUMN jour_livraison TEXT DEFAULT ''",
        "ALTER TABLE bons ADD COLUMN est_creance INTEGER DEFAULT 0",
        "ALTER TABLE bons ADD COLUMN nom_creance TEXT DEFAULT ''",
        "ALTER TABLE bons ADD COLUMN jour_creance TEXT DEFAULT ''",
        "ALTER TABLE bons ADD COLUMN creance_soldee INTEGER DEFAULT 0",
        "ALTER TABLE bons ADD COLUMN date_creance TEXT DEFAULT ''",
        "ALTER TABLE bons ADD COLUMN uid TEXT DEFAULT ''",
        "ALTER TABLE mon_stock ADD COLUMN peremption TEXT DEFAULT ''",
    ]:
        try: c.execute(ddl)
        except: pass
    # Attribue un uid aux bons qui n'en ont pas encore (bases antérieures)
    c.execute("SELECT id FROM bons WHERE uid IS NULL OR uid=''")
    for (bid,) in c.fetchall():
        c.execute("UPDATE bons SET uid=? WHERE id=?", (str(uuid.uuid4()), bid))
    # Comptes par défaut
    c.execute("INSERT OR IGNORE INTO utilisateurs VALUES (1,'yoann','1234','yoann')")
    c.execute("INSERT OR IGNORE INTO utilisateurs VALUES (2,'admin','admin','admin')")
    # Produits — catalogue v2 (octobre 2026).
    # Le nouveau catalogue officiel remplace entièrement l'ancien. On applique
    # une fois (flag catalogue_v2) : on vide la table produits et on recharge
    # depuis catalogue_data, puis on fixe le jour de livraison de chaque
    # catégorie. Les bons déjà enregistrés (historique, créances) ne sont pas
    # touchés — ils conservent leurs anciens libellés.
    _catalogue_charge = False
    try:
        import catalogue_data as _cat
        c.execute("SELECT valeur FROM parametres WHERE cle='catalogue_v2'")
        deja = c.fetchone() is not None
        c.execute("SELECT COUNT(*) FROM produits")
        vide = c.fetchone()[0] == 0
        if vide or not deja:
            c.execute("DELETE FROM produits")
            c.executemany(
                "INSERT INTO produits (id,nom,categorie,prix,qte_max,actif,jour_livraison) "
                "VALUES (?,?,?,?,?, 'Oui', '')",
                _cat.produits_rows())
            # Jour de livraison par catégorie (affiché dans le titre du bon)
            for nom, _pref, jour, *_rest in _cat.CATEGORIES_META:
                c.execute("INSERT OR REPLACE INTO parametres VALUES (?,?)",
                          (f"livraison_cat_{nom}", jour))
            c.execute("INSERT OR REPLACE INTO parametres VALUES ('catalogue_v2','1')")
        _catalogue_charge = True
    except Exception:
        _catalogue_charge = False
    # Repli : si catalogue_data est introuvable et base vide, ancien catalogue
    if not _catalogue_charge:
        c.execute("SELECT COUNT(*) FROM produits")
        if c.fetchone()[0] == 0:
            c.executemany(
                "INSERT INTO produits (id,nom,categorie,prix,qte_max,actif) VALUES (?,?,?,?,?,?)",
                PRODUITS_INITIAUX)
    # Paramètres Yoann
    defaults = [("nom","LUTZ"),("prenom","Yoann"),("ecrou","9283"),
                ("batiment","C"),("cellule","323"),("signature_path",""),
                ("maj_source","github"),("maj_chemin",""),
                ("bon_sans_identite","0"),
                ("ramassage_jour","Mercredi"),
                ("distribution_delai_semaines","3"),
                ("stock_seuil_bas","2")]
    for k, v in defaults:
        c.execute("INSERT OR IGNORE INTO parametres VALUES (?,?)", (k, v))

    # ── Calage d'impression : reset unique vers les valeurs mesurées ──────────
    # Les anciennes bases peuvent contenir des essais de calage erronés
    # (impr_y1/impr_pas/offsets). On force UNE FOIS le calage vérifié par
    # superposition sur les vrais bons, puis on marque l'opération faite pour
    # que l'utilisateur puisse ensuite réajuster librement.
    c.execute("SELECT valeur FROM parametres WHERE cle='impr_calage_v6'")
    if c.fetchone() is None:
        for k, v in [("impr_y1", "79"), ("impr_pas", "5.15"),
                     ("impression_offset_x", "0"), ("impression_offset_y", "0")]:
            c.execute("INSERT OR REPLACE INTO parametres VALUES (?,?)", (k, v))
        c.execute("INSERT OR REPLACE INTO parametres VALUES ('impr_calage_v6','1')")

    # ── Décalage vertical PAR CATÉGORIE (mode papier pré-imprimé) ─────────────
    # Certains blocs pré-imprimés (ex : Hygiène) ont leur tableau physiquement
    # décalé par rapport aux autres. Ce réglage, propre à chaque catégorie,
    # corrige UNE catégorie sans toucher aux autres. Positif = descend le texte.
    _cats_dy = ["boissons", "produits_laitiers", "fruits_legumes", "casher",
                "alimentaire", "produits_frais", "halal", "entretien_hygiene",
                "patisseries", "tabac", "revues"]
    for slug in _cats_dy:
        c.execute("INSERT OR IGNORE INTO parametres VALUES (?, '0')",
                  (f"impr_dy_{slug}",))

    conn.commit()
    conn.close()

def get_parametres():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT cle, valeur FROM parametres")
    result = dict(c.fetchall())
    conn.close()
    return result

def set_parametre(cle, valeur):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO parametres VALUES (?,?)", (cle, valeur))
    conn.commit()
    conn.close()

def get_produits(categorie=None, actif_only=True):
    conn = get_connection()
    c = conn.cursor()
    if categorie:
        q = ("SELECT * FROM produits WHERE categorie=?"
             + (" AND actif='Oui'" if actif_only else ""))
        c.execute(q, (categorie,))
    else:
        q = ("SELECT * FROM produits"
             + (" WHERE actif='Oui'" if actif_only else ""))
        c.execute(q)
    result = c.fetchall()
    conn.close()
    import re as _re
    def _sort_key(row):
        num = _re.sub(r'[^0-9]', '', str(row[0]))
        return int(num) if num else 0
    return sorted(result, key=_sort_key)

def update_produit(prod_id, nom, prix, qte_max, actif, jour_livraison=None):
    conn = get_connection()
    c = conn.cursor()
    if jour_livraison is None:
        c.execute("UPDATE produits SET nom=?, prix=?, qte_max=?, actif=? WHERE id=?",
                  (nom, prix, qte_max, actif, prod_id))
    else:
        c.execute("UPDATE produits SET nom=?, prix=?, qte_max=?, actif=?, jour_livraison=? WHERE id=?",
                  (nom, prix, qte_max, actif, jour_livraison, prod_id))
    conn.commit()
    conn.close()

def set_jour_livraison(prod_ids, jour):
    """prod_ids : un identifiant produit (str) ou une liste d'identifiants."""
    if isinstance(prod_ids, str):
        prod_ids = [prod_ids]
    conn = get_connection()
    c = conn.cursor()
    c.executemany("UPDATE produits SET jour_livraison=? WHERE id=?",
                  [(jour, pid) for pid in prod_ids])
    conn.commit()
    conn.close()

def verifier_utilisateur(login, mdp):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT role FROM utilisateurs WHERE login=? AND mot_de_passe=?", (login, mdp))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def changer_mot_de_passe(login, nouveau_mdp):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE utilisateurs SET mot_de_passe=? WHERE login=?", (nouveau_mdp, login))
    conn.commit()
    conn.close()

def sauvegarder_bon(categorie, nom, prenom, ecrou, batiment, cellule, lignes, total, date_str,
                     user_type="invite", est_creance=0, nom_creance="", jour_creance="",
                     date_creance=""):
    conn = get_connection()
    c = conn.cursor()
    bon_uid = str(uuid.uuid4())
    c.execute("""INSERT INTO bons
        (date,categorie,nom,prenom,ecrou,batiment,cellule,total,user_type,
         est_creance,nom_creance,jour_creance,date_creance,uid) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (date_str, categorie, nom, prenom, ecrou, batiment, cellule, total, user_type,
               1 if est_creance else 0, nom_creance, jour_creance, date_creance, bon_uid))
    bon_id = c.lastrowid
    for l in lignes:
        c.execute("INSERT INTO lignes_bon (bon_id,produit_id,designation,prix,quantite,total_ligne) VALUES (?,?,?,?,?,?)",
                  (bon_id, l['id'], l['nom'], l['prix'], l['qte'], l['total']))
    conn.commit()
    conn.close()
    # Livraison attendue : bons à MON nom + créances créent une réception à
    # confirmer le jour de livraison (le stock n'est PAS alimenté tout de suite).
    try:
        _creer_reception_si_concerne(nom, lignes, bool(est_creance),
                                     categorie, nom_creance, date_creance, bon_uid)
    except Exception:
        pass
    return bon_id

def get_creances(uniquement_actives=True):
    conn = get_connection()
    c = conn.cursor()
    q = "SELECT * FROM bons WHERE est_creance=1"
    if uniquement_actives:
        q += " AND creance_soldee=0"
    q += " ORDER BY id DESC"
    c.execute(q)
    result = c.fetchall()
    conn.close()
    return result

def marquer_creance_soldee(bon_id, soldee=True):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE bons SET creance_soldee=? WHERE id=?", (1 if soldee else 0, bon_id))
    conn.commit()
    conn.close()

def get_bon_creance_info(bon_id):
    """Retourne (est_creance, creance_soldee, nom_creance) pour un bon donné,
    ou None si le bon n'existe pas."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT est_creance, creance_soldee, nom_creance FROM bons WHERE id=?", (bon_id,))
    row = c.fetchone()
    conn.close()
    if row is None:
        return None
    return (row[0] or 0, row[1] or 0, row[2] or "")


def get_bon_complet(bon_id):
    """Retourne toutes les infos d'un bon sous forme de dict, ou None."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM bons WHERE id=?", (bon_id,))
    row = c.fetchone()
    conn.close()
    if row is None:
        return None
    d = dict(row)
    return {
        "categorie": d.get("categorie", ""),
        "nom": d.get("nom", ""), "prenom": d.get("prenom", ""),
        "ecrou": d.get("ecrou", ""), "batiment": d.get("batiment", ""),
        "cellule": d.get("cellule", ""), "date": d.get("date", ""),
        "user_type": d.get("user_type", "invite"),
        "nom_creance": d.get("nom_creance", ""),
        "jour_creance": d.get("jour_creance", ""),
        "date_creance": d.get("date_creance", ""),
    }


def get_bon_pour_recalcul(bon_id):
    """Retourne (categorie, [produit_ids]) d'un bon, pour recalculer ses dates
    de livraison. None si le bon n'existe pas."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT categorie FROM bons WHERE id=?", (bon_id,))
    row = c.fetchone()
    if row is None:
        conn.close()
        return None
    categorie = row[0]
    c.execute("SELECT produit_id FROM lignes_bon WHERE bon_id=?", (bon_id,))
    pids = [r[0] for r in c.fetchall()]
    conn.close()
    return (categorie, pids)


def modifier_date_bon(bon_id, nouvelle_date, jour_creance=None, date_creance=None):
    """Met à jour la date de posage d'un bon, et si fournis, les jour/date de
    créance recalculés."""
    conn = get_connection()
    c = conn.cursor()
    if jour_creance is None and date_creance is None:
        c.execute("UPDATE bons SET date=? WHERE id=?", (nouvelle_date, bon_id))
    else:
        c.execute("UPDATE bons SET date=?, jour_creance=?, date_creance=? WHERE id=?",
                  (nouvelle_date, jour_creance or "", date_creance or "", bon_id))
    conn.commit()
    conn.close()


def get_creances_calendrier(uniquement_actives=True):
    """Retourne les créances pour l'export calendrier, sous forme de liste de
    dicts : {uid, nom, montant, categorie, date_bon, jour_creance, date_creance, soldee}."""
    conn = get_connection()
    c = conn.cursor()
    q = ("SELECT uid, nom_creance, total, categorie, date, jour_creance, "
         "date_creance, creance_soldee FROM bons WHERE est_creance=1")
    if uniquement_actives:
        q += " AND creance_soldee=0"
    q += " ORDER BY date_creance, id"
    c.execute(q)
    rows = c.fetchall()
    conn.close()
    return [{"uid": r[0] or "", "nom": r[1] or "", "montant": r[2] or 0.0,
             "categorie": r[3] or "", "date_bon": r[4] or "",
             "jour_creance": r[5] or "", "date_creance": r[6] or "",
             "soldee": bool(r[7])} for r in rows]


# ─────────────────────────────────────────────
# Export / Import des créances (transfert entre postes)
# ─────────────────────────────────────────────
EXPORT_FORMAT_VERSION = 1

def exporter_creances(chemin_fichier):
    """Exporte toutes les créances (actives et soldées) vers un fichier JSON,
    lignes de bon incluses. Retourne le nombre de créances exportées."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM bons WHERE est_creance=1 ORDER BY id")
    bons = c.fetchall()

    creances = []
    for b in bons:
        b = dict(b)
        # Garantit un uid même sur de très vieux enregistrements
        if not b.get("uid"):
            b["uid"] = str(uuid.uuid4())
            c.execute("UPDATE bons SET uid=? WHERE id=?", (b["uid"], b["id"]))
        c.execute("SELECT produit_id,designation,prix,quantite,total_ligne "
                  "FROM lignes_bon WHERE bon_id=?", (b["id"],))
        lignes = [dict(l) for l in c.fetchall()]
        b.pop("id", None)  # l'id local n'a pas de sens sur l'autre poste
        b["lignes"] = lignes
        creances.append(b)
    conn.commit()
    conn.close()

    data = {
        "format": "cantine_creances",
        "version": EXPORT_FORMAT_VERSION,
        "creances": creances,
    }
    with open(chemin_fichier, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return len(creances)


def importer_creances(chemin_fichier):
    """Importe les créances d'un fichier JSON.
    - Créance inconnue (uid absent) : ajoutée.
    - Créance déjà présente (même uid) : son état récupéré/en attente est
      mis à jour depuis le fichier.
    Retourne un tuple (nb_ajoutees, nb_mises_a_jour).
    Lève ValueError si le fichier n'est pas un export de créances valide."""
    with open(chemin_fichier, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict) or data.get("format") != "cantine_creances":
        raise ValueError("Ce fichier n'est pas un export de créances valide.")

    creances = data.get("creances", [])
    conn = get_connection()
    c = conn.cursor()
    nb_ajoutees = 0
    nb_maj = 0

    for cr in creances:
        uid = cr.get("uid")
        if not uid:
            uid = str(uuid.uuid4())
        c.execute("SELECT id FROM bons WHERE uid=?", (uid,))
        existant = c.fetchone()

        if existant:
            # Mise à jour de l'état uniquement (récupéré / en attente)
            c.execute("UPDATE bons SET creance_soldee=? WHERE uid=?",
                      (int(cr.get("creance_soldee", 0) or 0), uid))
            nb_maj += 1
        else:
            c.execute("""INSERT INTO bons
                (date,categorie,nom,prenom,ecrou,batiment,cellule,total,user_type,
                 est_creance,nom_creance,jour_creance,date_creance,creance_soldee,uid)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (cr.get("date",""), cr.get("categorie",""), cr.get("nom",""),
                 cr.get("prenom",""), cr.get("ecrou",""), cr.get("batiment",""),
                 cr.get("cellule",""), float(cr.get("total",0) or 0),
                 cr.get("user_type","invite"), 1,
                 cr.get("nom_creance",""), cr.get("jour_creance",""),
                 cr.get("date_creance",""), int(cr.get("creance_soldee",0) or 0), uid))
            new_id = c.lastrowid
            for l in cr.get("lignes", []):
                c.execute("""INSERT INTO lignes_bon
                    (bon_id,produit_id,designation,prix,quantite,total_ligne)
                    VALUES (?,?,?,?,?,?)""",
                    (new_id, l.get("produit_id",""), l.get("designation",""),
                     float(l.get("prix",0) or 0), int(l.get("quantite",0) or 0),
                     float(l.get("total_ligne",0) or 0)))
            nb_ajoutees += 1

    conn.commit()
    conn.close()
    return nb_ajoutees, nb_maj

def get_historique_bons(limit=100):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM bons ORDER BY id DESC LIMIT ?", (limit,))
    result = c.fetchall()
    conn.close()
    return result

def get_lignes_bon(bon_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM lignes_bon WHERE bon_id=?", (bon_id,))
    result = c.fetchall()
    conn.close()
    return result

def get_creances_personne(nom_creance, uniquement_actives=False):
    """Retourne la liste des bons-créance d'une personne (par nom_creance),
    chacun sous forme de dict {categorie, date, soldee, lignes:[...]}.
    lignes = [{id, nom, qte, prix, total}, ...]"""
    conn = get_connection()
    c = conn.cursor()
    q = "SELECT id, categorie, date, creance_soldee FROM bons WHERE est_creance=1 AND nom_creance=?"
    if uniquement_actives:
        q += " AND creance_soldee=0"
    q += " ORDER BY date, id"
    c.execute(q, (nom_creance,))
    bons_rows = c.fetchall()

    bons = []
    for bid, cat, date, soldee in bons_rows:
        c.execute("SELECT produit_id, designation, prix, quantite, total_ligne "
                  "FROM lignes_bon WHERE bon_id=?", (bid,))
        lignes = [{"id": r[0], "nom": r[1], "prix": r[2],
                   "qte": r[3], "total": r[4]} for r in c.fetchall()]
        bons.append({"categorie": cat, "date": date,
                     "soldee": bool(soldee), "lignes": lignes})
    conn.close()
    return bons

def get_bons_creance_par_ids(bon_ids):
    """Retourne les bons-créance correspondant à une liste d'id, chacun sous
    forme de dict {nom, categorie, date, soldee, lignes:[...]}.
    Utilisé pour le récap d'une sélection multiple."""
    if not bon_ids:
        return []
    conn = get_connection()
    c = conn.cursor()
    bons = []
    for bid in bon_ids:
        c.execute("SELECT nom_creance, categorie, date, creance_soldee "
                  "FROM bons WHERE id=?", (bid,))
        row = c.fetchone()
        if row is None:
            continue
        nom, cat, date, soldee = row
        c.execute("SELECT produit_id, designation, prix, quantite, total_ligne "
                  "FROM lignes_bon WHERE bon_id=?", (bid,))
        lignes = [{"id": r[0], "nom": r[1], "prix": r[2],
                   "qte": r[3], "total": r[4]} for r in c.fetchall()]
        bons.append({"nom": nom or "", "categorie": cat, "date": date,
                     "soldee": bool(soldee), "lignes": lignes})
    conn.close()
    return bons

def get_budget_semaine():
    """Retourne (budget, total_depense) pour la semaine en cours."""
    from datetime import datetime, timedelta
    conn = get_connection()
    c = conn.cursor()
    # Lundi de la semaine courante
    today = datetime.now()
    lundi = today - timedelta(days=today.weekday())
    lundi_str = lundi.strftime("%d/%m/%Y")
    dimanche = lundi + timedelta(days=6)
    dimanche_str = dimanche.strftime("%d/%m/%Y")

    # Budget stocké en paramètre
    c.execute("SELECT valeur FROM parametres WHERE cle='budget_semaine'")
    row = c.fetchone()
    budget = float(row[0]) if row and row[0] else 0.0

    # Total dépensé cette semaine
    c.execute("SELECT date, total FROM bons")
    bons = c.fetchall()
    conn.close()

    total = 0.0
    for date_str, montant in bons:
        try:
            d = datetime.strptime(date_str, "%d/%m/%Y")
            if lundi <= d <= dimanche + timedelta(hours=23):
                total += montant
        except:
            pass
    return budget, round(total, 2)

def set_budget_semaine(montant):
    set_parametre("budget_semaine", str(montant))

def get_budget_demande():
    """Retourne True si le budget a déjà été demandé cette semaine."""
    from datetime import datetime, timedelta
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT valeur FROM parametres WHERE cle='budget_semaine_lundi'")
    row = c.fetchone()
    conn.close()
    if not row or not row[0]:
        return False
    today = datetime.now()
    lundi = (today - timedelta(days=today.weekday())).strftime("%d/%m/%Y")
    return row[0] == lundi

def marquer_budget_demande():
    from datetime import datetime, timedelta
    today = datetime.now()
    lundi = (today - timedelta(days=today.weekday())).strftime("%d/%m/%Y")
    set_parametre("budget_semaine_lundi", lundi)

def delete_bon(bon_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM lignes_bon WHERE bon_id=?", (bon_id,))
    c.execute("DELETE FROM bons WHERE id=?", (bon_id,))
    # Supprimer aussi la transaction compte liée
    c.execute("DELETE FROM compte_transactions WHERE bon_id=?", (bon_id,))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# COMPTE CANTINABLE
# ─────────────────────────────────────────────
def compte_ajouter_transaction(date, label, montant, categorie, bon_id=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO compte_transactions (date,label,montant,categorie,bon_id) VALUES (?,?,?,?,?)",
              (date, label, montant, categorie, bon_id))
    tid = c.lastrowid
    conn.commit()
    conn.close()
    return tid

def compte_modifier_transaction(tid, date, label, montant, categorie):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE compte_transactions SET date=?, label=?, montant=?, categorie=? WHERE id=?",
              (date, label, montant, categorie, tid))
    conn.commit()
    conn.close()

def compte_supprimer_transaction(tid):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM compte_transactions WHERE id=?", (tid,))
    conn.commit()
    conn.close()

def compte_get_transactions(limit=500):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM compte_transactions ORDER BY date DESC, id DESC LIMIT ?", (limit,))
    result = c.fetchall()
    conn.close()
    return result

def compte_get_solde():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(montant),0) FROM compte_transactions")
    solde = c.fetchone()[0]
    conn.close()
    return round(solde, 2)

def compte_get_stats():
    """Retourne (solde, total_revenus, total_depenses, total_cantines, total_fixes)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(montant),0) FROM compte_transactions")
    solde = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(montant),0) FROM compte_transactions WHERE montant>0")
    revenus = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(montant),0) FROM compte_transactions WHERE montant<0")
    depenses = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(montant),0) FROM compte_transactions WHERE categorie='Cantine'")
    cantines = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(montant),0) FROM compte_transactions WHERE categorie='Dépense fixe'")
    fixes = c.fetchone()[0]
    conn.close()
    return (round(solde,2), round(revenus,2), round(depenses,2),
            round(cantines,2), round(fixes,2))

# ── Dépenses fixes ──────────────────────────
def get_depenses_fixes():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM depenses_fixes")
    result = c.fetchall()
    conn.close()
    return result

def update_depense_fixe(fid, label, montant, actif):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE depenses_fixes SET label=?, montant=?, actif=? WHERE id=?",
              (label, montant, actif, fid))
    conn.commit()
    conn.close()

def ajouter_depense_fixe(fid, label, montant):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO depenses_fixes VALUES (?,?,?,1)", (fid, label, montant))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# Réserve de cantine (stock persistant pour la répartition par dette)
# ─────────────────────────────────────────────
def get_reserve():
    """Retourne la réserve sous forme de liste de dicts
    {id, nom, categorie, prix, qte} — quantités > 0 uniquement."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT produit_id, nom, categorie, prix, quantite FROM reserve "
              "WHERE quantite > 0")
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "nom": r[1], "categorie": r[2],
             "prix": r[3], "qte": r[4]} for r in rows]

def reserve_total():
    """Valeur totale de la réserve en euros."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(prix * quantite), 0) FROM reserve WHERE quantite > 0")
    v = c.fetchone()[0] or 0.0
    conn.close()
    return float(v)

def ajouter_a_reserve(articles):
    """Ajoute des articles à la réserve (cumule les quantités).
    articles : liste de dicts {id, nom, categorie, prix, qte}."""
    conn = get_connection()
    c = conn.cursor()
    for a in articles:
        pid = a["id"]
        qte = int(a.get("qte", 0) or 0)
        if qte <= 0:
            continue
        c.execute("SELECT quantite FROM reserve WHERE produit_id=?", (pid,))
        row = c.fetchone()
        if row:
            c.execute("UPDATE reserve SET quantite = quantite + ? WHERE produit_id=?",
                      (qte, pid))
        else:
            c.execute("INSERT INTO reserve (produit_id, nom, categorie, prix, quantite) "
                      "VALUES (?,?,?,?,?)",
                      (pid, a["nom"], a.get("categorie", ""), a["prix"], qte))
    conn.commit()
    conn.close()

def definir_reserve(articles):
    """Remplace entièrement la réserve par la liste fournie
    (utilisé pour enregistrer le reliquat après une répartition)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM reserve")
    for a in articles:
        qte = int(a.get("qte", 0) or 0)
        if qte <= 0:
            continue
        c.execute("INSERT INTO reserve (produit_id, nom, categorie, prix, quantite) "
                  "VALUES (?,?,?,?,?)",
                  (a["id"], a["nom"], a.get("categorie", ""), a["prix"], qte))
    conn.commit()
    conn.close()

def vider_reserve():
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM reserve")
    conn.commit()
    conn.close()

def modifier_qte_reserve(produit_id, nouvelle_qte):
    """Change la quantité d'un article de la réserve. Si <= 0, le supprime."""
    conn = get_connection()
    c = conn.cursor()
    if nouvelle_qte is None or int(nouvelle_qte) <= 0:
        c.execute("DELETE FROM reserve WHERE produit_id=?", (produit_id,))
    else:
        c.execute("UPDATE reserve SET quantite=? WHERE produit_id=?",
                  (int(nouvelle_qte), produit_id))
    conn.commit()
    conn.close()

def supprimer_de_reserve(produit_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM reserve WHERE produit_id=?", (produit_id,))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# « MON STOCK » : stock perso en cellule (widget quotidien)
# ─────────────────────────────────────────────
def mon_stock_get():
    """Liste de dicts {id, nom, categorie, prix, qte, peremption} — quantités > 0."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT produit_id, nom, categorie, prix, quantite, "
              "COALESCE(peremption,'') FROM mon_stock WHERE quantite > 0")
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "nom": r[1], "categorie": r[2],
             "prix": r[3], "qte": r[4], "peremption": r[5]} for r in rows]


def mon_stock_definir_peremption(produit_id, date_str):
    """Définit/efface la date de péremption (format 'YYYY-MM-DD', '' pour effacer)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE mon_stock SET peremption=? WHERE produit_id=?",
              (date_str or "", produit_id))
    conn.commit()
    conn.close()


def get_peremptions_proches(jours=7):
    """Articles périmés ou qui périment dans <= `jours` jours.
    Retourne des dicts {id, nom, qte, peremption, jours_restants} (négatif = périmé)."""
    import datetime as _dt
    today = _dt.date.today()
    res = []
    for a in mon_stock_get():
        p = (a.get("peremption") or "").strip()
        if not p:
            continue
        try:
            d = _dt.datetime.strptime(p, "%Y-%m-%d").date()
        except Exception:
            continue
        reste = (d - today).days
        if reste <= jours:
            res.append({"id": a["id"], "nom": a["nom"], "qte": a["qte"],
                        "peremption": p, "jours_restants": reste})
    res.sort(key=lambda x: x["jours_restants"])
    return res


def mon_stock_total():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(prix * quantite), 0) FROM mon_stock WHERE quantite > 0")
    v = c.fetchone()[0] or 0.0
    conn.close()
    return float(v)


def mon_stock_ajouter(articles):
    """Ajoute des articles à Mon stock (cumule les quantités).
    articles : liste de dicts {id, nom, categorie, prix, qte}."""
    conn = get_connection()
    c = conn.cursor()
    for a in articles:
        pid = a.get("id")
        if not pid:
            continue
        qte = int(a.get("qte", 0) or 0)
        if qte <= 0:
            continue
        c.execute("SELECT quantite FROM mon_stock WHERE produit_id=?", (pid,))
        row = c.fetchone()
        if row:
            c.execute("UPDATE mon_stock SET quantite = quantite + ? WHERE produit_id=?",
                      (qte, pid))
        else:
            c.execute("INSERT INTO mon_stock (produit_id, nom, categorie, prix, quantite) "
                      "VALUES (?,?,?,?,?)",
                      (pid, a.get("nom", pid), a.get("categorie", ""),
                       float(a.get("prix", 0) or 0), qte))
    conn.commit()
    conn.close()


def mon_stock_modifier_qte(produit_id, nouvelle_qte):
    conn = get_connection()
    c = conn.cursor()
    if nouvelle_qte is None or int(nouvelle_qte) <= 0:
        c.execute("DELETE FROM mon_stock WHERE produit_id=?", (produit_id,))
    else:
        c.execute("UPDATE mon_stock SET quantite=? WHERE produit_id=?",
                  (int(nouvelle_qte), produit_id))
    conn.commit()
    conn.close()


def mon_stock_vider():
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM mon_stock")
    conn.commit()
    conn.close()


def exporter_mon_stock(chemin_fichier):
    """Exporte Mon stock (+ les choix de rappel) dans un fichier JSON.
    Permet de transférer le stock d'une machine à l'autre sans tout retaper."""
    import datetime as _dt
    arts = mon_stock_get()
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT produit_id, actif FROM stock_rappel")
    rappels = {r[0]: int(r[1]) for r in c.fetchall()}
    conn.close()
    for a in arts:
        if a["id"] in rappels:
            a["rappel"] = rappels[a["id"]]
    data = {"format": "cantine_mon_stock", "version": 1,
            "date": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "articles": arts}
    with open(chemin_fichier, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return len(arts)


def importer_mon_stock(chemin_fichier, remplacer=True):
    """Importe Mon stock depuis un fichier JSON d'export.
    remplacer=True : le stock importé REMPLACE le stock actuel.
    remplacer=False : les quantités s'AJOUTENT au stock actuel.
    Retourne le nombre d'articles importés. Lève ValueError si le fichier est
    invalide."""
    with open(chemin_fichier, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or data.get("format") != "cantine_mon_stock":
        raise ValueError("Ce fichier n'est pas un export de stock valide.")
    arts = data.get("articles", [])
    conn = get_connection()
    c = conn.cursor()
    if remplacer:
        c.execute("DELETE FROM mon_stock")
    for a in arts:
        pid = a.get("id")
        if not pid:
            continue
        try:
            q = int(a.get("qte", 0) or 0)
        except (TypeError, ValueError):
            q = 0
        if q <= 0:
            continue
        nom = a.get("nom", pid)
        cat = a.get("categorie", "")
        prix = float(a.get("prix", 0) or 0)
        perem = (a.get("peremption", "") or "")
        if remplacer:
            c.execute("INSERT OR REPLACE INTO mon_stock "
                      "(produit_id, nom, categorie, prix, quantite, peremption) "
                      "VALUES (?,?,?,?,?,?)", (pid, nom, cat, prix, q, perem))
        else:
            c.execute("SELECT quantite FROM mon_stock WHERE produit_id=?", (pid,))
            row = c.fetchone()
            if row:
                c.execute("UPDATE mon_stock SET quantite = quantite + ? WHERE produit_id=?",
                          (q, pid))
                if perem:
                    c.execute("UPDATE mon_stock SET peremption=? WHERE produit_id=?",
                              (perem, pid))
            else:
                c.execute("INSERT INTO mon_stock "
                          "(produit_id, nom, categorie, prix, quantite, peremption) "
                          "VALUES (?,?,?,?,?,?)", (pid, nom, cat, prix, q, perem))
        # choix de rappel (apprentissage) s'il est présent dans l'export
        if "rappel" in a:
            try:
                c.execute("INSERT OR REPLACE INTO stock_rappel VALUES (?,?)",
                          (pid, 1 if int(a["rappel"]) else 0))
            except Exception:
                pass
    conn.commit()
    conn.close()
    return sum(1 for a in arts if int(a.get("qte", 0) or 0) > 0)


def retirer_du_stock(produit_id, qte=1, journaliser=True):
    """Retire `qte` d'un article de MON STOCK et journalise le retrait.
    Ne descend jamais sous 0 ; supprime la ligne si la quantité tombe à 0.
    Retourne la quantité réellement retirée (0 si absent/épuisé)."""
    import datetime as _dt
    try:
        qte = int(qte)
    except (TypeError, ValueError):
        qte = 1
    if qte <= 0:
        return 0
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT nom, categorie, prix, quantite FROM mon_stock WHERE produit_id=?",
              (produit_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return 0
    nom, categorie, prix, dispo = row[0], row[1], row[2], int(row[3] or 0)
    retire = min(qte, dispo)
    if retire <= 0:
        conn.close()
        return 0
    reste = dispo - retire
    if reste <= 0:
        c.execute("DELETE FROM mon_stock WHERE produit_id=?", (produit_id,))
    else:
        c.execute("UPDATE mon_stock SET quantite=? WHERE produit_id=?", (reste, produit_id))
    if journaliser:
        c.execute("INSERT INTO stock_retraits "
                  "(date, produit_id, nom, categorie, prix, quantite) "
                  "VALUES (?,?,?,?,?,?)",
                  (_dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                   produit_id, nom, categorie, prix, retire))
    conn.commit()
    conn.close()
    return retire


def get_retraits(jour=None, limite=500):
    """Journal des retraits de Mon stock. `jour`='YYYY-MM-DD' ou None pour tout."""
    conn = get_connection()
    c = conn.cursor()
    if jour:
        c.execute("SELECT date, produit_id, nom, categorie, prix, quantite "
                  "FROM stock_retraits WHERE date LIKE ? "
                  "ORDER BY id DESC LIMIT ?", (f"{jour}%", limite))
    else:
        c.execute("SELECT date, produit_id, nom, categorie, prix, quantite "
                  "FROM stock_retraits ORDER BY id DESC LIMIT ?", (limite,))
    rows = c.fetchall()
    conn.close()
    return [{"date": r[0], "produit_id": r[1], "nom": r[2], "categorie": r[3],
             "prix": r[4], "quantite": r[5]} for r in rows]


def annuler_dernier_retrait():
    """Annule le dernier retrait : remet la quantité dans Mon stock et supprime
    la ligne de journal. Retourne (nom, qte) ou None."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, produit_id, nom, categorie, prix, quantite "
              "FROM stock_retraits ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    if not row:
        conn.close()
        return None
    rid, pid, nom, categorie, prix, qte = row
    c.execute("SELECT quantite FROM mon_stock WHERE produit_id=?", (pid,))
    ex = c.fetchone()
    if ex:
        c.execute("UPDATE mon_stock SET quantite = quantite + ? WHERE produit_id=?",
                  (int(qte), pid))
    else:
        c.execute("INSERT INTO mon_stock (produit_id, nom, categorie, prix, quantite) "
                  "VALUES (?,?,?,?,?)", (pid, nom, categorie, prix, int(qte)))
    c.execute("DELETE FROM stock_retraits WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    return (nom, int(qte))


# ─────────────────────────────────────────────
# LIVRAISONS ATTENDUES (réception à confirmer le jour de livraison)
# ─────────────────────────────────────────────
_JOURS_SEM = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def _date_livraison_prevue(categorie, creation=None):
    """Date de livraison prévue (objet date) pour une catégorie : ramassage +
    délai de distribution, ajusté sur le jour hebdo de la catégorie."""
    import datetime as _dt
    p = get_parametres()
    creation = creation or _dt.date.today()
    if isinstance(creation, _dt.datetime):
        creation = creation.date()
    ram_nom = p.get("ramassage_jour", "Mercredi")
    ram_idx = _JOURS_SEM.index(ram_nom) if ram_nom in _JOURS_SEM else 2
    ramassage = creation + _dt.timedelta(days=(ram_idx - creation.weekday()) % 7)
    try:
        delai = int(p.get("distribution_delai_semaines", "3") or 0)
    except ValueError:
        delai = 3
    lundi = ramassage - _dt.timedelta(days=ramassage.weekday())
    debut = lundi + _dt.timedelta(weeks=delai)
    jour_cat = p.get(f"livraison_cat_{categorie}", "")
    if jour_cat in _JOURS_SEM:
        return debut + _dt.timedelta(days=(_JOURS_SEM.index(jour_cat) - debut.weekday()) % 7)
    return debut


def _creer_reception_si_concerne(nom, lignes, est_creance, categorie,
                                 nom_creance, date_creance, source_uid):
    """Crée une livraison attendue si le bon est à mon nom (cantine) ou est une
    créance. Sinon ne fait rien."""
    import datetime as _dt
    try:
        mon_nom = (get_parametres().get("nom", "") or "").strip().upper()
    except Exception:
        mon_nom = ""
    nom_bon = (nom or "").strip().upper()
    if est_creance:
        typ = "creance"
        personne = (nom_creance or nom or "").strip()
    elif mon_nom and nom_bon == mon_nom:
        typ = "cantine"
        personne = ""
    else:
        return None
    # Date prévue : date_creance si fournie (créance), sinon calcul catégorie
    dprev = None
    if date_creance:
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                dprev = _dt.datetime.strptime(date_creance.strip(), fmt).date().strftime("%Y-%m-%d")
                break
            except Exception:
                dprev = None
    if not dprev:
        dprev = _date_livraison_prevue(categorie).strftime("%Y-%m-%d")

    arts = []
    for l in lignes:
        try:
            q = int(l.get("qte", 0) or 0)
        except (TypeError, ValueError):
            q = 0
        if q <= 0:
            continue
        arts.append((l.get("id"), l.get("nom", ""), float(l.get("prix", 0) or 0), q))
    if not arts:
        return None
    return creer_reception_attendue(typ, source_uid, personne, categorie, dprev, arts)


def creer_reception_attendue(typ, source_uid, personne, categorie, date_prevue, lignes):
    """lignes : liste de tuples (produit_id, nom, prix, qte_attendue)."""
    import datetime as _dt
    conn = get_connection()
    c = conn.cursor()
    c.execute("""INSERT INTO receptions_attendues
        (type, source_uid, personne, categorie, date_prevue, statut, date_creation)
        VALUES (?,?,?,?,?, 'attente', ?)""",
              (typ, source_uid, personne, categorie, date_prevue,
               _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    rid = c.lastrowid
    for pid, nom, prix, q in lignes:
        c.execute("""INSERT INTO receptions_lignes
            (reception_id, produit_id, nom, prix, qte_attendue, qte_recue)
            VALUES (?,?,?,?,?,0)""", (rid, pid, nom, prix, int(q)))
    conn.commit()
    conn.close()
    return rid


def get_receptions_dues(date_max=None):
    """Réceptions en attente dont la date prévue est <= date_max (par défaut
    aujourd'hui). Retourne une liste de dicts avec leurs lignes."""
    import datetime as _dt
    date_max = date_max or _dt.date.today().strftime("%Y-%m-%d")
    conn = get_connection()
    c = conn.cursor()
    c.execute("""SELECT id, type, source_uid, personne, categorie, date_prevue
                 FROM receptions_attendues
                 WHERE statut='attente' AND date_prevue <= ?
                 ORDER BY date_prevue, id""", (date_max,))
    recs = c.fetchall()
    res = []
    for r in recs:
        rid = r[0]
        c.execute("""SELECT id, produit_id, nom, prix, qte_attendue
                     FROM receptions_lignes WHERE reception_id=?""", (rid,))
        lignes = [{"ligne_id": x[0], "id": x[1], "nom": x[2], "prix": x[3],
                   "qte_attendue": x[4]} for x in c.fetchall()]
        res.append({"id": rid, "type": r[1], "source_uid": r[2], "personne": r[3],
                    "categorie": r[4], "date_prevue": r[5], "lignes": lignes})
    conn.close()
    return res


def get_receptions_attente_count():
    conn = get_connection()
    c = conn.cursor()
    import datetime as _dt
    today = _dt.date.today().strftime("%Y-%m-%d")
    c.execute("SELECT COUNT(*) FROM receptions_attendues "
              "WHERE statut='attente' AND date_prevue <= ?", (today,))
    n = c.fetchone()[0]
    conn.close()
    return n


def confirmer_reception(reception_id, recu_par_ligne):
    """Confirme une réception : `recu_par_ligne` = {ligne_id: qte_recue}.
    Ajoute les quantités reçues à Mon stock.
    - CANTINE : ce qui n'est pas reçu est OUBLIÉ ; la réception passe 'recu'.
    - CRÉANCE : ce qui n'est pas reçu RESTE DÛ (la réception reste 'attente' avec
      les quantités manquantes, pour être redemandée)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT type, categorie FROM receptions_attendues WHERE id=?", (reception_id,))
    row = c.fetchone()
    typ = row[0] if row else "cantine"
    categorie = row[1] if row else ""
    c.execute("SELECT id, produit_id, nom, prix, qte_attendue "
              "FROM receptions_lignes WHERE reception_id=?", (reception_id,))
    lignes = c.fetchall()
    articles = []
    restes = []   # (ligne_id, pid, nom, prix, reste)
    for ligne_id, pid, nom, prix, qa in lignes:
        q = recu_par_ligne.get(ligne_id, recu_par_ligne.get(str(ligne_id), 0))
        try:
            q = int(q)
        except (TypeError, ValueError):
            q = 0
        q = max(0, min(q, int(qa or 0)))
        if q > 0:
            articles.append({"id": pid, "nom": nom, "categorie": categorie,
                             "prix": float(prix or 0), "qte": q})
        reste = int(qa or 0) - q
        restes.append((ligne_id, pid, nom, prix, reste))

    total_reste = sum(r[4] for r in restes)
    if typ == "creance" and total_reste > 0:
        # Le manquant reste dû : on garde la réception en attente avec les restes
        for ligne_id, pid, nom, prix, reste in restes:
            if reste > 0:
                c.execute("UPDATE receptions_lignes SET qte_attendue=?, qte_recue=0 "
                          "WHERE id=?", (reste, ligne_id))
            else:
                c.execute("DELETE FROM receptions_lignes WHERE id=?", (ligne_id,))
        # statut reste 'attente' -> sera redemandée
    else:
        for ligne_id, pid, nom, prix, reste in restes:
            qa_recue = 0
            # note le reçu (qte_attendue - reste)
            c.execute("SELECT qte_attendue FROM receptions_lignes WHERE id=?", (ligne_id,))
            rr = c.fetchone()
            qa_val = int(rr[0]) if rr else 0
            c.execute("UPDATE receptions_lignes SET qte_recue=? WHERE id=?",
                      (qa_val - reste, ligne_id))
        c.execute("UPDATE receptions_attendues SET statut='recu' WHERE id=?", (reception_id,))
    conn.commit()
    conn.close()
    if articles:
        mon_stock_ajouter(articles)
    return len(articles)


def get_receptions(inclure_recues=False):
    """Toutes les livraisons attendues (et reçues si demandé), avec leurs lignes.
    Triées par date prévue. Pour l'écran « Livraisons à venir »."""
    conn = get_connection()
    c = conn.cursor()
    if inclure_recues:
        c.execute("""SELECT id, type, source_uid, personne, categorie, date_prevue, statut
                     FROM receptions_attendues ORDER BY date_prevue, id""")
    else:
        c.execute("""SELECT id, type, source_uid, personne, categorie, date_prevue, statut
                     FROM receptions_attendues WHERE statut='attente'
                     ORDER BY date_prevue, id""")
    recs = c.fetchall()
    res = []
    for r in recs:
        c.execute("""SELECT id, produit_id, nom, prix, qte_attendue, qte_recue
                     FROM receptions_lignes WHERE reception_id=?""", (r[0],))
        lignes = [{"ligne_id": x[0], "id": x[1], "nom": x[2], "prix": x[3],
                   "qte_attendue": x[4], "qte_recue": x[5]} for x in c.fetchall()]
        res.append({"id": r[0], "type": r[1], "source_uid": r[2], "personne": r[3],
                    "categorie": r[4], "date_prevue": r[5], "statut": r[6],
                    "lignes": lignes})
    conn.close()
    return res


def supprimer_reception(reception_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM receptions_lignes WHERE reception_id=?", (reception_id,))
    c.execute("DELETE FROM receptions_attendues WHERE id=?", (reception_id,))
    conn.commit()
    conn.close()


def _parse_date(s):
    import datetime as _dt
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return _dt.datetime.strptime((s or "").strip(), fmt).date()
        except Exception:
            pass
    return None


def creer_receptions_retroactives():
    """(Re)construit les livraisons attendues depuis les bons à MON nom + les
    créances déjà saisis.
    - Créance : date = sa « date estimée » (date_creance) ; incluse tant qu'elle
      n'est pas récupérée (soldée), même si la date est passée.
    - Cantine : date calculée depuis la date du bon ; incluse seulement si à venir.
    Les réceptions en attente NON commencées sont recalculées (dates corrigées) ;
    celles déjà partiellement reçues sont préservées. Retourne le nombre traité."""
    import datetime as _dt
    try:
        mon_nom = (get_parametres().get("nom", "") or "").strip().upper()
    except Exception:
        mon_nom = ""
    today = _dt.date.today()
    conn = get_connection()
    c = conn.cursor()

    # On repart propre : on supprime les réceptions EN ATTENTE non entamées
    # (aucune quantité déjà reçue). Celles partiellement reçues sont gardées.
    c.execute("""SELECT id FROM receptions_attendues WHERE statut='attente'
                 AND id NOT IN (SELECT DISTINCT reception_id FROM receptions_lignes
                                WHERE qte_recue > 0)""")
    a_suppr = [r[0] for r in c.fetchall()]
    for rid in a_suppr:
        c.execute("DELETE FROM receptions_lignes WHERE reception_id=?", (rid,))
        c.execute("DELETE FROM receptions_attendues WHERE id=?", (rid,))
    conn.commit()

    # uids encore couverts (reçus ou partiellement reçus) -> on n'y touche pas
    c.execute("SELECT DISTINCT source_uid FROM receptions_attendues")
    deja = {x[0] for x in c.fetchall() if x[0]}

    try:
        c.execute("""SELECT id, date, categorie, nom, est_creance, nom_creance,
                            date_creance, uid, creance_soldee FROM bons""")
        bons = c.fetchall()
    except Exception:
        c.execute("""SELECT id, date, categorie, nom, est_creance, nom_creance,
                            date_creance, uid FROM bons""")
        bons = [r + (0,) for r in c.fetchall()]
    conn.close()

    cree = 0
    for bid, date_bon, categorie, nom, est_cr, nom_cr, date_cr, uid, soldee in bons:
        uid = uid or f"legacy-{bid}"
        if uid in deja:
            continue
        est_creance = bool(est_cr)
        nom_u = (nom or "").strip().upper()
        if not (est_creance or (mon_nom and nom_u == mon_nom)):
            continue

        if est_creance:
            # déjà récupérée -> ignorer
            if int(soldee or 0) == 1:
                continue
            # date = date estimée de la créance (telle qu'affichée dans Créances)
            dprev_d = _parse_date(date_cr)
            if not dprev_d:
                base = _parse_date(date_bon)
                dprev_d = _date_livraison_prevue(categorie, base) if base \
                    else _date_livraison_prevue(categorie)
            # créance non récupérée : on l'inclut même si la date est passée
        else:
            # cantine : date calculée depuis la date du bon
            base = _parse_date(date_bon)
            dprev_d = _date_livraison_prevue(categorie, base) if base \
                else _date_livraison_prevue(categorie)
            # seulement les cantines à venir (pas celles déjà livrées)
            if dprev_d < today:
                continue

        # lignes du bon
        conn2 = get_connection(); c2 = conn2.cursor()
        c2.execute("SELECT produit_id, designation, prix, quantite "
                   "FROM lignes_bon WHERE bon_id=?", (bid,))
        arts = [(r[0], r[1], float(r[2] or 0), int(r[3] or 0))
                for r in c2.fetchall() if int(r[3] or 0) > 0]
        conn2.close()
        if not arts:
            continue
        typ = "creance" if est_creance else "cantine"
        personne = (nom_cr or nom or "").strip() if est_creance else ""
        creer_reception_attendue(typ, uid, personne, categorie,
                                 dprev_d.strftime("%Y-%m-%d"), arts)
        cree += 1
    return cree


# Catégories entièrement consommables (on rachète toujours)
_CATS_CONSO = {"BOISSONS", "PRODUITS LAITIERS", "FRUITS & LEGUMES", "CASHER",
               "ALIMENTAIRE", "PRODUITS FRAIS", "HALAL", "PATISSERIES", "TABAC"}
# Mots-clés d'objets DURABLES (achetés une fois). Détection par mot entier
# (frontières) pour éviter les faux positifs (ex. « oiseau » ne contient pas
# « seau » en tant que mot). Les articles « Recharge ... » sont, eux, consommables.
_DURABLE_MOTS = [
    "balai", "manche", "pelle", "balayette", "poubelle", "seau", "cuvette",
    "serpillere", "serpillère", "sechoir", "séchoir", "cintre", "casserole",
    "poele", "poêle", "couvercle", "saladier", "passoire", "econome", "économe",
    "rape", "râpe", "ouvre-boites", "ouvre boites", "ouvre boîtes", "presse",
    "egouttoir", "égouttoir", "hermetiques", "hermétiques", "bol", "mug",
    "verre", "assiette", "couteau", "cuillere", "cuillère", "fourchette",
    "louche", "spatule", "fouet", "maryse", "abattant", "lampe", "cordon",
    "isolante", "cafetiere", "cafetière", "bouilloire", "ventilateur", "reveil",
    "réveil", "faitout", "tondeuse", "casque", "montre", "calculatrice",
    "ciseaux", "miroir", "peigne", "quies", "rouleur", "blaireau", "cendrier",
    "diffuseur", "saladier", "tarot",
    # expressions (plusieurs mots)
    "kit wc", "brosse wc", "bloc 3 prises", "porte filtre", "table de cuisson",
    "brosse a cheveux", "brosse à cheveux", "coupe ongles", "lime a ongles",
    "lime à ongles", "jeu de 54", "jeu de tarot", "necessaire couture",
    "nécessaire couture", "machine a garnir", "machine à garnir",
    "lampe de chevet", "boule quies",
    # compléments (objets achetés une seule fois) — affinage des rappels.
    # (volontairement SANS mots ambigus comme « serviette » ou « gobelet » qui
    #  peuvent désigner un consommable.)
    "gourde", "thermos", "entonnoir", "decapsuleur", "décapsuleur",
    "tire-bouchon", "tire bouchon", "chargeur", "adaptateur", "multiprise",
    "rallonge", "radio", "ecouteurs", "écouteurs", "lunettes", "parapluie",
    "trousse", "plateau", "boites de rangement", "boîtes de rangement",
    "porte-savon", "porte savon", "coussin", "oreiller", "chausson",
    "chaussons", "pantoufle", "pince a linge", "pince à linge", "etendoir",
    "étendoir", "balance", "infuseur", "verre doseur", "shaker",
]
import re as _re
_DURABLE_RE = _re.compile(
    r"(?<!\w)(?:" + "|".join(_re.escape(m) for m in _DURABLE_MOTS) + r")(?!\w)",
    _re.IGNORECASE)


def _rappel_override(pid):
    """Retourne True/False si l'utilisateur a forcé un choix, sinon None."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT actif FROM stock_rappel WHERE produit_id=?", (pid,))
    r = c.fetchone()
    conn.close()
    if r is None:
        return None
    return bool(r[0])


def est_durable(nom, categorie):
    """Objet durable / acheté une fois (balai, boîtes, économe, casserole, …) ou
    revue : ne doit PAS être traité comme du stock à consommer. Détection par
    NOM (mot entier, indépendante de la catégorie) + catégorie REVUES.
    Les articles « Recharge … » sont des consommables (jamais durables)."""
    n = (nom or "").strip().lower()
    if n.startswith("recharge"):
        return False
    cat = (categorie or "").strip().upper()
    if cat == "REVUES":
        return True
    return bool(_DURABLE_RE.search(n))


def est_consommable(pid, nom, categorie):
    """Pour les RAPPELS de rachat : un durable ne déclenche jamais de rappel ;
    sinon l'override manuel (apprentissage) prime ; par défaut oui."""
    if est_durable(nom, categorie):
        return False
    ov = _rappel_override(pid)
    if ov is not None:
        return ov
    return True


def definir_rappel(pid, actif):
    """Force le rappel pour un article : actif True (me rappeler) / False (ne plus)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO stock_rappel VALUES (?,?)", (pid, 1 if actif else 0))
    conn.commit()
    conn.close()


def effacer_rappel_override(pid):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM stock_rappel WHERE produit_id=?", (pid,))
    conn.commit()
    conn.close()


def get_stock_bas(seuil=None):
    """Articles de Mon stock à racheter : quantité <= seuil (défaut paramètre
    stock_seuil_bas, 2) ET considérés comme consommables (rappel intelligent :
    un objet durable comme un balai n'est jamais proposé au rachat)."""
    if seuil is None:
        try:
            seuil = int(get_parametres().get("stock_seuil_bas", "2") or 2)
        except ValueError:
            seuil = 2
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT produit_id, nom, categorie, prix, quantite FROM mon_stock "
              "WHERE quantite > 0 AND quantite <= ? ORDER BY quantite, nom", (seuil,))
    rows = c.fetchall()
    conn.close()
    res = []
    for r in rows:
        if est_consommable(r[0], r[1], r[2]):
            res.append({"id": r[0], "nom": r[1], "categorie": r[2],
                        "prix": r[3], "qte": r[4]})
    return res


# ─────────────────────────────────────────────
# REMBOURSEMENTS (articles de mes bons à rembourser)
# ─────────────────────────────────────────────
def get_bons_mon_nom(limite=300):
    """Mes bons perso (nom == paramètre 'nom', hors créances), récents d'abord,
    avec leurs lignes et la date de livraison prévue. Pour choisir des articles
    à rembourser."""
    try:
        mon_nom = (get_parametres().get("nom", "") or "").strip().upper()
    except Exception:
        mon_nom = ""
    if not mon_nom:
        return []
    conn = get_connection()
    c = conn.cursor()
    c.execute("""SELECT id, uid, date, categorie FROM bons
                 WHERE est_creance=0 AND UPPER(TRIM(nom))=?
                 ORDER BY id DESC LIMIT ?""", (mon_nom, limite))
    bons = c.fetchall()
    res = []
    for bid, uid, date_bon, categorie in bons:
        c.execute("SELECT produit_id, designation, prix, quantite "
                  "FROM lignes_bon WHERE bon_id=?", (bid,))
        lignes = [{"id": r[0], "nom": r[1], "prix": float(r[2] or 0), "qte": int(r[3] or 0)}
                  for r in c.fetchall()]
        # date de livraison : réception liée si elle existe, sinon calcul
        c.execute("SELECT date_prevue FROM receptions_attendues WHERE source_uid=? LIMIT 1",
                  (uid or f"legacy-{bid}",))
        rr = c.fetchone()
        if rr:
            date_liv = rr[0]
        else:
            import datetime as _dt
            date_liv = None
            for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                try:
                    base = _dt.datetime.strptime((date_bon or "").strip(), fmt).date()
                    date_liv = _date_livraison_prevue(categorie, base).strftime("%Y-%m-%d")
                    break
                except Exception:
                    date_liv = None
            if not date_liv:
                date_liv = _date_livraison_prevue(categorie).strftime("%Y-%m-%d")
        res.append({"id": bid, "uid": uid, "date": date_bon, "categorie": categorie,
                    "date_livraison": date_liv, "lignes": lignes})
    conn.close()
    return res


def ajouter_remboursement(articles):
    """articles : liste de dicts {produit_id|id, nom, categorie, prix, quantite,
    date_commande, date_livraison, source_uid}."""
    import datetime as _dt
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    c = conn.cursor()
    for a in articles:
        pid = a.get("produit_id", a.get("id"))
        q = int(a.get("quantite", a.get("qte", 0)) or 0)
        if q <= 0:
            continue
        c.execute("""INSERT INTO remboursements
            (produit_id, nom, categorie, prix, quantite, date_commande,
             date_livraison, source_uid, statut, date_ajout, date_remboursement)
            VALUES (?,?,?,?,?,?,?,?, 'a_rembourser', ?, '')""",
            (pid, a.get("nom", ""), a.get("categorie", ""), float(a.get("prix", 0) or 0),
             q, a.get("date_commande", ""), a.get("date_livraison", ""),
             a.get("source_uid", ""), now))
    conn.commit()
    conn.close()


def get_remboursements(statut=None):
    """Liste de dicts. statut : 'a_rembourser', 'rembourse', ou None (tous)."""
    conn = get_connection()
    c = conn.cursor()
    base = ("SELECT id, produit_id, nom, categorie, prix, quantite, date_commande, "
            "date_livraison, source_uid, statut, date_ajout, date_remboursement "
            "FROM remboursements")
    if statut:
        c.execute(base + " WHERE statut=? ORDER BY id DESC", (statut,))
    else:
        c.execute(base + " ORDER BY statut, id DESC")
    rows = c.fetchall()
    conn.close()
    cols = ["id", "produit_id", "nom", "categorie", "prix", "quantite",
            "date_commande", "date_livraison", "source_uid", "statut",
            "date_ajout", "date_remboursement"]
    return [dict(zip(cols, r)) for r in rows]


def valider_remboursement(remb_id):
    import datetime as _dt
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE remboursements SET statut='rembourse', date_remboursement=? "
              "WHERE id=?", (_dt.date.today().strftime("%Y-%m-%d"), remb_id))
    conn.commit()
    conn.close()


def supprimer_remboursement(remb_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM remboursements WHERE id=?", (remb_id,))
    conn.commit()
    conn.close()


def remboursements_a_faire_count():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM remboursements WHERE statut='a_rembourser'")
    n = c.fetchone()[0]
    conn.close()
    return n


# ─────────────────────────────────────────────
# Liste hygiène mensuelle (personnalisable)
# ─────────────────────────────────────────────
def get_hygiene_liste():
    """Retourne la liste hygiène jointe au catalogue, triée par ordre.
    Chaque élément : {id, nom, categorie, prix, groupe, qte_par_pers}."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""SELECT h.produit_id, p.nom, p.categorie, p.prix, h.groupe,
                        h.qte_par_pers, h.ordre
                 FROM hygiene_liste h
                 JOIN produits p ON p.id = h.produit_id
                 ORDER BY h.groupe DESC, h.ordre""")
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "nom": r[1], "categorie": r[2], "prix": r[3],
             "groupe": r[4], "qte_par_pers": r[5]} for r in rows]

def hygiene_definir_qte(produit_id, qte_par_pers):
    """Change la quantité par personne d'un produit ; <=0 supprime la ligne."""
    conn = get_connection()
    c = conn.cursor()
    if qte_par_pers is None or int(qte_par_pers) <= 0:
        c.execute("DELETE FROM hygiene_liste WHERE produit_id=?", (produit_id,))
    else:
        c.execute("UPDATE hygiene_liste SET qte_par_pers=? WHERE produit_id=?",
                  (int(qte_par_pers), produit_id))
    conn.commit()
    conn.close()

def hygiene_supprimer(produit_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM hygiene_liste WHERE produit_id=?", (produit_id,))
    conn.commit()
    conn.close()

def hygiene_ajouter(produit_id, groupe, qte_par_pers):
    """Ajoute (ou met à jour) un produit dans la liste hygiène."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COALESCE(MAX(ordre),0)+1 FROM hygiene_liste")
    ordre = c.fetchone()[0]
    c.execute("SELECT produit_id FROM hygiene_liste WHERE produit_id=?", (produit_id,))
    if c.fetchone():
        c.execute("UPDATE hygiene_liste SET groupe=?, qte_par_pers=? WHERE produit_id=?",
                  (groupe, int(qte_par_pers), produit_id))
    else:
        c.execute("INSERT INTO hygiene_liste VALUES (?,?,?,?)",
                  (produit_id, groupe, int(qte_par_pers), ordre))
    conn.commit()
    conn.close()
