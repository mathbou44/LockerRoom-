"""
SLABCOACH - le modele du Score SlabCoach (10 nov 2026).

Mathieu : « une precision a minimum 9 sur 10 avec un seuil de confiance a 9 sur 10 ». Banc (admin, interne) : 145 179
ventes de hockey reelles (mai-oct. 2026) ; apprentissage sur les ventes avant le 8 oct., test sur les 32 826 d'apres :
  precision 0,908 (quand une carte s'est vendue au moins 2 fois plus cher qu'une autre, le score les met dans le bon ordre
  9 fois sur 10), confiance 0,905 (5e centile sur 60 tirages). Le score fait a la main d'avant : 0,711.

Ce qui entre dans le score (a l'ecran) : le TITRE de l'annonce SANS le nom du joueur (sets, inserts, paralleles,
numerotation, auto, patch, gradation...) et des donnees PUBLIQUES sur le joueur (demande legale, Indice de la semaine,
Wikipedia, carriere, Temple, catalogue). AUCUN prix. Les poids sont appris hors ligne sur des ventes (zone grise : ventes
tierces, jamais montrees ni stockees ici).

Le modele est exporte en tableaux numpy (score_modele.npz + score_modele_vocab.json.gz) : aucune version de scikit-learn
n'est requise pour s'en servir sur Render. Sans fichier : score_slab garde son calcul simple.
"""
import gzip
import json
import math
import os
import re

import numpy as np

DOSSIER = os.path.dirname(os.path.abspath(__file__))
CHEMIN_NPZ = os.path.join(DOSSIER, "score_modele.npz")
CHEMIN_VOC = os.path.join(DOSSIER, "score_modele_vocab.json.gz")
COLS = ['annee', 'serie', 'num', 'auto', 'patch', 'rc', 'inscr', 'npar', 'indice', 'dem', 'v60', 'v20', 'wlen', 'hhof', 'top100',
        'troph', 'saisons', 'actif', 'car_pts', 'repech', 'an_rep', 'l5']
GRADES = {'psa': 1, 'bgs': 2, 'sgc': 3, 'cgc': 4}
_M = {"m": None, "essai": False}
# la derniere mesure du banc (hors ligne, sur des ventes jamais vues) : montree dans Admin > Validation
BANC = {"le": "2026-11-10", "ventes_test": 32826, "ventes_apprentissage": 112353, "precision": 0.908, "confiance": 0.905,
        "avant": 0.711, "regle": "paires dont l'une s'est vendue au moins 2 fois plus cher ; confiance = 5e centile (bootstrap)",
        # 11 nov 2026 : le score suit-il le marche ? quand les cartes d'un joueur bougent de 15 % et + d'une semaine a l'autre,
        # le score bouge dans le meme sens (memoire du marche) ; sans la memoire : 0,787
        "tendance": 0.841, "tendance_avant": 0.787,
        # 11 nov 2026 : SlabIQ v3 (score_appris : memoire du marche, voisins, mots, rarete du catalogue), meme banc
        "v3": {"precision": 0.9316, "confiance": 0.9294, "moteur": "lgb_leger", "pic_memoire_go": 1.7}}


# -- 1. les caracteristiques (les memes a l'apprentissage et a l'ecran) ---------------------------------------------------
def brut(titre, joueur=None, base=None, indice=None, demande=None):
    """Ce qu'on sait d'une annonce sans son prix : le titre sans le nom du joueur, la carte, le joueur (public)."""
    import cartes_match as cm
    import demande_legale as dl
    d = cm._decoder_memo(titre or "")
    nom = cm.joueur_du_titre(titre or "", joueur) if not joueur else cm.norm(joueur)
    if base is None:
        base = (dl.lire() or {}).get("joueurs") or {}
    idx = _index(base)
    k = idx.get(dl._norm(nom)) or _alias(dl._norm(nom))
    e = base.get(k) or {}
    h, w = e.get('nhl') or {}, e.get('wiki') or {}
    if indice is None:
        try:
            import indice_joueurs
            v = indice_joueurs.indice(k) if k else None
        except Exception:
            v = None
    else:
        v = indice.get(k) if k else None
    v = v or {}
    ns = cm.numero_serie(titre or "")
    txt = d['texte']
    for m in (nom or '').split():
        txt = re.sub(r'\b' + re.escape(m) + r'\b', ' ', txt)
    # la demande : celle deja calculee par l'Indice (la foret de demande_legale est lente : 0,25 s par joueur)
    dem = v.get('dem')
    if dem is None and k:
        if demande is not None:
            try:
                dem = demande(k)
            except Exception:
                dem = None
        else:
            dem = ((getattr(dl, "_MEMO", None) or {}).get("d") or {}).get(dl._norm(k))
    return {'t': re.sub(r'\s+', ' ', txt).strip(), 'joueur': k or nom, 'connu': bool(k),
            'annee': d.get('annee'), 'serie': d.get('serie') or (ns[1] if ns else None), 'num': ns[0] if ns else None,
            'auto': d['auto'], 'patch': d['patch'], 'rc': d['rc'], 'inscr': d['inscr'], 'exclu': d['exclu'],
            'grade': (d['grade'] or {}).get('cie'), 'note': (d['grade'] or {}).get('note'), 'npar': len(d['paralleles']),
            'indice': v.get('indice'), 'dem': dem, 'v60': w.get('v60'), 'v20': w.get('v20'), 'wlen': w.get('len'),
            'hhof': h.get('hhof'), 'top100': h.get('top100'), 'troph': h.get('trophees_n'), 'saisons': h.get('saisons'),
            'actif': h.get('actif'), 'car_pts': (h.get('carriere') or {}).get('points'), 'repech': h.get('repech'),
            'an_rep': h.get('an_repech'), 'l5': h.get('l5'),
            # 11 nov 2026 (v2 : « tester de nouvelles entrees ») : publiques aussi (LNH) - equipe, pays, position, age, rythme
            'equipe': h.get('equipe'), 'pays': h.get('pays'), 'prov': h.get('province'), 'pos': h.get('pos'), 'naiss': h.get('naissance'),
            'ronde': h.get('ronde'), 'sa': h.get('saison') or {}, 'ps': h.get('par_saison') or [], 'tc': h.get('trophees_c') or {},
            'crit': v.get('criteres') or {}, 'creux': v.get('creux')}


_IDX = {"id": None, "i": {}}


def _index(base):
    import demande_legale as dl
    if _IDX["id"] != id(base):
        _IDX.update(id=id(base), i={dl._norm(k): k for k in base})
        # 11 nov 2026 (« Alexander Ovechkin » dans les titres, « Alex Ovechkin » a la LNH) : initiale + nom de famille, si unique
        a = {}
        for nk, k in _IDX["i"].items():
            w = nk.split()
            if len(w) >= 2:
                a.setdefault(w[0][:1] + " " + w[-1], []).append(k)
        _IDX["a"] = {c: l[0] for c, l in a.items() if len(l) == 1}
    return _IDX["i"]


def _alias(nk):
    w = (nk or "").split()
    if len(w) < 2:
        return None
    return (_IDX.get("a") or {}).get(w[0][:1] + " " + w[-1])


def _num(x, k):
    v = x.get(k)
    try:
        return np.nan if v is None else float(v)
    except (TypeError, ValueError):
        return np.nan


def numeriques(x, pres=None):
    import demande_legale as dl
    pres_n, pres_h = pres or dl.presence_catalogue()
    k = dl._norm(x.get('joueur') or '')
    s, n = x.get('serie'), x.get('num')
    note = str(x.get('note') or '')
    return [_num(x, c) for c in COLS] + [GRADES.get(x.get('grade') or '', 0), float(note) if note.replace('.', '').isdigit() else np.nan,
                                        pres_n.get(k, 0), pres_h.get(k, 0), 1.0 if s == 1 else 0.0, (n / s) if s and n else np.nan,
                                        1.0 if (s and n and n == s) else 0.0, (2026 - x['annee']) if x.get('annee') else np.nan]


PAYS = {"CAN": 1, "USA": 2, "SWE": 3, "FIN": 4, "RUS": 5, "CZE": 6, "SVK": 7, "CHE": 8, "DEU": 9}
POS = {"C": 1, "L": 2, "R": 3, "D": 4, "G": 5}
MARCHES = {"TOR": 3, "MTL": 3, "NYR": 2, "CHI": 2, "BOS": 2, "EDM": 2, "VAN": 2, "PIT": 2, "DET": 2, "PHI": 2, "LAK": 1.5, "CGY": 1.5,
           "OTT": 1.5, "WPG": 1, "NJD": 1, "NYI": 1}
NOMS2 = ["pays", "qc", "pos", "age_j", "ronde", "sa_ppm", "sa_mj", "av_ppm", "car_ppm", "junior_ppm", "toi", "marche", "coupes", "hart",
         "calder", "c_forme", "c_asc", "c_buzz", "c_notor", "c_dem", "creux"]


def numeriques2(x, aujourdhui=None):
    """Les entrees publiques ajoutees le 11 nov 2026 (modele v2 seulement)."""
    import datetime as _dt
    today = aujourdhui or _dt.date.today()
    age = np.nan
    try:
        nn = _dt.date.fromisoformat(str(x.get("naiss") or "")[:10])
        age = (today - nn).days / 365.25
    except ValueError:
        pass
    sa = x.get("sa") or {}
    mj = sa.get("gamesPlayed") or 0
    ps = [p for p in x.get("ps") or [] if p.get("gp")]
    nhl = [p for p in ps if p.get("l") == "NHL"]
    av = [p for p in nhl[:-1] if (p.get("gp") or 0) >= 40][-2:] if nhl else []
    jun = [p for p in ps if p.get("l") in ("OHL", "WHL", "QMJHL", "LHJMQ", "USHL", "NCAA", "SHL", "Liiga", "KHL", "AHL") and (p.get("gp") or 0) >= 15]
    car = sum(p.get("p") or 0 for p in nhl), sum(p.get("gp") or 0 for p in nhl)
    toi = np.nan
    try:
        mm, ss = str((nhl[-1] if nhl else {}).get("toi") or "").split(":")[:2]
        toi = int(mm) + int(ss) / 60
    except (ValueError, TypeError):
        pass
    tc = x.get("tc") or {}
    cr = x.get("crit") or {}
    cx = x.get("creux") or {}
    f = lambda v: np.nan if v is None else float(v)
    return [PAYS.get(x.get("pays") or "", 0 if x.get("pays") else np.nan), 1.0 if str(x.get("prov") or "").lower() in ("québec", "quebec", "qc") else 0.0,
            POS.get(x.get("pos") or "", np.nan), age, f(x.get("ronde")), (sa.get("points") or 0) / mj if mj >= 3 else np.nan, float(mj) if sa else np.nan,
            max(((p.get("p") or 0) / p["gp"] for p in av), default=np.nan), car[0] / car[1] if car[1] >= 20 else np.nan,
            max(((p.get("p") or 0) / p["gp"] for p in jun), default=np.nan), toi, MARCHES.get(x.get("equipe") or "", 0.5 if x.get("equipe") else np.nan),
            f(tc.get("Stanley Cup")), f(tc.get("Hart Memorial Trophy")), f(tc.get("Calder Memorial Trophy")),
            f(cr.get("forme")), f(cr.get("ascension")), f(cr.get("buzz")), f(cr.get("notoriete")), f(cr.get("demande")),
            (-1.0 if cx.get("etat") == "creux" else 1.0) * (cx.get("potentiel") or 0) if cx else 0.0]


# -- 2. le modele exporte (sans scikit-learn) --------------------------------------------------------------------------------
def _empreinte():
    """La date du modele reappris sur le disque (ou 0) : quand le processus de la nuit en ecrit un nouveau, chaque
    travailleur du serveur le recharge tout seul (verifie au plus une fois par 2 minutes)."""
    try:
        import score_appris
        return os.path.getmtime(os.path.join(score_appris.dossier(), "modele.npz"))
    except (OSError, ImportError):
        return 0.0


def charger():
    """11 nov 2026 : le modele REAPPRIS (disque du serveur, score_appris) s'il est la ; sinon celui du depot (v7)."""
    import time as _t
    if (_M["m"] is not None or _M["essai"]) and _t.time() - _M.get("vu_le", 0) > 120:
        _M["vu_le"] = _t.time()
        if _empreinte() != _M.get("empreinte", 0.0):
            recharger()
    if _M["m"] is not None or _M["essai"]:
        return _M["m"]
    _M["essai"] = True
    _M["vu_le"] = _t.time()
    _M["empreinte"] = _empreinte()
    try:
        import score_appris
        score_appris._CACHE["vois"].clear()          # les vecteurs des voisins suivent le vocabulaire du modele
    except Exception:
        pass
    _M["m"] = None
    try:
        import score_appris
        if score_appris.present():
            d = score_appris.dossier()
            _M["m"] = _lire(os.path.join(d, "modele.npz"), os.path.join(d, "vocab.json.gz"))
            _M["m"]["source"] = "reappris"
    except Exception as e:
        print("Score modele (reappris) : " + repr(e), flush=True)
        _M["m"] = None
    if _M["m"] is None:
        try:
            _M["m"] = _lire(CHEMIN_NPZ, CHEMIN_VOC)
            _M["m"]["source"] = "depot"
        except (OSError, ValueError, KeyError) as e:
            print("Score modele : " + repr(e), flush=True)
            _M["m"] = None
    return _M["m"]


def _lire(npz, voc_ch):
    z = np.load(npz)
    with gzip.open(voc_ch, "rt", encoding="utf-8") as f:
        voc = json.load(f)
    zz = {k: z[k] for k in z.files}
    return {"z": zz, "vw": voc["mots"], "vc": voc["car"], "vt": voc.get("tok") or {}, "nw": len(voc["mots"]), "v": int(zz.get("version", 1))}


def modele_depot():
    """Le modele livre avec le code (v7, sans etat) : la reference du 1er reapprentissage."""
    try:
        return _lire(CHEMIN_NPZ, CHEMIN_VOC)
    except (OSError, ValueError, KeyError):
        return None


def recharger():
    _M.update(m=None, essai=False, vu_le=0, empreinte=0.0)


_TOK = re.compile(r'(?u)\b[\w/]+\b')


def _mots(t):
    toks = _TOK.findall(t.lower())
    out = []
    for n in (1, 2, 3):
        out += [" ".join(toks[i:i + n]) for i in range(len(toks) - n + 1)]
    return out


def _mots12(t):
    toks = _TOK.findall(t.lower())
    return set(toks + [" ".join(toks[i:i + 2]) for i in range(len(toks) - 1)])


def _car(t):
    """Les n-grammes de caracteres « char_wb » 2 a 5, exactement comme scikit-learn (_char_wb_ngrams)."""
    out = []
    for w in re.sub(r"\s\s+", " ", t.lower()).split():
        w = " " + w + " "
        lw = len(w)
        for n in range(2, 6):
            off = 0
            out.append(w[off:off + n])
            while off + n < lw:
                off += 1
                out.append(w[off:off + n])
            if off == 0:
                break
    return out


def _tfidf(grams, voc, idf, decal):
    c = {}
    for g in grams:
        j = voc.get(g)
        if j is not None:
            c[j] = c.get(j, 0) + 1
    if not c:
        return {}
    v = {j + decal: (1 + math.log(n)) * idf[j] for j, n in c.items()}
    norme = math.sqrt(sum(x * x for x in v.values())) or 1.0
    return {j: x / norme for j, x in v.items()}


def _arbres(z, X):
    """La prediction des arbres exportes (scikit-learn ou LightGBM) : base + la somme des feuilles atteintes.
    11 nov 2026 (vitesse) : TOUS les arbres avancent ensemble, niveau par niveau (lignes x arbres en une matrice)."""
    n = X.shape[0]
    out = np.full(n, float(z["base"]))
    if not n:
        return out
    debuts, val, fi, th, ml, gch, drt, feuille = z["debuts"], z["valeur"], z["feature"], z["seuil"], z["manque_gauche"], z["gauche"], z["droite"], z["feuille"]
    mt = z.get("type_manque")
    d0 = np.asarray(debuts[:-1], dtype=np.int64)
    T = len(d0)
    for r0 in range(0, n, 256):                         # par paquets de lignes : la memoire reste petite
        Xr = X[r0:r0 + 256]
        m = Xr.shape[0]
        i = np.broadcast_to(d0, (m, T)).copy()
        lig = np.broadcast_to(np.arange(m)[:, None], (m, T))
        for _ in range(64):
            nf = feuille[i] == 0
            if not nf.any():
                break
            k = i[nf]
            v = Xr[lig[nf], fi[k]]
            if mt is None:
                gauche = np.where(np.isnan(v), ml[k] == 1, v <= th[k])
            else:                     # LightGBM : NaN -> 0 (« None »), 0 et NaN manquants (« Zero »), NaN manquant (« NaN »)
                t_ = mt[k]
                nan_ = np.isnan(v)
                manque = np.where(t_ == 2, nan_, np.where(t_ == 1, nan_ | (v == 0), False))
                vv = np.where(nan_, 0.0, v)
                gauche = np.where(manque, ml[k] == 1, vv <= th[k])
            base_t = np.broadcast_to(d0, (m, T))[nf]
            i[nf] = base_t + np.where(gauche, gch[k], drt[k])
        out[r0:r0 + m] += val[i].sum(axis=1)
    return out


def vec_car(t, m=None):
    """Le vecteur des morceaux de mots (normalise) d'un titre : sert aux voisins (score_appris)."""
    m = m or charger()
    return _tfidf(_car(t or ""), m["vc"], m["z"]["idf_car"], 0)


def _matrice(bruts, m):
    import scipy.sparse as sp
    z, nw = m["z"], m["nw"]
    ri, ci, va = [], [], []
    for r_, x in enumerate(bruts):
        v = _tfidf(_mots(x['t']), m["vw"], z["idf_mots"], 0)
        v.update(_tfidf(_car(x['t']), m["vc"], z["idf_car"], nw))
        for j, w in v.items():
            ri.append(r_); ci.append(j); va.append(w)
    return sp.csr_matrix((va, (ri, ci)), shape=(len(bruts), z["ridge_w"].shape[0]))


def texte_pred(bruts, m=None):
    m = m or charger()
    return _matrice(bruts, m) @ m["z"]["ridge_w"].astype(np.float64) + float(m["z"]["ridge_b"])


def predire(bruts, pres=None, m=None):
    """[brut] -> log du « niveau de demande » predit (echelle interne), ou None sans modele. m : un autre modele charge."""
    m = m or charger()
    if not m:
        return None
    z = m["z"]
    if m.get("v", 1) >= 2:
        # 11 nov 2026 : le modele reappris : texte + public + la memoire du marche (mise a jour chaque jour) + voisins
        import score_appris
        M = _matrice(bruts, m)
        texte = M @ z["ridge_w"].astype(np.float64) + float(z["ridge_b"])
        comp = M @ z["svd"].T.astype(np.float64)
        Xn = np.array([numeriques(x, pres) for x in bruts], dtype=float)
        if int(z.get("extra", 0)):
            Xn = np.column_stack([Xn, np.array([numeriques2(x) for x in bruts], dtype=float)])
        Xm = score_appris.caracteristiques(bruts, lambda t: vec_car(t, m), xv=bool(int(z.get("xv", 0))))
        parts = [texte, Xn, comp, Xm]
        if int(z.get("rar", 0)):
            import rarete_cat
            parts.append(np.array([rarete_cat.rarete(x) for x in bruts], dtype=float))
        nt = int(z.get("ntok", 0))
        if nt:                                     # v3 : la presence des mots du titre (1-2 mots), comme a l'apprentissage
            Tk = np.zeros((len(bruts), nt))
            for r_, x in enumerate(bruts):
                for g in _mots12(x["t"]):
                    j = m["vt"].get(g)
                    if j is not None:
                        Tk[r_, j] = 1.0
            parts.append(Tk)
        X = np.column_stack(parts)
        return _arbres(z, X)
    nw = m["nw"]
    lignes = []
    for x in bruts:
        v = _tfidf(_mots(x['t']), m["vw"], z["idf_mots"], 0)
        v.update(_tfidf(_car(x['t']), m["vc"], z["idf_car"], nw))
        lignes.append(v)
    # le texte : ridge + composantes (SVD) ; mots et caracteres ont chacun leur norme l2, comme a l'apprentissage
    import scipy.sparse as sp
    ri, ci, va = [], [], []
    for r_, v in enumerate(lignes):
        for j, x in v.items():
            ri.append(r_); ci.append(j); va.append(x)
    M = sp.csr_matrix((va, (ri, ci)), shape=(len(lignes), z["ridge_w"].shape[0]))
    texte = M @ z["ridge_w"].astype(np.float64) + float(z["ridge_b"])
    comp = M @ z["svd"].T.astype(np.float64)
    Xn = np.array([numeriques(x, pres) for x in bruts], dtype=float)
    X = np.column_stack([texte, Xn, comp])
    return _arbres(z, X)


def scores(titres, joueurs=None):
    """[(titre)] -> [score 0-100] : le rang de la demande predite parmi les ventes du banc. None sans modele."""
    m = charger()
    if not m:
        return None
    joueurs = joueurs or [None] * len(titres)
    import demande_legale as dl
    base = (dl.lire() or {}).get("joueurs") or {}
    pres = dl.presence_catalogue()
    b = [brut(t, j, base=base) for t, j in zip(titres, joueurs)]
    p = predire(b, pres)
    q = m["z"]["quantiles"]
    return [int(round(100 * np.searchsorted(q, v) / len(q))) if informatif(t, b=bb) else None for v, t, bb in zip(p, titres, b)]


# 12 nov 2026 (nuit de revue) : « Test » sortait a 85 (« tres recherchee ») et « Nike shoes size 10 » aussi haut : sans
# joueur connu, sans annee et sans un mot de carte, le modele extrapole. Ces titres-la n'ont pas de score (None) : l'app
# dit « pas assez d'infos » au lieu d'inventer.
_MOTS_CARTE = re.compile(r"\b(rookie|rc|auto|autograph|patch|jersey|young guns|yg|psa|bgs|sgc|cgc|tag|refractor|prizm|upper deck|ud|"
                         r"o-pee-chee|opc|topps|panini|the cup|sp authentic|spx|parkhurst|bowman|chrome|parallel|insert|numbered|ssp|"
                         r"canvas|exclusives|high gloss|future watch|logo|card|carte)\b|/\s*\d{1,4}\b|#\s*\d+")


def informatif(titre, joueur=None, b=None):
    """Le titre donne-t-il assez d'indices pour un score ? (un joueur connu, une annee, ou un mot de carte)"""
    if b is None:
        import demande_legale as dl
        b = brut(titre or "", joueur, base=(dl.lire() or {}).get("joueurs") or {})
    if not isinstance(b, dict) or b.get("exclu"):
        return False
    return bool(b.get("connu") or b.get("annee") or _MOTS_CARTE.search((titre or "").lower()))


def score(titre, joueur=None):
    r = scores([titre], [joueur])
    return r[0] if r else None
