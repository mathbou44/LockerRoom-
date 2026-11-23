# La FORCE du signal ACHETE : un petit modele apprend, sur les signaux d'avant aout 2026, lesquels ont le mieux marche,
# puis on le juge sur les signaux d'apres (jamais vus). Criteres : seulement des choses publiques le soir du match.
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))); import cache_recherche as cr   # 23 nov 2026 : plus de pickle (Aikido)
import gzip, json, math, bisect, collections, datetime as dt
import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
import rejoue as R, signal_joueur as sj
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.ensemble import GradientBoostingRegressor
from scipy.stats import spearmanr
D = R.D; O = R.O
NH = {n.lower(): [(O(g[0]), g[1], g[2]) for g in (v.get('matchs') or [])] for n, v in D['nhl'].items()}
WK = {}
for nom, v in D['wiki'].items():
    ds = sorted(v)
    if len(ds) > 70: WK[nom.lower()] = (O(ds[0]), np.array([v[x] for x in ds], float))
rows = []
for nom, d, cas, e, s in R.SIG:
    if s not in ('ACHETE',) and not (e == 'panne'): continue
    G = NH.get(nom) or []; i = next((k for k, g in enumerate(G) if g[0] == d), None)
    if i is None: continue
    pts = [g[1] for g in G]; base = sum(pts[max(0, i - 40):i]) / max(1, min(i, 40)); y = dt.date.fromordinal(d)
    debut = dt.date(sj.saison(d), 10, 1).toordinal()
    f = dict(nom=nom, d=d, cas=cas, ev=e, sig=s, pts=G[i][1], buts=G[i][2], base=base, surprise=G[i][1] - base, jeune=int(cas == 'jeune'), chapeau=int(G[i][2] >= 3),
             jours_saison=d - debut, pts5=sum(pts[max(0, i - 4):i + 1]), pts5_avant=sum(pts[max(0, i - 5):i]), repos=d - G[i - 1][0] if i else 9)
    w = WK.get(nom)
    if w and 70 <= d - w[0] < len(w[1]):
        x = d - w[0]; f['pop'] = math.log(w[1][x - 67:x - 7].mean() + 1); f['buzz7'] = math.log((w[1][x - 6:x + 1].mean() + 1) / (w[1][x - 67:x - 7].mean() + 1))
    f['y'] = R.mesure(nom, d, (8, 60), True); f['y_tout'] = R.mesure(nom, d, (8, 60)); f['y1'] = R.mesure(nom, d, (1, 1))
    rows.append(f)
T = pd.DataFrame(rows); T['yy'] = T.y.where(T.y.notna(), T.y_tout)
A = T[(T.sig == 'ACHETE') & T.yy.notna()].copy(); print(len(A), 'signaux ACHETE notes ;', A.nom.nunique(), 'joueurs')
C = ['pts', 'buts', 'base', 'surprise', 'jeune', 'chapeau', 'jours_saison', 'pts5', 'pts5_avant', 'repos', 'pop', 'buzz7']
A[C] = A[C].fillna(A[C].median())
tr, te = A[A.d < R.lim], A[A.d >= R.lim]; print('apprend sur', len(tr), '(avant aout 2026) ; juge sur', len(te))
p = lambda v: f"{100*(math.exp(np.median(v))-1):+5.1f}% bon {10*(np.array(v)>0).mean():.1f}/10 (n={len(v)})"
for lab, mo in (('lineaire', Ridge(alpha=30)), ('arbres', GradientBoostingRegressor(n_estimators=150, max_depth=2, learning_rate=0.03, subsample=0.8, min_samples_leaf=20, random_state=1))):
    mu, sd = tr[C].mean(), tr[C].std() + 1e-9
    mo.fit((tr[C] - mu) / sd, tr.yy.clip(-1, 1)); pr = mo.predict((te[C] - mu) / sd); q = pd.Series(pr).rank(pct=True).values
    print(f"{lab}: IC hors echantillon {spearmanr(pr, te.yy)[0]:+.3f} | tiers du bas {p(te.yy[q <= 1/3])} | milieu {p(te.yy[(q > 1/3) & (q <= 2/3)])} | tiers du HAUT {p(te.yy[q > 2/3])}")
    if lab == 'lineaire': print('   poids :', ', '.join(f'{c} {w:+.3f}' for c, w in sorted(zip(C, mo.coef_), key=lambda x: -abs(x[1]))))
# lecture simple, critere par critere, sur les deux periodes
print('\ncritere par critere (jours 8 a 60) :'.ljust(40), 'avant aout 2026'.ljust(34), '| depuis')
def dc(lab, s):
    print(f'  {lab:38s}', (p(tr.yy[s[tr.index]]) if s[tr.index].sum() >= 12 else '-').ljust(34), '|', p(te.yy[s[te.index]]) if s[te.index].sum() >= 12 else '-')
dc('tous', A.pts >= 0); dc('surprise >= +2,5 points', A.surprise >= 2.5); dc('surprise < +2', A.surprise < 2); dc('2 buts et plus', A.buts >= 2); dc('moins de 2 buts', A.buts < 2)
dc('joueur a moins de 0,7 pt/match', A.base < 0.7); dc('joueur a 0,7-1,0', (A.base >= 0.7) & (A.base < 1.0)); dc('etoile (1,0+)', A.base >= 1.0)
dc('debut de saison (60 premiers jours)', A.jours_saison <= 60); dc('milieu', (A.jours_saison > 60) & (A.jours_saison <= 150)); dc('fin de saison et series (150 j+)', A.jours_saison > 150)
dc('deja chaud (5 pts+ sur les 5 d\'avant)', A.pts5_avant >= 5); dc('froid avant (<=2 pts sur les 5 d\'avant)', A.pts5_avant <= 2)
dc('tres populaire (Wikipedia haut)', A['pop'] >= A['pop'].quantile(.67)); dc('peu populaire', A['pop'] <= A['pop'].quantile(.33)); dc('jeune', A.jeune == 1); dc('veteran', A.jeune == 0)
cr.sauver_df(T, 'signaux_notes.csv.gz')
