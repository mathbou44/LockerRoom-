"""Qu'est-ce qui distingue les achats rates du Radar Pro ? Tous les achats de la regle actuelle, 27 fenetres (oct. 2025 a
oct. 2026), ranges par ce qu'on savait AVANT l'achat. Ecrit P.json.gz (les achats et leurs signaux) pour les scripts suivants.

    python3 outils/recherche/garde/diag.py <A_maintenant.json.gz> <dossier de travail>
"""
import collections
import datetime as dt
import gzip
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import banc

A, idx, parj = banc.charger(sys.argv[1])
TRAV = sys.argv[2]
# le joueur : la mediane du rapport prix / mediane 90 j de ses cartes, 30 derniers jours contre les 30 d'avant (toutes ses cartes)
JJ = {n: sorted(v) for n, v in parj.items()}


def joueur(nom, j):
    import bisect
    L = JJ.get(nom) or []
    js = [x[0] for x in L]
    i, i30, i60 = bisect.bisect_left(js, j), bisect.bisect_left(js, banc.moins(j, 30)), bisect.bisect_left(js, banc.moins(j, 60))
    # par carte : mediane recente / mediane d'avant, puis la mediane de ces rapports (au moins 3 cartes)
    r, v = collections.defaultdict(list), collections.defaultdict(list)
    for x in L[i30:i]:
        r[(x[2], x[3])].append(x[1])
    for x in L[i60:i30]:
        v[(x[2], x[3])].append(x[1])
    rap = [banc.med(r[k]) / banc.med(v[k]) for k in r if k in v and len(r[k]) >= 2 and len(v[k]) >= 2]
    return dict(j_tend=(banc.med(rap) - 1) if len(rap) >= 3 else None, j_n30=i - i30, j_acc=((i - i30) / max(1, i30 - i60)) if i30 - i60 >= 5 else None)


SAISON = re.compile(r"\b(20\d\d)-(\d\d)\b")
P = []
d0 = dt.date(2025, 10, 1)
while d0 <= dt.date(2026, 10, 4):
    for x in banc.fenetre(A, idx, d0.isoformat()):
        if not banc.radar(x, liq=5, rab=0.10):          # large : la regle d'avant ; la regle actuelle = liq >= 8 et prix <= med
            continue
        a = x.pop("a")
        m = SAISON.search(a["t"])
        x.update(f=d0.isoformat(), k=a["k"], gr=a["gr"], p=a["p"], j=a["j"], s=a["s"], so=a["so"], ra=a["ra"], nom=a["nom"], t=a["t"],
                 saison=int(m.group(1)) if m else None, **joueur(a["nom"], a["j"]))
        P.append(x)
    d0 += dt.timedelta(days=14)
with gzip.open(os.path.join(TRAV, "P.json.gz"), "wt", encoding="utf-8") as f:
    json.dump(P, f)
R = [x for x in P if x["liq"] >= 8 and x["p"] <= x["med"]]
print(len(P), "achats (regle large) ;", len(R), "achats de la regle actuelle ; reussis", round(sum(x["ok"] for x in R) / len(R), 3))


def table(nom, cle, bornes):
    print("\n" + nom)
    for lo, hi in zip(bornes, bornes[1:]):
        S = [x for x in R if cle(x) is not None and lo <= cle(x) < hi]
        if S:
            rev = sum(x["rev"] for x in S)
            print(f"  {lo:>8} a {hi:<8} n={len(S):5d}  reussi {sum(x['ok'] for x in S) / len(S):.3f}  revendue {rev / len(S):.3f}  garde {sum(x['ok'] for x in S) / max(1, rev):.3f}")
    S = [x for x in R if cle(x) is None]
    if S:
        print(f"  (inconnu)            n={len(S):5d}  reussi {sum(x['ok'] for x in S) / len(S):.3f}")


INF = 10 ** 9
table("age de la carte (jours depuis sa 1re vente chez nous)", lambda x: x["age"], [0, 21, 45, 90, 180, 365, INF])
table("prix / mediane recente", lambda x: x["p"] / x["med"], [0, 0.6, 0.75, 0.85, 0.93, 1.0001])
table("tendance 30 j contre les 30 d'avant", lambda x: x["tend"], [-9, -0.25, -0.12, -0.04, 0.04, 0.12, 0.25, 9])
table("tendance 30 j contre 30-90 j", lambda x: x["tend90"], [-9, -0.25, -0.12, -0.04, 0.04, 0.12, 0.25, 9])
table("tendance 14 j", lambda x: x["tend14"], [-9, -0.25, -0.12, -0.04, 0.04, 0.12, 0.25, 9])
table("acceleration des ventes (30 j / 30 j d'avant)", lambda x: x["accel"], [0, 0.5, 0.8, 1.25, 2, 4, INF])
table("ventes en 60 j", lambda x: x["liq"], [8, 12, 20, 40, 80, INF])
table("ventes en 14 j", lambda x: x["liq14"], [0, 1, 3, 6, 12, INF])
table("dispersion des prix (90 j)", lambda x: x["disp"], [0, 0.15, 0.25, 0.4, 0.6, 9])
table("prix paye", lambda x: x["p"], [30, 50, 80, 150, 300, INF])
table("note SlabIQ", lambda x: x["s"], [82, 86, 90, 101])
table("gradee (note)", lambda x: x["gr"], [0, 0.5, 9, 9.75, 11])
table("tendance du joueur (ses cartes, 30 j)", lambda x: x["j_tend"], [-9, -0.15, -0.06, 0.0, 0.06, 0.15, 9])
table("acceleration du joueur", lambda x: x["j_acc"], [0, 0.6, 0.9, 1.2, 1.8, INF])
table("saison de la carte", lambda x: x["saison"], [1900, 2015, 2023, 2024, 2025, 2026, 2030])
table("position dans la fourchette 90 j (0 = au plus bas, 1 = au plus haut)", lambda x: (x["med"] - x["bas90"]) / (x["haut90"] - x["bas90"]) if x["haut90"] and x["haut90"] > x["bas90"] else None, [0, 0.15, 0.3, 0.5, 0.7, 1.01])
c = collections.Counter(x["nom"] for x in R)
print("\njoueurs :", [(n, k, round(sum(x["ok"] for x in R if x["nom"] == n) / k, 2)) for n, k in c.most_common(14)])
c = collections.Counter(x["ra"] for x in R)
print("sortes :", [(n, k, round(sum(x["ok"] for x in R if x["ra"] == n) / k, 2)) for n, k in c.most_common(10)])
