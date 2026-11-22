"""22 nov 2026 (Mathieu : « une pastille verte Sell sur ce qui est dans l'inventaire, pas encore en vente ; dans les notifications aussi ») :
une carte pas sur eBay d'un joueur de « A vendre » porte a_vendre ; la notification « Temps de vendre » part une fois."""
import os, sys, tempfile
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes; comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom, alarmes, marche
lockerroom._VEN_NOMS.update({"le": 9e18, "v": {"sidney crosby": {"ecart_pct": 22, "courbe": [1,1.1,1.2,1.3,1.4], "haut_depuis_j": 120}}})
a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
a.carte_sauver({"joueur": "Sidney Crosby", "annee": "2005-06", "set_nom": "Young Guns", "numero": "201", "cout": 500, "sport": "hockey"})
a.carte_sauver({"joueur": "Connor McDavid", "annee": "2015-16", "set_nom": "Young Guns", "numero": "201", "cout": 500, "sport": "hockey"})
L = a.inventaire_liste({}); L = L if isinstance(L, list) else L["cartes"]
g = {x["joueur"]: x.get("a_vendre") for x in L}
assert g["Sidney Crosby"]["ecart_pct"] == 22 and not g["Connor McDavid"], g
assert alarmes.a_vendre(a, alarmes._lire()) == 1
n = a.alertes_liste()["notifications"]
assert any(x.get("sorte") == "a_vendre" and x.get("sujet", "").startswith("Sidney Crosby") for x in n), n
print("OK a_vendre")
