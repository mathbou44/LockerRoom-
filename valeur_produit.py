"""
LOCKERROOM - la valeur des cartes d'un produit, mesuree sur les VENTES reelles (25 oct 2026).

Mathieu : « pour la Series 1 2026-27, Boston a James Hagens, il vaut cher, l'equipe se vend donc plus cher
dans un break que Dallas qui n'a pas de bonnes recrues » et « base-toi toujours sur les last sold ».

Pour chaque produit : quelques recherches de ventes (SoldComps, 240 ventes chacune) sur ses sous-ensembles
qui comptent (Young Guns, Canvas Young Guns, autos, patchs...) ; chaque vente est rattachee au joueur de la
checklist (nom de famille + memes mots + meme annee, cartes_match) ; mediane par joueur et par sous-ensemble.
Aussi le prix d'une boite (ventes de boites scellees). Garde 7 jours (DONNEES/valeurs_produits.json).
Budget : environ 4 a 6 recherches par produit et par semaine.
"""
import json
import os
import re
import statistics
import threading
import time
from datetime import datetime

FRAICHEUR_S = 7 * 86400
MAX_SOUS = 8                    # sous-ensembles mesures par produit (les plus importants)
_verrou = threading.Lock()
_EN_COURS = set()


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "valeurs_produits.json")


_CACHE = {"mt": None, "d": {}}


def lire():
    """26 oct 2026 : en memoire tant que le fichier ne change pas (lu des milliers de fois par analyse de break :
    le relire a chaque carte rendait l'ecran tres lent en ligne, jusqu'a l'erreur du serveur)."""
    import time as _t
    if _CACHE.get("vu") and _t.time() - _CACHE["vu"] < 2.0 and _CACHE["mt"] is not None:
        return _CACHE["d"]           # 28 oct 2026 (vitesse) : la date du fichier regardee au plus toutes les 2 s (avant : ~26 000 fois)
    _CACHE["vu"] = _t.time()
    try:
        mt = os.path.getmtime(_chemin())
    except OSError:
        return {}
    if _CACHE["mt"] != mt:
        try:
            with open(_chemin(), encoding="utf-8") as f:
                _CACHE.update(mt=mt, d=json.load(f) or {})
        except (OSError, ValueError):
            return _CACHE["d"]
    return _CACHE["d"]


def _ecrire(d):
    tmp = _chemin() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, _chemin())


def de(pid):
    """{"maj", "boite", "sous": {nom: {"mediane", "n", "joueurs": {joueur: {"m", "n"}}}}} ou {}."""
    return (lire().get(pid) or {})


def _importants(prod):
    """Les sous-ensembles qui font la valeur d'un break : recrues de base, autos, patchs (les plus frequents d'abord)."""
    se = prod.get("sous_ensembles") or []
    rang = {"recrue": 0, "auto_memo": 1, "auto": 2, "memo": 3, "insert": 5, "base": 6}
    choix = [s for s in se if (s.get("groupe") in ("recrue", "auto", "memo", "auto_memo")) and not s.get("tirage")
             and not re.search(r"printing plate|oversized|1/1", s["nom"], re.I)]
    choix.sort(key=lambda s: (rang.get(s.get("groupe"), 9), -(s.get("par_boite") or 0)))
    return choix[:MAX_SOUS]


def _court(prod):
    """« 2026-27 Upper Deck Series 1 » -> (« 2026-27 », « upper deck »)."""
    saison = str(prod.get("saison") or (re.search(r"(19|20)\d{2}(-\d{2})?", prod.get("nom") or "") or [""])[0])
    marque = str(prod.get("marque") or "").lower()
    return saison, marque


def recrues_du_produit(prod):
    se = {s["nom"]: s for s in prod.get("sous_ensembles") or []}
    return sorted({c["joueur"] for c in prod.get("cartes") or [] if c.get("joueur") and "/" not in c["joueur"]
                   and (se.get(c.get("sous_ensemble")) or {}).get("groupe") == "recrue"
                   and not (se.get(c.get("sous_ensemble")) or {}).get("parallele_de")})


def _annonces_joueur(j, chercher):
    """Les annonces eBay a son nom (API Browse, gratuite) -> {m: mediane, h: 3e quartile, n} ou None."""
    import cartes_match
    res = chercher(f"{j} hockey card") or []
    fam = cartes_match.norm(j).split()[-1]
    prix = sorted(round((a.get("prix_cad") or 0) + (a.get("port_cad") or 0), 2) for a in res
                  if fam in cartes_match.norm(a.get("titre") or "").split() and not cartes_match.decoder(a.get("titre") or "").get("exclu")
                  and (a.get("prix_cad") or 0) > 0)
    if len(prix) < 3:
        return None
    h = statistics.quantiles(prix, n=4)[2] if len(prix) >= 4 else prix[-1]
    return {"m": round(statistics.median(prix), 2), "h": round(h, 2), "n": len(prix)}


ETALONS_MAX = 8


def _etalons(prod):
    """Des recrues que l'indice connait deja (demande mesuree sur leurs ventes) : celles du produit d'abord, sinon celles
    des autres produits du catalogue. Elles servent d'etalon pour mettre les nouvelles sur la MEME echelle."""
    import catalogue
    import valeurs
    vus, out = set(), []
    prods = [prod] + [p for p in (catalogue.liste() or []) if p.get("id") != prod.get("id")]
    for p in prods:
        try:
            pp = p if p.get("cartes") is not None else catalogue.charger(p["id"])
        except Exception:
            continue
        for j in recrues_du_produit(pp or {}):
            if j not in vus and valeurs.connu(j):
                vus.add(j)
                out.append(j)
        if len(out) >= ETALONS_MAX * 2:
            break
    # des forts et des moyens : l'etalon couvre toute l'echelle
    out.sort(key=lambda j: -valeurs.demande(j))
    if len(out) > ETALONS_MAX:
        pas = len(out) / ETALONS_MAX
        out = [out[int(k * pas)] for k in range(ETALONS_MAX)]
    return out


_RE_GRADEE = re.compile(r"\b(psa|bgs|sgc|cgc|graded|beckett|tag\s*\d|hga|ksa|gma|isa)\b", re.I)
_RE_PAS_BASE = re.compile(r"exclusives?|high gloss|canvas|oversized|retro|outburst|clear cut|french|deluxe|green foil|"
                          r"printing plate|/\s*\d+|\b1/1\b|dazzlers?|variation|auto|signed|patch|jersey|lot\b", re.I)


def sous_yg(prod):
    """La carte de recrue PRINCIPALE du produit : les Young Guns de base chez Upper Deck ; ailleurs (31 oct 2026, Mathieu :
    « les nouveaux produits aussi ») le sous-ensemble de recrues de base le plus frequent (Rated Rookie, Rookie Ticket,
    RC de base...), sans parallele, sans numerotation, ni Canvas, Oversized ou printing plate. None s'il n'y en a pas."""
    se = prod.get("sous_ensembles") or []
    for s in se:
        if re.fullmatch(r"\s*young guns\s*", s.get("nom") or "", re.I) and not s.get("parallele_de"):
            return s["nom"]
    cand = [s for s in se if s.get("groupe") == "recrue" and not s.get("parallele_de") and not s.get("tirage")
            and not re.search(r"oversized|canvas|printing plate|1/1|auto|patch|jersey", s.get("nom") or "", re.I)]
    cand.sort(key=lambda s: -(s.get("par_boite") or 0))
    return cand[0]["nom"] if cand else None


def yg_annonces(prod, chercher=None):
    """31 oct 2026 (Mathieu : « Porter Martone pour les Flyers vaut cher, Frondell pour les Blackhawks aussi ; bref, la
    valeur des equipes est en fonction de la valeur des Young Guns RAW de cette equipe ») : pour chaque recrue, le prix de
    SA Young Guns de base, non gradee, en vente sur eBay (API Browse, gratuite) -> {joueur: {m, n}}. Ses paralleles
    (Exclusives, High Gloss...) en decoulent (valeurs.valeur_carte remonte a la Young Guns)."""
    import cartes_match
    import ebay_compte
    nom = sous_yg(prod)
    if not nom:
        return {}
    saison, _m = _court(prod)
    chercher = chercher or (lambda q: ebay_compte.rechercher(q, categorie="261328", limite=50, fond=True))
    joueurs = sorted({c["joueur"] for c in prod.get("cartes") or [] if c.get("sous_ensemble") == nom and c.get("joueur")
                      and "/" not in c["joueur"]})
    mots_sous = [w for w in cartes_match.norm(nom).split() if len(w) >= 3 and w not in ("rookie", "rookies", "base", "the")] or ["rc"]
    _sm, marque = _court(prod)
    out = {}
    for j in joueurs:
        try:
            res = chercher(f"{saison} {'' if 'young guns' in nom.lower() else marque + ' '}{nom} {j}".replace("  ", " ")) or []
        except (RuntimeError, OSError):
            break
        fam = cartes_match.norm(j).split()[-1]
        prix = []
        for a in res:
            t = a.get("titre") or ""
            tn = cartes_match.norm(t)
            if fam not in tn.split() or not all(w in tn.split() for w in mots_sous) or saison.split("-")[0] not in t:
                continue
            if _RE_GRADEE.search(t) or _RE_PAS_BASE.search(t) or cartes_match.decoder(t).get("exclu"):
                continue
            if (a.get("prix_cad") or 0) > 0:
                prix.append(round((a.get("prix_cad") or 0) + (a.get("port_cad") or 0), 2))
        if len(prix) >= 3:
            out[j] = {"m": round(cartes_match.mediane_robuste(prix)[0] if len(prix) >= 4 else statistics.median(prix), 2),
                      "n": len(prix)}
    return out


JOUEURS_MESURES_MAX = 120


def joueurs_a_mesurer(prod):
    """31 oct 2026 (Mathieu : « les nouveaux produits doivent etre evalues en fonction des joueurs presents, la chance d'avoir
    une numerotee, un patch, une auto ou une SSP, et leur valeur sur le marche ») : les joueurs que l'indice ne connait pas
    (nouvelles recrues, espoirs, joueurs d'un nouveau produit), dans les recrues ET dans les sets de hits (autos, patchs,
    numerotees, SSP) ; ceux qui ont le plus de hits d'abord. Leur cote se lit dans leurs annonces eBay (gratuit)."""
    import calcul
    import valeurs
    se = {s["nom"]: s for s in prod.get("sous_ensembles") or []}
    poids = {}
    for c in prod.get("cartes") or []:
        j = c.get("joueur")
        s = se.get(c.get("sous_ensemble")) or {}
        if not j or "/" in j or s.get("parallele_de"):
            continue
        hit = bool(calcul.categories_carte(c, s))
        if hit or s.get("groupe") == "recrue" or c.get("recrue"):
            poids[j] = poids.get(j, 0) + (2 if hit else 1)
    l = [j for j in sorted(poids, key=lambda k: -poids[k]) if not valeurs.connu(j)]
    return l[:JOUEURS_MESURES_MAX]


def annonces_recrues(prod, chercher=None):
    """26 oct 2026 (Mathieu : « dans les Series 1, 2, Extended, on cherche les rookies : Boston (Hagens) devrait etre
    parmi les plus chers avec Chicago, Philadelphie, Washington ») - une recrue toute neuve n'a encore aucune vente :
    sa cote se lit dans ses cartes deja en vente (prospect, junior, autres produits). -> {joueur: {m, h, n}}.
    Seulement les recrues que l'indice ne connait pas ; plus (31 oct 2026) quelques recrues connues, les etalons."""
    import ebay_compte
    import valeurs
    chercher = chercher or (lambda q: ebay_compte.rechercher(q, categorie="261328", limite=50, fond=True))
    out = {}
    for j in joueurs_a_mesurer(prod):
        try:
            x = _annonces_joueur(j, chercher)
        except (RuntimeError, OSError):
            break
        if x:
            out[j] = x
    return out


def annonces_etalons(prod, chercher=None):
    import ebay_compte
    import valeurs
    chercher = chercher or (lambda q: ebay_compte.rechercher(q, categorie="261328", limite=50, fond=True))
    out = {}
    for j in _etalons(prod):
        try:
            x = _annonces_joueur(j, chercher)
        except (RuntimeError, OSError):
            break
        if x:
            out[j] = dict(x, d=valeurs.demande(j))
    return out


def demande_recrue(prod, joueur):
    """Demande relative d'une recrue sans ventes (meme echelle que valeurs.demande : ~0,6 = un joueur ordinaire).
    31 oct 2026 (Mathieu : « les Bruins (Hagens), les Flyers (Martone), les Blackhawks avec Frondell valent tous autant
    ou presque ») : avant, une nouvelle recrue etait comparee aux AUTRES nouvelles seulement (la mediane = 0,6) : quand
    toutes sont des vedettes, chacune tombait a « joueur ordinaire », loin de Schaefer (10,8) ou Demidov (6,5). Maintenant
    l'echelle vient des recrues connues (etalons) : meme prix d'annonces que Demidov -> meme demande que Demidov.
    None si on ne sait pas."""
    e = de(prod["id"])
    yg = e.get("yg_annonces") or {}
    if joueur in yg and len(yg) >= 5:
        # 31 oct 2026 : sa Young Guns raw comparee a la mediane de TOUTE la classe de recrues du produit (surtout des
        # joueurs ordinaires = 0,6) : les vedettes montent d'elles-memes (Martone, Frondell, Hagens...)
        ref = statistics.median(x["m"] for x in yg.values())
        if ref:
            return round(max(0.2, min(15.0, 0.6 * yg[joueur]["m"] / ref)), 2)
    a = e.get("annonces_recrues") or {}
    j = a.get(joueur)
    if not j:
        return None
    et = [x for x in (e.get("annonces_etalons") or {}).values() if x.get("d") and x.get("h")]
    if len(et) >= 3:
        import math
        k = statistics.median(math.log(x["d"]) - math.log(x["h"]) for x in et)
        return round(max(0.2, min(15.0, math.exp(k) * (j.get("h") or j["m"]))), 2)
    ref = statistics.median([x["m"] for x in a.values()]) if a else None
    if not ref:
        return None
    return round(max(0.2, min(15.0, 0.6 * (j["m"] / ref) ** 1.2)), 2)


def mesurer(prod, rechercher=None, chercher_annonces=None):
    import cartes_match
    import vendues
    rechercher = rechercher or vendues.rechercher
    saison, marque = _court(prod)
    out = {"maj": datetime.now().isoformat(timespec="seconds"), "sous": {}, "boite": None}
    try:
        out["yg_annonces"] = yg_annonces(prod, chercher_annonces)
    except Exception as e:
        out["erreur_yg"] = type(e).__name__
    try:
        out["annonces_recrues"] = annonces_recrues(prod, chercher_annonces)
        if out["annonces_recrues"]:
            out["annonces_etalons"] = annonces_etalons(prod, chercher_annonces)
    except Exception as e:
        out["erreur_annonces"] = type(e).__name__
    for s in (_importants(prod) if (vendues.actif() or rechercher is not vendues.rechercher) else []):
        nom = s["nom"]
        q = " ".join(x for x in (saison, marque if marque not in nom.lower() else "", nom) if x)
        r = rechercher(q, fond=True)
        if r.get("erreur") and not r.get("ventes"):
            out["erreur"] = r["erreur"]
            break
        joueurs = sorted({c["joueur"] for c in prod.get("cartes") or [] if c.get("sous_ensemble") == nom and c.get("joueur")})
        fam = {}
        for j in joueurs:
            for p in j.split("/"):
                f = cartes_match.norm(p.strip()).split()[-1:] or [""]
                if len(f[0]) >= 3:
                    fam.setdefault(f[0], []).append(j)
        par = {}
        cibles = {}
        for v in r.get("ventes") or []:
            t = cartes_match.norm(v["titre"])
            cand = {j for w in set(t.split()) for j in fam.get(w, [])}
            if len(cand) != 1:
                continue                                   # aucun joueur, ou deux (carte double, lot) : on passe
            j = cand.pop()
            if j not in cibles:
                cibles[j] = cartes_match.cible(f"{saison} {j} {nom}")
            if cartes_match.raisons_refus(cibles[j], v["titre"]):
                continue
            par.setdefault(j, []).append(v)
        js = {}
        for j, lv in par.items():
            l = [v["prix"] for v in lv]
            m = cartes_match.mediane_robuste(l)[0] if len(l) >= 3 else round(statistics.median(l), 2)
            # 26 oct 2026 - tendance et courbe du joueur (fiche joueur, tendances de la semaine)
            lv = sorted(lv, key=lambda v: str(v.get("le") or ""), reverse=True)
            js[j] = {"m": round(m, 2), "n": len(l), "t": vendues.tendance(lv), "p": [[v.get("le"), v["prix"]] for v in lv[:40] if v.get("le")]}
        tous = [x["m"] for x in js.values()]
        out["sous"][nom] = {"mediane": round(statistics.median(tous), 2) if tous else None, "n": sum(x["n"] for x in js.values()),
                            "joueurs": js}
    # le prix d'une boite scellee (hobby)
    try:
        q = f"{prod.get('nom')} hobby box"
        r = rechercher(q, fond=True)
        prix = [v["prix"] for v in r.get("ventes") or []
                if re.search(r"\bbox\b", v["titre"], re.I) and not re.search(r"\bcase\b|\bpack\b|\bbreak\b|\bspot\b|\bblaster\b|\bempty\b",
                                                                             v["titre"], re.I)
                and saison.split("-")[0] in v["titre"]]
        if len(prix) >= 2:
            out["boite"] = round(cartes_match.mediane_robuste(prix)[0] if len(prix) >= 4 else statistics.median(prix), 2)
    except Exception:
        pass
    with _verrou:
        d = dict(lire())
        d[prod["id"]] = out
        _ecrire(d)
    return out


def mesurer_si_besoin(prod, attendre=False):
    """Mesure en arriere-plan si plus vieux que 7 jours (ou jamais mesure). attendre=True : tout de suite."""
    e = de(prod["id"])
    try:
        age = time.time() - datetime.fromisoformat(str(e.get("maj"))).timestamp()
    except ValueError:
        age = 1e9
    # 31 oct 2026 : une mesure d'avant les etalons (nouvelles recrues sans echelle) est refaite tout de suite
    sans_etalons = bool(e.get("annonces_recrues")) and "annonces_etalons" not in e
    sans_yg = bool(sous_yg(prod)) and "yg_annonces" not in e        # 31 oct 2026 : les Young Guns raw de chaque recrue
    if age < FRAICHEUR_S and not e.get("erreur") and not sans_etalons and not sans_yg:
        return e
    if attendre:
        return mesurer(prod)
    with _verrou:
        if prod["id"] in _EN_COURS:
            return e
        _EN_COURS.add(prod["id"])

    def tache():
        try:
            mesurer(prod)
        except Exception as x:
            print("Valeur produit : " + repr(x), flush=True)
        finally:
            _EN_COURS.discard(prod["id"])
    threading.Thread(target=tache, daemon=True, name="valeur_produit").start()
    return e


def sous_yg_nom(_e, prod):
    k = prod.get("id")
    if k not in _YG_NOM:
        _YG_NOM[k] = sous_yg(prod)
    return _YG_NOM[k]


_YG_NOM = {}


def valeur(prod, nom_sous, joueur, defaut):
    """La valeur d'UNE carte (sous-ensemble, joueur) : sa mediane vendue si mesuree ; sinon la mediane du
    sous-ensemble x la demande relative du joueur (s'il est connu) ; sinon `defaut` (le modele d'avant)."""
    tout = de(prod["id"])
    e = (tout.get("sous") or {}).get(nom_sous)
    j = ((e or {}).get("joueurs") or {}).get(joueur)
    if j and j.get("n", 0) >= 2:
        return j["m"], True
    # 31 oct 2026 : sa Young Guns raw en vente (les annonces demandent un peu plus que les ventes : ramenees a l'echelle
    # des ventes par le rapport mesure sur les recrues qui ont les deux ; 0,85 sinon)
    yg = tout.get("yg_annonces") or {}
    if joueur in yg and nom_sous == sous_yg_nom(tout, prod):
        vend = (e or {}).get("joueurs") or {}
        r = [vend[k]["m"] / yg[k]["m"] for k in yg if k in vend and vend[k].get("n", 0) >= 2 and yg[k]["m"]]
        k = max(0.5, min(1.1, statistics.median(r))) if len(r) >= 3 else 0.85
        return round(yg[joueur]["m"] * k, 2), True
    if not e:
        return defaut, False
    if e.get("mediane"):
        if j:                                            # une seule vente : a mi-chemin avec la mediane
            return round((j["m"] + e["mediane"]) / 2, 2), True
        return round(e["mediane"] * 0.6, 2), True        # joueur jamais vendu : sous la mediane (les vedettes se vendent)
    return defaut, False
