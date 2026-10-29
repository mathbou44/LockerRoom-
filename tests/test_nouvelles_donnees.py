"""31 oct 2026 (Mathieu : « assure-toi que les donnees soient bonnes et justes, sinon on fait de la desinformation ») :
nos nouvelles du marche ne sortent que sur des ventes solides. python tests/test_nouvelles_donnees.py (aucun reseau)."""
import os
import random
import sys
import tempfile
from datetime import datetime, timedelta
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import nouvelles_donnees as N  # noqa: E402

AUJ = datetime(2026, 10, 31, 12)
J = lambda n: (AUJ - timedelta(days=n)).strftime("%Y-%m-%d")      # noqa: E731
random.seed(7)
T = "2023-24 Upper Deck Young Guns Connor Bedard #201"
PLAN = [("bedard yg", "2023-24 upper deck connor bedard young guns", "Connor Bedard", "Young Guns", "2023-24 Upper Deck Series 1")]

def ventes(spec):
    out, k = [], 0
    for suf, jours, prix in spec:
        for d, p in zip(jours, prix):
            k += 1
            out.append({"titre": T + suf, "prix": p, "le": J(d), "url": f"u{k}"})
    return out

def lancer(v):
    return N.analyser(maintenant=AUJ, charger=lambda j: (PLAN, {"bedard yg": v}))

bruit = lambda m, n: [round(m * random.uniform(0.85, 1.15), 2) for _ in range(n)]

# 1) une vraie hausse en PSA 10 : 8 ventes a ~400 $ (14 j) contre 9 a ~300 $ (15-45 j) -> nouvelle
v = ventes([(" PSA 10", range(1, 9), bruit(400, 8)), (" PSA 10", range(16, 43, 3), bruit(300, 9))])
a = lancer(v)
assert len(a["hausses"]) == 1 and a["hausses"][0]["condition"] == "PSA 10" and 20 <= a["hausses"][0]["pct"] <= 50, a["hausses"]
x = N.nouvelle_mouvement(1, "fr", a)
assert "PSA 10" in x["titre"] and "+" in x["titre"] and len(x["preuve"][0]["ventes"]) == 8 and "17 ventes" in x["source"], x

# 2) du bruit seulement (meme prix, variations normales) -> rien
v = ventes([(" PSA 10", range(1, 9), bruit(300, 8)), (" PSA 10", range(16, 43, 3), bruit(300, 9))])
assert not lancer(v)["hausses"] and not lancer(v)["baisses"]

# 3) un seul gros prix ne fait pas une hausse
v = ventes([(" PSA 10", range(1, 9), bruit(300, 7) + [1500]), (" PSA 10", range(16, 43, 3), bruit(300, 9))])
assert not lancer(v)["hausses"], lancer(v)["hausses"]

# 4) trop peu de ventes -> rien, meme si le prix double
v = ventes([(" PSA 10", range(1, 5), bruit(600, 4)), (" PSA 10", range(16, 43, 3), bruit(300, 9))])
assert not lancer(v)["hausses"]

# 5) brutes et PSA 10 jamais melangees ; les lots exclus ; une vente vue deux fois comptee une fois
v = ventes([("", range(1, 9), bruit(40, 8)), (" PSA 10", range(16, 43, 3), bruit(300, 9)),
            (" Lot of 3", range(1, 9), bruit(400, 8))])
v += [dict(v[0])]                                                 # la meme vente (meme lien) une 2e fois
a = lancer(v)
assert not a["hausses"] and not a["baisses"], a                   # brute recente vs PSA 10 ancienne : jamais compare

# 6) des ventes trop vieilles (derniere il y a 10 jours) -> rien
v = ventes([(" PSA 10", range(10, 14), bruit(450, 4)) , (" PSA 10", range(10, 14), bruit(450, 4)), (" PSA 10", range(16, 43, 3), bruit(300, 9))])
assert not lancer(v)["hausses"]

# 7) une vraie baisse en brute
v = ventes([("", range(1, 11), bruit(30, 10)), ("", range(16, 46, 3), bruit(50, 10))])
b = lancer(v)["baisses"]
assert len(b) == 1 and b[0]["condition"] is None and b[0]["pct"] <= -20, b
y = N.nouvelle_mouvement(-1, "fr", lancer(v))
assert "brute" in y["titre"] and "−" in y["titre"]

# 8) la prime PSA 10 / PSA 9, avec ses ventes
v = ventes([(" PSA 10", range(1, 40, 4), bruit(400, 10)), (" PSA 9", range(2, 40, 4), bruit(160, 10))])
p = lancer(v)["primes"]
assert len(p) == 1 and 2.0 <= p[0]["ratio"] <= 3.0 and p[0]["n10"] == 10 and p[0]["n9"] == 10, p
z = N.nouvelle_prime("fr", lancer(v))
assert "PSA 10" in z["titre"] and "×" in z["chiffre"] and z["preuve"][0]["titre"] == "PSA 10"
print("ok : nouvelles du marche (donnees solides seulement)")
