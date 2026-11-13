"""13 nov 2026 (Mathieu : « comprendre pourquoi les mouvements et les spikes de ventes ; pour un joueur cible, tout ce qui a pu
faire monter ou baisser sa valeur ou sa liquidite ») : le journal des evenements, les mouvements, leurs causes, les effets."""
import os, sys, tempfile, random
from datetime import date, timedelta
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import mouvements as M, quoi_de_neuf
random.seed(1)
J0 = date.today() - timedelta(days=120)
nom = "Cole Caufield"
cartes = ["2021-22 Upper Deck Young Guns Cole Caufield #451 RC", "2021-22 Upper Deck Young Guns Cole Caufield #451 RC PSA 10",
          "2021-22 SP Authentic Future Watch Auto Cole Caufield /999"]
base = {cartes[0]: 60, cartes[1]: 250, cartes[2]: 300}
spike = J0 + timedelta(days=77)                  # une semaine : un tour du chapeau, 5 fois plus de ventes, +40 %
spike -= timedelta(days=spike.weekday())
V = []
for d in range(120):
    j = J0 + timedelta(days=d)
    chaud = spike <= j < spike + timedelta(days=7)
    for _ in range((5 if chaud else 1)):
        t = random.choice(cartes)
        V.append({"titre": t, "prix": base[t] * (1.4 if chaud else 1.0) * random.uniform(0.95, 1.05), "le": j.isoformat()})
V.append({"titre": "Connor McDavid Young Guns", "prix": 500, "le": spike.isoformat()})        # un autre joueur : ignore
# le journal : l'Indice du jour du tour du chapeau
M.journal_noter({nom: {"evenements": [{"type": "exploit", "sens": 1, "titre": "Caufield records hat trick vs Leafs", "lien": "https://x",
                                       "date": (spike - timedelta(days=1)).isoformat()}]}})
M.journal_noter({nom: {"evenements": [{"type": "exploit", "sens": 1, "titre": "Caufield records hat trick vs Leafs", "lien": "https://x",
                                       "date": (spike - timedelta(days=1)).isoformat()}]}})      # pas de doublon
assert len(M.journal()[nom]) == 1
# l'equipe du jour (hist de l'Indice) : rien de change ; « en feu » ce jour-la
quoi_de_neuf.hist_noter({nom: {"indice": 80, "equipe": "MTL", "pastilles": []}}, jour=spike - timedelta(days=10))
quoi_de_neuf.hist_noter({nom: {"indice": 88, "equipe": "MTL", "pastilles": ["en_feu"]}}, jour=spike + timedelta(days=1))
r = M.analyser(nom, ventes=V)
m = r["mouvements"][0]
assert m["semaine"] == spike.isoformat() and m["volume"] and m["ventes_x"] >= 3 and m["prix"] and 25 <= m["prix_pct"] <= 55, m
types = {c["type"] for c in m["causes"]}
assert {"exploit", "feu"} <= types, m["causes"]
# ce que les evenements font, en general
e = M.effets([nom], ventes_de=lambda n: V)
assert e["exploit"]["n"] == 1 and e["exploit"]["prix_pct"] > 10 and e["exploit"]["ventes_x"] > 1.5, e
print("MOUVEMENTS OK")
