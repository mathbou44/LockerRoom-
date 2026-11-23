import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))); import cache_recherche as cr   # 23 nov 2026 : plus de pickle (Aikido)
import labo as L, numpy as np, pandas as pd
A, B = L.charger(); C = L.criteres(B)
print(len(C), 'criteres joueur ;', B.nom.nunique(), 'joueurs')
print(B.groupby('mois')[['ey30','ey60','ey90','vey30']].count().T.to_string())
for h, gap in ((30, 46), (60, 76), (90, 106)):
    c = f'ey{h}'
    P, mo = L.marche(B, c, gap, C, nmin=800); L.bilan(P, c, f'\nJOUEUR h{h} (indice)'); cr.sauver_df(P, f'PB_{h}.csv.gz')
    v = P[P['v' + c].notna()] if 'v' + c in P else P.iloc[:0]
    if len(v) > 300: L.bilan(v, 'v' + c, '   verif. vraies cartes')
    imp = pd.Series(mo.booster_.feature_importance('gain'), index=C).sort_values(ascending=False)
    print('   criteres :', ', '.join(f'{k} {100*x/imp.sum():.0f}%' for k, x in imp.head(10).items()))
    ic = P.groupby('fold').apply(lambda g: L.spearmanr(g.pred, g[c])[0]); print('   IC par mois :', ' '.join(f'{k[2:]}:{x:+.2f}' for k, x in ic.items()))
