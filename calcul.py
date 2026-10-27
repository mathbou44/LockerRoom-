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


# 26 oct 2026 (Mathieu : « la chance de tomber sur une carte numerotee, patch, auto, auto-patch ou SSP, pour une
# equipe ou un joueur ; tous evalues sur les memes metriques ») : une definition unique, la meme pour tout le monde.
CATEGORIES_HIT = ("numerotee", "auto", "patch", "auto_patch", "ssp")
_RE_SSP = re.compile(r"\bssp\b|super short", re.I)


def categories_carte(c, s):
    """Les categories de hit d'une version (carte x sous-ensemble) : numerotee (tirage connu, 1/1 compris), auto,
    patch (relique / memorabilia), auto_patch (les deux), ssp. Une auto-patch /25 compte dans les 4 premieres."""
    s = s or {}
    g = s.get("groupe") or "base"
    auto = bool(c.get("auto")) or g in ("auto", "auto_memo")
    patch = bool(c.get("memo") or c.get("relique")) or g in ("memo", "auto_memo")
    out = set()
    if c.get("tirage") or s.get("tirage"):
        out.add("numerotee")
    if auto:
        out.add("auto")
    if patch:
        out.add("patch")
    if auto and patch:
        out.add("auto_patch")
    if str(c.get("sp") or "").upper() == "SSP" or _RE_SSP.search(str(s.get("nom") or "")):
        out.add("ssp")
    return out


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


def _gamma_p(k, x):
    """Gamma incomplete reguliere P(k, x) (series / fraction continue, Numerical Recipes)."""
    if x <= 0:
        return 0.0
    if x < k + 1:
        terme = somme = 1.0 / k
        a = k
        for _ in range(500):
            a += 1
            terme *= x / a
            somme += terme
            if abs(terme) < abs(somme) * 1e-10:
                break
        return min(1.0, somme * math.exp(-x + k * math.log(x) - math.lgamma(k)))
    b, c, d = x + 1 - k, 1e300, 1 / (x + 1 - k)
    h = d
    for i in range(1, 500):
        an = -i * (i - k)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d
        h *= d * c
        if abs(d * c - 1) < 1e-10:
            break
    return max(0.0, 1.0 - math.exp(-x + k * math.log(x) - math.lgamma(k)) * h)


SEUIL_REVENTE = 1.50           # $ CA : sous ce prix, une carte ne se revend pas a l'unite


def chance_rembourser(dist, prix, pas_max=400):
    """La chance que les cartes recues valent AU MOINS le prix paye pour la place. dist = [(valeur d'une carte,
    nombre attendu dans le break)]. La somme suit une loi de Poisson composee (chaque carte possible arrive un
    nombre de fois aleatoire).
    26 oct 2026 (Mathieu : « comment ca 0 % ? ») : l'approximation Gamma (meme moyenne, meme variance) d'avant
    ecrasait les places « peu de chances, gros hit » (Islanders d'Ultimate Collection : 1 % au lieu de 5 %). Calcul
    exact maintenant : recursion de Panjer sur les valeurs arrondies au pas (prix / 400, 0,25 $ minimum),
    verifiee contre une simulation Monte-Carlo (memes chiffres a 0,5 point pres)."""
    prix = float(prix or 0)
    if prix <= 0:
        return 1.0
    h = max(0.01, prix / pas_max)
    # 27 oct 2026 (revue) : avant, max(1, round(v / h)) comptait une carte de 0,12 $ pour un pas entier (0,25 $) : 100
    # petites cartes gonflaient la chance (83 % au lieu de 19 %). Maintenant chaque valeur est partagee entre les deux pas
    # voisins (meme moyenne exacte) : une carte de 2,4 pas compte 60 % pour 2 pas et 40 % pour 3. La part « 0 pas » d'une
    # toute petite carte ne change pas la somme : elle sort du taux d'arrivee. Verifie contre Monte-Carlo (tests).
    m = int(math.ceil(prix / h - 1e-9))
    poids = {}
    for v, n in dist or []:
        v, n = float(v), float(n)
        if v <= 0 or n <= 0:
            continue
        x = v / h
        k = int(math.floor(x))
        fr = x - k
        for kk, w in ((k, n * (1 - fr)), (k + 1, n * fr)):
            if kk >= 1 and w > 0:
                poids[kk] = poids.get(kk, 0.0) + w
    lam = sum(poids.values())
    if lam <= 0:
        return 0.0
    fx = {k: w / lam for k, w in poids.items() if k < m}   # une carte qui vaut a elle seule le prix : rembourse d'office
    sauts = sorted(fx.items())
    fs = [0.0] * m
    fs[0] = math.exp(-lam)
    for s_ in range(1, m):
        acc = 0.0
        for k, f in sauts:
            if k > s_:
                break
            acc += k * f * fs[s_ - k]
        fs[s_] = lam / s_ * acc
    return round(max(0.0, min(1.0, 1 - sum(fs))), 3)


def prix_catalogue(prod, boites=1, cout_boite=0.0, marge=0.25, frais_pct=0.109, frais_fixe=0.30,
                   mode="equipes", plancher=1.0, arrondi=1.0, sport=None, garder_dist=False):
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
        v1, mesure = valeurs.valeur_carte(prod, nom, c.get("joueur"), se, taux, cache)      # 25 oct 2026 : ventes reelles
        # 26 oct 2026 (Mathieu : « on cherche les rookies ») : ce qui fait le prix d'une place, c'est ce qui se REVEND ;
        # une carte de 1 $ (base d'un veteran) ne vaut rien a revendre (frais + envoi) : seule la valeur au-dessus compte
        v1 = max(0.0, v1 - SEUIL_REVENTE)
        ev = n * v1
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
            d = cles.setdefault(k, {"cle": k, "ev": 0.0, "recrues": 0.0, "hits": 0.0, "numerotees": 0.0, "vedettes": {}, "n": 0.0})
            part = 1.0 / len(k_list)
            d.setdefault("dist", []).append((v1, n * part))         # 25 oct 2026 : valeur de chaque carte possible
            if garder_dist:                                         # 26 oct 2026 : « comment tu as calcule » (par sous-ensemble)
                x = d.setdefault("detail", {}).setdefault(nom, [0.0, 0.0, 0.0, False])
                x[0] += n * part
                x[1] = max(x[1], v1 + SEUIL_REVENTE)
                x[2] += ev * part
                x[3] = x[3] or bool(mesure)
            # les memes metriques pour chaque equipe / joueur : nombre attendu et valeur de chaque categorie de hit
            cats = categories_carte(c, s)
            if cats:
                ch = d.setdefault("cats", {})
                for cat in list(cats) + ["hit"]:
                    x = ch.setdefault(cat, [0.0, 0.0, 0.0])
                    x[0] += n * part
                    x[1] += n * part * (v1 + SEUIL_REVENTE)
                    x[2] += n * part * (v1 + SEUIL_REVENTE) if mesure else 0.0
            d["ev"] += ev * part
            d["n"] += n * part
            d["recrues"] += n * part if (g == "recrue" or c.get("recrue")) else 0.0
            d["hits"] += n * part if g in ("auto", "memo", "auto_memo") or c.get("auto") or c.get("memo") else 0.0
            d["numerotees"] += n * part if s.get("tirage") else 0.0
            j = str(c.get("joueur") or "").strip()
            if j and "/" not in j:                    # vedettes : joueurs seuls (pas les cartes doubles)
                d["vedettes"][j] = d["vedettes"].get(j, 0.0) + ev * part
    if mode == "equipes":
        for code in sports.equipes(sport):
            cles.setdefault(code, {"cle": code, "ev": 0.0, "recrues": 0.0, "hits": 0.0, "numerotees": 0.0, "vedettes": {}, "n": 0.0})
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
                       "vedettes": [j for j, _ in sorted(d["vedettes"].items(), key=lambda kv: -kv[1])[:3]],
                       # 24 oct 2026 - chances (loi de Poisson sur le nombre attendu) : au moins une carte, une recrue, un hit
                       "p_carte": round(1 - math.exp(-d.get("n", 0.0)), 3), "p_recrue": round(1 - math.exp(-d["recrues"]), 3),
                       "p_hit": round(1 - math.exp(-d["hits"]), 3), "n_attendu": round(d.get("n", 0.0), 2),
                       "chances": _chances(d.get("cats") or {}),
                       **({"_dist": d.get("dist") or [], "_detail": d.get("detail") or {}} if garder_dist else {})})
    places.sort(key=lambda p: (-p["prix"], p["nom"]))
    total = round(sum(p["prix"] for p in places), 2)
    net = total * (1 - float(frais_pct)) - float(frais_fixe) * len(places)
    return {"places": places, "total": total, "cible": round(cible, 2), "cout": cout, "profit_estime": round(net - cout, 2),
            "ev_total": round(ev_total, 2), "ev_par_boite": round(ev_total / max(1e-9, float(boites)), 2),
            "part_mesuree": round(100 * ev_mesuree / ev_total, 1) if ev_total else 0.0,
            "nb_cartes": len(prod.get("cartes") or [])}


# -- tirage verifiable ------------------------------------------------------------------
def _chances(cats):
    """{categorie: {p (au moins une, loi de Poisson), attendu, valeur (moyenne d'une carte de la categorie, ponderee par
    sa chance de sortir), reelle (% de cette valeur tiree des ventes reelles)}} ; « hit » = au moins une des categories."""
    out = {}
    for cat in CATEGORIES_HIT + ("hit",):
        lam, sv, sm = cats.get(cat) or (0.0, 0.0, 0.0)
        out[cat] = {"p": round(1 - math.exp(-lam), 6), "attendu": round(lam, 4),
                    "valeur": round(sv / lam, 2) if lam > 0 else None, "reelle": round(100 * sm / sv) if sv > 0 else 0}
    return out


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
