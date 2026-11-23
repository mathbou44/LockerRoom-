# C. Gain net (frais compris) d'un achat a la mediane du mois, revendu a la mediane 3 et 6 mois plus tard : par AGE de la carte et par lettre SlabIQ
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import cache_recherche as cr   # 23 nov 2026 : plus de pickle (Aikido)
import statistics as st, collections, datetime as dt, re, math
by=cr.charger('by.json.gz')
FR,FIX=0.1325,0.40
def saison(k):
    m=re.search(r'\b(19|20)(\d\d)-(\d\d)\b',k)
    if m: return int(m.group(1)+m.group(2))
    m=re.search(r'\b(19[5-9]\d|20[0-2]\d)\b',k)
    return int(m.group(1)) if m else None
def add(y,m,k): 
    t=y*12+m-1+k; return (t//12, t%12+1)
T=collections.defaultdict(list); TP=collections.defaultdict(lambda: collections.defaultdict(list))
for k,S in by.items():
    if len(S)<6: continue
    y0=saison(k)
    if not y0: continue
    G=collections.defaultdict(lambda: collections.defaultdict(list)); L={}
    for s in S:
        d=dt.date.fromordinal(s[0]); G[s[4]][(d.year,d.month)].append(s[1]); L[s[4]]=s[3]
    for gr,M in G.items():
        for (y,mo),v in M.items():
            if len(v)<2: continue
            p=st.median(v)
            if p<30: continue
            age=(y-y0)*12+(mo-10)
            ab='0-5 mois' if age<6 else '6-11 mois' if age<12 else '12-23 mois' if age<24 else '2-4 ans' if age<60 else '5 ans et +'
            let=L[gr][:1]
            for h in (3,6):
                w=M.get(add(y,mo,h))
                if not w or len(w)<2: continue
                net=(st.median(w)*(1-FR)-FIX)/p-1
                T[(h,ab,'tout')].append(net); T[(h,ab,let)].append(net)
                TP[(h,ab)][f"{y}-{'H1' if mo<=6 else 'H2'}"].append(net)
for h in (3,6):
    print(f"--- revente {h} mois plus tard (gain net median, frais compris ; % gagnants ; n) ---")
    for ab in ['0-5 mois','6-11 mois','12-23 mois','2-4 ans','5 ans et +']:
        def f(key):
            v=T.get(key) or []
            return f"{100*st.median(v):+4.0f}% {100*sum(x>0 for x in v)/len(v):2.0f}% n={len(v):4d}" if len(v)>=20 else '   --            '
        print(f"  {ab:11s} tout: {f((h,ab,'tout'))} | A: {f((h,ab,'A'))} | B: {f((h,ab,'B'))} | C: {f((h,ab,'C'))} | D-E: {f((h,ab,'D'))}")
        print('              par periode: '+' '.join(f"{p}:{100*st.median(x):+.0f}%({len(x)})" for p,x in sorted(TP[(h,ab)].items()) if len(x)>=20))
