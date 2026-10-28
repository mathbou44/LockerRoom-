"""29 oct 2026 - classement acheteur d'un break (python tests/test_break_ordre.py). Aucun appel reseau.
 - « Pour ton argent » (hits par dollar, sur la part exacte de la place) : le meme ordre avec 1, 3, 6, 16 ou 32 boites.
 - « Vaut ta place » (le score par defaut) : la chance d'au moins une carte qui vaut a elle seule le prix de la place ;
   elle peut bouger avec le nombre de boites (la place coute plus cher, la barre monte) : c'est voulu et explique."""
import math
import os
import sys
import tempfile

os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import catalogue  # noqa: E402
import forfaits  # noqa: E402
import lockerroom  # noqa: E402

forfaits.produit_permis = lambda pid: True
a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "o.db"))
pid = next((p["id"] for p in catalogue.liste()), None)
assert pid, "aucun produit au catalogue"


def argent(x):
    p = min(0.999999, ((x.get("chances") or {}).get("hit") or {}).get("p") or 0)
    return -math.log(1 - p) / x["part_brute"] if x.get("part_brute") else 0


ordres = []
for b in (1, 3, 6, 16, 32):
    r = a.analyse_break({"produit_id": pid, "boites": b, "acheteur": True})
    assert r["ok"], r
    j = sorted(r["joueurs"], key=lambda x: -argent(x))
    ordres.append([x["nom"] for x in j[:10]])
    best = max(r["joueurs"], key=lambda x: x["p_carte_prix"])
    assert max(x["score"] for x in r["joueurs"]) == 100 and best["score"] == 100
    assert all(0 <= x["p_carte_prix"] <= 1 for x in r["joueurs"])
assert all(o == ordres[0] for o in ordres), ordres
print("BREAK ORDRE OK")
