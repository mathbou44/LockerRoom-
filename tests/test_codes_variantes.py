"""23 nov 2026 (Mathieu, O-Pee-Chee Platinum #BA-AK : « Erreur, 2x opc et c'est une blue rainbow. Sert-toi du code BA ») :
- le titre ne repete plus la marque quand le set la contient (« O-Pee-Chee O-Pee-Chee Platinum ») ;
- le code de la carte donne le parallele quand la carte ne l'ecrit pas, d'apres nos ventes (codes_variantes.json), par saison ;
- une autre couleur lue sur la carte n'est jamais ecrasee : le champ passe « a verifier »."""
import json, os, sys
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ICI)
import annonces, cartes_match as cm, ebay_csv

lu = {"annee": "2023-24", "marque": "O-Pee-Chee", "set_nom": "O-Pee-Chee Platinum", "parallele": "Autographs", "joueur": "Anze Kopitar", "numero": "BA-AK"}
# 1. le titre : la marque une seule fois (les deux fabriques de titres)
assert annonces.titre_optimise(lu) == "2023-24 O-Pee-Chee Platinum Autographs Anze Kopitar #BA-AK", annonces.titre_optimise(lu)
assert "O-Pee-Chee O-Pee-Chee" not in ebay_csv.titre_annonce(lu)
# ... sans rien changer aux autres titres
assert annonces.titre_optimise({"annee": "2025-26", "marque": "Upper Deck", "set_nom": "Series 2", "parallele": "Young Guns Outburst Silver", "joueur": "Danila Yurov",
                                "numero": "452", "recrue": 1}) == "2025-26 Upper Deck Series 2 Young Guns Outburst Silver Danila Yurov #452 RC"
assert annonces.titre_optimise({"annee": "2025-26", "marque": "Upper Deck", "set_nom": "SP Authentic", "parallele": "Future Watch Autograph", "joueur": "Devin Kaplan",
                                "numero": "164", "recrue": 1, "tirage": 999, "auto": 1}) == "2025-26 Upper Deck SP Authentic Future Watch Autograph Devin Kaplan /999 #164 RC"
assert annonces.titre_optimise({"annee": "2024-25", "marque": "Upper Deck", "set_nom": "Upper Deck Series 1", "parallele": "Young Guns", "joueur": "Macklin Celebrini",
                                "numero": "201", "recrue": 1}) == "2024-25 Upper Deck Series 1 Young Guns Macklin Celebrini #201 RC"
# 2. le code dit le parallele
ch, av = cm.completer_par_code(lu, ["parallele"])
assert ch["parallele"] == "Blue Rainbow" and ch["auto"] is True and av == [], (ch, av)
assert annonces.titre_optimise(ch) == "2023-24 O-Pee-Chee Platinum Blue Rainbow Anze Kopitar Auto #BA-AK", annonces.titre_optimise(ch)
assert lu["parallele"] == "Autographs"                                         # la fiche recue n'est pas modifiee
assert cm.completer_par_code(dict(lu, parallele=""), [])[0]["parallele"] == "Blue Rainbow"
assert cm.completer_par_code(dict(lu, parallele="Blue Rainbow Autographs"), []) == (dict(lu, parallele="Blue Rainbow Autographs"), [])   # deja lu : rien a faire
# par saison : RA = Red Rainbow en 2025-26, « Rookie Autographs » avant ; BA sans vente en 2025-26 : on ne dit rien
assert cm.variante_du_code("O-Pee-Chee Platinum", "RA-PD", "2025-26") == "Red Rainbow"
assert cm.variante_du_code("O-Pee-Chee Platinum", "RA-WG", "2023-24") is None
assert cm.variante_du_code("O-Pee-Chee Platinum", "BA-AK", "2025-26") is None
assert cm.variante_du_code("O-Pee-Chee Platinum", "BA-AK", "2024") == "Blue Rainbow"       # une annee seule = la saison qui commence
# un autre produit, un numero sans code, une fiche vide : rien
for prod, num, an in (("Upper Deck SP Authentic", "BA-AK", "2023-24"), ("O-Pee-Chee Platinum", "451", "2023-24"), ("O-Pee-Chee Platinum", "BA-AK", ""), ("", "BA-AK", "2023-24")):
    assert cm.variante_du_code(prod, num, an) is None, (prod, num, an)
assert cm.completer_par_code({}, None) == ({}, [])
# 3. une AUTRE couleur lue sur la carte : jamais ecrasee, mais a verifier
ch, av = cm.completer_par_code(dict(lu, parallele="Red Prism"), [])
assert ch["parallele"] == "Red Prism" and av == ["parallele"] and "auto" not in ch
# 4. la table vient des ventes : chaque ligne a ses preuves (20 ventes par saison, 85 % des titres)
T = json.load(open(os.path.join(ICI, "codes_variantes.json"), encoding="utf-8"))
assert T["ventes"] > 1_000_000 and {(c["produit"], c["prefixe"], c["variante"]) for c in T["codes"]} >= {("o-pee-chee platinum", "BA", "Blue Rainbow")}
for c in T["codes"]:
    assert c["part"] >= 0.85 and all(n >= 20 and ok / n >= 0.85 for ok, n in c["saisons"].values()), c
# 5. les deux lectures (une carte, un lot) passent par la : sinon la correction ne sert a rien
src = open(os.path.join(ICI, "lockerroom.py"), encoding="utf-8").read()
assert src.count("cartes_match.completer_par_code(") == 2
print("OK test_codes_variantes")
