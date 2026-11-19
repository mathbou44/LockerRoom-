"""19 nov 2026 : le bouton « Encheres » relit la mise de chaque encan du Radar ; une mise trop haute sort des deals."""
import os, sys, tempfile
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import deals, lockerroom, ebay_compte
fin = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
d = deals.lire()
d["deals"] = [{"item_id": "A1", "titre": "x", "encan": True, "fin": fin, "total": 50, "valeur": 200, "port": 5},
              {"item_id": "A2", "titre": "y", "encan": True, "fin": fin, "total": 50, "valeur": 200, "port": 5},
              {"item_id": "F1", "titre": "z", "encan": False, "total": 50, "valeur": 200}]
deals._ecrire(d)
prix = {"A1": 60.0, "A2": 190.0}
ebay_compte.article = lambda iid, frais=False: {"item_id": iid, "prix_cad": prix[iid], "port_cad": 5.0, "mises": 3, "fin": fin, "encan": True}
api = lockerroom.Api()
api._est_admin = lambda *a, **k: True
r = api.deals_encans_rafraichir()
assert r["ok"] and r["encans"] == 2 and r["lus"] == 2 and r["retires"] == 1, r
L = {x["item_id"]: x for x in deals.lire()["deals"]}
assert L["A1"]["total"] == 65.0 and "A2" not in L and "F1" in L, L
print("OK test_encans_refresh")
