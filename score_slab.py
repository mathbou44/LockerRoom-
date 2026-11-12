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
            "type": ({k: ty.get(k) for k in ("type", "nom", "score", "rang", "sur")} if ty else None),
            "grade": (g.get("cie", "").upper() + " " + str(g.get("note") or "")).strip() if g else None,
            "exclu": bool(d.get("exclu")), "score": round(min(100.0, s), 1)}


def score(titre, joueur=None):
    """{score 0-100, joueur, indice, pastilles (du joueur), carte {...}}. Le score : joueur 55 % + carte 45 %."""
    import cartes_match
    c = carte(titre)
    j = (joueur or cartes_match.joueur_du_titre(titre or "") or "").strip()
    ij = None
    if j:
        try:
            import indice_joueurs
            ij = indice_joueurs.indice(j)
        except Exception:
            ij = None
    sj = float(ij["indice"]) if ij and ij.get("indice") is not None else JOUEUR_INCONNU
    total = POIDS_JOUEUR * sj + (1 - POIDS_JOUEUR) * c["score"]
    # 10 nov 2026 (« precision 9/10 ») : le modele appris (score_modele) quand il est la ; sinon le melange simple
    try:
        import score_modele
        sm = score_modele.score(nettoyer(titre), joueur)
        if sm is not None:
            total = sm
        elif score_modele.charger() and not score_modele.informatif(nettoyer(titre), joueur):
            total = None                     # 12 nov 2026 : pas assez d'indices dans le titre : pas de score invente
    except Exception as e:
        print("Score modele : " + repr(e), flush=True)
    total = plafond_inconnu(total, c, ij)
    k = _savoir(titre)
    total = plancher(total, k)
    nom = j.title() if j and j == j.lower() else j
    return {"score": int(round(total)) if total is not None else None, "joueur": nom or None, "indice": ij.get("indice") if ij else None,
            "pastilles": (ij or {}).get("pastilles") or [], "semaine": (ij or {}).get("semaine"), "carte": c,
            **({"connaissance": k} if k else {})}


def annoter(x):
    """Ajoute score, pastilles du joueur et attributs de la carte a une annonce (dict), sur place."""
    try:
        s = score(x.get("titre") or "", x.get("joueur"))
    except Exception:
        return x
    x["score"] = s["score"]
    x["carte"] = {k: s["carte"][k] for k in ("auto", "patch", "rc", "tirage", "numero", "grade")}
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
_CHAMPS_LOT = ("score", "carte", "pastilles_j", "joueur")


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
    """Comme annoter, pour une liste (le modele calcule tout d'un coup : bien plus rapide)."""
    items = [x for x in items if isinstance(x, dict)]
    try:
        import score_modele
        sc = score_modele.scores([nettoyer(x.get("titre")) for x in items], [x.get("joueur") for x in items])
    except Exception as e:
        print("Score modele (lot) : " + repr(e), flush=True)
        sc = None
    for k, x in enumerate(items):
        try:
            c = carte(x.get("titre") or "")
            import cartes_match
            j = (x.get("joueur") or cartes_match.joueur_du_titre(x.get("titre") or "") or "").strip()
            ij = None
            if j:
                import indice_joueurs
                ij = indice_joueurs.indice(j)
            sv = _savoir(x.get("titre") or "")
            if sc is not None:
                x["score"] = sc[k] if sc[k] is None else int(round(plancher(plafond_inconnu(sc[k], c, ij), sv)))
            else:
                sj = float(ij["indice"]) if ij and ij.get("indice") is not None else JOUEUR_INCONNU
                x["score"] = int(round(plancher(POIDS_JOUEUR * sj + (1 - POIDS_JOUEUR) * c["score"], sv)))
            x["carte"] = {kk: c[kk] for kk in ("auto", "patch", "rc", "tirage", "numero", "grade")}
            if ij and ij.get("pastilles"):
                x["pastilles_j"] = ij["pastilles"]
            if j and not x.get("joueur"):
                x["joueur"] = j.title() if j == j.lower() else j
        except Exception:
            continue
    return items
