import json, collections, random, statistics as st
random.seed(7)
H = [o for o in json.load(open("/tmp/v26/histo_14_double.json")) if o.get("autres")]
def sj(o):
    a = o["autres"]; return "hausse" if a["net"] and a["pct"] >= 5 else "baisse" if a["net"] and a["pct"] <= -5 else "neutre"
def ic(L, cle, n=600):
    pj = collections.defaultdict(list)
    for o in L: pj[o["jn"]].append(o[cle])
    js = list(pj); r = []
    for _ in range(n):
        e = [x for j in random.choices(js, k=len(js)) for x in pj[j]]; r.append(st.median(e))
    r.sort(); return r[int(.05 * n)], r[int(.95 * n)]
def ligne(nom, L, cle="f30"):
    L = [o for o in L if o.get(cle) is not None]
    nj = len({o["jn"] for o in L})
    if len(L) < 20 or nj < 8:
        print(f"  {nom:34} trop peu ({len(L)} mesures, {nj} joueurs)"); return
    top = [j for j, _ in collections.Counter(o["jn"] for o in L).most_common(5)]
    sans = [o for o in L if o["jn"] not in top]
    pj = collections.defaultdict(list)
    for o in L: pj[o["jn"]].append(o[cle])
    votes = [st.median(v) for v in pj.values()]
    lo, hi = ic(L, cle)
    s5 = f"{st.median(o[cle] for o in sans):+5.1f}" if len(sans) >= 12 else "  n/d"
    print(f"  {nom:34} n={len(L):4d} joueurs={nj:3d} | {cle} {st.median(o[cle] for o in L):+5.1f} % [{lo:+5.1f} ; {hi:+5.1f}] | sans les 5 plus gros {s5} | un joueur = une voix {st.median(votes):+5.1f} ({sum(v > 0 for v in votes)} en hausse, {sum(v < 0 for v in votes)} en baisse) | top : {top[0]} {collections.Counter(o['jn'] for o in L)[top[0]]}")
print(len(H), "mesures avec le marche du joueur ;", len({o["jn"] for o in H}), "joueurs")
for cle in ("f30", "f60"):
    print("====", cle)
    for sc in ("hausse", "stable", "baisse"):
        for sp in ("hausse", "neutre", "baisse"):
            ligne(f"carte {sc} / joueur {sp}", [o for o in H if o["sens"] == sc and sj(o) == sp], cle)
