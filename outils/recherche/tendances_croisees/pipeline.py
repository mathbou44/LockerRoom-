import os, sys, time, resource, collections
os.environ["LOCKERROOM_DONNEES"] = "/tmp/v26"
sys.path.insert(0, "/home/claude/mathbou44/lockerroom-")
import comptes; comptes.DONNEES = "/tmp/v26"
from datetime import datetime
import base_ventes, tendance_sortes as t
base_ventes.NOUVELLES_MAX = 10**9
class FauxNow(datetime):
    @classmethod
    def now(cls, tz=None): return cls(2026, 11, 26, 8, 0, 0)
base_ventes.datetime = FauxNow
jours = int(sys.argv[1]); sortie = sys.argv[2]
t0 = time.time()
C = base_ventes.cartes_toutes(jours=jours, n_min=4, max_q=30000, detail=True)
print("cartes_toutes(", jours, ") :", len(C), "recherches gardees ;", sum(len(c["points"]) for c in C), "ventes acceptees ;", sum(len(c["ventes"]) for c in C), "apres reeditions et lots ; a trier", base_ventes.A_TRIER, ";", round(time.time() - t0), "s ; memoire", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024, "Mo", flush=True)
print("sports :", collections.Counter(c.get("sport") for c in C).most_common(6), flush=True)
sys.path.insert(0, "/home/claude/mathbou44/lockerroom-/outils/recherche"); import cache_recherche      # sans pickle (tests/test_sans_pickle.py)
cache_recherche.sauver(C, sortie)
print("FINI", flush=True)
