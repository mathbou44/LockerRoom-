"""8 nov 2026 (Mathieu : « le 25 $ de ma Anders Lee c'est MA carte... si aucun autre comp, mettre 10 % moins cher que la
mediane des memes cartes affichees ») : le prix suggere a la vente ignore tes achats ; sans vente : annonces - 10 %."""
import os, sys, tempfile
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom, vendues, ebay_compte, forfaits

api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "p.db"))
forfaits.verifier = lambda *a, **k: None
forfaits.compter = lambda *a, **k: None
T = "2024-25 Upper Deck Clear Cut High Gloss Auto Anders Lee /10 #CC-LE"
j = lambda k: (datetime.now() - timedelta(days=k)).strftime("%Y-%m-%d")
c = api._db(); c.execute(api._SQL_ACHATS)
c.execute("INSERT INTO achats_ebay (item_id, n, titre, cout, devise, date, carte_id) VALUES ('123456789012', 1, ?, 25.32, 'CAD', ?, NULL)", (T, j(80)))
c.commit(); c.close()
ma_vente = {"titre": T, "prix": 25.32, "le": j(80), "url": "https://www.ebay.com/itm/123456789012"}
vendues.memes = lambda t, **k: {"ventes": [dict(ma_vente)], "mediane": None}
ebay_compte.rechercher = lambda *a, **k: [{"item_id": "1", "titre": T, "prix_cad": 60.0, "port_cad": 0, "url": "u1"},
                                          {"item_id": "2", "titre": T, "prix_cad": 80.0, "port_cad": 0, "url": "u2"}]
r = api.annonce_preparer({"titre": T})
assert r["ok"] and not r["vendues"] and r["vendu"] is None, (r["vendues"], r["vendu"])          # mon achat ne compte pas
assert r["source_prix"] == "annonces" and r["prix"]["mediane"] == 63.0 and r["prix"]["marche"] == 65.0, r["prix"]   # 70 - 10 %
# une vraie vente d'un autre acheteur : elle compte
vendues.memes = lambda t, **k: {"ventes": [dict(ma_vente), {"titre": T, "prix": 55.0, "le": j(10), "url": "https://www.ebay.com/itm/999999999999"}], "mediane": None}
r = api.annonce_preparer({"titre": T})
assert len(r["vendues"]) == 1 and r["vendues"][0]["prix"] == 55.0 and r["prix"]["marche"] == 55.0, (r["vendues"], r["prix"])
print("PRIX VENTE OK")
