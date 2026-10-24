"""
LOCKERROOM - sante de l'inventaire (tous les articles eBay, toutes categories).

Pour chaque annonce active : son prix face aux annonces semblables (API
Browse, prix fixe), son age et ses watchers ->
  baisser : plus de 15 % au-dessus du marche
  monter  : plus de 20 % sous le marche
  traine  : 60 jours et plus sans vendre
  ok
et pour ce qui s'est bien vendu : les annonces neuves au moins 30 % moins
cheres que ton prix de vente (« a racheter »).

Rien n'est modifie sur eBay : l'app suggere un prix, le vendeur decide.
"""
import math
import re
import statistics
from datetime import datetime, timedelta

HAUT, BAS = 1.15, 0.80
MIN_ANNONCES = 5
TRAINE_JOURS = 60
RACHAT_RATIO = 0.70
_VIDES = set("""a an and the of for with in on to by new neuf neuve lot free shipping fast ship rare htf look wow nice
mint nm near brand sealed vintage authentic genuine original oem nib nwt nwot box l k mint+ comme
de du des la le les et en avec pour sans""".split())


def requete(titre, max_mots=8):
    """Titre -> mots-cles de recherche (sans bruit, ni emoji, ni numeros d'exemplaire)."""
    t = re.sub(r"\b\d{1,4}\s*/\s*(\d{1,4})\b", r"/\1", str(titre or ""))
    mots = re.findall(r"/\d{1,4}\b|[A-Za-z0-9][A-Za-z0-9'#\-.]*", t)
    out = []
    for m in mots:
        b = m.lower().strip(".-'")
        if not b or b in _VIDES or (len(b) == 1 and not b.isdigit()):
            continue
        if b not in (x.lower() for x in out):
            out.append(m.strip(".-'"))
        if len(out) >= max_mots:
            break
    return " ".join(out)


def prix_rond(v):
    """39.37 -> 38.99 ; sous 5 $ : 2 decimales."""
    if v is None:
        return None
    return round(max(0.99, math.floor(v) - 0.01), 2) if v >= 5 else round(v, 2)


def age_jours(debut):
    try:
        d = datetime.fromisoformat(str(debut).replace("Z", "+00:00")).replace(tzinfo=None)
        return max(0, (datetime.utcnow() - d).days)
    except (TypeError, ValueError):
        return None


def evaluer(prix, semblables, age=None, watchers=None):
    """{verdict, suggestion, mediane, n, ecart} d'une annonce."""
    prix = float(prix or 0)
    totaux = [s["prix_cad"] + (s.get("port_cad") or 0) for s in semblables if s.get("prix_cad")]
    n = len(totaux)
    med = round(statistics.median(totaux), 2) if totaux else None
    ecart = round(prix / med - 1, 3) if med else None
    verdict, sugg = "ok", None
    if med and n >= MIN_ANNONCES and prix > med * HAUT:
        verdict, sugg = "baisser", prix_rond(med * 0.98)
    elif med and n >= MIN_ANNONCES and prix < med * BAS:
        verdict, sugg = "monter", prix_rond(med * 0.95)
    elif age is not None and age >= TRAINE_JOURS:
        verdict, sugg = "traine", prix_rond(prix * (0.90 if not watchers else 0.95))
    return {"verdict": verdict, "suggestion": sugg, "mediane": med, "n": n, "ecart": ecart}


def opportunites(ref_prix, trouvees, exclure=()):
    """Annonces au moins 30 % sous ce que l'article s'est vendu chez toi."""
    out = []
    for a in trouvees:
        if a["item_id"] in exclure:
            continue
        total = a["prix_cad"] + (a.get("port_cad") or 0)
        if ref_prix and total <= ref_prix * RACHAT_RATIO:
            out.append(dict(a, total=round(total, 2), ratio=round(total / ref_prix, 2)))
    return sorted(out, key=lambda x: x["ratio"])
