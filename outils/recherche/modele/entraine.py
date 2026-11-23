# Apprentissage « en marchant » : on entraine sur le passe, on predit le mois suivant jamais vu, on avance d'un mois.
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))); import cache_recherche as cr   # 23 nov 2026 : plus de pickle (Aikido)
import pandas as pd, numpy as np, datetime as dt, lightgbm as lgb, sys, warnings
from scipy.stats import spearmanr
warnings.filterwarnings('ignore')
df = cr.charger_df('jeu.csv.gz')
for h in ('y30', 'y60', 'y90'): df['e' + h] = df[h] - df.pe
df['typ'] = df.typ.astype('category'); df['grc'] = (df.gr > 0).astype(int); df['grn'] = df.gr
CRIT = ['p0', 'n30', 'r30', 'r90', 'r7', 'macd', 'ema30_90', 'sma200', 'haut', 'bas', 'disp', 'vol', 'age', 'grn', 'typ',
        'j_r30', 'j_r90', 'j_r7', 'j_macd', 'j_ema30_90', 'j_vol', 'j_nc', 'j_part', 'f5', 'f15', 'base', 'repos', 'wk7', 'wk30', 'wkmax', 'wkniv',
        'm_r30', 'm_r7', 'm_macd']
O = lambda s: dt.date.fromisoformat(s).toordinal()
def mois_suiv(y, m): return (y + (m == 12), m % 12 + 1)
FRAIS = lambda lr: np.exp(lr) * (1 - 0.1325) - 1   # net de 13,25 % (le 0,40 $ est neglige ici)
def marche(cible, gap, debut=(2025, 11), fin=(2026, 10), crit=CRIT, relatif=True, verb=True):
    d = df[df[cible].notna()].copy(); d[cible] = d[cible].clip(-1.5, 1.5)
    y, m = debut; P = []
    while (y, m) <= fin:
        a = dt.date(y, m, 1).toordinal(); y2, m2 = mois_suiv(y, m); b = dt.date(y2, m2, 1).toordinal()
        tr = d[d.t + gap < a]; te = d[(d.t >= a) & (d.t < b)]
        if len(tr) > 1500 and len(te) > 100:
            yt = tr[cible] - (tr.groupby('t')[cible].transform('median') if relatif else 0)
            mo = lgb.LGBMRegressor(n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=40, subsample=0.8, subsample_freq=1,
                                   colsample_bytree=0.7, reg_lambda=5, objective='huber', verbose=-1, random_state=1)
            mo.fit(tr[crit], yt); te = te.copy(); te['pred'] = mo.predict(te[crit]); te['fold'] = f'{y}-{m:02d}'; P.append(te)
        y, m = y2, m2
    P = pd.concat(P)
    if verb:
        print(f'\n=== cible {cible} ({"relatif au marche" if relatif else "absolu"}), {len(P)} cas jamais vus, {P.nom.nunique()} joueurs')
        print('mois      n    IC    | 20 % du BAS predit: med, hausse% | 20 % du HAUT predit: med, hausse%, net de frais')
        for f, g in P.groupby('fold'):
            q = g.pred.rank(pct=True); lo, hi = g[q <= .2][cible], g[q >= .8][cible]
            print(f"{f} {len(g):5d} {spearmanr(g.pred, g[cible])[0]:+.3f} | {100*(np.exp(lo.median())-1):+6.1f}% {100*(lo>0).mean():3.0f}% | {100*(np.exp(hi.median())-1):+6.1f}% {100*(hi>0).mean():3.0f}%  {100*FRAIS(hi.median()):+6.1f}%")
        q = P.groupby('fold').pred.rank(pct=True)
        for nomq, s in (('BAS 10 %', q <= .1), ('BAS 20 %', q <= .2), ('milieu', (q > .4) & (q < .6)), ('HAUT 20 %', q >= .8), ('HAUT 10 %', q >= .9), ('HAUT 5 %', q >= .95)):
            g = P[s][cible]; print(f"  {nomq:10s} n={len(g):5d} mediane {100*(np.exp(g.median())-1):+6.1f}%  en hausse {100*(g>0).mean():3.0f}%  net de frais median {100*FRAIS(g.median()):+6.1f}%  gagnants nets {100*(FRAIS(g)>0).mean():3.0f}%")
    return P, mo
if __name__ == '__main__':
    P30, mo = marche('ey30', 46); cr.sauver_df(P30, 'p30.csv.gz')
    imp = pd.Series(mo.booster_.feature_importance('gain'), index=CRIT).sort_values(ascending=False)
    print('\ncriteres qui comptent (gain) :', ', '.join(f'{k} {100*v/imp.sum():.0f}%' for k, v in imp.head(14).items()))
    P60, mo = marche('ey60', 76); cr.sauver_df(P60, 'p60.csv.gz')
    marche('ey30', 46, relatif=False)
    # reference naive : seulement le rendement 30 j de la carte
    marche('ey30', 46, crit=['r30'])
