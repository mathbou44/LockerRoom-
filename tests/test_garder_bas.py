"""20 nov 2026 (Mathieu : « dans Achetees et Collection, un indice : le joueur est a chier en ce moment, vends-la pas ») : une
carte pas vendue et pas sur eBay d'un joueur cle au marche bas (verifie) porte « garder_bas » ; une carte sur eBay ou vendue,
jamais ; un joueur normal, jamais."""
import os, sys, tempfile
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom, marche_cles as mc
mc.ecrire({"v": mc.VERSION, "verif": {"actif": True, "seuil": 0.2}, "cles": {"Sidney Crosby": {"score": 95}, "Connor Mcdavid": {"score": 96}},
           "etats": {"Sidney Crosby": {"indice": 0.7, "n": 30, "ecart_pct": -30}, "Connor Mcdavid": {"indice": 1.02, "n": 40, "ecart_pct": 2}}})
a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
i1 = a.carte_sauver({"joueur": "Sidney Crosby", "annee": "2005-06", "set_nom": "Young Guns", "numero": "201", "cout": 500, "sport": "hockey"})
i2 = a.carte_sauver({"joueur": "Connor McDavid", "annee": "2015-16", "set_nom": "Young Guns", "numero": "201", "cout": 500, "sport": "hockey"})
L = a.inventaire_liste({})
L = L if isinstance(L, list) else L.get("cartes")
g = {x["joueur"]: x.get("garder_bas") for x in L}
assert g["Sidney Crosby"] == {"ecart_pct": -30} and not g["Connor McDavid"], g
print("OK test_garder_bas")
