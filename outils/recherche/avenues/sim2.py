"""Suite de sim.py : la regle « prix <= mediane » choisit des ventes qui ont fini bas ; dans un encan, on ne connait pas le
prix final d'avance. Deux bornes : (haut) on paie le prix de la vente ; (bas) on paie la MEDIANE (sa mise maximale) chaque fois
que la vente a fini a la mediane ou dessous. Et 3 dates de fin (la valeur = mediane des ventes d'apres la date)."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))); import cache_recherche as cr   # 23 nov 2026 : plus de pickle (Aikido)
import collections, statistics as st, bisect, datetime as dt, sys, random, json
import os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))   # la racine du depot
import liquidite
A = cr.charger("A.json.gz")
PMIN, FIXE, ENCAN = 30.0, 86.0, 82.0
par = collections.defaultdict(list)
for a in A: par[(a["k"], a["gr"])].append((a["j"], a["p"]))
idx = {k: ([j for j, _ in sorted(v)], [p for _, p in sorted(v)]) for k, v in par.items()}
def moins(j, n): return (dt.date.fromisoformat(j) - dt.timedelta(days=n)).isoformat()
SIG = {}
def sig(a):
    k = (a["k"], a["gr"]); js, ps = idx[k]
    i = bisect.bisect_left(js, a["j"]); i90 = bisect.bisect_left(js, moins(a["j"], 90))
    return i - bisect.bisect_left(js, moins(a["j"], 60)), (liquidite.mediane_recente(list(zip(js[i90:i], ps[i90:i])), a["j"], avant=True) if i > i90 else None)
def sim(C, regle, payer_med=False, runs=400, seed=3):
    fin = {k: st.median([p for j, p in v if j >= C]) for k, v in par.items() if any(j >= C for j, p in v)}
    d = dt.date(2025, 11, 1); P = []
    while d.isoformat() < C:
        n_ = (d.replace(day=1) + dt.timedelta(days=32)).replace(day=1); P.append((d.isoformat(), min(n_.isoformat(), C))); d = n_
    pools = {pp: [] for pp in P}
    for n, a in enumerate(A):
        if not ("2025-11-01" <= a["j"] < C) or not (PMIN <= a["p"] <= 150): continue
        k = (a["k"], a["gr"])
        if k not in fin: continue
        if n not in SIG: SIG[n] = sig(a)
        liq, med = SIG[n]
        if not regle(a["s"], a["p"], liq, med): continue
        cout = med if (payer_med and med is not None) else a["p"]
        for pp in P:
            if pp[0] <= a["j"] < pp[1]: pools[pp].append((k, cout, a["nom"])); break
    rng = random.Random(seed); F = []
    for _ in range(runs):
        deja, parj, inv, val = set(), collections.Counter(), 0, 0
        for pp in P:
            L = pools[pp][:]; rng.shuffle(L); reste = 500
            for k, p, nom in L:
                if k in deja or p > reste or parj[nom] >= 4: continue
                deja.add(k); parj[nom] += 1; reste -= p; inv += p; val += fin[k]
                if reste < PMIN: break
        F.append((inv, val))
    return F
R = {"hasard": lambda s, p, liq, med: True,
     "lettre A et plus (le site)": lambda s, p, liq, med: s >= FIXE,
     "Radar Pro (A-, 8 ventes, <= mediane)": lambda s, p, liq, med: s >= ENCAN and liq >= 8 and med is not None and p <= med,
     "A et plus, <= mediane": lambda s, p, liq, med: s >= FIXE and med is not None and p <= med,
     "A et plus, 8 ventes, <= mediane": lambda s, p, liq, med: s >= FIXE and liq >= 8 and med is not None and p <= med}
for C in ("2026-08-31", "2026-09-27", "2026-10-29"):
    print("=== fin", C)
    base = None
    for nom, r in R.items():
        for pm in ((False, True) if "mediane" in nom else (False,)):
            F = sim(C, r, pm)
            ret = np.array([v / i for i, v in F]); g = np.array([v - i for i, v in F]); inv = np.array([i for i, v in F])
            if base is None: base = (ret, g)
            print(f"  {nom:38s} {'paie la MEDIANE' if pm else 'paie le prix   '}  {100 * (np.median(ret) - 1):+6.1f} %   mis {np.median(inv):5.0f} $   gain {np.median(g):+5.0f} $   ecart {np.median(g - base[1]):+5.0f} $   bat le hasard {100 * np.mean(ret > base[0]):3.0f} %")
