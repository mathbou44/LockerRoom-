"""
SLABCOACH - la rarete d'une carte d'apres NOTRE catalogue (11 nov 2026, SlabIQ).

Pour un titre : le produit (saison + nom) et le sous-ensemble (insert, parallele) qui lui ressemblent le plus dans nos
checklists, puis sa rarete publique : combien de boites il faut ouvrir pour UNE carte precise de ce sous-ensemble
(cotes de la composition / nombre de cartes), le tirage, la taille du sous-ensemble. Aucune vente, aucun prix.
"""
import math
import re

_C = {"prods": None}
GEN = set("upper deck the of and card cards hockey nhl set base series rookie rookies autographs autograph auto autos".split())


def _mots(s):
    return set(w for w in re.findall(r"[a-z0-9]+", (s or "").lower().replace("o-pee-chee", "opc").replace("o pee chee", "opc")))


def _prods():
    if _C["prods"] is None:
        import catalogue
        out = []
        for p in catalogue.liste() or []:
            pr = catalogue.charger(p["id"]) or {}
            try:
                taux = catalogue.taux_par_boite(pr)
            except Exception:
                taux = {}
            ses = []
            for s in pr.get("sous_ensembles") or []:
                nb = s.get("nb_cartes") or len((pr.get("_par_se") or {}).get(s["nom"]) or []) or None
                t = taux.get(s["nom"])
                ses.append({"nom": s["nom"], "m": _mots(s["nom"]) - GEN, "tous": _mots(s["nom"]), "tirage": catalogue.tirage_de(s),
                            "nb": nb, "taux": t})
            an = int(str(p.get("saison") or "0")[:4] or 0)
            cle = _mots(p["nom"]) - GEN - {str(an), str(an + 1)[2:], (p.get("saison") or "")[5:]}
            cle = {w for w in cle if not re.fullmatch(r"\d{2,4}", w)}
            out.append({"id": p["id"], "an": an, "m": cle, "ses": ses})
        _C["prods"] = out
    return _C["prods"]


def rarete(b):
    """b = un « brut » (score_modele) -> [produit trouve, log10 boites par carte, log10 tirage, log10 taille, taux par boite, recouvrement]."""
    vide = [0.0, float("nan"), float("nan"), float("nan"), float("nan"), float("nan")]
    an = b.get("annee")
    if not an:
        return vide
    m = _mots(b.get("t"))
    best = None
    for p in _prods():
        if p["an"] != an or not p["m"] or not p["m"] <= m:
            continue
        if best is None or len(p["m"]) > len(best["m"]):
            best = p
    if not best:
        return vide
    sb, sc = None, 0.0
    for s in best["ses"]:
        if not s["m"]:
            continue
        cov = len(s["m"] & m) / len(s["m"])
        sco = cov + 0.01 * len(s["m"] & m)
        if cov >= 0.99 and sco > sc:
            sb, sc = s, sco
    if not sb:
        return [1.0, float("nan"), float("nan"), float("nan"), float("nan"), 0.0]
    bpc = (sb["nb"] / sb["taux"]) if sb.get("taux") and sb.get("nb") else float("nan")
    lg = lambda v: math.log10(v) if v and v > 0 else float("nan")
    return [1.0, lg(bpc), lg(sb.get("tirage")), lg(sb.get("nb")), sb.get("taux") if sb.get("taux") is not None else float("nan"), sc]
