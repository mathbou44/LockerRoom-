# Le jumelage avec la cote SlabIQ : au meme gros match, une carte A reagit-elle autrement qu'une carte C ?
import pickle, gzip, json, math, bisect, collections, datetime as dt
import numpy as np
O = lambda s: dt.date.fromisoformat(s).toordinal()
by = pickle.load(open('by2.pkl', 'rb')); E = pickle.load(open('ev4.pkl', 'rb')); ev3 = pickle.load(open('ev3.pkl', 'rb'))
D = json.load(gzip.open('/mnt/user-data/uploads/Downloads/slabiq_donnees.json.gz', 'rt'))
CJ = collections.defaultdict(list)
for (k, g), S in by.items():
    L = sorted((s[0], math.log(s[1])) for s in S if s[1] >= 3)
    if len(L) >= 3: CJ[k[0]].append((np.array([x[0] for x in L]), np.array([x[1] for x in L]), S[0][5], S[0][6], k[1], g[1], float(np.median([x[1] for x in L]))))
FEN = [(0, 0), (1, 1), (2, 7), (8, 30), (31, 60)]
def espacer(EV, j=14):
    out = []; der = {}
    for nom, d in sorted(EV, key=lambda e: e[1]):
        if d - der.get(nom, -999) >= j: out.append((nom, d))
        der[nom] = d
    return out
def etude(lab, EV, filtre=lambda c, d: True, mini=25):
    EV = espacer(EV); R = collections.defaultdict(list); J = set()
    for nom, d in EV:
        for f in FEN:
            v = []
            for c in CJ.get(nom, ()):
                if not filtre(c, d): continue
                ds, lp = c[0], c[1]; a, b = bisect.bisect_left(ds, d - 7), bisect.bisect_left(ds, d)
                if b <= a: continue
                x, y = bisect.bisect_left(ds, d + f[0]), bisect.bisect_right(ds, d + f[1])
                if y > x: v.append(float(np.median(lp[x:y]) - np.median(lp[a:b])))
            if v: R[f].append(float(np.median(v))); J.add(nom)
    n = max((len(R[f]) for f in FEN), default=0)
    if n < mini: print(f'{lab:52s} trop peu ({n})'); return
    s = ' | '.join((f"{100*(math.exp(np.median(R[f]))-1):+5.1f}% ({100*(np.array(R[f])>0).mean():2.0f}%h, {len(R[f]):3d})" if len(R[f]) >= 15 else '      -         ') for f in FEN)
    print(f'{lab:52s} {len(J):3d} j. | {s}')
print('meme carte, vs ses 7 j d\'avant'.ljust(52), '       | jour meme       | lendemain       | j2-7            | j8-30           | j31-60')
GM = sorted(set(E['3 points+'] + E['2 buts+'])); FEU = E['EN FEU (debut)']; PAN = E['PANNE 4 matchs (0,5+)']; POS = sorted(set(GM + FEU))
age = lambda c, d: (dt.date.fromordinal(d).year * 12 + dt.date.fromordinal(d).month - 1) - (c[4] * 12 + 9) if c[4] else None
for lab, EV in (('GROS MATCH ou EN FEU', POS), ('PANNE 4 matchs', PAN)):
    etude(lab + ' / toutes les cartes', EV)
    etude(lab + ' / cote SlabIQ A (80+)', EV, lambda c, d: c[3] >= 80)
    etude(lab + ' / cote B (65-79)', EV, lambda c, d: 65 <= c[3] < 80)
    etude(lab + ' / cote C et D (<65)', EV, lambda c, d: c[3] < 65)
    etude(lab + ' / type de carte fort (88+ : YG, auto, RPA)', EV, lambda c, d: c[2] >= 88)
    etude(lab + ' / type de carte ordinaire (<=55)', EV, lambda c, d: c[2] <= 55)
    etude(lab + ' / carte recrue (annee 1 ou 2 du joueur)', EV, lambda c, d: age(c, d) is not None and age(c, d) <= 33)
    etude(lab + ' / carte de 3 ans et plus', EV, lambda c, d: age(c, d) is not None and age(c, d) > 33)
    etude(lab + ' / gradee', EV, lambda c, d: c[5] > 0)
    etude(lab + ' / brute', EV, lambda c, d: c[5] == 0)
    print()
# (les recrues de l'annee sont traitees dans rejoue.py, avec la vraie annee de leur carte recrue)
