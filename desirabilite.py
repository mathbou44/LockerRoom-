"""
SLABCOACH - le score de desirabilite d'une carte, de 0 a 100 (31 oct 2026).

Mathieu : « faire la difference entre un inventaire a vendre rapidement et un inventaire de collection. La collection, tu
achetes avec une autre mentalite : plus rare, plus de desirability, les cartes que le monde recherche mais qui ne sortent
jamais ; tu gardes plus longtemps ».

Quatre morceaux, chacun explique a l'utilisateur :
  rarete (0-40)  : le tirage (1/1, /5, /10, /25...), SP / SSP / variation, inscription, auto, patch, gradation haute ;
  marche (0-15)  : 31 oct 2026 (Mathieu : « la rarete, c'est aussi le nombre de fois qu'elle s'est vendue ; le pop count
                   aussi ») : combien de copies de CETTE carte (meme version, meme gradation) se sont vendues dans les
                   ventes que SlabCoach connait (eBay garde 90 jours ; notre base garde tout depuis son debut). Une carte
                   qui ne passe presque jamais est rare sur le marche. Inconnu : 5 (neutre).
                   Le « pop count » de PSA n'est PAS utilise : l'entente de l'API PSA interdit ses donnees dans une app
                   payante. Les copies gradees vues en vente (meme gradation) en tiennent lieu, avec nos propres donnees ;
  joueur (0-30)  : la demande du joueur (l'indice de SlabCoach, mesure sur ses ventes reelles) ;
  valeur (0-15)  : ce que la carte vaut (une carte de 1 000 $ est recherchee par definition).
Aucune promesse de hausse : le score dit ce qui est RARE et RECHERCHE aujourd'hui, pas ce qui va monter.
"""
import re

_RE_SSP = re.compile(r"\bssp\b|case hit|super short|\bsspv?\b", re.I)
_RE_SP = re.compile(r"\bsp\b|short print|variation|photo variant|design variant", re.I)
_RE_INSC = re.compile(r"inscri|[\"“”«][^\"“”»]{2,30}[\"“”»]", re.I)


def _rarete(dc, titre, carte):
    pts, raisons = 0, []
    s = dc.get("serie")
    try:
        s = int(s) if s is not None else (int(carte.get("tirage")) if carte and str(carte.get("tirage") or "").isdigit() else None)
    except (TypeError, ValueError):
        s = None
    if s:
        for lim, p in ((1, 45), (5, 40), (10, 35), (25, 28), (50, 22), (99, 16), (250, 9), (999, 4)):
            if s <= lim:
                pts += p
                raisons.append("1/1" if s == 1 else f"/{s}")
                break
    tsp = re.sub(r"\bsp\s*(authentic|game used|signature|legendary|premier)\b|\bspx\b", " ", titre, flags=re.I)
    if _RE_SSP.search(tsp):
        pts += 12
        raisons.append("SSP")
    elif _RE_SP.search(tsp):
        pts += 6
        raisons.append("SP")
    if _RE_INSC.search(titre):
        pts += 6
        raisons.append("inscription")
    auto = dc.get("auto") or bool(carte and carte.get("auto"))
    if auto and dc.get("patch"):
        pts += 14
        raisons.append("auto patch")
    elif auto:
        pts += 10
        raisons.append("auto")
    elif dc.get("patch"):
        pts += 6
        raisons.append("patch")
    g = dc.get("grade") or {}
    note = str(g.get("note") or "")
    if note in ("10", "9.5") or (carte and re.search(r"\b(psa|sgc)\s*10\b|\bbgs\s*(9\.5|10)\b", str(carte.get("grade") or ""), re.I)):
        pts += 5
        raisons.append("gradée " + (f"{g.get('cie', '').upper()} {note}".strip() if note else "haute"))
    return min(40, pts), raisons


def _joueur(j):
    import valeurs
    if not j or not valeurs.connu(j):
        return 5, None
    d = valeurs.demande(j)
    for lim, p in ((8, 30), (5, 26), (3, 21), (1.5, 15), (0.8, 9)):
        if d >= lim:
            return p, ("vedette" if p >= 26 else "joueur recherché" if p >= 15 else None)
    return 5, None


def _marche(n, jours=None):
    """Combien de ventes de la meme carte, dans la periode connue -> (points 0-15, raison)."""
    if n is None:
        return 5, None
    j = int(jours or 90)
    per = f"{j} j" if j < 365 else f"{round(j / 365)} an" + ("s" if j >= 730 else "")
    if n <= 1:
        return 15, f"presque jamais en vente ({n} vente{'s' if n > 1 else ''} en {per})"
    if n <= 3:
        return 11, f"rare en vente ({n} ventes en {per})"
    if n <= 7:
        return 7, None
    if n <= 15:
        return 3, None
    return 0, "se vend souvent"


def ventes_connues(titre):
    """Les ventes de CETTE carte que SlabCoach connait sans rien payer : la base des ventes (gardee depuis son debut) et le
    cache des recherches (3 jours). -> (nombre, jours couverts) ou None si on n'a aucune donnee pour cette carte."""
    import base_ventes
    import cartes_match
    import vendues
    from datetime import datetime
    cib = cartes_match.cible_titre(titre or "")
    q = (cartes_match.requete_ebay(cib) or "").strip()
    if not q:
        return None
    l, vus = [], set()
    try:
        c = base_ventes._cx()
        try:
            l += [{"titre": t, "le": le, "url": u} for t, le, u in c.execute("SELECT titre, le, url FROM ventes WHERE q=?", (q,))]
        finally:
            c.close()
    except Exception:
        pass
    cache = vendues.en_cache(q)
    if cache is None and not l:
        return None
    l += [{"titre": v.get("titre"), "le": v.get("le"), "url": v.get("url")} for v in cache or []]
    n, plus_vieux = 0, None
    for v in l:
        k = v.get("url") or f"{v.get('titre')}|{v.get('le')}"
        if k in vus or cartes_match.raisons_refus(cib, v.get("titre") or ""):
            continue
        vus.add(k)
        n += 1
        if v.get("le") and (plus_vieux is None or str(v["le"]) < plus_vieux):
            plus_vieux = str(v["le"])[:10]
    try:
        jours = max(90, (datetime.now() - datetime.fromisoformat(plus_vieux)).days) if plus_vieux else 90
    except ValueError:
        jours = 90
    return n, jours


def _valeur(v):
    try:
        v = float(v or 0)
    except (TypeError, ValueError):
        return 0
    for lim, p in ((1000, 15), (400, 12), (150, 9), (50, 6), (20, 3)):
        if v >= lim:
            return p
    return 0


def score(titre="", joueur=None, valeur=None, carte=None, ventes=None, jours=None):
    """-> {"score": 0-100, "rarete", "marche", "joueur", "valeur", "raisons": [...]}
    ventes : combien de ventes de la meme carte (None = inconnu) ; jours : la periode couverte."""
    import cartes_match
    t = str(titre or "")
    if carte:
        extra = " ".join(str(carte.get(k) or "") for k in ("parallele", "grade"))
        if carte.get("tirage") and "/" not in t:
            extra += f" /{carte['tirage']}"
        t = (t + " " + extra).strip()
    dc = cartes_match._decoder_memo(t) if t else {}
    r, raisons = _rarete(dc, t, carte)
    j = joueur or (carte or {}).get("joueur") or cartes_match.joueur_du_titre(t)
    pj, rj = _joueur(j)
    if rj:
        raisons.append(rj)
    pm, rm = _marche(ventes, jours)
    if rm:
        raisons.append(rm)
    pv = _valeur(valeur if valeur is not None else (carte or {}).get("valeur"))
    return {"score": int(min(100, r + pm + pj + pv)), "rarete": r, "marche": pm, "joueur": pj, "valeur": pv, "raisons": raisons[:5]}
