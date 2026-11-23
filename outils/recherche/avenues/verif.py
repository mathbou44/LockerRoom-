import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))); import cache_recherche as cr   # 23 nov 2026 : plus de pickle (Aikido)
import collections, statistics as st
from radar import regle, bilan
P = cr.charger("P5.json.gz")
C = [("actuelle", 82, 5, .10), ("liq 8", 82, 8, .10), ("liq 8 <= med", 82, 8, 0.0), ("liq 12 <= med", 82, 12, 0.0)]
print("== variete : cartes et joueurs distincts parmi les achats (fenetre du 22 nov), part du joueur le plus present, part des YG")
S0 = P["22 nov"]
for nom, note, liq, rab in C:
    S = [x for x in S0 if regle(x, note, liq, rab)]
    ck = {(x["a"]["k"], x["a"]["gr"]) for x in S}
    pj = collections.Counter(x["a"]["nom"] for x in S)
    ra = collections.Counter(x["a"]["ra"] for x in S)
    pr = sorted(x["a"]["p"] for x in S)
    print(f"{nom:14} achats={len(S):5} cartes={len(ck):4} joueurs={len(pj):4} top={pj.most_common(3)} sortes={[(r, round(n/len(S), 2)) for r, n in ra.most_common(4)]} prix med={st.median(pr):.0f} q1={pr[len(pr)//4]:.0f} q3={pr[3*len(pr)//4]:.0f}")
print("\n== un achat par carte (chaque carte compte une fois par fenetre) : le % tient-il ?")
for w in P:
    out = []
    for nom, note, liq, rab in C:
        S = [x for x in P[w] if regle(x, note, liq, rab)]
        par = collections.defaultdict(list)
        for x in S: par[(x["a"]["k"], x["a"]["gr"])].append(x["ok"])
        v = [sum(o) / len(o) for o in par.values()]
        out.append(f"{nom}: {sum(v)/len(v)*100:5.1f} ({len(v)})")
    print(f"{w:8}", "   ".join(out))
print("\n== un joueur ne compte qu'une fois par fenetre")
for w in P:
    out = []
    for nom, note, liq, rab in C:
        S = [x for x in P[w] if regle(x, note, liq, rab)]
        par = collections.defaultdict(list)
        for x in S: par[x["a"]["nom"]].append(x["ok"])
        v = [sum(o) / len(o) for o in par.values()]
        out.append(f"{nom}: {sum(v)/len(v)*100:5.1f} ({len(v)})")
    print(f"{w:8}", "   ".join(out))
