"""La carte et le RESTE du joueur, version stricte : le reste = ses AUTRES cartes (une autre base), jamais la meme carte dans une
autre note (Young Guns PSA 10 contre Young Guns) ni sous un autre nom (« upper deck young guns 201 »)."""
import os, sys, json, bisect, statistics as st, collections, random, re
os.environ["LOCKERROOM_DONNEES"] = "/tmp/v26"
sys.path.insert(0, "/home/claude/mathbou44/lockerroom-")
import comptes; comptes.DONNEES = "/tmp/v26"
from datetime import datetime, timedelta
import tendance_sortes as t
sys.path.insert(0, "/home/claude/mathbou44/lockerroom-/outils/recherche"); import cache_recherche      # sans pickle (tests/test_sans_pickle.py)
random.seed(5)
RG = re.compile(r"\b(psa|bgs|sgc|cgc|ksa|hga|bccg|tag|gma|mnt|aca|isa|csg)\b(\s*\d+(\.5)?)?")
def base(k):
    b = RG.sub(" ", k)
    b = re.sub(r"\bupper deck\b|\bud\b|\bgraded\b|\braw\b|\b\d{1,3}\b", " ", b)
    return " ".join(b.split())
C = [c for c in cache_recherche.charger("/tmp/v26/cartes_tout.json.gz") if (c.get("sport") or "hockey") == "hockey"]
ex = t._cartes_exactes(C)
par_j = collections.defaultdict(list)
for (jn, k), g in ex.items():
    for saison, pts in t._saisons(g):
        l = sorted((t._jour(a), float(b)) for a, b in pts if t._jour(a) and b and float(b) > 0)
        if len(l) >= 8: par_j[jn].append((k, saison, l, [d for d, _p in l]))
R = json.load(open("/tmp/v26/histo_14.json"))
memo = {}
def autres(jn, k, s, Ts, strict):
    T = datetime.fromisoformat(Ts); mes = []
    for k2, s2, l, ds in par_j[jn]:
        if (k2, s2) == (k, s) or (strict and base(k2) == base(k) and s2 == s): continue
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
    o["strict"] = autres(o["jn"], o["k"], o["s"], o["T"], True)
json.dump(R, open("/tmp/v26/histo_14_strict.json", "w"))
def sj(a, nmin):
    if not a or a["n"] < nmin: return None
    return "hausse" if a["net"] and a["pct"] >= 5 else "baisse" if a["net"] and a["pct"] <= -5 else "neutre" if abs(a["pct"]) < 10 else "flou"
def stat(nom, L, cle):
    L = [o for o in L if o.get(cle) is not None]
    pj = collections.defaultdict(list)
    for o in L: pj[o["jn"]].append(o[cle])
    js = list(pj)
    if len(L) < 20 or len(js) < 8:
        print(f"  {nom:40} {cle} trop peu ({len(L)} mesures, {len(js)} joueurs)"); return
    r = []
    for _ in range(2000):
        e = [x for j in random.choices(js, k=len(js)) for x in pj[j]]; r.append(st.median(e))
    r.sort(); votes = [st.median(v) for v in pj.values()]
    top = [j for j, _ in collections.Counter(o["jn"] for o in L).most_common(5)]
    sans = [o[cle] for o in L if o["jn"] not in top]
    print(f"  {nom:40} {cle} n={len(L):4d} joueurs={len(js):3d} cartes={len({(o['jn'], o['k'], o['s']) for o in L}):3d} med {st.median(o[cle] for o in L):+5.1f} ic95 [{r[50]:+5.1f} ; {r[1949]:+5.1f}] | voix {sum(v < 0 for v in votes)} baisse / {sum(v > 0 for v in votes)} hausse | sans top5 {st.median(sans) if len(sans) >= 12 else None} | top {top[0]} {collections.Counter(o['jn'] for o in L)[top[0]]}")
for nmin in (1, 20):
    av = [o for o in R if sj(o["strict"], nmin)]
    print(f"== reste strict, au moins {nmin} ventes :", len(av), "mesures,", len({o['jn'] for o in av}), "joueurs,", len({(o['jn'], o['k'], o['s']) for o in av}), "cartes ;", collections.Counter((o["sens"], sj(o["strict"], nmin)) for o in av).most_common())
    for cle in ("f30", "f60"):
        stat("A carte hausse / reste neutre", [o for o in av if o["sens"] == "hausse" and sj(o["strict"], nmin) == "neutre"], cle)
        stat("B reste baisse / carte stable ou baisse", [o for o in av if o["sens"] != "hausse" and sj(o["strict"], nmin) == "baisse"], cle)
        stat("C reste hausse / carte stable ou hausse", [o for o in av if o["sens"] != "baisse" and sj(o["strict"], nmin) == "hausse"], cle)
        stat("temoin carte stable / reste neutre", [o for o in av if o["sens"] == "stable" and sj(o["strict"], nmin) == "neutre"], cle)
