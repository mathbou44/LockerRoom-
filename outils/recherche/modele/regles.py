import pandas as pd, numpy as np, datetime as dt
df=pd.read_pickle('jeu.pkl')
for h in ('y30','y60','y90'): df['e'+h]=df[h]-df.pe
df['mois']=df.t.map(lambda t: dt.date.fromordinal(t).strftime('%y-%m'))
F=lambda lr: np.exp(lr)*(1-0.1325)-1
def test(lab, s):
    print(f'\n## {lab}')
    for c in ('ey30','ey60','ey90'):
        g=df[s & df[c].notna()]; r=df[~s & df[c].notna()]
        if len(g)<40: print(f'  {c}: trop peu ({len(g)})'); continue
        pm=g.groupby('mois')[c].agg(['median','size']); pm=pm[pm['size']>=15]
        rm=r.groupby('mois')[c].median()
        mieux=sum(pm['median'][m] > rm[m] for m in pm.index); 
        print(f"  {c}: n={len(g)} ({g.nom.nunique()} joueurs) mediane {100*(np.exp(g[c].median())-1):+5.1f}% (les autres {100*(np.exp(r[c].median())-1):+5.1f}%)  en hausse {100*(g[c]>0).mean():.0f}% (autres {100*(r[c]>0).mean():.0f}%)  net de frais {100*F(g[c].median()):+.1f}%  gagnants nets {100*(F(g[c])>0).mean():.0f}%  | au-dessus des autres {mieux}/{len(pm)} mois")
        print('     par mois:',' '.join(f"{m}:{100*(np.exp(v)-1):+.0f}%" for m,v in pm['median'].items()))
test('A. COUTEAU QUI TOMBE : carte de moins de 10 mois, joueur en creux (f5<=-0.2), ses autres cartes deja en baisse (j_r30<=-10 %)', (df.age<=9)&(df.f5<=-0.2)&(df.j_r30<=-0.10))
test('A2. Sans la forme : carte jeune + autres cartes du joueur en baisse', (df.age<=9)&(df.j_r30<=-0.10))
test('A3. Tout age : joueur en creux + ses cartes en baisse sur 90 j (j_r90<=-0.27)', (df.f5<=-0.2)&(df.j_r90<=-0.27))
test('B. SAISON MORTE : carte de plus de 10 mois, joueur sans match depuis 126 j+, ses cartes pas en chute', (df.age>9)&(df.repos>126)&(df.j_r90>-0.27))
test('B2. Saison morte, toutes cartes de plus de 10 mois', (df.age>9)&(df.repos>126))
test('B3. Hors saison morte, cartes de plus de 10 mois (temoin)', (df.age>9)&(df.repos<=30))
test('C. EN FEU + pas encore monte : f5>=+0.3, carte r30<=+5 %, carte de plus de 10 mois', (df.f5>=0.3)&(df.r30<=0.05)&(df.age>9))
test('D. Tendance haussiere du joueur : j_r90>=+0.15 et j_macd>0, carte de plus de 10 mois', (df.j_r90>=0.15)&(df.j_macd>0)&(df.age>9))
test('E. Nouvelle : pic Wikipedia (wkmax>=1.5) et carte pas encore montee (r7<=0.05)', (df.wkmax>=1.5)&(df.r7<=0.05))
print('\n===== PAIRES (stat arb) : la carte contre les AUTRES cartes du meme joueur')
test('F. Carte en retard : les autres cartes du joueur ont monte (j_r30>=+10 %), celle-ci non (r30<=0)', (df.j_r30>=0.10)&(df.r30<=0))
test('G. Carte en avance : celle-ci a monte (r30>=+15 %), les autres non (j_r30<=0)', (df.r30>=0.15)&(df.j_r30<=0))
test('H. Retour a la moyenne pur : carte a -20 % de ses 31-90 j (r30<=-0.22), joueur stable (|j_r30|<0.08), carte de plus de 10 mois', (df.r30<=-0.22)&(df.j_r30.abs()<0.08)&(df.age>9))
test('I. Carte au-dessus : r30>=+20 % (0.18)', (df.r30>=0.18))
