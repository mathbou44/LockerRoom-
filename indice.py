"""
SLABCOACH - l'Indice SlabCoach (27 oct 2026, Mathieu : « que ca devienne notre indice a l'aide des donnees PSA ;
les stats les plus utiles et precises possible pour les consommateurs »).

Deux mesures, calculees a partir des VRAIES ventes (base des ventes SlabCoach + ventes des produits du catalogue)
et, quand on la connait, de la population PSA de la carte (psa.py). Methode v1, publique (feuille « Comment c'est
calcule » dans l'app) : pas de boite noire, chaque chiffre montre son nombre de ventes.

1. Indice d'une carte (0 a 100) :
   - Elan (45 %)      : mediane des ventes des 30 derniers jours vs les 60 jours d'avant. 0 % = 50 ; +50 % ou plus = 100 ;
                        -50 % ou moins = 0.
   - Liquidite (30 %) : ventes par semaine (echelle log : 20 ventes / semaine et plus = 100). Une carte qui se vend vite
                        se revend vite.
   - Rarete PSA (25 %): nouvelles gradations PSA sur 30 jours, en % de la population. 0 % = 100 ; 25 % et plus = 0.
                        Sans donnees PSA : Elan 60 %, Liquidite 40 %, et l'indice le dit.
   Confiance : elevee (20 ventes et plus), moyenne (8 a 19), faible (moins de 8).
2. Indice du marche (hockey) : variation moyenne ponderee des cartes suivies (poids = racine du nombre de ventes,
   variations bornees a +-60 % pour qu'une carte folle ne fasse pas tout bouger), part des cartes en hausse,
   et, si PSA est active, la croissance des gradations des fiches suivies.
A titre informatif seulement : ce n'est pas un conseil financier.
"""
import math
from datetime import date

METHODE = "v1"


def _borne(v, a, b):
    return max(a, min(b, v))


def _ventes_semaine(x):
    if x.get("n_7j") is not None:
        return float(x["n_7j"])
    pts = [p for p in (x.get("points") or []) if p and p[0]]
    n = x.get("n") or len(pts)
    if len(pts) < 2:
        return None
    try:
        d = sorted(date.fromisoformat(str(p[0])[:10]) for p in pts)
        semaines = max(1.0, (d[-1] - d[0]).days / 7)
    except ValueError:
        return None
    return n / semaines


def carte(x):
    """Indice d'une carte des tendances -> {score, elan, liquidite, rarete, ventes_sem, confiance, avec_psa} ou None."""
    pct = x.get("pct")
    vps = _ventes_semaine(x)
    if pct is None and vps is None:
        return None
    elan = round(50 + _borne(float(pct), -50, 50)) if pct is not None else None
    liq = round(_borne(100 * math.log10(1 + vps) / math.log10(21), 0, 100)) if vps is not None else None
    p = x.get("psa") or {}
    c = p.get("croissance_pct")
    rar = round(_borne(100 - 4 * float(c), 0, 100)) if c is not None else None
    parts = [(elan, .45), (liq, .30), (rar, .25)] if rar is not None else [(elan, .60), (liq, .40)]
    parts = [(v, w) for v, w in parts if v is not None]
    tot = sum(w for _v, w in parts)
    score = round(sum(v * w for v, w in parts) / tot) if tot else None
    n = x.get("n_t") or x.get("n") or 0
    return {"score": score, "elan": elan, "liquidite": liq, "rarete": rar,
            "ventes_sem": round(vps, 1) if vps is not None else None,
            "confiance": "elevee" if n >= 20 else "moyenne" if n >= 8 else "faible", "n": n, "avec_psa": rar is not None,
            "methode": METHODE}


def marche(cartes, psa_stats=None):
    """Indice du marche a partir de TOUTES les cartes mesurees (pas seulement les tops affiches)."""
    l = [x for x in cartes or [] if x.get("pct") is not None]
    if not l:
        return None
    poids = [(math.sqrt(max(1, x.get("n_t") or x.get("n") or 1)), _borne(float(x["pct"]), -60, 60)) for x in l]
    w = sum(p for p, _v in poids)
    out = {"variation": round(sum(p * v for p, v in poids) / w, 1), "hausse_pct": round(100 * sum(1 for x in l if x["pct"] > 0) / len(l)),
           "n_cartes": len(l), "n_ventes": sum(int(x.get("n") or 0) for x in l), "fenetre": "30 j vs 60 j d'avant", "methode": METHODE}
    st = [s for s in (psa_stats or []) if s and s.get("nouvelles_30j") is not None and s.get("pop")]
    if st:
        nouv = sum(s["nouvelles_30j"] for s in st)
        base = sum(s["pop"] - s["nouvelles_30j"] for s in st)
        gems = [s["gem_pct"] for s in st if s.get("gem_pct") is not None]
        out["psa"] = {"fiches": len(st), "nouvelles_30j": nouv, "croissance_pct": round(100 * nouv / base, 1) if base > 0 else None,
                      "gem_moyen": round(sum(gems) / len(gems)) if gems else None}
    return out
