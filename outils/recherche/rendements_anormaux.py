# Rendements mensuels ANORMAUX par joueur : chaque carte vs les cartes du meme age le meme mois (comme un rendement anormal en bourse)
import pickle, statistics as st, collections, datetime as dt, re, math, gzip, json
by=pickle.load(open('by.pkl','rb'))
def saison(k):
    m=re.search(r'\b(19|20)(\d\d)-(\d\d)\b',k)
    if m: return int(m.group(1)+m.group(2))
    m=re.search(r'\b(19[5-9]\d|20[0-2]\d)\b',k)
    return int(m.group(1)) if m else None
MED={}   # (key,gr) -> {mois: mediane}, age0
for k,S in by.items():
    if len(S)<4: continue
    y0=saison(k)
    G=collections.defaultdict(lambda: collections.defaultdict(list))
    for s in S:
        d=dt.date.fromordinal(s[0]); G[s[4]][d.year*12+d.month-1].append(s[1])
    for gr,M in G.items():
        mm={m: st.median(v) for m,v in M.items() if len(v)>=2 and st.median(v)>=10}
        if len(mm)>=2: MED[(k,gr)]=(S[0][2].lower(), y0, mm)
print('cartes avec >=2 mois',len(MED))
def bande(m,y0):
    if not y0: return 'x'
    a=m-(y0*12+9)
    return 'a0' if a<6 else 'a1' if a<12 else 'a2' if a<24 else 'a3'
out={}
for h in (1,2,3):
    raw=collections.defaultdict(list)   # (mois, bande) -> log returns
    rows=[]
    for (k,gr),(nom,y0,mm) in MED.items():
        for m,p in mm.items():
            q=mm.get(m+h)
            if q: 
                lr=math.log(q/p); b=bande(m,y0); raw[(m,b)].append(lr); rows.append((nom,m,b,lr))
    bench={kb: st.median(v) for kb,v in raw.items() if len(v)>=8}
    P=collections.defaultdict(list)
    for nom,m,b,lr in rows:
        if (m,b) in bench: P[(nom,m)].append(lr-bench[(m,b)])
    out[h]={kk: (st.median(v),len(v)) for kk,v in P.items()}
    print('h',h,'joueur-mois',len(out[h]),'avec >=2 cartes',sum(1 for v in out[h].values() if v[1]>=2))
pickle.dump(out,open('abn.pkl','wb'))
