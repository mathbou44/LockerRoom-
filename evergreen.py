"""
SLABCOACH - les joueurs « evergreen » (16 nov 2026).

Mathieu : « les gens qui investissent vont dans des joueurs evergreen : deja au Temple, des retraites ou des joueurs
exceptionnels qui jouent encore (Crosby, Ovechkin, Patrick Kane, tres longtemps dans le gros marche de Chicago ; Datsyuk,
tres longtemps avec Detroit). Des joueurs populaires pour l'achat de grosses cartes pour des collections. Il faut etre sur de
les voir ; ajouter des variables a SlabIQ, sans ajouter de complexite a l'utilisateur. »

Un score 0-100 par joueur, presque immobile (une carriere ne change pas d'une semaine a l'autre), sur des faits publics (fiche
LNH : Temple, top 100, coupes, trophees, matchs, points par match, saisons avec la meme franchise et la taille de son marche)
et nos propres donnees (la notoriete, la demande et la communaute de l'Indice SlabIQ). Evergreen = 60 et plus.
Il sert dans SlabIQ (score_slab) : la raison « Long terme » d'une grosse carte d'un evergreen, et un plancher pour elle
(regle par la boucle de l'expert, slabiq_expert). L'utilisateur ne voit qu'une raison, derriere le « ? » du score.
"""
import math
import time

SEUIL = 60
# 18 nov 2026 (Mathieu : « McDavid ? Ovechkin ? Kane ? il y en a d'autres, c'est sur ») : les evergreen du hobby, toujours dans la
# liste meme si une fiche publique manque (un joueur absent de la base n'avait aucun score) ; plancher 75
EVERGREEN_HOBBY = (
    # en activite (ou tout juste retires), carrieres de vedette
    "Connor McDavid", "Sidney Crosby", "Alex Ovechkin", "Patrick Kane", "Evgeni Malkin", "Nathan MacKinnon", "Auston Matthews",
    "Leon Draisaitl", "Nikita Kucherov", "Steven Stamkos", "Jonathan Toews", "Marc-Andre Fleury", "Carey Price", "Anze Kopitar",
    "Brad Marchand", "Patrice Bergeron", "Henrik Lundqvist", "Andrei Vasilevskiy", "Victor Hedman", "Erik Karlsson", "Drew Doughty",
    "Cale Makar", "Connor Bedard", "Macklin Celebrini",
    # legendes
    "Wayne Gretzky", "Mario Lemieux", "Bobby Orr", "Gordie Howe", "Maurice Richard", "Jean Beliveau", "Guy Lafleur", "Patrick Roy",
    "Martin Brodeur", "Jaromir Jagr", "Steve Yzerman", "Joe Sakic", "Mark Messier", "Ray Bourque", "Nicklas Lidstrom",
    "Pavel Datsyuk", "Teemu Selanne", "Peter Forsberg", "Brett Hull", "Bobby Hull", "Mike Bossy", "Dominik Hasek", "Paul Kariya",
    "Martin St. Louis", "Joe Thornton", "Jarome Iginla", "Ken Dryden", "Terry Sawchuk", "Stan Mikita", "Phil Esposito",
)
_CACHE = {"t": 0.0, "d": None}


def _faits(nom):
    try:
        import demande_legale as dl
        base = (dl.lire() or {}).get("joueurs") or {}
        e = base.get(nom) or base.get(next((k for k in base if dl._norm(k) == dl._norm(nom)), ""), {})
        return (e or {}).get("nhl") or {}
    except Exception:
        return {}


def score_de(h, crit=None):
    """(score 0-100, raisons) d'un joueur : h = sa fiche LNH (demande_legale), crit = ses criteres de l'Indice (0-100)."""
    h, crit = h or {}, crit or {}
    s, r = 0.0, []
    if h.get("hhof"):
        s += 25
        r.append("temple")
    if h.get("top100"):
        s += 10
        if "temple" not in r:
            r.append("top100")
    tc = h.get("trophees_c") or {}
    coupes = int(tc.get("Stanley Cup") or 0)
    if coupes:
        s += min(10.0, 4.0 * coupes)
        r.append("coupes")
    try:
        import indice_joueurs
        tp = indice_joueurs.TROPHEES_POIDS
    except Exception:
        tp = {}
    tw = sum(tp.get(k, 0.6) * int(n or 0) for k, n in tc.items() if k != "Stanley Cup")
    if tw:
        s += min(10.0, 3.0 * math.log1p(tw))
    hart = int(tc.get("Hart Memorial Trophy") or 0)          # le joueur le plus utile : une vedette de son epoque
    if hart:
        s += min(12.0, 6.0 * hart)
        r.append("vedette")
    car = h.get("carriere") or {}
    gp, pts = int(car.get("gamesPlayed") or 0), int(car.get("points") or 0)
    if gp >= 1000:
        s += 12
        r.append("longevite")
    elif gp >= 800:
        s += 8
    elif gp >= 600:
        s += 4
    if gp >= 300 and h.get("pos") != "G":
        ppg = pts / gp
        s += 8 if ppg >= 1.0 else 5 if ppg >= 0.8 else 2 if ppg >= 0.6 else 0
    try:
        import score_modele as sm
        fi = sm.fidelite(h.get("equipes") or [])
        marche = sm.MARCHES.get(fi[0], 0) if fi else 0
    except Exception:
        fi, marche = None, 0
    if fi and fi[2] >= 10 and fi[1] >= 0.6:
        s += 14 if fi[2] >= 15 else 10
        r.append("fidele")
        if marche >= 2:
            s += 2 * marche
            r.append("gros_marche")
    s += 0.08 * float(crit.get("notoriete") or 0) + 0.06 * float(crit.get("demande") or 0) + 0.03 * float(crit.get("communaute") or 0)
    if float(crit.get("notoriete") or 0) >= 80 or float(crit.get("demande") or 0) >= 80:
        r.append("populaire")
    return round(min(100.0, s), 1), r


def tous():
    """{nom: {score, raisons}} des joueurs connus (garde 6 h)."""
    if _CACHE["d"] is not None and time.time() - _CACHE["t"] < 6 * 3600:
        return _CACHE["d"]
    out = {}
    try:
        import demande_legale as dl
        import indice_joueurs
        base = (dl.lire() or {}).get("joueurs") or {}
        I = indice_joueurs.lire().get("indice") or {}
        for nom, e in base.items():
            sc, r = score_de((e or {}).get("nhl") or {}, (I.get(nom) or {}).get("criteres") or {})
            if sc >= 35:
                out[nom] = {"score": sc, "raisons": r}
    except Exception:
        pass
    for nom in EVERGREEN_HOBBY:
        k = next((x for x in out if x.lower() == nom.lower()), nom)
        v = out.get(k) or {"score": 0.0, "raisons": []}
        if v["score"] < 75:
            v = {"score": 75.0, "raisons": list(dict.fromkeys((v.get("raisons") or []) + ["hobby"]))}
        out[k] = v
    _CACHE.update(t=time.time(), d=out)
    return out


def de(nom):
    """{score, raisons, evergreen} d'un joueur, ou None."""
    if not nom:
        return None
    T = tous()
    v = T.get(nom) or next((x for k, x in T.items() if k.lower() == str(nom).lower()), None)
    if v is None:
        h = _faits(nom)
        if not h:
            return None
        sc, r = score_de(h)
        v = {"score": sc, "raisons": r}
    return {**v, "evergreen": v["score"] >= SEUIL}


def liste(n=150):
    """Les evergreen, du plus fort au plus faible (pour la validation de l'admin)."""
    return sorted(({"nom": k, **v} for k, v in tous().items() if v["score"] >= SEUIL), key=lambda x: -x["score"])[:n]
