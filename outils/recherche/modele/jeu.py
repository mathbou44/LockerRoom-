# Jeu de donnees du modele de timing : une ligne = (carte exacte + grade, date t). Tout ce qui est a gauche de t = criteres ; a droite = cible.
# Aucune fuite : chaque critere ne lit que des ventes <= t. Cible = prix median de la MEME carte 16-45 j (h30) et 46-75 j (h60) apres t.
import pickle, gzip, json, math, re, bisect, collections, datetime as dt, statistics as st, sys
import numpy as np
by = pickle.load(open('/tmp/an/by.pkl', 'rb'))
D = json.load(gzip.open('/mnt/user-data/uploads/Downloads/slabiq_donnees.json.gz', 'rt'))
O = lambda s: dt.date.fromisoformat(s).toordinal()
NHL = {}
for nom, v in D['nhl'].items():
    G = v.get('matchs') or []
    if len(G) >= 10:
        NHL[nom.lower()] = ([O(g[0]) for g in G], np.cumsum([0] + [g[1] for g in G]), np.cumsum([0] + [g[2] for g in G]))
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

# series par (carte, grade)
SER = {}; PJ = collections.defaultdict(list)
for k, S in by.items():
    G = collections.defaultdict(list)
    for s in S:
        if s[1] >= 3: G[s[4]].append((s[0], s[1]))
    for gr, L in G.items():
        if len(L) < 4: continue
        L.sort(); ds = np.array([x[0] for x in L]); lp = np.log([x[1] for x in L])
        SER[(k, gr)] = (ds, lp, S[0][2].lower(), S[0][5], saison(k))
        PJ[S[0][2].lower()].append((k, gr))
print('series', len(SER), 'joueurs', len(PJ), file=sys.stderr)
# volume total du marche par jour (pour normaliser : la collecte grossit avec le temps, pas le marche)
allD = np.sort(np.concatenate([v[0] for v in SER.values()]))
def nmar(a, b): return bisect.bisect_right(allD, b) - bisect.bisect_right(allD, a)

def med(ds, lp, a, b):   # mediane des log-prix dans ]a, b]
    i = bisect.bisect_right(ds, a); j = bisect.bisect_right(ds, b)
    return (float(np.median(lp[i:j])), j - i) if j > i else (None, 0)
def ema(ds, lp, t, demi):
    j = bisect.bisect_right(ds, t); i = bisect.bisect_right(ds, t - 6 * demi)
    if j <= i: return None
    w = 0.5 ** ((t - ds[i:j]) / demi); return float((w * lp[i:j]).sum() / w.sum())

T0, T1 = O('2025-03-03'), O('2026-11-16')
rows = []
for t in range(T0, T1 + 1, 7):
    cart = {}
    for key, (ds, lp, nom, typ, y0) in SER.items():
        p0, n0 = med(ds, lp, t - 30, t)
        if n0 < 2: continue
        f = {'t': t, 'nom': nom, 'typ': typ, 'gr': key[1], 'p0': p0, 'n30': n0}
        p1, n1 = med(ds, lp, t - 90, t - 30); p2, n2 = med(ds, lp, t - 365, t - 90); p7, n7 = med(ds, lp, t - 7, t)
        f['r30'] = p0 - p1 if n1 else np.nan            # prix vs les 31-90 j d'avant (le « rendement 30 jours »)
        f['r90'] = p0 - p2 if n2 else np.nan
        f['r7'] = p7 - p0 if n7 else np.nan             # derniere semaine vs le mois
        e7, e30, e90 = ema(ds, lp, t, 7), ema(ds, lp, t, 30), ema(ds, lp, t, 90)
        f['macd'] = e7 - e30; f['ema30_90'] = e30 - e90   # croisements de moyennes mobiles exponentielles
        s200, ns = med(ds, lp, t - 200, t)
        j = bisect.bisect_right(ds, t); i = bisect.bisect_right(ds, t - 200)
        f['sma200'] = p0 - float(lp[i:j].mean())          # prix vs sa moyenne simple 200 j
        f['haut'] = p0 - float(lp[i:j].max()); f['bas'] = p0 - float(lp[i:j].min())   # distance du haut / du bas 200 j
        i30 = bisect.bisect_right(ds, t - 30)
        f['disp'] = float(lp[i30:j].std()) if j - i30 >= 3 else np.nan
        m30, m90 = nmar(t - 30, t), nmar(t - 120, t - 30)
        f['vol'] = math.log((n0 / max(m30, 1)) / ((n1 + med(ds, lp, t - 120, t - 90)[1] + 0.5) / max(m90, 1)))   # part de marche des ventes, maintenant vs avant
        f['age'] = ((dt.date.fromordinal(t).year * 12 + dt.date.fromordinal(t).month - 1) - (y0 * 12 + 9)) if y0 else np.nan
        for h, (a, b) in (('y30', (t + 15, t + 45)), ('y60', (t + 45, t + 75)), ('y90', (t + 75, t + 105))):
            q, nq = med(ds, lp, a, b); f[h] = q - p0 if nq else np.nan
        pe, ne = med(ds, lp, t, t + 14); f['pe'] = pe - p0 if ne else np.nan; f['ne'] = ne   # prix d'entree REEL : ventes des 14 j APRES le signal (independant du bruit des criteres)
        cart[key] = f
    # criteres du joueur : mediane de ses AUTRES cartes + forme + nouvelles
    G = collections.defaultdict(list)
    for key, f in cart.items(): G[f['nom']].append(f)
    tot = sum(f['n30'] for f in cart.values())
    for nom, L in G.items():
        nh = NHL.get(nom); wk = WIKI.get(nom); pj = {}
        if nh:
            gd, cp, cb = nh; j = bisect.bisect_right(gd, t)
            def ppg(a, b):
                return (cp[b] - cp[a]) / (b - a) if b > a >= 0 else np.nan
            pj['f5'] = ppg(j - 5, j) - ppg(max(0, j - 45), j - 5) if j >= 30 else np.nan
            pj['f15'] = ppg(j - 15, j) - ppg(max(0, j - 55), j - 15) if j >= 40 else np.nan
            pj['base'] = ppg(max(0, j - 82), j) if j >= 20 else np.nan
            pj['repos'] = min(t - gd[j - 1], 200) if j else np.nan
            pj['nm'] = j
        if wk:
            d0, cw, a = wk; x = t - d0
            if 75 <= x < len(a):
                w7 = (cw[x + 1] - cw[x - 6]) / 7; w60 = (cw[x - 6] - cw[x - 66]) / 60; w30 = (cw[x + 1] - cw[x - 29]) / 30
                pj['wk7'] = math.log((w7 + 1) / (w60 + 1)); pj['wk30'] = math.log((w30 + 1) / (w60 + 1))
                pj['wkmax'] = math.log((a[x - 13:x + 1].max() + 1) / (w60 + 1)); pj['wkniv'] = math.log(w60 + 1)
        nj = sum(f['n30'] for f in L)
        for f in L:
            aut = [g for g in L if g is not f]
            for c in ('r30', 'r90', 'r7', 'macd', 'ema30_90', 'vol'):
                v = [g[c] for g in aut if g[c] == g[c]]
                f['j_' + c] = float(np.median(v)) if len(v) >= 2 else np.nan
            f['j_nc'] = len(L); f['j_part'] = math.log(nj / tot)
            f.update(pj)
    # marche : mediane de toutes les cartes cette semaine
    for c in ('r30', 'r7', 'macd'):
        v = [f[c] for f in cart.values() if f[c] == f[c]]; mm = float(np.median(v)) if v else np.nan
        for f in cart.values(): f['m_' + c] = mm
    rows.extend(cart.values())
    print(dt.date.fromordinal(t), len(cart), file=sys.stderr)
import pandas as pd
df = pd.DataFrame(rows); df.to_pickle('jeu.pkl')
print(len(df), df[['y30', 'y60', 'y90']].notna().sum().to_dict())
