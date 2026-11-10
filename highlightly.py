"""
SLABCOACH - stats des joueurs par Highlightly (10 nov 2026).

Mathieu : « si on sait toutes les stats des joueurs (AHL, G-League, majeures), on peut prevoir les cartes qui vont monter » ;
BALLDONTLIE trop cher (≈ 160 $/mois pour 4 ligues). Highlightly : usage commercial permis (conditions §6.1 : nos apps,
affichees a nos utilisateurs), LNH + NBA + MLB + NFL (+ NCAA), 170+ ligues de hockey (AHL, OHL).

Securite (Mathieu : « assure-toi que c'est securitaire ») :
  - la cle HIGHLIGHTLY_CLE reste dans Render : envoyee seulement dans l'en-tete x-rapidapi-key, en HTTPS (certificat
    verifie), jamais dans une adresse, un journal, une reponse ou l'ecran (4 derniers caracteres au plus) ;
  - seuls les hotes *.highlightly.net sont appeles ; une redirection ailleurs est refusee (la cle ne part jamais ailleurs) ;
  - on n'envoie RIEN de nos utilisateurs : seulement des noms de joueurs publics et des numeros de joueurs ;
  - reponses : 3 Mo au plus, 15 s au plus, JSON seulement, chaque champ verifie (type, longueur) ; les logos et images sont
    jetes (droits non garantis par Highlightly, §6.3-6.4) ; jamais de cotes ni de paris (§7) ;
  - plafond par jour a nous (LR_HIGHLIGHTLY_JOUR, 90 par defaut = forfait gratuit 100) + le compteur d'Highlightly
    (x-ratelimit-requests-remaining) : on s'arrete avant zero ; une panne met l'adaptateur en pause 30 min ;
  - cache : la liste des joueurs 7 jours, les stats 20 h (on ne recopie jamais leur base en entier, §6.2).
Inactif sans cle : rien ne change.
"""
import json
import os
import re
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

SPORTS = {"hockey": "nhl", "basket": "nba", "baseball": "mlb", "football": "nfl"}
HOTE_OK = re.compile(r"^https://([a-z0-9-]+\.)?highlightly\.net(/|$)")
MAX_OCTETS = 3 * 1024 * 1024
DELAI_S = 15
CACHE_JOUEURS_S = 7 * 86400
CACHE_STATS_S = 20 * 3600
_verrou = threading.Lock()
_PANNE = [0.0, 0]
_ETAT = {"base": {}, "restant": None, "limite": None, "erreur": None, "test": None}


def _cle():
    return (os.environ.get("HIGHLIGHTLY_CLE") or "").strip()


def actif():
    return bool(_cle())


def _masque(s):
    s = str(s or "")
    return ("…" + s[-4:]) if len(s) > 4 else "…"


def _sans_cle(texte):
    """Retire la cle de tout texte (message d'erreur, journal), au cas ou."""
    t = str(texte or "")
    k = _cle()
    return t.replace(k, "[cle]") if k else t


def plafond_jour():
    try:
        return max(0, int(os.environ.get("LR_HIGHLIGHTLY_JOUR") or 90))
    except ValueError:
        return 90


def _dossier():
    try:
        import comptes
        return comptes.DONNEES
    except Exception:
        return os.environ.get("LOCKERROOM_DONNEES") or os.path.dirname(os.path.abspath(__file__))


def _chemin(nom):
    return os.path.join(_dossier(), nom)


def _lire(nom, defaut):
    try:
        with open(_chemin(nom), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def _ecrire(nom, d):
    p = _chemin(nom)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, p)


def _jour():
    return datetime.utcnow().strftime("%Y-%m-%d")


def utilisees():
    u = _lire("highlightly_usage.json", {})
    return int(u.get(_jour()) or 0)


def _compter():
    with _verrou:
        u = _lire("highlightly_usage.json", {})
        j = _jour()
        u = {j: int(u.get(j) or 0) + 1}
        _ecrire("highlightly_usage.json", u)


class _PasDeRedirection(urllib.request.HTTPRedirectHandler):
    """Une redirection pourrait emporter la cle ailleurs : refusee."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirection refusee", headers, fp)


_OUVREUR = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl.create_default_context()), _PasDeRedirection())


def _appel(chemin, params=None, sport="hockey"):
    """GET sur Highlightly ; (json, None) ou (None, erreur en mots simples). Jamais la cle dans l'erreur."""
    if not actif():
        return None, "HIGHLIGHTLY_CLE absente"
    if time.time() < _PANNE[0]:
        return None, "en pause (panne recente)"
    if utilisees() >= plafond_jour():
        return None, "plafond du jour"
    if _ETAT["restant"] is not None and _ETAT["restant"] <= 3:
        return None, "quota Highlightly presque epuise"
    lig = SPORTS.get(sport, sport)
    if not re.fullmatch(r"[a-z]{2,12}", lig or ""):
        return None, "sport inconnu"
    bases = [_ETAT["base"].get(lig)] if _ETAT["base"].get(lig) else [f"https://sports.highlightly.net/{lig}", f"https://{lig}.highlightly.net"]
    derniere = None
    for base in bases:
        url = base + chemin + ("?" + urllib.parse.urlencode(params) if params else "")
        if not HOTE_OK.match(url):
            return None, "hote refuse"
        req = urllib.request.Request(url, headers={"x-rapidapi-key": _cle(), "Accept": "application/json",
                                                   "User-Agent": "SlabCoach/1.0"})
        _compter()
        try:
            with _OUVREUR.open(req, timeout=DELAI_S) as r:
                if "json" not in (r.headers.get("Content-Type") or ""):
                    derniere = "reponse pas en JSON"
                    continue
                corps = r.read(MAX_OCTETS + 1)
                for h, k in (("x-ratelimit-requests-remaining", "restant"), ("x-ratelimit-requests-limit", "limite")):
                    v = r.headers.get(h)
                    if v and str(v).isdigit():
                        _ETAT[k] = int(v)
            if len(corps) > MAX_OCTETS:
                return None, "reponse trop grosse"
            _ETAT["base"][lig] = base
            _PANNE[:] = [0.0, 0]
            _ETAT["erreur"] = None
            return json.loads(corps.decode("utf-8")), None
        except urllib.error.HTTPError as e:
            derniere = f"HTTP {e.code}"
            if e.code in (401, 403):
                continue                              # l'autre adresse (abonnement « tous les sports » ou une ligue)
            if e.code == 429:
                _PANNE[:] = [time.time() + 3600, _PANNE[1] + 1]
                break
            if e.code >= 500:
                _PANNE[:] = [time.time() + 1800, _PANNE[1] + 1]
                break
            break
        except (urllib.error.URLError, OSError, ValueError) as e:
            derniere = type(e).__name__
            _PANNE[:] = [time.time() + 1800, _PANNE[1] + 1]
            break
    _ETAT["erreur"] = {"le": time.time(), "texte": _sans_cle(derniere)}
    return None, _sans_cle(derniere or "erreur")


# -- nettoyage des reponses : seulement ce qu'on attend, types verifies, sans images -----------------------------
def _txt(v, n=80):
    if not isinstance(v, str):
        return None
    v = re.sub(r"<[^>]*>", "", v).strip()
    return v[:n] or None


def _num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v if v == v and abs(v) < 1e9 else None
    if isinstance(v, str) and re.fullmatch(r"-?\d+(\.\d+)?", v.strip()):
        return float(v)
    return None


def _joueur(x):
    if not isinstance(x, dict):
        return None
    i = _num(x.get("id"))
    n = _txt(x.get("fullName"))
    return {"id": int(i), "nom": n} if i is not None and n else None


def chercher(nom, sport="hockey"):
    """Les joueurs de ce nom : [{id, nom}] (cache 7 jours)."""
    nom = re.sub(r"\s+", " ", str(nom or "")).strip()[:60]
    if not nom:
        return []
    cache = _lire("highlightly_joueurs.json", {})
    k = f"{sport}|{nom.lower()}"
    c = cache.get(k)
    if c and time.time() - c.get("le", 0) < CACHE_JOUEURS_S:
        return c["l"]
    d, err = _appel("/players", {"name": nom, "limit": 20}, sport)
    if err:
        return []
    l = [j for j in (_joueur(x) for x in ((d or {}).get("data") or [])[:20]) if j]
    cache[k] = {"le": time.time(), "l": l}
    if len(cache) > 5000:
        cache = dict(sorted(cache.items(), key=lambda kv: -kv[1].get("le", 0))[:4000])
    _ecrire("highlightly_joueurs.json", cache)
    return l


def _saison(s):
    if not isinstance(s, dict):
        return None
    st = {}
    for e in (s.get("stats") or [])[:200]:
        if isinstance(e, dict):
            n, v = _txt(e.get("name"), 60), _num(e.get("value"))
            if n and v is not None:
                st[n] = v
    eq = [{"nom": _txt(t.get("displayName")) or _txt(t.get("name")), "abrev": _txt(t.get("abbreviation"), 8), "ligue": _txt(t.get("league"), 30)}
          for t in (s.get("teams") or [])[:6] if isinstance(t, dict)]            # sans les logos
    an = _num(s.get("season"))
    return {"saison": int(an) if an else None, "ligue": _txt(s.get("league"), 30), "partie": _txt(s.get("seasonBreakdown"), 12),
            "equipes": eq, "stats": st}


def stats(pid, sport="hockey"):
    """Les stats par saison d'un joueur : {id, nom, saisons: [...]} (cache 20 h)."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    cache = _lire("highlightly_stats.json", {})
    k = f"{sport}|{pid}"
    c = cache.get(k)
    if c and time.time() - c.get("le", 0) < CACHE_STATS_S:
        return c["v"]
    d, err = _appel(f"/players/{pid}/statistics", None, sport)
    if err:
        return None
    if isinstance(d, list):
        d = d[0] if d else {}
    if not isinstance(d, dict):
        return None
    v = {"id": pid, "nom": _txt(d.get("fullName")),
         "saisons": [s for s in (_saison(x) for x in (d.get("perSeason") or [])[:60]) if s]}
    cache[k] = {"le": time.time(), "v": v}
    if len(cache) > 6000:
        cache = dict(sorted(cache.items(), key=lambda kv: -kv[1].get("le", 0))[:5000])
    _ecrire("highlightly_stats.json", cache)
    return v


def stats_joueur(nom, sport="hockey"):
    """Le joueur le plus proche du nom, puis ses stats."""
    l = chercher(nom, sport)
    if not l:
        return None
    cible = re.sub(r"[^a-z ]", "", nom.lower())
    meilleur = next((j for j in l if re.sub(r"[^a-z ]", "", j["nom"].lower()) == cible), l[0])
    return stats(meilleur["id"], sport)


def test(nom="Connor McDavid", sport="hockey"):
    """Essai complet (admin) : la recherche, les stats, les ligues vues, le quota. Aucun secret dans le resultat."""
    t0 = time.time()
    out = {"ok": False, "actif": actif(), "cle": _masque(_cle()) if actif() else None, "sport": sport, "joueur": nom}
    if not actif():
        out["erreur"] = "HIGHLIGHTLY_CLE absente dans Render"
        return out
    # le cache ne doit pas cacher une panne : on relit pour de vrai
    for f, k in (("highlightly_joueurs.json", f"{sport}|{nom.lower()}"),):
        c = _lire(f, {})
        c.pop(k, None)
        _ecrire(f, c)
    l = chercher(nom, sport)
    out["trouves"] = len(l)
    if not l:
        out["erreur"] = (_ETAT.get("erreur") or {}).get("texte") or "aucun joueur trouve"
        return out
    c = _lire("highlightly_stats.json", {})
    c.pop(f"{sport}|{l[0]['id']}", None)
    _ecrire("highlightly_stats.json", c)
    s = stats_joueur(nom, sport)
    out["duree_s"] = round(time.time() - t0, 2)
    out["base"] = _ETAT["base"].get(SPORTS.get(sport, sport))
    out["restant"], out["limite"] = _ETAT["restant"], _ETAT["limite"]
    if not s or not s.get("saisons"):
        out["erreur"] = (_ETAT.get("erreur") or {}).get("texte") or "pas de stats (forfait gratuit : certaines donnees cachees ?)"
        return out
    sa = sorted(s["saisons"], key=lambda x: x.get("saison") or 0)
    out.update(ok=True, saisons=len(sa), ligues=sorted({x["ligue"] for x in sa if x.get("ligue")}),
               premiere=sa[0].get("saison"), derniere=sa[-1].get("saison"),
               noms_stats=sorted({n for x in sa for n in x["stats"]})[:40],
               exemple={k: v for k, v in list(sa[-1]["stats"].items())[:8]})
    _ETAT["test"] = {**out, "le": time.time()}
    _ecrire("highlightly_test.json", _ETAT["test"])
    return out


def statut():
    t = _ETAT.get("test") or _lire("highlightly_test.json", None)
    return {"actif": actif(), "aujourdhui": utilisees(), "plafond": plafond_jour(), "restant": _ETAT["restant"],
            "limite": _ETAT["limite"], "pause": time.time() < _PANNE[0], "derniere_erreur": _ETAT.get("erreur"),
            "test": {k: t.get(k) for k in ("ok", "le", "saisons", "ligues", "erreur", "duree_s")} if isinstance(t, dict) else None}
