# Le labo : charge les tableaux (A3 cartes, B3 joueurs), definit LES CAS, et fournit l'apprentissage « en marchant ».
import pandas as pd, numpy as np, datetime as dt, lightgbm as lgb, warnings
from scipy.stats import spearmanr
warnings.filterwarnings('ignore')
FOND = ['f3', 'f5', 'f10', 'f20', 'g5', 'g10', 'serie5', 'base', 'repos', 'wk3', 'wk7', 'wk14', 'wk30', 'wkmax', 'wkniv', 'wk30_90']
pc = lambda x: f"{100*(np.exp(x)-1):+5.1f}%"
FRAIS = lambda lr: np.exp(lr) * (1 - 0.1325) - 1
def charger():
    A = pd.read_pickle('A3.pkl'); B = pd.read_pickle('B3.pkl')
    for c in FOND:                       # sur la glace + nouvelles : une seule colonne, que le joueur ait un indice ou non
        A[c] = A[c].where(A[c].notna(), A.get('j_' + c)) if 'j_' + c in A else A[c]
        if 'j_' + c in A: del A['j_' + c]
    a = A.age
    A['cas_age'] = np.select([a.isna(), a <= 9, a <= 33, a <= 120], ['inconnu', 'recrue', 'jeune', 'etabli'], 'ancien')
    A['cas'] = A.cas_age + np.where(A.gr > 0, ' gradee', ' brute')
    A['sais'] = np.select([A.repos.isna(), A.repos <= 21], [0, 1], 2)        # 0 = pas de matchs connus, 1 = en saison, 2 = saison morte / blesse
    A['grn'] = A.gr; A['typ'] = A.typ.astype('category'); A['ciec'] = A.cie.astype('category'); A['casn'] = A.cas.astype('category')
    for d in (A, B): d['mois'] = d.t.map(lambda t: dt.date.fromordinal(t).strftime('%y-%m'))
    return A, B
EXCL = {'t', 'nom', 'gr', 'cie', 'pe', 'ey30', 'ey60', 'ey90', 'vey30', 'vey60', 'vey90', 'mois', 'cas', 'cas_age', 'pred', 'fold', 'ex'}
def criteres(d): return [c for c in d.columns if c not in EXCL]
def suiv(y, m): return (y + (m == 12), m % 12 + 1)
def marche(d, cible, gap, crit, debut=(2025, 11), fin=(2026, 10), par_cas=None, classe=None, nmin=1500, arbres=300):
    """Entraine sur tout ce qui est connu avant le mois, predit le mois. par_cas : un modele par valeur de cette colonne.
    classe : None = regression de l'ecart au marche ; sinon fonction y -> 0/1 (probabilite)."""
    d = d[d[cible].notna()].copy(); d['yy'] = d[cible].clip(-1.5, 1.5)
    y, m = debut; P = []
    while (y, m) <= fin:
        a = dt.date(y, m, 1).toordinal(); y2, m2 = suiv(y, m); b = dt.date(y2, m2, 1).toordinal()
        tr = d[d.t + gap < a]; te = d[(d.t >= a) & (d.t < b)].copy()
        if len(tr) > nmin and len(te) > 50:
            te['pred'] = np.nan
            for g in ([None] if par_cas is None else sorted(te[par_cas].unique())):
                r = tr if g is None else tr[tr[par_cas] == g]; e = te.index if g is None else te.index[te[par_cas] == g]
                if len(r) < 400: r = tr                        # cas trop rare : on retombe sur le modele general
                if classe is None:
                    mo = lgb.LGBMRegressor(n_estimators=arbres, learning_rate=0.03, num_leaves=15, min_child_samples=40, subsample=0.8, subsample_freq=1, colsample_bytree=0.6, reg_lambda=5, objective='huber', verbose=-1, random_state=1)
                    mo.fit(r[crit], r.yy - r.groupby('t').yy.transform('median')); te.loc[e, 'pred'] = mo.predict(te.loc[e, crit])
                else:
                    mo = lgb.LGBMClassifier(n_estimators=arbres, learning_rate=0.03, num_leaves=15, min_child_samples=40, subsample=0.8, subsample_freq=1, colsample_bytree=0.6, reg_lambda=5, verbose=-1, random_state=1)
                    mo.fit(r[crit], classe(r.yy).astype(int)); te.loc[e, 'pred'] = mo.predict_proba(te.loc[e, crit])[:, 1]
            te['fold'] = f'{y}-{m:02d}'; P.append(te)
        y, m = y2, m2
    return pd.concat(P), mo
def bilan(P, cible, lab=''):
    q = P.groupby('fold').pred.rank(pct=True); ic = P.groupby('fold').apply(lambda g: spearmanr(g.pred, g[cible])[0])
    print(f'{lab} n={len(P)} | IC moyen {ic.mean():+.3f}, positif {int((ic>0).sum())}/{len(ic)} mois', end=' | ')
    for nom, s in (('bas20', q <= .2), ('mil', (q > .4) & (q < .6)), ('haut20', q >= .8), ('haut5', q >= .95)):
        g = P[s][cible]; print(f"{nom} {pc(g.median())} ({100*(g>0).mean():.0f}% hausse)", end=' ; ')
    print()
