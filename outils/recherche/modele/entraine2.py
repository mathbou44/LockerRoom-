# Meme apprentissage en marchant que entraine.py, sur le jeu large (70 criteres), + lecture par joueur.
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))); import cache_recherche as cr   # 23 nov 2026 : plus de pickle (Aikido)
import pandas as pd, numpy as np, entraine as e, warnings; warnings.filterwarnings('ignore')
from scipy.stats import spearmanr
d = cr.charger_df('jeu2.csv.gz'); d['typ'] = d.typ.astype('category'); d['grn'] = d.gr
C = [c for c in d.columns if c not in {'t', 'nom', 'gr', 'pe', 'ey30', 'ey60', 'ey90', 'nm'}]
e.df = d
for c, gap in (('ey30', 46), ('ey60', 76), ('ey90', 106)):
    P, mo = e.marche(c, gap, crit=C)
    imp = pd.Series(mo.booster_.feature_importance('gain'), index=C).sort_values(ascending=False)
    print('criteres qui comptent :', ', '.join(f'{k} {100*v/imp.sum():.0f}%' for k, v in imp.head(10).items()))
    J = P.groupby(['fold', 't', 'nom']).agg(pred=('pred', 'mean'), y=(c, 'median'), n=(c, 'size')).reset_index(); J = J[J.n >= 3]; q = J.groupby('t').pred.rank(pct=True)
    for lab, s in (('JOUEUR 20 % du bas', q <= .2), ('JOUEUR milieu', (q > .4) & (q < .6)), ('JOUEUR 20 % du haut', q >= .8)):
        g = J[s].y; print(f"  {lab:20s} n={len(g):4d} ({J[s].nom.nunique()} joueurs) mediane {100*(np.exp(g.median())-1):+5.1f}% en hausse {100*(g>0).mean():3.0f}% en baisse {100*(g<0).mean():3.0f}%")
