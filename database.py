import sys
import sqlite3, os

def _app_data_dir():
    """Dossier données utilisateur — fonctionne en .py ET en .exe PyInstaller."""
    if getattr(sys, "frozen", False):
        # Mode .exe : données dans %APPDATA%/CantineApp
        base = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "CantineApp")
    else:
        # Mode script : données à côté du .py
        base = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(base, exist_ok=True)
    return base

DB_PATH = os.path.join(_app_data_dir(), "cantine.db")

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
        id TEXT PRIMARY KEY, nom TEXT, categorie TEXT, prix REAL, qte_max INTEGER, actif TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS parametres (cle TEXT PRIMARY KEY, valeur TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS bons (
        id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, categorie TEXT,
        nom TEXT, prenom TEXT, ecrou TEXT, batiment TEXT, cellule TEXT,
        total REAL, user_type TEXT DEFAULT 'invite')""")
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
    # Dépenses fixes par défaut
    for fid, flbl, fmnt in [("tv","Télévision",8.0),("frigo","Frigo",10.0),("telephone","Téléphone",20.0)]:
        c.execute("INSERT OR IGNORE INTO depenses_fixes VALUES (?,?,?,1)", (fid, flbl, fmnt))
    try:
        c.execute("ALTER TABLE bons ADD COLUMN user_type TEXT DEFAULT 'invite'")
    except: pass
    # Comptes par défaut
    c.execute("INSERT OR IGNORE INTO utilisateurs VALUES (1,'yoann','1234','yoann')")
    c.execute("INSERT OR IGNORE INTO utilisateurs VALUES (2,'admin','admin','admin')")
    # Produits
    c.execute("SELECT COUNT(*) FROM produits")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO produits VALUES (?,?,?,?,?,?)", PRODUITS_INITIAUX)
    # Paramètres Yoann
    defaults = [("nom","LUTZ"),("prenom","Yoann"),("ecrou","9283"),
                ("batiment","C"),("cellule","323"),("signature_path","")]
    for k, v in defaults:
        c.execute("INSERT OR IGNORE INTO parametres VALUES (?,?)", (k, v))
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

def update_produit(prod_id, nom, prix, qte_max, actif):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE produits SET nom=?, prix=?, qte_max=?, actif=? WHERE id=?", (nom, prix, qte_max, actif, prod_id))
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

def sauvegarder_bon(categorie, nom, prenom, ecrou, batiment, cellule, lignes, total, date_str, user_type="invite"):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO bons (date,categorie,nom,prenom,ecrou,batiment,cellule,total,user_type) VALUES (?,?,?,?,?,?,?,?,?)",
              (date_str, categorie, nom, prenom, ecrou, batiment, cellule, total, user_type))
    bon_id = c.lastrowid
    for l in lignes:
        c.execute("INSERT INTO lignes_bon (bon_id,produit_id,designation,prix,quantite,total_ligne) VALUES (?,?,?,?,?,?)",
                  (bon_id, l['id'], l['nom'], l['prix'], l['qte'], l['total']))
    conn.commit()
    conn.close()
    return bon_id

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
