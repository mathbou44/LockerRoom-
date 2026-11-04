"""3 nov 2026 (Mathieu : « le jeudi, beaucoup d'encheres finissent ») : le budget SoldComps suit le jour de la semaine,
le total de la semaine ne change pas. Aucun reseau."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vendues
p = vendues.poids_jours()
assert abs(sum(p.values()) - 7) < 0.01 and p["jeu"] == 1.6 and p["mer"] == 1.2 and abs(p["lun"] - 0.84) < 0.01, p
vendues.poids_aujourdhui = lambda: p["jeu"]
os.environ["LR_SOLDCOMPS_JOUR"] = "700"
assert vendues.plafond_jour() == 1120
sem = sum(int(round(700 * v)) for v in p.values())
assert abs(sem - 4900) <= 4, sem                       # meme total sur 7 jours (a l'arrondi pres)
os.environ["LR_POIDS_JOURS"] = "jeu:2,dim:1.5"
q = vendues.poids_jours()
assert abs(sum(q.values()) - 7) < 0.01 and q["jeu"] == 2 and q["dim"] == 1.5 and abs(q["mar"] - 0.7) < 0.01, q
os.environ["LR_POIDS_JOURS"] = "n'importe quoi"
assert vendues.poids_jours()["jeu"] == 1.0              # reglage illisible : tous les jours egaux
print("ok poids des jours")
