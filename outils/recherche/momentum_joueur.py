# D. Momentum ou retour a la moyenne ? Indice mensuel par JOUEUR (ventes repetees de ses cartes de 12 mois et +), puis : le passe predit-il la suite ?
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import cache_recherche as cr   # 23 nov 2026 : plus de pickle (Aikido)
import statistics as st, collections, datetime as dt, re, math
by=cr.charger('by.json.gz')
def saison(k):
    m=re.search(r'\b(19|20)(\d\d)-(\d\d)\b',k)
    if m: return int(m.group(1)+m.group(2))
    m=re.search(r'\b(19[5-9]\d|20[0-2]\d)\b',k)
    return int(m.group(1)) if m else None
def mi(y,m): return y*12+m-1
LR=collections.defaultdict(lambda: collections.defaultdict(list))  # joueur -> mois -> log ratios (m-1 -> m)
for k,S in by.items():
    if len(S)<4: continue
    y0=saison(k)
    if not y0: continue
    G=collections.defaultdict(lambda: collections.defaultdict(list)); nom=S[0][2]
    for s in S:
        d=dt.date.fromordinal(s[0])
        if (d.year-y0)*12+(d.month-10) < 12: continue
        G[s[4]][mi(d.year,d.month)].append(s[1])
    for gr,M in G.items():
        for m,v in M.items():
            w=M.get(m-1)
            if w and st.median(w)>=15: LR[nom][m].append(math.log(st.median(v)/st.median(w)))
IDX={}
for nom,M in LR.items():
    IDX[nom]={m: st.median(v) for m,v in M.items() if len(v)>=3}
print('joueurs avec un indice',sum(1 for v in IDX.values() if len(v)>=4))
def test(lb, skip, fw, lab):
    X=[]
    for nom,I in IDX.items():
        for m in I:
            past=[I.get(m-skip-i) for i in range(lb)]; fut=[I.get(m+1+i) for i in range(fw)]
            if None in past or None in fut: continue
            X.append((sum(past),sum(fut),m))
    if len(X)<100: print(lab,'trop peu',len(X)); return
    X.sort(); n=len(X); q=n//5
    lo,hi=[x[1] for x in X[:q]],[x[1] for x in X[-q:]]
    # rank corr
    import random
    xs=[x[0] for x in X]; ys=[x[1] for x in X]
    def rk(a):
        o=sorted(range(len(a)),key=lambda i:a[i]); r=[0]*len(a)
        for i,j in enumerate(o): r[j]=i
        return r
    rx,ry=rk(xs),rk(ys); mx=(n-1)/2
    rho=sum((a-mx)*(b-mx) for a,b in zip(rx,ry))/sum((a-mx)**2 for a in rx)
    print(f"{lab}: n={n} rho={rho:+.2f} | 20% qui ont le plus BAISSE: passe {100*(math.exp(st.median([x[0] for x in X[:q]]))-1):+.0f}% -> suite {100*(math.exp(st.median(lo))-1):+.1f}% | 20% qui ont le plus MONTE: passe {100*(math.exp(st.median([x[0] for x in X[-q:]]))-1):+.0f}% -> suite {100*(math.exp(st.median(hi))-1):+.1f}%")
test(1,0,1,'1 mois -> mois suivant (bruit de mesure possible)')
test(1,1,1,'1 mois, saute 1 mois -> 1 mois')
test(2,1,2,'2 mois, saute 1 -> 2 mois')
test(3,1,3,'3 mois, saute 1 -> 3 mois')
test(3,0,3,'3 mois -> 3 mois')
