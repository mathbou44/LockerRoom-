# Les techniques classiques de la bourse, appliquees a l'indice du joueur (B3) et verifiees sur ses vraies cartes.
import labo as L, numpy as np, pandas as pd
A, B = L.charger(); p = L.pc
def test(lab, s, d=B):
    out = []
    for c in ('ey30', 'ey60', 'ey90'):
        g = d[s & d[c].notna()]; r = d[~s & d[c].notna()]
        if len(g) < 60: out.append('     -      '); continue
        pm = g.groupby('mois')[c].agg(['median', 'size']); pm = pm[pm['size'] >= 10]; rm = r.groupby('mois')[c].median()
        mieux = sum(pm['median'][m] > rm.get(m, 0) for m in pm.index)
        out.append(f"{p(g[c].median())} vs {p(r[c].median())} ({100*(g[c]>0).mean():2.0f}%h, n={len(g):4d}, {g.nom.nunique():3d}j, {mieux:2d}/{len(pm):2d}m)")
    print(f'{lab:62s} | ' + ' | '.join(out))
print('regle (indice du joueur, prix reel 14 j apres)'.ljust(62), '| 30 j : mediane vs les autres (hausse, n, joueurs, mois au-dessus) | 60 j | 90 j')
test('Croix doree : EMA7 > EMA30 et EMA30 > EMA120', (B.e7_30 > 0.02) & (B.e30_120 > 0.02))
test('Croix de la mort : EMA7 < EMA30 et EMA30 < EMA120', (B.e7_30 < -0.02) & (B.e30_120 < -0.02))
test('MACD qui tourne a la hausse : EMA3 > EMA14, EMA14 < EMA60', (B.e3_14 > 0.02) & (B.e14_60 < -0.02))
test('Prix au-dessus de sa moyenne 200 j (+10 %)', B.sma200 > 0.10)
test('Prix sous sa moyenne 200 j (-10 %)', B.sma200 < -0.10)
test('Bollinger haut (z >= +1,5) : surachete', B.boll >= 1.5)
test('Bollinger bas (z <= -1,5) : survendu', B.boll <= -1.5)
test('RSI haut (80 % de hausses sur 10 ventes)', B.rsi >= 0.8)
test('RSI bas (20 %)', B.rsi <= 0.2)
test('Cassure du haut 90 j', B.haut90 >= -0.02)
test('Cassure du bas 90 j', B.bas90 <= 0.02)
test('Elan 60 j : +10 % et plus', B.r_60 >= 0.10)
test('Elan 60 j : -10 % et moins', B.r_60 <= -0.10)
test('Elan 180 j : +15 % et plus', B.r_180 >= 0.14)
test('Elan 180 j : -15 % et moins', B.r_180 <= -0.16)
test('Acceleration (le mois fait mieux que le mois d\'avant, +10 pts)', B.acc >= 0.10)
test('Deceleration (-10 pts)', B.acc <= -0.10)
test('Volume du joueur qui explose (x2,7) et prix qui monte', (B.vol >= 1.0) & (B.r_60 > 0.03))
test('Volume du joueur qui explose (x2,7) et prix qui baisse', (B.vol >= 1.0) & (B.r_60 < -0.03))
test('Volume qui s\'effondre (/2,7)', B.vol <= -1.0)
test('Forme : en feu sur 5 matchs (+0,4)', B.f5 >= 0.4)
test('Forme : en feu sur 20 matchs (+0,25)', B.f20 >= 0.25)
test('Forme : en creux sur 5 matchs (-0,4)', B.f5 <= -0.4)
test('Forme : en creux sur 20 matchs (-0,25)', B.f20 <= -0.25)
test('En feu (f10>=+0,3) ET prix pas encore monte (r_60<=+3 %)', (B.f10 >= 0.3) & (B.r_60 <= 0.03))
test('En creux (f10<=-0,3) ET prix deja tombe (r_60<=-8 %)', (B.f10 <= -0.3) & (B.r_60 <= -0.08))
test('Nouvelles : Wikipedia 7 j a x2 et plus', B.wk7 >= 0.7)
test('Nouvelles : interet en hausse sur 30 j (x1,5)', B.wk30 >= 0.4)
test('Nouvelles : interet en baisse sur 30 j (/1,5)', B.wk30 <= -0.4)
print('\nMEMES REGLES, verifiees sur les VRAIES cartes du joueur (mediane de ses cartes, 3 cartes et plus)')
V = B.copy()
for h in ('30', '60', '90'):
    V['ey' + h] = V.get('vey' + h, np.nan)
for lab, s in (('Croix doree', (V.e7_30 > 0.02) & (V.e30_120 > 0.02)), ('Croix de la mort', (V.e7_30 < -0.02) & (V.e30_120 < -0.02)), ('Bollinger bas : survendu', V.boll <= -1.5), ('Bollinger haut', V.boll >= 1.5),
               ('Elan 180 j -15 %', V.r_180 <= -0.16), ('Elan 180 j +15 %', V.r_180 >= 0.14), ('En feu 20 matchs', V.f20 >= 0.25), ('En creux 20 matchs', V.f20 <= -0.25), ('Volume explose et prix baisse', (V.vol >= 1.0) & (V.r_60 < -0.03)), ('Interet Wikipedia en baisse 30 j', V.wk30 <= -0.4)):
    test(lab, s, V)
