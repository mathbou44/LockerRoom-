"""17 nov 2026 : « Grader ? » (grader.py) : le verdict, la chance d'un 10 (pre-grade ou marche) et le seuil."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timedelta
import grader as g
j = lambda n: (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d")
S = [{"cle": "brute", "points": [[j(i), 100] for i in range(5, 40, 5)]}, {"cle": "psa 10", "points": [[j(i), 600] for i in range(5, 40, 8)]},
     {"cle": "psa 9", "points": [[j(i), 180] for i in range(5, 40, 6)]}]
r = g.calculer(S)
assert r["ok"] and r["verdict"] == "oui" and r["multiple"] == 6.0 and r["source"] == "marche" and 0 <= r["seuil_10"] <= 1
assert g.calculer(S, note=9.5)["gain"] > r["gain"] > g.calculer(S, note=7)["gain"]
assert g.calculer(S, note=7)["verdict"] == "non"
# une carte ou meme un 10 ne paie pas les frais
S2 = [{"cle": "brute", "points": [[j(i), 20] for i in range(5, 40, 5)]}, {"cle": "psa 10", "points": [[j(i), 45] for i in range(5, 40, 8)]}]
r2 = g.calculer(S2)
assert r2["verdict"] == "non" and r2["seuil_10"] is None
assert not g.calculer(S[:1])["ok"]                                  # sans ventes PSA 10 : rien
assert g.gradee("Lane Hutson PSA 10") and not g.gradee("Lane Hutson Young Guns #201")
print("GRADER OK")
