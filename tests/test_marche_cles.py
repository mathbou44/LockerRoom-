"""16 nov 2026 (Mathieu : « les joueurs cles ; savoir quand leur marche est plus bas qu'a l'habitude, ca tend a remonter ») :
les joueurs cles, l'indice de marche (chaque sorte contre sa normale), la verification contre le hasard, la pastille."""
import os, sys, tempfile, random, json
from datetime import date, timedelta
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import marche_cles as mc
import types_cartes

# 1. joueurs cles : le Temple, les trophees, la fidelite a une equipe et ce que le monde achete / suit
yz = {"hhof": True, "top100": True, "trophees_c": {"Stanley Cup": 3, "Conn Smythe Trophy": 1}, "carriere": {"points": 1755},
      "equipes": [[1983 + i, "Detroit Red Wings", 70] for i in range(22)]}
quatrieme = {"carriere": {"points": 80}, "equipes": [[2019, "A", 40], [2020, "B", 30], [2021, "C", 25]]}
assert mc.fidelite(yz) == 22 and mc.fidelite(quatrieme) == 1
s_yz, r_yz = mc.score_cle(yz, 0.9, 0.7)
s_q, _ = mc.score_cle(quatrieme, 0.1, 0.0)
assert s_yz >= 80 and "fidele" in r_yz and "temple" in r_yz, (s_yz, r_yz)
assert s_q < mc.SCORE_CLE_MIN, s_q
L = mc.cles(base={"steve yzerman": {"nhl": yz}, "joe quatrieme": {"nhl": quatrieme}}, ventes_n={"Steve Yzerman": 300, "Joe Quatrieme": 3}, suivis={})
noms = [x["nom"] for x in L]
assert "Steve Yzerman" in noms and "Joe Quatrieme" not in noms, L

# 2. l'indice : chaque sorte contre SA normale (une Young Guns et une Kaboom se comparent a elles-memes)
types_cartes.type_de = lambda t: ("kaboom|r" if "kaboom" in t.lower() else "young_guns|r")
random.seed(3)
auj = date(2026, 11, 16)
J = lambda n: (auj - timedelta(days=n)).isoformat()


def ventes_joueur(nom, creux_les, profondeur=0.75, rebond=True):
    """~1 an de ventes : une YG (~100 $) et une Kaboom (~1 000 $), avec des creux (puis un retour a la normale)."""
    v = []
    for d in range(420, -1, -2):
        f = 1.0
        for c in creux_les:
            if c - 14 < d <= c:
                f = profondeur
            elif rebond is False and d <= c:
                f = profondeur
        v.append((nom, "2023-24 Upper Deck Young Guns " + nom, round(100 * f * random.uniform(0.92, 1.08), 2), J(d)))
        if d % 4 == 0:
            v.append((nom, "Upper Deck Kaboom " + nom, round(1000 * f * random.uniform(0.92, 1.08), 2), J(d)))
    return v


V = []
liste = []
for i in range(12):
    nom = f"Joueur Cle{i}"
    V += ventes_joueur(nom, creux_les=[300 - 7 * i, 160 - 5 * i] + ([7] if i < 3 else []))
    liste.append({"nom": nom, "score": 70, "raisons": []})
S = mc.series(V, [x["nom"] for x in liste])
ix, n = mc.indice_a(S["Joueur Cle0"], auj.toordinal())
assert ix is not None and 0.68 < ix < 0.82 and n >= mc.N_W_MIN, (ix, n)       # en creux aujourd'hui : ~ -25 %
ix5, _ = mc.indice_a(S["Joueur Cle5"], auj.toordinal())
assert 0.9 < ix5 < 1.1, ix5                                                     # normal

# 3. la verification : les creux passes ont remonte (+33 %) -> le signal est actif, le hasard est battu
d = mc.calculer(ventes=V, liste=liste, aujourd=auj)
v = d["verif"]
assert v["actif"] and v["taux"] > v["base"] and v["n"] >= mc.N_TEST_MIN, v
mc.ecrire(d)
b = mc.bas("Joueur Cle0")
assert b and b["ecart_pct"] <= -18 and b["source"] == "marche", b
assert mc.bas("Joueur Cle5") is None
assert [x["nom"] for x in mc.liste_bas()][:3] and all(x["nom"] in ("Joueur Cle0", "Joueur Cle1", "Joueur Cle2") for x in mc.liste_bas()), mc.liste_bas()

# 4. un marche qui ne remonte jamais (les creux restent bas) : le signal ne bat pas le hasard -> rien n'est affiche
random.seed(5)
V2, l2 = [], []
for i in range(12):
    nom = f"Joueur Bas{i}"
    V2 += ventes_joueur(nom, creux_les=[300 - 7 * i], rebond=False)
    l2.append({"nom": nom, "score": 70, "raisons": []})
d2 = mc.calculer(ventes=V2, liste=l2, aujourd=auj)
assert not d2["verif"]["actif"], d2["verif"]
mc.ecrire(d2)
assert mc.bas("Joueur Bas0") is None
print("MARCHE CLES OK", {k: v[k] for k in ("seuil", "taux", "base", "n", "gain_med")})
