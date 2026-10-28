"""
SLABCOACH - le pouls du hobby (27 oct 2026, Mathieu : « en ce moment, le hobby, c'est ou la grosse popularite ? Michael
Jordan ? les annees 90 ? le vintage ? le moderne ? un joueur ? Il faut trouver un moyen de le savoir, puis donner un
petit indice a l'utilisateur d'aller voir ca, sans lui dire que c'est ca »).

Comment on le sait : quelques recherches de ventes eBay REELLES (SoldComps, budget protege) par segment du hobby, refaites
tous les 3 jours. Pour chaque segment on mesure :
  - la vitesse : ventes par jour (calculee sur l'heure exacte des ventes, donc juste meme pour un segment qui vend des
    centaines de cartes par jour) ;
  - le prix : la mediane des ventes.
La chaleur compare la mesure du jour a celles des 6 a 45 derniers jours du MEME segment (jamais un segment a un autre) :
ventes qui accelerent (60 %) et prix qui montent (40 %). Sans au moins une mesure passee, le segment est « en mesure » et
on ne dit rien. L'app n'affirme jamais « c'est ca la mode » : elle donne un indice (« ca bouge du cote de... ») et montre
des ventes recentes du segment pour que l'utilisateur juge lui-meme.
"""
import json
import math
import os
import statistics
import threading
import time
from datetime import datetime, timedelta

REFAIRE_J = 3
_verrou = threading.Lock()
_ETAT = {"le": 0.0}

# cle, nom FR, nom EN, recherches SoldComps (categorie cartes de sport)
SEGMENTS = [
    ("jordan", "Michael Jordan", "Michael Jordan", ["michael jordan"]),
    ("gretzky", "Wayne Gretzky", "Wayne Gretzky", ["wayne gretzky"]),
    ("ohtani", "Shohei Ohtani", "Shohei Ohtani", ["shohei ohtani"]),
    ("wemby", "Victor Wembanyama", "Victor Wembanyama", ["victor wembanyama"]),
    ("annees90", "les inserts des années 90", "90s inserts", ["1997 insert", "1998 refractor", "1996 insert"]),
    ("annees80", "les années 80", "the 80s", ["1986 fleer", "1985 topps", "1989 upper deck"]),
    ("vintage", "le vintage (avant 1980)", "vintage (pre-1980)", ["1969 topps", "1972 topps", "1979 o-pee-chee"]),
    ("recrues", "les recrues modernes", "modern rookies", ["young guns rookie", "prizm rookie"]),
    ("psa10", "les cartes gradées PSA 10", "PSA 10 graded cards", ["psa 10 rookie"]),
    ("autos", "les autos numérotées", "numbered autos", ["auto /25", "auto /10"]),
]


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "pouls_hobby.json")


def _lire():
    try:
        with open(_chemin(), encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def _ecrire(d):
    p = _chemin()
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(d, f)
    os.replace(p + ".tmp", p)


def _moment(v):
    s = str(v.get("ts") or v.get("le") or "")
    try:
        return datetime.fromisoformat(s[:19]) if len(s) > 10 else datetime.fromisoformat(s[:10] + "T12:00:00")
    except ValueError:
        return None


def _vitesse(ventes, plein=240):
    """Ventes par jour d'une recherche : sur l'etendue reelle des ventes (heures comprises), 30 jours au plus."""
    t = sorted(m for m in (_moment(v) for v in ventes) if m)
    if len(t) < 5:
        return None
    fin, debut = t[-1], max(t[0], t[-1] - timedelta(days=30))
    n = sum(1 for m in t if m >= debut)
    jours = max(0.25, (fin - debut).total_seconds() / 86400)
    if len(ventes) < plein and (fin - t[0]).days >= 30:      # pas plein : toutes les ventes du mois sont la
        jours = 30
    return n / jours


def mesurer(cle, rechercher=None, maintenant=None):
    """Une mesure d'un segment (1 recherche SoldComps par requete, ou le cache de 3 jours)."""
    import vendues
    rechercher = rechercher or vendues.rechercher
    seg = next((s for s in SEGMENTS if s[0] == cle), None)
    if not seg:
        return None
    vit, prix, exemples, vus = 0.0, [], [], set()
    for q in seg[3]:
        r = rechercher(q, fond=True)
        if r.get("erreur") and not r.get("ventes"):
            return {"erreur": r["erreur"]}
        l = [v for v in r.get("ventes") or [] if v.get("prix")]
        x = _vitesse(l)
        if x is None:
            continue
        vit += x
        for v in l:
            k = v.get("url") or (v.get("titre"), v.get("prix"), v.get("le"))
            if k in vus:
                continue
            vus.add(k)
            prix.append(float(v["prix"]))
            exemples.append({k2: v.get(k2) for k2 in ("titre", "prix", "le", "photo", "url")})
    if len(prix) < 15:
        return None
    jour = (maintenant or datetime.now()).strftime("%Y-%m-%d")
    exemples.sort(key=lambda v: (str(v.get("le") or ""), v.get("prix") or 0), reverse=True)
    recents = sorted(exemples[:60], key=lambda v: -(v.get("prix") or 0))[:8]
    return {"le": jour, "v": round(vit, 2), "med": round(statistics.median(prix), 2), "n": len(prix), "exemples": recents}


def rafraichir(n=2, rechercher=None, maintenant=None):
    """Les segments les moins frais d'abord, au plus n par appel ; chacun au plus une fois par 3 jours."""
    maint = maintenant or datetime.now()
    with _verrou:
        d = _lire()
    segs = d.setdefault("segments", {})
    limite = (maint - timedelta(days=REFAIRE_J)).strftime("%Y-%m-%d")
    a_faire = sorted((s[0] for s in SEGMENTS if (segs.get(s[0]) or {}).get("dernier", "") <= limite),
                     key=lambda k: (segs.get(k) or {}).get("dernier", ""))[:n]
    faits = 0
    for k in a_faire:
        m = mesurer(k, rechercher, maint)
        if m is None:
            continue
        if m.get("erreur"):
            break
        s = segs.setdefault(k, {"hist": []})
        s["hist"] = [h for h in s["hist"] if h["le"] != m["le"]][-30:] + [{x: m[x] for x in ("le", "v", "med", "n")}]
        s["exemples"], s["dernier"] = m["exemples"], m["le"]
        faits += 1
    if faits:
        with _verrou:
            _ecrire(d)
    return faits


def rafraichir_si_besoin():
    """Chaque heure (boucle du serveur) : 2 segments au plus, seulement si SoldComps est actif."""
    if os.environ.get("LR_POULS", "1") == "0" or time.time() - _ETAT["le"] < 3500:
        return 0
    _ETAT["le"] = time.time()
    try:
        import vendues
        if not vendues.actif():
            return 0
        return rafraichir(2)
    except Exception as e:
        print("Pouls du hobby : " + repr(e), flush=True)
        return 0


def _chaleur(hist, maint):
    """(score, niveau) : la derniere mesure contre celles de 6 a 45 jours avant, du meme segment."""
    if not hist:
        return None, None
    der = hist[-1]
    d0 = datetime.fromisoformat(der["le"])
    avant = [h for h in hist[:-1] if 6 <= (d0 - datetime.fromisoformat(h["le"])).days <= 45]
    if not avant or (maint - d0).days > 10:
        return None, None
    bv = statistics.median(h["v"] for h in avant)
    bp = statistics.median(h["med"] for h in avant)
    if bv <= 0 or bp <= 0 or der["v"] <= 0 or der["med"] <= 0:
        return None, None
    score = 60 * math.log2(der["v"] / bv) + 40 * math.log2(der["med"] / bp)
    niveau = 3 if score >= 35 else 2 if score >= 18 else 1 if score >= 8 else -1 if score <= -15 else 0
    return round(score, 1), niveau


def resume(langue="fr", maintenant=None):
    """Les segments avec leur chaleur (None = en mesure), du plus chaud au plus froid."""
    maint = maintenant or datetime.now()
    segs = (_lire().get("segments") or {})
    out = []
    for k, fr, en, _q in SEGMENTS:
        s = segs.get(k) or {}
        sc, niv = _chaleur(s.get("hist") or [], maint)
        out.append({"cle": k, "nom": en if langue == "en" else fr, "score": sc, "chaleur": niv, "mesure": s.get("dernier"),
                    "exemples": s.get("exemples") or []})
    out.sort(key=lambda x: (x["score"] is None, -(x["score"] or 0)))
    return {"segments": out, "methode": "v1"}


def indice(langue="fr", maintenant=None):
    """Le segment qui chauffe le plus (chaleur >= 1), ou None : de quoi donner un indice, sans l'affirmer."""
    l = [x for x in resume(langue, maintenant)["segments"] if (x["chaleur"] or 0) >= 1 and x["exemples"]]
    return l[0] if l else None
