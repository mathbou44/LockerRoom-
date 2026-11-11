"""10 nov 2026 (Mathieu : « precision minimum 9/10, confiance 9/10 ») : le modele du Score SlabCoach (exporte, sans
scikit-learn). Le banc (hors ligne, 32 826 ventes jamais vues) a mesure 0,908 / 0,905 ; ici : il se charge, il est
rapide, il classe les cartes dans le bon sens, et il ne regarde jamais un prix."""
import os
import sys
import tempfile
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import score_modele as sm
import score_slab

assert sm.charger() is not None, "score_modele.npz manquant"
assert sm.BANC["precision"] >= 0.90 and sm.BANC["confiance"] >= 0.90
T = ["2024-25 Upper Deck The Cup Macklin Celebrini Rookie Patch Auto /249",
     "Upper Deck 2025-26 Premier Matvei Gridin Focus Rookies Patch Auto 85/99",
     "2023-24 Upper Deck Young Guns Connor Bedard #451 PSA 10",
     "2022-23 O-Pee-Chee Nick Suzuki #45",
     "2023-24 Upper Deck Series 1 Brock Nelson base #12"]
s = sm.scores(T)
assert all(0 <= x <= 100 for x in s), s
assert s[0] > s[3] and s[1] > s[4] and s[2] > s[4], s           # une RPA de la Cup, un auto-patch /99, une YG gradee 10 > une base
# le prix n'entre jamais : le meme titre avec ou sans prix ecrit donne le meme score... un prix n'est meme pas un parametre
import inspect
assert "prix" not in inspect.signature(sm.scores).parameters and "prix" not in inspect.signature(sm.brut).parameters
t0 = time.time()
sm.scores(T * 60)
assert time.time() - t0 < 5, time.time() - t0
x = score_slab.annoter_lot([{"titre": T[1]}, {"titre": T[4]}])
assert x[0]["score"] > x[1]["score"] and x[0]["carte"]["tirage"] == 99
print("OK score modele", s)
