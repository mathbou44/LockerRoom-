# B. Indice a ventes repetees (meme carte, mois m -> m+1), par age du produit : la courbe de vie d'une carte
import pickle, statistics as st, collections, datetime as dt, re, math
by=pickle.load(open('by.pkl','rb'))
def saison(k):
    m=re.search(r'\b(19|20)(\d\d)-(\d\d)\b',k)
    if m: return int(m.group(1)+m.group(2))
    m=re.search(r'\b(19[5-9]\d|20[0-2]\d)\b',k)
    return int(m.group(1)) if m else None
R=collections.defaultdict(list)   # (cohorte_age, ym) -> log ratios
RA=collections.defaultdict(list)  # age en mois depuis octobre de la saison -> log ratios
for k,S in by.items():
    if len(S)<6: continue
    y0=saison(k)
    if not y0: continue
    G=collections.defaultdict(lambda: collections.defaultdict(list))
    for s in S:
        d=dt.date.fromordinal(s[0]); G[s[4]][(d.year,d.month)].append(s[1])
    for gr,M in G.items():
        for (y,mo),v in M.items():
            if len(v)<2 or st.median(v)<15: continue
            ny,nm=(y,mo+1) if mo<12 else (y+1,1)
            w=M.get((ny,nm))
            if not w or len(w)<2: continue
            lr=math.log(st.median(w)/st.median(v))
            age=(y-y0)*12+(mo-10)        # mois depuis octobre de la saison de la carte
            coh='recrue de l annee (0-11 mois)' if age<12 else '2e annee (12-23 mois)' if age<24 else 'ancienne (2 ans et +)'
            R[(coh,(y,mo))].append(lr); RA[min(age,48)].append(lr)
print("Courbe de vie : variation mediane du prix d'un mois au suivant, selon l'age de la carte (mois depuis octobre de sa saison)")
cum=0
for a in sorted(RA):
    v=RA[a]
    if len(v)<25 or a<0: continue
    med=st.median(v); cum+=med
    print(f"  age {a:2d} mois : {100*(math.exp(med)-1):+5.1f}% /mois  (n={len(v)})   cumul depuis la sortie {100*(math.exp(cum)-1):+5.0f}%")
print()
for coh in ['recrue de l annee (0-11 mois)','2e annee (12-23 mois)','ancienne (2 ans et +)']:
    print(coh)
    for (c,ym),v in sorted(R.items()):
        if c==coh and len(v)>=25: print(f"   {ym[0]}-{ym[1]:02d} -> mois suivant : {100*(math.exp(st.median(v))-1):+5.1f}%  (n={len(v)})")
