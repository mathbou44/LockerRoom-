# On REJOUE l'histoire jour par jour : chaque soir de match (et chaque pic de nouvelles) le signal est calcule avec ce qu'on savait
# ce soir-la, puis note sur LA MEME CARTE : prix des 7 jours d'avant contre prix des jours 8 a 60 apres.
# « Bon conseil » : ACHETE -> le prix a monte ; VENDS et ATTENDS -> le prix a baisse.
import pickle, gzip, json, math, bisect, collections, datetime as dt, sys
import numpy as np
import signal_joueur as sj
O = lambda s: dt.date.fromisoformat(s).toordinal()
by = pickle.load(open('by2.pkl', 'rb')); D = json.load(gzip.open('/mnt/user-data/uploads/Downloads/slabiq_donnees.json.gz', 'rt'))
REC = ('yg', 'fw_auto', 'rc_auto', 'cup_rpa', 'premier_rpa', 'ice_premieres', 'opc_plat')
CJ = collections.defaultdict(list); AR = collections.defaultdict(collections.Counter)
for (k, g), S in by.items():
    if k[1] and str(S[0][3]).startswith(REC): AR[k[0]][k[1]] += len(S)
    L = sorted((s[0], math.log(s[1])) for s in S if s[1] >= 3)
    if len(L) >= 3: CJ[k[0]].append((np.array([x[0] for x in L]), np.array([x[1] for x in L]), S[0][5], k[1]))
# la saison recrue = la PLUS VIEILLE annee de ses cartes recrues (3 ventes et plus) : le mode prenait Ovechkin et Crosby pour des jeunes
# (leurs « Young Guns Renewed » recentes se vendent plus que leurs vraies recrues de 2005)
RY = {n: min(y for y, k in c.items() if k >= 3) for n, c in AR.items() if any(k >= 3 for k in c.values())}
# ---- les signaux, soir par soir
SIG = []
gm = collections.defaultdict(set)
for nom, v in D['nhl'].items():
    G = v.get('matchs') or []; nom = nom.lower()
    G = [(O(g[0]), g[1], g[2]) for g in G]
    for i in range(len(G)):
        d = G[i][0]; cas = sj.cas_joueur(RY.get(nom), d); evs = sj.evenements(G, i, cas)
        if 'gros' in evs: gm[nom].add(d)
        if evs:
            s, raison, e = sj.signal(cas, evs); SIG.append((nom, d, cas, e, s))
for nom, v in D['wiki'].items():
    ds = sorted(v); a = np.array([v[x] for x in ds], float); dern = -99; nom = nom.lower()
    for i in range(67, len(a)):
        if a[i] >= 3 * a[i - 67:i - 7].mean():
            d = O(ds[i])
            if a[i] >= 400 and i - dern > 21 and not gm[nom] & {d, d - 1, d - 2}:
                cas = sj.cas_joueur(RY.get(nom), d); s, raison, e = sj.signal(cas, ['pic']); SIG.append((nom, d, cas, e, s))
            dern = i
# ---- la note : meme carte, avant / apres
def mesure(nom, d, fen, fort=None):
    v = []
    for ds, lp, so, an in CJ.get(nom, ()):
        if fort is not None and (so >= 88) != fort: continue
        a, b = bisect.bisect_left(ds, d - 7), bisect.bisect_left(ds, d)
        if b <= a: continue
        x, y = bisect.bisect_left(ds, d + fen[0]), bisect.bisect_right(ds, d + fen[1])
        if y > x: v.append(float(np.median(lp[x:y]) - np.median(lp[a:b])))
    return float(np.median(v)) if v else None
def espacer(L, j=14):
    out = []; der = {}
    for x in sorted(L, key=lambda e: e[1]):
        if x[1] - der.get((x[0], x[3]), -999) >= j: out.append(x)
        der[(x[0], x[3])] = x[1]
    return out
SIG = espacer(SIG); lim = O('2026-08-01')
def ligne(lab, L, sens, fen=(8, 60), fort=None):
    R = [(mesure(n, d, fen, fort), d, n) for n, d, *_ in L]; R = [r for r in R if r[0] is not None]
    if len(R) < 20: return f'{lab:44s} trop peu ({len(R)})'
    def f(X):
        if len(X) < 12: return '      -        '
        v = np.array([x[0] for x in X]); bon = (v > 0).mean() if sens > 0 else (v < 0).mean()
        return f"{100*(math.exp(np.median(v))-1):+5.1f}% bon {10*bon:3.1f}/10 ({len(X):3d})"
    return f"{lab:44s} {len({r[2] for r in R}):3d} j. | {f(R)} | avant aout 26 : {f([r for r in R if r[1] < lim])} | depuis : {f([r for r in R if r[1] >= lim])}"
if __name__ == '__main__':
    print(len(SIG), 'signaux ;', len(RY), 'joueurs avec annee recrue connue')
    print('\nSIGNAL (cas / evenement)'.ljust(45), '       | jours 8 a 60 : mediane, bon conseil sur 10 (cas)')
    G = collections.defaultdict(list)
    for x in SIG: G[(x[4], x[2], x[3])].append(x)
    for k in sorted(G):
        print(ligne(f'{k[0]:8s} {k[1]:8s} {k[2]}', G[k], 1 if k[0] == 'ACHETE' else -1))
    print()
    for s, sens in (('ACHETE', 1), ('VENDS', -1), ('ATTENDS', -1)):
        L = [x for x in SIG if x[4] == s]
        print(ligne(f'TOUS LES {s}', L, sens)); print(ligne('   le lendemain seulement', L, sens, (1, 1))); print(ligne('   jours 2 a 7', L, sens, (2, 7))); print(ligne('   jours 8 a 30', L, sens, (8, 30))); print(ligne('   jours 31 a 60', L, sens, (31, 60)))
        print(ligne('   cartes fortes selon SlabIQ (YG, auto, RPA)', L, sens, fort=True)); print(ligne('   cartes ordinaires', L, sens, fort=False))
    pickle.dump(SIG, open('signaux.pkl', 'wb'))
