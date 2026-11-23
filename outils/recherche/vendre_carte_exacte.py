import gzip, sys, statistics as st, collections, datetime as dt
D=collections.defaultdict(list)
with gzip.open(sys.argv[1],'rt',encoding='utf-8') as f:
    f.readline()
    for line in f:
        p=line.rstrip('\n').split('\t')
        if len(p)<4: continue
        try: pr=float(p[1]); d=dt.date.fromisoformat(p[2][:10])
        except: continue
        if pr<20: continue
        D[p[3]].append((d,pr))
fin=dt.date(2026,11,22); deb=dt.date(2023,11,22)
res=collections.defaultdict(lambda: collections.Counter())
def med(L,a,b): v=[p for d,p in L if a<=d<b]; return (st.median(v),len(v)) if v else (None,0)
for q,L in D.items():
    if len(L)<20: continue
    L.sort()
    t=deb; actif=False
    while t+dt.timedelta(days=75)<=fin:
        niv,n1=med(L,t-dt.timedelta(30),t); nor,n0=med(L,t-dt.timedelta(365),t-dt.timedelta(30)); apr,n2=med(L,t+dt.timedelta(45),t+dt.timedelta(75))
        if niv and nor and apr and n1>=3 and n0>=8 and n2>=3:
            ec=niv/nor-1; baisse=apr<niv*0.97
            per=f"{t.year}-{'H1' if t.month<=6 else 'H2'}"
            res[('hasard',per)]['n']+=1; res[('hasard',per)]['b']+=baisse
            for s in (0.1,0.2,0.3,0.5):
                if ec>=s:
                    k=('+%d%%'%(s*100),per)
                    if not (actif and s==0.1):
                        res[k]['n']+=1; res[k]['b']+=baisse
            actif = ec>=0.1
        t+=dt.timedelta(days=28)
pers=sorted({p for _,p in res})
for sig in ('hasard','+10%','+20%','+30%','+50%'):
    print(sig.ljust(7), '  '.join(f"{p}: {res[(sig,p)]['b']}/{res[(sig,p)]['n']}={100*res[(sig,p)]['b']/max(1,res[(sig,p)]['n']):.0f}%" for p in pers))
