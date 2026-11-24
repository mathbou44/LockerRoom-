"""Pourquoi les cartes B se revendent moins que les C au test du 23 nov au soir (7,9 % contre 9,7 %) : par lettre puis par
sorte de carte, les reventes de la MEME carte apres C, ses ventes des 60 jours d'avant et son prix.

    python3 outils/recherche/garde/lettres_bc.py <A_maintenant.json.gz> <C, ex. 2026-10-22>
"""
import gzip, json, collections, statistics as st, sys
A = json.load(gzip.open(sys.argv[1], "rt"))["A"]
C = sys.argv[2]
import datetime as dt
banc_moins = lambda j, n: (dt.date.fromisoformat(j) - dt.timedelta(days=n)).isoformat()
lettre, ra, prix, avant = {}, {}, collections.defaultdict(list), collections.Counter()
for a in A:
    k = (a["k"], a["gr"])
    if a["j"] < C:
        lettre[k] = a["fin"]; ra[k] = a["ra"]; prix[k].append(a["p"])
        if a["j"] >= banc_moins(C, 60): avant[k] += 1
apres = collections.Counter((a["k"], a["gr"]) for a in A if a["j"] >= C)
def ligne(K):
    n = len(K); return f"n={n:6d} reventes {sum(apres.get(k, 0) for k in K)/max(1,n):.3f} | part revendue {sum(1 for k in K if apres.get(k))/max(1,n):.3f} | ventes 60 j avant {sum(avant.get(k,0) for k in K)/max(1,n):.2f} | prix med {st.median([st.median(prix[k]) for k in K]) if K else 0:.0f}"
for L in ("A+", "A", "A-", "B+", "B", "C", "D", "E"):
    K = [k for k, l in lettre.items() if l == L]
    print(L, ligne(K))
for L in ("B+", "B", "C"):
    K = [k for k, l in lettre.items() if l == L]
    c = collections.Counter(ra[k] for k in K)
    print("\n", L, "par sorte :")
    for r, n in c.most_common(9):
        print(f"   {r:18s}", ligne([k for k in K if ra[k] == r]))
