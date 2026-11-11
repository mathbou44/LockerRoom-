"""
SLABCOACH - la forme des joueurs de la LNH (28 oct 2026, Mathieu : « ok go »).

Une serie de points fait souvent monter le prix d'une recrue : quand un joueur dont les cartes se vendent dans SlabCoach
connait un gros debut de semaine, l'app donne un indice (« Psst… 8 points a ses 5 derniers matchs »), sans rien affirmer.

Source : les adresses publiques du site de la LNH (non documentees officiellement, voir github.com/Zmalski/NHL-API-Reference) :
  https://search.d3.nhle.com/api/v1/search/player?culture=en-us&limit=5&q={nom}   -> playerId
  https://api-web.nhle.com/v1/player/{playerId}/landing                          -> last5Games (buts, passes, points)
Usage leger et poli : au plus LR_NHL_PAR_HEURE joueurs par heure (4), chaque joueur relu au plus aux 12 h, tout est garde.
Rien d'autre n'est copie (pas de photos, pas de logos de la LNH). LR_NHL=0 coupe tout.
"""
import json
import os
import re
import threading
import time
import unicodedata
import urllib.parse
import urllib.request

GARDE_S = 6 * 3600                 # 10 nov 2026 : 12 h -> 6 h (« tout ce qui est vivant » : les matchs du soir, vus le matin)
_verrou = threading.Lock()
_ETAT = {"le": 0.0}


def actif():
    return os.environ.get("LR_NHL", "1") != "0"


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "nhl_forme.json")


def _lire():
    try:
        with open(_chemin(), encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def _ecrire(d):
    p = _chemin()
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(d, f)
    os.replace(p + ".tmp", p)


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]+", "", s).strip()


def _get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "SlabCoach/1.0 (+https://www.slabcoach.com)"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read() or b"null")
    except Exception:
        return None


def _id(nom):
    l = _get("https://search.d3.nhle.com/api/v1/search/player?" + urllib.parse.urlencode({"culture": "en-us", "limit": 5, "q": nom}))
    if not isinstance(l, list):
        return None
    n = _norm(nom)
    for x in l:
        if isinstance(x, dict) and _norm(x.get("name")) == n and str(x.get("active", True)).lower() != "false":
            return str(x.get("playerId") or "") or None
    return None


def _nom_de(d):
    v = lambda k: (d.get(k) or {}).get("default") if isinstance(d.get(k), dict) else d.get(k)
    return " ".join(x for x in (v("firstName"), v("lastName")) if x)


def forme(nom, maintenant=None):
    """5 derniers matchs d'un joueur actif -> {joueur, matchs, buts, passes, points, dernier} ou None (garde 12 h)."""
    if not actif() or not nom:
        return None
    t = maintenant or time.time()
    cle = _norm(nom)
    with _verrou:
        d = _lire()
    g = (d.get("joueurs") or {}).get(cle)
    if g and t - g.get("le", 0) < GARDE_S:
        return g.get("f")
    pid = (g or {}).get("id") or _id(nom)
    f = None
    if pid:
        land = _get(f"https://api-web.nhle.com/v1/player/{pid}/landing")
        if isinstance(land, dict):
            l5 = [m for m in land.get("last5Games") or [] if isinstance(m, dict)]
            if l5:
                s = lambda k: sum(int(m.get(k) or 0) for m in l5)
                f = {"joueur": _nom_de(land) or nom, "matchs": len(l5), "buts": s("goals"), "passes": s("assists"), "points": s("points"),
                     "dernier": max(str(m.get("gameDate") or "") for m in l5)}
    with _verrou:
        d = _lire()
        d.setdefault("joueurs", {})[cle] = {"le": t, "id": pid, "f": f}
        _ecrire(d)
    return f


def rafraichir(noms, n=None):
    """Quelques joueurs par heure (les moins frais d'abord)."""
    try:
        n = int(n or os.environ.get("LR_NHL_PAR_HEURE") or 4)
    except ValueError:
        n = 4
    j = (_lire().get("joueurs") or {})
    a_faire = sorted({x for x in noms if x}, key=lambda x: (j.get(_norm(x)) or {}).get("le", 0))[:n]
    return sum(1 for x in a_faire if forme(x) is not None)


def rafraichir_si_besoin():
    """Chaque heure : les joueurs des tendances (hausses et plus vendues) de la base des ventes."""
    if not actif() or time.time() - _ETAT["le"] < 3500:
        return 0
    _ETAT["le"] = time.time()
    try:
        import base_ventes
        t = base_ventes.tendances() or {}
        noms = [x.get("joueur") for k in ("hausses", "plus_vendues") for x in (t.get(k) or [])[:8]]
        return rafraichir(noms)
    except Exception as e:
        print("LNH : " + repr(e), flush=True)
        return 0


def en_feu(min_points=7, maintenant=None):
    """Le joueur le plus chaud (5 derniers matchs, joues dans les 10 derniers jours), ou None."""
    t = maintenant or time.time()
    lim = time.strftime("%Y-%m-%d", time.localtime(t - 10 * 86400))
    l = [g["f"] for g in (_lire().get("joueurs") or {}).values() if g.get("f") and g["f"]["dernier"] >= lim
         and (g["f"]["points"] >= min_points or g["f"]["buts"] >= 5)]
    return max(l, key=lambda f: (f["points"], f["buts"])) if l else None


def chauds(min_points=6, maintenant=None):
    """28 oct 2026 : tous les joueurs en feu (5 derniers matchs, joues dans les 10 derniers jours), du plus chaud au moins."""
    t = maintenant or time.time()
    lim = time.strftime("%Y-%m-%d", time.localtime(t - 10 * 86400))
    l = [g["f"] for g in (_lire().get("joueurs") or {}).values() if g.get("f") and g["f"]["dernier"] >= lim
         and (g["f"]["points"] >= min_points or g["f"]["buts"] >= 4)]
    return sorted(l, key=lambda f: (-f["points"], -f["buts"]))


# -- 13 nov 2026 (Mathieu : « on devrait TOUJOURS avoir toute l'info » : la fiche d'un joueur retraite, Terry Ruskowski, etait
# vide) : la carriere LNH de N'IMPORTE QUEL joueur (actif ou retraite) et quelques lignes de sa biographie (Wikipedia, texte
# seulement, source citee). Des faits publics ; jamais une photo ni un logo. Garde 7 jours.
GARDE_CARRIERE_S = 7 * 86400
_ABREGES = {"bap", "ud", "opc", "spx", "sp", "rc", "au", "auto", "psa", "bgs", "sgc", "cgc", "yg", "rookie", "card", "cards", "lot",
            "mint", "gem", "nm", "mt", "nhl", "hockey", "jersey", "patch", "the", "cup", "parkhurst", "topps", "panini", "fleer"}


def nom_propre(nom):
    """« Alexei Semenov BAP » -> « Alexei Semenov » : les mots de set ou de vendeur colles au nom sont retires."""
    m = [x for x in re.split(r"\s+", str(nom or "").strip()) if x]
    while len(m) > 2 and (_norm(m[-1]) in _ABREGES or re.fullmatch(r"[#/\d.-]+", m[-1])):
        m.pop()
    while len(m) > 2 and _norm(m[0]) in _ABREGES:
        m.pop(0)
    return " ".join(m)


def _chercher(nom):
    """Le joueur, actif ou retraite : {id, nom}. Le nom complet d'abord ; la recherche de la LNH classe mal les noms
    courants (« Alexei Semenov » ne sort pas) : alors son nom de famille, et le prenom qui commence pareil."""
    n = _norm(nom)
    mots = n.split()
    for q in (nom, mots[-1] if mots else nom):
        l = _get("https://search.d3.nhle.com/api/v1/search/player?" + urllib.parse.urlencode({"culture": "en-us", "limit": 20, "q": q}))
        if not isinstance(l, list):
            continue
        l = [x for x in l if isinstance(x, dict) and x.get("playerId")]
        ex = [x for x in l if _norm(x.get("name")) == n]
        if not ex and len(mots) >= 2:
            ex = [x for x in l if _norm(x.get("name")).split()[-1:] == mots[-1:] and _norm(x.get("name"))[:3] == n[:3]]
        if len(ex) >= 1:
            return {"id": str(ex[0]["playerId"]), "nom": ex[0].get("name") or nom}
    return None


def _wiki(nom):
    for lang, titre in (("en", nom), ("en", nom + " (ice hockey)"), ("en", nom + " (ice hockey, born 1981)")):
        d = _get(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(titre.replace(" ", "_")))
        if isinstance(d, dict) and d.get("type") == "standard" and re.search(r"hockey", (d.get("description") or "") + (d.get("extract") or ""), re.I):
            phr = re.split(r"(?<=[.!?])\s+", str(d.get("extract") or "").strip())
            return {"texte": " ".join(phr[:3])[:600], "lien": ((d.get("content_urls") or {}).get("desktop") or {}).get("page"), "langue": lang}
    return None


def carriere(nom, maintenant=None):
    """-> {nom, actif, position, ne_le, lieu, equipe, saisons: [debut, fin], mj, buts, passes, points, (gardien : victoires,
    moyenne, efficacite), temple, repechage, bio: {texte, lien}} ou None."""
    if not actif() or not nom:
        return None
    t = maintenant or time.time()
    nom = nom_propre(nom)
    cle = "c:" + _norm(nom)
    with _verrou:
        d = _lire()
    g = (d.get("carrieres") or {}).get(cle)
    if g and t - g.get("le", 0) < GARDE_CARRIERE_S:
        return g.get("c")
    j = _chercher(nom)
    c = None
    if j:
        land = _get(f"https://api-web.nhle.com/v1/player/{j['id']}/landing")
        if isinstance(land, dict):
            v = lambda o, k: (o.get(k) or {}).get("default") if isinstance(o.get(k), dict) else o.get(k)
            tot = ((land.get("careerTotals") or {}).get("regularSeason")) or {}
            saisons = sorted({int(s.get("season")) for s in land.get("seasonTotals") or [] if s.get("leagueAbbrev") == "NHL" and s.get("gameTypeId") == 2 and s.get("season")})
            equipes = [v(s, "teamName") for s in land.get("seasonTotals") or [] if s.get("leagueAbbrev") == "NHL" and s.get("gameTypeId") == 2]
            pos = land.get("position")
            dr = land.get("draftDetails") or {}
            c = {"nom": _nom_de(land) or j["nom"], "actif": bool(land.get("isActive")), "position": pos,
                 "ne_le": land.get("birthDate"), "lieu": ", ".join(x for x in (v(land, "birthCity"), v(land, "birthStateProvince"), land.get("birthCountry")) if x),
                 "equipe": v(land, "fullTeamName") or (equipes[-1] if equipes else None), "equipes": list(dict.fromkeys(e for e in equipes if e))[:8],
                 "saisons": [str(saisons[0])[:4], str(saisons[-1])[4:]] if saisons else None,
                 "mj": tot.get("gamesPlayed"), "temple": bool(land.get("inHHOF")),
                 "repechage": {"an": dr.get("year"), "rang": dr.get("overallPick"), "equipe": dr.get("teamAbbrev")} if dr.get("year") else None}
            if pos == "G":
                c.update(victoires=tot.get("wins"), moyenne=tot.get("goalsAgainstAvg"), efficacite=tot.get("savePctg"), blanchissages=tot.get("shutouts"))
            else:
                c.update(buts=tot.get("goals"), passes=tot.get("assists"), points=tot.get("points"))
    if c is not None or j is None:
        b = _wiki((c or {}).get("nom") or nom)
        if b:
            c = dict(c or {"nom": nom}, bio=b)
    with _verrou:
        d = _lire()
        d.setdefault("carrieres", {})[cle] = {"le": t, "c": c}
        if len(d["carrieres"]) > 3000:
            d["carrieres"] = dict(sorted(d["carrieres"].items(), key=lambda kv: kv[1].get("le", 0))[-2500:])
        _ecrire(d)
    return c
