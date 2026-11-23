import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))); import cache_recherche as cr   # 23 nov 2026 : plus de pickle (Aikido)
import collections, statistics as st, bisect, sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))   # la racine du depot
from radar import regle, idx, moins
P = cr.charger("P5.json.gz")
W = {"27 sept": ("2026-09-10", "2026-09-27"), "11 oct": ("2026-09-26", "2026-10-11"), "25 oct": ("2026-10-10", "2026-10-25"), "8 nov": ("2026-10-23", "2026-11-08"), "22 nov": ("2026-10-29", "2026-11-22")}
C = [("actuelle", 82, 5, .10), ("liq 8", 82, 8, .10), ("liq 8 <= med", 82, 8, 0.0), ("liq 12 <= med", 82, 12, 0.0), ("liq 8 sans prix", 82, 8, None)]
print("Le MARCHE de la carte a-t-il tenu ? (mediane d'apres >= 90 % de la mediane d'avant, sans regarder le prix paye) ; parmi les revendues")
for w, (C_, FIN) in W.items():
    out = []
    for nom, note, liq, rab in C:
        S = [x for x in P[w] if regle(x, note, liq, rab) and x["med"]]
        t = n = 0
        for x in S:
            js, ps = idx[(x["a"]["k"], x["a"]["gr"])]
            L = [p for j, p in zip(js, ps) if C_ <= j <= FIN]
            if L:
                n += 1; t += st.median(L) >= 0.9 * x["med"]
        out.append(f"{nom}: {t/max(1,n)*100:5.1f}")
    print(f"{w:8}", "   ".join(out))
