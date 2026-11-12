"""
SLABCOACH - l'ordre des credits de ventes (12 nov 2026).

Mathieu : « pour eviter de passer a cote des vraiment bons deals, on devrait y aller par ordre pour limiter le gaspillage de
credit [...] patch ou auto de bons joueurs, puis les numerotees [...] toujours dans nos bons vendeurs (Savage, Remi, CF31) [...]
les petits vendeurs, une categorie toute seule [...] les cartes gradees PSA, TAG, Beckett [...] les SP / SSP qui valent cher
[...] je veux rien savoir des cartes en bas de 30 $ vendues. »

Chaque carte a verifier recoit une note : le PROFIT ATTENDU PAR CREDIT de sa categorie (auto-patch, gradee 10, /26-99...)
pour le calibre de son joueur (bon, moyen, gris), fois le groupe de son vendeur. Les notes de depart viennent d'un test sur
38 600 ventes eBay (profit = ce qu'une vente a 70 % de la mediane ou moins laisse sur la table, cartes de 30 $ et plus) :

    auto-patch bon joueur 17,7 $/credit · gradee <9 bon 31 (vintage) · /26-99 bon 10,7 · gradee 10 bon 7,5 · auto bon 5,0
    auto gris 1,4 · recrue base gris 0,3 · parallele gris 0,2   (un bon joueur rapporte ~4 fois plus qu'un gris)

Puis le serveur APPREND : chaque verification (journal des deals) est notee dans credits_rendement.json (categorie, joueur,
groupe de vendeur, ventes trouvees, deal ou non, profit) et la note de chaque categorie glisse vers ce qu'elle rapporte
VRAIMENT (moyenne bayesienne : K credits de depart pour le test, puis les vrais). L'admin voit le rapport (« Crédits »).

Une carte dont la valeur attendue est sous 30 $ (une base ou une recrue base d'un joueur gris, a 3 $) n'est jamais verifiee.
"""
import json
import os
import threading
import time
from datetime import date, timedelta

VALEUR_MIN = 30.0                 # Mathieu : « en bas de 30 $ vendues, je m'en fous : pas assez de profit »
PLANCHER_PRIO = 10.0              # vendeurs prioritaires, bon joueur : la categorie vaut au moins 10 $ (voir note())
K_PRIOR = 40                      # le poids du test de depart (en credits) avant que les vrais resultats prennent le dessus
JOURS_GARDES = 60
_verrou = threading.Lock()
_CACHE = {"mt": None, "d": None}
_TIERS = {"le": 0.0, "bon": set(), "moyen": set()}

# (profit attendu par credit en $, valeur mediane en $) par categorie et calibre ; le test du 12 nov 2026, arrondi et
# lisse (les petits echantillons ramenes vers leurs voisins)
PRIORS = {
    "auto-patch":   {"bon": (17.0, 180), "gris": (5.0, 41)},
    "serie /25-":   {"bon": (9.0, 100), "gris": (4.5, 55)},
    "serie /26-99": {"bon": (10.0, 116), "gris": (3.9, 25)},
    "gradee 10":    {"bon": (7.5, 268), "gris": (1.8, 91)},
    "gradee <9":    {"bon": (12.0, 120), "gris": (3.0, 80)},
    "gradee 9":     {"bon": (4.5, 110), "gris": (0.8, 50)},
    "vintage":      {"bon": (12.0, 36), "gris": (2.0, 7)},
    "auto":         {"bon": (5.0, 81), "gris": (1.4, 18)},
    "patch":        {"bon": (3.7, 38), "gris": (0.5, 10)},
    "serie /100+":  {"bon": (3.0, 54), "gris": (1.5, 21)},
    "sp/ssp":       {"bon": (2.0, 30), "gris": (0.8, 6)},
    "recrue base":  {"bon": (2.0, 21), "gris": (0.3, 5)},
    "parallele":    {"bon": (1.9, 9), "gris": (0.2, 3)},
    "base":         {"bon": (1.0, 17), "gris": (0.1, 4)},
}
NOMS = {"auto-patch": "Auto-patch", "serie /25-": "Numérotée /25 et moins", "serie /26-99": "Numérotée /26 à /99",
        "gradee 10": "Gradée 10", "gradee 9": "Gradée 9 à 9,5", "gradee <9": "Gradée sous 9", "vintage": "Vintage (avant 1995)",
        "auto": "Auto", "patch": "Patch", "serie /100+": "Numérotée /100 et plus", "sp/ssp": "SP / SSP",
        "recrue base": "Recrue de base", "parallele": "Parallèle", "base": "Base"}
# le groupe du vendeur : les 4 prioritaires (finissent souvent sous la mediane, pas de port chez Savage/Remi/CF31), les
# petits vendeurs suivis (une categorie a part), les maisons a volume, les autres
GROUPES = {"prio": 1.5, "petit": 1.25, "autre": 1.0, "volume": 0.8}
# Mathieu : « on priorise nos meilleurs vendeurs et les petits vendeurs, ensuite les moins bons (Probstein en dernier) » :
# l'ORDRE suit d'abord le groupe du vendeur, puis la note de la carte
GROUPE_RANG = {"prio": 0, "petit": 1, "autre": 2, "volume": 3}
# Mathieu : « les USA, il y a 50 % du prix paye en surplus (douanes, change) : ce n'est que tres rarement des deals ; on
# priorise le Canada ». Sur le test (38 600 ventes), une carte achetee aux Etats-Unis avec 49,7 % de frais rapporte 0,57 fois
# le profit d'une carte au Canada et 0,48 fois les deals -> 0,45. LR_CREDITS_ETRANGER pour changer.
try:
    FACTEUR_ETRANGER = max(0.0, min(1.0, float(os.environ.get("LR_CREDITS_ETRANGER") or 0.45)))
except ValueError:
    FACTEUR_ETRANGER = 0.45
NOMS_GROUPES = {"prio": "Vendeurs prioritaires", "petit": "Petits vendeurs suivis", "autre": "Autres vendeurs", "volume": "Maisons à volume"}


# -- la categorie d'une carte ---------------------------------------------------------------------------------------------
def etiquettes(cib):
    """Toutes les categories d'une carte (une Caufield Emerald Surge 1/10 PSA 8 : « serie /25- » et « gradee <9 »)."""
    s, a, p = cib.get("serie"), cib.get("auto"), cib.get("patch")
    L = []
    if a and p:
        L.append("auto-patch")
    elif a:
        L.append("auto")
    elif p:
        L.append("patch")
    try:
        s = int(s) if s else None
    except (TypeError, ValueError):
        s = None
    if s:
        L.append("serie /25-" if s <= 25 else "serie /26-99" if s <= 99 else "serie /100+")
    g = cib.get("grade")
    if g:
        n = str((g or {}).get("note") or "")
        try:
            nf = float(n.replace(",", "."))
        except ValueError:
            nf = None
        L.append("gradee 10" if nf is not None and nf >= 10 else "gradee 9" if nf is not None and nf >= 9 else "gradee <9")
    an = cib.get("annee")
    try:
        if an and int(an) < 1995:
            L.append("vintage")
    except (TypeError, ValueError):
        pass
    par = cib.get("paralleles") or set()
    if "ssp" in par or "sp" in par:
        L.append("sp/ssp")
    if not L:
        L.append("recrue base" if cib.get("rc") else ("parallele" if par else "base"))
    return L


def _charger_tiers():
    """Les bons joueurs (top 15 % de l'Indice SlabIQ, legendes, vedettes du chasseur) et les moyens (15 a 40 %)."""
    if time.time() - _TIERS["le"] < 3600 and (_TIERS["bon"] or _TIERS["moyen"]):
        return
    bon, moyen = set(), set()
    try:
        import indice_joueurs
        import cartes_match
        I = indice_joueurs.lire().get("indice") or {}
        l = sorted(((v.get("indice") or 0, n, v) for n, v in I.items()), key=lambda x: -x[0])
        for i, (ix, n, v) in enumerate(l):
            k = cartes_match.norm(n)
            if i < len(l) * 0.15 or "legende" in (v.get("pastilles") or []):
                bon.add(k)
            elif i < len(l) * 0.40:
                moyen.add(k)
    except Exception:
        pass
    _TIERS.update(le=time.time(), bon=bon, moyen=moyen)


def calibre(joueur):
    """bon / moyen / gris : le calibre du joueur pour les credits."""
    if not joueur:
        return "gris"
    try:
        import cartes_match
        k = cartes_match.norm(joueur)
    except Exception:
        k = str(joueur).lower()
    _charger_tiers()
    if k in _TIERS["bon"]:
        return "bon"
    try:
        import deals
        if _VEDETTES["k"] is None:
            _VEDETTES["k"] = {deals._cle_nom(n) for n in deals.VEDETTES}
        if deals._cle_nom(joueur) in _VEDETTES["k"]:
            return "bon"
    except Exception:
        pass
    return "moyen" if k in _TIERS["moyen"] else "gris"


def _prior(cat, cal):
    p = PRIORS.get(cat) or PRIORS["base"]
    if cal == "moyen":       # entre les deux (moyenne geometrique)
        b, g = p["bon"], p["gris"]
        return ((b[0] * max(g[0], 0.05)) ** 0.5, (b[1] * g[1]) ** 0.5)
    return p.get(cal) or p["gris"]


_VEDETTES = {"k": None}
_GR = {"le": 0.0, "d": {}}


def groupe_vendeur(v):
    """Le groupe du vendeur (garde 2 min : appele pour chaque annonce d'un tour)."""
    v = str(v or "").lower()
    if time.time() - _GR["le"] > 120:
        _GR.update(le=time.time(), d={})
    g = _GR["d"].get(v)
    if g is None:
        g = _GR["d"][v] = _groupe_vendeur(v)
    return g


def _groupe_vendeur(v):
    try:
        import deals
        r = deals.rang_vendeur(str(v or "").lower())
        if r < len(deals.VENDEURS_PRIORITE):
            return "prio"
        if str(v or "").lower() in deals.vendeurs_dernier():
            return "volume"
        if r == 4:
            return "petit"
    except Exception:
        pass
    return "autre"


# -- le registre (ce que chaque categorie rapporte vraiment) -------------------------------------------------------------
def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "credits_rendement.json")


def lire():
    p = _chemin()
    try:
        mt = os.path.getmtime(p)
    except OSError:
        return {}
    if _CACHE["mt"] != mt:
        try:
            with open(p, encoding="utf-8") as f:
                _CACHE["d"] = json.load(f) or {}
            _CACHE["mt"] = mt
        except (OSError, ValueError):
            return _CACHE["d"] or {}
    return _CACHE["d"] or {}


def _cle(cat, cal):
    return cat + "|" + cal


def appris(cat, cal):
    """Le profit par credit de la categorie : le test de depart, puis les vrais resultats (moyenne bayesienne)."""
    p = _prior(cat, cal)[0]
    s = (lire().get("cles") or {}).get(_cle(cat, cal))
    if not s:
        return p
    n, gain = s[0], s[3]
    return (p * K_PRIOR + gain) / (K_PRIOR + n)


def note(cib, total=None, vendeur=None, connue=None, annonce=None):
    """-> (note, categorie, calibre, valeur attendue). note 0 = ne pas depenser de credit.
    total : le prix (port compris) ou la mise ; connue : une valeur deja connue (quelques ventes) ; annonce : pour son pays
    (hors Canada : les frais d'importation, FACTEUR_ETRANGER)."""
    cal = calibre(cib.get("joueur"))
    L = etiquettes(cib)
    vals = [(appris(c, cal), _prior(c, cal)[1], c) for c in L]
    vals.sort(key=lambda x: -x[0])
    ppc, med, cat = vals[0]
    ppc += 0.3 * sum(v[0] for v in vals[1:])         # une auto numerotee gradee vaut plus que chacune
    med = max(v[1] for v in vals)
    k = 1.0
    if annonce is not None:
        if annonce.get("encan"):
            k = 1.5 if _heures(annonce) <= 6 else 1.0       # une mise a 6 h de la fin dit deja quelque chose ; a 2 jours, non
        else:
            k = 1 / 0.7                                     # un prix fixe qui serait un deal : la carte vaut au moins prix / 0,7
    est = max(med, float(total or 0) * k, float(connue or 0))
    g = groupe_vendeur(vendeur)
    # Mathieu (30 oct) : chez Savage, Remi, CF31, « c'est la carte qui compte, pas la mise » (une mise de 3 $ a 2 jours de la
    # fin) : un bon joueur (ou moyen) y est verifie des que sa categorie vaut 10 $ et plus (Canvas, Clear Cut, Young Guns)
    plancher = PLANCHER_PRIO if g == "prio" and cal in ("bon", "moyen") else VALEUR_MIN
    if est < plancher:
        return 0.0, cat, cal, round(est, 2)
    f = GROUPES.get(g, 1.0)
    if annonce is not None:
        try:
            import deals
            if deals.etranger(annonce):
                f *= FACTEUR_ETRANGER
        except Exception:
            pass
    return round(ppc * f, 3), cat, cal, round(est, 2)


def _heures(a):
    from datetime import datetime, timezone
    try:
        return (datetime.fromisoformat(str(a.get("fin")).replace("Z", "+00:00")) - datetime.now(timezone.utc)).total_seconds() / 3600
    except (TypeError, ValueError):
        return 99.0


def vaut(cib, total=None, vendeur=None, connue=None, annonce=None):
    return note(cib, total, vendeur, connue, annonce)[0] > 0


def cle_ordre(cib, total=None, vendeur=None, annonce=None, urgence=1.0):
    """La cle de tri des verifications : le groupe du vendeur (prioritaires, petits, autres, maisons a volume), puis la
    note de la carte (le Canada avant les Etats-Unis : la note d'une carte etrangere est reduite)."""
    return (GROUPE_RANG.get(groupe_vendeur(vendeur), 2), -note(cib, total, vendeur, annonce=annonce)[0] * urgence)


def noter(cib, vendeur, total, res, ratio, cache=False, n_ventes=0, encan=False):
    """Une verification faite : ce qu'elle a rapporte. Une recherche en cache n'a pas coute de credit : pas notee.
    Le gain d'un deal : la valeur moins le prix ; pour un ENCAN, la mise d'aujourd'hui va monter : on compte ce qu'il
    rapporte si on l'achete a notre mise maximale (environ 30 % de la valeur), pas la valeur moins une mise de 3 $."""
    if cache:
        return
    _s, cat, cal, _e = note(cib, total, vendeur)
    gain = 0.0
    if res == "deal" and ratio:
        try:
            valeur = float(total) / float(ratio)
            prix = float(total)
            if encan:
                try:
                    import deals
                    prix = max(prix, deals.prix_max(valeur))
                except Exception:
                    prix = max(prix, 0.7 * valeur)
            gain = max(0.0, valeur - prix)
        except (TypeError, ValueError, ZeroDivisionError):
            gain = 0.0
    g = groupe_vendeur(vendeur)
    jour = date.today().isoformat()
    with _verrou:
        d = json.loads(json.dumps(lire() or {}))
        for nom, k in (("cles", _cle(cat, cal)), ("groupes", g)):
            s = d.setdefault(nom, {}).setdefault(k, [0, 0, 0, 0.0])
            s[0] += 1
            s[1] += 1 if n_ventes else 0
            s[2] += 1 if res == "deal" else 0
            s[3] = round(s[3] + gain, 2)
        j = d.setdefault("jours", {}).setdefault(jour, [0, 0, 0.0])
        j[0] += 1
        j[1] += 1 if res == "deal" else 0
        j[2] = round(j[2] + gain, 2)
        lim = (date.today() - timedelta(days=JOURS_GARDES)).isoformat()
        d["jours"] = {k: v for k, v in d["jours"].items() if k >= lim}
        p = _chemin()
        try:
            with open(p + ".tmp", "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, separators=(",", ":"))
            os.replace(p + ".tmp", p)
            _CACHE["mt"], _CACHE["d"] = os.path.getmtime(p), d
        except OSError:
            pass


def rapport():
    """Admin : ce que chaque categorie rapporte par credit (test de depart et vrai), du meilleur au moins bon."""
    d = lire()
    cles = d.get("cles") or {}
    lignes = []
    for cat in PRIORS:
        for cal in ("bon", "moyen", "gris"):
            s = cles.get(_cle(cat, cal)) or [0, 0, 0, 0.0]
            pr = _prior(cat, cal)
            lignes.append({"cat": cat, "nom": NOMS.get(cat, cat), "calibre": cal, "credits": s[0], "avec_ventes": s[1],
                           "deals": s[2], "gain": s[3], "depart": round(pr[0], 2), "valeur": round(pr[1]),
                           "vrai": round(s[3] / s[0], 2) if s[0] else None, "note": round(appris(cat, cal), 2),
                           "sautee": pr[1] < VALEUR_MIN})
    lignes.sort(key=lambda x: -x["note"])
    gr = d.get("groupes") or {}
    groupes = [{"groupe": k, "nom": NOMS_GROUPES[k], "facteur": GROUPES[k], "credits": (gr.get(k) or [0])[0],
                "deals": (gr.get(k) or [0, 0, 0])[2], "gain": (gr.get(k) or [0, 0, 0, 0.0])[3]} for k in GROUPES]
    jours = sorted((d.get("jours") or {}).items())[-14:]
    tot = [sum(v[i] for _k, v in (d.get("jours") or {}).items()) for i in range(3)] if d.get("jours") else [0, 0, 0.0]
    return {"lignes": lignes, "groupes": groupes, "jours": [{"jour": k, "credits": v[0], "deals": v[1], "gain": v[2]} for k, v in jours],
            "total": {"credits": tot[0], "deals": tot[1], "gain": round(tot[2], 2),
                      "par_credit": round(tot[2] / tot[0], 2) if tot[0] else None},
            "valeur_min": VALEUR_MIN, "k": K_PRIOR}
