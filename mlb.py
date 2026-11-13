"""
SLABCOACH - le baseball : les joueurs et leurs stats publiques (13 nov 2026).

Mathieu : « il va falloir commencer a integrer les autres sports ; on va y aller avec le baseball » (2e sport au Canada :
~1,3 M annonces de cartes au Canada contre ~420 k pour le basketball).

Source : l'API publique des stats de la MLB (statsapi.mlb.com, gratuite, sans cle), comme api-web.nhle.com pour la LNH.
  - la liste des joueurs : MLB et ligues mineures (AAA, AA, A+, A) : les prospects des 1st Bowman y sont ;
  - la fiche d'un joueur : equipe, position, naissance, debut, repechage, trophees (MVP, Cy Young, recrue de l'annee, Temple
    de la renommee...), stats de chaque saison (frappeur et lanceur).
Jamais un prix ici. Les fiches sont gardees dans mlb_fiches.json (relues chaque jour pour les joueurs qui se vendent).
"""
import json
import os
import re
import threading
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import date

BASE = "https://statsapi.mlb.com/api/v1"
UA = "SlabCoach/1.0 (+https://www.slabcoach.com; support@slabcoach.com)"
NIVEAUX = {1: "MLB", 11: "AAA", 12: "AA", 13: "A+", 14: "A"}
LISTE_S = 7 * 86400                   # la liste des joueurs : chaque semaine
FICHE_S = 20 * 3600                   # une fiche : chaque jour
PAR_PASSE = 150
_verrou = threading.Lock()
_ETAT = {"en_cours": False, "le": 0.0, "derniere": None, "erreur": None}
_CACHE = {}


def _n(t):
    t = "".join(c for c in unicodedata.normalize("NFKD", str(t or "")) if not unicodedata.combining(c)).lower()
    t = re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", " ", t)
    return " ".join(re.sub(r"[^a-z ]", " ", t.replace("'", "").replace(".", "")).split())


def _get(chemin, params=None, timeout=20):
    u = BASE + chemin + ("?" + urllib.parse.urlencode(params, safe=",[]()") if params else "")
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "application/json"}), timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        _ETAT["erreur"] = {"le": time.time(), "texte": f"{type(e).__name__} {chemin}"[:160]}
        return None


def _chemin(nom):
    import comptes
    return os.path.join(comptes.DONNEES, nom)


def _lire(nom):
    p = _chemin(nom)
    try:
        mt = os.path.getmtime(p)
    except OSError:
        return {}
    c = _CACHE.get(nom)
    if c and c[0] == mt:
        return c[1]
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f) or {}
    except (OSError, ValueError):
        return c[1] if c else {}
    _CACHE[nom] = (mt, d)
    return d


def _ecrire(nom, d):
    p = _chemin(nom)
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(p + ".tmp", p)
    _CACHE[nom] = (os.path.getmtime(p), d)


def saison(aujourdhui=None):
    """La saison de baseball : l'annee (de mars a decembre) ; en janvier-fevrier, celle d'avant."""
    d = aujourdhui or date.today()
    return d.year if d.month >= 3 else d.year - 1


# -- la liste des joueurs -----------------------------------------------------------------------------------------
def lire_liste(personnes, niveau):
    """La reponse /sports/{id}/players -> {nom normalise: joueur}. Calcul pur (teste)."""
    out = {}
    for p in personnes or []:
        if not isinstance(p, dict) or not p.get("id") or not p.get("fullName"):
            continue
        out[_n(p["fullName"])] = {"id": p["id"], "nom": p["fullName"], "niveau": niveau, "naissance": str(p.get("birthDate") or "")[:10],
                                  "debut": str(p.get("mlbDebutDate") or "")[:10] or None, "pos": (p.get("primaryPosition") or {}).get("abbreviation"),
                                  "equipe_id": (p.get("currentTeam") or {}).get("id"), "actif": p.get("active", True)}
    return out


def joueurs():
    """Tous les joueurs connus (le fichier seulement : JAMAIS un appel reseau ici, cette fonction sert a chaque carte).
    La liste est relue par la passe de fond (charger_liste)."""
    return _lire("mlb_joueurs.json").get("joueurs") or {}


def charger_liste(forcer=False):
    """Relit la liste des joueurs (MLB d'abord ; un joueur des mineures qui est aussi en MLB reste MLB). Chaque semaine ;
    apres un echec, on attend 6 h avant de reessayer."""
    d = _lire("mlb_joueurs.json")
    if d.get("joueurs") and not forcer and time.time() - d.get("le", 0) < LISTE_S:
        return d["joueurs"]
    if not forcer and time.time() - _ETAT.get("liste_echec", 0) < 6 * 3600:
        return d.get("joueurs") or {}
    tous = {}
    s = saison()
    for sid in (14, 13, 12, 11, 1):                   # les mineures d'abord : le niveau le plus haut gagne
        for an in (s, s - 1):
            r = _get(f"/sports/{sid}/players", {"season": an})
            if r and r.get("people"):
                for k, v in lire_liste(r["people"], NIVEAUX[sid]).items():
                    if k not in tous or an == s:
                        tous[k] = v
                break
        time.sleep(0.3)
    eq = _get("/teams", {"sportIds": "1,11,12,13,14", "season": s}) or {}
    equipes = {str(t.get("id")): {"abbr": t.get("abbreviation"), "nom": t.get("name"), "niveau": NIVEAUX.get((t.get("sport") or {}).get("id"))}
               for t in eq.get("teams") or [] if t.get("id")}
    if tous:
        _ecrire("mlb_joueurs.json", {"le": time.time(), "saison": s, "joueurs": tous, "equipes": equipes})
        return tous
    _ETAT["liste_echec"] = time.time()
    return d.get("joueurs") or {}


def equipes():
    return _lire("mlb_joueurs.json").get("equipes") or {}


_RE_NOMS = {"le": 0.0, "re": None, "noms": None}


def joueur_du_titre(titre):
    """Le joueur de baseball d'un titre d'annonce (le nom connu le plus long), ou None."""
    J = joueurs()
    if not J:
        return None
    if _RE_NOMS["re"] is None or _RE_NOMS["noms"] is not J:
        noms = sorted((k for k in J if len(k.split()) >= 2), key=len, reverse=True)
        _RE_NOMS.update(re=re.compile(r"\b(" + "|".join(re.escape(k) for k in noms) + r")\b") if noms else None, noms=J)
    if not _RE_NOMS["re"]:
        return None
    m = _RE_NOMS["re"].search(_n(titre))
    return J[m.group(1)] if m else None


# -- la fiche d'un joueur -----------------------------------------------------------------------------------------
TROPHEES = {"mvp": ("most valuable player",), "cy": ("cy young",), "recrue": ("rookie of the year",), "etoile": ("all-star",),
            "gant": ("gold glove",), "baton": ("silver slugger",), "ws": ("world series champion",), "hof": ("hall of fame",)}


def _ip(v):
    """Les manches lancees de la MLB (« 45.2 » = 45 manches et 2 retraits) -> manches."""
    try:
        e, _p, f = str(v or "0").partition(".")
        return int(e or 0) + int(f or 0) / 3
    except ValueError:
        return 0.0


def lire_fiche(p, eqs=None):
    """La reponse /people/{id}?hydrate=... -> la fiche SlabCoach (meme esprit que la fiche LNH). Calcul pur (teste)."""
    if not isinstance(p, dict) or not p.get("id"):
        return None
    eqs = eqs or {}
    par = {}                                            # (saison, groupe) -> lignes
    carriere = {}
    for bloc in p.get("stats") or []:
        typ = ((bloc.get("type") or {}).get("displayName") or "").lower()
        grp = ((bloc.get("group") or {}).get("displayName") or "").lower()
        for sp in bloc.get("splits") or []:
            st = sp.get("stat") or {}
            if typ == "career":
                carriere[grp] = st
                continue
            if typ != "yearbyyear" or (sp.get("sport") or {}).get("id", 1) != 1:
                continue
            par.setdefault((str(sp.get("season")), grp), []).append(sp)
    saisons = {}
    for (s, grp), lignes in par.items():
        tot = [x for x in lignes if not x.get("team")]       # un echange : la ligne sans equipe = le total de la saison
        lignes_t = tot or lignes
        e = saisons.setdefault(s, {"s": int(s), "l": "MLB", "gp": 0, "ab": 0, "hr": 0, "h": 0, "ip": 0.0, "so_l": 0, "er": 0, "equipes": []})
        for x in lignes_t:
            st = x.get("stat") or {}
            if grp == "hitting":
                e["gp"] = max(e["gp"], int(st.get("gamesPlayed") or 0))
                e["ab"] += int(st.get("atBats") or 0)
                e["hr"] += int(st.get("homeRuns") or 0)
                e["h"] += int(st.get("hits") or 0)
                if st.get("ops"):
                    e["ops"] = st.get("ops")
            elif grp == "pitching":
                e["gp"] = max(e["gp"], int(st.get("gamesPlayed") or st.get("gamesPitched") or 0))
                e["ip"] += _ip(st.get("inningsPitched"))
                e["so_l"] += int(st.get("strikeOuts") or 0)
                e["er"] += int(st.get("earnedRuns") or 0)
        for x in lignes:
            t = (x.get("team") or {}).get("name")
            if t and t not in e["equipes"]:
                e["equipes"].append(t)
    par_saison = sorted(saisons.values(), key=lambda e: e["s"])
    for e in par_saison:
        e["ip"] = round(e["ip"], 1)
        e["era"] = round(9 * e["er"] / e["ip"], 2) if e["ip"] else None
    awards = p.get("awards") or []
    tc = {}
    for a in awards:
        nm = str(a.get("name") or "").lower()
        for k, mots in TROPHEES.items():
            if any(m in nm for m in mots) and ("minor" not in nm and "milb" not in nm or k == "hof"):
                tc[k] = tc.get(k, 0) + 1
    dr = (p.get("drafts") or [{}])[-1] if p.get("drafts") else {}
    ct = p.get("currentTeam") or {}
    eq = eqs.get(str(ct.get("id"))) or {}
    pos = (p.get("primaryPosition") or {}).get("abbreviation")
    return {"id": p["id"], "nom": p.get("fullName"), "sport": "baseball", "actif": bool(p.get("active")),
            "equipe": eq.get("abbr") or ct.get("abbreviation"), "equipe_nom": eq.get("nom") or ct.get("name"), "niveau": eq.get("niveau"),
            "pos": pos, "lanceur": pos in ("P", "SP", "RP", "TWP") if pos else None,
            "naissance": str(p.get("birthDate") or "")[:10], "pays": p.get("birthCountry"), "province": p.get("birthStateProvince"),
            "debut": str(p.get("mlbDebutDate") or "")[:10] or None, "chandail": p.get("primaryNumber"),
            "an_repech": dr.get("year") and int(dr["year"]), "ronde": dr.get("pickRound"), "repech": dr.get("pickNumber"),
            "trophees_c": tc, "hof": bool(tc.get("hof")), "saisons": len([e for e in par_saison if e["gp"] > 0]),
            "par_saison": par_saison,
            "equipes": [[e["s"], ", ".join(e["equipes"]), e["gp"]] for e in par_saison],
            "carriere": {"hitting": {k: (carriere.get("hitting") or {}).get(k) for k in ("gamesPlayed", "atBats", "homeRuns", "hits", "avg", "ops")},
                         "pitching": {k: (carriere.get("pitching") or {}).get(k) for k in ("gamesPlayed", "inningsPitched", "wins", "strikeOuts", "era", "saves")}}}


def fiche_api(pid):
    r = _get(f"/people/{int(pid)}", {"hydrate": "currentTeam,awards,draft,stats(group=[hitting,pitching],type=[yearByYear,career])"})
    p = ((r or {}).get("people") or [None])[0]
    return lire_fiche(p, equipes())


def recrue(f, aujourdhui=None):
    """La regle de la MLB : recrue tant qu'il n'a pas depasse 130 presences au baton (AB) ni 50 manches lancees en MLB
    avant cette saison (on ne lit pas les jours sur la liste active, que l'API ne donne pas simplement). Il doit avoir
    joue en MLB cette saison."""
    s = saison(aujourdhui)
    ps = (f or {}).get("par_saison") or []
    avant = [e for e in ps if e.get("s") and e["s"] < s]
    if sum(e.get("ab") or 0 for e in avant) > 130 or sum(e.get("ip") or 0 for e in avant) > 50:
        return False
    return any(e.get("s") == s and (e.get("gp") or 0) > 0 for e in ps)


def prospect(f):
    """Un prospect : pas encore en MLB (ses cartes 1st Bowman sont les plus suivies)."""
    return bool(f) and not (f.get("par_saison") or []) and (f.get("niveau") or "MLB") != "MLB"


# -- les fiches : les joueurs qui se vendent, chaque jour ---------------------------------------------------------
def fiches():
    return _lire("mlb_fiches.json").get("joueurs") or {}


def fiche(nom):
    return fiches().get(_n(nom))


def noms_du_marche(jours=60, n_min=3, max_=600):
    """Les joueurs de baseball qui reviennent dans NOS ventes de baseball (base_ventes_baseball), les plus vendus d'abord."""
    import collections
    import sqlite3
    import base_ventes
    from datetime import datetime, timedelta
    try:
        c = base_ventes._cx("baseball")
        try:
            d = (datetime.now() - timedelta(days=jours)).strftime("%Y-%m-%d")
            titres = [r[0] for r in c.execute("SELECT titre FROM ventes WHERE le >= ? ORDER BY le DESC LIMIT 60000", (d,))]
        finally:
            c.close()
    except sqlite3.Error:
        return []
    cnt = collections.Counter()
    for t in titres:
        j = joueur_du_titre(t)
        if j:
            cnt[_n(j["nom"])] += 1
    return [(k, n) for k, n in cnt.most_common(max_) if n >= n_min]


def passe(n=PAR_PASSE):
    """Une passe : la liste des joueurs (chaque semaine), puis les fiches perimees des joueurs les plus vendus (n au plus)."""
    J = charger_liste()
    d = dict(_lire("mlb_fiches.json") or {})
    F = dict(d.get("joueurs") or {})
    maint = time.time()
    a_lire = [k for k, _c in noms_du_marche() if maint - (F.get(k) or {}).get("le", 0) > FICHE_S][:n]
    lus = 0
    for k in a_lire:
        j = J.get(k)
        if not j:
            continue
        f = fiche_api(j["id"])
        if f:
            f["le"] = maint
            F[k] = f
            lus += 1
        time.sleep(0.25)
    if lus:
        with _verrou:
            _ecrire("mlb_fiches.json", {"le": maint, "joueurs": F})
    _ETAT["derniere"] = {"le": maint, "lus": lus, "joueurs": len(J), "fiches": len(F)}
    return _ETAT["derniere"]


def passe_si_besoin():
    """Appele par la boucle du serveur : une passe par heure au plus, dans un fil a part. LR_MLB=0 pour couper."""
    if _ETAT["en_cours"] or time.time() - _ETAT["le"] < 3500 or os.environ.get("LR_MLB") == "0":
        return False
    _ETAT.update(en_cours=True, le=time.time())

    def tache():
        try:
            print("MLB :", passe(), flush=True)
        except Exception as e:
            print("MLB : " + repr(e), flush=True)
        finally:
            _ETAT["en_cours"] = False
    threading.Thread(target=tache, daemon=True, name="mlb").start()
    return True


def statut():
    import base_ventes
    d = _lire("mlb_joueurs.json")
    return {"joueurs": len(d.get("joueurs") or {}), "fiches": len(fiches()), "ventes": base_ventes.nombre("baseball"),
            "ventes_30j": base_ventes.nombre("baseball", 30), "derniere": _ETAT["derniere"], "erreur": _ETAT["erreur"]}
