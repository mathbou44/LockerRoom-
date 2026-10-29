"""
SLABCOACH - les produits et les inserts appris tout seuls (31 oct 2026).

Mathieu : « on peut pas integrer un auto-learn pour les cartes non reconnues ? »

Une carte dont on ne connait pas le produit (Tim Hortons NHL Signatures, SP Rookie Authentics, Credentials Debut Ticket
Access...) donnait une recherche de ventes trop large (« brady tkachuk auto ») et ses comps se perdaient. On apprend donc,
sans rien taper, les noms qui disent QUELLE carte c'est :
  1. le catalogue de l'admin : le nom de chaque produit et de chacun de ses sous-ensembles (checklists importees) ;
  2. le calendrier des sorties (Upper Deck, Topps...) : le nom des produits ;
  3. les annonces vues par le chasseur : une expression de 2 ou 3 mots qui revient dans au moins MIN_TITRES titres
     differents, chez au moins MIN_JOUEURS joueurs differents (un insert couvre plusieurs joueurs ; un nom de joueur, non).
Ces expressions servent a la RECHERCHE de ventes seulement (le tri des comps reste le meme : meme carte, meme variante) :
apprendre un mauvais mot ne peut pas donner un faux comp, au pire une recherche un peu plus etroite.
"""
import json
import os
import re
import threading
import time

MIN_TITRES = 6
MIN_JOUEURS = 3
MAX_APPRIS = 400
RELIRE_S = 600
_verrou = threading.Lock()
_MEMO = {"le": 0.0, "phrases": None}
# mots qui ne nomment jamais un produit ni un insert (en plus des mots generiques de cartes_match)
_BRUIT = set("""card cards rookie rookies auto autograph autographs signed patch jersey relic numbered parallel insert base
hockey nhl lnh nba nfl mlb psa bgs sgc cgc beckett gem mint graded raw lot ssp short print rare sp hot see pics pic look
new invest investment free shipping ship upper deck ud panini topps the and with for of in on from by""".split())


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "produits_appris.json")


def _lire():
    try:
        with open(_chemin(), encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def _ecrire(d):
    p = _chemin()
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(p + ".tmp", p)


def _nettoyer(nom):
    """« 2020-21 Upper Deck Tim Hortons Hockey » -> « tim hortons » ; « NHL Signatures » -> « nhl signatures »."""
    import cartes_match
    t = cartes_match.norm(nom)
    t = re.sub(r"\b(19|20)\d{2}(-\d{2,4})?\b", " ", t)
    t = re.sub(r"\b(upper deck|ud|panini|topps|hockey|basketball|football|baseball|soccer|cards?|hobby|retail|blaster|box)\b", " ", t)
    mots = [w for w in t.split() if len(w) >= 2 and w.replace("-", "").replace("'", "").isalpha()]     # pas de « /1000 », « 26 »
    if not mots or all(w in _BRUIT or w in cartes_match.GENERIQUES for w in mots):
        return None
    return " ".join(mots[:4])


def _du_catalogue():
    out = set()
    try:
        import catalogue
        for p in catalogue.liste():
            n = _nettoyer(p.get("nom") or "")
            if n:
                out.add(n)
            try:
                for s in catalogue.charger(p["id"]).get("sous_ensembles") or []:
                    n = _nettoyer(s.get("nom") or "")
                    if n:
                        out.add(n)
            except Exception:
                continue
    except Exception:
        pass
    return out


def _des_sorties():
    out = set()
    try:
        import sorties
        for x in (sorties._lire().get("produits") or []):
            if x.get("sport") in ("hockey", None):
                n = _nettoyer(x.get("nom") or "")
                if n:
                    out.add(n)
    except Exception:
        pass
    return out


def apprendre(titres):
    """Les annonces d'un tour du chasseur -> expressions qui reviennent chez plusieurs joueurs (2 ou 3 mots)."""
    import cartes_match
    gen = cartes_match.GENERIQUES | _BRUIT
    compte, joueurs = {}, {}
    vus = set()
    for t0 in titres or []:
        t = cartes_match.norm(t0 or "")
        if not t or t in vus:
            continue
        vus.add(t)
        j = cartes_match.joueur_du_titre(t0)
        jm = set((j or "").split())
        t2 = re.sub(r"\b(19|20)\d{2}(-\d{2,4})?\b|#\s*\S+|/\s*\d+|\d+", " | ", t)
        for bloc in re.split(r"\s*\|\s*", t2):
            m = [w for w in bloc.split() if w.isalpha()]
            for n in (2, 3):
                for i in range(len(m) - n + 1):
                    g = m[i:i + n]
                    if any(w in jm for w in g) or all(w in gen for w in g) or g[0] in _BRUIT or g[-1] in _BRUIT \
                            or any(len(w) < 3 for w in g):
                        continue
                    k = " ".join(g)
                    compte[k] = compte.get(k, 0) + 1
                    joueurs.setdefault(k, set()).add(j or t)
    nouveaux = {k: c for k, c in compte.items() if c >= MIN_TITRES and len(joueurs[k]) >= MIN_JOUEURS}
    # une expression de 3 mots qui contient une de 2 mots aussi frequente : on garde la plus longue
    for k in list(nouveaux):
        if len(k.split()) == 2 and any(k in k3 and nouveaux[k3] >= nouveaux[k] * 0.8 for k3 in nouveaux if len(k3.split()) == 3):
            nouveaux.pop(k, None)
    with _verrou:
        d = _lire()
        a = d.setdefault("annonces", {})
        maint = time.strftime("%Y-%m-%d")
        for k, c in nouveaux.items():
            x = a.setdefault(k, {"n": 0, "premier": maint})
            x["n"], x["vu"] = max(x["n"], c), maint
        if len(a) > MAX_APPRIS:                                # les plus vues seulement
            d["annonces"] = dict(sorted(a.items(), key=lambda kv: -kv[1]["n"])[:MAX_APPRIS])
        _ecrire(d)
    _MEMO["le"] = 0.0
    return len(nouveaux)


def phrases():
    """Toutes les expressions connues (catalogue + sorties + apprises), les plus longues d'abord. Gardees 10 min."""
    if _MEMO["phrases"] is not None and time.time() - _MEMO["le"] < RELIRE_S:
        return _MEMO["phrases"]
    s = _du_catalogue() | _des_sorties() | set((_lire().get("annonces") or {}).keys())
    l = sorted(s, key=lambda x: (-len(x.split()), -len(x)))
    rx = re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(x) for x in l) + r")(?![a-z0-9])") if l else None
    _MEMO.update(le=time.time(), phrases=l, rx=rx)
    return l


def dans(titre_norm, exclure=()):
    """Les expressions connues presentes dans un titre (deja normalise), sans chevauchement, dans l'ordre du titre
    (une seule expression reguliere : rapide, meme pour des milliers de titres par tour)."""
    phrases()
    rx = _MEMO.get("rx")
    if rx is None:
        return []
    return [m.group(0) for m in rx.finditer(titre_norm) if not all(w in exclure for w in m.group(0).split())]
