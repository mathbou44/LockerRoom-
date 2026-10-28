"""29 oct 2026 - « pourquoi le meilleur joueur change avec le nombre de boites ? » : le classement acheteur d'un break ne
depend pas du nombre de boites (python tests/test_break_ordre.py). Aucun appel reseau."""
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
ordres = []
for b in (1, 3, 6, 16, 32):
    r = a.analyse_break({"produit_id": pid, "boites": b, "acheteur": True})
    assert r["ok"], r
    ordres.append([x["nom"] for x in r["joueurs"][:10]])
    eq = [x["nom"] for x in sorted(r["places"], key=lambda x: -x["score"])[:5]]
    if b == 1:
        eq1 = eq
    else:
        assert eq == eq1, (b, eq, eq1)
assert all(o == ordres[0] for o in ordres), ordres
print("BREAK ORDRE OK")
