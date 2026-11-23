import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import cache_recherche as cr   # 23 nov 2026 : plus de pickle (Aikido)
import statistics as st, collections, datetime as dt, bisect, re
by=cr.charger('by.json.gz')
FR, FIX = 0.1325, 0.40
def saison(k):
    m=re.search(r'\b(19|20)(\d\d)-(\d\d)\b',k)
    if m: return int(m.group(1)+m.group(2))
    m=re.search(r'\b(19[5-9]\d|20[0-2]\d)\b',k)
    return int(m.group(1)) if m else None
def run(nom, filtre_gr, age_min, age_max, pmin=30):
    B=collections.defaultdict(list); per=collections.defaultdict(lambda: collections.defaultdict(list)); cards=collections.defaultdict(set)
    for k,S in by.items():
        if len(S)<10: continue
        y0=saison(k)
        if not y0: continue
        G=collections.defaultdict(list)
        for s in S: G[s[4]].append(s)
        for gr,L in G.items():
            if len(L)<10 or not filtre_gr(gr): continue
            days=[s[0] for s in L]; pr=[s[1] for s in L]
            for i in range(len(L)):
                t,p=days[i],pr[i]
                if p<pmin: continue
                d_=dt.date.fromordinal(t); age=(d_.year-y0)*12+(d_.month-10)
                if not (age_min<=age<age_max): continue
                a=bisect.bisect_left(days,t-90); ref=pr[a:i]
                if len(ref)<4: continue
                m=st.median(ref)
                fut=pr[bisect.bisect_left(days,t+30):bisect.bisect_right(days,t+150)]
                if len(fut)<2: continue
                net=(st.median(fut)*(1-FR)-FIX)/p-1; d=p/m-1
                b = '<=-30' if d<=-.3 else '-30..-20' if d<=-.2 else '-20..-10' if d<=-.1 else '-10..+10' if d<=.1 else '>+10'
                B[b].append(net); per[b][f"{d_.year}-{'H1' if d_.month<=6 else 'H2'}"].append(net); cards[b].add((k,gr))
    print('==',nom)
    tot=sum(len(v) for v in B.values())
    for b in ['<=-30','-30..-20','-20..-10','-10..+10','>+10']:
        v=B[b]
        if len(v)<15: continue
        print(f"  {b:9s} {100*len(v)/tot:3.0f}% des ventes n={len(v):5d} ({len(cards[b])} cartes) net median {100*st.median(v):+5.1f}%  gagnants {100*sum(x>0 for x in v)/len(v):3.0f}% | " + ' '.join(f"{p}:{100*st.median(x):+.0f}%({len(x)})" for p,x in sorted(per[b].items()) if len(x)>=20))
run('GRADEES, carte de 12 mois et plus', lambda g:g>0, 12, 999)
run('GRADEES, carte de moins de 12 mois', lambda g:g>0, -5, 12)
run('BRUTES, carte de 12 mois et plus', lambda g:g==0, 12, 999)
run('BRUTES, carte de moins de 12 mois', lambda g:g==0, -5, 12)
