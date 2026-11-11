"""
SLABCOACH - 2e source de ventes eBay : TheCardAPI (10 nov 2026).

Mathieu (eBay refuse Marketplace Insights) : « on doit avoir le plus de sources possible, une de base et les autres pour
raffiner et sauver ». SoldComps reste la BASE. TheCardAPI (thecardapi.com) sert a :
  - RAFFINER : les ventes des derniers jours qu'une recherche de l'utilisateur n'a pas encore (meme carte, doublons retires) ;
  - SAUVER   : quand SoldComps ne repond pas, une recherche passe par ici (apres CompSniper pour un geste de l'utilisateur) ;
  - ARCHIVER : chaque jour, une moisson des ventes de hockey d'hier va dans nos archives (base_ventes) : a nous pour de bon.

Cle : THECARDAPI_CLE (Render, jamais sur GitHub ni a l'ecran). Forfait gratuit : 5 000 ventes lues par jour ; le plafond
LR_THECARDAPI_JOUR (4 950 par defaut) laisse une petite marge. Prix en $ US -> $ CA (taux de la Banque du Canada).
Inactif sans cle : rien ne change.
"""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

URL_API = "https://thecardapi.com/api/v1/market/sales"
_verrou = threading.Lock()
_CACHE = {}                      # recherche -> (le, ventes) : 6 h, pour ne pas relire les memes lignes
CACHE_S = 6 * 3600
_PANNE = [0.0, 0]                # jusqu'a quand on n'essaie plus, echecs de suite
_ETAT = {"moisson_le": 0.0, "en_cours": False, "derniere": None, "erreur": None}


def _cle():
    return (os.environ.get("THECARDAPI_CLE") or "").strip()


def actif():
    return bool(_cle())


def plafond_jour():
    try:
        return max(0, int(os.environ.get("LR_THECARDAPI_JOUR") or 4950))
    except ValueError:
        return 4950                  # 11 nov 2026 (Mathieu : « maximiser jusqu'a 5 000, c'est gratuit ») : 50 de marge


def _chemin_usage():
    try:
        import comptes
        d = comptes.DONNEES
    except Exception:
        d = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(d, "thecardapi_usage.json")


def _jour():
    return datetime.utcnow().strftime("%Y-%m-%d")           # le forfait compte par jour UTC


def utilisees(usage=None):
    """Lignes (ventes) lues aujourd'hui, en tout ou pour un usage (« tap », « secours », « moisson »)."""
    try:
        with open(_chemin_usage(), encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return 0
    if d.get("jour") != _jour():
        return 0
    return int(d.get(usage or "total") or 0)


def _compter(n, usage):
    with _verrou:
        try:
            with open(_chemin_usage(), encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            d = {}
        if d.get("jour") != _jour():
            d = {"jour": _jour()}
        d["total"] = int(d.get("total") or 0) + n
        d[usage] = int(d.get(usage) or 0) + n
        try:
            with open(_chemin_usage(), "w", encoding="utf-8") as f:
                json.dump(d, f)
        except OSError:
            pass


# la part du jour de chaque usage : les gestes de l'utilisateur d'abord, la moisson prend ce qui reste en fin de journee
# « tap » = le secours d'un geste de l'utilisateur (SoldComps en panne) : il prend ce qui reste ; « raffiner » = les ventes
# en plus d'une recherche qui a deja repondu ; « secours » = les verifications de deals pendant une panne
# 11 nov 2026 (forfait gratuit : 5 000 lignes par jour, pagination par curseur) : SoldComps reste la base des gestes de
# l'utilisateur ; la moisson (qui nourrit SlabIQ) prend jusqu'a 80 % du jour
# 11 nov 2026 (Mathieu : « on enregistre le MAXIMUM de ventes utiles dans notre banque a nous ? ») : la moisson prend
# jusqu'a 93 % du jour (avant 80 %, le reste se perdait chaque jour) ; ~300 lignes restent pour les secours
PARTS = {"tap": 1.0, "raffiner": 0.4, "secours": 0.25, "moisson": 0.93}
_DERNIER = {"curseur": None, "cles": None}


def _budget_ok(usage, limite):
    pl = plafond_jour()
    tot = utilisees()
    if tot + limite > pl:
        return False
    if usage == "tap":
        return True
    return utilisees(usage) + limite <= pl * PARTS.get(usage, 0.3)


def _num(v):
    try:
        return float(str(v).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None


def _url(it):
    u = str(it.get("listing_url") or it.get("url") or "")
    if u.startswith("http"):
        return u
    m = re.match(r"ebay_(\d{9,15})$", str(it.get("id") or ""))
    return "https://www.ebay.com/itm/" + m.group(1) if m else None


def vers_vente(it, taux):
    """Une ligne de TheCardAPI -> une vente au format de vendues (prix en $ CA, port non compris)."""
    prix = _num(it.get("sale_price"))
    if not prix or prix <= 0:
        return None
    dev = str(it.get("currency") or "USD").upper()
    if dev not in ("USD", "CAD"):
        return None
    if str(it.get("platform") or "eBay").lower() != "ebay":     # des ventes eBay seulement (comme partout dans l'app)
        return None
    le = str(it.get("sale_date") or "")[:10]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", le):
        return None
    t = str(it.get("listing_type") or "")
    return {"titre": str(it.get("title") or "")[:200], "prix": round(prix * (taux if dev == "USD" else 1.0), 2), "le": le, "ts": le,
            "photo": it.get("image_url") or it.get("thumbnail") or None, "url": _url(it), "offre": t.lower() == "bestoffer",
            "mises": None, "source": "eBay", "via": "thecardapi"}


def _taux():
    try:
        import vendues
        return vendues._taux_usd_cad()
    except Exception:
        return 1.38


def _appel(params, delai):
    req = urllib.request.Request(URL_API + "?" + urllib.parse.urlencode(params),
                                 headers={"x-market-api-key": _cle(), "Accept": "application/json", "User-Agent": "SlabCoach/1.0"})
    with urllib.request.urlopen(req, timeout=delai) as r:
        return json.loads(r.read().decode("utf-8"))


def _curseur(d):
    """Le curseur de la page suivante, ou None (les noms usuels : next_cursor, cursor, meta / pagination)."""
    if not isinstance(d, dict):
        return None
    for src in (d, d.get("meta") or {}, d.get("pagination") or {}, d.get("links") or {}):
        if isinstance(src, dict):
            for k in ("next_cursor", "nextCursor", "cursor_next", "next"):
                v = src.get(k)
                if v and isinstance(v, (str, int)) and not str(v).startswith("http"):
                    return str(v)
    return None


def rechercher(q, jours=None, limite=50, usage="tap", delai=10, page=None, curseur=None):
    """-> (ventes, erreur). Rien si inactif, en panne ou hors budget (erreur dit pourquoi)."""
    q = " ".join(str(q or "").split())[:120]
    if not q or not actif():
        return [], "inactif"
    cle_c = f"{q.lower()}|{jours}|{limite}|{page}|{curseur}"
    c = _CACHE.get(cle_c)
    if c and time.time() - c[0] < CACHE_S:
        return list(c[1]), None
    if time.time() < _PANNE[0]:
        return [], "TheCardAPI en pause (panne)"
    if not _budget_ok(usage, limite):
        return [], "plafond du jour"
    p = {"q": q, "limit": limite}
    if jours:
        p["date_from"] = (datetime.utcnow() - timedelta(days=jours)).strftime("%Y-%m-%d")
    if curseur:
        p["cursor"] = curseur
    elif page:
        p["page"] = page
    try:
        d = _appel(p, delai)
    except urllib.error.HTTPError as e:
        err = {401: "clé TheCardAPI refusée", 403: "clé TheCardAPI refusée", 429: "quota TheCardAPI atteint"}.get(e.code, f"TheCardAPI HTTP {e.code}")
        return [], _panne(err)
    except Exception as e:
        return [], _panne("TheCardAPI injoignable (" + type(e).__name__ + ")")
    _PANNE[1] = 0
    _DERNIER["curseur"] = _curseur(d)
    _DERNIER["cles"] = sorted(d.keys())[:12] if isinstance(d, dict) else None
    lignes = (d or {}).get("data") or []
    _compter(len(lignes), usage)
    taux = _taux()
    ventes = [v for v in (vers_vente(it, taux) for it in lignes if isinstance(it, dict)) if v]
    if len(_CACHE) > 3000:
        _CACHE.clear()
    _CACHE[cle_c] = (time.time(), ventes)
    return ventes, None


def _panne(err):
    _PANNE[1] += 1
    _PANNE[0] = time.time() + (60, 300, 900, 1800)[min(3, _PANNE[1] - 1)]
    _ETAT["erreur"] = {"erreur": err, "le": time.time()}
    print("TheCardAPI : " + err, flush=True)
    return err


# -- la moisson : les ventes de hockey d'hier, une fois par jour, dans nos archives -------------------------
# 11 nov 2026 : les ventes UTILES d'abord (celles qui font les deals : autos, patchs, numerotees, gradees, Young Guns), puis
# le reste du hockey avec ce qui reste du budget ; une meme vente n'est gardee qu'une fois (base_ventes)
MOTS_MOISSON = ("hockey auto", "hockey patch", "hockey psa", "hockey numbered", "young guns", "hockey")


def moissonner(max_pages=None):
    """Les ventes de hockey des derniers jours (le forfait gratuit voit 3 jours) -> base_ventes. -> nombre gardees."""
    import base_ventes
    n, pages = 0, max_pages or int(os.environ.get("LR_THECARDAPI_PAGES") or 40)
    for mot in MOTS_MOISSON:
        if not _budget_ok("moisson", 100):
            break
        vus, cur = set(), None
        # les recherches ciblees : 8 pages (800 ventes) chacune au plus ; « hockey » (la derniere) prend tout le reste
        for page in range(1, (pages if mot == MOTS_MOISSON[-1] else min(pages, 8)) + 1):
            # la page suivante : par curseur quand l'API en donne un (forfait actuel), sinon par numero de page
            ventes, err = rechercher(mot, jours=2, limite=100, usage="moisson", delai=20, page=None if cur else page, curseur=cur)
            if err or not ventes:
                break
            neuves = [v for v in ventes if v.get("url") not in vus]
            if not neuves:                           # la meme page revient : fin
                break
            vus.update(v.get("url") for v in neuves)
            n += base_ventes.noter("moisson " + mot, neuves)
            cur = _DERNIER.get("curseur")
            if page > 1 and not cur and len(ventes) < 100:
                break
    _ETAT["derniere"] = {"le": time.time(), "gardees": n}
    return n


def moissonner_si_besoin():
    """Appele chaque heure par la boucle du serveur : une moisson apres 20 h UTC (le gros des encans est fini), puis une 2e a
    23 h UTC qui prend ce qui reste du budget du jour (11 nov 2026 : rien ne se perd)."""
    h = datetime.utcnow().hour
    if not actif() or _ETAT["en_cours"] or h < 20 or not _budget_ok("moisson", 100):
        return False
    if time.time() - _ETAT["moisson_le"] < (2.5 * 3600 if h >= 23 else 20 * 3600):
        return False
    _ETAT.update(moisson_le=time.time(), en_cours=True)

    def tache():
        try:
            print("TheCardAPI moisson :", moissonner(), "ventes gardees", flush=True)
        except Exception as e:
            print("TheCardAPI moisson : " + repr(e), flush=True)
        finally:
            _ETAT["en_cours"] = False
    threading.Thread(target=tache, daemon=True, name="thecardapi").start()
    return True


def statut():
    return {"actif": actif(), "aujourdhui": utilisees(), "plafond": plafond_jour(),
            "par_usage": {u: utilisees(u) for u in PARTS}, "pause": time.time() < _PANNE[0],
            "derniere_moisson": _ETAT["derniere"], "derniere_erreur": _ETAT["erreur"], "reponse_champs": _DERNIER["cles"]}
