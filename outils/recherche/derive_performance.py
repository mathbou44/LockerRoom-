import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import cache_recherche as cr   # 23 nov 2026 : plus de pickle (Aikido)
import statistics as st, collections, math, gzip, json, random
abn=cr.charger('abn.json.gz')
D=json.load(gzip.open('/mnt/user-data/uploads/Downloads/slabiq_donnees.json.gz','rt'))
NHL={k.lower(): v for k,v in D['nhl'].items()}
def mi(d): return int(d[:4])*12+int(d[5:7])-1
PERF={}
for nom,v in NHL.items():
    G=v.get('matchs') or []
    if len(G)<40: continue
    bym=collections.defaultdict(list)
    for i,(d,pts,buts) in enumerate(G): bym[mi(d)].append(i)
    for m,idx in bym.items():
        if len(idx)<6: continue
        base=[G[i][1] for i in range(max(0,idx[0]-40),idx[0])]
        if len(base)<25: continue
        cur=[G[i][1] for i in idx]; PERF[(nom,m)]=(sum(cur)/len(cur)-sum(base)/len(base))
def rho(X):
    n=len(X)
    def rk(a):
        o=sorted(range(n),key=lambda i:a[i]); r=[0]*n
        for i,j in enumerate(o): r[j]=i
        return r
    rx,ry=rk([x[0] for x in X]),rk([x[1] for x in X]); mx=(n-1)/2
    return sum((a-mx)*(b-mx) for a,b in zip(rx,ry))/sum((a-mx)**2 for a in rx)
random.seed(7)
for h in (1,2,3):
    X=[(s,abn[h][k][0],k[0],k[1]) for k,s in PERF.items() if k in abn[h]]
    r=rho(X)
    # permutation en gardant les joueurs groupes : on melange la forme entre joueur-mois
    ys=[x[1] for x in X]; cnt=0
    for _ in range(2000):
        random.shuffle(ys)
        if abs(rho([(x[0],y) for x,y in zip(X,ys)]))>=abs(r): cnt+=1
    # par periode
    per=collections.defaultdict(list)
    for x in X: per['2024-25' if x[3]<2025*12+8 else '2025-26' if x[3]<2026*12+8 else '2026-27'].append(x)
    def sp(L):
        if len(L)<45: return f"n={len(L)} trop peu"
        L=sorted(L); t=len(L)//3
        return f"creux {100*sum(x[1]>0 for x in L[:t])/t:.0f}% en hausse vs feu {100*sum(x[1]>0 for x in L[-t:])/t:.0f}% (n={len(L)})"
    print(f"h={h} mois : n={len(X)} rho={r:+.3f} p={cnt/2000:.3f} | " + ' | '.join(f"{p}: {sp(L)}" for p,L in sorted(per.items())))
# 2x2 : le PRIX du mois (rendement anormal m-1 -> m) x la FORME du mois -> suite (m -> m+2)
X=[]
for k,s in PERF.items():
    nom,m=k
    prev=abn[1].get((nom,m-1)); nxt=abn[2].get((nom,m))
    if prev and nxt: X.append((s,prev[0],nxt[0]))
print('\n2x2 (n=%d) : prix deja monte ou non CE mois x forme -> cartes 2 mois plus tard'%len(X))
ms=st.median([x[0] for x in X]); mp=st.median([x[1] for x in X])
for lab,c in [('prix en hausse + joueur en feu',lambda x:x[1]>mp and x[0]>ms),('prix en hausse + forme faible',lambda x:x[1]>mp and x[0]<=ms),('prix en baisse + joueur en feu',lambda x:x[1]<=mp and x[0]>ms),('prix en baisse + forme faible',lambda x:x[1]<=mp and x[0]<=ms)]:
    L=[x[2] for x in X if c(x)]
    if L: print(f"   {lab:32s}: {100*(math.exp(st.median(L))-1):+5.1f}%  en hausse {100*sum(v>0 for v in L)/len(L):.0f}%  n={len(L)}")
