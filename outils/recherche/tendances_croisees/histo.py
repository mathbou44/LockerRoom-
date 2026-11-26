"""Test sur l'historique : a chaque date T du passe, on mesure chaque carte EXACTEMENT comme tendance_sortes le fait (avec les seules
ventes d'avant T), puis on regarde les 30 et 60 jours suivants. Sortie : /tmp/v26/histo.json (une ligne par carte et par date)."""
import os, sys, json, bisect, statistics, time
os.environ["LOCKERROOM_DONNEES"] = "/tmp/v26"
sys.path.insert(0, "/home/claude/mathbou44/lockerroom-")
import comptes; comptes.DONNEES = "/tmp/v26"
from datetime import datetime, timedelta
import tendance_sortes as t
sys.path.insert(0, "/home/claude/mathbou44/lockerroom-/outils/recherche"); import cache_recherche      # sans pickle (tests/test_sans_pickle.py)
C = [c for c in cache_recherche.charger("/tmp/v26/cartes_tout.json.gz") if (c.get("sport") or "hockey") == "hockey"]
ex = t._cartes_exactes(C)
cartes = []          # (joueur, jn, k, saison, [(date, prix)] tries)
for (jn, k), g in ex.items():
    for saison, pts in t._saisons(g):
        l = sorted((t._jour(a), float(b)) for a, b in pts if t._jour(a) and b and float(b) > 0)
        if len(l) >= 16:
            cartes.append((g["joueur"], jn, k, saison, l))
print(len(C), "recherches ->", len(ex), "groupes ->", len(cartes), "cartes exactes de 16 ventes et plus ;", sum(len(c[4]) for c in cartes), "ventes", flush=True)
PAS = int(sys.argv[1]) if len(sys.argv) > 1 else 14
fin = datetime(2026, 11, 26)
dates = []
T = datetime(2024, 1, 1)
while T <= fin - timedelta(days=30):
    dates.append(T); T += timedelta(days=PAS)
med = statistics.median
out = []; t0 = time.time()
for joueur, jn, k, saison, l in cartes:
    ds = [d for d, _p in l]
    for T in dates:
        i0 = bisect.bisect_left(ds, T - timedelta(days=130)); i1 = bisect.bisect_left(ds, T)
        if i1 - i0 < 12:
            continue
        w = l[i0:i1]
        m = t.mesure_carte([(d.strftime("%Y-%m-%d"), p) for d, p in w], T)
        if not m:
            continue
        if "young guns" not in k and m["mediane"] < t.PRIX_MIN_HORS_YG:
            continue
        if m.get("disp") and m["disp"] > t.DISPERSION_MAX:
            continue
        if m["n_av"] + m["n_re"] < t.CARTE_VENTES_MIN or m["n_av"] < t.CARTE_PERIODE_MIN or m["n_re"] < t.CARTE_PERIODE_MIN or not m.get("disp"):
            continue
        a = t._agreger([m], T, t.CARTE_SEMAINE_MIN)
        a["net"] = bool(a["net"] and a["p"] is not None and a["p"] < t.P_CARTE)
        confirme, sens = t._sens(a)
        rec = [p for d, p in w if d >= T - timedelta(days=30)]
        j1 = bisect.bisect_left(ds, T + timedelta(days=30)); j2 = bisect.bisect_left(ds, T + timedelta(days=60))
        f30 = [p for _d, p in l[i1:j1]]; f60 = [p for _d, p in l[j1:j2]]
        base = med(rec)
        out.append({"j": joueur, "jn": jn, "k": k, "s": saison, "T": T.strftime("%Y-%m-%d"), "sens": sens, "pct": a["pct"], "brut": a["brut"], "p": a["p"],
                    "coh": a["coherent"], "n": a["n"], "n_re": a["n_re"], "base": round(base, 2),
                    "f30": round(100 * (med(f30) / base - 1), 1) if len(f30) >= 4 else None, "n30": len(f30),
                    "f60": round(100 * (med(f60) / base - 1), 1) if len(f60) >= 4 and T + timedelta(days=60) <= fin else None, "n60": len(f60),
                    "complet30": T + timedelta(days=30) <= fin})
print(len(out), "mesures (carte x date) ;", len({(o["jn"], o["k"], o["s"]) for o in out}), "cartes ;", len({o["jn"] for o in out}), "joueurs ;", len(dates), "dates aux", PAS, "jours ;", round(time.time() - t0), "s", flush=True)
json.dump(out, open("/tmp/v26/histo_%d.json" % PAS, "w"))
