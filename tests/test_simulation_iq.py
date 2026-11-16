"""16 nov 2026 (Mathieu : « deux collectionneurs, le meme budget, avec et sans SlabIQ ») : le nettoyage (un checklist a 5 $
n'est pas la YG), la simulation (memes frais, B n'achete jamais en flambee, la valeur finale = les ventes de la fin)."""
import os, sys, tempfile
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import simulation_iq as s
from datetime import date
# 1. le nettoyage : la vente a 5 $ au milieu de ventes a 200 $ n'est pas la carte
l = [(date(2026, 1, 1).toordinal() + k, 200.0 + (k % 5)) for k in range(20)] + [(date(2026, 1, 10).toordinal(), 5.0)]
l.sort()
assert all(p > 100 for _, p in s.nettoyer(l)) and len(s.nettoyer(l)) == 20
# 2. une simulation : un joueur dont la carte vaut 100 $, flambee les 30 premiers jours (150 $), puis 100 $
class J:
    pass
j = J()
d0 = date(2026, 1, 1).toordinal()
import numpy as np
v = [(d0 + k, 150.0 if k < 30 else 100.0, "raw") for k in range(0, 200)]
j.ventes = v
j.par_g = {"raw": (np.array([o for o, _, _ in v]), np.array([p for _, p, _ in v])), "psa10": (np.array([]), np.array([]))}
j.etat = {d0 + k: ("flambee" if k < 30 else "neutre") for k in range(200)}
j.mediane = lambda g, d, jours=14, avant=True: s.Joueur.mediane(j, g, d, jours, avant)
j.valeur_fin = lambda g, fin: s.Joueur.valeur_fin(j, g, fin)
r = s.simuler([j], d0, 180, 200, "fomo", 0.10, graine=1)
assert r["A"]["cartes"] > 0 and r["B"]["cartes"] > 0, r
assert r["B"]["total"] >= r["A"]["total"], r          # A achete pendant la flambee (150 $) ; B attend
print("SIMULATION OK", r)
