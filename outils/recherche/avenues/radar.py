import pickle, collections, statistics as st, bisect, datetime as dt, sys, itertools
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))   # la racine du depot
import liquidite
A = pickle.load(open("A.pkl", "rb"))
par = collections.defaultdict(list)
for a in A:
    par[(a["k"], a["gr"])].append((a["j"], a["p"]))
idx = {k: ([j for j, _ in sorted(v)], [p for _, p in sorted(v)]) for k, v in par.items()}
FRAIS, FIXE = 0.1325, 0.40
def moins(j, n): return (dt.date.fromisoformat(j) - dt.timedelta(days=n)).isoformat()
def prep(C0, C, FIN, pmin=30):
    """Chaque achat de la fenetre, avec ses signaux d'avant et son resultat d'apres (ventes de C a FIN)."""
    out = []
    for a in A:
        if not (C0 <= a["j"] < C) or a["p"] < pmin or a["ra"] in ("base", "lot_checklist"):
            continue
        js, ps = idx[(a["k"], a["gr"])]
        i = bisect.bisect_left(js, a["j"])
        liq = i - bisect.bisect_left(js, moins(a["j"], 60))
        liq30 = i - bisect.bisect_left(js, moins(a["j"], 30))
        i90 = bisect.bisect_left(js, moins(a["j"], 90))
        med = liquidite.mediane_recente(list(zip(js[i90:i], ps[i90:i])), a["j"], avant=True)
        # tendance : mediane des 30 derniers jours contre les 30 d'avant
        i30, i60 = bisect.bisect_left(js, moins(a["j"], 30)), bisect.bisect_left(js, moins(a["j"], 60))
        r, v = ps[i30:i], ps[i60:i30]
        tend = (st.median(r) / st.median(v) - 1) if len(r) >= 2 and len(v) >= 2 else None
        disp = (st.pstdev(ps[i90:i]) / st.mean(ps[i90:i])) if i - i90 >= 4 else None
        L = [p for j, p in zip(js, ps) if C <= j <= FIN]
        m_ = st.median(L) if L else None
        out.append(dict(a=a, liq=liq, liq30=liq30, med=med, tend=tend, disp=disp, rev=m_ is not None,
                        ok=m_ is not None and m_ >= 0.9 * a["p"], net=m_ is not None and m_ * (1 - FRAIS) - FIXE >= a["p"]))
    return out
def regle(x, note=82, liq=5, rab=0.10):
    if x["a"]["s"] < note or x["liq"] < liq: return False
    if rab is None: return True
    return x["med"] is not None and x["a"]["p"] <= x["med"] * (1 + rab)
def bilan(S):
    n = len(S)
    if not n: return None
    return dict(n=n, ok=sum(x["ok"] for x in S) / n, rev=sum(x["rev"] for x in S) / n, net=sum(x["net"] for x in S) / n)
if __name__ == "__main__":
    F = {"choix": ("2026-09-25", "2026-10-10", "2026-10-25"), "juge": ("2026-10-15", "2026-10-29", "2026-11-22")}
    P = {k: prep(*v) for k, v in F.items()}
    pickle.dump(P, open("P.pkl", "wb"))
    for k, S in P.items():
        print(k, "hasard", bilan(S), " regle actuelle", bilan([x for x in S if regle(x)]))
