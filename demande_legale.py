"""
SLABCOACH - la demande d'un joueur SANS ventes eBay (10 nov 2026).

Mathieu : « pour la classification des joueurs dans le break, comment on fait ? les points dans la LNH ? Teste des
alternatives pour te rapprocher au max des stats last sold, itere jusqu'a etre egal ou plus precis ».

Pour le public (lancement 100 % legal), la demande d'un joueur (meme echelle que valeurs.demande : 1,0 = moyen) se
calcule seulement avec des donnees publiques du sport, jamais avec des ventes ni des annonces eBay :
  - LNH (api-web.nhle.com) : points de la saison et en carriere, matchs, age, rang au repechage, position, actif ;
  - Wikipedia (API Wikimedia, donnees libres) : les visites de sa page sur 90 jours (la popularite), et sur 30 jours
    contre les 60 d'avant (la tendance).
Le LABO (admin) mesure chaque piece et leur combinaison contre la demande mesuree sur les ventes (valeurs.demande,
admin seulement) : correlation de rang (Spearman), validation croisee, les 20 premiers en commun. La formule gardee est
la plus proche ; chaque joueur est ensuite classe avec SES donnees publiques seulement.
"""
import json
import math
import os
import re
import threading
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

UA = "SlabCoach/1.0 (+https://www.slabcoach.com; support@slabcoach.com)"
FRAICHEUR_J = 7                  # les donnees d'un joueur sont relues chaque semaine
PAR_PASSE = 120                  # joueurs lus par passe (une passe par heure au plus)
_verrou = threading.Lock()
_ETAT = {"d": None, "mtime": None, "en_cours": False, "le": 0.0}


def _chemin():
    try:
        import comptes
        d = comptes.DONNEES
    except Exception:
        d = None
    return os.path.join(d or os.environ.get("LOCKERROOM_DONNEES") or os.path.dirname(os.path.abspath(__file__)), "demande_legale.json")


def _norm(n):
    n = unicodedata.normalize("NFKD", str(n or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]+", " ", n).strip()


def lire():
    ch = _chemin()
    try:
        mt = os.path.getmtime(ch)
    except OSError:
        return {"joueurs": {}, "modele": None, "labo": None}
    if _ETAT["mtime"] != mt:
        try:
            with open(ch, encoding="utf-8") as f:
                _ETAT.update(d=json.load(f), mtime=mt)
        except (OSError, ValueError):
            pass
    return _ETAT["d"] or {"joueurs": {}, "modele": None, "labo": None}


def _ecrire(d):
    ch = _chemin()
    tmp = ch + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, ch)


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"null")
    except Exception:
        return None


# -- les donnees publiques d'un joueur ------------------------------------------------------------------------
def _wiki(nom):
    """Visites de sa page Wikipedia (anglais) : 90 jours et la tendance. La page doit parler de hockey (homonymes)."""
    base = nom.strip().replace(" ", "_")
    for t in (base + "_(ice_hockey)", base):
        s = _get("https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(t, safe=""))
        if not isinstance(s, dict) or s.get("type") == "disambiguation":
            continue
        desc = (str(s.get("description") or "") + " " + str(s.get("extract") or "")[:400]).lower()
        if "hockey" not in desc:
            continue
        titre = (s.get("titles") or {}).get("canonical") or t
        fin = date.today() - timedelta(days=1)
        debut = fin - timedelta(days=89)
        d = _get(f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/"
                 f"{urllib.parse.quote(titre, safe='')}/daily/{debut:%Y%m%d}/{fin:%Y%m%d}")
        v = [int(x.get("views") or 0) for x in ((d or {}).get("items") or [])]
        if not v:
            return {"titre": titre, "v90": 0, "v30": 0}
        return {"titre": titre, "v90": sum(v), "v30": sum(v[-30:])}
    return None


def _nhl(nom):
    import nhl
    pid = nhl._id(nom)
    if not pid:
        l = _get("https://search.d3.nhle.com/api/v1/search/player?" + urllib.parse.urlencode({"culture": "en-us", "limit": 5, "q": nom}))
        n = _norm(nom)
        pid = next((str(x.get("playerId")) for x in (l or []) if isinstance(x, dict) and _norm(x.get("name")) == n and x.get("playerId")), None)
    if not pid:
        return None
    d = _get(f"https://api-web.nhle.com/v1/player/{pid}/landing")
    if not isinstance(d, dict):
        return None
    fs = ((d.get("featuredStats") or {}).get("regularSeason") or {})
    sub = fs.get("subSeason") or {}
    car = ((d.get("careerTotals") or {}).get("regularSeason") or {})
    dd = d.get("draftDetails") or {}
    age = None
    try:
        age = round((date.today() - date.fromisoformat(str(d.get("birthDate"))[:10])).days / 365.25, 1)
    except ValueError:
        pass
    return {"id": pid, "pos": d.get("position"), "actif": bool(d.get("isActive")), "age": age,
            "repech": dd.get("overallPick"), "an_repech": dd.get("year"),
            "mj": sub.get("gamesPlayed"), "pts": sub.get("points"), "buts": sub.get("goals"),
            "mj_c": car.get("gamesPlayed"), "pts_c": car.get("points"), "buts_c": car.get("goals"),
            "vic_c": car.get("wins"), "trophees": len(d.get("awards") or [])}


def lire_joueur(nom):
    return {"nom": nom, "le": time.time(), "nhl": _nhl(nom), "wiki": _wiki(nom)}


# -- les pieces (features) ---------------------------------------------------------------------------------------
PIECES = ("wiki90", "wiki_tend", "ppm", "pts_c", "age", "repech", "trophees", "gardien", "defense", "actif")


def pieces(e):
    n, w = (e or {}).get("nhl") or {}, (e or {}).get("wiki") or {}
    mj = n.get("mj") or 0
    v90, v30 = w.get("v90") or 0, w.get("v30") or 0
    return {
        "wiki90": math.log1p(v90),
        "wiki_tend": math.log1p(v30) - math.log1p((v90 - v30) / 2) if v90 else 0.0,
        "ppm": (n.get("pts") or 0) / mj if mj >= 5 else ((n.get("pts_c") or 0) / n["mj_c"] if n.get("mj_c") else 0.0),
        "pts_c": math.log1p(n.get("pts_c") or 0),
        "age": float(n.get("age") or 26.0),
        "repech": math.log(float(n.get("repech") or 250)),
        "trophees": math.log1p(n.get("trophees") or 0),
        "gardien": 1.0 if n.get("pos") == "G" else 0.0,
        "defense": 1.0 if n.get("pos") == "D" else 0.0,
        "actif": 1.0 if n.get("actif") else 0.0,
    }


# -- le labo : chaque piece et la combinaison, contre la demande mesuree sur les ventes (admin) -----------------
def _rangs(x):
    o = sorted(range(len(x)), key=lambda i: x[i])
    r = [0.0] * len(x)
    i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and x[o[j + 1]] == x[o[i]]:
            j += 1
        for k in range(i, j + 1):
            r[o[k]] = (i + j) / 2.0
        i = j + 1
    return r


def spearman(a, b):
    if len(a) < 5:
        return None
    ra, rb = _rangs(a), _rangs(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return round(num / den, 3) if den else None


def _ajuster(X, y, lam=1.0):
    """Regression ridge (numpy). -> (moyennes, ecarts, coefficients, constante)."""
    import numpy as np
    X, y = np.asarray(X, float), np.asarray(y, float)
    mu, sd = X.mean(0), X.std(0)
    sd[sd == 0] = 1.0
    Z = (X - mu) / sd
    A = Z.T @ Z + lam * np.eye(Z.shape[1])
    w = np.linalg.solve(A, Z.T @ (y - y.mean()))
    return mu.tolist(), sd.tolist(), w.tolist(), float(y.mean())


def _predire(m, p):
    z = [(p[k] - m["mu"][i]) / m["sd"][i] for i, k in enumerate(m["pieces"])]
    return m["b"] + sum(a * b for a, b in zip(m["w"], z))


def labo(d=None, verite=None):
    """Mesure chaque piece seule, puis des combinaisons (validation croisee en 5 plis). Garde la meilleure formule."""
    d = d or lire()
    if verite is None:
        import valeurs
        valeurs._charger()
        verite = {k: v for k, v in (valeurs._ETAT["data"].get("joueurs") or {}).items() if v and v > 0}
    vn = {_norm(k): v for k, v in verite.items()}
    lignes = [(nom, pieces(e), math.log(vn[_norm(nom)])) for nom, e in (d.get("joueurs") or {}).items()
              if _norm(nom) in vn and ((e.get("nhl") or e.get("wiki")))]
    if len(lignes) < 30:
        return {"n": len(lignes), "note": "pas assez de joueurs lus (30 au moins)"}
    y = [l[2] for l in lignes]
    seules = {k: spearman([l[1][k] for l in lignes], y) for k in PIECES}
    combos = {"popularite": ["wiki90"], "stats": ["ppm", "pts_c", "age", "repech", "gardien", "defense"],
              "tout": list(PIECES), "pop_stats": ["wiki90", "wiki_tend", "ppm", "pts_c", "age", "repech"]}
    res, meilleur = {}, None
    for nom_c, ks in combos.items():
        preds = [0.0] * len(lignes)
        for pli in range(5):
            tr = [i for i in range(len(lignes)) if i % 5 != pli]
            te = [i for i in range(len(lignes)) if i % 5 == pli]
            mu, sd, w, b = _ajuster([[lignes[i][1][k] for k in ks] for i in tr], [y[i] for i in tr])
            m = {"pieces": ks, "mu": mu, "sd": sd, "w": w, "b": b}
            for i in te:
                preds[i] = _predire(m, lignes[i][1])
        rho = spearman(preds, y)
        top_v = set(sorted(range(len(y)), key=lambda i: -y[i])[:20])
        top_p = set(sorted(range(len(y)), key=lambda i: -preds[i])[:20])
        res[nom_c] = {"rho": rho, "top20": len(top_v & top_p)}
        if rho is not None and (meilleur is None or rho > res[meilleur]["rho"]):
            meilleur = nom_c
    ks = combos[meilleur]
    mu, sd, w, b = _ajuster([[l[1][k] for k in ks] for l in lignes], y)
    modele = {"pieces": ks, "mu": mu, "sd": sd, "w": w, "b": b, "nom": meilleur, "n": len(lignes),
              "le": datetime.now().isoformat(timespec="seconds")}
    return {"n": len(lignes), "seules": seules, "combinaisons": res, "garde": meilleur, "modele": modele}


# -- la demande publique ---------------------------------------------------------------------------------------
def demande(joueur):
    """La demande d'un joueur (meme echelle que valeurs.demande) avec ses donnees publiques seulement ; None si inconnu."""
    d = lire()
    m = d.get("modele")
    if not m:
        return None
    idx = d.get("_idx")
    if idx is None:
        idx = d["_idx"] = {_norm(k): k for k in (d.get("joueurs") or {})}
    k = idx.get(_norm(joueur))
    e = (d.get("joueurs") or {}).get(k) if k else None
    if not e or not (e.get("nhl") or e.get("wiki")):
        return None
    return round(min(8.0, max(0.15, math.exp(_predire(m, pieces(e))))), 3)


def tendance(joueur):
    """La tendance publique : visites Wikipedia des 30 derniers jours contre les 60 d'avant (+ / - / =)."""
    d = lire()
    e = next((v for k, v in (d.get("joueurs") or {}).items() if _norm(k) == _norm(joueur)), None)
    w = (e or {}).get("wiki") or {}
    v90, v30 = w.get("v90") or 0, w.get("v30") or 0
    if v90 < 300:
        return None
    r = v30 / max(1.0, (v90 - v30) / 2)
    return {"ratio": round(r, 2), "sens": "hausse" if r >= 1.25 else "baisse" if r <= 0.8 else "stable"}


# -- la collecte (une passe par heure, en arriere-plan) ---------------------------------------------------------
def _a_lire(n=PAR_PASSE):
    import valeurs
    valeurs._charger()
    noms = list((valeurs._ETAT["data"].get("joueurs") or {}).keys())
    try:
        import catalogue
        for p in catalogue.liste() or []:
            pp = catalogue.charger(p["id"]) or {}
            noms += [c["joueur"] for c in pp.get("cartes") or [] if c.get("joueur") and "/" not in c["joueur"]]
    except Exception:
        pass
    d = lire()
    lim = time.time() - FRAICHEUR_J * 86400
    vus, out = set(), []
    for nm in noms:
        k = _norm(nm)
        if not k or k in vus:
            continue
        vus.add(k)
        e = (d.get("joueurs") or {}).get(nm)
        if not e or e.get("le", 0) < lim:
            out.append(nm)
        if len(out) >= n:
            break
    return out


def passe(n=PAR_PASSE):
    lus = 0
    for nom in _a_lire(n):
        e = lire_joueur(nom)
        with _verrou:
            d = dict(lire())
            d.pop("_idx", None)
            d.setdefault("joueurs", {})[nom] = e
            _ecrire(d)
        lus += 1
        time.sleep(0.4)
    with _verrou:
        d = dict(lire())
        d.pop("_idx", None)
        r = labo(d)
        if r.get("modele"):
            d["modele"] = r["modele"]
        d["labo"] = {k: v for k, v in r.items() if k != "modele"}
        d["labo"]["le"] = datetime.now().isoformat(timespec="seconds")
        _ecrire(d)
    return {"lus": lus, "labo": d.get("labo")}


def passe_si_besoin():
    if _ETAT["en_cours"] or time.time() - _ETAT["le"] < 3500 or os.environ.get("LR_DEMANDE_LEGALE") == "0":
        return False
    _ETAT.update(en_cours=True, le=time.time())

    def tache():
        try:
            r = passe()
            print("Demande legale :", r.get("lus"), "joueurs lus ; labo", (r.get("labo") or {}).get("combinaisons"), flush=True)
        except Exception as e:
            print("Demande legale : " + repr(e), flush=True)
        finally:
            _ETAT["en_cours"] = False
    threading.Thread(target=tache, daemon=True, name="demande_legale").start()
    return True


def statut():
    d = lire()
    return {"joueurs": len(d.get("joueurs") or {}), "labo": d.get("labo"), "modele": (d.get("modele") or {}).get("nom")}
