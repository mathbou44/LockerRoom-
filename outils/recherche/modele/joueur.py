import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))); import cache_recherche as cr   # 23 nov 2026 : plus de pickle (Aikido)
import pandas as pd, numpy as np, warnings; warnings.filterwarnings('ignore')
from scipy.stats import spearmanr
from sklearn.tree import DecisionTreeRegressor, export_text
for nomf, c in (('p30.csv.gz','ey30'),('p60.csv.gz','ey60')):
    P=cr.charger_df(nomf)
    J=P.groupby(['fold','t','nom']).agg(pred=('pred','mean'), y=(c,'median'), n=(c,'size')).reset_index()
    J=J[J.n>=3]
    q=J.groupby('t').pred.rank(pct=True)
    print(f'\n== JOUEUR ({c}) : {len(J)} joueur-semaines (>=3 cartes), {J.nom.nunique()} joueurs ; IC {spearmanr(J.pred,J.y)[0]:+.3f}')
    for lab,s in (('VENDS/ATTENDS (20 % du bas)',q<=.2),('milieu',(q>.4)&(q<.6)),('20 % du haut',q>=.8),('10 % du haut',q>=.9)):
        g=J[s].y; print(f"  {lab:28s} n={len(g):4d} joueurs={J[s].nom.nunique():3d} mediane {100*(np.exp(g.median())-1):+5.1f}%  en hausse {100*(g>0).mean():3.0f}%  en baisse {100*(g<0).mean():3.0f}%")
    ic=J.groupby('fold').apply(lambda g: spearmanr(g.pred,g.y)[0] if len(g)>15 else np.nan)
    print('  IC par mois:',' '.join(f'{k[2:]}:{v:+.2f}' for k,v in ic.items()), ' positifs',int((ic>0).sum()),'/',int(ic.notna().sum()))
    b=J[q<=.1].groupby('nom').size().sort_values(ascending=False).head(8); print('  souvent en bas:',dict(b))
P=cr.charger_df('p60.csv.gz')
C=['r30','r90','r7','macd','ema30_90','sma200','haut','bas','vol','age','j_r30','j_r90','j_part','f5','f15','base','repos','wk7','wk30','wkmax','p0','grn','disp','n30']
q=P.groupby('fold').pred.rank(pct=True)
print('\nprofil du 10 % du bas vs le reste (medianes) :')
for c in C: print(f'  {c:9s} bas {P[q<=.1][c].median():+7.2f}   haut10 {P[q>=.9][c].median():+7.2f}   tous {P[c].median():+7.2f}')
tr=DecisionTreeRegressor(max_depth=3,min_samples_leaf=300).fit(P[C].fillna(-99),P.pred)
print(export_text(tr,feature_names=C))
