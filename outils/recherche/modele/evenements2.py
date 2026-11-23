# Evenements, par CAS : la reaction depend-elle du joueur (recrue, etoile), de la taille du match, de la periode ?
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))); import cache_recherche as cr   # 23 nov 2026 : plus de pickle (Aikido)
import gzip, json, math, bisect, collections, datetime as dt, sys
import numpy as np
O = lambda s: dt.date.fromisoformat(s).toordinal()
import evenements as _e          # memes donnees et meme indice que evenements.py (il affiche d'abord sa propre etude)
D, PJ, IND = _e.D, _e.PJ, _e.IND
NHL = {n.lower(): v.get('matchs') or [] for n, v in D['nhl'].items()}
# age median des cartes vendues du joueur (annee de la carte) -> recrue de l'annee ?
AN = {}
for nom, L in PJ.items():
    a = [c[0][1] for _, _, c in L if c[0][1]]
    if a: AN[nom] = float(np.median(a))
FEN = [(0, 0), (1, 1), (2, 7), (8, 30), (31, 60)]
def etude(lab, EV, ref=(-7, -1), nmin=2, mini=30):
    R = collections.defaultdict(list); nev = 0; J = set()
    for nom, d in EV:
        if nom not in IND: continue
        rd, rv = IND[nom]
        def m(a, b):
            x, y = bisect.bisect_left(rd, d + a), bisect.bisect_right(rd, d + b); return float(np.median(rv[x:y])) if y - x >= nmin else None
        b0 = m(*ref)
        if b0 is None: continue
        nev += 1; J.add(nom)
        for f in FEN:
            v = m(*f)
            if v is not None: R[f].append(v - b0)
    if nev < mini: print(f'{lab:58s} trop peu ({nev})'); return
    s = ' | '.join(f"j{f[0]}{'-'+str(f[1]) if f[1]!=f[0] else ''}: {100*(math.exp(np.median(R[f]))-1):+5.1f}% ({100*(np.array(R[f])>0).mean():2.0f}%, n={len(R[f])})" if len(R[f]) >= 15 else f"j{f[0]}: -" for f in FEN)
    print(f'{lab:58s} {nev:4d} ev, {len(J):3d} j. | {s}')
E = collections.defaultdict(list)
for nom, G in NHL.items():
    if len(G) < 45: continue
    pts = [g[1] for g in G]; ds = [O(g[0]) for g in G]
    for i in range(40, len(G)):
        base = sum(pts[i - 40:i]) / 40; d = ds[i]; y = dt.date.fromordinal(d); sais = y.year - (y.month < 8)
        rec = AN.get(nom, 0) >= sais                     # ses cartes sont surtout de cette saison = recrue de l'annee
        jeune = (not rec) and AN.get(nom, 0) >= sais - 2
        cas = 'recrue' if rec else 'jeune' if jeune else 'veteran'
        niv = 'etoile (0,9+)' if base >= 0.9 else 'bon (0,5-0,9)' if base >= 0.5 else 'soutien (<0,5)'
        p, b = G[i][1], G[i][2]
        if p >= 3: E['3 points+'].append((nom, d)); E['3 points+ / ' + cas].append((nom, d)); E['3 points+ / ' + niv].append((nom, d))
        if p >= 4: E['4 points+'].append((nom, d))
        if b >= 2: E['2 buts+'].append((nom, d)); E['2 buts+ / ' + cas].append((nom, d)); E['2 buts+ / ' + niv].append((nom, d))
        if b >= 3: E['tour du chapeau'].append((nom, d))
        if p == 2: E['2 points (bon match)'].append((nom, d))
        if p == 0 and i % 5 == 0: E['0 point (temoin)'].append((nom, d))
        if i >= 41 and ds[i] - ds[i - 1] >= 12 and 10 <= ((y.month - 10) % 12) <= 6 + 12 and y.month not in (7, 8, 9, 10): E['RETOUR apres 12 j+ d\'absence'].append((nom, d))
        if sum(pts[i - 4:i + 1]) >= 5 * (base + 0.6) and sum(pts[i - 5:i]) < 5 * (base + 0.6): E['EN FEU (debut)'].append((nom, d)); E['EN FEU / ' + cas].append((nom, d)); E['EN FEU / ' + niv].append((nom, d))
        if base >= 0.6 and sum(pts[i - 4:i + 1]) == 0 and sum(pts[i - 5:i]) > 0: E['PANNE 5 matchs (0,6+)'].append((nom, d))
        if base >= 0.5 and sum(pts[i - 3:i + 1]) == 0 and sum(pts[i - 4:i]) > 0: E['PANNE 4 matchs (0,5+)'].append((nom, d))
    # absence : dernier match suivi de 12 j+ sans match, en pleine saison (le jour ou on le sait : 6 j apres le dernier match)
    for i in range(40, len(G) - 1):
        y = dt.date.fromordinal(ds[i])
        if ds[i + 1] - ds[i] >= 12 and y.month in (11, 12, 1, 2, 3): E['ABSENCE (blessure probable, vue 6 j apres)'].append((nom, ds[i] + 6))
for k in ['0 point (temoin)', '2 points (bon match)', '3 points+', '4 points+', '2 buts+', 'tour du chapeau', 'EN FEU (debut)', 'PANNE 4 matchs (0,5+)', 'PANNE 5 matchs (0,6+)', 'ABSENCE (blessure probable, vue 6 j apres)', "RETOUR apres 12 j+ d'absence"]:
    etude(k, E[k])
print()
for k in sorted(E):
    if ' / ' in k: etude(k, E[k])
# nouvelles SANS performance : pic Wikipedia sans gros match la veille ou le jour meme
gm = collections.defaultdict(set)
for nom, d in E['3 points+'] + E['2 buts+']: gm[nom].add(d)
ev = cr.charger('ev3.json.gz'); pics = ev['pics']
print(); etude('PIC Wikipedia AVEC gros match (j-1, j)', [(n, d) for n, d in pics if gm[n] & {d, d - 1}], mini=20)
etude('PIC Wikipedia SANS gros match', [(n, d) for n, d in pics if not gm[n] & {d, d - 1, d - 2}])
etude('PIC SANS gros match, joueur actif (LNH connue)', [(n, d) for n, d in pics if not gm[n] & {d, d - 1, d - 2} and n in NHL and len(NHL[n]) > 40])
etude('PIC, joueur sans matchs LNH (retraite, espoir)', [(n, d) for n, d in pics if n not in NHL or len(NHL[n]) <= 40])
cr.sauver(dict(E), 'ev4.json.gz')
