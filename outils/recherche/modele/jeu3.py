# Jeu 3 : cle de carte CANONIQUE (by2.pkl, voir cle2.py) + INDICE PAR JOUEUR (le « cours de l'action » du joueur).
# Deux tableaux : A3 = une ligne par (carte, semaine) ; B3 = une ligne par (joueur, semaine).
# Tout critere ne lit que des ventes <= t. Prix d'entree = mediane des 14 j APRES t ; sorties a 30, 60 et 90 j.
import pickle, gzip, json, math, bisect, collections, datetime as dt, sys
import numpy as np, pandas as pd
by = pickle.load(open('by2.pkl', 'rb'))
D = json.load(gzip.open('/mnt/user-data/uploads/Downloads/slabiq_donnees.json.gz', 'rt'))
O = lambda s: dt.date.fromisoformat(s).toordinal(); NAN = float('nan')
NHL = {}
for nom, v in D['nhl'].items():
    G = v.get('matchs') or []
    if len(G) >= 10:
        NHL[nom.lower()] = ([O(g[0]) for g in G], np.cumsum([0] + [g[1] for g in G]), np.cumsum([0] + [g[2] for g in G]), np.cumsum([0] + [int(g[1] > 0) for g in G]))
WIKI = {}
for nom, v in D['wiki'].items():
    if len(v) >= 60:
        ds = sorted(v); d0 = O(ds[0]); a = np.zeros(O(ds[-1]) - d0 + 1)
        for d in ds: a[O(d) - d0] = v[d]
        WIKI[nom.lower()] = (d0, np.cumsum(np.concatenate([[0], a])), a)

# ---------- series par carte, et flux de ventes par joueur
SER = {}; PJ = collections.defaultdict(list)
for (k, g), S in by.items():
    L = sorted((s[0], math.log(s[1])) for s in S if s[1] >= 3)
    for d, lp in L: PJ[k[0]].append((d, lp, (k, g)))
    if len(L) >= 4: SER[(k, g)] = (np.array([x[0] for x in L]), np.array([x[1] for x in L]), k[0], S[0][3], k[1])
allD = np.sort(np.concatenate([[x[0] for x in L] for L in PJ.values()]))
nmar = lambda a, b: bisect.bisect_right(allD, b) - bisect.bisect_right(allD, a)

# ---------- indice causal par joueur : chaque vente d'une carte deja vue donne « le niveau du joueur » = prix - niveau habituel de la carte
IND = {}; PJD = {}
for nom, L in PJ.items():
    if len(L) < 150: continue
    L.sort(key=lambda x: x[0]); PJD[nom] = np.array([x[0] for x in L])
    FE = collections.defaultdict(list); rd, rv = [], []; idx = 0.0; i = 0; w = L[0][0] // 7
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
print('series', len(SER), 'joueurs avec indice', len(IND), file=sys.stderr)

def crit(ds, v, t, nmin):
    """Tous les indicateurs techniques d'une serie (dates, log-prix) vus a la date t."""
    j = bisect.bisect_right(ds, t); B = lambda d: bisect.bisect_right(ds, t - d); i30 = B(30)
    if j - i30 < nmin: return None
    def md(a, b):
        x, y = B(a), B(b); return float(np.median(v[x:y])) if y > x else NAN
    def mn(a):
        x = B(a); return float(v[x:j].mean())
    def em(demi):
        x = B(6 * demi); w = 0.5 ** ((t - ds[x:j]) / demi); return float((w * v[x:j]).sum() / w.sum())
    p0 = float(np.median(v[i30:j])); f = {'p0': p0, 'n30': j - i30}
    m60, m90 = md(60, 30), md(90, 60)
    f['r_60'] = p0 - m60; f['r_90'] = p0 - md(90, 30); f['r_180'] = p0 - md(180, 30); f['r_365'] = p0 - md(365, 30); f['r_90_365'] = md(90, 30) - md(365, 90)
    f['acc'] = (p0 - m60) - (m60 - m90)                          # acceleration : la tendance du mois contre celle du mois d'avant
    f['r7'] = md(7, 0) - p0; f['r14'] = md(14, 0) - p0
    E = {h: em(h) for h in (3, 7, 14, 30, 60, 120)}
    f['e3_14'] = E[3] - E[14]; f['e7_30'] = E[7] - E[30]; f['e14_60'] = E[14] - E[60]; f['e30_120'] = E[30] - E[120]; f['p_e60'] = p0 - E[60]; f['p_e120'] = p0 - E[120]
    f['sma60'] = p0 - mn(60); f['sma120'] = p0 - mn(120); f['sma200'] = p0 - mn(200); f['sma365'] = p0 - mn(365)
    for w in (90, 200, 365):
        x = B(w); f[f'haut{w}'] = p0 - float(np.percentile(v[x:j], 95)); f[f'bas{w}'] = p0 - float(np.percentile(v[x:j], 5))
    x = B(200); sd = float(v[x:j].std()) if j - x >= 5 else NAN
    f['boll'] = (p0 - float(v[x:j].mean())) / sd if sd and sd > 0.02 else NAN
    dl = np.diff(v[max(0, j - 11):j]); f['rsi'] = float((dl > 0).sum() / max(1, (dl != 0).sum())) if len(dl) >= 4 else NAN
    f['disp30'] = float(v[i30:j].std()) if j - i30 >= 3 else NAN; x = B(90); f['disp90'] = float(v[x:j].std()) if j - x >= 4 else NAN
    x = B(60)
    if j - x >= 6:
        dd = (ds[x:j] - t).astype(float); va = dd.var()
        f['pente60'] = float(((dd - dd.mean()) * (v[x:j] - v[x:j].mean())).mean() / va * 30) if va > 4 else NAN   # pente du prix sur 60 j, par mois
    else: f['pente60'] = NAN
    return f
def cibles(ds, v, t, nmin, f):
    a, b = bisect.bisect_right(ds, t), bisect.bisect_right(ds, t + 14)
    if b - a >= nmin:
        pe = float(np.median(v[a:b])); f['pe'] = pe - f['p0']
        for h, (u, w) in (('ey30', (t + 15, t + 45)), ('ey60', (t + 45, t + 75)), ('ey90', (t + 75, t + 105))):
            x, y = bisect.bisect_right(ds, u), bisect.bisect_right(ds, w); f[h] = float(np.median(v[x:y])) - pe if y - x >= nmin else NAN
def vol(ds, t, m):
    B = lambda d: bisect.bisect_right(ds, t - d); j = B(0)
    return (math.log(((j - B(30) + 0.5) / max(m[0], 1)) / ((B(30) - B(120) + 0.5) / max(m[1], 1))),
            math.log(((j - B(14) + 0.5) / max(m[2], 1)) / ((B(14) - B(60) + 0.5) / max(m[3], 1))))
def fond(nom, t):
    """Sur la glace (forme, buts, serie, repos) et nouvelles (Wikipedia)."""
    pj = {}; nh = NHL.get(nom); wk = WIKI.get(nom)
    if nh:
        gd, cp, cb, cq = nh; j = bisect.bisect_right(gd, t)
        pg = lambda c, a, b: (c[b] - c[a]) / (b - a) if b > a >= 0 else NAN
        for k in (3, 5, 10, 20):
            pj[f'f{k}'] = pg(cp, j - k, j) - pg(cp, max(0, j - k - 40), j - k) if j >= k + 20 else NAN
        pj['g5'] = pg(cb, j - 5, j) - pg(cb, max(0, j - 45), j - 5) if j >= 25 else NAN
        pj['g10'] = pg(cb, j - 10, j) - pg(cb, max(0, j - 50), j - 10) if j >= 30 else NAN
        pj['serie5'] = pg(cq, j - 5, j) if j >= 5 else NAN; pj['base'] = pg(cp, max(0, j - 82), j) if j >= 20 else NAN
        pj['repos'] = min(t - gd[j - 1], 200) if j else NAN
    if wk:
        d0, cw, a = wk; x = t - d0
        if 95 <= x < len(a):
            av = lambda n, dec=0: (cw[x + 1 - dec] - cw[x + 1 - dec - n]) / n
            w60 = av(60, 7)
            for n in (3, 7, 14, 30): pj[f'wk{n}'] = math.log((av(n) + 1) / (w60 + 1))
            pj['wkmax'] = math.log((a[x - 13:x + 1].max() + 1) / (w60 + 1)); pj['wkniv'] = math.log(w60 + 1); pj['wk30_90'] = math.log((av(30) + 1) / (av(60, 30) + 1))
    return pj

T0, T1 = O('2025-03-03'), O('2026-11-16'); RA, RB = [], []
for t in range(T0, T1 + 1, 7):
    m = (nmar(t - 30, t), nmar(t - 120, t - 30), nmar(t - 14, t), nmar(t - 60, t - 14)); ym = dt.date.fromordinal(t).year * 12 + dt.date.fromordinal(t).month - 1
    JJ = {}
    for nom, (rd, rv) in IND.items():
        f = crit(rd, rv, t, 5)
        if f is None: continue
        f['vol'], f['vol14'] = vol(PJD[nom], t, m); f['part'] = math.log((bisect.bisect_right(PJD[nom], t) - bisect.bisect_right(PJD[nom], t - 30) + 0.5) / max(m[0], 1))
        f.update(fond(nom, t)); JJ[nom] = f
        g = dict(f); g['t'] = t; g['nom'] = nom; cibles(rd, rv, t, 3, g); RB.append(g)
    na = 0
    for key, (ds, lp, nom, typ, an) in SER.items():
        f = crit(ds, lp, t, 2)
        if f is None: continue
        f['t'] = t; f['nom'] = nom; f['typ'] = typ; f['gr'] = key[1][1]; f['cie'] = key[1][0]; f['vol'], f['vol14'] = vol(ds, t, m)
        f['age'] = ym - (an * 12 + 9) if an else NAN
        cibles(ds, lp, t, 1, f)
        if 'pe' not in f: f['pe'] = NAN
        J = JJ.get(nom)
        if J:
            for c, x in J.items(): f['j_' + c] = x
            for c in ('r_60', 'r_90', 'r_180', 'r7', 'e7_30', 'e14_60', 'pente60'): f['ec_' + c] = f[c] - J[c]     # paires : la carte contre l'indice de son joueur
        else: f.update(fond(nom, t))
        RA.append(f); na += 1
    print(dt.date.fromordinal(t), na, len(JJ), file=sys.stderr)
A = pd.DataFrame(RA); B = pd.DataFrame(RB)
for c in ('r_90', 'r7', 'e7_30', 'pente60'):
    mm = A.groupby('t')[c].median(); A['m_' + c] = A.t.map(mm); B['m_' + c] = B.t.map(mm)
# pour le joueur : ce que ses cartes ont VRAIMENT fait (meme carte, prix reel), en verification de l'indice
for h in ('ey30', 'ey60', 'ey90'):
    x = A[A[h].notna()].groupby(['t', 'nom'])[h].agg(['median', 'size']); x = x[x['size'] >= 3]['median'].rename('v' + h)
    B = B.join(x, on=['t', 'nom'])
A.to_pickle('A3.pkl'); B.to_pickle('B3.pkl')
print('A', len(A), len(A.columns), A[['ey30', 'ey60', 'ey90']].notna().sum().to_dict()); print('B', len(B), len(B.columns), B[['ey30', 'ey60', 'ey90', 'vey30', 'vey60']].notna().sum().to_dict(), B.nom.nunique())
