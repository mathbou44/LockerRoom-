# Etude d'evenements AU JOUR PRES sur l'indice du joueur : que fait le prix les jours qui suivent
#  (a) un gros match (3 points et plus, ou 2 buts et plus), (b) un pic de nouvelles (Wikipedia x3), (c) une panne (5 matchs sans point pour un bon joueur).
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))); import cache_recherche as cr   # 23 nov 2026 : plus de pickle (Aikido)
import gzip, json, math, bisect, collections, datetime as dt, sys, runpy
import numpy as np
sys.argv = ['x']; O = lambda s: dt.date.fromisoformat(s).toordinal()
by = cr.charger('by2.json.gz'); D = json.load(gzip.open('/mnt/user-data/uploads/Downloads/slabiq_donnees.json.gz', 'rt'))
PJ = collections.defaultdict(list)
for (k, g), S in by.items():
    for s in S:
        if s[1] >= 3: PJ[k[0]].append((s[0], math.log(s[1]), (k, g)))
IND = {}
for nom, L in PJ.items():
    if len(L) < 150: continue
    L.sort(key=lambda x: x[0]); FE = collections.defaultdict(list); rd, rv = [], []; idx = 0.0; i = 0; w = L[0][0] // 7
    while i < len(L):
        j = i
        while j < len(L) and L[j][0] // 7 == w: j += 1
        for d, lp, c in L[i:j]:
            f = FE.get(c)
            if f: rd.append(d); rv.append(lp - float(np.median(f[-12:])))
        fin = w * 7 + 6
        for fen in (14, 30):
            a = bisect.bisect_right(rd, fin - fen)
            if len(rd) - a >= 3: idx = float(np.median(rv[a:])); break
        for d, lp, c in L[i:j]: FE[c].append(lp - idx)
        i = j; w = L[i][0] // 7 if i < len(L) else w
    if len(rd) >= 60: IND[nom] = (np.array(rd), np.array(rv))
FEN = [(-30, -8), (-7, -1), (0, 0), (1, 1), (2, 3), (4, 7), (8, 14), (15, 30), (31, 60)]
def etude(lab, EV, ref=(-7, -1), nmin=2):
    R = collections.defaultdict(list); nev = 0
    for nom, d in EV:
        if nom not in IND: continue
        rd, rv = IND[nom]
        def m(a, b):
            x, y = bisect.bisect_left(rd, d + a), bisect.bisect_right(rd, d + b); return float(np.median(rv[x:y])) if y - x >= nmin else None
        b0 = m(*ref)
        if b0 is None: continue
        nev += 1
        for f in FEN:
            v = m(*f)
            if v is not None: R[f].append(v - b0)
    print(f'\n{lab} : {nev} evenements mesurables ({len({n for n, _ in EV if n in IND})} joueurs)')
    for f in FEN:
        v = np.array(R[f])
        if len(v) >= 25: print(f"   jours {f[0]:+3d} a {f[1]:+3d} : {100*(math.exp(np.median(v))-1):+5.1f}%  (au-dessus {100*(v>0).mean():2.0f}%, n={len(v)})")
    return R
NHL = {n.lower(): v.get('matchs') or [] for n, v in D['nhl'].items()}
gros, buts2, pannes, feu5, normal = [], [], [], [], []
for nom, G in NHL.items():
    if len(G) < 45: continue
    pts = [g[1] for g in G]
    for i in range(40, len(G)):
        base = sum(pts[i - 40:i]) / 40; d = O(G[i][0])
        if G[i][1] >= 3: gros.append((nom, d))
        if G[i][2] >= 2: buts2.append((nom, d))
        if base >= 0.6 and sum(pts[i - 4:i + 1]) == 0 and sum(pts[i - 5:i]) > 0: pannes.append((nom, d))          # 5e match de suite sans point (le premier jour ou ca arrive)
        if sum(pts[i - 4:i + 1]) >= 5 * (base + 0.6) and sum(pts[i - 5:i]) < 5 * (base + 0.6): feu5.append((nom, d))   # 5 matchs a +0,6 pt/match au-dessus de sa base
        if i % 7 == 0: normal.append((nom, d))
etude('TEMOIN : un match ordinaire', normal)
etude('GROS MATCH (3 points et plus)', gros); etude('2 BUTS et plus', buts2)
etude('EN FEU : 5 matchs a +0,6 pt/match au-dessus de sa base (premier jour)', feu5)
etude('PANNE : 5 matchs de suite sans point pour un joueur a 0,6 pt/match et plus', pannes)
pics = []
for nom, v in D['wiki'].items():
    ds = sorted(v); a = np.array([v[d] for d in ds], float); dern = -99
    for i in range(67, len(a)):
        b = a[i - 67:i - 7].mean()
        if a[i] >= 3 * b and a[i] >= 400 and i - dern > 21: pics.append((nom.lower(), O(ds[i]))); dern = i
        elif a[i] >= 3 * b: dern = i
etude('PIC DE NOUVELLES (Wikipedia x3, 400 vues et plus, premier jour)', pics)
cr.sauver({'gros': gros, 'pics': pics, 'feu5': feu5, 'pannes': pannes}, 'ev3.json.gz')
# saison 2025-26 seulement (avant aout 2026) vs debut 2026-27 : est-ce que ca tient dans les deux ?
lim = O('2026-08-01')
for lab, EV in (('GROS MATCH', gros), ('EN FEU', feu5), ('PIC', pics)):
    etude(lab + ' / avant aout 2026', [e for e in EV if e[1] < lim]); etude(lab + ' / depuis aout 2026', [e for e in EV if e[1] >= lim])
