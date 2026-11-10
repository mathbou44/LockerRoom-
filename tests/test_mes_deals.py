"""10 nov 2026 : « Mes deals » = les annonces de la MEME carte au prix cible de l'utilisateur ou moins (son prix decide)."""
import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom
import ebay_compte
api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "m.db"))
T = "2024-25 Upper Deck Young Guns Will Smith #230"
ebay_compte.rechercher = lambda q, **k: [
    {"item_id": "1", "titre": T, "prix_cad": 40, "port_cad": 2, "url": "u1", "encan": bool(k.get("encheres"))},
    {"item_id": "2", "titre": T, "prix_cad": 70, "port_cad": 0, "url": "u2"},
    {"item_id": "3", "titre": "2024-25 Upper Deck Will Smith base #12", "prix_cad": 1, "port_cad": 0, "url": "u3"}]
assert api.alerte_ajouter("Will Smith Young Guns", 60)["ok"]
r = api.mes_deals()
assert r["ok"] and [x["item_id"] for x in r["deals"]] == ["1"], r["deals"]       # sous 60 $, la meme carte seulement
assert r["deals"][0]["sous_pct"] == 30 and r["cibles"][0]["n"] == 1
print("OK mes deals")
# l'accueil d'un utilisateur (sans les deals de l'admin) montre « Mes deals » dans le carrousel
lockerroom.ebay_prix_actif = lambda api=None: False
a = api.acheteur_accueil()
assert [d["item_id"] for d in a["deals"]] == ["1"] and a["deals"][0]["rabais"] == 30 and a["gain_deals"] == 0, a["deals"]
print("OK accueil mes deals")
