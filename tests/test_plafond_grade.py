"""19 nov 2026 (Mathieu : « PSA c'est A+, TAG et Beckett A, SGC et CGC B+, le reste B ») : A+ est reserve a PSA ; toute
autre compagnie au plus A (la regle complete, mesuree, baissait les profits : le prix escompte deja la compagnie). Une carte
non gradee ne change pas."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("LOCKERROOM_DONNEES", tempfile.mkdtemp())
import score_slab as s, bareme_iq as bq

P = s.plafond_grade
assert P(None) is None and P("PSA 10") is None
for g in ("BGS 9.5", "TAG 10", "SGC 10", "CGC 9", "KSA 10", "HGA 9", "GMA 10"):
    assert bq.lettre(P(g)) == "A", g
base = "1989-90 O-Pee-Chee #113 Joe Sakic Rookie Card"
brut = s.score(base)["score"]
assert s.score(base + " KSA 10 GEM MINT")["score"] <= 91
assert s.score(base)["score"] == brut
print("OK test_plafond_grade")
