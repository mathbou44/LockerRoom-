"""Le banc du Radar Pro avec de VRAIES ventes : une vente comptee une fois, la meme carte sous une seule cle (24 nov 2026).

    python3 outils/recherche/garde/banc2.py <A_maintenant.json.gz> <dossier de travail> [--deja | ventes_avec_id.tsv.gz]

Mathieu (une Rantanen Canvas PSA 10 partie a 63 $ : « j'espere qu'on l'avait captee » ; puis « on doit etre parfait avant Apple »).
Nos archives gardent une vente une fois par recherche qui l'a trouvee, et la cle de carte changeait avec la facon d'ecrire le
titre. Ici : les memes fenetres que banc.py (21 jours d'achats, 30 jours de reventes), sur des ventes dedoublonnees et avec la
cle de liquidite.cle_base. Sert a re-choisir le nombre de ventes de la regle (« 8 ventes » etait compte avec les doublons).

Sans le fichier des ventes avec identifiant : doublons ESTIMES (meme titre, a 1 jour pres, prix a 1 % pres).
Avec : doublons exacts (le numero de l'annonce vendue).
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
import liquidite

A = json.load(gzip.open(sys.argv[1], "rt", encoding="utf-8"))["A"]
TRAV = sys.argv[2]
for a in A:
    a["j"] = a["j"][:10]
n0 = len(A)
if "--deja" in sys.argv:                                 # le fichier de travail vient deja d'un export avec « id » (tests_site.charger)
    B, mode = A, "deja enleves par tests_site (exacts)"
elif len(sys.argv) > 3:                                  # exact : (titre, prix, jour) -> numero de l'annonce
    ids = {}
    with gzip.open(sys.argv[3], "rt", encoding="utf-8", errors="replace") as f:
        ent = f.readline().rstrip("\n").split("\t")
        ii = ent.index("id")
        for l in f:
            c = l.rstrip("\n").split("\t")
            if len(c) > ii and c[ii]:
                try:
                    ids[(c[0][:120], round(float(c[1]), 2), c[2][:10])] = c[ii]
                except ValueError:
                    pass
    vus, B = set(), []
    for a in A:
        i = ids.get((a["t"], round(a["p"], 2), a["j"])) or (a["t"], a["p"], a["j"])
        k = (i, a["gr"])
        if k in vus:
            continue
        vus.add(k)
        B.append(a)
    mode = "exacts (numero de l'annonce)"
else:
    par_t = collections.defaultdict(list)
    for a in A:
        par_t[a["t"]].append((dt.date.fromisoformat(a["j"]).toordinal(), a["p"], a))
    B = []
    for t, L in par_t.items():
        L.sort(key=lambda x: (x[0], x[1]))
        g = []
        for jour, p, a in L:
            if any(abs(jour - j2) <= 1 and abs(p - p2) <= 0.01 * max(p, p2) for j2, p2, _ in g):
                continue
            g.append((jour, p, a))
        B += [a for _, _, a in g]
    mode = "estimes (meme titre, a 1 jour pres, prix a 1 % pres)"
print(f"{n0} ventes annotees ; doublons {mode} : {n0 - len(B)} ({100 * (n0 - len(B)) / n0:.1f} %) ; restent {len(B)}")
memo = {}
for a in B:
    t = a["t"]
    if t not in memo:
        memo[t] = liquidite.cle_base(t) + ("|" + a["cie"].lower() if a["cie"] else "")
    a["k0"], a["k"] = a["k"], memo[t]
par = collections.defaultdict(list)
for a in B:
    par[(a["k"], a["gr"])].append((a["j"], a["p"]))
idx = {k: ([j for j, _ in sorted(v)], [p for _, p in sorted(v)]) for k, v in par.items()}
print(len({(a["k0"], a["gr"]) for a in B}), "cartes avec la cle d'avant ;", len(idx), "avec la nouvelle")
SAISON = re.compile(r"\b(20\d\d)-(\d\d)\b")
P = []
d0 = dt.date(2025, 10, 1)
while d0 <= dt.date(2026, 10, 4):
    for x in banc.fenetre(B, idx, d0.isoformat()):
        a = x["a"]
        if not (a["s"] >= 82 and x["liq"] >= 2 and x["med"] is not None and a["p"] <= x["med"] * 1.10):
            continue
        x.pop("a")
        x.update(f=d0.isoformat(), k=a["k"], gr=a["gr"], p=a["p"], j=a["j"], s=a["s"], nom=a["nom"], t=a["t"])
        P.append(x)
    d0 += dt.timedelta(days=14)
with gzip.open(os.path.join(TRAV, "P2.json.gz"), "wt", encoding="utf-8") as f:
    json.dump(P, f)
print(len(P), "achats (A- et plus, 2 ventes et plus, prix jusqu'a +10 %) ecrits dans P2.json.gz")
