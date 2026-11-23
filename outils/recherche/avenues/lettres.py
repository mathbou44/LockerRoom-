import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))); import cache_recherche as cr   # 23 nov 2026 : plus de pickle (Aikido)
import collections, statistics as st
A = cr.charger("A.json.gz")
C0, C = "2026-10-15", "2026-10-29"
ORD = ["A+", "A", "A-", "B+", "B", "C", "D", "E"]
lettre, ra, avant60, pmed = {}, {}, collections.Counter(), collections.defaultdict(list)
import datetime as dt
j60 = (dt.date.fromisoformat(C) - dt.timedelta(days=60)).isoformat()
for a in A:
    k = (a["k"], a["gr"])
    if a["j"] < C:
        lettre[k] = a["fin"]; ra[k] = a["ra"]
        pmed[k].append(a["p"])
        if a["j"] >= j60: avant60[k] += 1
apres = collections.Counter((a["k"], a["gr"]) for a in A if a["j"] >= C)
print("== publie : reventes moyennes ; part avec >=1 revente ; cartes")
for L in ORD:
    ks = [k for k in lettre if lettre[k] == L]
    v = [apres.get(k, 0) for k in ks]
    print(f"{L:3} n={len(ks):6} moy={sum(v)/len(v):.3f}  p1={sum(1 for x in v if x)/len(v):.3f}  prixmed={st.median(st.median(pmed[k]) for k in ks):7.1f}  vues60j_moy={sum(avant60[k] for k in ks)/len(ks):.2f}")
print("\n== meme liquidite d'avant (ventes de la carte dans les 60 j avant C) : part avec >=1 revente")
bins = [(0, 0), (1, 1), (2, 4), (5, 9), (10, 999)]
print("     " + "".join(f"{str(b):>18}" for b in bins))
for L in ORD:
    row = []
    for lo, hi in bins:
        ks = [k for k in lettre if lettre[k] == L and lo <= avant60[k] <= hi]
        v = [apres.get(k, 0) for k in ks]
        row.append(f"{(sum(1 for x in v if x)/len(v) if len(v) >= 100 else float('nan')):7.3f} (n={len(ks):5})")
    print(f"{L:3}  " + "  ".join(row))
print("\n== par sorte de carte (ra) : part avec >=1 revente, A+ contre A (>=100 cartes)")
for r, _ in collections.Counter(ra.values()).most_common(30):
    out = []
    for L in ORD:
        ks = [k for k in lettre if lettre[k] == L and ra[k] == r]
        if len(ks) >= 100:
            v = [apres.get(k, 0) for k in ks]
            out.append(f"{L}:{sum(1 for x in v if x)/len(v):.3f}/{sum(v)/len(v):.2f}({len(ks)})")
    print(f"{r:14}", "  ".join(out))
print("\n== composition de A+ et de A par sorte")
for L in ("A+", "A", "A-", "B+"):
    c = collections.Counter(ra[k] for k in lettre if lettre[k] == L)
    n = sum(c.values())
    print(L, [(r, round(x / n, 2)) for r, x in c.most_common(8)])
