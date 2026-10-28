"""Indice SlabCoach (methode v1) : python tests/test_indice.py. Aucun appel reseau."""
import os
import sys

ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ICI)
import indice  # noqa: E402

# carte sans donnees -> rien
assert indice.carte({}) is None

# sans PSA : Elan 60 %, Liquidite 40 %
r = indice.carte({"pct": 0, "n_7j": 20, "n": 25})
assert r["elan"] == 50 and r["liquidite"] == 100 and r["rarete"] is None and not r["avec_psa"], r
assert r["score"] == round(50 * .6 + 100 * .4) == 70 and r["confiance"] == "elevee" and r["methode"] == "v1", r

# bornes : +200 % -> elan 100 ; -90 % -> 0 ; jamais hors 0..100
assert indice.carte({"pct": 200, "n_7j": 0})["elan"] == 100
r = indice.carte({"pct": -90, "n_7j": 0, "n": 3})
assert r["elan"] == 0 and r["liquidite"] == 0 and r["score"] == 0 and r["confiance"] == "faible", r
for pct in (-500, -10, 0, 7, 500):
    for v in (0, 1, 5, 50, 5000):
        s = indice.carte({"pct": pct, "n_7j": v})["score"]
        assert 0 <= s <= 100, (pct, v, s)

# avec PSA : 45 / 30 / 25 ; rarete = 100 - 4 x croissance
r = indice.carte({"pct": 20, "n_7j": 20, "n": 10, "psa": {"croissance_pct": 5}})
assert r["rarete"] == 80 and r["avec_psa"] and r["confiance"] == "moyenne", r
assert r["score"] == round(70 * .45 + 100 * .30 + 80 * .25), r
assert indice.carte({"pct": 0, "n_7j": 1, "psa": {"croissance_pct": 40}})["rarete"] == 0
assert indice.carte({"pct": 0, "n_7j": 1, "psa": {"croissance_pct": -3}})["rarete"] == 100

# liquidite a partir des points de ventes (pas de n_7j) : 8 ventes sur 4 semaines = 2 / sem
pts = [["2026-09-01", 10], ["2026-09-15", 11], ["2026-09-29", 12]]
r = indice.carte({"pct": 0, "n": 8, "points": pts})
assert r["ventes_sem"] == 2.0 and r["liquidite"] == 36, r

# marche : poids racine(n), variations bornees a +-60 %
m = indice.marche([{"pct": 10, "n": 100}, {"pct": -10, "n": 1}, {"pct": 1000, "n": 4}, {"pct": None, "n": 50}])
attendu = round((10 * 10 + -10 * 1 + 60 * 2) / (10 + 1 + 2), 1)
assert m["variation"] == attendu and m["n_cartes"] == 3 and m["hausse_pct"] == 67 and m["n_ventes"] == 105, m
assert "psa" not in m and indice.marche([]) is None and indice.marche([{"pct": None}]) is None

# marche avec PSA : croissance = nouvelles / population d'il y a 30 jours
m = indice.marche([{"pct": 5, "n": 9}], [{"pop": 1000, "nouvelles_30j": 200, "gem_pct": 40},
                                          {"pop": 300, "nouvelles_30j": 0, "gem_pct": 20}, {"pop": 50}, None])
assert m["psa"] == {"fiches": 2, "nouvelles_30j": 200, "croissance_pct": round(100 * 200 / 1100, 1), "gem_moyen": 30}, m
print("INDICE OK")
