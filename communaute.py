"""
SLABCOACH - les signaux de la communaute SlabCoach (11 nov 2026).

Mathieu : « ce que les utilisateurs regardent, suivent, ajoutent a leur watchlist : un signal de demande que personne
d'autre n'a ». Par JOUR et par JOUEUR (des noms publics), on compte :
  - « fiche »   : sa fiche joueur ouverte ;
  - « annonce » : une annonce de ses cartes ouverte ;
  - « watch »   : une de ses cartes ajoutee a une watchlist ;
  - « favori »  : ajoute aux joueurs favoris (Radar) ;
  - « comptes » : le nombre de comptes differents ce jour-la (une empreinte SALEE PAR JOUR, comme activite.py : elle ne se
    relie ni a un autre jour, ni au compte ; le lendemain il ne reste que le nombre).
Rien d'autre : ni compte, ni carte, ni prix. 400 jours gardes (comptes.DONNEES/communaute.json). Ecrit par lots.
Sert a SlabIQ (le critere « communaute ») et au test de prediction (slabiq_test).
"""
import json
import os
import threading
import time
from datetime import date, datetime, timedelta

JOURS = 400
SORTES = ("fiche", "annonce", "watch", "favori")
POIDS = {"fiche": 1.0, "annonce": 1.0, "watch": 3.0, "favori": 4.0}   # suivre une carte dit plus que la regarder
FLUSH_S = 60
_verrou = threading.Lock()
_delta = {}                  # {jour: {joueur: {sorte: n, "vus": set()}}}
_dernier = [0.0]
_MEM = {"mtime": None, "v": None}


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "communaute.json")


def _jour():
    return datetime.now().strftime("%Y-%m-%d")


def _nom(j):
    j = " ".join(str(j or "").split())[:60]
    if len(j) < 4 or len(j.split()) < 2:
        return None
    return " ".join(w[:1].upper() + w[1:] for w in j.lower().split())


def noter(joueur, sorte, compte=None):
    j = _nom(joueur)
    if not j or sorte not in SORTES:
        return
    if compte is None:
        try:
            import comptes
            compte = comptes.courant()
        except Exception:
            compte = None
    jour = _jour()
    with _verrou:
        d = _delta.setdefault(jour, {}).setdefault(j, {"vus": set()})
        d[sorte] = d.get(sorte, 0) + 1
        if compte:
            import activite
            d["vus"].add(activite.empreinte(compte, jour))
        doit = time.time() - _dernier[0] >= FLUSH_S
    if doit:
        try:
            ecrire()
        except Exception as e:
            print("Communaute : " + repr(e), flush=True)


def noter_titre(titre, sorte, compte=None):
    """Le joueur d'un titre d'annonce (cartes_match), puis noter."""
    try:
        import cartes_match
        j = cartes_match.joueur_du_titre(str(titre or "")[:200])
    except Exception:
        j = None
    if j:
        noter(j, sorte, compte)


def lire():
    ch = _chemin()
    try:
        mt = os.path.getmtime(ch)
    except OSError:
        return {"jours": {}}
    if _MEM["v"] is not None and _MEM["mtime"] == mt:
        return _MEM["v"]
    try:
        with open(ch, encoding="utf-8") as f:
            v = json.load(f) or {"jours": {}}
    except (OSError, ValueError):
        v = {"jours": {}}
    _MEM.update(mtime=mt, v=v)
    return v


def ecrire():
    with _verrou:
        delta = {jr: {j: {**{k: v for k, v in x.items() if k != "vus"}, "vus": set(x["vus"])} for j, x in d.items()} for jr, d in _delta.items()}
        _delta.clear()
        _dernier[0] = time.time()
    if not delta:
        return
    p = _chemin()
    try:
        import fcntl
    except ImportError:
        fcntl = None
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + ".verrou", "a") as v:
        if fcntl:
            fcntl.flock(v, fcntl.LOCK_EX)
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f) or {}
        except (OSError, ValueError):
            d = {}
        jours = d.setdefault("jours", {})
        auj = _jour()
        for jr, par_j in delta.items():
            o = jours.setdefault(jr, {})
            for j, x in par_j.items():
                e = o.setdefault(j, {})
                for k in SORTES:
                    if x.get(k):
                        e[k] = int(e.get(k) or 0) + x[k]
                vus = set(e.get("vus") or []) | x["vus"]
                e["comptes"] = max(int(e.get("comptes") or 0), len(vus))
                if jr == auj:
                    e["vus"] = sorted(vus)
                else:
                    e.pop("vus", None)
        for jr in list(jours):
            if jr != auj:
                for e in jours[jr].values():
                    e.pop("vus", None)
        lim = (date.today() - timedelta(days=JOURS)).isoformat()
        for jr in [x for x in jours if x < lim]:
            jours.pop(jr, None)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(tmp, p)
    _MEM.update(mtime=None, v=None)


def score_jour(e):
    """L'interet d'une journee pour un joueur : chaque geste pondere, et les comptes differents (pas un seul curieux)."""
    if not e:
        return 0.0
    gestes = sum(POIDS[k] * int(e.get(k) or 0) for k in SORTES)
    return gestes * (1 + 0.5 * max(0, int(e.get("comptes") or 1) - 1)) ** 0.5


def serie(joueur, jusqua=None, jours=60):
    """[score du jour] des `jours` jours avant `jusqua` (exclu), du plus ancien au plus recent."""
    j = _nom(joueur)
    jj = (lire().get("jours") or {})
    fin = date.fromisoformat(jusqua) if jusqua else date.today() + timedelta(days=1)
    return [score_jour((jj.get((fin - timedelta(days=k)).isoformat()) or {}).get(j)) for k in range(jours, 0, -1)]


def par_joueur(jours=30):
    """{joueur: (score des 7 derniers jours, score des `jours` derniers jours)} pour SlabIQ."""
    jj = lire().get("jours") or {}
    auj = date.today()
    out = {}
    for k in range(jours):
        jr = (auj - timedelta(days=k)).isoformat()
        for j, e in (jj.get(jr) or {}).items():
            s = score_jour(e)
            a = out.setdefault(j, [0.0, 0.0])
            a[1] += s
            if k < 7:
                a[0] += s
    return {j: tuple(v) for j, v in out.items()}
