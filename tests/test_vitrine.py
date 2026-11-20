"""19 nov 2026 : la vitrine du Radar Pro : ce que le chasseur balaie, seulement les cartes A- et mieux, 30 $ et plus.
20 nov 2026 : et liquides (5 ventes de la meme carte en 60 jours), pas plus de 10 % au-dessus de ce qu'elles se vendent ;
la mediane et le compte ne sortent jamais."""
import os, sys, tempfile, time
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import vitrine
import base_ventes
import liquidite
from datetime import date
MCD = "2015-16 Upper Deck Young Guns Connor McDavid #201 PSA 10"
RPA = "2005-06 The Cup Sidney Crosby Rookie Patch Auto RPA /99"
c = base_ventes._cx()
lignes = []
for i in range(6):
    le = (date.today() - timedelta(days=3 + 7 * i)).isoformat()
    lignes.append(("q1", "m%d" % i, MCD, 2400 + 10 * i, le, None, None, 0, le))
    lignes.append(("q2", "r%d" % i, RPA, 9500, le, None, None, 0, le))
    lignes.append(("q3", "s%d" % i, MCD.replace("PSA 10", "SGC 10"), 900, le, None, None, 0, le))   # une autre compagnie
c.executemany("INSERT INTO ventes VALUES (?,?,?,?,?,?,?,?,?)", lignes)
c.commit(); c.close()
assert liquidite.signaux([MCD]) is None                  # l'index n'est pas encore bati : on attend (pas rejete)
time.sleep(0.5)
while liquidite._ETAT["en_cours"]:
    time.sleep(0.05)
liquidite.rafraichir(pause=0)
s_ = liquidite.signaux([MCD, RPA, MCD.replace("PSA 10", "SGC 10")])
assert s_[MCD][0] == 6 and 2400 <= s_[MCD][1] <= 2450, s_
assert s_[MCD.replace("PSA 10", "SGC 10")][1] == 900, s_
assert liquidite.passe(6, 2400, 2640) and not liquidite.passe(6, 2400, 2700) and not liquidite.passe(4, 2400, 1000)
fin = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
fini = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
A = [{"item_id": "1", "titre": "2015-16 Upper Deck Young Guns Connor McDavid #201 PSA 10", "prix_cad": 2400, "port_cad": 0, "encan": True, "fin": fin},
     {"item_id": "2", "titre": "2023-24 Upper Deck Series 1 Connor McDavid #1 base", "prix_cad": 40, "port_cad": 5},
     {"item_id": "3", "titre": "2023-24 SP Authentic Future Watch Auto Connor Bedard /999", "prix_cad": 12, "port_cad": 2},
     {"item_id": "4", "titre": "2005-06 The Cup Sidney Crosby Rookie Patch Auto RPA /99", "prix_cad": 9000, "port_cad": 0},
     {"item_id": "5", "titre": "2015-16 Upper Deck Young Guns Connor McDavid #201 PSA 10", "prix_cad": 2300, "encan": True, "fin": fini},
     {"item_id": "6", "titre": "2015-16 Upper Deck Young Guns Connor McDavid #201 PSA 10", "prix_cad": 3500, "port_cad": 0},   # trop cher
     {"item_id": "7", "titre": "2016-17 Upper Deck Young Guns Auston Matthews #201 PSA 10", "prix_cad": 900, "port_cad": 0}]   # pas de ventes
n = vitrine.ajouter(A)
L = vitrine.liste()
ids = [x["item_id"] for x in L]
assert "2" not in ids and "3" not in ids, ids            # une base ; une carte a 14 $
assert "5" not in ids, ids                               # un encan fini
assert "6" not in ids and "7" not in ids, ids            # 45 % au-dessus de ce qu'elle se vend ; aucune vente archivee
assert "1" in ids and "4" in ids, ids
assert all(x["score"] >= 82 and x["a_la_une"] and "_med" not in x and "_liq" not in x for x in L)
# deja vue : le prix se met a jour, sans la renoter
vitrine.ajouter([{"item_id": "1", "titre": A[0]["titre"], "prix_cad": 2500, "port_cad": 0, "encan": True, "fin": fin, "mises": 9}])
x1 = next(x for x in vitrine.liste() if x["item_id"] == "1")
assert x1["total"] == 2500 and x1["mises"] == 9
# l'encan monte au-dessus de la limite : il sort de la liste (et revient s'il redescend, ce qui n'arrive pas)
vitrine.ajouter([{"item_id": "1", "titre": A[0]["titre"], "prix_cad": 2900, "port_cad": 0, "encan": True, "fin": fin, "mises": 12}])
assert "1" not in [x["item_id"] for x in vitrine.liste()]
vitrine.ajouter([{"item_id": "1", "titre": A[0]["titre"], "prix_cad": 2500, "port_cad": 0, "encan": True, "fin": fin, "mises": 9}])
# son budget
assert [x["item_id"] for x in vitrine.liste(prix_max=3000)] == ["1"] or "4" not in [x["item_id"] for x in vitrine.liste(prix_max=3000)]
vitrine._ecrire_si_besoin(forcer=True)
vitrine._ETAT["pool"] = None
assert {x["item_id"] for x in vitrine.liste()} == {"1", "4"}
print("OK test_vitrine", vitrine.etat())
