# Le profil dans le temps apres un signal Achete : FORT (deja chaud ou tour du chapeau) contre FAIBLE (gros match isole).
# Meme carte (cartes fortes SlabIQ si possible), prix des 7 jours d'avant contre une fenetre de 10 jours autour de l'horizon.
import math, numpy as np, boucle as B
lim, FINV = B.lim, B.FINV
def serie(E, lab):
    print(f"\n{lab} : {len(E)} entrees")
    for h in (7, 14, 21, 30, 45, 60, 90, 120):
        L = []
        for nom, d, cas, ev in E:
            if d + h + 10 > FINV: continue
            y = B.carte(nom, d - 7, d - 1, d + h + 1, d + h + 10, True); y = y if y is not None else B.carte(nom, d - 7, d - 1, d + h + 1, d + h + 10)
            if y is not None: L.append((y, d, nom))
        def f(X):
            if len(X) < 15: return '      -'
            v = np.array([x[0] for x in X]); return f"{100*(math.exp(np.median(v))-1):+5.1f}% gagne {10*(v>0).mean():.1f}/10 (n={len(X):3d}, {len({x[2] for x in X}):3d} j.)"
        print(f"  {h:3d} j | avant aout 26 : {f([x for x in L if x[1] < lim]):40s} | depuis : {f([x for x in L if x[1] >= lim])}")
F = [e for e in B.ENT if B.chaud(e[0], e[1]) or e[3] == 'chapeau']; W = [e for e in B.ENT if not (B.chaud(e[0], e[1]) or e[3] == 'chapeau')]
serie(F, 'FORT (deja chaud : 5 points+ a ses 5 matchs d\'avant, ou tour du chapeau)'); serie(W, 'FAIBLE (gros match isole)')
serie([e for e in F if e[2] == 'jeune'], 'FORT, jeune joueur'); serie([e for e in F if e[2] == 'veteran'], 'FORT, veteran')
