"""
SLABCOACH - le banc de la VALEUR d'une carte, sur toutes nos ventes (20 nov 2026).

Mathieu : « repasser les tests qu'on a batis et les ameliorer pour etre le plus pres possible de la realite ; ensuite faire passer
nos algorithmes au travers ».

  python3 outils/banc_valeur.py [ventes_hockey.tsv.gz]

Ce que le banc du serveur (banc.valider_valeur) faisait et ce qui change ici :
  - il testait une COPIE simplifiee de la regle (banc._valeur_param) ; ici c'est la VRAIE fonction de l'app (deals._valeur_sure0 :
    ventes abimees et numeros speciaux retires, 365 jours pour un hit, refus si trop disperse...), et la mediane ponderee par la
    recence de la pastille de prix (deals.mediane_recente) ;
  - il cachait UNE vente par carte et la predisait : une seule vente est bruitee (une enchere ratee, un lot) ; ici la verite = la
    MEDIANE des ventes de la meme carte dans les 14 jours a partir de la date du test (3 au plus : le marche du moment) ;
  - 400 cartes au plus ; ici toutes les cartes avec 5 ventes et plus, plusieurs dates de test par carte (jusqu'a 6) ;
  - la meme carte : la cle de validation_iq.cle_carte + la COMPAGNIE et la note (une PSA 10 n'est pas une SGC 10).
Jamais une vente du futur : chaque regle ne voit que les ventes d'AVANT la date du test (le jour meme exclu). Pour la vraie regle
de l'app (qui compte les jours depuis aujourd'hui), les dates sont decalees : la date du test devient aujourd'hui.
On mesure : la couverture (la regle ose une valeur), l'ecart median a la verite, la part a +/- 15 % et 25 %, le BIAIS (une
valeur trop haute fait de faux deals et de faux « trop cher »), sur toutes les cartes et sur les cartes communes a toutes.
"""
import collections
import datetime as dt
import gzip
import json
import os
import json                      # 20 nov 2026 (Aikido) : le cache en JSON, plus de pickle
import random
import re
import statistics as st
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
TRAV = os.environ.get("LR_BANC_TRAV") or "/tmp/claude-0/banc_valeur"
G = re.compile(r"\b(psa|bgs|sgc|cgc|tag|ksa|hga|beckett|bccg|csg|gma|isa|ags|mnt)\s*-?\s*(?:gem\s*(?:mint|mt)?\s*|mint\s*|pristine\s*)?(\d+(?:\.\d)?)\b", re.I)
HORIZON = 14
MAX_TESTS_CARTE = 6


def charger(chemin):
    os.makedirs(TRAV, exist_ok=True)
    cache = os.path.join(TRAV, "cartes_%d.json.gz" % int(os.path.getmtime(chemin)))
    if os.path.exists(cache):
        with gzip.open(cache, "rt", encoding="utf-8") as f:
            return {(k[0], tuple(k[1]) if k[1] else None): l for k, l in json.load(f)}
    import validation_iq as v
    import score_slab
    vus, par = set(), collections.defaultdict(list)
    with gzip.open(chemin, "rt", encoding="utf-8") as f:
        next(f)
        for l in f:
            p = l.rstrip("\n").split("\t")
            if len(p) < 3 or not p[2]:
                continue
            try:
                pr = float(p[1])
            except ValueError:
                continue
            r = (p[0], pr, p[2][:10])
            if pr < 3 or r in vus:
                continue
            vus.add(r)
            if score_slab.sport_autre(p[0]) or not (v._RE_HOCKEY_SUR.search(p[0]) or v._equipe_lnh(p[0])):
                continue
            g = G.search(p[0])
            cle = (v.cle_carte(p[0]), (g.group(1).lower().replace("beckett", "bgs"), float(g.group(2))) if g else None)
            par[cle].append({"titre": p[0], "prix": pr, "le": p[2][:10]})
    cartes = {k: sorted(l, key=lambda x: x["le"]) for k, l in par.items() if len(l) >= 5}
    with gzip.open(cache, "wt", encoding="utf-8") as f:
        json.dump([[list(k), l] for k, l in cartes.items()], f)
    return cartes


def tests(cartes, seed=7):
    """[(cle, date du test, historique, verite)] : jusqu'a MAX_TESTS_CARTE dates par carte, reparties au hasard dans le temps."""
    import bisect
    rng = random.Random(seed)
    out = []
    for k in sorted(cartes, key=str):
        l = cartes[k]
        les = [x["le"] for x in l]
        jours = sorted(set(les))
        ok = [d for d in jours if bisect.bisect_left(les, d) >= 2]
        if len(ok) > MAX_TESTS_CARTE:
            ok = sorted(rng.sample(ok, MAX_TESTS_CARTE))
        for d in ok:
            a = bisect.bisect_left(les, d)
            fin = (dt.date.fromisoformat(d) + dt.timedelta(days=HORIZON)).isoformat()
            b = bisect.bisect_left(les, fin)
            fut = [x["prix"] for x in l[a:b]][:3]
            if fut:
                out.append((k, d, l[max(0, a - 60):a], st.median(fut)))
    return out


def _decaler(hist, d):
    """Les ventes decalees pour que la date du test soit aujourd'hui (la regle de l'app compte depuis aujourd'hui)."""
    delta = (dt.date.today() - dt.date.fromisoformat(d)).days
    return [dict(x, le=(dt.date.fromisoformat(x["le"]) + dt.timedelta(days=delta)).isoformat()) for x in hist]


def recettes():
    import deals
    import cartes_match

    def app(hist, d, titre):
        m, _pv = deals._valeur_sure0(_decaler(hist, d), titre)
        return m

    def recente(dv):
        def f(hist, d, titre):
            h = [x for x in hist if (dt.date.fromisoformat(d) - dt.date.fromisoformat(x["le"])).days <= 90]
            return deals.mediane_recente(h, demi_vie=dv, maint=dt.datetime.fromisoformat(d)) if len(h) >= 2 else None
        return f

    def mediane90(hist, d, titre):
        h = [x["prix"] for x in hist if (dt.date.fromisoformat(d) - dt.date.fromisoformat(x["le"])).days <= 90]
        return cartes_match.mediane_robuste(h)[0] if len(h) >= 2 else None

    def derniere(hist, d, titre):
        return hist[-1]["prix"]

    def moy3(hist, d, titre):
        return st.median(x["prix"] for x in hist[-3:]) if len(hist) >= 3 else None

    return {"app_valeur_sure": app, "pastille_recente_15j": recente(15), "pastille_recente_30j": recente(30),
            "pastille_recente_45j": recente(45), "mediane_90j": mediane90, "derniere_vente": derniere, "mediane_3_dernieres": moy3}


def mesurer(T, R):
    res = {k: [] for k in R}
    for k, d, h, t in T:
        titre = h[-1]["titre"]
        for nom, f in R.items():
            try:
                v = f(h, d, titre)
            except Exception:
                v = None
            res[nom].append(None if not v else (v - t) / t)
    communs = [i for i in range(len(T)) if all(res[n][i] is not None for n in R)]

    def resume(l):
        ok = [e for e in l if e is not None]
        if not ok:
            return {"n": len(l), "couverture": 0}
        a = [abs(e) for e in ok]
        return {"n": len(l), "couverture": round(len(ok) / len(l), 3), "ecart_median": round(st.median(a), 3),
                "dans15": round(sum(x <= .15 for x in a) / len(a), 3), "dans25": round(sum(x <= .25 for x in a) / len(a), 3),
                "biais_median": round(st.median(ok), 3), "trop_haut_25": round(sum(e > .25 for e in ok) / len(ok), 3)}
    out = {"tests": len(T), "cartes": len({k for k, *_ in T}), "communs": len(communs), "recettes": {}}
    for nom in R:
        out["recettes"][nom] = {"tout": resume(res[nom]), "communs": resume([res[nom][i] for i in communs])}
    # par gamme de prix (sur les cartes communes)
    bandes = ((0, 20), (20, 50), (50, 100), (100, 250), (250, 10 ** 9))
    out["par_prix"] = {}
    for lo, hi in bandes:
        idx = [i for i in communs if lo <= T[i][3] < hi]
        out["par_prix"][f"{lo}-{hi if hi < 10 ** 9 else '+'}"] = {n: resume([res[n][i] for i in idx]) for n in R}
    return out


def lancer(chemin):
    cartes = charger(chemin)
    T = tests(cartes)
    print(f"{len(cartes)} cartes (5 ventes et plus), {len(T)} tests", flush=True)
    R = recettes()
    out = mesurer(T, R)
    out["le"] = dt.date.today().isoformat()
    os.makedirs(TRAV, exist_ok=True)
    json.dump(out, open(os.path.join(TRAV, "banc_valeur.json"), "w"), ensure_ascii=False, indent=1)
    print(f"{'recette':24s} {'couv':>6s} {'ecart':>6s} {'±15%':>6s} {'±25%':>6s} {'biais':>6s} {'>+25%':>6s} | communs: {'ecart':>6s} {'±25%':>6s} {'biais':>6s}")
    for n, r in out["recettes"].items():
        a, c = r["tout"], r["communs"]
        print(f"{n:24s} {a['couverture']:6.1%} {a.get('ecart_median', 0):6.1%} {a.get('dans15', 0):6.1%} {a.get('dans25', 0):6.1%} "
              f"{a.get('biais_median', 0):+6.1%} {a.get('trop_haut_25', 0):6.1%} | {c.get('ecart_median', 0):6.1%} {c.get('dans25', 0):6.1%} {c.get('biais_median', 0):+6.1%}")
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    lancer(args[0] if args else "/mnt/user-data/uploads/Downloads/ventes_hockey.tsv.gz")
