# Verification la plus directe : LA MEME CARTE, avant (7 j avant l'evenement) et apres. Pas d'indice, pas de modele.
# + replication sur deux periodes (avant / depuis aout 2026) + un seul evenement par joueur par 14 j (cas independants).
import pickle, math, bisect, collections, datetime as dt
import numpy as np
O = lambda s: dt.date.fromisoformat(s).toordinal()
by = pickle.load(open('by2.pkl', 'rb')); E = pickle.load(open('ev4.pkl', 'rb')); ev3 = pickle.load(open('ev3.pkl', 'rb'))
CJ = collections.defaultdict(list)
for (k, g), S in by.items():
    L = sorted((s[0], math.log(s[1])) for s in S if s[1] >= 3)
    if len(L) >= 3: CJ[k[0]].append((np.array([x[0] for x in L]), np.array([x[1] for x in L])))
FEN = [(0, 0), (1, 1), (2, 7), (8, 30), (31, 60)]
def espacer(EV, j=14):
    out = []; der = {}
    for nom, d in sorted(EV, key=lambda e: e[1]):
        if d - der.get(nom, -999) >= j: out.append((nom, d))
        der[nom] = d
    return out
def etude(lab, EV, mini=25, esp=True):
    if esp: EV = espacer(EV)
    R = collections.defaultdict(list); J = set()
    for nom, d in EV:
        for f in FEN:
            v = []
            for ds, lp in CJ.get(nom, ()):
                a, b = bisect.bisect_left(ds, d - 7), bisect.bisect_left(ds, d)
                if b <= a: continue
                x, y = bisect.bisect_left(ds, d + f[0]), bisect.bisect_right(ds, d + f[1])
                if y > x: v.append(float(np.median(lp[x:y]) - np.median(lp[a:b])))
            if v: R[f].append(float(np.median(v))); J.add(nom)
    n = max((len(R[f]) for f in FEN), default=0)
    if n < mini: print(f'{lab:50s} trop peu ({n})'); return
    s = ' | '.join((f"{100*(math.exp(np.median(R[f]))-1):+5.1f}% ({100*(np.array(R[f])>0).mean():2.0f}%h, {len(R[f]):3d})" if len(R[f]) >= 15 else '      -         ') for f in FEN)
    print(f'{lab:50s} {len(J):3d} j. | {s}')
print('meme carte, vs ses 7 j d\'avant'.ljust(50), '       | jour meme       | lendemain       | j2-7            | j8-30           | j31-60')
lim = O('2026-08-01'); ev = dict(E); ev['PIC nouvelles (Wikipedia x3)'] = ev3['pics']
gm = collections.defaultdict(set)
for nom, d in E['3 points+'] + E['2 buts+']: gm[nom].add(d)
ev['PIC sans gros match'] = [(n, d) for n, d in ev3['pics'] if not gm[n] & {d, d - 1, d - 2}]
ev['GROS MATCH (3 pts+ ou 2 buts+)'] = sorted(set(E['3 points+'] + E['2 buts+']))
for k in ['0 point (temoin)', '2 points (bon match)', 'GROS MATCH (3 pts+ ou 2 buts+)', '3 points+', '4 points+', '2 buts+', 'tour du chapeau', 'EN FEU (debut)', 'PANNE 4 matchs (0,5+)', 'PANNE 5 matchs (0,6+)', 'PIC nouvelles (Wikipedia x3)', 'PIC sans gros match',
          'ABSENCE (blessure probable, vue 6 j apres)']:
    etude(k, ev[k])
    if k in ('GROS MATCH (3 pts+ ou 2 buts+)', 'EN FEU (debut)', 'PANNE 4 matchs (0,5+)', 'PIC sans gros match', 'tour du chapeau', '0 point (temoin)'):
        etude('   avant aout 2026', [e for e in ev[k] if e[1] < lim], mini=15); etude('   depuis aout 2026', [e for e in ev[k] if e[1] >= lim], mini=15)
print()
for k in ['3 points+ / jeune', '3 points+ / veteran', '3 points+ / etoile (0,9+)', '3 points+ / bon (0,5-0,9)', '2 buts+ / jeune', '2 buts+ / veteran', 'EN FEU / jeune', 'EN FEU / veteran', 'EN FEU / etoile (0,9+)', 'EN FEU / bon (0,5-0,9)']:
    etude(k, E[k])
