# Cle de carte CANONIQUE : la cle stricte (tous les mots du titre) coupe la meme carte en dizaines de morceaux
# (« #205 2025-26 ... series 1 », « #205 2025 ... canadiens montreal »...). Ici on se sert du decodeur de l'app (cartes_match) :
# joueur + annee + numero de carte + tirage (/99) + paralleles + auto + patch (+ mots d'identite s'il n'y a pas de numero).
import sys, gzip, json, collections, pickle, datetime as dt
sys.path.insert(0, '/home/claude/mathbou44/lockerroom-')
import cartes_match as cm
A = json.load(gzip.open('/tmp/claude-0/ts/A_maintenant.json.gz', 'rt')); A = A['A'] if isinstance(A, dict) else A
by = collections.defaultdict(list); strict = collections.defaultdict(list)
for x in A:
    d = cm._decoder_memo(x['t']); nom = x['nom']
    par = tuple(sorted(d.get('paralleles') or ()))
    if d.get('num'):
        k = (nom.lower(), d.get('annee'), '#' + str(d['num']), d.get('serie'), par, bool(d.get('auto')), bool(d.get('patch')), bool(d.get('inscr')))
    else:
        mots, marques = cm.identite(x['t'], nom)
        k = (nom.lower(), d.get('annee'), tuple(sorted(mots | marques)), d.get('serie'), par, bool(d.get('auto')), bool(d.get('patch')), bool(d.get('inscr')))
    g = (x['cie'], x['gr'])
    s = (dt.date.fromisoformat(x['j'][:10]).toordinal(), x['p'], nom, x['ra'], x['nj'], x['so'], x['s'])   # ... type de carte, note du joueur, note du type (0-100), cote SlabIQ (0-100)
    by[(k, g)].append(s); strict[(x['k'], x['gr'])].append(s)
import numpy as np
def bilan(lab, B):
    n = sum(len(v) for v in B.values()); c = collections.Counter(min(len(v), 4) for v in B.values())
    sd = []
    for v in B.values():
        if len(v) < 5: continue
        M = collections.defaultdict(list)
        for s in v: M[s[0] // 30].append(np.log(s[1]))
        sd += [np.std(m) for m in M.values() if len(m) >= 5]
    print(f"{lab}: {len(B)} cartes, {n} ventes ; seules {c[1]} ; ventes dans les cartes de 4+ : {sum(len(v) for v in B.values() if len(v)>=4)} ; dispersion des prix dans un meme mois (ecart-type log, mediane) {np.median(sd):.3f} sur {len(sd)} carte-mois")
bilan('STRICTE ', strict); bilan('CANONIQUE', by)
top = sorted(by.items(), key=lambda kv: -len(kv[1]))[:6]
for k, v in top: print(len(v), k)
pickle.dump(dict(by), open('/home/claude/modele/by2.pkl', 'wb'))
