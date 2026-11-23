import pickle, itertools, collections, statistics as st
from radar import regle, bilan
P = pickle.load(open("P.pkl", "rb"))
ch, ju = P["choix"], P["juge"]
base_c, base_j = bilan([x for x in ch if regle(x)]), bilan([x for x in ju if regle(x)])
print("actuelle  choix", base_c, "\n          juge ", base_j)
res = []
for note, liq, rab in itertools.product((75, 82, 86, 88, 90), (2, 3, 5, 8, 12, 20, 30), (-0.10, 0.0, 0.05, 0.10, 0.25, None)):
    c, j = bilan([x for x in ch if regle(x, note, liq, rab)]), bilan([x for x in ju if regle(x, note, liq, rab)])
    if c and j: res.append((note, liq, rab, c, j))
def f(b): return f"n={b['n']:5} ok={b['ok']*100:5.1f} rev={b['rev']*100:5.1f} net={b['net']*100:5.1f}"
print("\n== choisi sur 'choix' : le meilleur 'ok' a volume >= 60 % de l'actuel ; puis juge")
for note, liq, rab, c, j in sorted([r for r in res if r[3]["n"] >= 0.6 * base_c["n"]], key=lambda r: -r[3]["ok"])[:12]:
    print(f"note>={note} liq>={liq:2} rab={rab}   choix {f(c)}   juge {f(j)}")
print("\n== meme chose a volume >= 30 %")
for note, liq, rab, c, j in sorted([r for r in res if r[3]["n"] >= 0.3 * base_c["n"]], key=lambda r: -r[3]["ok"])[:12]:
    print(f"note>={note} liq>={liq:2} rab={rab}   choix {f(c)}   juge {f(j)}")
print("\n== ou la regle actuelle rate (fenetre choix), par signal")
S = [x for x in ch if regle(x)]
def coupe(nom, fn, bornes):
    print(nom)
    for lo, hi in bornes:
        T = [x for x in S if fn(x) is not None and lo <= fn(x) < hi]
        if len(T) >= 25: print(f"   [{lo},{hi})  {f(bilan(T))}")
coupe("liq 60 j", lambda x: x["liq"], [(5, 8), (8, 12), (12, 20), (20, 40), (40, 999)])
coupe("prix", lambda x: x["a"]["p"], [(30, 50), (50, 100), (100, 200), (200, 500), (500, 1e9)])
coupe("prix / mediane", lambda x: x["a"]["p"] / x["med"] if x["med"] else None, [(0, .7), (.7, .85), (.85, .95), (.95, 1.03), (1.03, 1.11)])
coupe("tendance 30 j", lambda x: x["tend"], [(-9, -.2), (-.2, -.05), (-.05, .05), (.05, .2), (.2, 9)])
coupe("dispersion", lambda x: x["disp"], [(0, .15), (.15, .3), (.3, .5), (.5, 9)])
coupe("note", lambda x: x["a"]["s"], [(82, 86), (86, 90), (90, 95), (95, 101)])
coupe("gradee", lambda x: x["a"]["gr"], [(0, .1), (.1, 9.4), (9.4, 9.9), (9.9, 11)])
c = collections.Counter(x["a"]["ra"] for x in S)
print("sorte")
for r, n in c.most_common(12):
    T = [x for x in S if x["a"]["ra"] == r]
    if n >= 20: print(f"   {r:14} {f(bilan(T))}")
