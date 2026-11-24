"""Combien de joueurs ont des cartes qui passent la regle du Radar ? (24 nov 2026)

Mathieu : « il nous faut beaucoup de cartes a proposer. Chaque personne collectionne des equipes et des joueurs differents,
donc notre Radar doit s'adapter aux demandes de chacun et leur offrir le meilleur ».

    python3 outils/recherche/garde/couverture.py <A_maintenant.json.gz> <date de debut, ex. 2026-08-25>

Les ventes de 30 $ et plus (ni base ni lot) depuis la date, joueurs connus, 20 ventes et plus par joueur. Resultat du 24 nov
(export du 23 nov, 90 derniers jours, 522 joueurs) : aucune carte a 82 et plus (la regle par defaut) : 427 joueurs ; aucune a
76 et plus (la regle d'un joueur SUIVI) : 343 joueurs ; aucune a 65 et plus (B) : 88 ; aucune a 50 et plus (C) : 11.
D'ou lockerroom.RADAR_RANGEE_MIN (la rangee d'un joueur suivi se complete avec ses meilleures cartes, C et plus).
"""
import collections
import gzip
import json
import statistics as st
import sys

A = json.load(gzip.open(sys.argv[1], "rt", encoding="utf-8"))["A"]
R = [a for a in A if a["j"] >= sys.argv[2] and a["p"] >= 30 and a["ra"] not in ("base", "lot_checklist") and a["connu"]]
J = collections.defaultdict(list)
for a in R:
    J[a["nom"]].append(a)
G = {n: L for n, L in J.items() if len(L) >= 20}
print(len(R), "ventes ;", len(G), "joueurs avec 20 ventes et plus")
part = lambda L, s: sum(1 for a in L if a["s"] >= s) / len(L)
for seuil, nom in ((82, "82 et plus (defaut)"), (76, "76 et plus (joueur suivi)"), (65, "65 et plus (B)"), (50, "50 et plus (C)")):
    P = [part(L, seuil) for L in G.values()]
    print(f"  {nom:28s} joueurs sans aucune carte : {sum(p == 0 for p in P):4d} | mediane de la part qui passe : {st.median(P):.2f}")
B = collections.defaultdict(list)
for L in G.values():
    B[min(9, int(L[0]["nj"] // 10))].append((part(L, 82), part(L, 76), part(L, 50)))
for b in sorted(B):
    v = B[b]
    print(f"  note du joueur {b * 10}-{b * 10 + 9} : {len(v):3d} joueurs | 82+ {st.median(x[0] for x in v):.2f} | 76+ {st.median(x[1] for x in v):.2f} | 50+ {st.median(x[2] for x in v):.2f}")
