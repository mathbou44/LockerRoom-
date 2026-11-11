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
