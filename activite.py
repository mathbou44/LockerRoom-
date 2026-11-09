"""
SLABCOACH - l'activite de l'app, anonyme (9 nov 2026).

Mathieu : « un statsboard pour l'administrateur : toute l'activite, les utilisateurs, les pages les plus utilisees, les
fonctions les moins utilisees, tous les commentaires regroupes par categorie, ce qui est a faire ».

Ce qui est garde (comptes.DONNEES/activite.json), par JOUR, 90 jours :
  - le nombre d'appels de chaque fonction du serveur (les noms des methodes de l'Api, jamais leurs donnees) ;
  - le nombre de visites de chaque ecran (la route : « accueil », « deals », « inventaire »...), envoye par l'app ;
  - le nombre de personnes actives : une empreinte du compte SALEE PAR JOUR (sha256 du jour, du compte et d'un secret du
    serveur), gardee seulement le jour meme pour compter sans double ; le lendemain il ne reste que le nombre. Une
    empreinte d'un jour ne se relie ni a celle d'un autre jour, ni au compte.
Rien d'autre : ni nom, ni courriel, ni carte, ni prix, ni adresse IP.
Les compteurs sont accumules en memoire et ecrits par lots (au plus une fois par minute), fusionnes avec le fichier
(plusieurs processus du serveur peuvent ecrire).
"""
import hashlib
import json
import os
import re
import threading
import time
from datetime import datetime, timedelta

JOURS = 90
_verrou = threading.Lock()
_delta = {}                  # {jour: {"api": {}, "pages": {}, "vus": set()}}
_dernier = [0.0]
FLUSH_S = 60
# les appels techniques (sondes, battements) ne disent rien de l'usage
IGNORES = {"activite_page", "statut", "session", "forfait", "notifs_compte", "ping", "version", "reglages_lire", "majCloche"}
_RE_PAGE = re.compile(r"^[a-z0-9_\-]{1,40}$")


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "activite.json")


def _jour():
    return datetime.now().strftime("%Y-%m-%d")


def _sel():
    return (os.environ.get("LOCKERROOM_CLE") or os.environ.get("LR_SECRET") or "slabcoach-activite")[:64]


def empreinte(compte, jour=None):
    """L'empreinte du jour d'un compte (ne se relie pas d'un jour a l'autre)."""
    return hashlib.sha256(f"{jour or _jour()}|{compte}|{_sel()}".encode()).hexdigest()[:16]


def noter_api(nom, compte=None):
    if not nom or nom in IGNORES or nom.startswith("_") or nom.startswith("admin"):
        return
    _noter("api", nom, compte)


def noter_page(page, compte=None):
    p = str(page or "").strip().lower().split("/")[0].split("?")[0][:40]
    if not _RE_PAGE.match(p) or p == "admin":
        return
    _noter("pages", p, compte)


def _noter(sorte, cle, compte):
    j = _jour()
    with _verrou:
        d = _delta.setdefault(j, {"api": {}, "pages": {}, "vus": set()})
        d[sorte][cle] = d[sorte].get(cle, 0) + 1
        if compte:
            d["vus"].add(empreinte(compte, j))
        doit = time.time() - _dernier[0] >= FLUSH_S
    if doit:
        try:
            ecrire()
        except Exception as e:
            print("Activite : " + repr(e), flush=True)


def lire():
    try:
        with open(_chemin(), encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def ecrire():
    """Fusionne les compteurs en memoire dans le fichier ; les empreintes des jours passes sont remplacees par un nombre."""
    with _verrou:
        delta = {j: {"api": dict(v["api"]), "pages": dict(v["pages"]), "vus": set(v["vus"])} for j, v in _delta.items()}
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
        d = lire()
        jours = d.setdefault("jours", {})
        auj = _jour()
        for j, x in delta.items():
            o = jours.setdefault(j, {"api": {}, "pages": {}, "actifs": 0})
            for s in ("api", "pages"):
                for k, n in x[s].items():
                    o[s][k] = int(o[s].get(k) or 0) + n
            vus = set(o.get("vus") or []) | x["vus"]
            o["actifs"] = max(int(o.get("actifs") or 0), len(vus))
            if j == auj:
                o["vus"] = sorted(vus)
            else:
                o.pop("vus", None)
        for j in list(jours):
            if j != auj:
                jours[j].pop("vus", None)
            if j < (datetime.now() - timedelta(days=JOURS)).strftime("%Y-%m-%d"):
                del jours[j]
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(tmp, p)


def resume(jours=30, fonctions=None):
    """Pour la console Admin : actifs par jour, ecrans et fonctions les plus / les moins utilises sur la periode.
    fonctions : la liste de toutes les fonctions de l'Api (celles jamais appelees comptent pour « les moins utilisees »)."""
    try:
        ecrire()
    except Exception:
        pass
    d = (lire().get("jours") or {})
    lim = (datetime.now() - timedelta(days=jours - 1)).strftime("%Y-%m-%d")
    sel = {j: v for j, v in d.items() if j >= lim}
    api, pages = {}, {}
    for v in sel.values():
        for k, n in (v.get("api") or {}).items():
            api[k] = api.get(k, 0) + n
        for k, n in (v.get("pages") or {}).items():
            pages[k] = pages.get(k, 0) + n
    serie = []
    for i in range(jours - 1, -1, -1):
        j = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        v = sel.get(j) or {}
        serie.append({"jour": j, "actifs": int(v.get("actifs") or 0), "appels": sum((v.get("api") or {}).values())})
    tri = sorted(api.items(), key=lambda kv: -kv[1])
    jamais = sorted(f for f in (fonctions or []) if f not in api and f not in IGNORES and not f.startswith("admin"))
    moins = sorted(api.items(), key=lambda kv: kv[1])[:15]
    a7 = [s_["actifs"] for s_ in serie[-7:]]
    return {"jours": jours, "serie": serie, "actifs_auj": serie[-1]["actifs"] if serie else 0,
            "actifs_7j_moy": round(sum(a7) / len(a7), 1) if a7 else 0,
            "pages": sorted(pages.items(), key=lambda kv: -kv[1])[:20], "fonctions_top": tri[:20], "fonctions_moins": moins,
            "jamais": jamais[:60], "appels": sum(api.values())}
