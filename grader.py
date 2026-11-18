"""
SLABCOACH - « Grader ? » : vaut-il la peine de faire grader cette carte ? (17 nov 2026)

Mathieu : « certaines cartes, le monde les achete pour les faire grader, puis les revendent et font des sous ; comment
l'integrer sans etre trop lourd ». Un verdict la ou on regarde deja la carte (la fiche, l'inventaire, apres le pre-grade).

Le calcul (la MEME carte, nos ventes reelles, 365 jours, les plus recentes d'abord) :
  - la valeur brute, PSA 10, PSA 9 et PSA 8 (medianes des ventes ; PSA 8 absent : 85 % de la brute) ;
  - la chance d'un 10 : le pre-grade photo s'il y en a un ; sinon la part des PSA 10 parmi les PSA vendues de cette carte,
    reduite de 30 % (on revend plus souvent un 10 qu'un 8 : la part vue est trop belle), entre 5 % et 70 % ;
  - le gain espere = chances x (prix de revente - frais eBay) - la brute (ce que la carte vaut deja) - frais PSA et envoi ;
  - le seuil : la chance d'un 10 qu'il faut pour ne pas perdre d'argent.
Verdict : « oui » (gain espere >= 15 $ et >= 15 % de la brute), « peut-etre » (positif, plus petit), « non ».
Les montants suivent la regle des comps (admin / Platine) ; le verdict et les multiples aussi pour l'instant.
"""
import re
import statistics

FRAIS_PSA = 35.0          # $ CA par carte (forfait « Value » ~25 $ US) ; reglage « frais_psa »
ENVOI_PSA = 6.0           # $ CA par carte : l'envoi aller-retour et l'assurance, en lot
JOURS = 120


def chance_10_pregrade(note):
    try:
        n = float(note)
    except (TypeError, ValueError):
        return None
    for seuil, p in ((9.5, 0.6), (9, 0.3), (8.5, 0.12), (8, 0.05)):
        if n >= seuil:
            return p
    return 0.02


def _med(points, jours=JOURS):
    from datetime import datetime, timedelta
    lim = (datetime.now() - timedelta(days=jours)).strftime("%Y-%m-%d")
    p = [x[1] for x in points if x[0] >= lim] or [x[1] for x in points[-6:]]
    return statistics.median(p) if len(p) >= 2 else None, len(p)


def calculer(series, note=None, frais_pct=0.1325, frais_fixe=0.40, frais_psa=FRAIS_PSA):
    """series = vendues.par_gradation()["series"] (toutes les gradations, pas seulement 4) -> verdict."""
    S = {s["cle"]: s for s in series or []}
    brute = S.get("brute")
    psa = {k: v for k, v in S.items() if k.startswith("psa ")}
    p10s = S.get("psa 10")
    if not brute or not p10s:
        return {"ok": False, "raison": "peu de ventes"}
    vb, nb = _med(brute["points"])
    v10, n10 = _med(p10s["points"])
    if not vb or not v10 or nb < 3 or n10 < 3:
        return {"ok": False, "raison": "peu de ventes"}
    v9 = _med(psa["psa 9"]["points"])[0] if "psa 9" in psa else None
    v8 = _med(psa["psa 8"]["points"])[0] if "psa 8" in psa else None
    v9 = v9 or (v10 * 0.45)
    v8 = v8 or vb * 0.85
    p10 = chance_10_pregrade(note)
    source = "pregrade" if p10 is not None else "marche"
    if p10 is None:
        tot = sum(len(v["points"]) for v in psa.values())
        p10 = max(0.05, min(0.7, 0.7 * len(p10s["points"]) / tot)) if tot else 0.25
    p9 = (1 - p10) * 0.55
    p8 = 1 - p10 - p9
    net = lambda v: v * (1 - frais_pct) - frais_fixe
    cout = vb + frais_psa + ENVOI_PSA
    ev = p10 * net(v10) + p9 * net(v9) + p8 * net(v8) - cout
    # la chance d'un 10 qu'il faut pour ne pas perdre (le reste reparti comme plus haut)
    def gain(p):
        q9 = (1 - p) * 0.55
        return p * net(v10) + q9 * net(v9) + (1 - p - q9) * net(v8) - cout
    seuil = None
    for i in range(0, 101):
        if gain(i / 100) >= 0:
            seuil = i / 100
            break
    verdict = "oui" if ev >= max(15.0, 0.15 * vb) else "peut-etre" if ev > 0 else "non"
    return {"ok": True, "verdict": verdict, "multiple": round(v10 / vb, 1), "chance_10": round(p10, 2), "source": source,
            "seuil_10": seuil, "gain": round(ev, 2), "brute": round(vb, 2), "psa10": round(v10, 2), "psa9": round(v9, 2),
            "frais": round(frais_psa + ENVOI_PSA, 2), "n_brute": nb, "n_psa10": n10}


_RE_GRADE = re.compile(r"\b(psa|bgs|sgc|cgc|tag|beckett|ksa)\s*\d", re.I)


def gradee(titre):
    return bool(_RE_GRADE.search(titre or ""))
