"""La cle de carte de la liquidite coupe-t-elle la meme carte en morceaux ? Et la meme vente est-elle comptee plusieurs fois ? (24 nov 2026)

Mathieu, devant une Rantanen Canvas Young Guns PSA 10 partie a 63 $ en encan : « j'espere qu'on l'avait captee ». Sous son titre
exact, la carte avait 2 ventes en 60 jours chez nous (il en faut 8 pour « A la une ») ; la MEME carte, toutes facons de l'ecrire
confondues : 59 ventes sous 21 cles. Et plusieurs de ces « ventes » sont la meme, a quelques cents pres.

    python3 outils/recherche/garde/cle_carte.py <A_maintenant.json.gz> <jour, ex. 2026-11-24>

1. doublons : meme titre, a un jour pres, meme prix a 1 % pres ;
2. cle stricte (liquidite.cle : tous les mots du titre) contre cle canonique (le decodeur de l'app, comme outils/recherche/modele/cle2.py) :
   combien de cartes ont 8 ventes en 60 jours avec l'une et avec l'autre, doublons enleves.
"""
import collections
import datetime as dt
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import cartes_match as cm

A = json.load(gzip.open(sys.argv[1], "rt", encoding="utf-8"))["A"]
J = sys.argv[2]
d = lambda n: (dt.date.fromisoformat(J) - dt.timedelta(days=n)).isoformat()
R = [a for a in A if a["j"][:10] >= d(90) and a["p"] >= 30 and a["ra"] not in ("base", "lot_checklist")]
print(len(R), "ventes de 30 $ et plus, 90 derniers jours")
# 1. les doublons
par_t = collections.defaultdict(list)
for a in R:
    par_t[a["t"]].append((dt.date.fromisoformat(a["j"][:10]).toordinal(), a["p"], a))
uniques, n_dup = [], 0
for t, L in par_t.items():
    L.sort(key=lambda x: (x[0], x[1]))
    gardes = []
    for jour, p, a in L:
        if any(abs(jour - j2) <= 1 and abs(p - p2) <= 0.01 * max(p, p2) for j2, p2, _ in gardes):
            n_dup += 1
            continue
        gardes.append((jour, p, a))
    uniques += [a for _, _, a in gardes]
print(f"doublons (meme titre, a 1 jour pres, prix a 1 % pres) : {n_dup} sur {len(R)} ({100 * n_dup / len(R):.1f} %) ; restent {len(uniques)} ventes")


def canon(a):
    x = cm._decoder_memo(a["t"]); nom = a["nom"].lower()
    par = tuple(sorted(x.get("paralleles") or ()))
    if x.get("num"):
        k = (nom, x.get("annee"), "#" + str(x["num"]).replace("-", "").lower(), x.get("serie"), par, bool(x.get("auto")), bool(x.get("patch")), bool(x.get("inscr")))
    else:
        mots, marques = cm.identite(a["t"], a["nom"])
        k = (nom, x.get("annee"), tuple(sorted(mots | marques)), x.get("serie"), par, bool(x.get("auto")), bool(x.get("patch")), bool(x.get("inscr")))
    return (k, a["cie"], a["gr"])


def compte(L, cle, nom):
    C60, C90 = collections.Counter(), collections.Counter()
    for a in L:
        k = cle(a)
        if a["j"][:10] >= d(60):
            C60[k] += 1
        else:
            C90[k] += 1
    liquides = [k for k, n in C60.items() if n >= 8]
    print(f"  {nom:44s} cartes : {len(set(C60) | set(C90)):6d} | 8 ventes en 60 j : {len(liquides):5d} | et deja vendue il y a 2 mois : {sum(1 for k in liquides if C90.get(k)):5d}")
    return set(liquides)


stricte = lambda a: (a["k"], a["gr"])
print("cartes « liquides » (8 ventes en 60 jours) :")
compte(R, stricte, "cle stricte, avec les doublons (EN PLACE)")
compte(uniques, stricte, "cle stricte, sans les doublons")
compte(R, canon, "cle canonique, avec les doublons")
L4 = compte(uniques, canon, "cle canonique, sans les doublons")
ex = [a for a in uniques if "rantanen" in a["nom"].lower() and "canvas" in a["t"].lower() and a["gr"] == 10.0]
print("Rantanen Canvas PSA 10, 90 jours, sans doublons :", sorted((a["j"][:10], round(a["p"])) for a in ex), "| cles strictes :", len({a["k"] for a in ex}), "| cles canoniques :", len({canon(a) for a in ex}))
