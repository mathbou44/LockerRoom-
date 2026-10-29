"""
SLABCOACH - nos propres nouvelles du marche, tirees de NOS donnees (31 oct 2026).

Mathieu : « on peut mettre nos propres nouvelles inspirees de nos interpretations des donnees » ; « assure-toi juste que
les donnees soient bonnes et justes, sinon on fait de la desinformation ».

Source : la base des ventes eBay REELLES de SlabCoach (base_ventes : chaque recherche SoldComps, vente par vente). Pas de
PSA (leur entente l'interdit), pas d'annonces (un prix demande n'est pas un prix paye).

Une nouvelle ne sort que si TOUTES ces regles passent ; sinon, rien (mieux vaut se taire que dire faux) :
  1. la MEME carte (cartes_match : annee, set, variante, numero, joueur) dans la MEME condition (brute, PSA 10, PSA 9) ;
     les lots, les autres variantes et les autres gradations sont exclus ;
  2. une vente comptee une seule fois (la meme annonce vue par deux recherches) ;
  3. les prix aberrants retires (moins du tiers ou plus du triple de la mediane) ;
  4. assez de ventes : au moins MIN_VENTES dans chaque periode comparee ;
  5. un changement net ET solide : au moins SEUIL_PCT %, et un test statistique (Mann-Whitney, p < P_MAX) qui dit que
     ce n'est pas le hasard de quelques ventes (on regarde des centaines de cartes : le seuil est severe) ;
  6. fraiche : la derniere vente a SEMAINE jours au plus ;
  7. un fait mesure, jamais une prediction ni un conseil d'achat : les chiffres, la periode, le nombre de ventes, et les
     ventes elles-memes (la preuve, avec leur lien eBay) pour que chacun verifie.
Pour la comparaison PSA 10 / PSA 9 : on montre la carte qui a le PLUS de ventes (la plus solide), pas la plus extreme
(choisir l'extreme parmi des centaines de cartes, c'est montrer le hasard).
"""
import math
import statistics
import time
from datetime import datetime, timedelta

RECENT_J = 14                    # periode recente : les 14 derniers jours
AVANT_J = (15, 45)               # comparee aux ventes d'il y a 15 a 45 jours
SEMAINE = 7
MIN_VENTES = 6
SEUIL_PCT = 20
P_MAX = 0.01
PRIME_J = 45
CONDITIONS = (("", None), (" psa 10", "PSA 10"), (" psa 9", "PSA 9"))
FRAICHEUR_S = 3600
_CACHE = {"le": 0.0, "v": None}


def _p_mann_whitney(a, b):
    """p bilateral du test de Mann-Whitney (approximation normale, correction des ex aequo et de continuite)."""
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2:
        return 1.0
    tout = sorted([(x, 0) for x in a] + [(x, 1) for x in b])
    rangs, i = [0.0] * len(tout), 0
    egal = 0.0
    while i < len(tout):
        j = i
        while j + 1 < len(tout) and tout[j + 1][0] == tout[i][0]:
            j += 1
        r = (i + j) / 2 + 1
        for k in range(i, j + 1):
            rangs[k] = r
        t = j - i + 1
        egal += t ** 3 - t
        i = j + 1
    r1 = sum(r for r, (_x, g) in zip(rangs, tout) if g == 0)
    u = r1 - n1 * (n1 + 1) / 2
    mu = n1 * n2 / 2
    n = n1 + n2
    var = n1 * n2 / 12 * ((n + 1) - egal / (n * (n - 1)))
    if var <= 0:
        return 1.0
    z = (abs(u - mu) - 0.5) / math.sqrt(var)
    return max(0.0, min(1.0, math.erfc(max(0.0, z) / math.sqrt(2))))


def _nettoyer(ventes):
    """Une vente une fois (par lien, sinon titre+date+prix), puis sans les prix aberrants."""
    import cartes_match
    vus, l = set(), []
    for v in ventes:
        k = v.get("url") or (v.get("titre"), v.get("le"), v.get("prix"))
        if k in vus or not v.get("prix") or v["prix"] <= 0:
            continue
        vus.add(k)
        l.append(v)
    if len(l) < 3:
        return l
    _m, garde = cartes_match.mediane_robuste([v["prix"] for v in l])
    lo, hi = (min(garde), max(garde)) if garde else (0, 1e12)
    return [v for v in l if lo <= v["prix"] <= hi]


def _preuve(l, n=40):
    return [{"le": v["le"], "prix": round(v["prix"], 2), "titre": (v.get("titre") or "")[:120], "url": v.get("url")}
            for v in sorted(l, key=lambda v: v["le"], reverse=True)[:n]]


def _charger(jours):
    """(plan, ventes par recherche) de la base, ou (None, None)."""
    import base_ventes
    try:
        c = base_ventes._cx()
        try:
            plan = c.execute("SELECT q, cible, joueur, carte, produit FROM plan WHERE fait_le IS NOT NULL").fetchall()
            ventes = {}
            d = (datetime.now() - timedelta(days=jours)).strftime("%Y-%m-%d")
            for q, titre, prix, le, url in c.execute("SELECT q, titre, prix, le, url FROM ventes WHERE le >= ?", (d,)):
                ventes.setdefault(q, []).append({"titre": titre, "prix": prix, "le": le, "url": url})
        finally:
            c.close()
    except Exception:
        return None, None
    return plan, ventes


def analyser(maintenant=None, charger=None):
    """Toutes les cartes de la base : mouvements de prix solides et primes PSA 10 / PSA 9. Garde 1 h."""
    import cartes_match
    if charger is None and _CACHE["v"] is not None and time.time() - _CACHE["le"] < FRAICHEUR_S:
        return _CACHE["v"]
    auj = maintenant or datetime.now()
    jour = lambda n: (auj - timedelta(days=n)).strftime("%Y-%m-%d")          # noqa: E731
    d_rec, d_av1, d_av0, d_sem, d_prime = jour(RECENT_J), jour(AVANT_J[0]), jour(AVANT_J[1]), jour(SEMAINE), jour(PRIME_J)
    plan, ventes = (charger or _charger)(max(AVANT_J[1], PRIME_J) + 1)
    if plan is None:
        return None
    mouvements, primes, vues = [], [], set()
    for q, full, joueur, carte, produit in plan:
        if (full or "").lower() in vues:
            continue
        vues.add((full or "").lower())
        par_cond = {}
        for suf, lib in CONDITIONS:
            cib = cartes_match.cible(full + suf)
            l = _nettoyer([v for v in ventes.get(q) or [] if not cartes_match.raisons_refus(cib, v["titre"] or "")])
            par_cond[lib] = l
            rec = [v for v in l if v["le"] >= d_rec]
            av = [v for v in l if d_av0 <= v["le"] < d_av1]
            if len(rec) < MIN_VENTES or len(av) < MIN_VENTES or max(v["le"] for v in rec) < d_sem:
                continue
            a, b = statistics.median(v["prix"] for v in av), statistics.median(v["prix"] for v in rec)
            if a <= 0:
                continue
            pct = 100 * (b - a) / a
            p = _p_mann_whitney([v["prix"] for v in rec], [v["prix"] for v in av])
            if abs(pct) >= SEUIL_PCT and p < P_MAX:
                mouvements.append({"joueur": joueur, "carte": carte, "produit": produit, "condition": lib, "pct": round(pct),
                                   "avant": round(a, 2), "recent": round(b, 2), "n_avant": len(av), "n_recent": len(rec), "p": round(p, 4),
                                   "du": min(v["le"] for v in av), "au": max(v["le"] for v in rec),
                                   "preuve": {"recent": _preuve(rec), "avant": _preuve(av)}})
        p10 = [v for v in par_cond.get("PSA 10") or [] if v["le"] >= d_prime]
        p9 = [v for v in par_cond.get("PSA 9") or [] if v["le"] >= d_prime]
        if len(p10) >= MIN_VENTES and len(p9) >= MIN_VENTES:
            m10, m9 = statistics.median(v["prix"] for v in p10), statistics.median(v["prix"] for v in p9)
            if m9 > 0 and m10 > m9 and _p_mann_whitney([v["prix"] for v in p10], [v["prix"] for v in p9]) < P_MAX:
                primes.append({"joueur": joueur, "carte": carte, "produit": produit, "ratio": round(m10 / m9, 1),
                               "m10": round(m10, 2), "m9": round(m9, 2), "n10": len(p10), "n9": len(p9),
                               "preuve": {"PSA 10": _preuve(p10), "PSA 9": _preuve(p9)}})
    out = {"hausses": sorted((m for m in mouvements if m["pct"] > 0), key=lambda m: (m["p"], -m["pct"])),
           "baisses": sorted((m for m in mouvements if m["pct"] < 0), key=lambda m: (m["p"], m["pct"])),
           # la plus SOLIDE (le plus de ventes), jamais la plus extreme
           "primes": sorted(primes, key=lambda m: -(m["n10"] + m["n9"])), "le": auj.isoformat(timespec="minutes")}
    if charger is None:
        _CACHE.update(le=time.time(), v=out)
    return out


def _cond_txt(m, t):
    return m["condition"] or t("brute (non gradée)", "raw (ungraded)")


def _jours_fr(d):
    try:
        return datetime.fromisoformat(d).strftime("%d/%m")
    except ValueError:
        return d


def nouvelle_mouvement(sens, langue="fr", a=None):
    import astuces
    t = astuces.T(langue)
    a = a if a is not None else analyser()
    l = (a or {}).get("hausses" if sens > 0 else "baisses") or []
    if not l:
        return None
    m = l[0]
    nom = " ".join(x for x in (m["joueur"], m["carte"]) if x)
    cond = _cond_txt(m, t)
    signe = "+" if m["pct"] > 0 else "−"
    return {"id": "marche_hausse" if sens > 0 else "marche_baisse", "niveau": "tous", "genre": "info", "marche": True,
            "titre": t(f"{nom} ({cond}) : {signe}{abs(m['pct'])} % en 2 semaines",
                       f"{nom} ({cond}): {signe}{abs(m['pct'])}% in 2 weeks"),
            "chiffre": f"{signe}{abs(m['pct'])} %",
            "texte": t(f"Prix médian vendu : {m['recent']:.0f} $ sur {m['n_recent']} ventes des 14 derniers jours, contre "
                       f"{m['avant']:.0f} $ sur {m['n_avant']} ventes il y a 15 à 45 jours. Même carte, même condition.",
                       f"Median sold price: ${m['recent']:.0f} over {m['n_recent']} sales in the last 14 days, vs ${m['avant']:.0f} "
                       f"over {m['n_avant']} sales 15 to 45 days ago. Same card, same condition."),
            "truc": t("Ce qui s’est vendu, pas une prédiction : le prix peut repartir dans l’autre sens. Regarde les ventes "
                      "toi-même avant de décider.",
                      "What sold, not a prediction: the price can go the other way. Look at the sales yourself before deciding."),
            "source": t(f"{m['n_recent'] + m['n_avant']} ventes eBay réelles (SoldComps), du {_jours_fr(m['du'])} au "
                        f"{_jours_fr(m['au'])}, calcul SlabCoach",
                        f"{m['n_recent'] + m['n_avant']} real eBay sales (SoldComps), {m['du']} to {m['au']}, SlabCoach math"),
            "lien": "#valeur/" + nom + (" " + m["condition"] if m["condition"] else ""), "calcule": True,
            "preuve": [{"titre": t("14 derniers jours", "Last 14 days"), "ventes": m["preuve"]["recent"]},
                       {"titre": t("Il y a 15 à 45 jours", "15 to 45 days ago"), "ventes": m["preuve"]["avant"]}]}


def nouvelle_prime(langue="fr", a=None):
    import astuces
    t = astuces.T(langue)
    a = a if a is not None else analyser()
    l = (a or {}).get("primes") or []
    if not l:
        return None
    m = l[0]
    nom = " ".join(x for x in (m["joueur"], m["carte"]) if x)
    return {"id": "marche_prime", "niveau": "tous", "genre": "info", "marche": True,
            "titre": t(f"{nom} : une PSA 10 se vend {m['ratio']:.1f}× une PSA 9", f"{nom}: a PSA 10 sells for {m['ratio']:.1f}× a PSA 9"),
            "chiffre": f"×{m['ratio']:.1f}",
            "texte": t(f"Sur 45 jours : PSA 10, médiane {m['m10']:.0f} $ ({m['n10']} ventes) ; PSA 9, médiane {m['m9']:.0f} $ "
                       f"({m['n9']} ventes). Même carte.",
                       f"Over 45 days: PSA 10, median ${m['m10']:.0f} ({m['n10']} sales); PSA 9, median ${m['m9']:.0f} "
                       f"({m['n9']} sales). Same card."),
            "truc": t("L’écart dit combien vaut un point de note sur cette carte. Il change d’une carte à l’autre.",
                      "The gap shows what one grade point is worth on this card. It changes from card to card."),
            "source": t(f"{m['n10'] + m['n9']} ventes eBay réelles (SoldComps), 45 derniers jours, calcul SlabCoach",
                        f"{m['n10'] + m['n9']} real eBay sales (SoldComps), last 45 days, SlabCoach math"),
            "lien": "#valeur/" + nom + " PSA 10", "calcule": True,
            "preuve": [{"titre": "PSA 10", "ventes": m["preuve"]["PSA 10"]}, {"titre": "PSA 9", "ventes": m["preuve"]["PSA 9"]}]}
