"""23 nov 2026 (Mathieu, devant le graphique « 500 $ de cartes par mois pendant un an » : « toujours vrai ou on fait encore mieux ? ») :
la simulation du site (memes definitions que tests_site.mesures : 400 collectionneurs, 500 $ par mois, cartes de 30 a 150 $,
valeur = mediane des ventes d'apres le 29 oct 2026) rejouee avec d'autres regles d'achat : la lettre seule (le site), puis
la regle du Radar Pro (ventes en 60 jours, prix contre la mediane des 90 jours d'AVANT l'achat : rien du futur)."""
import pickle, collections, statistics as st, bisect, datetime as dt, sys, random, json
import os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))   # la racine du depot
import liquidite
A = pickle.load(open("A.pkl", "rb"))
C, PMIN, FIXE, ENCAN = "2026-10-29", 30.0, 86.0, 82.0
par = collections.defaultdict(list)
for a in A:
    par[(a["k"], a["gr"])].append((a["j"], a["p"]))
idx = {k: ([j for j, _ in sorted(v)], [p for _, p in sorted(v)]) for k, v in par.items()}
fin = {k: st.median([p for j, p in v if j >= C]) for k, v in par.items() if any(j >= C for j, p in v)}
def moins(j, n): return (dt.date.fromisoformat(j) - dt.timedelta(days=n)).isoformat()
d = dt.date(2025, 11, 1)
ventes = []
for a in A:
    if not (d.isoformat() <= a["j"] < C): continue
    k = (a["k"], a["gr"])
    if not (PMIN <= a["p"] <= 150) or k not in fin: continue
    js, ps = idx[k]
    i = bisect.bisect_left(js, a["j"])
    liq = i - bisect.bisect_left(js, moins(a["j"], 60))
    i90 = bisect.bisect_left(js, moins(a["j"], 90))
    med = liquidite.mediane_recente(list(zip(js[i90:i], ps[i90:i])), a["j"], avant=True) if i > i90 else None
    ventes.append((a["j"], k, a["p"], a["s"], a["nom"], liq, med, a.get("ra")))
P = []
while d.isoformat() < C:
    n_ = (d.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
    P.append((d.isoformat(), min(n_.isoformat(), C))); d = n_
mens = collections.defaultdict(dict)
for k, v in par.items():
    dd = collections.defaultdict(list)
    for j, p in v: dd[j[:7]].append(p)
    for mo, l in dd.items(): mens[k][mo] = st.median(l)
def courbes(regle, runs=400, seed=3):
    pools = {pp: [(k, p, s, j, nom) for j, k, p, s, nom, liq, med, ra in ventes if pp[0] <= j < pp[1] and regle(s, p, liq, med, ra)] for pp in P}
    rng = random.Random(seed); Cs = []
    for _ in range(runs):
        tenus, deja, parj, cur, inv = [], set(), collections.Counter(), [], 0
        for pp in P:
            L = pools[pp][:]; rng.shuffle(L); reste = 500
            for k, p, s, j, nom in L:
                if k in deja or p > reste or parj[nom] >= 4: continue
                deja.add(k); parj[nom] += 1; tenus.append((k, p, j)); reste -= p; inv += p
                if reste < PMIN: break
            cur.append((inv, 0))
        cur[-1] = (inv, sum(fin[k] for k, _, _ in tenus))
        Cs.append((cur, len(tenus), len({nom for nom in parj})))
    return [c[0][-1] for c in Cs], [len(v) for v in pools.values()], [c[1] for c in Cs], [c[2] for c in Cs], [[c[0][i][0] for c in Cs] for i in range(len(P))]
REGLES = {
    "au hasard (seul)": lambda s, p, liq, med, ra: True,
    "lettre A et plus (le site)": lambda s, p, liq, med, ra: s >= FIXE,
    "Radar Pro d'avant (A-, 5 ventes, +10 %)": lambda s, p, liq, med, ra: s >= ENCAN and liq >= 5 and med is not None and p <= med * 1.10,
    "Radar Pro (A-, 8 ventes, <= mediane)": lambda s, p, liq, med, ra: s >= ENCAN and liq >= 8 and med is not None and p <= med,
    "A et plus, 8 ventes, <= mediane": lambda s, p, liq, med, ra: s >= FIXE and liq >= 8 and med is not None and p <= med,
    "A et plus, <= mediane (sans les 8 ventes)": lambda s, p, liq, med, ra: s >= FIXE and med is not None and p <= med,
    "hasard, <= mediane (sans lettre)": lambda s, p, liq, med, ra: med is not None and p <= med,
    "hasard, 8 ventes, <= mediane (sans lettre)": lambda s, p, liq, med, ra: liq >= 8 and med is not None and p <= med,
}
out = {}
base = None
for nom, r in REGLES.items():
    F, pools, nb, nj, invm = courbes(r)
    ret = np.array([v / i if i else np.nan for i, v in F]); gain = np.array([v - i for i, v in F]); inv = np.array([i for i, v in F])
    if base is None: base = (ret, gain)
    o = dict(rendement=round(float(np.nanmedian(ret)) - 1, 4), mis=round(float(np.median(inv))), gain=round(float(np.median(gain))), ecart=round(float(np.median(gain - base[1]))),
             bat=round(float(np.mean(ret > base[0])), 3), p10=round(float(np.percentile(gain - base[1], 10))), p90=round(float(np.percentile(gain - base[1], 90))),
             cartes=round(float(np.median(nb))), joueurs=round(float(np.median(nj))), pools=pools, mis_par_mois=[round(float(np.median(x))) for x in invm])
    out[nom] = o
    print(f"{nom:46s} rendement {o['rendement']*100:+6.1f} %  mis {o['mis']:5d} $  gain {o['gain']:+5d} $  ecart {o['ecart']:+5d} $ (p10 {o['p10']:+d}, p90 {o['p90']:+d})  bat le hasard {o['bat']*100:3.0f} %  cartes {o['cartes']} joueurs {o['joueurs']}")
    print("    cartes offertes par mois :", pools)
json.dump(out, open("sim_resultats.json", "w"), indent=1)
