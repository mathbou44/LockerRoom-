"""SLABCOACH - le modele de prediction du PRIX d'une carte dans 30 et 60 jours, avec CHAMPION et ASPIRANT (27 nov 2026).

ADMIN SEULEMENT tant qu'il n'a pas fait ses preuves (Mathieu, 12 h 06 : « on garde ca dans admin jusqu'a temps qu'on ait prouve son
fonctionnement »).

Mathieu (11 h 21) : « notre modele / algo / IA doit apprendre en vue de la creation d'un modele de prediction avec toutes les
variables intrants et les etudes de tout le data qu'on a ramasse depuis le debut » ; (11 h 24) « on doit etre sur que lorsqu'il
apprend, il y a une maniere de pouvoir valider si ces modifications sont bonnes ou mauvaises. Il peut y avoir une version qui
roule en arriere de la nouvelle ; si elle est bonne, elle remplace l'autre une fois validee. On serait un petit peu en arriere,
mais on serait tout le temps bon. Il faudrait juste une maniere de tester ca. »

Le meme code sert au banc (hors ligne, sur le passe) et au serveur : ce qui est mesure est ce qui tourne.

1. LA TABLE (panneau) : une ligne par carte exacte (a_grader.classer : joueur, sorte, saison, /N, numero) ET par note (raw, PSA 9,
   PSA 10), chaque lundi, avec seulement ce qu'on savait CE JOUR-LA :
     le prix du moment (mediane des 30 derniers jours, sinon 60), le nombre de ventes, la pente (30 jours contre les 60 d'avant,
     60 contre les 120 d'avant), l'etalement des prix, la derniere vente, l'age de la carte (saisons depuis sa sortie), la note,
     Young Guns ou non, le tirage, depuis quand on la voit se vendre, le mois ; et autour d'elle : la pente des AUTRES cartes du
     joueur, des autres joueurs de la MEME sorte, de tout le marche, et le volume du joueur.
   La CIBLE : le prix de la carte 15 a 45 jours plus tard (horizon 30) et 45 a 75 jours plus tard (horizon 60), en ecart au
   prix du moment (log). Il faut CIBLE_MIN ventes dans la fenetre, sinon la ligne n'a pas de cible (elle ne sert pas).
2. LE MODELE : des arbres (LightGBM), ecrits en texte (jamais de pickle). La REGLE A BATTRE : « le prix ne bouge pas » (0 %).
3. CHAMPION ET ASPIRANT, PAR SEGMENT (horizon x raw / gradee ; au depart partout : « le prix ne bouge pas ») : le champion est le
   seul que l'app utilise. L'aspirant (une nouvelle version : plus de donnees, une
   variable de plus) roule a cote, sur les MEMES cartes, les MEMES jours ; les deux FIGENT leurs predictions avant de connaitre
   la suite. Quand la suite est connue, `decider` les compare carte par carte : l'aspirant ne remplace le champion que s'il fait
   mieux sur au moins N_MIN predictions murries ET que son avance tient au tirage (95 % des tirages bootstrap) ET qu'elle vaut
   au moins GAIN_MIN de l'erreur du champion. L'ancien champion reste en RESERVE : s'il bat le nouveau de la meme facon, il
   reprend sa place. Le PIEGE : une version volontairement mauvaise doit etre refusee (tests/test_modele_prix.py).
"""
import bisect
import json
import math
from datetime import date, timedelta

import numpy as np

HORIZONS = (30, 60)
CIBLE_J = {30: (15, 45), 60: (45, 75)}       # la fenetre de la cible, en jours apres la date de la prediction
CIBLE_MIN = 3
P0_J, P0_MIN = 30, 3                          # le prix du moment : 3 ventes dans les 30 derniers jours...
P0_LONG_J, P0_LONG_MIN = 60, 4                # ... sinon 4 dans les 60
N_MIN = 1000                                  # predictions murries, communes au champion et a l'aspirant, pour decider
GAIN_MIN = 0.03                               # l'aspirant doit faire au moins 3 % mieux (erreur moyenne)
# 27 nov 2026 (banc, voir plus bas) : avec 300 predictions et 1 %, des modeles prenaient un segment puis faiblissaient (la reserve
# reprenait, mais trop tard : le systeme faisait 3 a 7 % PIRE que « ne bouge pas » sur les gradees). Avec 1 000 et 3 % : jamais pire,
# nulle part ; seul le segment 30 jours raw est pris (avril 2026), et le systeme y fait mieux que la regle, prouve a 95 %.
CONFIANCE = 0.95
TIRAGES = 2000
BORNE = 1.2                                   # une prediction ne depasse jamais x3,3 ou /3,3 (log 1,2)

VARIABLES = ["p0", "n30", "n90", "pente", "pente2", "etale", "derniere", "age", "note", "yg", "tirage", "anciennete", "mois",
             "j_pente", "j_n30", "s_pente", "m_pente"]
NOTES = {"raw": 0, "9": 1, "10": 2}


def _o(d):
    return date.fromisoformat(str(d)[:10]).toordinal()


def _saison(o):
    d = date.fromordinal(o)
    return d.year if d.month >= 7 else d.year - 1


def _med(xs):
    return float(np.median(xs)) if len(xs) else math.nan


def lundis(debut, fin):
    """Les lundis de debut a fin (AAAA-MM-JJ)."""
    d = date.fromisoformat(debut)
    d += timedelta(days=(7 - d.weekday()) % 7)
    f = date.fromisoformat(fin)
    out = []
    while d <= f:
        out.append(d.isoformat())
        d += timedelta(days=7)
    return out


def cartes(ventes):
    """ventes : des (cle de la carte, note, date, prix) -> {(cle, note): (jours[], log prix[])} tries par date. La cle :
    (joueur, recherche, saison, /N, numero), comme a_grader.classer."""
    par = {}
    for cle, note, le, prix in ventes:
        if not prix or prix <= 0 or note not in NOTES:
            continue
        par.setdefault((tuple(cle), note), []).append((_o(le), math.log(float(prix))))
    out = {}
    for k, L in par.items():
        L.sort()
        out[k] = (np.array([x[0] for x in L], dtype=np.int64), np.array([x[1] for x in L]))
    return out


def _fen(j, p, a, b):
    """Les prix (log) des ventes du jour a (inclus) au jour b (exclu)."""
    i, k = bisect.bisect_left(j, a), bisect.bisect_left(j, b)
    return p[i:k]


def _ligne(cle, note, j, p, t):
    """Les variables propres a la carte au jour t (seulement les ventes AVANT t), ou None si on ne connait pas son prix."""
    w = _fen(j, p, t - P0_J, t)
    if len(w) < P0_MIN:
        w = _fen(j, p, t - P0_LONG_J, t)
        if len(w) < P0_LONG_MIN:
            return None
    p0 = _med(w)
    w30, w90 = _fen(j, p, t - 30, t), _fen(j, p, t - 90, t)
    av = _fen(j, p, t - 90, t - 30)
    w60, av2 = _fen(j, p, t - 60, t), _fen(j, p, t - 180, t - 60)
    i = bisect.bisect_left(j, t)
    q, an, se = cle[1], cle[2], cle[3]
    return {"p0": p0, "n30": math.log1p(len(w30)), "n90": math.log1p(len(w90)),
            "pente": (_med(w30) - _med(av)) if len(w30) >= 2 and len(av) >= 2 else math.nan,
            "pente2": (_med(w60) - _med(av2)) if len(w60) >= 3 and len(av2) >= 3 else math.nan,
            "etale": float(np.std(w60)) if len(w60) >= 3 else math.nan,
            "derniere": float(p[i - 1] - p0) if i else math.nan,
            "age": _saison(t) - int(an), "note": NOTES[note], "yg": 1.0 if "young guns" in q else 0.0,
            "tirage": math.log(int(se)) if se else 0.0, "anciennete": min(720, t - int(j[0])), "mois": date.fromordinal(t).month}


def _cible(j, p, t, p0, h):
    a, b = CIBLE_J[h]
    w = _fen(j, p, t + a, t + b)
    return (_med(w) - p0) if len(w) >= CIBLE_MIN else math.nan


def panneau(C, dates, cibles=True):
    """C = cartes(ventes) ; dates = des lundis (AAAA-MM-JJ). -> (lignes : liste de dict avec « cle », « note », « t », les
    VARIABLES et y30 / y60 (nan si la suite n'est pas connue))."""
    lignes = []
    for t_ in dates:
        t = _o(t_)
        du_jour = []
        for (cle, note), (j, p) in C.items():
            if len(j) < P0_MIN + (CIBLE_MIN if cibles else 0) or j[0] >= t or j[-1] < t - P0_LONG_J:
                continue
            x = _ligne(cle, note, j, p, t)
            if x is None:
                continue
            x.update(cle=cle, note_=note, t=t_, _j=cle[0], _s=" ".join(w for w in cle[1].split() if w not in set(cle[0].split())))
            if cibles:
                for h in HORIZONS:
                    x["y%d" % h] = _cible(j, p, t, x["p0"], h)
            du_jour.append(x)
        # autour de la carte : le joueur (ses AUTRES cartes), la sorte (les autres joueurs), le marche
        pj, ps, nj = {}, {}, {}
        for x in du_jour:
            if not math.isnan(x["pente"]):
                pj.setdefault(x["_j"], []).append(x["pente"])
                ps.setdefault(x["_s"], []).append(x["pente"])
            nj[x["_j"]] = nj.get(x["_j"], 0) + math.expm1(x["n30"])
        m = _med([x["pente"] for x in du_jour if not math.isnan(x["pente"])])
        def autres(L, v):                                 # sans la carte elle-meme
            if math.isnan(v):
                return L
            L = list(L)
            L.remove(v)
            return L
        for x in du_jour:
            a, b = autres(pj.get(x["_j"], []), x["pente"]), autres(ps.get(x["_s"], []), x["pente"])
            x["j_pente"] = _med(a) if a else math.nan
            x["s_pente"] = _med(b) if b else math.nan
            x["j_n30"] = math.log1p(nj.get(x["_j"], 0) - math.expm1(x["n30"]))
            x["m_pente"] = m
        lignes += du_jour
    return lignes


def matrice(lignes, h=None):
    X = np.array([[x[v] for v in VARIABLES] for x in lignes], dtype=float) if lignes else np.zeros((0, len(VARIABLES)))
    y = np.array([x.get("y%d" % h, math.nan) for x in lignes], dtype=float) if h else None
    return X, y


PARAMS = {"objective": "huber", "alpha": 0.3, "learning_rate": 0.04, "num_leaves": 31, "min_data_in_leaf": 200, "feature_fraction": 0.8,
          "bagging_fraction": 0.8, "bagging_freq": 1, "lambda_l2": 5.0, "verbose": -1, "seed": 7, "num_threads": 2}
ARBRES = 400


def apprendre(lignes, h, params=None, arbres=ARBRES, variables=None):
    """-> un modele (dict, en texte) appris sur les lignes qui ont leur cible a l'horizon h."""
    import lightgbm as lgb
    var = list(variables or VARIABLES)
    X = np.array([[x[v] for v in var] for x in lignes], dtype=float)
    y = np.array([x.get("y%d" % h, math.nan) for x in lignes], dtype=float)
    ok = ~np.isnan(y)
    b = lgb.train({**PARAMS, **(params or {})}, lgb.Dataset(X[ok], np.clip(y[ok], -BORNE, BORNE)), num_boost_round=arbres)
    return {"h": h, "variables": var, "texte": b.model_to_string(), "n": int(ok.sum())}


_BOOST = {}


def predire(modele, lignes):
    """-> les ecarts predits (log) ; la regle « le prix ne bouge pas » (modele None ou « zero ») : 0."""
    if not lignes:
        return np.zeros(0)
    if modele in (None, "zero"):
        return np.zeros(len(lignes))
    if isinstance(modele, dict) and modele.get("bruit") is not None:      # le PIEGE des tests : une version mauvaise expres
        r = np.random.default_rng(int(modele.get("graine") or 0))
        return r.normal(0, float(modele["bruit"]), len(lignes))
    import lightgbm as lgb
    k = id(modele)
    if k not in _BOOST or _BOOST[k][0] is not modele:
        _BOOST[k] = (modele, lgb.Booster(model_str=modele["texte"]))
    X = np.array([[x[v] for v in modele["variables"]] for x in lignes], dtype=float)
    return np.clip(_BOOST[k][1].predict(X), -BORNE, BORNE)


def erreurs(pred, y):
    """L'erreur de chaque prediction : l'ecart absolu (log) entre le prix predit et le prix obtenu."""
    return np.abs(np.asarray(pred) - np.asarray(y))


def decider(err_champion, err_aspirant, n_min=N_MIN, gain_min=GAIN_MIN, confiance=CONFIANCE, tirages=TIRAGES, graine=0):
    """Les erreurs des DEUX versions sur les MEMES predictions murries -> {« promu »: bool, « raison », chiffres}.
    L'aspirant est promu seulement si : assez de predictions, il fait mieux en moyenne d'au moins gain_min, et son avance
    tient dans `confiance` des tirages bootstrap (paires : la meme carte, le meme jour)."""
    a = np.asarray(err_champion, dtype=float)
    b = np.asarray(err_aspirant, dtype=float)
    ok = ~(np.isnan(a) | np.isnan(b))
    a, b = a[ok], b[ok]
    n = len(a)
    r = {"n": n, "erreur_champion": round(float(a.mean()), 5) if n else None, "erreur_aspirant": round(float(b.mean()), 5) if n else None}
    if n < n_min:
        return {**r, "promu": False, "raison": f"seulement {n} predictions murries (il en faut {n_min})"}
    d = a - b                                                             # > 0 : l'aspirant se trompe moins
    gain = float(d.mean()) / max(1e-9, float(a.mean()))
    rng = np.random.default_rng(graine)
    moy = np.array([d[rng.integers(0, n, n)].mean() for _ in range(tirages)])
    bas = float(np.quantile(moy, 1 - confiance))
    r.update(gain=round(gain, 4), borne_basse=round(bas, 5))
    if gain < gain_min:
        return {**r, "promu": False, "raison": f"pas assez mieux ({gain:+.1%}, il faut {gain_min:+.0%})"}
    if bas <= 0:
        return {**r, "promu": False, "raison": f"pas prouve : son avance ne tient pas dans {confiance:.0%} des tirages"}
    return {**r, "promu": True, "raison": f"mieux de {gain:.1%} sur {n} predictions, prouve a {confiance:.0%}"}


def bilan(pred, y, seuil=0.10):
    """Ce qu'on montre : l'erreur, celle de « le prix ne bouge pas », et le SENS quand le modele annonce un mouvement >= seuil."""
    pred, y = np.asarray(pred, dtype=float), np.asarray(y, dtype=float)
    ok = ~np.isnan(y)
    pred, y = pred[ok], y[ok]
    if not len(y):
        return {"n": 0}
    fort = np.abs(pred) >= seuil
    return {"n": int(len(y)), "erreur": round(float(np.abs(pred - y).mean()), 4), "erreur_zero": round(float(np.abs(y).mean()), 4),
            "gain_vs_zero": round(1 - float(np.abs(pred - y).mean()) / max(1e-9, float(np.abs(y).mean())), 4),
            "annonces": int(fort.sum()), "bon_sens": round(float((np.sign(pred[fort]) == np.sign(y[fort])).mean()), 3) if fort.any() else None,
            "hausse_annoncee_obtenue": round(float(np.median(y[fort & (pred > 0)])), 3) if (fort & (pred > 0)).any() else None,
            "baisse_annoncee_obtenue": round(float(np.median(y[fort & (pred < 0)])), 3) if (fort & (pred < 0)).any() else None}


# -- 4. le tour de decision, par SEGMENT (horizon x raw / gradee) ----------------------------------------------------------
# Banc du 27 nov 2026 (789 073 ventes rangees par carte exacte, 168 935 lignes ; appris mois par mois sans jamais voir la suite,
# teste de janvier 2025 a septembre 2026) : a 30 jours, sur les cartes RAW, le modele bat « le prix ne bouge pas » (+3,4 %) ;
# sur les PSA 9 / PSA 10 et a 60 jours, NON. Une seule decision pour tout aurait donc empire une partie. Chaque segment a son
# champion ; au depart, partout : « le prix ne bouge pas » (ZERO). Un modele ne prend un segment qu'apres l'avoir prouve.
# Le systeme rejoue sur le passe (chaque mois : un aspirant appris sans la suite ; les predictions murries des 8 derniers mois
# decident ; le champion EN PLACE au moment de predire est celui qui compte), regle 1 000 / 3 % :
#   30-raw : 29 256 predictions, erreur 0,309 contre 0,313 (+1,2 %, prouve) ; quand il annonce un mouvement de 10 % et plus :
#            le bon sens 67 % du temps (5 708 annonces). 30-gradee, 60-raw, 60-gradee : la regle reste (0,0 %, jamais pire).
ZERO = "zero"


def segment(x, h):
    return "%d-%s" % (h, "raw" if x.get("note") in (0, "raw") else "gradee")


def etat_initial():
    return {"%d-%s" % (h, g): {"champion": ZERO, "reserve": None, "historique": []} for h in HORIZONS for g in ("raw", "gradee")}


def tour(etat, mures, le=None, **regles):
    """etat : {segment: {champion, reserve, historique}} ; mures : {segment: {version: erreurs}} ou les erreurs de toutes les
    versions sont ALIGNEES (les memes predictions murries, dans le meme ordre). -> (nouvel etat, decisions).
    1) la RESERVE (l'ancien champion) reprend sa place si elle bat le champion ; 2) sinon, le meilleur aspirant promu le remplace."""
    etat = json.loads(json.dumps(etat))
    decisions = []
    for seg, e in etat.items():
        m = mures.get(seg) or {}
        ch = e["champion"]
        if ch not in m:
            continue
        nouveau, d_ = None, None
        if e.get("reserve") and e["reserve"] in m:
            d = decider(m[ch], m[e["reserve"]], **regles)
            decisions.append({"segment": seg, "champion": ch, "aspirant": e["reserve"], "reserve": True, **d})
            if d["promu"]:
                nouveau, d_ = e["reserve"], d
        if nouveau is None:
            best = None
            for v, err in m.items():
                if v in (ch, e.get("reserve")):
                    continue
                d = decider(m[ch], err, **regles)
                decisions.append({"segment": seg, "champion": ch, "aspirant": v, **d})
                if d["promu"] and (best is None or d["gain"] > best[1]["gain"]):
                    best = (v, d)
            if best:
                nouveau, d_ = best
        if nouveau is not None:
            e["historique"] = (e.get("historique") or [])[-49:] + [{"le": le, "de": ch, "a": nouveau, "gain": d_["gain"], "n": d_["n"], "raison": d_["raison"]}]
            e["reserve"], e["champion"] = ch, nouveau
    return etat, decisions


def ecrire(modele):
    return json.dumps(modele, ensure_ascii=False)


def lire(texte):
    return json.loads(texte)
