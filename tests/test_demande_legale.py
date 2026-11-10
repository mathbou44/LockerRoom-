"""10 nov 2026 : la demande d'un joueur sans ventes eBay (LNH, Wikipedia) ; le labo la mesure contre les ventes (admin)."""
import math
import os
import random
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import demande_legale as dl

rnd = random.Random(7)
verite, joueurs = {}, {}
for i in range(120):
    pop = rnd.uniform(0, 4)                                # la « vraie » popularite
    nom = "Joueur " + chr(65 + i // 26) + chr(97 + i % 26) + "son"
    verite[nom] = round(math.exp(0.6 * pop - 1.2 + rnd.gauss(0, 0.25)), 3)
    joueurs[nom] = {"le": 9e9, "wiki": {"v60": int(math.exp(6 + pop + rnd.gauss(0, 0.4))), "v20": 100},
                    "nhl": {"pos": "C", "actif": True, "naissance": "2002-01-01", "repech": int(200 / (1 + pop)),
                            "saison": {"gamesPlayed": 20, "points": int(5 + 5 * pop)}, "carriere": {"gamesPlayed": 200, "points": int(50 * (1 + pop))},
                            "trophees_n": 0}}
r = dl.labo({"joueurs": joueurs}, verite)
assert r["n"] == 120 and r["seules"]["wiki"] > 0.7, r["seules"]
assert r["combinaisons"][r["garde"]]["rho"] >= 0.8, r["combinaisons"]
dl._ecrire({"joueurs": joueurs, "modele": r["modele"], "labo": {}})
fort = max(verite, key=verite.get)
faible = min(verite, key=verite.get)
assert dl.demande(fort) > dl.demande(faible), (dl.demande(fort), dl.demande(faible))
assert dl.demande("Personne Inconnue") is None
assert dl.spearman([1, 2, 3, 4, 5], [5, 6, 7, 8, 9]) == 1.0
# le public passe par la demande legale (jamais les ventes)
import valeurs
comptes.MULTI = True
import lockerroom
api = lockerroom.Api()
cid, _ = comptes.trouver_ou_creer("apple-1", "x", "apple")
api._est_admin = lambda reel=False: False
with comptes.utiliser(cid):
    assert abs(valeurs.demande(fort) - dl.demande(fort)) < 1e-9
    assert valeurs.demande("Personne Inconnue") == valeurs.DEMANDE_INCONNUE
print("OK demande legale")
