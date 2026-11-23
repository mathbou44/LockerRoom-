# G. Etude d'evenements : un pic de visites Wikipedia (une NOUVELLE) -> le prix de ses cartes avant / apres, compare a des dates au hasard du meme joueur
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import cache_recherche as cr   # 23 nov 2026 : plus de pickle (Aikido)
import statistics as st, collections, datetime as dt, math, gzip, json, random, bisect
by=cr.charger('by.json.gz')
D=json.load(gzip.open('/mnt/user-data/uploads/Downloads/slabiq_donnees.json.gz','rt'))
WIKI={k.lower(): v for k,v in D['wiki'].items()}; NHL={k.lower(): v for k,v in D['nhl'].items()}
CJ=collections.defaultdict(list)
for k,S in by.items():
    if len(S)>=8:
        G=collections.defaultdict(list)
        for s in S: G[s[4]].append((s[0],s[1]))
        for gr,L in G.items():
            if len(L)>=8: CJ[S[0][2].lower()].append(([x[0] for x in L],[x[1] for x in L]))
W=[(-21,-8),(-7,-1),(0,6),(7,20),(21,45),(46,90)]
def profil(nom,t):
    out=[[] for _ in W]
    for days,pr in CJ.get(nom,[]):
        ref=pr[bisect.bisect_left(days,t-75):bisect.bisect_left(days,t-21)]
        if len(ref)<3: continue
        m=st.median(ref)
        for i,(a,b) in enumerate(W):
            v=pr[bisect.bisect_left(days,t+a):bisect.bisect_right(days,t+b)]
            if len(v)>=2: out[i].append(math.log(st.median(v)/m))
    return [st.median(v) if v else None for v in out]
EV=[]
for nom,V in WIKI.items():
    if nom not in CJ: continue
    ds=sorted(V); vals=[V[d] for d in ds]; last=-99
    pts={g[0]:g[1] for g in (NHL.get(nom) or {}).get('matchs',[])}
    for i in range(35,len(ds)):
        base=st.median(vals[i-35:i-3])
        if vals[i]>=max(1500,4*base) and i-last>21:
            last=i; t=dt.date.fromisoformat(ds[i]).toordinal()
            p3=sum(pts.get((dt.date.fromordinal(t-j)).isoformat(),0) for j in range(0,3))
            EV.append((nom,t,vals[i]/max(1,base),p3,ds[i]))
print('pics de nouvelles',len(EV),'joueurs',len({e[0] for e in EV}))
random.seed(3)
def agg(L):
    P=[profil(n,t) for n,t in L]
    return [(st.median([p[i] for p in P if p[i] is not None]) if sum(p[i] is not None for p in P)>=15 else None, sum(p[i] is not None for p in P)) for i in range(len(W))]
def show(lab,L):
    A=agg(L)
    # controle : dates au hasard (meme joueur, +/- 120 jours, pas a moins de 30 jours)
    C=agg([(n,t+random.choice([-1,1])*random.randint(40,120)) for n,t in L for _ in range(3)])
    print(lab, f"({len(L)} evenements)")
    for (a,b),(x,n),(c,_) in zip(W,A,C):
        if x is not None and c is not None: print(f"   jours {a:+4d} a {b:+4d} : {100*(math.exp(x)-1):+5.1f}%  (dates au hasard {100*(math.exp(c)-1):+5.1f}%)  -> effet {100*(math.exp(x-c)-1):+5.1f}%   n={n}")
show('TOUS les pics',[(e[0],e[1]) for e in EV])
show('Pic avec GROSSE performance (3 pts et + en 3 jours)',[(e[0],e[1]) for e in EV if e[3]>=3])
show('Pic SANS performance (nouvelle hors glace : blessure, echange, contrat...)',[(e[0],e[1]) for e in EV if e[3]==0])
top=sorted(EV,key=lambda e:-e[2])[:25]
print('\nLes plus gros pics :'); 
for e in top: print(f"   {e[4]} {e[0]} x{e[2]:.0f} pts3j={e[3]} cartes={len(CJ[e[0]])}")
cr.sauver(EV, 'ev.json.gz')
