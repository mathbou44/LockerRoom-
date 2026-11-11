"""
SLABCOACH - le Score SlabCoach APPRIS et REAPPRIS (11 nov 2026).

Mathieu : « a toutes les semaines, le modele reapprend, il prend les nouvelles donnees ; il faut toujours etre a jour, c'est
un marche qui change tres vite ; tres tres precis dans l'ordre des cartes » ; « valide tout avec les ventes (SoldComps) ;
on joue dans la zone grise pour batir notre programme ».

Le meme code sert au banc (hors ligne, la mesure) et au serveur (Render) : ce qui est mesure est ce qui tourne.

Ce que le modele regarde (jamais le prix de l'annonce a noter) :
  1. le TITRE sans le nom du joueur (mots et morceaux de mots : set, insert, parallele, numerotation, auto, patch, note) ;
  2. le JOUEUR, en donnees publiques : Indice de la semaine, demande, Wikipedia, carriere, Temple, repechage, catalogue ;
  3. la MEMOIRE DU MARCHE (zone grise : ventes tierces, jamais montrees aux utilisateurs) mise a jour CHAQUE JOUR :
     l'ecart entre ce que les cartes d'un joueur se vendent et ce que leur titre laisse prevoir, sur 7, 30 et ~1000 jours,
     par joueur, joueur x sorte de carte (auto, patch, recrue, numerotation, gradation), joueur x saison, joueur x produit,
     segment du marche, carte exacte ; le niveau de l'insert (sans le joueur) et du produit ;
  4. les VOISINS : les cartes du meme joueur deja vendues qui ressemblent le plus a celle-ci (texte).
Le score = le rang (0-100) de la prediction parmi les ventes d'apprentissage.

Le calendrier (server.py, toutes les heures) :
  - chaque jour : les ventes de la veille (base_ventes) entrent dans la memoire -> les scores bougent avec le marche ;
  - chaque semaine (la nuit) : reapprentissage complet dans un processus a part, mesure sur les 10 derniers jours JAMAIS
    vus ; le nouveau modele ne remplace l'ancien que s'il fait au moins aussi bien (garde-fou) ; tout est note dans
    l'historique (Admin > Validation).
"""
import gc
import gzip
import json
import math
import os
import re
import sqlite3
import sys
import threading
import time
from datetime import date, datetime, timedelta

import numpy as np

HL = (7.0, 30.0, 1000.0)
EXTRA = os.environ.get("LR_SCORE_EXTRA", "1") != "0"
K_VOIS = 10
VOIS_MAX = 400                       # ventes gardees par joueur pour les voisins
COUPE_JOURS = 10                     # le reapprentissage se mesure sur ses 10 derniers jours (jamais vus)
FENETRE_JOURS = 180                  # les ventes utilisees pour apprendre
MAX_VENTES = int(os.environ.get("LR_SCORE_MAX_VENTES", "110000"))   # au plus (les plus recentes) : la memoire du serveur
MO_LIBRES_MIN = float(os.environ.get("LR_SCORE_MO_LIBRES", "1300"))  # 145 000 ventes, moteur leger : pic mesure de 1,7 Go
REAPPRENDRE_J = 7
HEURES_NUIT = (7, 8, 9)               # heure du serveur (UTC sur Render) : 2 h a 5 h a Montreal
_verrou = threading.Lock()
_CACHE = {"vois": {}, "vois_jour": None}

STOP = set("psa bgs sgc cgc gem mint mt nm rc rookie card cards hockey nhl the and of with a new lot".split())
MARQUES = ["upper deck", "o-pee-chee", "opc", "sp authentic", "spx", "sp game used", "the cup", "ice", "artifacts", "trilogy",
           "black diamond", "allure", "synergy", "mvp", "credentials", "premier", "chronology", "clear cut", "parkhurst",
           "tim hortons", "extended", "series 1", "series 2", "young guns", "canvas", "exclusives", "high gloss", "future watch",
           "marquee rookies", "rookie patch", "platinum", "metal universe", "skybox"]


# -- 1. les cles de la memoire ------------------------------------------------------------------------------------------
def _bucket(s):
    if not s:
        return "n"
    for b in (1, 5, 10, 25, 50, 99, 199, 499):
        if s <= b:
            return str(b)
    return "g"


def sorte(b):
    g = "g10" if (b.get("grade") and str(b.get("note") or "") in ("10", "9.5")) else ("g" if b.get("grade") else "r")
    return f"{int(bool(b.get('auto')))}{int(bool(b.get('patch')))}{int(bool(b.get('rc')))}{_bucket(b.get('serie'))}{g}"


def cle_carte(b):
    t = re.sub(r"#?\b\d{1,3}/\d{1,4}\b", " ", (b.get("t") or "").lower())
    t = re.sub(r"\b(psa|bgs|sgc|cgc|gem|mint|mt|nm|rc|rookie|card|hockey|nhl)\b", " ", t)
    return (b.get("joueur") or "?") + "|" + " ".join(sorted(set(re.findall(r"[a-z0-9]+", t)))) + "|" + sorte(b)


def toks(t):
    t = re.sub(r"#?\b\d{1,3}/\d{1,4}\b", " ", (t or "").lower())
    t = re.sub(r"\b(19|20)\d\d(-\d\d)?\b", " ", t)
    return " ".join(sorted(set(w for w in re.findall(r"[a-z][a-z0-9\-]+", t) if w not in STOP)))


def produit(b):
    tl = (b.get("t") or "").lower()
    return str(b.get("annee")) + "|" + ",".join([m for m in MARQUES if m in tl][:3])


def _j(b):
    return b.get("joueur") or "?"


# (nom, cible : « res » = l'ecart prix / texte, « y » = le prix lui-meme (log), la cle)
CLES = (("j", "res", _j), ("js", "res", lambda b: _j(b) + "|" + sorte(b)), ("ja", "res", lambda b: _j(b) + "|" + str(b.get("annee"))),
        ("seg", "res", lambda b: sorte(b) + "|" + str(b.get("annee"))), ("c", "res", cle_carte),
        ("jp", "res", lambda b: _j(b) + "|" + produit(b)), ("tc", "y", lambda b: toks(b.get("t"))), ("p", "y", produit),
        ("eq", "res", lambda b: str(b.get("equipe") or "?") + "|" + sorte(b)))          # 11 nov : le marche de l'equipe
NOMS_MEM = [f"{k}_{s}{int(h)}" for k, _c, _f in CLES for h in HL for s in ("m", "w")] + [f"{k}_{s}" for k, _c, _f in CLES for s in ("dern", "age")]
NOMS_VOIS = ["v_y0", "v_s0", "v_d0", "v_moy", "v_med3", "v_s3", "v_n", "v_std", "v_n80"]
# 11 nov 2026 (v3) : les voisins ENTRE joueurs (meme saison, meme sorte), ramenes au niveau de leur joueur
NOMS_XV = ["xv_moy", "xv_s0", "xv_v0", "xv_med5", "xv_s5", "xv_moy_j"]
XV_MAX = 6000
NOMS_RAR = ["r_prod", "r_boites_carte", "r_tirage", "r_taille", "r_taux", "r_recouv"]
NTOK = 4000


def bloc_xv(b):
    return str(b.get("annee")) + "|" + sorte(b)


def _xv_feats(S, vals, lvl_self):
    """S : similarites (candidats d'avant du meme bloc), vals : prix - niveau de leur joueur -> 6 caracteristiques."""
    if not len(vals):
        return [np.nan] * len(NOMS_XV)
    o = np.argsort(-S)[:15]
    ss, v = S[o], vals[o]
    w = np.maximum(ss, 0) ** 4 + 1e-9
    moy = float((w * v).sum() / w.sum())
    return [moy, float(ss[0]), float(v[0]), float(np.median(v[:5])), float(ss[:5].mean()), moy + (0.0 if np.isnan(lvl_self) else lvl_self)]


I_JLVL = None


class Memoire:
    """L'etat roulant : cle -> [S(h)..., W(h)..., jour, derniere valeur]. Chaque lecture « vieillit » l'etat jusqu'au jour lu."""

    def __init__(self, d=None):
        self.d = d if d is not None else {}

    def lire(self, b, jour):
        n = len(HL)
        m, w, extra = [], [], []
        for k, cible, f in CLES:
            e = self.d.get(k + "\x1f" + f(b))
            for hi, h in enumerate(HL):
                if e:
                    fa = 0.5 ** ((jour - e[2 * n]) / h)
                    S, W = e[hi] * fa, e[n + hi] * fa
                    m.append((S / (W + 1.0) if cible == "res" else S / W) if W > 0 else np.nan)
                    w.append(W)
                else:
                    m.append(np.nan)
                    w.append(np.nan)
            extra += [e[2 * n + 1], jour - e[2 * n]] if e else [np.nan, np.nan]
        out = []
        i = 0
        for _k in CLES:                                    # m7, w7, m30, w30, m1000, w1000 par cle (comme NOMS_MEM)
            for hi in range(n):
                out += [m[i + hi], w[i + hi]]
            i += n
        return out + extra

    def ajouter(self, b, jour, y, res):
        n = len(HL)
        for k, cible, f in CLES:
            kk = k + "\x1f" + f(b)
            e = self.d.get(kk)
            if not e:
                e = self.d[kk] = [0.0] * (2 * n) + [jour, 0.0]
            v = res if cible == "res" else y
            for hi, h in enumerate(HL):
                fa = 0.5 ** ((jour - e[2 * n]) / h)
                e[hi] = e[hi] * fa + v
                e[n + hi] = e[n + hi] * fa + 1.0
            e[2 * n] = jour
            e[2 * n + 1] = v

    def cles(self, b):
        return [k + "\x1f" + f(b) for k, _c, f in CLES]


# -- 2. le texte (exactement les memes vecteurs a l'apprentissage et au serveur) ------------------------------------------
def _sk_vectoriseurs(textes, wmax=30000, cmax=30000):
    from sklearn.feature_extraction.text import TfidfVectorizer
    vw = TfidfVectorizer(ngram_range=(1, 3), min_df=5, sublinear_tf=True, token_pattern=r"(?u)\b[\w/]+\b", max_features=wmax, dtype=np.float32).fit(textes)
    vc = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=10, sublinear_tf=True, max_features=cmax, dtype=np.float32).fit(textes)
    return vw, vc


def _vois_feats(sims, ys, ds):
    """sims, ys, ds : les candidats (ventes d'avant du meme joueur) -> les 9 caracteristiques des voisins."""
    ok = sims > 0
    if not ok.any():
        return [np.nan] * len(NOMS_VOIS)
    o = np.argsort(-sims)[:K_VOIS]
    s, yy, dd = sims[o], ys[o], ds[o]
    m = s > 0
    s, yy, dd = s[m], yy[m], dd[m]
    w = s ** 4
    return [yy[0], s[0], dd[0], float((w * yy).sum() / w.sum()), float(np.median(yy[:3])), float(s[:3].mean()), float(len(s)),
            float(yy.std()) if len(s) > 1 else np.nan, float((s > 0.8).sum())]


# -- 3. l'apprentissage (banc ET serveur) ---------------------------------------------------------------------------------
PICK = re.compile(r"\b(you pick|pick your|choose|complete your|from list|u pick|lot of|lots?\b|team set|set of|\d+\s*card lot|bundle|"
                  r"mystery|repack|break)\b", re.I)


def preparer(ventes, base=None, indice=None, sport="hockey"):
    """ventes : [(titre, prix, 'AAAA-MM-JJ')] -> (bruts, y, jours ordinaux), tries par jour ; aberrants, lots, « choisis ta
    carte » et autres sports retires (comme au banc)."""
    import score_modele as sm
    import demande_legale as dl
    import sports
    if base is None:
        base = (dl.lire() or {}).get("joueurs") or {}
    if indice is None:
        try:
            import indice_joueurs
            indice = indice_joueurs.lire().get("indice") or {}
        except Exception:
            indice = {}
    L = []
    for t, p, j in ventes:
        try:
            p = float(p)
            jo = date.fromisoformat(str(j)[:10]).toordinal()
        except (TypeError, ValueError):
            continue
        if not (0.5 <= p <= 50000) or not t:
            continue
        t = re.sub(r"^\d{6,}\s+", "", str(t))
        b = sm.brut(t, base=base, indice=indice)
        if b.get("exclu") or PICK.search(b["t"]):
            continue
        if sport and sports.detecter(b["t"] + " " + (b.get("joueur") or ""), defaut="inconnu") != sport:
            continue
        L.append((jo, b, math.log(p)))
    L.sort(key=lambda x: x[0])
    return [x[1] for x in L], np.array([x[2] for x in L]), np.array([x[0] for x in L])


def _mo():
    try:
        with open("/proc/self/status") as f:
            return next(int(l.split()[1]) // 1024 for l in f if l.startswith("VmRSS"))
    except (OSError, StopIteration, ValueError):
        return -1


def entrainer(bruts, y, jours, coupe=None, iters=1000, log=print):
    """Apprend le modele. coupe (jour ordinal) : apprend AVANT, mesure APRES (jamais vu) et rend la mesure.
    -> {"modele": tableaux a exporter, "memoire": Memoire a la fin, "vois": ventes par joueur, "mesure": {...} ou None}."""
    import scipy.sparse as sp
    from sklearn.linear_model import Ridge
    from sklearn.model_selection import KFold
    from sklearn.decomposition import TruncatedSVD
    from sklearn.ensemble import HistGradientBoostingRegressor
    import score_modele as sm
    import demande_legale as dl
    n = len(bruts)
    tr = jours < coupe if coupe else np.ones(n, bool)
    te = ~tr
    T = [b["t"] for b in bruts]
    vw, vc = _sk_vectoriseurs([t for t, a in zip(T, tr) if a])
    Xw, Xc = vw.transform(T), vc.transform(T)
    Xt = sp.hstack([Xw, Xc], format="csr", dtype=np.float32)
    del Xw                                                   # 11 nov 2026 : la memoire du serveur (2 Go partages avec l'app)
    itr = np.where(tr)[0]
    oof = np.zeros(n)
    for a, b_ in KFold(5, shuffle=True, random_state=0).split(itr):
        oof[itr[b_]] = Ridge(alpha=1.0).fit(Xt[itr[a]], y[itr[a]]).predict(Xt[itr[b_]])
    rid = Ridge(alpha=1.0).fit(Xt[tr], y[tr])
    if te.any():
        oof[te] = rid.predict(Xt[te])
    res = y - oof
    log(f"texte ok ({_mo()} Mo)")
    svd = TruncatedSVD(n_components=64, random_state=0).fit(Xt[tr] if te.any() else Xt)
    Xs = svd.transform(Xt).astype(np.float32)
    del Xt
    gc.collect()
    # la memoire et les voisins, dans l'ordre du temps : chaque vente ne voit que les jours d'AVANT
    mem = Memoire()
    R = np.full((n, len(NOMS_MEM)), np.nan)
    V = np.full((n, len(NOMS_VOIS)), np.nan)
    XV = np.full((n, len(NOMS_XV)), np.nan)
    ij = NOMS_MEM.index("j_m1000")
    lvl = np.zeros(n)
    Xc = Xc.tocsr()
    par_j, par_b = {}, {}
    i = 0
    while i < n:
        j = i
        while j < n and jours[j] == jours[i]:
            j += 1
        d = int(jours[i])
        for r in range(i, j):
            R[r] = mem.lire(bruts[r], d)
            lvl[r] = 0.0 if np.isnan(R[r, ij]) else R[r, ij]
        # les voisins entre joueurs (meme saison, meme sorte), bloc par bloc
        grpb = {}
        for r in range(i, j):
            grpb.setdefault(bloc_xv(bruts[r]), []).append(r)
        for bk, rs in grpb.items():
            av = par_b.get(bk)
            if not av:
                continue
            ix = np.array(av[-XV_MAX:])
            vals = y[ix] - lvl[ix]
            XcT = Xc[ix].T.tocsc()
            for c0 in range(0, len(rs), 400):                # par morceaux : la memoire reste petite
                part = rs[c0:c0 + 400]
                S = (Xc[part] @ XcT).toarray()
                for q, r in enumerate(part):
                    XV[r] = _xv_feats(S[q], vals, R[r, ij])
        # les voisins du jour, joueur par joueur
        grp = {}
        for r in range(i, j):
            if bruts[r].get("joueur"):
                grp.setdefault(bruts[r]["joueur"], []).append(r)
        for jo, rs in grp.items():
            av = par_j.get(jo)
            if not av:
                continue
            ix = np.array(av[-VOIS_MAX:])
            S = (Xc[rs] @ Xc[ix].T).toarray()
            for q, r in enumerate(rs):
                V[r] = _vois_feats(S[q], y[ix], d - jours[ix])
        for r in range(i, j):
            mem.ajouter(bruts[r], d, float(y[r]), float(res[r]))
            if bruts[r].get("joueur"):
                par_j.setdefault(bruts[r]["joueur"], []).append(r)
            par_b.setdefault(bloc_xv(bruts[r]), []).append(r)
        i = j
    log(f"memoire ok ({_mo()} Mo)")
    pres = dl.presence_catalogue()
    Xn = np.array([sm.numeriques(b, pres) for b in bruts], dtype=float)
    if EXTRA:                                                # 11 nov 2026 : equipe, pays, position, age, rythme, criteres de l'Indice
        Xn = np.column_stack([Xn, np.array([sm.numeriques2(b) for b in bruts], dtype=float)])
    import rarete_cat
    Rr = np.array([rarete_cat.rarete(b) for b in bruts], dtype=float)
    X = np.column_stack([oof, Xn, Xs, R, V, XV, Rr])
    vide = ~np.isfinite(X[tr]).any(axis=0)                 # une colonne sans aucune valeur (scikit-learn plante) : 0 partout,
    X[:, vide] = 0.0                                         # l'arbre ne s'en sert jamais (aucune valeur au service n'y change rien)
    # 11 nov 2026 (v3) : les arbres lisent aussi les MOTS du titre (presence de « young guns », « canvas », « high gloss »...)
    from sklearn.feature_extraction.text import CountVectorizer
    del Xc, Xs, R, V, XV, Rr, Xn
    gc.collect()
    moteur = _moteur()
    ntok = {"lgb": NTOK, "lgb_leger": 1500}.get(moteur, 0)
    cvt = CountVectorizer(ngram_range=(1, 2), min_df=30, max_features=max(1, ntok), binary=True,
                          token_pattern=r"(?u)\b[\w/]+\b", dtype=np.float32).fit([t for t, a in zip(T, tr) if a])
    if not ntok:
        cvt.vocabulary_ = {}
    if moteur.startswith("lgb"):
        # par morceaux de 10 000 lignes : jamais de grosse copie temporaire (la memoire du serveur)
        parts = []
        for i0 in range(0, n, 10000):
            bloc = sp.csr_matrix(X[i0:i0 + 10000].astype(np.float32))
            parts.append(sp.hstack([bloc, cvt.transform(T[i0:i0 + 10000])], format="csr") if ntok else bloc)
        del X
        gc.collect()
        M = sp.vstack(parts, format="csr")
        del parts
    else:
        M = X.astype(np.float32)
        del X
    gc.collect()
    log(f"matrice ok ({_mo()} Mo)")
    if moteur.startswith("lgb"):
        import lightgbm as lgb
        leger = moteur == "lgb_leger"
        gb = lgb.LGBMRegressor(n_estimators=int(iters * (2.0 if leger else 2.5)), learning_rate=0.04 if leger else 0.03,
                               num_leaves=127 if leger else 255, max_bin=63 if leger else 255, min_child_samples=20, subsample=0.8,
                               subsample_freq=1, colsample_bytree=0.5, reg_lambda=1.0, random_state=0, verbose=-1, force_col_wise=True,
                               n_jobs=int(os.environ.get("LR_SCORE_FILS", "2"))).fit(M[tr], y[tr])
        arbres = exporter_lgb(gb.booster_)
        pred = gb.predict
    else:
        Md = M
        gb = HistGradientBoostingRegressor(max_iter=iters, learning_rate=0.05, max_leaf_nodes=127, min_samples_leaf=25,
                                           l2_regularization=1.0, random_state=0).fit(Md[tr], y[tr])
        noeuds = [p[0].nodes for p in gb._predictors]
        N = np.concatenate(noeuds)
        arbres = dict(debuts=np.cumsum([0] + [len(x) for x in noeuds]).astype(np.int64), valeur=N["value"],
                      feature=N["feature_idx"].astype(np.int32), seuil=N["num_threshold"], manque_gauche=N["missing_go_to_left"],
                      gauche=N["left"].astype(np.int32), droite=N["right"].astype(np.int32), feuille=N["is_leaf"],
                      base=np.float64(gb._baseline_prediction.ravel()[0]))
        pred = gb.predict
    log(f"arbres ok ({moteur}, {_mo()} Mo)")
    mesure = None
    if te.any():
        mesure = bilan(pred(M[te]), y[te])
        mesure.update(ventes_test=int(te.sum()), ventes_apprentissage=int(tr.sum()), moteur=moteur)
    pred_tr = pred(M[tr])
    modele = dict(idf_mots=vw.idf_.astype(np.float32), idf_car=vc.idf_.astype(np.float32), ridge_w=rid.coef_.astype(np.float32),
                  ridge_b=np.float64(rid.intercept_), svd=svd.components_.astype(np.float32), **arbres,
                  quantiles=np.quantile(pred_tr, np.linspace(0, 1, 1001)), version=np.int32(3), extra=np.int32(1 if EXTRA else 0),
                  xv=np.int32(1), rar=np.int32(1), ntok=np.int32(len(cvt.vocabulary_)))
    vocab = {"mots": {k: int(v) for k, v in vw.vocabulary_.items()}, "car": {k: int(v) for k, v in vc.vocabulary_.items()},
             "tok": {k: int(v) for k, v in cvt.vocabulary_.items()}}
    vois = {jo: [(int(jours[r]), bruts[r]["t"], float(y[r])) for r in rs[-VOIS_MAX:]] for jo, rs in par_j.items()}
    xvois = {bk: [(int(jours[r]), bruts[r]["t"], float(y[r] - lvl[r])) for r in rs[-XV_MAX:]] for bk, rs in par_b.items()}
    return {"modele": modele, "vocab": vocab, "memoire": mem, "vois": vois, "xvois": xvois, "mesure": mesure, "n": n,
            "dernier_jour": int(jours.max()) if n else None, "_X": M, "_gb": gb, "_pred": pred}


def _mo_libres():
    try:
        with open("/proc/meminfo") as fi:
            return next(int(l.split()[1]) for l in fi if l.startswith("MemAvailable")) / 1024
    except (OSError, StopIteration, ValueError):
        return None


def _moteur():
    """« lgb » (complet : 4 000 mots, 255 feuilles) si la memoire libre le permet, « lgb_leger » (1 500 mots, 127 feuilles :
    pour le forfait Render de 2 Go), sinon « hgb » (scikit-learn, sans les mots). LR_SCORE_MOTEUR force un choix."""
    f = os.environ.get("LR_SCORE_MOTEUR")
    if f in ("lgb", "lgb_leger", "hgb"):
        return f
    try:
        import importlib
        importlib.import_module("lightgbm")          # 11 nov 2026 : un vrai import (libgomp peut manquer sur le serveur)
    except Exception:
        return "hgb"
    try:
        with open("/proc/meminfo") as fi:
            libre = next(int(l.split()[1]) for l in fi if l.startswith("MemAvailable")) / 1024
    except (OSError, StopIteration, ValueError):
        libre = 0
    return "lgb" if libre >= float(os.environ.get("LR_SCORE_MO_MIN", "3800")) else "lgb_leger"


def bilan(pred, y, ratio=2.0, tirages=60, n_paires=200000):
    """La precision (paires dont l'une s'est vendue >= 2x plus cher : la part que le score met dans le bon ordre) et la
    confiance (5e centile sur des tirages bootstrap)."""
    rng = np.random.default_rng(1)
    p, y = np.asarray(pred, float), np.asarray(y, float)

    def conc(s, v, k):
        n = len(s)
        i, j = rng.integers(0, n, k), rng.integers(0, n, k)
        d = v[i] - v[j]
        m = np.abs(d) >= math.log(ratio)
        ds = s[i][m] - s[j][m]
        return float(((np.sign(ds) == np.sign(d[m])).sum() + 0.5 * (ds == 0).sum()) / max(1, m.sum()))
    c = conc(p, y, n_paires)
    bs = []
    for _ in range(tirages):
        ix = rng.integers(0, len(p), len(p))
        bs.append(conc(p[ix], y[ix], 40000))
    return {"precision": round(c, 4), "confiance": round(float(np.percentile(bs, 5)), 4), "n": len(p)}


# -- 4. le modele sur le disque (Render : le disque persistant) ------------------------------------------------------------
def dossier():
    import comptes
    return os.path.join(comptes.DONNEES, "score_modele")


def exporter(r, dest=None, meta=None):
    """Ecrit le modele (npz + vocabulaire) et l'etat (memoire, voisins) dans un dossier neuf, puis le met en place d'un coup."""
    dest = dest or dossier()
    tmp = dest + ".neuf"
    os.makedirs(tmp, exist_ok=True)
    np.savez_compressed(os.path.join(tmp, "modele.npz"), **r["modele"])
    with gzip.open(os.path.join(tmp, "vocab.json.gz"), "wt", encoding="utf-8") as f:
        json.dump(r["vocab"], f)
    _ecrire_etat(os.path.join(tmp, "etat.sqlite"), r["memoire"], r["vois"], r["dernier_jour"], r.get("xvois"))
    with open(os.path.join(tmp, "meta.json"), "w") as f:
        json.dump(dict(meta or {}, n=r["n"], mesure=r["mesure"], le=datetime.now().isoformat(timespec="seconds"),
                       dernier_jour=date.fromordinal(r["dernier_jour"]).isoformat() if r["dernier_jour"] else None), f)
    vieux = dest + ".vieux"
    if os.path.exists(vieux):
        import shutil
        shutil.rmtree(vieux, ignore_errors=True)
    if os.path.exists(dest):
        os.replace(dest, vieux)
    os.replace(tmp, dest)
    _CACHE["vois"].clear()
    return dest


def _ecrire_etat(chemin, mem, vois, dernier, xvois=None):
    if os.path.exists(chemin):
        os.remove(chemin)
    c = sqlite3.connect(chemin)
    try:
        c.execute("CREATE TABLE mem (k TEXT PRIMARY KEY, v TEXT)")
        c.execute("CREATE TABLE vois (joueur TEXT, jour INTEGER, t TEXT, y REAL)")
        c.execute("CREATE INDEX vois_j ON vois (joueur, jour)")
        c.execute("CREATE TABLE info (k TEXT PRIMARY KEY, v TEXT)")
        c.execute("CREATE TABLE xvois (bloc TEXT, jour INTEGER, t TEXT, v REAL)")
        c.execute("CREATE INDEX xvois_b ON xvois (bloc, jour)")
        c.executemany("INSERT INTO xvois VALUES (?, ?, ?, ?)", ((bk, d, t, round(v, 5)) for bk, l in (xvois or {}).items() for d, t, v in l))
        c.executemany("INSERT INTO mem VALUES (?, ?)", ((k, json.dumps([round(x, 5) for x in v])) for k, v in mem.d.items()))
        c.executemany("INSERT INTO vois VALUES (?, ?, ?, ?)", ((jo, d, t, round(yv, 5)) for jo, l in vois.items() for d, t, yv in l))
        c.execute("INSERT INTO info VALUES ('dernier_jour', ?)", (str(dernier or 0),))
        c.commit()
    finally:
        c.close()


def _etat_cx():
    ch = os.path.join(dossier(), "etat.sqlite")
    if not os.path.exists(ch):
        return None
    return sqlite3.connect(ch, timeout=10)


def present():
    return os.path.exists(os.path.join(dossier(), "modele.npz"))


def lire_meta():
    try:
        with open(os.path.join(dossier(), "meta.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# -- 5. au serveur : les caracteristiques « marche » d'une liste d'annonces, aujourd'hui ----------------------------------
def caracteristiques(bruts, vec_car, aujourdhui=None, xv=False):
    """bruts -> matrice [memoire (aujourd'hui) | voisins | voisins entre joueurs (xv)]. vec_car(t) -> vecteur creux normalise."""
    jour = (aujourdhui or date.today()).toordinal()
    nm, nv = len(NOMS_MEM), len(NOMS_VOIS)
    out = np.full((len(bruts), nm + nv + (len(NOMS_XV) if xv else 0)), np.nan)
    c = _etat_cx()
    if c is None:
        return out
    try:
        cles = sorted({k for b in bruts for k in Memoire().cles(b)})
        d = {}
        for s0 in range(0, len(cles), 500):
            part = cles[s0:s0 + 500]
            for k, v in c.execute(f"SELECT k, v FROM mem WHERE k IN ({','.join('?' * len(part))})", part):
                d[k] = json.loads(v)
        mem = Memoire(d)
        for i, b in enumerate(bruts):
            out[i, :len(NOMS_MEM)] = mem.lire(b, jour)
        # 11 nov 2026 (vitesse : 300 annonces en 20 s -> moins d'une seconde) : les similarites en matrices creuses, par
        # joueur et par bloc (les candidats sont gardes en matrice pour la journee)
        Q = _csr([vec_car(b["t"]) for b in bruts])
        par_j = {}
        for i, b in enumerate(bruts):
            if b.get("joueur"):
                par_j.setdefault(b["joueur"], []).append(i)
        for jo, ix in par_j.items():
            C = _vois_du(c, jo, jour)
            if C is None:
                continue
            S = (Q[ix] @ C["M"].T).toarray()
            for q, i in enumerate(ix):
                out[i, nm:nm + nv] = _vois_feats(S[q], C["y"], jour - C["d"])
        if xv:
            ij = NOMS_MEM.index("j_m1000")
            par_b = {}
            for i, b in enumerate(bruts):
                par_b.setdefault(bloc_xv(b), []).append(i)
            for bk, ix in par_b.items():
                C = _xv_du(c, bk, jour)
                if C is None:
                    continue
                S = (Q[ix] @ C["M"].T).toarray()
                for q, i in enumerate(ix):
                    out[i, nm + nv:] = _xv_feats(S[q], C["v"], out[i, ij])
    finally:
        c.close()
    return out


def _csr(vecs, n=None):
    """[{j: x}] -> matrice creuse (lignes = vecteurs du modele, deja normalises)."""
    import scipy.sparse as sp
    import score_modele as sm
    m = sm.charger()
    n = n or (len(m["vc"]) if m else 1)
    ri, ci, va = [], [], []
    for r_, v in enumerate(vecs):
        for j, x in v.items():
            ri.append(r_)
            ci.append(j)
            va.append(x)
    return sp.csr_matrix((va, (ri, ci)), shape=(len(vecs), n))


def _cache_jour(jour):
    if _CACHE["vois_jour"] != jour:
        _CACHE["vois"].clear()
        _CACHE["vois_jour"] = jour
    if len(_CACHE["vois"]) > 600:
        _CACHE["vois"].clear()


def _xv_du(c, bk, jour):
    import score_modele as sm
    cle = ("xv", bk)
    _cache_jour(jour)
    if cle not in _CACHE["vois"]:
        try:
            rows = c.execute("SELECT t, v FROM xvois WHERE bloc = ? AND jour < ? ORDER BY jour DESC LIMIT ?", (bk, jour, XV_MAX)).fetchall()
        except sqlite3.OperationalError:
            rows = []
        m = sm.charger()
        _CACHE["vois"][cle] = {"M": _csr([sm.vec_car(t, m) for t, _v in rows]), "v": np.array([v for _t, v in rows])} if (m and rows) else None
    return _CACHE["vois"][cle]


def _vois_du(c, joueur, jour):
    import score_modele as sm
    _cache_jour(jour)
    if joueur not in _CACHE["vois"]:
        rows = c.execute("SELECT jour, t, y FROM vois WHERE joueur = ? AND jour < ? ORDER BY jour DESC LIMIT ?", (joueur, jour, VOIS_MAX)).fetchall()
        rows = list(reversed(rows))
        m = sm.charger()
        _CACHE["vois"][joueur] = {"M": _csr([sm.vec_car(t, m) for _d, t, _y in rows]), "y": np.array([y for _d, _t, y in rows]),
                                  "d": np.array([d for d, _t, _y in rows])} if (m and rows) else None
    return _CACHE["vois"][joueur]


# -- 6. chaque jour : les ventes d'hier entrent dans la memoire -----------------------------------------------------------
def passe_jour(ventes=None, aujourdhui=None):
    """Ajoute a l'etat les ventes des jours entre le dernier jour connu et hier (base_ventes du serveur). Un seul processus
    a la fois (plusieurs travailleurs gunicorn) : verrou de fichier."""
    if not present():
        return {"ok": False, "raison": "pas de modele reappris"}
    import fcntl
    with open(os.path.join(dossier(), "jour.verrou"), "w") as fv:
        try:
            fcntl.flock(fv, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return {"ok": True, "ajoutees": 0, "occupe": True}
        try:
            return _passe_jour(ventes, aujourdhui)
        finally:
            fcntl.flock(fv, fcntl.LOCK_UN)


def _passe_jour(ventes=None, aujourdhui=None):
    import score_modele as sm
    if not present():
        return {"ok": False, "raison": "pas de modele reappris"}
    c = _etat_cx()
    try:
        dern = int((c.execute("SELECT v FROM info WHERE k='dernier_jour'").fetchone() or ["0"])[0])
    finally:
        c.close()
    auj = (aujourdhui or date.today()).toordinal()
    if dern >= auj - 1:
        return {"ok": True, "ajoutees": 0}
    if ventes is None:
        ventes = _ventes_base(date.fromordinal(dern + 1).isoformat(), date.fromordinal(auj).isoformat())
    bruts, y, jours = preparer(ventes)
    m = sm.charger()
    if not m or not len(bruts):
        _info(dern_max=auj - 1)
        return {"ok": True, "ajoutees": 0}
    texte = sm.texte_pred(bruts, m)
    res = y - texte
    c = _etat_cx()
    try:
        cles = sorted({k for b in bruts for k in Memoire().cles(b)})
        d = {}
        for s0 in range(0, len(cles), 500):
            part = cles[s0:s0 + 500]
            for k, v in c.execute(f"SELECT k, v FROM mem WHERE k IN ({','.join('?' * len(part))})", part):
                d[k] = json.loads(v)
        mem = Memoire(d)
        ij = NOMS_MEM.index("j_m1000")
        xv_l = []
        for b, yy, jj in zip(bruts, y, jours):                   # le niveau du joueur AVANT ses ventes du jour (comme a l'apprentissage)
            lv = mem.lire(b, int(jj))[ij]
            xv_l.append((bloc_xv(b), int(jj), b["t"], round(float(yy) - (0.0 if np.isnan(lv) else lv), 5)))
        for b, yy, rr, jj in zip(bruts, y, res, jours):
            mem.ajouter(b, int(jj), float(yy), float(rr))
        c.executemany("INSERT OR REPLACE INTO mem VALUES (?, ?)", ((k, json.dumps([round(x, 5) for x in v])) for k, v in mem.d.items()))
        c.executemany("INSERT INTO vois VALUES (?, ?, ?, ?)", ((b["joueur"], int(jj), b["t"], round(float(yy), 5))
                                                              for b, yy, jj in zip(bruts, y, jours) if b.get("joueur")))
        try:
            c.executemany("INSERT INTO xvois VALUES (?, ?, ?, ?)", xv_l)
        except sqlite3.OperationalError:
            pass
        c.execute("INSERT OR REPLACE INTO info VALUES ('dernier_jour', ?)", (str(auj - 1),))
        c.commit()
    finally:
        c.close()
    _CACHE["vois"].clear()
    return {"ok": True, "ajoutees": len(bruts)}


def _info(dern_max):
    c = _etat_cx()
    if c is None:
        return
    try:
        c.execute("INSERT OR REPLACE INTO info VALUES ('dernier_jour', ?)", (str(dern_max),))
        c.commit()
    finally:
        c.close()


def _ventes_base(depuis, avant):
    """Les ventes reelles recoltees par le serveur (base_ventes) : [(titre, prix, jour)]. Lecture seule."""
    import comptes
    ch = os.path.join(comptes.DONNEES, "base_ventes.sqlite")
    if not os.path.exists(ch):
        return []
    c = sqlite3.connect(ch, timeout=10)
    try:
        rows = c.execute("SELECT titre, prix, substr(le, 1, 10) FROM ventes WHERE le >= ? AND le < ? AND prix > 0", (depuis, avant)).fetchall()
    finally:
        c.close()
    vus, out = set(), []
    for t, p, j in rows:
        k = (t, round(p, 2), j)
        if k not in vus:
            vus.add(k)
            out.append(k)
    return out


# -- 7. chaque semaine : le reapprentissage (processus a part), avec garde-fou -------------------------------------------
def _hist_chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "score_reappris.json")


def historique():
    try:
        with open(_hist_chemin()) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"essais": []}


def _hist_ajouter(e):
    h = historique()
    h["essais"] = (h.get("essais") or [])[-51:] + [e]
    tmp = _hist_chemin() + ".tmp"
    with open(tmp, "w") as f:
        json.dump(h, f)
    os.replace(tmp, _hist_chemin())


def reapprendre(ventes=None, aujourdhui=None, log=print, iters=1000):
    """1) apprend sur tout sauf les 10 derniers jours et mesure sur ceux-ci (jamais vus) ; 2) garde-fou : au moins 0,90 et
    pas plus de 0,01 sous la derniere mesure acceptee ; 3) si oui : reapprend sur TOUT et remplace le modele."""
    auj = aujourdhui or date.today()
    libre = _mo_libres()
    if libre is not None and libre < MO_LIBRES_MIN:
        e = {"le": datetime.now().isoformat(timespec="seconds"), "ventes": 0, "accepte": False,
             "raison": f"memoire libre insuffisante ({int(libre)} Mo) : l'ancien modele reste"}
        _hist_ajouter(e)
        return e
    if ventes is None:
        ventes = _ventes_base((auj - timedelta(days=FENETRE_JOURS)).isoformat(), auj.isoformat())
    bruts, y, jours = preparer(ventes)
    if len(bruts) > MAX_VENTES:
        bruts, y, jours = bruts[-MAX_VENTES:], y[-MAX_VENTES:], jours[-MAX_VENTES:]
    e = {"le": datetime.now().isoformat(timespec="seconds"), "ventes": len(bruts)}
    if len(bruts) < 20000:
        e.update(accepte=False, raison="pas assez de ventes (%d)" % len(bruts))
        _hist_ajouter(e)
        return e
    coupe = int(jours.max()) - COUPE_JOURS + 1
    r = entrainer(bruts, y, jours, coupe=coupe, iters=iters, log=log)
    mz = r["mesure"]
    e.update(mesure=mz)
    prec = [x["mesure"]["precision"] for x in historique().get("essais") or [] if x.get("accepte") and x.get("mesure")]
    # 11 nov 2026 : le garde-fou compare sur les MEMES ventes jamais vues : au 1er reapprentissage, le modele du depot (v7)
    # est mesure sur la meme fenetre ; ensuite, la derniere mesure acceptee (moins 0,01 : la fenetre change chaque semaine)
    ref = None
    if not prec:
        try:
            import score_modele as sm
            import demande_legale as dl
            md = sm.modele_depot()
            te = jours >= coupe
            if md:
                p0 = sm.predire([b for b, a in zip(bruts, te) if a], dl.presence_catalogue(), m=md)
                ref = bilan(p0, y[te])["precision"]
                e.update(reference_depot=ref)
        except Exception as ex:
            log("reference : " + repr(ex)[:120])
    seuil = max(0.85, ref - 0.002 if ref is not None else 0.0, (prec[-1] - 0.01) if prec else 0.0)
    if mz["precision"] < seuil:
        e.update(accepte=False, raison=f"precision {mz['precision']} sous le seuil {round(seuil, 4)} : l'ancien modele reste")
        _hist_ajouter(e)
        return e
    del r
    gc.collect()
    r2 = entrainer(bruts, y, jours, coupe=None, iters=iters, log=log)
    exporter(r2, meta={"mesure_garde_fou": mz, "coupe": date.fromordinal(coupe).isoformat()})
    import score_modele as sm
    sm.recharger()
    e.update(accepte=True)
    _hist_ajouter(e)
    return e


def _verrou_fichier():
    import comptes
    return os.path.join(comptes.DONNEES, "score_reappris.verrou")


def taches_si_besoin(maintenant=None):
    """Appele chaque heure par server.py. La passe du jour (rapide, sur place) ; le reapprentissage de la semaine (la nuit,
    dans un processus a part pour ne pas ralentir l'app)."""
    maint = maintenant or datetime.now()
    out = {}
    try:
        if present():
            out["jour"] = passe_jour()
    except Exception as ex:
        out["jour"] = {"ok": False, "erreur": repr(ex)[:200]}
    if os.environ.get("LR_SCORE_REAPPRENDRE", "1") == "0":
        return out
    h = historique().get("essais") or []
    der = h[-1]["le"] if h else None
    du = (maint - datetime.fromisoformat(der)).days if der else 99
    if du >= REAPPRENDRE_J and maint.hour in HEURES_NUIT:
        v = _verrou_fichier()
        try:
            if os.path.exists(v) and time.time() - os.path.getmtime(v) < 6 * 3600:
                return out
            with open(v, "w") as f:
                f.write(str(os.getpid()))
            import subprocess
            subprocess.Popen([sys.executable, os.path.abspath(__file__), "reapprendre"], cwd=os.path.dirname(os.path.abspath(__file__)),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
                             preexec_fn=(lambda: os.nice(10)) if hasattr(os, "nice") else None)
            out["reapprendre"] = "lance"
        except Exception as ex:
            out["reapprendre"] = repr(ex)[:200]
    return out


def statut():
    m = lire_meta() or {}
    h = historique().get("essais") or []
    return {"actif": present(), "le": m.get("le"), "ventes": m.get("n"), "mesure": (m.get("mesure_garde_fou") or m.get("mesure")),
            "dernier_jour": m.get("dernier_jour"), "essais": h[-6:]}




# -- 8. LightGBM -> les memes tableaux que les arbres de scikit-learn (le serveur n'a besoin que de numpy) -----------------
def exporter_lgb(booster):
    """booster LightGBM -> {debuts, valeur, feature, seuil, manque_gauche, type_manque, gauche, droite, feuille, base}."""
    TYPES = {"None": 0, "Zero": 1, "NaN": 2}
    deb, val, fea, seu, mg, tm, ga, dr, fe = [0], [], [], [], [], [], [], [], []
    for t in booster.dump_model()["tree_info"]:
        noeuds = []

        def visiter(nd):
            k = len(noeuds)
            noeuds.append(None)
            if "leaf_value" in nd and "split_feature" not in nd:
                noeuds[k] = (float(nd["leaf_value"]), 0, 0.0, 0, 0, -1, -1, 1)
                return k
            g = visiter(nd["left_child"])
            d = visiter(nd["right_child"])
            noeuds[k] = (0.0, int(nd["split_feature"]), float(nd["threshold"]), int(bool(nd.get("default_left"))),
                         TYPES.get(nd.get("missing_type"), 0), g, d, 0)
            return k
        visiter(t["tree_structure"])
        for v_, f_, s_, m_, t_, g_, d_, l_ in noeuds:
            val.append(v_); fea.append(f_); seu.append(s_); mg.append(m_); tm.append(t_); ga.append(g_); dr.append(d_); fe.append(l_)
        deb.append(deb[-1] + len(noeuds))
    return dict(debuts=np.array(deb, np.int64), valeur=np.array(val), feature=np.array(fea, np.int32), seuil=np.array(seu),
                manque_gauche=np.array(mg, np.uint8), type_manque=np.array(tm, np.int8), gauche=np.array(ga, np.int32),
                droite=np.array(dr, np.int32), feuille=np.array(fe, np.uint8), base=np.float64(0.0))


# -- 9. le processus de la nuit (lance par taches_si_besoin) : EN DERNIER, apres toutes les definitions -------------------
if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "reapprendre":
    try:
        print(json.dumps(reapprendre(log=lambda s: print(s, flush=True))), flush=True)
    except Exception as ex:                  # 11 nov 2026 : une panne de la nuit est notee (Admin > Validation), jamais muette
        import traceback
        traceback.print_exc()
        try:
            _hist_ajouter({"le": datetime.now().isoformat(timespec="seconds"), "ventes": 0, "accepte": False,
                           "raison": "erreur : " + repr(ex)[:200]})
        except Exception:
            pass
    finally:
        try:
            os.remove(_verrou_fichier())
        except OSError:
            pass
