"""
LOCKERROOM - les ventes reelles d'un joueur dans un produit (26 oct 2026).

Mathieu : « mettre les ventes moyennes de ce joueur pour montrer sa valeur ; ca doit etre applicable a tous les
joueurs de la meme maniere, ils doivent tous etre evalues sur les memes metriques pour assurer la veracite de nos stats ».

La meme regle pour chaque joueur :
  - UNE recherche SoldComps « saison produit joueur » (gardee 3 jours par vendues : pas de cout de plus ensuite) ;
  - on garde les ventes de SES cartes de CE produit : son nom de famille dans le titre, la bonne saison, pas un autre
    produit (MVP, SP Authentic...), pas un lot, pas une carte a plusieurs joueurs ;
  - cartes NON gradees seulement (une PSA 10 n'est pas la carte que tu tires dans un break) : les gradees sont comptees
    a part ;
  - chaque vente est classee avec les memes categories que les chances (calcul.CATEGORIES_HIT) : numerotee, auto, patch,
    auto-patch, SSP ; le reste = « autres cartes » (base, recrues, inserts) ;
  - par categorie : nombre de ventes, moyenne, mediane. Moins de 3 ventes : affiche, mais marque « peu de ventes ».
"""
import re
import statistics
import unicodedata

import calcul

AUTRES_PRODUITS = ["mvp", "sp authentic", "sp game used", "black diamond", "artifacts", "allure", "synergy", "o-pee-chee",
                   "opc", "credentials", "trilogy", "premier", "the cup", "spx", "extended", "series 2", "series two",
                   "tim hortons", "chronology", "engrained", "ultimate collection", "fleer", "skybox", "metal universe",
                   "hockey card day", "parkhurst", "stature", "biography", "ice", "chrome", "o pee chee", "heroes",
                   "team canada", "world of juniors", "spgu", "sp signature"]
_RE_NUM = re.compile(r"(?:#\s*'?d|\bnumbered\b|\bserial\b|(?<![\d-])(?:\d{1,4}\s?)?/\s?\d{1,4}\b|\b1\s?of\s?1\b)", re.I)
_RE_SAISON_SLASH = re.compile(r"\b(19|20)\d{2}\s?/\s?\d{2}\b")
_RE_AUTO = re.compile(r"\bauto(graph|graphs|graphed)?s?\b|\bsigned\b|\bsignatures?\b|\bink\b", re.I)
_RE_PATCH = re.compile(r"\bpatch|\bjersey|\brelics?\b|\bmemorabilia|\bswatch|\bgame[- ]used|\bgame[- ]worn|\bmaterials?\b|\bfabrics?\b", re.I)
_RE_SSP = re.compile(r"\bssp\b|super short", re.I)


def _plat(t):
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9/#'&-]+", " ", t).split())


def categories_titre(titre):
    """Les categories d'une vente, d'apres son titre (memes noms que calcul.categories_carte)."""
    t = _RE_SAISON_SLASH.sub(" ", str(titre or ""))
    out = set()
    if _RE_NUM.search(t):
        out.add("numerotee")
    a, p = bool(_RE_AUTO.search(t)), bool(_RE_PATCH.search(t))
    if a:
        out.add("auto")
    if p:
        out.add("patch")
    if a and p:
        out.add("auto_patch")
    if _RE_SSP.search(t):
        out.add("ssp")
    return out


def _mots_produit(prod):
    """Les mots qui nomment CE produit (« series 1 ») et les noms de ses sous-ensembles (« young guns », « canvas »)."""
    nom = _plat(re.sub(r"^\d{4}-\d{2}\s+", "", prod.get("nom") or ""))
    marque = _plat(prod.get("marque") or "")
    propre = " ".join(w for w in nom.split() if w not in marque.split()).strip()
    sous = set()
    for s in prod.get("sous_ensembles") or []:
        n = _plat(re.sub(r"\b(parallel|set|variations?|inserts?)\b", " ", s.get("nom") or "", flags=re.I))
        if len(n) >= 4:
            sous.add(n)
    return propre, sous


def _saisons(prod):
    s = str(prod.get("saison") or "")
    m = re.match(r"(\d{4})-(\d{2})", s)
    if not m:
        return [s.lower()] if s else []
    return [f"{m.group(1)}-{m.group(2)}", f"{m.group(1)}/{m.group(2)}", f"{m.group(1)[2:]}-{m.group(2)}", f"{m.group(1)}-20{m.group(2)}", m.group(1)]


def de_ce_produit(prod, joueur, titre):
    """True si la vente est une carte de `joueur` dans `prod` (et une carte seule)."""
    import cartes_match
    t = re.sub(r"\bseries one\b", "series 1", re.sub(r"\bseries two\b", "series 2", _plat(titre)))
    fam = _plat(joueur).split()
    if not fam or fam[-1] not in t.split():
        return False
    if not any(s in t for s in _saisons(prod)):
        return False
    if any(re.search(x, t) for x in cartes_match.EXCLUS):
        return False
    propre, sous = _mots_produit(prod)
    if propre and propre in t:
        return True
    if any(re.search(r"\b" + re.escape(x) + r"\b", t) for x in AUTRES_PRODUITS if x not in propre):
        return False
    return any(x in t for x in sous)


def _resume(prix):
    if not prix:
        return {"n": 0, "moyenne": None, "mediane": None}
    return {"n": len(prix), "moyenne": round(sum(prix) / len(prix), 2), "mediane": round(statistics.median(prix), 2),
            "min": round(min(prix), 2), "max": round(max(prix), 2), "peu": len(prix) < 3}


def requete(prod, joueur):
    return " ".join(f"{prod.get('nom') or ''} {joueur}".split())[:120]


def ventes(prod, joueur, rechercher=None):
    """-> {ok, joueur, n, moyenne, mediane, par_cat: {cat: resume}, autres: resume, gradees, depuis, jusqu, exemples}."""
    import cartes_match
    import vendues
    rechercher = rechercher or vendues.rechercher
    noms = [x.strip() for x in str(joueur or "").split("/") if x.strip()]
    if len(noms) != 1:
        return {"ok": False, "erreur": "un joueur à la fois"}
    j = noms[0]
    r = rechercher(requete(prod, j), fond=False)
    brut = r.get("ventes") or []
    garde, gradees = [], 0
    for v in brut:
        if not v.get("prix") or not de_ce_produit(prod, j, v.get("titre")):
            continue
        if cartes_match._RE_GRADE.search(_plat(v.get("titre"))) and re.search(r"\b(psa|bgs|sgc|cgc|beckett)\b", _plat(v.get("titre"))):
            gradees += 1
            continue
        garde.append(v)
    garde.sort(key=lambda v: str(v.get("le") or ""), reverse=True)
    par = {c: [] for c in calcul.CATEGORIES_HIT}
    hits, autres = [], []
    for v in garde:
        cats = categories_titre(v["titre"])
        for c in cats:
            par[c].append(float(v["prix"]))
        (hits if cats else autres).append(float(v["prix"]))
    tous = [float(v["prix"]) for v in garde]
    dates = [str(v.get("le") or "")[:10] for v in garde if v.get("le")]
    return {"ok": True, "joueur": j, **_resume(tous), "par_cat": {c: _resume(l) for c, l in par.items()},
            "hit": _resume(hits), "autres": _resume(autres), "gradees": gradees,
            "depuis": min(dates) if dates else None, "jusqu": max(dates) if dates else None,
            "erreur": r.get("erreur") if not garde else None, "cache": bool(r.get("cache")),
            "exemples": [{"titre": v.get("titre"), "prix": v.get("prix"), "le": v.get("le"), "url": v.get("url"), "photo": v.get("photo"),
                          "cats": sorted(categories_titre(v["titre"]))} for v in garde[:8]]}
