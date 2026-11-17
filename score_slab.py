"""
SLABCOACH - le Score SlabCoach d'une annonce (10 nov 2026).

Mathieu : « revoir l'interieur des annonces avec nos nouveaux scores ; un score SlabCoach ? joueur en feu ou populaire ?
tout ce qui est legal pour aider l'utilisateur a savoir s'il met la carte dans sa watchlist ».

Le score dit a quel point une CARTE est recherchee, jamais si son PRIX est bon (licence eBay §9 : pas de prix modelise
avec les annonces eBay). Il melange :
  - le JOUEUR (55 %) : l'Indice joueur de la semaine (stats, popularite publique, legende, recrue) ;
  - la CARTE  (45 %) : ce que le titre dit d'elle : numerotee (plus le tirage est petit, mieux c'est), auto, patch,
    auto-patch, recrue, gradee 10.
Aucun prix n'entre dans le calcul.
10 nov 2026 : quand score_modele.npz est la, le score vient du modele appris (precision 0,908 / confiance 0,905 sur 32 826
ventes jamais vues) ; ce melange simple reste en secours.
"""
import re

POIDS_JOUEUR = 0.55
JOUEUR_INCONNU = 45.0

# 11 nov 2026 (Mathieu : « es-tu sur du 94 ? » : une PSA 8 de Terry Ruskowski « LOW POP /5 » notee 94) : les mots de
# vendeur (low pop, rare, hot, invest...) ne disent rien de la carte : retires avant le modele ; et un joueur que SlabIQ
# ne connait pas ne peut pas monter plus haut que ce que la carte elle-meme justifie (auto, patch, numerotee, recrue).
_RE_HYPE = re.compile(r"\b(?:low\s*pop(?:ulation)?|pop(?:ulation)?\s*(?:of\s*)?\d+(?:\s*(?:of|/)\s*\d+)?|pop\b(?:\s*/\s*\d+)?|(?:super\s*|very\s*|ultra\s*)?rare|hot|invest(?:ment)?|grail|must\s*see|wow|look|l@@k|nice|beautiful|gorgeous|sharp)\b"
                      r"(?:\s*/\s*\d+)?", re.I)


def nettoyer(titre):
    return re.sub(r"\s{2,}", " ", _RE_HYPE.sub(" ", str(titre or ""))).strip()


def _savoir(titre):
    """11 nov 2026 (Mathieu : « SlabIQ doit apprendre du livre sur les cartes des annees 90 ») : ce que le hobby sait de la carte."""
    try:
        import connaissance
        return connaissance.reconnaitre(titre)
    except Exception:
        return None


def plancher(total, k):
    """Une carte reconnue (graal, chasse, recrue cle des annees 90) ne descend pas sous son plancher ; jamais baisse."""
    if total is None or not k:
        return total
    return max(total, k["plancher"])


ECHANGE_SCORE = 12                 # 14 nov 2026 : un joueur qui quitte Toronto/Montreal : -12 sur ses cartes (Knies : -50 % de valeur)
ECHANGE_SCORE_HAUSSE = 8           # ... qui y arrive : +8


def ajuster_echange(total, ij):
    """14 nov 2026 (Mathieu : « Knies echange a Columbus ; SlabIQ aurait du le capter ») : le modele a appris sur des ventes
    ou le joueur etait encore dans son ancien club ; un changement d'equipe recent qui touche le marche le corrige."""
    if total is None or not ij:
        return total
    p = set(ij.get("pastilles") or [])
    if "echange_baisse" in p:
        return max(0.0, total - ECHANGE_SCORE)
    if "echange_hausse" in p:
        return min(100.0, total + ECHANGE_SCORE_HAUSSE)
    return total


JOUEUR_MARGE = 10.0          # points au-dessus de l'indice du joueur
JOUEUR_PART_CARTE = 0.2      # + 20 % du score de la carte elle-meme (rarete, auto, patch, recrue, gradee)


def plafond_joueur(total, c, ij):
    """15 nov 2026 (Mathieu : « un score aussi haut (88) pour Scott Perunovich est bizarre, ce n'est pas un joueur recherche » ;
    « la liquidite et la popularite d'un joueur sont toujours le main driver ») : la carte d'un joueur peu recherche ne monte
    jamais plus haut que l'indice du joueur + 10 + 20 % du score de la carte. Une PMG Red /100 d'un joueur a 25 reste ~50 ;
    un joueur a 80 et plus n'est presque jamais plafonne."""
    if total is None or not ij or ij.get("indice") is None:
        return total
    return min(total, float(ij["indice"]) + JOUEUR_MARGE + JOUEUR_PART_CARTE * float(c.get("score") or 0))


def plafond_inconnu(total, c, ij):
    """Joueur absent de l'indice SlabIQ : le score ne depasse pas 50 + la moitie du score de la carte."""
    if total is None or (ij and ij.get("indice") is not None):
        return total
    try:                                  # l'indice n'est pas encore calcule (serveur neuf) : pas de plafond
        import indice_joueurs
        if len(indice_joueurs.lire().get("indice") or {}) < 100:
            return total
    except Exception:
        return total
    return min(total, 50 + 0.5 * (c.get("score") or 0))


def _rarete(tirage):
    if not tirage:
        return 15.0
    for lim, pts in ((1, 100), (5, 92), (10, 85), (25, 75), (50, 65), (99, 55), (199, 45), (499, 35)):
        if tirage <= lim:
            return float(pts)
    return 25.0


def _gem(g):
    if not g:
        return False
    n = str(g.get("note") or "")
    return n in ("10", "9.5") or n.startswith("10")


def carte(titre, avec_type=True):
    """Ce que le titre dit de la carte (sans prix) : {auto, patch, rc, tirage, numero, grade, score}."""
    import cartes_match
    d = cartes_match._decoder_memo(titre or "")
    ns = cartes_match.numero_serie(titre or "")
    tirage = d.get("serie") or (ns[1] if ns else None)
    auto, patch, rc = bool(d.get("auto")), bool(d.get("patch")), bool(d.get("rc"))
    g = d.get("grade")
    s = 0.45 * _rarete(tirage) + (22 if auto else 0) + (14 if patch else 0) + (8 if auto and patch else 0) + (16 if rc else 0) \
        + (10 if _gem(g) else 0)
    # 12 nov 2026 (Mathieu : « une Dazzler PSA 10 versus une Young Guns PSA 10, ca n'a rien a voir ») : le type de carte appris
    # dans nos ventes (types_cartes : la carte contre la carte typique du MEME joueur) compte pour 30 % de la part carte
    ty = None
    try:
        if not avec_type:
            raise LookupError
        import types_cartes
        ty = types_cartes.info(titre)
        if ty and ty.get("score") is not None and types_cartes.aide():
            s = 0.7 * min(100.0, s) + 0.3 * ty["score"]
    except Exception:
        ty = None
    return {"auto": auto, "patch": patch, "rc": rc, "tirage": tirage, "numero": ns[0] if ns else None,
            "type": ({k: ty.get(k) for k in ("type", "nom", "score", "rang", "sur", "niveau")} if ty else None),
            "grade": (g.get("cie", "").upper() + " " + str(g.get("note") or "")).strip() if g else None,
            "exclu": bool(d.get("exclu")), "score": round(min(100.0, s), 1)}


_RE_PAS_HOCKEY = re.compile(r"\b(?:nrl|afl|rugby|soccer|premier league|la liga|bundesliga|nba|nfl|mlb|wnba|prizm|mosaic|optic"
                            r"|topps chrome|bowman chrome|sensational signatures|ufc|wwe|f1|formula 1|golf|pga|tennis)\b", re.I)


def sport_autre(titre):
    """Le sport d'une carte quand SlabIQ ne le sert pas (sports.MOTEURS["score"]), sinon None."""
    try:
        import sports
        sp = sports.sport_de(titre or "")
        if sp == "hockey":
            # 16 nov 2026 (Trevor Lawrence, Justin Herbert au Radar) : aucun joueur de hockey connu, rien du hockey dans le titre
            # et des mots d'un autre sport (Prizm, NFL...) : pas une carte de hockey
            import cartes_match
            sc = sports.scores(titre or "")
            autre = max((k for k in sc if k != "hockey"), key=lambda k: sc[k])
            connu = cartes_match._noms_dans(cartes_match.norm(titre or ""))
            if sc.get("hockey", 0) == 0 and sc[autre] >= 2 and not connu:
                sp = autre
            # 16 nov 2026 (audit du Radar : une NRL « Young Guns », une Prizm de basket) : des mots qui ne sont jamais du hockey
            elif not connu and _RE_PAS_HOCKEY.search(titre or ""):
                sp = autre if sc.get(autre) else "autre"
        return None if sports.sert("score", sp) else sp
    except Exception:
        return None


def _veteran(nom):
    """Un joueur qui avait deja 350 matchs et plus dans la LNH (donc pas une recrue de 2024-25), d'apres sa fiche LNH."""
    try:
        import evergreen
        h = evergreen._faits(nom) if nom else {}
        return int(((h or {}).get("carriere") or {}).get("gamesPlayed") or 0) >= 350
    except Exception:
        return False


def score(titre, joueur=None):
    """{score 0-100, joueur, indice, pastilles (du joueur), carte {...}, bareme {...}}. 16 nov 2026 : le bareme de l'expert
    (bareme_iq) : la sorte x la cote de collection du joueur, + un demi-cran s'il est en feu."""
    import cartes_match
    c = carte(titre)
    sp = sport_autre(titre)
    if sp:
        # 13 nov 2026 (« on va y aller avec le baseball ») : le modele SlabIQ a appris le HOCKEY ; une carte d'un autre sport
        # n'a pas de score invente. Le baseball aura le sien quand sa base de ventes sera assez grande (mlb, base_ventes)
        return {"score": None, "joueur": joueur or None, "indice": None, "pastilles": [], "semaine": None, "carte": c, "sport": sp,
                "bientot": sp == "baseball"}
    j = (joueur or cartes_match.joueur_du_titre(titre or "") or "").strip()
    nom = j.title() if j and j == j.lower() else j
    ij = None
    if j:
        try:
            import indice_joueurs
            ij = indice_joueurs.indice(j)
        except Exception:
            ij = None
    # 16 nov 2026 (Mathieu, questionnaires : « fais-toi un bareme de A+ a D ; les YG, Future Watch Auto, Cup RPA, Premier RPA
    # sont A+ ») : la note = la SORTE de carte (bareme de l'expert) x la cote de COLLECTION du joueur ; le plus faible domine
    import bareme_iq as bq
    so, so_r = bq.sorte(titre)
    crit = (ij or {}).get("criteres") or {}
    # 16 nov 2026 (Mathieu : « marquee Retro, mais c'est une Renewed ») : une « Young Guns » 2024-25 d'un VETERAN (pas une
    # recrue, aucun mot rookie dans le titre) = une Young Guns Renewed (les vraies YG de 2024-25 sont des recrues)
    if so_r in ("yg", "insert_retro", "yg_variante") and (bq._annee(str(titre or "").lower()) or 0) == 2024 \
            and not re.search(r"\brookies?\b|\brc\b|\(rc\)", str(titre or "").lower()) \
            and float(crit.get("recrue") or 0) < 80 and _veteran(nom or j):
        so, so_r = "E", "yg_renewed"
    nj, lj, src = bq.note_joueur(nom or (ij or {}).get("nom"), crit, recrue=bq.recrue_recente(titre, bool(c.get("rc")) or so_r.startswith("yg")))
    ev = None
    try:
        import evergreen
        ev = evergreen.de(nom) if nom else None
    except Exception:
        ev = None
    prem = bq.NOTE[so] >= bq.NOTE["B+"]            # une grosse carte = une sorte B+ et plus (une base gradee reste une base)
    if ev and ev.get("evergreen") and prem and src != "expert":
        nj = max(nj, float(ev["score"]))
        lj = bq.lettre_joueur(nj)
    total = bq.note_finale(bq.NOTE[so], nj)
    if so_r == "lot_checklist":
        total = min(total, bq.PLAFOND_LOT)
    pil0 = set((ij or {}).get("pastilles") or [])
    if pil0 & {"en_feu", "en_hausse", "buzz"} and so_r != "lot_checklist":
        total = min(100.0, total + bq.FEU_PTS)          # « en feu : un demi-cran »
    total = ajuster_echange(total, ij)
    k = _savoir(titre)
    total = plancher(total, k)
    if total is not None and ev and ev.get("evergreen") and prem:
        pe = parametres().get("plancher_evergreen")
        if pe:
            total = max(total, float(pe))
    pil = list((ij or {}).get("pastilles") or [])
    mb = None
    try:                                   # 16 nov 2026 : un joueur cle au marche bas (verifie) : une pastille, l'ecart en %
        import marche_cles
        mb = marche_cles.bas(nom) if nom else None
    except Exception:
        mb = None
    if mb:
        pil = ["marche_bas"] + [x for x in pil if x != "marche_bas"]
    raison = raison_de(pil, mb, ev, prem, k)
    return {"score": int(round(total)) if total is not None else None, "joueur": nom or None, "indice": ij.get("indice") if ij else None,
            "pastilles": pil, "semaine": (ij or {}).get("semaine"), "carte": c, "raison": raison,
            # 16 nov 2026 (Mathieu : « tous nos baremes doivent etre la, de maniere simple ») : les criteres du joueur (0-100)
            "criteres": {k: round(float(v)) for k, v in (((ij or {}).get("criteres")) or {}).items()
                         if k in ("forme", "demande", "buzz", "notoriete", "marche", "communaute", "legende", "ascension", "recrue") and v is not None},
            **({"evergreen": {"score": ev["score"], "raisons": ev["raisons"]}} if ev and ev.get("evergreen") else {}),
            "bareme": {"sorte": so, "sorte_raison": so_r, "joueur": lj, "joueur_note": round(nj, 1), "joueur_source": src},
            **({"marche": {"ecart_pct": mb.get("ecart_pct")}} if mb else {}), **({"connaissance": k} if k else {})}


def premium(c):
    """16 nov 2026 : une « grosse carte » (ce que les collectionneurs gardent) : auto, patch, numerotee /99 et moins, recrue,
    gradee, ou une sorte ultra / tres recherchee."""
    c = c or {}
    t = c.get("tirage")
    ty = c.get("type") or {}
    return bool(c.get("auto") or c.get("patch") or (t and t <= 99) or c.get("rc") or c.get("grade")
                or ty.get("niveau") in ("ultra", "forte"))


def raison_de(pil, mb, ev, prem, k=None):
    """LA raison principale de la note, pour l'expliquer en un mot : « marche_bas » (le joueur cle sous sa normale),
    « chaud » (en feu, en hausse, buzz), « long_terme » (evergreen et grosse carte, ou une carte mythique), sinon None.
    (« flip » : une annonce sous le prix des ventes, dite par l'ecran du deal.)"""
    pil = pil or []
    if mb:
        return "marche_bas"
    if any(x in pil for x in ("en_feu", "en_hausse", "buzz")):
        return "chaud"
    if (ev and ev.get("evergreen") and prem) or (k and k.get("niveau") in ("graal", "chasse", "cle")):
        return "long_terme"
    return None


_PARAMS = {"t": 0.0, "v": None}


def parametres():
    """Les reglages choisis par la boucle de l'expert (slabiq_expert), gardes 10 min ; defaut : un plancher A- (80)."""
    import time as _t
    if _PARAMS["v"] is None or _t.time() - _PARAMS["t"] > 600:
        try:
            import slabiq_expert
            _PARAMS["v"] = slabiq_expert.params()
        except Exception:
            _PARAMS["v"] = {}
        _PARAMS["t"] = _t.time()
    return {"plancher_evergreen": 80, **(_PARAMS["v"] or {})}


def annoter(x):
    """Ajoute score, pastilles du joueur et attributs de la carte a une annonce (dict), sur place."""
    try:
        s = score(x.get("titre") or "", x.get("joueur"))
    except Exception:
        return x
    x["score"] = s["score"]
    x["carte"] = {k: s["carte"][k] for k in ("auto", "patch", "rc", "tirage", "numero", "grade")}
    if s.get("bareme"):
        x["sorte"] = s["bareme"]["sorte"]
    if s["pastilles"]:
        x["pastilles_j"] = s["pastilles"]
    if s["joueur"] and not x.get("joueur"):
        x["joueur"] = s["joueur"]
    return x


# 12 nov 2026 (Mathieu : « tout est ultralent dans le Radar ») : le Radar annote des centaines d'annonces a chaque ouverture,
# souvent les memes. Ce qu'on a calcule pour un titre (score, carte, pastilles, joueur) est garde 30 min (20 000 titres au
# plus) ; un nouveau modele SlabIQ vide la memoire. Seuls les titres jamais vus passent par le modele.
_LOT = {"m": None, "d": {}}
LOT_S = 1800
_CHAMPS_LOT = ("score", "carte", "pastilles_j", "joueur", "sorte")


def annoter_lot(items):
    """Comme annoter, pour une liste (le modele calcule tout d'un coup : bien plus rapide). Avec memoire par titre."""
    import time as _t
    items = [x for x in items if isinstance(x, dict)]
    try:
        import score_modele
        mid = id(score_modele.charger())
    except Exception:
        mid = None
    if _LOT["m"] != mid or len(_LOT["d"]) > 20000:
        _LOT.update(m=mid, d={})
    m, D, manque = _t.time(), _LOT["d"], []
    for x in items:
        g = D.get(((x.get("titre") or ""), x.get("joueur") or ""))
        if g and m - g[0] < LOT_S:
            for k, v in g[1].items():
                if k == "joueur" and x.get("joueur"):
                    continue
                x[k] = v
        else:
            manque.append(x)
    if manque:
        cles = [((x.get("titre") or ""), x.get("joueur") or "") for x in manque]
        _annoter_lot(manque)
        for cle, x in zip(cles, manque):
            D[cle] = (m, {k: x[k] for k in _CHAMPS_LOT if k in x})
    return items


def _annoter_lot(items):
    """Comme annoter, pour une liste (16 nov 2026 : le bareme de l'expert est rapide : une annonce a la fois)."""
    for x in items:
        if isinstance(x, dict):
            annoter(x)
    return items
