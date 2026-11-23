import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))); import cache_recherche as cr   # 23 nov 2026 : plus de pickle (Aikido)
import labo as L, numpy as np, pandas as pd
A, B = L.charger(); C = L.criteres(A)
print(len(C), 'criteres ; cas :', A[A.ey30.notna()].cas.value_counts().to_dict())
for h, gap in ((30, 46), (60, 76), (90, 106)):
    c = f'ey{h}'
    P, _ = L.marche(A, c, gap, C); L.bilan(P, c, f'\nh{h} GLOBAL      '); cr.sauver_df(P, f'P3_{h}.csv.gz')
    for k, g in P.groupby('cas'):
        if len(g) > 600: L.bilan(g, c, f'   {k:16s}')
    Pc, _ = L.marche(A, c, gap, C, par_cas='cas'); L.bilan(Pc, c, f'h{h} UN MODELE PAR CAS')
    for k, g in Pc.groupby('cas'):
        if len(g) > 600: L.bilan(g, c, f'   {k:16s}')
