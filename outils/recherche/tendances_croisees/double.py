"""« Le type de carte en hausse jumele au joueur en hausse = mega valeur » : la carte monte ET les AUTRES cartes du meme joueur montent
aussi (mesurees de la meme facon, a la meme date). Que se passe-t-il ensuite ?"""
import os, sys, json, bisect, statistics as st, time, collections, random
os.environ["LOCKERROOM_DONNEES"] = "/tmp/v26"
sys.path.insert(0, "/home/claude/mathbou44/lockerroom-")
import comptes; comptes.DONNEES = "/tmp/v26"
from datetime import datetime, timedelta
import tendance_sortes as t
sys.path.insert(0, "/home/claude/mathbou44/lockerroom-/outils/recherche"); import cache_recherche      # sans pickle (tests/test_sans_pickle.py)
random.seed(5)
C = [c for c in cache_recherche.charger("/tmp/v26/cartes_tout.json.gz") if (c.get("sport") or "hockey") == "hockey"]
ex = t._cartes_exactes(C)
par_j = collections.defaultdict(list)
for (jn, k), g in ex.items():
    for saison, pts in t._saisons(g):
        l = sorted((t._jour(a), float(b)) for a, b in pts if t._jour(a) and b and float(b) > 0)
        if len(l) >= 8: par_j[jn].append((k, saison, l, [d for d, _p in l]))
R = json.load(open("/tmp/v26/histo_14.json"))
memo = {}
def autres(jn, k, s, Ts):
    T = datetime.fromisoformat(Ts); mes = []
    for k2, s2, l, ds in par_j[jn]:
        if (k2, s2) == (k, s): continue
        cle = (jn, k2, s2, Ts)
        if cle not in memo:
            i0 = bisect.bisect_left(ds, T - timedelta(days=130)); i1 = bisect.bisect_left(ds, T)
            m = t.mesure_carte([(d.strftime("%Y-%m-%d"), p) for d, p in l[i0:i1]], T) if i1 - i0 >= 4 else None
            if m and ("young guns" not in k2 and m["mediane"] < t.PRIX_MIN_HORS_YG or (m.get("disp") and m["disp"] > t.DISPERSION_MAX)): m = None
            memo[cle] = m
        if memo[cle]: mes.append(memo[cle])
    if not mes: return None
    a = t._agreger(mes, T, 6)
    return {"pct": a["pct"], "net": a["net"], "n": a["n"], "cartes": len(mes)}
for o in R:
    o["autres"] = autres(o["jn"], o["k"], o["s"], o["T"])
avec = [o for o in R if o["autres"]]
print(len(R), "mesures ;", len(avec), "ou le joueur a d'autres cartes mesurables a la meme date ;", len({o["jn"] for o in avec}), "joueurs")
def sj(o):
    a = o["autres"]; return "hausse" if a["net"] and a["pct"] >= 5 else "baisse" if a["net"] and a["pct"] <= -5 else "neutre"
def ic(L, f, n=500):
    pc = collections.defaultdict(list)
    for o in L: pc[(o["jn"], o["k"], o["s"])].append(o)
    cles = list(pc); res = []
    for _ in range(n):
        e = [x for c in random.choices(cles, k=len(cles)) for x in pc[c]]; res.append(f(e))
    res.sort(); return res[int(.05 * n)], res[int(.95 * n)], len(pc)
def ligne(nom, L):
    L = [o for o in L if o["f30"] is not None]
    if len(L) < 12: print(f"  {nom:52} trop peu ({len(L)} mesures, {len({(o['jn'], o['k'], o['s']) for o in L})} cartes)"); return
    med = lambda e: st.median(x["f30"] for x in e); tx = lambda e: sum(1 for x in e if x["f30"] >= -10) / len(e)
    lo, hi, nc = ic(L, med); l2, h2, _ = ic(L, tx)
    print(f"  {nom:52} n={len(L):4d} cartes={nc:3d} | 30 j suivants : {med(L):+5.1f} % [{lo:+5.1f} ; {hi:+5.1f}] | revend a 90 %+ : {100*tx(L):3.0f} % [{100*l2:3.0f} ; {100*h2:3.0f}]")
print("LA CARTE MONTE (confirmee)")
ligne("... et les autres cartes du joueur montent aussi", [o for o in avec if o["sens"] == "hausse" and sj(o) == "hausse"])
ligne("... les autres cartes du joueur ne bougent pas", [o for o in avec if o["sens"] == "hausse" and sj(o) == "neutre"])
ligne("... les autres cartes du joueur baissent", [o for o in avec if o["sens"] == "hausse" and sj(o) == "baisse"])
ligne("... (toutes les hausses, avec ou sans autres cartes)", [o for o in R if o["sens"] == "hausse"])
print("LA CARTE NE BOUGE PAS")
ligne("... mais les autres cartes du joueur montent", [o for o in avec if o["sens"] == "stable" and sj(o) == "hausse"])
ligne("... et les autres non plus", [o for o in avec if o["sens"] == "stable" and sj(o) == "neutre"])
ligne("... les autres cartes du joueur baissent", [o for o in avec if o["sens"] == "stable" and sj(o) == "baisse"])
print("LA CARTE BAISSE (confirmee)")
ligne("... et les autres cartes du joueur baissent aussi", [o for o in avec if o["sens"] == "baisse" and sj(o) == "baisse"])
ligne("... les autres cartes du joueur ne bougent pas", [o for o in avec if o["sens"] == "baisse" and sj(o) == "neutre"])
ligne("... les autres cartes du joueur montent", [o for o in avec if o["sens"] == "baisse" and sj(o) == "hausse"])
# saison passee seulement (sans l'effet « nouveau produit »)
def saison_de(T):
    a, m = int(T[:4]), int(T[5:7]); return a if m >= 9 else a - 1
P = [o for o in avec if o["s"] and saison_de(o["T"]) - o["s"] >= 1]
print("CARTES D'UNE SAISON PASSEE SEULEMENT")
ligne("double hausse", [o for o in P if o["sens"] == "hausse" and sj(o) == "hausse"])
ligne("la carte monte seule", [o for o in P if o["sens"] == "hausse" and sj(o) != "hausse"])
ligne("le joueur monte, pas (encore) cette carte", [o for o in P if o["sens"] == "stable" and sj(o) == "hausse"])
ligne("rien ne bouge", [o for o in P if o["sens"] == "stable" and sj(o) == "neutre"])
json.dump(R, open("/tmp/v26/histo_14_double.json", "w"))
