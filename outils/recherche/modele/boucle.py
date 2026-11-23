# LA BOUCLE COMPLETE par joueur : on ENTRE sur le signal Achete, on SORT sur une regle. Mesure : la MEME carte, du prix d'entree au
# prix de sortie. Deux prix d'entree : « soir meme » (les 7 jours d'avant : le prix n'a pas encore bouge) et « prudent » (jour du
# match et lendemain). Sortie : les 10 jours APRES le signal de sortie. On choisit la regle avant aout 2026, on la juge apres.
import bisect, collections, math, sys
import numpy as np
import rejoue as R, signal_joueur as sj
D, O, CJ, lim = R.D, R.O, R.CJ, R.lim
NH = {n.lower(): [(O(g[0]), g[1], g[2]) for g in (v.get('matchs') or [])] for n, v in D['nhl'].items()}
FIN = max(g[-1][0] for g in NH.values() if g)                      # dernier jour de matchs connu
FINV = max(int(c[0][-1]) for L in CJ.values() for c in L)          # dernier jour de ventes

def carte(nom, a0, a1, b0, b1, fort=None):
    """Mediane, sur les cartes du joueur, de ln(prix dans [b0, b1] / prix dans [a0, a1])."""
    v = []
    for ds, lp, so, an in CJ.get(nom, ()):
        if fort is not None and (so >= 88) != fort: continue
        a, b = bisect.bisect_left(ds, a0), bisect.bisect_right(ds, a1)
        x, y = bisect.bisect_left(ds, b0), bisect.bisect_right(ds, b1)
        if b > a and y > x: v.append(float(np.median(lp[x:y]) - np.median(lp[a:b])))
    return float(np.median(v)) if v else None

def sortie(G, i, regle):
    """Le jour de sortie apres une entree au match i, selon la regle ; None si la regle ne s'est pas encore declenchee."""
    pts = [g[1] for g in G]; d = G[i][0]
    if regle[0] == 'jours':
        return d + regle[1] if d + regle[1] <= FINV - 10 else None
    base = sum(pts[max(0, i - 40):i]) / max(1, min(i, 40))
    for k in range(i + 1, len(G)):
        if G[k][0] - d > 150: return G[k][0]                       # jamais plus de 5 mois
        if regle[0] == 'secs' and k - i >= regle[1] and sum(pts[k - regle[1] + 1:k + 1]) == 0: return G[k][0]          # N matchs de suite sans point
        if regle[0] == 'froid' and k - i >= regle[1] and sum(pts[k - regle[1] + 1:k + 1]) / regle[1] <= base + regle[2]: return G[k][0]   # N derniers matchs sous sa base
        if regle[0] == 'feu_fini' and k - i >= 5 and sum(pts[k - 4:k + 1]) < 5 * (base + regle[1]): return G[k][0]     # la sequence de 5 matchs retombe
    return None

REGLES = [('jours', 14), ('jours', 30), ('jours', 60), ('jours', 90), ('secs', 2), ('secs', 3), ('secs', 4), ('froid', 5, -0.2), ('froid', 5, 0.0),
          ('froid', 10, -0.1), ('froid', 10, 0.0), ('feu_fini', 0.0), ('feu_fini', 0.2), ('feu_fini', 0.4)]
def nomr(r):
    return {'jours': lambda: f"apres {r[1]} jours", 'secs': lambda: f"{r[1]} matchs de suite sans point", 'froid': lambda: f"{r[1]} derniers matchs a {r[2]:+.1f} pt/match de sa base ou moins",
            'feu_fini': lambda: f"ses 5 derniers matchs retombent sous sa base {r[1]:+.1f}"}[r[0]]()
ENT = [(n, d, cas, e) for n, d, cas, e, s in R.SIG if s == 'ACHETE']
def chaud(nom, d):
    G = NH.get(nom) or []; i = next((k for k, g in enumerate(G) if g[0] == d), None)
    return i is not None and i >= 5 and sum(g[1] for g in G[i - 5:i]) >= 5
p = lambda v: f"{100*(math.exp(np.median(v))-1):+5.1f}%"
def bilan(lab, X):
    """X = [(rendement entree soir meme, rendement entree prudente, suite apres la sortie, jours tenus, jour d'entree)]"""
    def f(L):
        if len(L) < 15: return '        -                         '
        a = np.array([x[0] for x in L]); b = np.array([x[1] for x in L if x[1] is not None]); c = np.array([x[2] for x in L if x[2] is not None])
        return f"{p(a)} gagne {10*(a>0).mean():3.1f}/10, net de frais {100*(math.exp(np.median(a))*(1-0.1325)-1):+5.1f}% | prudent {p(b) if len(b)>=10 else '  -  '} | apres la sortie {p(c) if len(c)>=10 else '  -  '} | {np.median([x[3] for x in L]):3.0f} j (n={len(L):3d})"
    print(f"{lab:58s} | AVANT aout 26 : {f([x for x in X if x[4] < lim])}\n{'':58s} | DEPUIS        : {f([x for x in X if x[4] >= lim])}")
if __name__ == '__main__':
    filtre = sys.argv[1] if len(sys.argv) > 1 else 'tous'
    E = [e for e in ENT if filtre == 'tous' or (filtre == 'fort' and (chaud(e[0], e[1]) or e[3] == 'chapeau')) or (filtre == 'faible' and not (chaud(e[0], e[1]) or e[3] == 'chapeau'))]
    print(f"{len(E)} entrees ({filtre}) ; cartes fortes selon SlabIQ si possible, sinon toutes ses cartes")
    for r in REGLES:
        X = []
        for nom, d, cas, ev in E:
            G = NH.get(nom) or []; i = next((k for k, g in enumerate(G) if g[0] == d), None)
            if i is None: continue
            s = sortie(G, i, r)
            if s is None or s + 10 > FINV: continue
            y = carte(nom, d - 7, d - 1, s + 1, s + 10, True); y = y if y is not None else carte(nom, d - 7, d - 1, s + 1, s + 10)
            if y is None: continue
            yp = carte(nom, d, d + 1, s + 1, s + 10)
            ap = carte(nom, s + 1, s + 10, s + 20, s + 50) if s + 50 <= FINV else None
            X.append((y, yp, ap, s - d, d))
        bilan(nomr(r), X)
