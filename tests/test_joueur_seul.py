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

# 13 nov 2026 : le marche du club (le plus de ventes dans nos archives = 100), americain ou canadien
import base_ventes, indice_joueurs
base_ventes.ventes_par_joueur = lambda jours=90: {"Cole Caufield": 900, "Nick Suzuki": 700, "Jack Hughes": 1200, "Joe Nobody": 20}
d = {"joueurs": {"Cole Caufield": {"nom": "Cole Caufield", "nhl": {"equipe": "MTL", "actif": True}},
                 "Nick Suzuki": {"nom": "Nick Suzuki", "nhl": {"equipe": "MTL", "actif": True}},
                 "Jack Hughes": {"nom": "Jack Hughes", "nhl": {"equipe": "NJD", "actif": True}},
                 "Joe Nobody": {"nom": "Joe Nobody", "nhl": {"equipe": "UTA", "actif": True}}}}
t = demande_legale.table_equipes(d, {"Cole Caufield": 3.0, "Jack Hughes": 2.0})
assert t["MTL"]["ventes"] == 1600 and t["NJD"]["ventes"] == 1200 and t["MTL"]["rang_pct"] > t["NJD"]["rang_pct"] > t["UTA"]["rang_pct"], t
demande_legale._ecrire({**d, "equipes": t})
assert demande_legale.marche_equipe("mtl") == t["MTL"]["rang_pct"] and demande_legale.marche_equipe("XXX") is None
assert demande_legale.pieces(d["joueurs"]["Jack Hughes"])["eq_marche"] == t["NJD"]["rang_pct"] / 100
assert "marche" in indice_joueurs.POIDS_ACTIF
print("MARCHE DES EQUIPES OK", {k: v["rang_pct"] for k, v in t.items()})
