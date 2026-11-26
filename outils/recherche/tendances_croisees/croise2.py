import json, collections, random, statistics as st
random.seed(7)
H = [o for o in json.load(open("/tmp/v26/histo_14_double.json")) if o.get("autres")]
print("periode :", min(o["T"] for o in H), "->", max(o["T"] for o in H), "|", len(H), "mesures,", len({o["jn"] for o in H}), "joueurs,", len({(o["jn"], o["k"], o["s"]) for o in H}), "cartes")
def sj(o):
    a = o["autres"]; return "hausse" if a["net"] and a["pct"] >= 5 else "baisse" if a["net"] and a["pct"] <= -5 else "neutre"
def stat(nom, L, cle):
    L = [o for o in L if o.get(cle) is not None]
    pj = collections.defaultdict(list)
    for o in L: pj[o["jn"]].append(o[cle])
    js = list(pj); r = []
    for _ in range(2000):
        e = [x for j in random.choices(js, k=len(js)) for x in pj[j]]; r.append(st.median(e))
    r.sort()
    votes = [st.median(v) for v in pj.values()]
    top = [j for j, _ in collections.Counter(o["jn"] for o in L).most_common(5)]
    sans = [o[cle] for o in L if o["jn"] not in top]
    d = dict(n=len(L), joueurs=len(js), cartes=len({(o["jn"], o["k"], o["s"]) for o in L}), med=round(st.median(o[cle] for o in L), 1), ic90=[round(r[100], 1), round(r[1899], 1)], ic95=[round(r[50], 1), round(r[1949], 1)],
             baissent=sum(v < 0 for v in votes), montent=sum(v > 0 for v in votes), sans5=round(st.median(sans), 1) if len(sans) >= 12 else None, part_baisse=round(sum(1 for o in L if o[cle] < 0) / len(L), 2))
    print(f"{nom:44} {cle} {d}")
    return d
for cle in ("f30", "f60"):
    stat("A carte hausse / joueur neutre (monte seule)", [o for o in H if o["sens"] == "hausse" and sj(o) == "neutre"], cle)
    stat("B joueur baisse / carte stable ou baisse", [o for o in H if o["sens"] in ("stable", "baisse") and sj(o) == "baisse"], cle)
    stat("temoin : carte stable / joueur neutre", [o for o in H if o["sens"] == "stable" and sj(o) == "neutre"], cle)
    stat("tout", H, cle)
