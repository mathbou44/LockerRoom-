# Jeu LARGE : memes lignes que jeu.py (carte exacte + grade, semaine t) mais chaque famille de criteres a plusieurs fenetres
# (medianes, moyennes simples, moyennes exponentielles, hauts/bas, volume, forme, nouvelles). Aucun critere ne lit apres t.
import pickle, gzip, json, math, re, bisect, collections, datetime as dt, sys
import numpy as np, pandas as pd
by = pickle.load(open('/tmp/an/by.pkl', 'rb'))
D = json.load(gzip.open('/mnt/user-data/uploads/Downloads/slabiq_donnees.json.gz', 'rt'))
O = lambda s: dt.date.fromisoformat(s).toordinal()
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
def saison(k):
    m = re.search(r'\b(19|20)(\d\d)-(\d\d)\b', k)
    if m: return int(m.group(1) + m.group(2))
    m = re.search(r'\b(19[5-9]\d|20[0-2]\d)\b', k)
    return int(m.group(1)) if m else None
SER = {}
for k, S in by.items():
    G = collections.defaultdict(list)
    for s in S:
        if s[1] >= 3: G[s[4]].append((s[0], s[1]))
    for gr, L in G.items():
        if len(L) < 4: continue
        L.sort(); SER[(k, gr)] = (np.array([x[0] for x in L]), np.log([x[1] for x in L]), S[0][2].lower(), S[0][5], saison(k))
allD = np.sort(np.concatenate([v[0] for v in SER.values()]))
nmar = lambda a, b: bisect.bisect_right(allD, b) - bisect.bisect_right(allD, a)
NAN = float('nan')
T0, T1 = O('2025-03-03'), O('2026-11-16')
JC = ['r_60', 'r_90', 'r_180', 'r_365', 'r7', 'r14', 'e3_14', 'e7_30', 'e14_60', 'e30_120', 'sma200', 'vol', 'vol14', 'haut200', 'bas200']
rows = []
for t in range(T0, T1 + 1, 7):
    cart = {}; m30, m90, m14, m46 = nmar(t - 30, t), nmar(t - 120, t - 30), nmar(t - 14, t), nmar(t - 60, t - 14)
    for key, (ds, lp, nom, typ, y0) in SER.items():
        j = bisect.bisect_right(ds, t); i30 = bisect.bisect_right(ds, t - 30)
        if j - i30 < 2: continue
        B = lambda d: bisect.bisect_right(ds, t - d)
        def md(a, b):      # mediane des ventes de t-a a t-b (a > b)
            x, y = B(a), B(b); return float(np.median(lp[x:y])) if y > x else NAN
        def mn(a):
            x = B(a); return float(lp[x:j].mean())
        def em(demi):
            x = B(6 * demi); w = 0.5 ** ((t - ds[x:j]) / demi); return float((w * lp[x:j]).sum() / w.sum())
        p0 = float(np.median(lp[i30:j])); f = {'t': t, 'nom': nom, 'typ': typ, 'gr': key[1], 'p0': p0, 'n30': j - i30}
        f['r_60'] = p0 - md(60, 30); f['r_90'] = p0 - md(90, 30); f['r_180'] = p0 - md(180, 30); f['r_365'] = p0 - md(365, 30); f['r_90_365'] = md(90, 30) - md(365, 90)
        f['r7'] = md(7, 0) - p0; f['r14'] = md(14, 0) - p0
        E = {h: em(h) for h in (3, 7, 14, 30, 60, 120)}
        f['e3_14'] = E[3] - E[14]; f['e7_30'] = E[7] - E[30]; f['e14_60'] = E[14] - E[60]; f['e30_120'] = E[30] - E[120]; f['p_e60'] = p0 - E[60]; f['p_e120'] = p0 - E[120]
        f['sma60'] = p0 - mn(60); f['sma120'] = p0 - mn(120); f['sma200'] = p0 - mn(200); f['sma365'] = p0 - mn(365)
        for w in (90, 200, 365):
            x = B(w); f[f'haut{w}'] = p0 - float(lp[x:j].max()); f[f'bas{w}'] = p0 - float(lp[x:j].min())
        x = B(200); sd = float(lp[x:j].std()) if j - x >= 5 else NAN
        f['boll'] = (p0 - float(lp[x:j].mean())) / sd if sd and sd > 0.02 else NAN      # ecart a la moyenne 200 j, en ecarts-types (bandes de Bollinger)
        dl = np.diff(lp[max(0, j - 11):j]); f['rsi'] = float((dl > 0).sum() / max(1, (dl != 0).sum())) if len(dl) >= 4 else NAN   # part des hausses sur les 10 dernieres ventes
        f['disp30'] = float(lp[i30:j].std()) if j - i30 >= 3 else NAN; x = B(90); f['disp90'] = float(lp[x:j].std()) if j - x >= 4 else NAN
        f['vol'] = math.log(((j - i30) / max(m30, 1)) / ((i30 - B(120) + 0.5) / max(m90, 1)))
        x14 = B(14); f['vol14'] = math.log(((j - x14 + 0.5) / max(m14, 1)) / ((x14 - B(60) + 0.5) / max(m46, 1)))
        f['age'] = ((dt.date.fromordinal(t).year * 12 + dt.date.fromordinal(t).month - 1) - (y0 * 12 + 9)) if y0 else NAN
        a, b = bisect.bisect_right(ds, t), bisect.bisect_right(ds, t + 14)
        if b > a:
            pe = float(np.median(lp[a:b])); f['pe'] = pe - p0
            for h, (u, v) in (('ey30', (t + 15, t + 45)), ('ey60', (t + 45, t + 75)), ('ey90', (t + 75, t + 105))):
                x, y = bisect.bisect_right(ds, u), bisect.bisect_right(ds, v); f[h] = float(np.median(lp[x:y])) - pe if y > x else NAN
        cart[key] = f
    G = collections.defaultdict(list)
    for f in cart.values(): G[f['nom']].append(f)
    tot = sum(f['n30'] for f in cart.values())
    for nom, L in G.items():
        nh = NHL.get(nom); wk = WIKI.get(nom); pj = {}
        if nh:
            gd, cp, cb, cq = nh; j = bisect.bisect_right(gd, t)
            pg = lambda c, a, b: (c[b] - c[a]) / (b - a) if b > a >= 0 else NAN
            for k in (3, 5, 10, 20):
                pj[f'f{k}'] = pg(cp, j - k, j) - pg(cp, max(0, j - k - 40), j - k) if j >= k + 20 else NAN
            pj['g5'] = pg(cb, j - 5, j) - pg(cb, max(0, j - 45), j - 5) if j >= 25 else NAN
            pj['g10'] = pg(cb, j - 10, j) - pg(cb, max(0, j - 50), j - 10) if j >= 30 else NAN
            pj['serie5'] = pg(cq, j - 5, j) if j >= 5 else NAN          # part des 5 derniers matchs avec au moins 1 point
            pj['base'] = pg(cp, max(0, j - 82), j) if j >= 20 else NAN
            pj['repos'] = min(t - gd[j - 1], 200) if j else NAN; pj['nm'] = j
        if wk:
            d0, cw, a = wk; x = t - d0
            if 95 <= x < len(a):
                av = lambda n, dec=0: (cw[x + 1 - dec] - cw[x + 1 - dec - n]) / n
                w60 = av(60, 7)
                for n in (3, 7, 14, 30): pj[f'wk{n}'] = math.log((av(n) + 1) / (w60 + 1))
                pj['wkmax'] = math.log((a[x - 13:x + 1].max() + 1) / (w60 + 1)); pj['wkniv'] = math.log(w60 + 1); pj['wk30_90'] = math.log((av(30) + 1) / (av(60, 30) + 1))
        nj = sum(f['n30'] for f in L)
        for f in L:
            aut = [g for g in L if g is not f]
            for c in JC:
                v = [g[c] for g in aut if g[c] == g[c]]
                f['j_' + c] = float(np.median(v)) if len(v) >= 2 else NAN
            f['j_nc'] = len(L); f['j_part'] = math.log(nj / tot); f.update(pj)
            f['ecart90'] = f['r_90'] - f['j_r_90']; f['ecart60'] = f['r_60'] - f['j_r_60']; f['ecart7'] = f['r7'] - f['j_r7']     # paires : la carte contre les autres cartes du joueur
    for c in ('r_90', 'r7', 'e7_30'):
        v = [f[c] for f in cart.values() if f[c] == f[c]]; mm = float(np.median(v)) if v else NAN
        for f in cart.values(): f['m_' + c] = mm
    rows.extend(cart.values()); print(dt.date.fromordinal(t), len(cart), file=sys.stderr)
df = pd.DataFrame(rows); df.to_pickle('jeu2.pkl'); print(len(df), len(df.columns), df[['ey30', 'ey60', 'ey90']].notna().sum().to_dict())
