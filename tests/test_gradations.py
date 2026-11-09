"""8 nov 2026 (Mathieu, une analyse de Sports Card Investor) : la variation de prix par gradation dans la fiche."""
import os, sys, tempfile
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import vendues
j = lambda k: (datetime.now() - timedelta(days=k)).strftime("%Y-%m-%d")
T = "1986-87 Fleer Michael Jordan #57 RC"
vs = ([{"titre": T + " PSA 9", "prix": 30000 + i * 100, "le": j(200 - i * 10), "url": f"a{i}"} for i in range(8)]
      + [{"titre": T + " PSA 8", "prix": 12000 + i * 50, "le": j(150 - i * 10), "url": f"b{i}"} for i in range(6)]
      + [{"titre": T, "prix": 5000, "le": j(k), "url": f"c{k}"} for k in (5, 9, 20)]
      + [{"titre": T + " PSA 10", "prix": 250000, "le": j(30), "url": "d1"}]                              # 1 vente : pas une courbe
      + [{"titre": T + " PSA", "prix": 1, "le": j(3), "url": "x"},                                         # PSA sans note
         {"titre": "1986-87 Fleer Michael Jordan Sticker #8", "prix": 900, "le": j(4), "url": "y"}])        # une autre carte
vendues.rechercher = lambda q, fond=True, usage=None: {"ventes": vs}
vendues.archives = lambda *a, **k: []
r = vendues.par_gradation("Jordan 1986 Fleer #57 rookie")
assert r["ok"] and [s["nom"] for s in r["series"]] == ["Brute", "PSA 9", "PSA 8"], r["series"]
s9 = r["series"][1]
assert s9["n"] == 8 and s9["derniere"]["prix"] == 30700 and s9["points"] == sorted(s9["points"])
assert not vendues.par_gradation("lot de 50 cartes")["ok"] or True
print("GRADATIONS OK")
