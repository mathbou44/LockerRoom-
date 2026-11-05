"""5 nov 2026 : les indices de ventes repetees (indices.py) : une hausse reguliere est retrouvee, une vente folle ou une
carte chere vendue une fois ne fait pas l'indice, et la valeur d'une carte sans vente recente suit l'indice du joueur."""
import os, sys, tempfile, random, math
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import indices

auj = datetime(2026, 11, 5)
rnd = random.Random(7)
def carte(base, hausse_sem, semaines=20, par_sem=3, bruit=0.08, joueur="Connor Bedard"):
    pts = []
    for s in range(semaines):
        for _ in range(par_sem):
            d = auj - timedelta(days=7 * (semaines - 1 - s) + rnd.randint(0, 6))
            pts.append([d.strftime("%Y-%m-%d"), round(base * (1 + hausse_sem) ** s * math.exp(rnd.gauss(0, bruit)), 2)])
    return {"joueur": joueur, "points": pts, "sport": "hockey", "annee": 2023}

# 1. +2 % par semaine sur 5 cartes de prix tres differents : ~+8,2 % sur 4 semaines, ~+29 % sur 13
cs = [carte(b, 0.02) for b in (12, 40, 90, 300, 2500)]
i = indices.indice(cs)
assert i and i["n_cartes"] == 5, i
assert 4 <= i["v4"] <= 13 and 20 <= i["v13"] <= 40, (i["v4"], i["v13"])
# 2. une vente folle (x10) d'une carte : l'indice ne s'envole pas
cs2 = [dict(c, points=list(c["points"])) for c in cs]
cs2[0]["points"].append([auj.strftime("%Y-%m-%d"), 120.0])
i2 = indices.indice(cs2)
assert abs(i2["v4"] - i["v4"]) < 8, (i["v4"], i2["v4"])
# 3. un marche plat : pres de 0
plat = indices.indice([carte(b, 0.0) for b in (20, 60, 150, 400)])
assert abs(plat["v4"]) < 6 and abs(plat["v13"]) < 8, plat
# 4. une carte qui ne se vend qu'une semaine : aucune paire
assert indices.paires([[auj.strftime("%Y-%m-%d"), 50]]) == []
# 5. les cartes a moins de 5 $ ne comptent pas
assert indices.paires(carte(2, 0.1)["points"]) == []
# 6. calculer + ajuster : une carte vendue il y a 10 semaines suit l'indice du joueur
tout = indices.calculer(cs + [carte(b, -0.01, joueur="Ivan Demidov") for b in (30, 80, 200)])
assert "connor bedard" in tout["joueurs"] and "ivan demidov" in tout["joueurs"]
assert tout["hobby"]["egal"] and any(s["cle"] == "sport:hockey" for s in tout["segments"])
indices.garder(tout)
v, info = indices.ajuster(100.0, (auj - timedelta(days=70)).strftime("%Y-%m-%d"), "Connor Bedard", "hockey", auj=auj)
assert info and info["source"] == "joueur" and 110 < v < 140, (v, info)
v, info = indices.ajuster(100.0, (auj - timedelta(days=70)).strftime("%Y-%m-%d"), "Ivan Demidov", auj=auj)
assert info and 85 < v < 97, (v, info)
# recente (moins de 14 jours) : pas d'ajustement ; joueur inconnu : le hobby
assert indices.ajuster(100.0, (auj - timedelta(days=5)).strftime("%Y-%m-%d"), "Connor Bedard", auj=auj) == (100.0, None)
v, info = indices.ajuster(100.0, (auj - timedelta(days=70)).strftime("%Y-%m-%d"), "Personne Inconnu", auj=auj)
assert info and info["source"] == "hobby", info
# hors de la serie (avant le debut) : rien
assert indices.ajuster(100.0, (auj - timedelta(days=400)).strftime("%Y-%m-%d"), "Connor Bedard", auj=auj)[1] is None
print("INDICES OK", i["v4"], i["v13"], plat["v4"])

# 7. un joueur d'une seule carte (confiance faible) : pas de courbe affichee, la valeur suit le sport
tout2 = indices.calculer(cs + [carte(40, 0.05, joueur="Un Seul")])
indices.garder(tout2)
assert tout2["joueurs"]["un seul"]["confiance"] == "faible" and indices.joueur("Un Seul") is None
assert indices.joueur("Un Seul", meme_faible=True)
v, info = indices.ajuster(100.0, (auj - timedelta(days=70)).strftime("%Y-%m-%d"), "Un Seul", "hockey", auj=auj)
assert info and info["source"] == "sport", info
print("INDICES CONFIANCE OK")
