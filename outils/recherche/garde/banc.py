"""SLABCOACH - recherche « garde sa valeur » (23 nov 2026 au soir).

Mathieu, devant le test du soir (Radar Pro 74 % ; « garde sa valeur » 80 % contre 86 %) : « continue a travailler pour rendre
SlabIQ infaillible ». Ce banc refait la mesure du Radar Pro (memes definitions que tests_site.mesures) sur le fichier de
travail du test du site, a n'importe quelle fenetre, avec pour chaque achat ce qu'on savait AVANT l'achat.

    python3 outils/recherche/garde/banc.py <A_maintenant.json.gz> <dossier de travail>

Un achat = une vente entre C0 et C (30 $ et plus, ni base ni lot). Reussi = la meme carte se revend entre C et FIN, et la
mediane de ces reventes vaut au moins 90 % du prix paye. Chaque fenetre : 21 jours d'achats, puis 30 jours de reventes
(la meme duree partout, pour comparer les fenetres entre elles).
"""
import bisect
import collections
import datetime as dt
import gzip
import json
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import liquidite

FRAIS, FIXE = 0.1325, 0.40
ACHATS_J, REVENTES_J = 21, 30


def moins(j, n):
    return (dt.date.fromisoformat(j[:10]) - dt.timedelta(days=n)).isoformat()


def plus(j, n):
    return (dt.date.fromisoformat(j[:10]) + dt.timedelta(days=n)).isoformat()


def charger(chemin):
    with gzip.open(chemin, "rt", encoding="utf-8") as f:
        A = json.load(f)["A"]
    par = collections.defaultdict(list)
    parj = collections.defaultdict(list)
    for a in A:
        a["j"] = a["j"][:10]
        par[(a["k"], a["gr"])].append((a["j"], a["p"]))
        parj[a["nom"]].append((a["j"], a["p"], a["k"], a["gr"]))
    idx = {k: ([j for j, _ in sorted(v)], [p for _, p in sorted(v)]) for k, v in par.items()}
    return A, idx, parj


def med(L):
    return st.median(L) if L else None


def signaux(a, idx):
    """Ce qu'on sait de la carte la veille de l'achat."""
    js, ps = idx[(a["k"], a["gr"])]
    j = a["j"]
    i = bisect.bisect_left(js, j)
    b = lambda n: bisect.bisect_left(js, moins(j, n))
    i14, i30, i60, i90 = b(14), b(30), b(60), b(90)
    m = liquidite.mediane_recente(list(zip(js[i90:i], ps[i90:i])), j, avant=True)
    r30, v30 = ps[i30:i], ps[i60:i30]
    r14 = ps[i14:i]
    v3090 = ps[i90:i30]
    return dict(liq=i - i60, liq30=i - i30, liq14=i - i14, med=m,
                tend=(med(r30) / med(v30) - 1) if len(r30) >= 3 and len(v30) >= 3 else None,
                tend90=(med(r30) / med(v3090) - 1) if len(r30) >= 3 and len(v3090) >= 3 else None,
                tend14=(med(r14) / med(ps[i60:i14]) - 1) if len(r14) >= 2 and len(ps[i60:i14]) >= 3 else None,
                accel=((i - i30) / max(1, i30 - i60)) if i30 - i60 >= 3 else None,
                disp=(st.pstdev(ps[i90:i]) / st.mean(ps[i90:i])) if i - i90 >= 4 else None,
                bas90=min(ps[i90:i]) if i > i90 else None, haut90=max(ps[i90:i]) if i > i90 else None,
                age=(dt.date.fromisoformat(j) - dt.date.fromisoformat(js[0])).days, n_tot=i,
                vieux90=i60 - i90)          # ventes entre 60 et 90 jours avant (ce que l'index de 90 jours du serveur peut voir)


def fenetre(A, idx, C0, pmin=30.0, achats_j=ACHATS_J, reventes_j=REVENTES_J):
    C, FIN = plus(C0, achats_j), plus(C0, achats_j + reventes_j)
    out = []
    for a in A:
        if not (C0 <= a["j"] < C) or a["p"] < pmin or a["ra"] in ("base", "lot_checklist"):
            continue
        js, ps = idx[(a["k"], a["gr"])]
        L = ps[bisect.bisect_left(js, C):bisect.bisect_right(js, FIN)]
        m_ = med(L)
        x = signaux(a, idx)
        x.update(a=a, rev=m_ is not None, ok=m_ is not None and m_ >= 0.9 * a["p"], ratio=(m_ / a["p"]) if m_ else None,
                 net=m_ is not None and m_ * (1 - FRAIS) - FIXE >= a["p"], n_rev=len(L))
        out.append(x)
    return out


def radar(x, note=liquidite.NOTE_MIN, liq=liquidite.LIQ_MIN, rab=liquidite.RABAIS_MAX, vieux=0):
    """vieux=0 : la regle d'avant le 23 nov au soir ; vieux=1 : avec « la carte se vendait deja il y a deux mois »."""
    return x["a"]["s"] >= note and x["liq"] >= liq and x["med"] is not None and x["a"]["p"] <= x["med"] * (1 + rab) and x["vieux90"] >= vieux


def bilan(S):
    n = len(S)
    if not n:
        return dict(n=0)
    rev = sum(x["rev"] for x in S)
    return dict(n=n, ok=round(sum(x["ok"] for x in S) / n, 3), rev=round(rev / n, 3), garde=round(sum(x["ok"] for x in S) / rev, 3) if rev else None,
                cartes=len({(x["a"]["k"], x["a"]["gr"]) for x in S}), joueurs=len({x["a"]["nom"] for x in S}))


def par_carte(S):
    """Une carte ne compte qu'une fois par fenetre (la part de ses achats reussis)."""
    d = collections.defaultdict(list)
    for x in S:
        d[(x["a"]["k"], x["a"]["gr"])].append(x["ok"])
    return round(sum(sum(v) / len(v) for v in d.values()) / len(d), 3) if d else None


if __name__ == "__main__":
    A, idx, parj = charger(sys.argv[1])
    print(len(A), "ventes annotees")
    # 1. le test officiel du soir : achats du 27 sept au 22 oct, reventes jusqu'a la fin
    S = fenetre(A, idx, "2026-09-27", achats_j=25, reventes_j=400)
    print("officiel :", bilan([x for x in S if radar(x)]), "| hasard :", bilan(S))
    print("officiel, pas une carte neuve :", bilan([x for x in S if radar(x, vieux=1)]), "par carte", par_carte([x for x in S if radar(x, vieux=1)]),
          "(avant, par carte :", par_carte([x for x in S if radar(x)]), ")")
    if "--officiel" in sys.argv:
        sys.exit(0)
    # 2. les fenetres comparables (21 jours d'achats, 30 jours de reventes), une aux 2 semaines
    d0 = dt.date(2025, 10, 1)
    while d0 <= dt.date(2026, 10, 4):
        S = fenetre(A, idx, d0.isoformat())
        R = [x for x in S if radar(x)]
        print(d0, "radar", bilan(R), "par carte", par_carte(R), "| hasard ok", bilan(S).get("ok"), "n", len(S))
        d0 += dt.timedelta(days=14)
