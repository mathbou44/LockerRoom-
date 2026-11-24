"""Re-choisir la regle du Radar Pro sur de vraies ventes (P2.json.gz, ecrit par banc2.py) : choisie sur oct. 2025 a mars 2026,
jugee sur avril a oct. 2026.

    python3 outils/recherche/garde/regles2.py <dossier de travail>
"""
import collections, gzip, json, os, statistics as st, sys
P = json.load(gzip.open(os.path.join(sys.argv[1], "P2.json.gz"), "rt"))
F = sorted({x["f"] for x in P})


def b(S):
    n = len(S)
    if not n:
        return "n=    0"
    rev = sum(x["rev"] for x in S)
    d = collections.defaultdict(list)
    for x in S:
        d[(x["f"], x["k"], x["gr"])].append(x["ok"])
    pc = sum(sum(v) / len(v) for v in d.values()) / len(d)
    pf = [sum(x["ok"] for x in S if x["f"] == f) / sum(1 for x in S if x["f"] == f) for f in F if any(x["f"] == f for x in S)]
    return (f"n={n:5d} reussi {sum(x['ok'] for x in S) / n:.3f} revendue {rev / n:.3f} garde {sum(x['ok'] for x in S) / max(1, rev):.3f} "
            f"par carte {pc:.3f} | fenetres min {min(pf):.2f} med {st.median(pf):.2f}")


def regle(liq, rab=0.0, vieux=1):
    return lambda x: x["liq"] >= liq and x["p"] <= x["med"] * (1 + rab) and x["vieux90"] >= vieux


REG = collections.OrderedDict()
for liq in (2, 3, 4, 5, 6, 8):
    REG[f"{liq} ventes, <= mediane, pas neuve"] = regle(liq)
REG["4 ventes, <= mediane, 2 ventes il y a 2 mois"] = regle(4, 0.0, 2)
REG["5 ventes, <= mediane, 2 ventes il y a 2 mois"] = regle(5, 0.0, 2)
REG["4 ventes, <= mediane, neuve permise"] = regle(4, 0.0, 0)
REG["5 ventes, +10 %, pas neuve"] = regle(5, 0.10)
der = [x for x in P if x["f"] == F[-1]]
for nom, S0 in (("CHOIX (oct. 2025 a mars 2026)", [x for x in P if x["f"] < "2026-04-01"]), ("JUGE (avril a oct. 2026)", [x for x in P if x["f"] >= "2026-04-01"])):
    print(nom)
    for k, r in REG.items():
        print(f"  {k:46s}", b([x for x in S0 if r(x)]))
print("derniere fenetre (30 sept) : achats, cartes differentes, joueurs")
for k, r in REG.items():
    S = [x for x in der if r(x)]
    print(f"  {k:46s} {len(S):4d} {len({(x['k'], x['gr']) for x in S}):4d} {len({x['nom'] for x in S}):4d}")
