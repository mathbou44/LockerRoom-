"""Les regles candidates sur les achats du Radar Pro (P.json.gz, ecrit par diag.py) : choisies sur oct. 2025 a mars 2026 (CHOIX),
jugees sur avril a oct. 2026 (JUGE). Une regle n'est retenue que si elle tient sur les DEUX periodes.

    python3 outils/recherche/garde/regles.py <dossier de travail>
"""
import gzip, json, collections, os, statistics as st, sys
P = json.load(gzip.open(os.path.join(sys.argv[1], "P.json.gz"), "rt"))
R = [x for x in P if x["liq"] >= 8 and x["p"] <= x["med"]]
F = sorted({x["f"] for x in R})
def b(S):
    n = len(S); rev = sum(x["rev"] for x in S)
    d = collections.defaultdict(list)
    for x in S: d[(x["f"], x["k"], x["gr"])].append(x["ok"])
    pc = sum(sum(v)/len(v) for v in d.values())/max(1, len(d))
    pf = [sum(x["ok"] for x in S if x["f"] == f)/max(1, sum(1 for x in S if x["f"] == f)) for f in F if any(x["f"] == f for x in S)]
    return f"n={n:5d} reussi {sum(x['ok'] for x in S)/max(1,n):.3f} garde {sum(x['ok'] for x in S)/max(1,rev):.3f} par carte {pc:.3f} | fenetres min {min(pf):.2f} med {st.median(pf):.2f}"
REG = {
 "actuelle": lambda x: True,
 "V1 age>=60": lambda x: x["age"] >= 60,
 "V2 vente entre 60 et 90 j": lambda x: x["vieux90"] >= 1,
 "V2b 2 ventes entre 60 et 90 j": lambda x: x["vieux90"] >= 2,
 "V1 age>=90": lambda x: x["age"] >= 90,
 "V1 + A et plus": lambda x: x["age"] >= 60 and x["s"] >= 86,
 "V1 + 12 ventes": lambda x: x["age"] >= 60 and x["liq"] >= 12,
 "V1 + prix<=0.93 med": lambda x: x["age"] >= 60 and x["p"] <= 0.93 * x["med"],
 "V1 + 50 $ et plus": lambda x: x["age"] >= 60 and x["p"] >= 50,
 "V1 + joueur pas en baisse >15%": lambda x: x["age"] >= 60 and not (x["j_tend"] is not None and x["j_tend"] < -0.15),
 "V1 + tend14 > -25%": lambda x: x["age"] >= 60 and not (x["tend14"] is not None and x["tend14"] < -0.25),
}
for nom, S0 in (("CHOIX", [x for x in R if x["f"] < "2026-04-01"]), ("JUGE ", [x for x in R if x["f"] >= "2026-04-01"])):
    print(nom)
    for k, r in REG.items():
        print(f"  {k:32s}", b([x for x in S0 if r(x)]))
der = [x for x in R if x["f"] == F[-1]]
print("derniere fenetre (30 sept) :", {k: (len([x for x in der if r(x)]), len({(x['k'], x['gr']) for x in der if r(x)}), len({x['nom'] for x in der if r(x)})) for k, r in REG.items()})

print("\npar anciennete de la carte (jours depuis sa 1re vente chez nous) :")
for nom, S0 in (("CHOIX", [x for x in R if x["f"] < "2026-04-01"]), ("JUGE ", [x for x in R if x["f"] >= "2026-04-01"])):
    for lo, hi in ((0, 21), (21, 45), (45, 60), (60, 75), (75, 90), (90, 180), (180, 10 ** 9)):
        print(f"  {nom} age {lo:>3}-{hi:<10}", b([x for x in S0 if lo <= x["age"] < hi]))
