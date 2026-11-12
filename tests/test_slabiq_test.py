"""11 nov 2026 : le test de prediction SlabIQ rejoue le passe sans fuite d'information (donnees fabriquees : un pic de
visites Wikipedia precede une hausse des prix ; le modele doit l'apprendre). Aucun reseau."""
import os, sys, tempfile, random, math
from datetime import date, timedelta
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import slabiq_test, base_ventes, nhl
random.seed(3)
d0 = date(2025, 11, 1)
jours = 360
cartes, buzz = [], {}
for j in range(60):
    nom = f"Joueur {j}"
    vues = {}
    evts = sorted(random.sample(range(70, jours - 40), 4))
    for d in range(-70, jours):
        jj = d0 + timedelta(days=d)
        v = 100 + random.randint(-10, 10)
        for e in evts:
            if 0 <= d - e < 5:
                v *= 6                                   # un pic de buzz
        vues[jj.isoformat()] = int(v)
    buzz[nom] = vues
    for c in range(3):
        base, pts = 20 + 30 * c, []
        for d in range(0, jours, 2):
            hausse = sum(1 for e in evts if 0 <= d - e < 35)
            p = base * (1.35 if hausse else 1.0) * math.exp(random.gauss(0, 0.05))
            pts.append([(d0 + timedelta(days=d)).isoformat(), round(p, 2)])
        cartes.append({"joueur": nom, "carte": f"c{c}", "sport": "hockey", "points": pts})
base_ventes.cartes_toutes = lambda **k: cartes
slabiq_test._vues_jour = lambda titre, a, b: buzz.get(titre.replace(" (ice hockey)", ""), {})
nhl._chercher = lambda nom: None
r = slabiq_test.executer()
assert "erreur" not in r, r
assert r["exemples"] > 500 and r["test"] > 50, r
assert r["resultat"]["exactitude"] > r["reperes"].get("elan_naif", 0), r
assert r["signaux"] and r["signaux"][0][0].startswith("buzz") or any(k.startswith("buzz") for k, _v in r["signaux"][:3]), r["signaux"]
print("SLABIQ TEST OK", r["resultat"], r["reperes"], r["signaux"][:3])

# 12 nov 2026 : sans aucun signal (prix au hasard), le test ne doit PAS annoncer de miracle (le 1er rapport voyait le futur)
random.seed(5)
bruit = []
for j in range(60):
    for c in range(3):
        base = 20 + 30 * c
        bruit.append({"joueur": f"Joueur {j}", "carte": f"c{c}", "sport": "hockey",
                      "points": [[(d0 + timedelta(days=d)).isoformat(), round(base * math.exp(random.gauss(0, 0.15)), 2)] for d in range(0, jours, 2)]})
base_ventes.cartes_toutes = lambda **k: bruit
r2 = slabiq_test.executer()
x2 = r2["resultat"]
assert not r2["atteint"], x2
assert x2["exactitude"] <= max(r2["reperes"].values()) + 0.05, (x2, r2["reperes"])
assert r2["courbe"] and r2["ventes_mois"], r2.keys()
print("SLABIQ BRUIT OK", x2, r2["reperes"], (r2.get("meilleur") or {}))

# 12 nov 2026 : AUCUN signal d'un lundi ne bouge si on change tout ce qui arrive apres (prix x10, ventes en plus)
import copy
T = "2026-06-01"
fut = copy.deepcopy(bruit)
for c in fut:
    c["points"] = [[le, p * (10 if le >= T else 1)] for le, p in c["points"]] + [[le, 999] for le, p in c["points"] if le >= T][:5]
def _sig(cs):
    pj = slabiq_test._series(cs)
    toutes = [le for cj in pj.values() for pts in cj for le, _ in pts]
    X, y, meta, _n = slabiq_test._exemples(pj, {}, {}, date.fromisoformat(min(toutes)), date(2026, 11, 1))
    return {(m[0], m[1]): x for x, m in zip(X, meta) if m[0] <= T}
a_, b_ = _sig(bruit), _sig(fut)
assert len(a_) > 300, len(a_)
assert not [k for k in a_ if k in b_ and any(abs(u - v) > 1e-9 for u, v in zip(a_[k], b_[k]))], "le futur fuit dans les signaux"
print("SLABIQ SANS FUTUR OK", len(a_))

# 12 nov 2026 : le test laisse ses donnees (slabiq_test_donnees.json.gz) et se rejoue a l'identique depuis ce fichier
import os as _os
base_ventes.cartes_toutes = lambda **k: cartes
r3 = slabiq_test.executer()
p_ = _os.path.join(comptes.DONNEES, "slabiq_test_donnees.json.gz")
assert _os.path.exists(p_), "donnees pas sauvees"
base_ventes.cartes_toutes = lambda **k: (_ for _ in ()).throw(AssertionError("ne doit pas relire la base"))
r4 = slabiq_test.executer(depuis=p_)
assert r4["resultat"] == r3["resultat"] and r4["exemples"] == r3["exemples"], (r3["resultat"], r4["resultat"])
print("SLABIQ REJOUE OK", r4["resultat"])
