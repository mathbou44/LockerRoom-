"""
LOCKERROOM - calculs purs (aucune base, aucun reseau) : faciles a tester.

  - prix_places() : prix de chaque equipe / joueur / division d'un break a
    partir de la checklist, des cartes par boite, du cout, de la marge et des
    frais de la plateforme.
  - tirage() : attribution aleatoire VERIFIABLE (graine publiee apres coup).
  - profit_vente() / profit_break() : profit net reel.
  - offre_rachat() : offre a un client qui vend ses cartes au comptoir.
"""
import hashlib
import math
import random
import re
import secrets
import unicodedata

# -- equipes : voir sports.py (23 oct 2026 - NHL, NFL, NBA, MLB) -------------------------
import sports

EQUIPES_LNH = sports.equipes("hockey")


def _sans_accents(t):
    return "".join(c for c in unicodedata.normalize("NFKD", str(t or "")) if not unicodedata.combining(c)).lower()


def code_equipe(texte, sport=None):
    """« Montréal Canadiens », « MTL », « Canadiens » -> « MTL » ; inconnu -> le texte."""
    return sports.code_equipe(texte, sport)


def nom_equipe(code, sport=None):
    return sports.nom_equipe(code, sport)


def division(code, sport=None):
    return sports.division(code, sport)


# -- poids des cartes ------------------------------------------------------------------
POIDS_DEFAUT = {
    "base": 0.05, "insert": 0.6, "recrue": 4.0, "auto_mult": 4.0, "relique": 2.0, "sp": 3.0,
    "numerotee_ref": 10.0,      # /N : poids x max(1, 10 / sqrt(N))  -> /1 x10, /10 x3,2, /99 x1
}
# popularite du joueur (etoiles) -> multiplicateur
ETOILES = {1: 0.35, 2: 0.65, 3: 1.0, 4: 1.8, 5: 3.0}


def poids_carte(c, poids=None):
    p = dict(POIDS_DEFAUT, **(poids or {}))
    cat = _sans_accents(c.get("categorie"))
    if c.get("recrue") or any(m in cat for m in ("young guns", "rookie", "recrue", "yg")):
        w = p["recrue"]
    elif "sp" == cat or "short print" in cat or c.get("sp"):
        w = p["sp"]
    elif cat and cat not in ("base", "base set"):
        w = p["insert"]
    else:
        w = p["base"]
    if c.get("relique"):
        w = max(w, p["relique"])
    if c.get("auto"):
        w *= p["auto_mult"]
    n = c.get("tirage")
    if n:
        try:
            w *= max(1.0, p["numerotee_ref"] / math.sqrt(max(1, int(n))))
        except (TypeError, ValueError):
            pass
    return w


def _groupe(c):
    """Cle de categorie pour les cotes « par boite » (recrue, auto, numerotee, base, insert)."""
    if c.get("auto"):
        return "auto"
    if c.get("tirage"):
        return "numerotee"
    cat = _sans_accents(c.get("categorie"))
    if c.get("recrue") or any(m in cat for m in ("young guns", "rookie", "recrue")):
        return "recrue"
    if cat and cat not in ("base", "base set"):
        return "insert"
    return "base"


def _arrondir(v, pas):
    pas = max(0.01, float(pas or 1))
    return round(math.ceil(v / pas - 1e-9) * pas, 2)


def prix_places(checklist, boites=1, cout_boite=0.0, marge=0.25, frais_pct=0.109, frais_fixe=0.30,
                mode="equipes", par_boite=None, etoiles=None, plancher=1.0, arrondi=1.0, poids=None, sport=None):
    """Prix de chaque place. `par_boite` : cartes de chaque groupe par boite
    (ex. {"recrue": 6, "auto": 0.5}) - sans cote connue, chaque carte du groupe
    compte une fois. `etoiles` : {joueur: 1-5}. Retourne {"places": [...],
    "total", "cible", "cout", "profit_estime", "nb_cartes"}."""
    etoiles = etoiles or {}
    par_boite = {k: float(v) for k, v in (par_boite or {}).items() if v not in (None, "")}
    nb_groupe = {}
    for c in checklist:
        g = _groupe(c)
        nb_groupe[g] = nb_groupe.get(g, 0) + 1
    # nombre attendu d'exemplaires de CHAQUE carte dans le break
    attendu = {}
    for g, n in nb_groupe.items():
        attendu[g] = (par_boite[g] * boites / n) if g in par_boite and n else 1.0
    cles = {}
    for c in checklist:
        equipes = [code_equipe(e, sport) for e in re.split(r"\s*/\s*|\s*,\s*", str(c.get("equipe") or "")) if e.strip()] or ["?"]
        if mode == "joueurs":
            cle = [str(c.get("joueur") or "?").strip()]
        elif mode == "divisions":
            cle = sorted({division(e, sport) for e in equipes})
        else:
            cle = equipes
        f = ETOILES.get(int(etoiles.get(str(c.get("joueur") or "").strip(), 3) or 3), 1.0)
        valeur = poids_carte(c, poids) * f * attendu[_groupe(c)] / len(cle)     # carte a 2 equipes : moitie chacune
        for k in cle:
            d = cles.setdefault(k, {"cle": k, "ev": 0.0, "nb": 0, "recrues": 0, "autos": 0, "numerotees": 0, "vedettes": {}})
            d["ev"] += valeur
            d["nb"] += 1
            g = _groupe(c)
            d["recrues"] += 1 if g == "recrue" else 0
            d["autos"] += 1 if c.get("auto") else 0
            d["numerotees"] += 1 if c.get("tirage") else 0
            j = str(c.get("joueur") or "").strip()
            if j:
                d["vedettes"][j] = d["vedettes"].get(j, 0) + valeur
    if mode == "equipes":                       # les 32 equipes, meme sans carte
        for code in sports.equipes(sport):
            cles.setdefault(code, {"cle": code, "ev": 0.0, "nb": 0, "recrues": 0, "autos": 0, "numerotees": 0, "vedettes": {}})
        cles.pop("?", None)
    cout = round(float(cout_boite) * boites, 2)
    n = len(cles) or 1
    cible = (cout * (1 + float(marge)) + float(frais_fixe) * n) / max(0.01, 1 - float(frais_pct))
    total_ev = sum(d["ev"] for d in cles.values()) or 1.0
    reste = max(0.0, cible - float(plancher) * n)
    places = []
    for d in cles.values():
        brut = float(plancher) + reste * d["ev"] / total_ev
        places.append({
            "cle": d["cle"], "nom": nom_equipe(d["cle"], sport) if mode == "equipes" else d["cle"],
            "prix": _arrondir(brut, arrondi), "part": round(100 * d["ev"] / total_ev, 1), "nb_cartes": d["nb"],
            "recrues": d["recrues"], "autos": d["autos"], "numerotees": d["numerotees"],
            "vedettes": [j for j, _ in sorted(d["vedettes"].items(), key=lambda kv: -kv[1])[:3]],
        })
    places.sort(key=lambda p: (-p["prix"], p["nom"]))
    total = round(sum(p["prix"] for p in places), 2)
    net = total * (1 - float(frais_pct)) - float(frais_fixe) * len(places)
    return {"places": places, "total": total, "cible": round(cible, 2), "cout": cout,
            "profit_estime": round(net - cout, 2), "nb_cartes": len(checklist)}


def prix_catalogue(prod, boites=1, cout_boite=0.0, marge=0.25, frais_pct=0.109, frais_fixe=0.30,
                   mode="equipes", plancher=1.0, arrondi=1.0, sport=None):
    """Liste de prix d'un break a partir d'un produit du CATALOGUE : chaque
    carte (et chaque parallele) compte pour son nombre d'exemplaires attendus
    dans `boites` boites x sa valeur (valeur du sous-ensemble x demande du
    joueur, voir valeurs.py). La valeur attendue (EV) de chaque equipe fixe sa
    part du prix cible (cout + marge + frais), avec un prix minimum."""
    import catalogue
    import valeurs
    sport = sport or prod.get("sport")
    se = {s["nom"]: s for s in prod.get("sous_ensembles") or []}
    taux = prod["_taux"]
    cache, cles = {}, {}
    ev_total = ev_mesuree = 0.0
    for c, s, n in catalogue.cartes_attendues(prod, boites):
        nom = s["nom"]
        if nom not in cache:
            cache[nom] = valeurs.valeur_sous_ensemble(prod, nom, se, taux)
        vref, mesure = cache[nom]
        ev = n * vref * valeurs.demande(c.get("joueur"))
        ev_total += ev
        ev_mesuree += ev if mesure else 0.0
        equipes = [code_equipe(e, sport) for e in re.split(r"\s*/\s*|\s*,\s*", str(c.get("equipe") or "")) if e.strip()] or ["?"]
        if mode == "joueurs":
            k_list = [x.strip() for x in re.split(r"\s*/\s*", str(c.get("joueur") or "?")) if x.strip()] or ["?"]
        elif mode == "divisions":
            k_list = sorted({division(e, sport) for e in equipes})
        else:
            k_list = list(dict.fromkeys(equipes))
        g = s.get("groupe") or "base"
        for k in k_list:
            d = cles.setdefault(k, {"cle": k, "ev": 0.0, "recrues": 0.0, "hits": 0.0, "numerotees": 0.0, "vedettes": {}})
            part = 1.0 / len(k_list)
            d["ev"] += ev * part
            d["recrues"] += n * part if (g == "recrue" or c.get("recrue")) else 0.0
            d["hits"] += n * part if g in ("auto", "memo", "auto_memo") or c.get("auto") or c.get("memo") else 0.0
            d["numerotees"] += n * part if s.get("tirage") else 0.0
            j = str(c.get("joueur") or "").strip()
            if j and "/" not in j:                    # vedettes : joueurs seuls (pas les cartes doubles)
                d["vedettes"][j] = d["vedettes"].get(j, 0.0) + ev * part
    if mode == "equipes":
        for code in sports.equipes(sport):
            cles.setdefault(code, {"cle": code, "ev": 0.0, "recrues": 0.0, "hits": 0.0, "numerotees": 0.0, "vedettes": {}})
        cles.pop("?", None)
    cout = round(float(cout_boite) * boites, 2)
    n = len(cles) or 1
    cible = (cout * (1 + float(marge)) + float(frais_fixe) * n) / max(0.01, 1 - float(frais_pct))
    somme = sum(d["ev"] for d in cles.values()) or 1.0
    reste = max(0.0, cible - float(plancher) * n)
    places = []
    for d in cles.values():
        brut = float(plancher) + reste * d["ev"] / somme
        places.append({"cle": d["cle"], "nom": nom_equipe(d["cle"], sport) if mode == "equipes" else d["cle"],
                       "prix": _arrondir(brut, arrondi), "part": round(100 * d["ev"] / somme, 1), "ev": round(d["ev"], 2),
                       "recrues": round(d["recrues"], 1), "hits": round(d["hits"], 2), "numerotees": round(d["numerotees"], 2),
                       "vedettes": [j for j, _ in sorted(d["vedettes"].items(), key=lambda kv: -kv[1])[:3]]})
    places.sort(key=lambda p: (-p["prix"], p["nom"]))
    total = round(sum(p["prix"] for p in places), 2)
    net = total * (1 - float(frais_pct)) - float(frais_fixe) * len(places)
    return {"places": places, "total": total, "cible": round(cible, 2), "cout": cout, "profit_estime": round(net - cout, 2),
            "ev_total": round(ev_total, 2), "ev_par_boite": round(ev_total / max(1e-9, float(boites)), 2),
            "part_mesuree": round(100 * ev_mesuree / ev_total, 1) if ev_total else 0.0,
            "nb_cartes": len(prod.get("cartes") or [])}


# -- tirage verifiable ------------------------------------------------------------------
def tirage(participants, lots, graine=None):
    """Melange `lots` et les attribue dans l'ordre a `participants` (les places
    vendues). Graine aleatoire forte ; son empreinte SHA-256 est publiee AVANT
    (engagement), la graine apres : n'importe qui peut refaire le tirage."""
    graine = graine or secrets.token_hex(16)
    melange = list(lots)
    random.Random(graine).shuffle(melange)
    paires = [{"participant": p, "lot": melange[i] if i < len(melange) else None} for i, p in enumerate(participants)]
    return {"graine": graine, "empreinte": hashlib.sha256(graine.encode()).hexdigest(), "resultat": paires,
            "methode": "random.Random(graine).shuffle(lots) - Python"}


def pile_ou_face(options, graine=None):
    graine = graine or secrets.token_hex(8)
    return {"gagnant": random.Random(graine).choice(list(options)), "graine": graine}


# -- profits ---------------------------------------------------------------------------------
def profit_vente(prix, cout=0.0, port_paye=0.0, port_charge=0.0, frais_pct=0.1325, frais_fixe=0.40,
                 promo_pct=0.0):
    """Vente eBay : frais sur (prix + port charge), comme eBay. Retourne un dict."""
    prix, cout = float(prix or 0), float(cout or 0)
    port_paye, port_charge = float(port_paye or 0), float(port_charge or 0)
    base = prix + port_charge
    frais = round(base * (float(frais_pct) + float(promo_pct)) + (float(frais_fixe) if prix else 0), 2)
    net = round(base - frais - port_paye, 2)
    return {"frais": frais, "net": net, "profit": round(net - cout, 2),
            "marge_pct": round(100 * (net - cout) / cout, 1) if cout else None}


def profit_break(revenus, nb_ventes, cout_produit, frais_pct, frais_fixe, port_paye=0.0, autres=0.0):
    revenus = float(revenus or 0)
    frais = round(revenus * float(frais_pct) + float(frais_fixe) * int(nb_ventes or 0), 2)
    profit = round(revenus - frais - float(cout_produit or 0) - float(port_paye or 0) - float(autres or 0), 2)
    return {"revenus": round(revenus, 2), "frais": frais, "cout": round(float(cout_produit or 0), 2),
            "port": round(float(port_paye or 0), 2), "profit": profit}


# -- rachat au comptoir ---------------------------------------------------------------------
PALIERS_RACHAT = [(10, 0.30), (50, 0.50), (200, 0.60), (float("inf"), 0.70)]


def offre_rachat(valeurs, paliers=None, bonus_credit=0.10):
    """Offre pour un lot : % de la valeur selon le palier de chaque carte.
    Retourne {"lignes", "valeur", "comptant", "credit"}."""
    paliers = paliers or PALIERS_RACHAT
    lignes, total_v, total_o = [], 0.0, 0.0
    for v in valeurs:
        v = float(v or 0)
        pct = next((p for seuil, p in paliers if v < seuil), paliers[-1][1])
        o = round(v * pct, 2)
        lignes.append({"valeur": v, "pct": pct, "offre": o})
        total_v += v
        total_o += o
    return {"lignes": lignes, "valeur": round(total_v, 2), "comptant": round(total_o, 2),
            "credit": round(total_o * (1 + float(bonus_credit)), 2)}
