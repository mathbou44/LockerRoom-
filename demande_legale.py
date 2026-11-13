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
FRAICHEUR_J = 7                  # (ancien) : remplace par les deux fraicheurs ci-dessous
# 10 nov 2026 (Mathieu : « les stats doivent etre mises a jour regulierement, tout ce qui est vivant ») : les stats LNH de
# chaque joueur relues chaque jour (les matchs sont le soir), ses visites Wikipedia aux 3 jours (limite de Wikimedia)
FRAICHEUR_NHL_S = 20 * 3600
FRAICHEUR_WIKI_S = 86400           # 10 nov 2026 (Mathieu : « a chaque jour, a la fine pointe ») : chaque jour
PAR_PASSE = 400                  # joueurs relus (LNH) par passe ; une passe par heure : tout le monde chaque jour
PAR_PASSE_WIKI = 250
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


AMORCE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demande_legale_amorce.json")


def lire():
    ch = _chemin()
    if not os.path.exists(ch) and os.path.exists(AMORCE):
        # 10 nov 2026 : l'amorce (758 joueurs deja lus : LNH + Wikipedia, donnees publiques) : le labo et le modele
        # demarrent tout de suite en ligne ; les joueurs sont ensuite relus chaque semaine
        try:
            import shutil
            shutil.copyfile(AMORCE, ch)
        except OSError:
            pass
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
def _wiki_lot(noms):
    """Visites Wikipedia (anglais, 60 jours) de plusieurs joueurs en UNE requete (50 titres) : « Nom (ice hockey) » puis
    « Nom » ; la page doit parler de hockey (homonymes). Respecte la limite de Wikimedia (retry-after). -> {nom: {...}}"""
    import urllib.error
    titres = []
    for n in noms:
        titres += [n + " (ice hockey)", n]
    out = {}
    for i in range(0, len(titres), 50):
        lot = titres[i:i + 50]
        u = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({"action": "query", "format": "json", "formatversion": 2,
                                                                          "redirects": 1, "prop": "pageviews|description|info|langlinks", "pvipdays": 60,
                                                                          "lllang": "fr", "lllimit": "max",
                                                                          "titles": "|".join(lot)})
        def lire_u(adr):
            for _essai in range(4):
                try:
                    with urllib.request.urlopen(urllib.request.Request(adr, headers={"User-Agent": UA}), timeout=30) as r:
                        return json.loads(r.read())
                except urllib.error.HTTPError as e:
                    if e.code != 429:
                        return None
                    time.sleep(min(90, int(e.headers.get("retry-after") or 30) + 2))
                except Exception:
                    return None
            return None
        d = lire_u(u)
        if not d:
            continue
        # les visites arrivent par morceaux (« pvipcontinue ») : on suit la suite jusqu'au bout
        vues = {p_["title"]: p_.get("pageviews") for p_ in (d.get("query") or {}).get("pages") or [] if p_.get("pageviews")}
        suite, garde = d.get("continue"), 0
        while suite and garde < 10:
            garde += 1
            time.sleep(1)
            d2 = lire_u(u + "&" + urllib.parse.urlencode(suite))
            if not d2:
                break
            for p_ in (d2.get("query") or {}).get("pages") or []:
                if p_.get("pageviews"):
                    vues[p_["title"]] = p_["pageviews"]
            suite = d2.get("continue")
        q = d.get("query") or {}
        redir = {m["from"]: m["to"] for m in (q.get("normalized") or []) + (q.get("redirects") or [])}
        pages = {p["title"]: p for p in q.get("pages") or []}
        for t in lot:
            tt = t
            for _ in range(3):
                tt = redir.get(tt, tt)
            p = pages.get(tt)
            nom = t[:-len(" (ice hockey)")] if t.endswith(" (ice hockey)") else t
            if not p or p.get("missing") or "hockey" not in str(p.get("description") or "").lower():
                continue
            pv = [v or 0 for v in (vues.get(p.get("title")) or p.get("pageviews") or {}).values()]
            if nom not in out:
                fr = ((p.get("langlinks") or [{}])[0] or {}).get("title")
                out[nom] = {"titre": tt, "v60": sum(pv), "v20": sum(pv[-20:]), "v7": sum(pv[-7:]), "v3": sum(pv[-3:]), "len": p.get("length"), "fr": fr,
                            "fr60": _vues_fr(fr) if fr else 0}
        time.sleep(2)
    return out


def _vues_fr(titre):
    """Visites de la page Wikipedia francaise (60 jours) : le marche du Quebec. API REST de Wikimedia, une page a la fois."""
    import urllib.error
    fin = date.today() - timedelta(days=1)
    deb = fin - timedelta(days=59)
    u = (f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/fr.wikipedia/all-access/user/"
         f"{urllib.parse.quote(str(titre).replace(' ', '_'), safe='')}/daily/{deb:%Y%m%d}/{fin:%Y%m%d}")
    for _essai in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=20) as r:
                time.sleep(0.5)
                return sum(int(it.get("views") or 0) for it in json.loads(r.read()).get("items") or [])
        except urllib.error.HTTPError as e:
            if e.code != 429:
                return 0
            time.sleep(min(60, int(e.headers.get("retry-after") or 20) + 2))
        except Exception:
            return 0
    return 0


def _wiki(nom):
    return _wiki_lot([nom]).get(nom)


def _nhl(nom):
    import nhl
    pid = nhl._id(nom)
    if not pid:
        l = _get("https://search.d3.nhle.com/api/v1/search/player?" + urllib.parse.urlencode({"culture": "en-us", "limit": 5, "q": nom}))
        n = _norm(nom)
        pid = next((str(x.get("playerId")) for x in (l or []) if isinstance(x, dict) and _norm(x.get("name")) == n and x.get("playerId")), None)
    if not pid:
        return None
    L = _get(f"https://api-web.nhle.com/v1/player/{pid}/landing")
    if not isinstance(L, dict):
        return None
    bsp = L.get("birthStateProvince")
    return {"id": pid, "equipe": L.get("currentTeamAbbrev"), "pays": L.get("birthCountry"),
            "province": (bsp or {}).get("default") if isinstance(bsp, dict) else bsp,
            "hhof": bool(L.get("inHHOF")), "top100": bool(L.get("inTop100AllTime")), "actif": bool(L.get("isActive")),
            "pos": L.get("position"), "repech": (L.get("draftDetails") or {}).get("overallPick"), "naissance": str(L.get("birthDate") or "")[:10],
            "trophees": [str((a.get("trophy") or {}).get("default") or "") for a in L.get("awards") or []],
            "trophees_n": sum(len(a.get("seasons") or []) for a in L.get("awards") or []),
            "carriere": (L.get("careerTotals") or {}).get("regularSeason") or {}, "series": (L.get("careerTotals") or {}).get("playoffs") or {},
            "saison": (((L.get("featuredStats") or {}).get("regularSeason") or {}).get("subSeason") or {}),
            "saisons": len([x for x in L.get("seasonTotals") or [] if x.get("leagueAbbrev") == "NHL" and x.get("gameTypeId") == 2]),
            # 10 nov 2026 (labo, 0,71 -> 0,735) : chaque saison (LNH et junior), la ronde et l'annee du repechage, chaque trophee
            "par_saison": [{"s": x.get("season"), "l": x.get("leagueAbbrev"), "gp": x.get("gamesPlayed"), "p": x.get("points"),
                            "toi": x.get("avgToi")} for x in L.get("seasonTotals") or [] if x.get("gameTypeId") == 2 and (x.get("gamesPlayed") or 0) > 0],
            "chandail": L.get("sweaterNumber"),          # 13 nov 2026 : numerotee au numero du chandail (numeriques4)
            # 13 nov 2026 : l'equipe de chaque saison LNH (fidelite a une franchise : score_modele.numeriques3)
            "equipes": [[x.get("season"), (x.get("teamName") or {}).get("default"), x.get("gamesPlayed") or 0] for x in L.get("seasonTotals") or []
                        if x.get("leagueAbbrev") == "NHL" and x.get("gameTypeId") == 2],
            "ronde": (L.get("draftDetails") or {}).get("round"), "an_repech": (L.get("draftDetails") or {}).get("year"),
            "trophees_c": {str((a.get("trophy") or {}).get("default") or ""): len(a.get("seasons") or []) for a in L.get("awards") or []},
            "l5": sum(int(m.get("points") or 0) for m in L.get("last5Games") or [] if isinstance(m, dict))}


# -- les pieces (features) ---------------------------------------------------------------------------------------
EQUIPES = ("ANA", "BOS", "BUF", "CGY", "CAR", "CHI", "COL", "CBJ", "DAL", "DET", "EDM", "FLA", "LAK", "MIN", "MTL", "NSH", "NJD",
           "NYI", "NYR", "OTT", "PHI", "PIT", "SJS", "SEA", "STL", "TBL", "TOR", "UTA", "VAN", "VGK", "WSH", "WPG")
EQ_CAN = {"MTL", "TOR", "VAN", "EDM", "CGY", "OTT", "WPG"}
EQ_ORIG6 = {"MTL", "TOR", "BOS", "CHI", "DET", "NYR"}
PIECES = ("age", "logpick", "top10", "gp", "pts", "ppg", "spts", "sppg", "po_pts", "trophees", "hart", "hhof", "top100", "legende",
          "actif", "G", "D", "saisons", "l5", "wiki", "wiki_tend",
          # 10 nov 2026 (2e iteration) : saisons, trophees detailles, catalogue, Wikipedia francais
          "pic", "picppg", "dppg", "tend_ppg", "debut", "jppg", "toi", "ronde", "an_rep", "stanley", "calder", "artross", "conn",
          "vezina", "norris", "richard", "cat_n", "cat_hits", "wiki_fr", "wiki_len",
          # 13 nov 2026 (Mathieu : « tu prends en consideration les equipes qui vendent le plus ? ») : l'equipe (marche canadien,
          # Original Six, chaque club) et d'ou il vient (Canada, Quebec) ; le labo mesure ce qu'elles valent contre les ventes
          "eq_marche", "eq_can", "eq_orig6", "ne_can", "ne_qc") + tuple("eq_" + e for e in EQUIPES)
JUNIORS = {"OHL", "WHL", "QMJHL", "LHJMQ", "USHL", "NCAA", "SHL", "KHL", "Liiga", "NTDP", "USDP", "MHL", "AHL", "Allsvenskan", "NL"}
_CAT = {"le": 0.0, "n": {}, "h": {}}


def presence_catalogue():
    """Combien de cartes (et de hits : autos, patchs, /99 et moins) le fabricant donne a chaque joueur dans nos produits.
    Notre catalogue (checklists officielles) : le fabricant sait qui se vend. Garde 6 h."""
    if time.time() - _CAT["le"] < 6 * 3600 and _CAT["n"]:
        return _CAT["n"], _CAT["h"]
    n, h = {}, {}
    try:
        import catalogue
        for p in catalogue.liste() or []:
            pp = catalogue.charger(p["id"]) or {}
            se = {x["nom"]: x for x in pp.get("sous_ensembles") or []}
            for c in pp.get("cartes") or []:
                s_ = se.get(c.get("sous_ensemble")) or {}
                hit = str(s_.get("groupe") or "") in ("auto", "memo", "auto_memo") or bool(s_.get("tirage") and s_["tirage"] <= 99)
                for j in re.split(r"\s*/\s*", str(c.get("joueur") or "")):
                    k = _norm(j)
                    if k:
                        n[k] = n.get(k, 0) + 1
                        if hit:
                            h[k] = h.get(k, 0) + 1
    except Exception as e:
        print("Demande legale (catalogue) : " + repr(e), flush=True)
    _CAT.update(le=time.time(), n=n, h=h)
    return n, h


def _toi(x):
    try:
        m, s_ = str(x).split(":")
        return int(m) + int(s_) / 60
    except (ValueError, TypeError):
        return 0.0


def pieces(e):
    """Les mesures publiques d'un joueur (LNH + Wikipedia). Les anciennes fiches (avant le 10 nov) donnent des zeros."""
    n, w = (e or {}).get("nhl") or {}, (e or {}).get("wiki") or {}
    car, po, sa = n.get("carriere") or {}, n.get("series") or {}, n.get("saison") or {}
    try:
        age = (date.today() - date.fromisoformat(n.get("naissance") or "")).days / 365.25
    except ValueError:
        age = float(n.get("age") or 27.0)
    gp, pts = car.get("gamesPlayed") or n.get("mj_c") or 0, car.get("points") or n.get("pts_c") or 0
    sgp, spts = sa.get("gamesPlayed") or n.get("mj") or 0, sa.get("points") or n.get("pts") or 0
    pick = float(n.get("repech") or 250)
    tr = [str(x) for x in n.get("trophees") or []] if isinstance(n.get("trophees"), list) else []
    v60 = w.get("v60") if w.get("v60") is not None else (w.get("v90") or 0) * 2 / 3
    v20 = w.get("v20") if w.get("v20") is not None else (w.get("v30") or 0) * 2 / 3
    return {
        "age": age, "logpick": math.log(pick), "top10": 1.0 if pick <= 10 else 0.0,
        "gp": math.log1p(gp), "pts": math.log1p(pts), "ppg": pts / gp if gp >= 20 else 0.0,
        "spts": math.log1p(spts), "sppg": spts / sgp if sgp >= 5 else 0.0, "po_pts": math.log1p(po.get("points") or 0),
        "trophees": math.log1p(n.get("trophees_n") or (n.get("trophees") if isinstance(n.get("trophees"), int) else 0) or 0),
        "hart": 1.0 if any("Hart" in x for x in tr) else 0.0, "hhof": 1.0 if n.get("hhof") else 0.0, "top100": 1.0 if n.get("top100") else 0.0,
        "legende": 1.0 if (n.get("hhof") or n.get("top100")) and not n.get("actif") else 0.0,
        "actif": 1.0 if n.get("actif") else 0.0, "G": 1.0 if n.get("pos") == "G" else 0.0, "D": 1.0 if n.get("pos") == "D" else 0.0,
        "saisons": float(n.get("saisons") or 0), "l5": float(n.get("l5") or 0),
        "wiki": math.log1p(v60 or 0), "wiki_tend": (math.log1p(v20) - math.log1p(((v60 or 0) - v20) / 2)) if v60 else 0.0,
        **_pieces2(e, n, w),
    }


def _pieces2(e, n, w):
    st = n.get("par_saison") or []
    lnh = sorted([x for x in st if x.get("l") == "NHL" and (x.get("gp") or 0) > 0], key=lambda x: x.get("s") or 0)
    jr = [x for x in st if x.get("l") in JUNIORS and (x.get("gp") or 0) >= 10]
    der, avd = (lnh[-1] if lnh else {}), (lnh[-2] if len(lnh) > 1 else {})
    ppg = lambda x: (x.get("p") or 0) / x["gp"] if x.get("gp") else 0.0
    tc = n.get("trophees_c") or {}
    cnt = lambda k: float(sum(v for t, v in tc.items() if k in t))
    cn, ch = presence_catalogue()
    k = _norm((e or {}).get("nom") or "")
    return {"pic": math.log1p(max([x.get("p") or 0 for x in lnh] or [0])),
            "picppg": max([ppg(x) for x in lnh if (x.get("gp") or 0) >= 20] or [0.0]),
            "dppg": ppg(der), "tend_ppg": ppg(der) - ppg(avd),
            "debut": float(date.today().year - int(str(lnh[0]["s"])[:4])) if lnh else -1.0,
            "jppg": max([ppg(x) for x in jr] or [0.0]), "toi": _toi(der.get("toi")),
            "ronde": float(n.get("ronde") or 9), "an_rep": float(n.get("an_repech") or 0),
            "stanley": cnt("Stanley"), "calder": cnt("Calder"), "artross": cnt("Art Ross"), "conn": cnt("Conn Smythe"),
            "vezina": cnt("Vezina"), "norris": cnt("Norris"), "richard": cnt("Richard"),
            "cat_n": math.log1p(cn.get(k, 0)), "cat_hits": math.log1p(ch.get(k, 0)),
            "wiki_fr": math.log1p(w.get("fr60") or 0), "wiki_len": math.log1p(w.get("len") or 0),
            **_pieces_equipe(n)}


def _pieces_equipe(n):
    eq = str(n.get("equipe") or "").upper()
    pays, prov = str(n.get("pays") or "").upper(), str(n.get("province") or "").lower()
    try:
        mq = marche_equipe(eq) if eq else None
    except Exception:
        mq = None
    return {"eq_marche": (mq or 50.0) / 100.0 if eq else 0.0,
            "eq_can": 1.0 if eq in EQ_CAN else 0.0, "eq_orig6": 1.0 if eq in EQ_ORIG6 else 0.0,
            "ne_can": 1.0 if pays in ("CAN", "CA") else 0.0, "ne_qc": 1.0 if prov in ("quebec", "québec", "qc") else 0.0,
            **{"eq_" + e: 1.0 if eq == e else 0.0 for e in EQUIPES}}


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
    combos = {"popularite": ["wiki", "wiki_tend"],
              "stats": ["age", "logpick", "top10", "gp", "pts", "ppg", "spts", "sppg", "po_pts", "trophees", "saisons", "l5", "G", "D"],
              "stats_legendes": ["age", "logpick", "top10", "gp", "pts", "ppg", "spts", "sppg", "po_pts", "trophees", "hart", "hhof", "top100",
                                 "legende", "actif", "saisons", "l5", "G", "D"],
              "tout": list(PIECES)}
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
    # 10 nov 2026 : des arbres (gradient boosting) captent ce qu'une droite ne voit pas (une legende retiree, une recrue n°1)
    gb = _arbres_cv(lignes, y)
    if gb:
        res["arbres"] = gb["mesure"]
        if gb["mesure"]["rho"] is not None and (meilleur is None or gb["mesure"]["rho"] > res[meilleur]["rho"]):
            meilleur = "arbres"
    if meilleur == "arbres":
        modele = {"pieces": list(PIECES), "nom": "arbres", "arbres": True, "n": len(lignes), "le": datetime.now().isoformat(timespec="seconds")}
        _sauver_arbres(gb["modele"])
    else:
        ks = combos[meilleur]
        mu, sd, w, b = _ajuster([[l[1][k] for k in ks] for l in lignes], y)
        modele = {"pieces": ks, "mu": mu, "sd": sd, "w": w, "b": b, "nom": meilleur, "n": len(lignes),
                  "le": datetime.now().isoformat(timespec="seconds")}
    return {"n": len(lignes), "seules": seules, "combinaisons": res, "garde": meilleur, "modele": modele,
            "equipes": table_equipes(d, verite)}


def table_equipes(d=None, verite=None):
    """13 nov 2026 (Mathieu : « les equipes, meme americaines, qui ont le plus d'acheteurs / de liquidite doivent avoir un
    score plus eleve ») : chaque club LNH : le nombre de ventes de cartes de ses joueurs dans nos archives (90 jours) et la
    demande moyenne mesuree sur les ventes. Calculee au labo (admin) ; un joueur n'y est relie que par le NOM de son equipe."""
    d = d or lire()
    try:
        import base_ventes
        vpj = {_norm(k): v for k, v in base_ventes.ventes_par_joueur(90).items()}
    except Exception:
        vpj = {}
    vn = {_norm(k): v for k, v in (verite or {}).items()}
    eq = {}
    for nom, e in (d.get("joueurs") or {}).items():
        n = (e or {}).get("nhl") or {}
        t = str(n.get("equipe") or "").upper()
        if not t or n.get("actif") is False:
            continue
        x = eq.setdefault(t, {"ventes": 0, "joueurs": 0, "dem": []})
        x["joueurs"] += 1
        x["ventes"] += vpj.get(_norm(nom), 0)
        if _norm(nom) in vn:
            x["dem"].append(math.log(vn[_norm(nom)]))
    out = {}
    for t, x in eq.items():
        out[t] = {"ventes": x["ventes"], "joueurs": x["joueurs"],
                  "demande": round(math.exp(sum(x["dem"]) / len(x["dem"])), 3) if x["dem"] else None}
    tot = sorted(out.values(), key=lambda v: v["ventes"])
    for r, v in enumerate(tot):
        v["rang_pct"] = round(100 * (r + 0.5) / len(tot), 1)          # 100 = le club qui vend le plus
    return out


def marche_equipe(equipe):
    """Le marche d'un club (0 a 100 : 100 = le plus d'acheteurs), d'apres la table du labo ; None si inconnu."""
    t = (lire().get("equipes") or {}).get(str(equipe or "").upper())
    return t.get("rang_pct") if t else None


def _arbres_cv(lignes, y):
    try:
        import numpy as np
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.model_selection import KFold, cross_val_predict
    except ImportError:
        return None
    from sklearn.ensemble import RandomForestRegressor
    X = np.array([[l[1][k] for k in PIECES] for l in lignes])
    yy = np.array(y)
    # 10 nov 2026 (labo sur 758 joueurs) : foret 0,71, boosting 0,70, droite 0,64 ; on garde le meilleur des deux arbres
    meilleur = None
    for m in (RandomForestRegressor(n_estimators=500, min_samples_leaf=3, max_features=0.33, random_state=0, n_jobs=2),
              GradientBoostingRegressor(n_estimators=300, max_depth=4, learning_rate=0.03, subsample=0.8, min_samples_leaf=8, random_state=0)):
        p = cross_val_predict(m, X, yy, cv=KFold(5, shuffle=True, random_state=0))
        rho = spearman(list(p), list(yy))
        top = len(set(np.argsort(-yy)[:20]) & set(np.argsort(-p)[:20]))
        if meilleur is None or (rho or 0) > (meilleur[0] or 0):
            meilleur = (rho, int(top), m)
    meilleur[2].fit(X, yy)
    return {"mesure": {"rho": meilleur[0], "top20": meilleur[1], "type": type(meilleur[2]).__name__}, "modele": meilleur[2]}


_ARBRES = {"m": None, "mt": None}


def _chemin_arbres():
    return _chemin().replace(".json", "_arbres.pkl")


def _sauver_arbres(m):
    import pickle
    with open(_chemin_arbres() + ".tmp", "wb") as f:
        pickle.dump(m, f)
    os.replace(_chemin_arbres() + ".tmp", _chemin_arbres())


def _arbres():
    import pickle
    try:
        mt = os.path.getmtime(_chemin_arbres())
    except OSError:
        return None
    if _ARBRES["mt"] != mt:
        with open(_chemin_arbres(), "rb") as f:            # notre propre modele, ecrit par notre serveur
            _ARBRES.update(m=pickle.load(f), mt=mt)
    return _ARBRES["m"]


# -- la demande publique ---------------------------------------------------------------------------------------
_MEMO = {"cle": None, "d": {}}


def demande(joueur):
    """La demande d'un joueur (meme echelle que valeurs.demande) avec ses donnees publiques seulement ; None si inconnu.
    Gardee en memoire par joueur tant que le fichier ne change pas (appelee des milliers de fois par calcul de break)."""
    cle = (_ETAT.get("mtime"), _ARBRES.get("mt"))
    if _MEMO["cle"] != cle:
        _MEMO.update(cle=cle, d={})
    k0 = _norm(joueur)
    if k0 in _MEMO["d"]:
        return _MEMO["d"][k0]
    v = _demande0(joueur)
    if len(_MEMO["d"]) < 20000:
        _MEMO["d"][k0] = v
    return v


def _demande0(joueur):
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
    if m.get("arbres"):
        a = _arbres()
        if a is None or getattr(a, "n_features_in_", len(PIECES)) != len(PIECES):
            return None                                   # modele d'avant les nouvelles mesures : refait a la passe suivante
        p = pieces(e)
        return round(min(20.0, max(0.15, math.exp(float(a.predict([[p[k] for k in PIECES]])[0])))), 3)
    return round(min(20.0, max(0.15, math.exp(_predire(m, pieces(e))))), 3)


def tendance(joueur):
    """La tendance publique : visites Wikipedia des 30 derniers jours contre les 60 d'avant (+ / - / =)."""
    d = lire()
    e = next((v for k, v in (d.get("joueurs") or {}).items() if _norm(k) == _norm(joueur)), None)
    w = (e or {}).get("wiki") or {}
    v60, v20 = w.get("v60") or 0, w.get("v20") or 0
    if v60 < 200:
        return None
    r = v20 / max(1.0, (v60 - v20) / 2)
    return {"ratio": round(r, 2), "sens": "hausse" if r >= 1.25 else "baisse" if r <= 0.8 else "stable"}


# -- la collecte (une passe par heure, en arriere-plan) ---------------------------------------------------------
def _tous_les_noms():
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
    noms += _noms_marche()
    vus, out = set(), []
    for nm in noms:
        k = _norm(nm)
        if k and k not in vus:
            vus.add(k)
            out.append(nm)
    return out


_MARCHE = {"le": 0.0, "noms": []}
PAS_DES_NOMS = {"from list", "complete your", "tim hortons", "wild card", "take your", "road to", "upper deck", "young guns",
                "pick your", "you pick", "o pee", "series one", "series two"}


def _noms_marche(jours=60, n_min=12, max_=300):
    """11 nov 2026 (SlabIQ : les prospects - Martone, Hagens, McKenna - et des legendes - Messier, Clarke, Hasek - etaient
    « inconnus » : ils n'etaient ni au catalogue ni dans nos valeurs) : les joueurs qui reviennent le plus dans les VENTES
    du serveur (base_ventes). Ceux que la LNH ne connait pas restent simplement sans fiche. Recalcule une fois par jour."""
    if time.time() - _MARCHE["le"] < 86400:
        return _MARCHE["noms"]
    _MARCHE["le"] = time.time()
    try:
        import sqlite3
        import collections
        import comptes
        import cartes_match
        ch = os.path.join(comptes.DONNEES, "base_ventes.sqlite")
        if not os.path.exists(ch):
            return []
        depuis = time.strftime("%Y-%m-%d", time.gmtime(time.time() - jours * 86400))
        c = sqlite3.connect(ch, timeout=5)
        try:
            titres = [r[0] for r in c.execute("SELECT titre FROM ventes WHERE le >= ? ORDER BY le DESC LIMIT 80000", (depuis,))]
        finally:
            c.close()
        cnt = collections.Counter()
        for t in titres:
            j = cartes_match.joueur_du_titre(t or "")
            if j and len(j.split()) >= 2 and j not in PAS_DES_NOMS:
                cnt[j] += 1
        _MARCHE["noms"] = [n.title() for n, k in cnt.most_common(max_) if k >= n_min]
    except Exception as e:
        print("Demande (noms du marche) : " + repr(e), flush=True)
    return _MARCHE["noms"]


def _a_lire(n=PAR_PASSE, quoi="nhl"):
    """Les joueurs dont les stats LNH (ou les visites Wikipedia) sont perimees, les plus vieilles d'abord."""
    d = lire()
    maint = time.time()
    lim = maint - (FRAICHEUR_NHL_S if quoi == "nhl" else FRAICHEUR_WIKI_S)
    a = []
    for nm in _tous_les_noms():
        e = (d.get("joueurs") or {}).get(nm) or {}
        le = e.get("le_" + quoi, e.get("le", 0))
        if le > maint + 86400:                            # vieille amorce (date dans le futur)
            le = 0
        if le < lim:
            a.append((le, nm))
    a.sort()
    return [nm for _le, nm in a[:n]]


def passe(n=PAR_PASSE):
    """Une passe : les stats LNH perimees (chaque jour), les visites Wikipedia perimees (aux 3 jours), puis le labo."""
    maint = time.time()
    noms_n = _a_lire(n, "nhl")
    noms_w = _a_lire(PAR_PASSE_WIKI, "wiki")
    wiki = {}
    for i in range(0, len(noms_w), 25):                  # Wikipedia : 25 joueurs (50 titres) par requete
        wiki.update(_wiki_lot(noms_w[i:i + 25]))
    nhl_ = {}
    for nom in noms_n:
        nhl_[nom] = _nhl(nom)
        time.sleep(0.25)
    with _verrou:
        d = dict(lire())
        d.pop("_idx", None)
        J = d.setdefault("joueurs", {})
        for nom in set(noms_n) | set(noms_w):
            e = dict(J.get(nom) or {"nom": nom})
            if nom in nhl_ and (nhl_[nom] or not e.get("nhl")):
                e["nhl"], e["le_nhl"] = nhl_[nom], maint      # un echec passager ne remplace pas les stats d'hier
            if nom in noms_w and (wiki.get(nom) or not e.get("wiki")):
                e["wiki"], e["le_wiki"] = wiki.get(nom), maint
            e["le"] = maint
            J[nom] = e
        _ecrire(d)
    with _verrou:
        d = dict(lire())
        d.pop("_idx", None)
        r = labo(d)
        if r.get("modele"):
            d["modele"] = r["modele"]
        if r.get("equipes"):
            d["equipes"] = r["equipes"]
        d["labo"] = {k: v for k, v in r.items() if k not in ("modele", "equipes")}
        d["labo"]["le"] = datetime.now().isoformat(timespec="seconds")
        _ecrire(d)
    return {"lus": len(noms_n), "wiki": len(noms_w), "labo": d.get("labo")}


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
    J = list((d.get("joueurs") or {}).values())
    maint = time.time()
    a_jour_n = sum(1 for e in J if maint - e.get("le_nhl", e.get("le", 0)) < FRAICHEUR_NHL_S + 7200)
    a_jour_w = sum(1 for e in J if maint - e.get("le_wiki", e.get("le", 0)) < FRAICHEUR_WIKI_S + 7200)
    return {"joueurs": len(J), "labo": d.get("labo"), "modele": (d.get("modele") or {}).get("nom"),
            "a_jour_lnh": a_jour_n, "a_jour_wiki": a_jour_w}


def populaires(n=12, recrues=False):
    """10 nov 2026 (Mathieu : « on devrait voir des cartes ») : les joueurs actifs les plus demandes selon nos donnees
    publiques (le score de demande legal), la popularite en hausse d'abord a score proche. Pour le questionnaire du Radar
    (les pastilles de joueurs) et « A decouvrir » quand le Radar est vide. Aucun prix ici."""
    d = lire()
    out = []
    for nom, e in (d.get("joueurs") or {}).items():
        h = e.get("nhl") or {}
        if not h.get("equipe") or h.get("actif") is False:
            continue
        if recrues and (h.get("saisons") or 0) > 2:
            continue
        s = demande(nom) if d.get("modele") else None
        if not s:                                  # pas encore de modele (1re passe) : les visites Wikipedia des 60 jours
            s = math.log1p((e.get("wiki") or {}).get("v60") or 0) / 3
        if not s:
            continue
        t = tendance(nom) or {}
        out.append({"nom": nom, "equipe": h.get("equipe"), "recrue": (h.get("saisons") or 0) <= 2,
                    "hausse": t.get("sens") == "hausse", "_s": s * (1.15 if t.get("sens") == "hausse" else 1.0)})
    out.sort(key=lambda x: -x["_s"])
    for x in out:
        x.pop("_s", None)
    return out[:n]
