# Grande recherche de regles : toutes les paires de conditions (critere x seuil) x filtre d'age x horizon.
# On CHOISIT sur le passe (train), on JUGE une seule fois sur la periode suivante jamais regardee (test). Sinon, avec un million d'essais,
# on trouve toujours une regle « parfaite » par chance.
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))); import cache_recherche as cr   # 23 nov 2026 : plus de pickle (Aikido)
import pandas as pd, numpy as np, datetime as dt, sys, warnings; warnings.filterwarnings('ignore')
df = cr.charger_df('jeu2.csv.gz'); O = lambda s: dt.date.fromisoformat(s).toordinal()
EXCL = {'t', 'nom', 'typ', 'gr', 'pe', 'ey30', 'ey60', 'ey90', 'nm'}
F = [c for c in df.columns if c not in EXCL]
FRAIS = lambda lr: np.exp(lr) * (1 - 0.1325) - 1
pc = lambda x: f"{100*(np.exp(x)-1):+5.1f}%"
def recherche(h, test0, K=25, nmin=200, sortie=None):
    c = f'ey{h}'; d = df[df[c].notna()].copy(); d['ex'] = (d[c] - d.groupby('t')[c].transform('median')).clip(-1, 1); d['y'] = d[c].clip(-1.5, 1.5)
    a = O(test0); tr = d[d.t <= a - (h + 31)]; te = d[d.t >= a]
    mid = tr.t.median(); print(f'\n######## horizon {h} j : train {len(tr)} lignes (jusqu\'au {dt.date.fromordinal(int(tr.t.max()))}), test {len(te)} lignes (du {test0})')
    atoms = []; Mtr = []; Mte = []
    for f in F:
        x = tr[f].values; xt = te[f].values
        if np.isfinite(x).sum() < 800: continue
        for q in (.1, .2, .3, .7, .8, .9):
            s = np.nanquantile(x, q)
            if q < .5: m, mt, lab = x <= s, xt <= s, f'{f} <= {s:+.2f}'
            else: m, mt, lab = x >= s, xt >= s, f'{f} >= {s:+.2f}'
            if m.sum() < nmin or m.mean() > 0.6: continue
            atoms.append(lab); Mtr.append(m); Mte.append(mt)
    atoms.append('(seul)'); Mtr.append(np.ones(len(tr), bool)); Mte.append(np.ones(len(te), bool))
    Mtr = np.array(Mtr, dtype=np.float32); Mte = np.array(Mte, dtype=np.float32); A = len(atoms)
    res = []
    for flab, ftr, fte in (('tout age', np.ones(len(tr), bool), np.ones(len(te), bool)), ('carte < 10 mois', (tr.age <= 9).values, (te.age <= 9).values), ('carte >= 10 mois', (tr.age > 9).values, (te.age > 9).values)):
        def stats(M, dd, filt, demi=None):
            w = filt.astype(np.float32) if demi is None else (filt & demi).astype(np.float32)
            Mw = M * w
            return Mw @ M.T, (Mw * dd.ex.values.astype(np.float32)) @ M.T, (Mw * (dd.y.values > 0)) @ M.T, (Mw * dd.y.values.astype(np.float32)) @ M.T
        n, sx, hit, sy = stats(Mtr, tr, ftr)
        n1, sx1, _, _ = stats(Mtr, tr, ftr, (tr.t <= mid).values); n2, sx2 = n - n1, sx - sx1
        nt, sxt, hitt, syt = stats(Mte, te, fte)
        iu = np.triu_indices(A)
        R = pd.DataFrame({'i': iu[0], 'j': iu[1], 'n': n[iu], 'mx': sx[iu] / np.maximum(n[iu], 1), 'm1': sx1[iu] / np.maximum(n1[iu], 1), 'm2': sx2[iu] / np.maximum(n2[iu], 1), 'n1': n1[iu], 'n2': n2[iu],
                          'hit': hit[iu] / np.maximum(n[iu], 1), 'nt': nt[iu], 'mxt': sxt[iu] / np.maximum(nt[iu], 1), 'hitt': hitt[iu] / np.maximum(nt[iu], 1), 'myt': syt[iu] / np.maximum(nt[iu], 1)})
        R['age'] = flab; res.append(R)
    R = pd.concat(res); tot = len(R); R = R[(R.n >= nmin) & (R.n1 >= 60) & (R.n2 >= 60)]
    R['score'] = R.mx * np.sqrt(R.n) * np.where(np.sign(R.m1) == np.sign(R.m2), 1, 0)
    print(f'{tot} regles essayees, {len(R)} avec assez de cas en train')
    V = R[R.nt >= 80]; print(f'la recherche se generalise-t-elle ? correlation (ecart train, ecart test) sur {len(V)} regles : {np.corrcoef(V.mx, V.mxt)[0,1]:+.3f}')
    base = te.y; print(f'temoin test : toutes les cartes mediane {pc(base.median())}, en hausse {100*(base>0).mean():.0f}%')
    out = {}
    for sens, lab in ((1, 'ACHETE (meilleures en train)'), (-1, 'ATTENDS / VENDS (pires en train)')):
        top = R.sort_values('score', ascending=(sens < 0)).head(400); vus = set(); k = 0; rows = []
        print(f'\n-- {lab} : jugees sur le test')
        for _, r in top.iterrows():
            cle = (atoms[int(r.i)].split()[0], atoms[int(r.j)].split()[0], r.age)
            if cle in vus or r.nt < 60: continue
            vus.add(cle); k += 1
            fa = {'tout age': np.ones(len(te), bool), 'carte < 10 mois': (te.age <= 9).values, 'carte >= 10 mois': (te.age > 9).values}[r.age]
            g = te[(Mte[int(r.i)] > 0) & (Mte[int(r.j)] > 0) & fa]
            rows.append((r.mx, r.mxt, g.y.median(), (g.y > 0).mean(), len(g), g.nom.nunique()))
            if k <= 12:
                print(f"  [{r.age:16s}] {atoms[int(r.i)]:22s} & {atoms[int(r.j)]:22s} | train n={int(r.n):4d} ecart {pc(r.mx)} hausse {100*r.hit:2.0f}% | TEST n={len(g):4d} ({g.nom.nunique():3d} j.) ecart {pc(r.mxt)} mediane {pc(g.y.median())} hausse {100*(g.y>0).mean():2.0f}% net {100*FRAIS(g.y.median()):+5.1f}%")
            if k >= K: break
        Z = np.array(rows); out[sens] = Z
        print(f"  => les {len(Z)} premieres : ecart moyen train {pc(Z[:,0].mean())} -> test {pc(Z[:,1].mean())} ; mediane test {pc(np.median(Z[:,2]))} ; en hausse {100*Z[:,3].mean():.0f}% ; {int((np.sign(Z[:,1])==sens).sum())}/{len(Z)} gardent le bon signe")
    if sortie is not None: cr.sauver_df(R.assign(a=[atoms[int(i)] for i in R.i], b=[atoms[int(j)] for j in R.j]), sortie)
    return out
if __name__ == '__main__':
    recherche(30, '2026-07-06', sortie='regles30.csv.gz'); recherche(60, '2026-06-15', sortie='regles60.csv.gz'); recherche(90, '2026-04-13', sortie='regles90.csv.gz')
