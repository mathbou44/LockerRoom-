"""13 nov 2026 (Mathieu : « cole caufield » -> seulement des cartes a 2 $, score 2) : un nom de joueur seul n'est pas une
carte : toutes ses cartes, les hits d'abord, 20 $ et plus ; le score du JOUEUR ; l'equipe compte dans la demande (labo)."""
import os, sys, tempfile
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom, demande_legale
A = lockerroom.Api
assert A._joueur_seul("cole caufield") and A._joueur_seul("Cole Caufield").lower().endswith("caufield")
for q in ("cole caufield young guns", "connor bedard 2023", "bedard auto", "caufield psa 10"):
    assert not A._joueur_seul(q), q
p = demande_legale.pieces({"nom": "Cole Caufield", "nhl": {"equipe": "MTL", "pays": "USA", "actif": True}, "wiki": {}})
assert p["eq_can"] == 1.0 and p["eq_orig6"] == 1.0 and p["eq_MTL"] == 1.0 and p["eq_TOR"] == 0.0 and p["ne_can"] == 0.0
assert all(k in p for k in demande_legale.PIECES)
print("JOUEUR SEUL OK")
