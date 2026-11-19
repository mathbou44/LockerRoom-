"""19 nov 2026 : la vitrine du Radar Pro : ce que le chasseur balaie, seulement les cartes A et A+, 30 $ et plus, sans valeur."""
import os, sys, tempfile, time
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import vitrine
fin = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
fini = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
A = [{"item_id": "1", "titre": "2015-16 Upper Deck Young Guns Connor McDavid #201 PSA 10", "prix_cad": 2400, "port_cad": 0, "encan": True, "fin": fin},
     {"item_id": "2", "titre": "2023-24 Upper Deck Series 1 Connor McDavid #1 base", "prix_cad": 40, "port_cad": 5},
     {"item_id": "3", "titre": "2023-24 SP Authentic Future Watch Auto Connor Bedard /999", "prix_cad": 12, "port_cad": 2},
     {"item_id": "4", "titre": "2005-06 The Cup Sidney Crosby Rookie Patch Auto RPA /99", "prix_cad": 9000, "port_cad": 0},
     {"item_id": "5", "titre": "2015-16 Upper Deck Young Guns Connor McDavid #201 PSA 10", "prix_cad": 2300, "encan": True, "fin": fini}]
n = vitrine.ajouter(A)
L = vitrine.liste()
ids = [x["item_id"] for x in L]
assert "2" not in ids and "3" not in ids, ids            # une base ; une carte a 14 $
assert "5" not in ids, ids                               # un encan fini
assert "1" in ids and "4" in ids, ids
assert all(x["score"] >= 86 and x["a_la_une"] for x in L)
# deja vue : le prix se met a jour, sans la renoter
vitrine.ajouter([{"item_id": "1", "titre": A[0]["titre"], "prix_cad": 2500, "port_cad": 0, "encan": True, "fin": fin, "mises": 9}])
x1 = next(x for x in vitrine.liste() if x["item_id"] == "1")
assert x1["total"] == 2500 and x1["mises"] == 9
# son budget
assert [x["item_id"] for x in vitrine.liste(prix_max=3000)] == ["1"] or "4" not in [x["item_id"] for x in vitrine.liste(prix_max=3000)]
vitrine._ecrire_si_besoin(forcer=True)
vitrine._ETAT["pool"] = None
assert {x["item_id"] for x in vitrine.liste()} == {"1", "4"}
print("OK test_vitrine", vitrine.etat())
