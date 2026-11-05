"""
SLABCOACH - les indices de prix (5 nov 2026, Mathieu : « comment Card Ladder calcule le trending ; ameliorer notre algo »).

Card Ladder : la moyenne des DERNIERS prix vendus des cartes d'un joueur (une vente chere fait bouger tout l'indice). Ici,
une methode de ventes repetees (repeat sales : Bailey-Muth-Nourse, Case-Shiller), ce qu'on fait de plus solide avec des
ventes eBay :
  1. Chaque carte exacte (meme set, parallele, numero ; raw et gradees separees) n'est comparee qu'a ELLE-MEME : sa mediane
     de la semaine, d'une semaine ou elle s'est vendue a la suivante (au plus 13 semaines d'ecart).
  2. Chaque paire donne un rendement logarithmique, borne a x3 / div. 3 (une vente folle ne fait pas l'indice).
     Poids : racine du nombre de ventes (la plus petite des deux semaines), divise par l'ecart (Case-Shiller : plus
     l'ecart est long, plus le bruit est grand). Version « valeur » : aussi le prix de la carte (ce que fait l'argent).
  3. L'indice de chaque semaine est la solution des moindres carres de toutes les paires, avec un lissage (penalite sur
     la courbure : pas de dents de scie, mais une hausse reguliere n'est pas freinee). Base 1 000.
  4. Variations sur 4, 13 et 52 semaines quand l'historique le permet ; chaque indice dit son nombre de paires.
La valeur d'une carte sans vente recente (ajuster) : sa valeur x l'evolution de l'indice du joueur depuis ses ventes
(comme la CL Value), seulement si l'indice couvre les deux dates, borne a /2 et x2.
"""
import json
import math
import os
import statistics
import threading
from datetime import datetime, timedelta

BASE = 1000.0
LISSAGE = 0.6               # penalite sur la courbure (les dents de scie)
K_PRIOR = 1.0               # retrecissement : une semaine avec ~1 paire est ramenee a moitie vers le prior
R_MAX = math.log(3)
ECART_MAX = 13              # semaines entre deux ventes d'une meme carte
PRIX_MIN = 5.0
PAIRES_MIN = 6              # un indice de joueur : au moins 6 paires
PAIRES_MIN_SEG = 20         # un segment du hobby
RECENT_J = 14               # une valeur de moins de 14 jours n'est pas ajustee
COUVERTURE_J = 60           # l'indice doit avoir des donnees a 60 jours de la vente et d'aujourd'hui
METHODE = "rs-v1"
_verrou = threading.Lock()
_MEM = {"mtime": None, "v": None}


def _date(s):
    try:
        return datetime.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        return None


def _lundi(d):
    d = datetime(d.year, d.month, d.day)
    return d - timedelta(days=d.weekday())


def _hebdo(points):
    """[[date, prix]] -> {lundi: (mediane, n)} (prix > 0)."""
    sem = {}
    for d, p in points or []:
        dd = _date(d)
        try:
            p = float(p)
        except (TypeError, ValueError):
            continue
        if not dd or p <= 0:
            continue
        sem.setdefault(_lundi(dd), []).append(p)
    return {w: (statistics.median(l), len(l)) for w, l in sem.items()}


def paires(points, poids_valeur=False):
    """Les paires d'une carte : (semaine a, semaine b, rendement log, poids)."""
    h = _hebdo(points)
    if len(h) < 2:
        return []
    ws = sorted(h)
    med = statistics.median(m for m, _n in h.values())
    if med < PRIX_MIN:
        return []
    out = []
    for a, b in zip(ws, ws[1:]):
        ecart = (b - a).days // 7
        if ecart < 1 or ecart > ECART_MAX:
            continue
        r = max(-R_MAX, min(R_MAX, math.log(h[b][0] / h[a][0])))
        w = math.sqrt(min(h[a][1], h[b][1])) / (1 + 0.15 * (ecart - 1))
        if poids_valeur:
            w *= med
        out.append((a, b, r, w))
    return out


def resoudre(pr, prior=None):
    """Les paires -> [(lundi, valeur)] (base 1 000 a la premiere semaine), ou None.
    prior : {lundi: valeur} d'un indice plus large (le sport, le hobby). Peu de ventes -> les variations de la semaine
    sont ramenees vers celles du prior (sans prior : vers 0, « pas de changement »). Retrecissement bayesien (comme
    tendance_stats) : un joueur avec 9 paires d'une seule carte ne fait pas +150 %."""
    if not pr:
        return None
    import numpy as np
    w0, w1 = min(p[0] for p in pr), max(p[1] for p in pr)
    n = (w1 - w0).days // 7 + 1
    if n < 2:
        return None
    if any(p[3] > 0 for p in pr) and max(p[3] for p in pr) > 0:
        k = 1.0 / max(p[3] for p in pr)                    # poids ramenes a 1 au plus (la version « valeur » : des dollars)
    else:
        return None
    M = np.zeros((n, n))
    v = np.zeros(n)
    for a, b, r, w in pr:
        i, j, w = (a - w0).days // 7, (b - w0).days // 7, w * k
        M[j, j] += w; M[i, i] += w; M[i, j] -= w; M[j, i] -= w
        v[j] += w * r; v[i] -= w * r
    tot = sum(p[3] * k for p in pr)
    lam = LISSAGE * tot / max(1, len(pr))                  # le lissage a l'echelle des poids
    # le lissage porte sur la COURBURE (2e difference) : une hausse reguliere n'est pas freinee ; une semaine sans
    # vente est interpolee entre ses voisines. Un tout petit lissage des sauts garde le systeme stable.
    for t in range(1, n - 1):
        for x, cx in ((t - 1, 1.0), (t, -2.0), (t + 1, 1.0)):
            for y, cy in ((t - 1, 1.0), (t, -2.0), (t + 1, 1.0)):
                M[x, y] += lam * cx * cy
    kap = K_PRIOR * tot / max(1, len(pr))
    lp = {}
    for w_, val in (prior or {}).items():
        if val and val > 0:
            lp[w_] = math.log(val)
    for t in range(1, n):
        wa, wb = w0 + timedelta(days=7 * (t - 1)), w0 + timedelta(days=7 * t)
        d = (lp[wb] - lp[wa]) if wa in lp and wb in lp else 0.0
        M[t, t] += kap; M[t - 1, t - 1] += kap; M[t, t - 1] -= kap; M[t - 1, t] -= kap
        v[t] += kap * d; v[t - 1] -= kap * d
    M[0, 0] += 1e6                                         # la 1re semaine : 0 (base)
    try:
        beta = np.linalg.solve(M, v)
    except np.linalg.LinAlgError:
        return None
    beta = beta - beta[0]
    return [(w0 + timedelta(days=7 * t), round(BASE * math.exp(float(beta[t])), 1)) for t in range(n)]


def _var(points, semaines):
    if len(points) <= semaines:
        return None
    a, b = points[-1 - semaines][1], points[-1][1]
    return round(100 * (b / a - 1), 1) if a else None


def indice(cartes, poids_valeur=False, paires_min=PAIRES_MIN, prior=None):
    """cartes : [{points: [[date, prix]]}] -> {points, v4, v13, v52, n_paires, n_cartes, debut, fin, confiance} ou None."""
    pr, nc = [], 0
    for c in cartes or []:
        p = paires(c.get("points"), poids_valeur)
        if p:
            nc += 1
            pr += p
    if len(pr) < paires_min:
        return None
    s = resoudre(pr, prior)
    if not s or len(s) < 2:
        return None
    pts = [[w.strftime("%Y-%m-%d"), v] for w, v in s]
    conf = "elevee" if len(pr) >= 60 and nc >= 5 else "moyenne" if len(pr) >= 20 and nc >= 3 else "faible"
    return {"points": pts, "v4": _var(pts, 4), "v13": _var(pts, 13), "v52": _var(pts, 52), "n_paires": len(pr), "n_cartes": nc,
            "debut": pts[0][0], "fin": pts[-1][0], "confiance": conf, "methode": METHODE}


def _epoque(c):
    a = c.get("annee")
    try:
        a = int(str(a)[:4]) if a else None
    except ValueError:
        a = None
    if c.get("recrue"):
        return "recrues"
    if not a:
        return None
    return "vintage" if a < 1980 else "annees80" if a < 1990 else "annees90" if a < 2000 else "annees2000" if a < 2015 else "moderne"


def _gamme(c):
    prix = [float(p) for _d, p in (c.get("points") or []) if p]
    if not prix:
        return None
    m = statistics.median(prix)
    return "moins50" if m < 50 else "50a500" if m < 500 else "plus500"


SEGMENTS = {"recrues": ("Recrues", "Rookies"), "vintage": ("Vintage (avant 1980)", "Vintage (pre-1980)"), "annees80": ("Années 80", "80s"),
            "annees90": ("Années 90", "90s"), "annees2000": ("2000 à 2014", "2000 to 2014"), "moderne": ("Moderne (2015+)", "Modern (2015+)"),
            "moins50": ("Cartes de moins de 50 $", "Cards under $50"), "50a500": ("Cartes de 50 à 500 $", "Cards $50 to $500"),
            "plus500": ("Cartes de plus de 500 $", "Cards over $500")}


def calculer(cartes):
    """Toutes les cartes mesurees -> {hobby: {egal, valeur}, segments: [...], joueurs: {nom minuscule: indice}}."""
    cartes = [c for c in cartes or [] if c.get("points")]
    out = {"le": datetime.now().isoformat(timespec="seconds"), "methode": METHODE,
           "hobby": {"egal": indice(cartes, False, PAIRES_MIN_SEG), "valeur": indice(cartes, True, PAIRES_MIN_SEG)}, "segments": [], "joueurs": {}}
    grp = {}
    for c in cartes:
        for k in ("sport:" + str(c.get("sport") or "hockey"), _epoque(c), _gamme(c)):
            if k:
                grp.setdefault(k, []).append(c)
    for k, l in grp.items():
        i = indice(l, False, PAIRES_MIN_SEG)
        if i:
            fr, en = SEGMENTS.get(k, (None, None))
            out["segments"].append({"cle": k, "fr": fr, "en": en, **{x: i[x] for x in ("v4", "v13", "v52", "n_paires", "n_cartes", "fin")},
                                    "points": i["points"][-26:]})
    # le prior d'un joueur : l'indice de son sport (sinon le hobby)
    def _pr(i):
        return {datetime.fromisoformat(p[0]): p[1] for p in (i or {}).get("points") or []} if i else None
    pri_sport = {k[6:]: _pr(indice(l, False, PAIRES_MIN_SEG)) for k, l in grp.items() if k.startswith("sport:")}
    pri_hobby = _pr(out["hobby"]["egal"])
    pj = {}
    for c in cartes:
        j = str(c.get("joueur") or "").strip()
        if j and "/" not in j:
            pj.setdefault(j.lower(), []).append(c)
    for j, l in pj.items():
        sps = [str(c.get("sport") or "hockey") for c in l]
        sp = max(set(sps), key=sps.count)
        i = indice(l, prior=pri_sport.get(sp) or pri_hobby)
        if i:
            out["joueurs"][j] = i
    return out


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "indices.json")


def garder(res):
    ch = _chemin()
    with _verrou:
        tmp = ch + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False)
        os.replace(tmp, ch)
        _MEM.update(mtime=None, v=None)


def lire():
    ch = _chemin()
    try:
        mt = os.path.getmtime(ch)
    except OSError:
        return None
    if _MEM["v"] is not None and _MEM["mtime"] == mt:
        return _MEM["v"]
    try:
        with open(ch, encoding="utf-8") as f:
            v = json.load(f)
    except (OSError, ValueError):
        return None
    _MEM.update(mtime=mt, v=v)
    return v


def joueur(nom, meme_faible=False):
    """L'indice d'un joueur (None si sa confiance est faible : on ne montre pas une courbe faite de 2 cartes)."""
    d = lire() or {}
    i = (d.get("joueurs") or {}).get(str(nom or "").strip().lower())
    return i if i and (meme_faible or i.get("confiance") != "faible") else None


def _au(points, d):
    """La valeur de l'indice la semaine de d (None si hors de la serie)."""
    w = _lundi(d).strftime("%Y-%m-%d")
    for p in points:
        if p[0] == w:
            return p[1]
    return None


def ajuster(valeur, date_ventes, joueur_=None, sport=None, auj=None):
    """La valeur d'une carte dont les ventes datent : x (indice aujourd'hui / indice a la date des ventes).
    -> (valeur, info) ; info None si pas d'ajustement (ventes recentes, pas d'indice qui couvre les deux dates)."""
    auj = auj or datetime.now()
    d = _date(date_ventes)
    if not valeur or not d or (auj - d).days <= RECENT_J:
        return valeur, None
    data = lire() or {}
    choix = []
    if joueur_:
        choix.append(("joueur", (data.get("joueurs") or {}).get(str(joueur_).strip().lower())))
    if sport:
        choix.append(("sport", next((s for s in data.get("segments") or [] if s.get("cle") == "sport:" + str(sport)), None)))
    choix.append(("hobby", (data.get("hobby") or {}).get("egal")))
    for src, i in choix:
        # un joueur a l'indice trop mince (moins de 20 paires ou de 3 cartes) : celui de son sport, puis du hobby
        if not i or not i.get("points") or (src == "joueur" and i.get("confiance") == "faible"):
            continue
        pts = i["points"]
        fin = _date(pts[-1][0])
        if not fin or (auj - fin).days > COUVERTURE_J:
            continue
        a = _au(pts, d)
        if a is None:
            continue
        f = max(0.5, min(2.0, pts[-1][1] / a))
        if abs(f - 1) < 0.01:
            return valeur, None
        return round(float(valeur) * f, 2), {"facteur": round(f, 3), "pct": round(100 * (f - 1), 1), "depuis": d.strftime("%Y-%m-%d"), "source": src}
    return valeur, None
