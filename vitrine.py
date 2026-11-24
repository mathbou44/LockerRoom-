"""
SLABCOACH - la vitrine du Radar Pro (19 nov 2026).

Mathieu : « pourquoi le Radar Pro montre des cartes a 20 $ qu'on ne veut pas, et le Radar admin de belles cartes ? Le Pro doit
trouver les memes cartes que le Platine, ou presque ; c'est la version qu'on lance ».

Pourquoi l'ecart : le Radar admin voit ce que le chasseur balaie chaque heure (les gros vendeurs, les flux de hits et de recrues,
la categorie hockey : des dizaines de milliers d'annonces) ; le Pro ne cherchait que quelques joueurs (en feu, a decouvrir).
La vitrine garde, pendant ce meme balayage, les annonces dont la CARTE est tres recherchee (SlabIQ A et A+, jamais une base,
30 $ et plus) ; le Radar Pro les montre en premier (« A la une »).

20 nov 2026 (Mathieu : « il ne faut pas que l'acheteur reste pogne avec ; des cartes liquides et desirees » ; « le prix en
coulisse, mais l'utilisateur voit juste la lettre ») : une annonce entre dans la vitrine si sa carte est A- ou mieux ET se
vend (5 ventes et plus de la meme carte, meme compagnie, meme note, en 60 jours) ET n'est pas plus de 10 % au-dessus de ce
qu'elle se vend (liquidite.py). L'utilisateur voit la lettre et l'annonce : jamais la mediane ni le compte de ventes.

Teste sur des achats jamais vus (outils/radar_iq.py ; reussi = la carte se revend ensuite ET a au moins 90 % du prix paye) :
oct. : hasard 11,7 %, ancienne regle (A et A+) 29,8 %, cette regle 71,0 % ; nov. : hasard 11,3 %, cette regle 60,3 %.
23 nov 2026 (Mathieu : « B : 78 % ») : 8 ventes en 60 jours et jamais au-dessus de ce que la carte se vend (liquidite.py :
78 a 90 % aux 5 dates du bulletin, contre 59 a 76 % avant).
23 nov 2026 au soir : et la carte se vendait deja il y a deux mois (une carte neuve perd sa valeur : liquidite.py). Les annonces
deja en vitrine sont completees au prochain balayage (_completer), sans attendre qu'elles expirent.
24 nov 2026 (Mathieu, en vue Pro : « only 34 are showing » ; « il nous faut beaucoup de cartes a proposer » ; il choisit « deux
rangees ») : la vitrine garde maintenant TOUTES les annonces dont la carte est A- ou mieux (jamais une base, 30 $ et plus), avec
leurs signaux. « A la une » (liste) reste la regle prouvee, telle quelle ; « Tres recherchees » (recherchees) montre les autres :
la lettre SlabIQ, sans la preuve de revente (au test, A et A+ sans la regle : 24 % gardent leur valeur, contre 84,6 %). Avant,
une annonce qui ne passait pas la regle etait oubliee pour de bon (None) : le nouveau fichier (vitrine2.json) reprend les
annonces deja en vitrine et laisse rejuger les autres au prochain balayage.
Les annonces sont gardees au plus 12 h (prix fixe) ou jusqu'a la fin de l'encan, et le Radar relit la fiche en direct quand
on l'ouvre. Un encan dont la mise monte au-dessus de la limite de prix sort de la liste.
"""
import json
import os
import re
import threading
import time
from datetime import datetime

import liquidite

PRIX_MIN = 30.0
MAX = 4000
FIXE_H = 12
_SIGNAL = re.compile(r"auto|autograph|signed|patch|relic|jersey|rpa|young guns?|\byg\b|/\s?\d{1,4}\b|\b1/1\b|psa\s?10|bgs\s?9\.5|"
                     r"sgc\s?10|rookie|\brc\b|the cup|future watch|premier|ice premieres|black diamond|ssp|short print|"
                     r"precious metal|clear cut|manga|canvas|exclusives|high gloss|o-?pee-?chee|parkhurst|topps", re.I)
_VERROU = threading.Lock()
_ETAT = {"pool": None, "ecrit": 0.0, "sale": False}
CHAMPS = ("item_id", "titre", "prix_cad", "port_cad", "encan", "fin", "mises", "vendeur", "vendeur_pct", "vendeur_score", "url",
          "photo", "lieu")


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "vitrine2.json")        # 24 nov 2026 : les deux rangees (avant : vitrine_liq.json)


def _chemin_avant():
    import comptes
    return os.path.join(comptes.DONNEES, "vitrine_liq.json")


def _pool():
    if _ETAT["pool"] is None:
        try:
            with open(_chemin(), encoding="utf-8") as f:
                _ETAT["pool"] = json.load(f) or {}
        except (OSError, ValueError):
            # 24 nov 2026 : la 1re fois, on reprend les annonces deja en vitrine (« A la une » ne se vide pas a la mise en
            # ligne) ; celles qui avaient ete refusees (None) ne sont PAS reprises : elles seront rejugees au prochain balayage
            try:
                with open(_chemin_avant(), encoding="utf-8") as f:
                    _ETAT["pool"] = {k: x for k, x in (json.load(f) or {}).items() if isinstance(x, dict)}
                _ETAT["sale"] = True
            except (OSError, ValueError):
                _ETAT["pool"] = {}
    return _ETAT["pool"]


def _ts(v):
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def _vivante(x, maint):
    if x.get("encan"):
        f = _ts(x.get("fin"))
        return f is None or f > maint
    return maint - float(x.get("vu") or 0) < FIXE_H * 3600


def ajouter(annonces):
    """Des annonces balayees par le chasseur -> la vitrine (seulement les cartes A et A+, 30 $ et plus). Rapide pour les annonces
    deja vues (le prix, les mises et la fin sont rafraichis) ; la note SlabIQ n'est calculee qu'une fois par annonce."""
    maint = time.time()
    neuves = []
    with _VERROU:
        P = _pool()
        for a in annonces or []:
            if not isinstance(a, dict) or not a.get("item_id") or not a.get("titre"):
                continue
            k = str(a["item_id"])
            tot = round(float(a.get("total") or 0) or (float(a.get("prix_cad") or 0) + float(a.get("port_cad") or 0)), 2)
            if k in P:
                if P[k] is not None:
                    P[k].update({c: a.get(c) for c in ("prix_cad", "port_cad", "mises", "fin") if a.get(c) is not None}, total=tot, vu=maint)
                continue
            if tot < PRIX_MIN or not _SIGNAL.search(a["titre"]):
                continue
            neuves.append({**{c: a.get(c) for c in CHAMPS if a.get(c) is not None}, "item_id": k, "total": tot, "vu": maint})
    if not neuves:
        if _completer():
            _ecrire_si_besoin()
        return 0
    try:
        import score_slab
        import sports
        score_slab.annoter_lot(neuves)
    except Exception as e:
        print("Vitrine (notes) : " + repr(e)[:160], flush=True)
        return 0
    bonnes = []
    for x in neuves:
        ok = (x.get("score") or 0) >= liquidite.NOTE_MIN and x.get("sorte") not in (None, "D") and x.get("joueur")
        try:
            ok = ok and sports.detecter(x.get("titre") or "", defaut="hockey") == "hockey"
        except Exception:
            pass
        x["_ok"] = bool(ok)
        bonnes += [x["titre"]] if ok else []
    try:
        sig = liquidite.signaux(bonnes) if bonnes else {}
    except Exception as e:
        print("Vitrine (liquidite) : " + repr(e)[:160], flush=True)
        sig = None
    gardees = 0
    with _VERROU:
        P = _pool()
        for x in neuves:
            ok = x.pop("_ok")
            if ok and sig is None:
                continue                                 # l'index n'est pas pret : jugee au prochain balayage
            if ok:                                       # 24 nov 2026 : gardee des que la carte est A- ou mieux ; la regle se juge a la lecture
                x["_liq"], x["_med"], x["_vieux"] = sig.get(x["titre"]) or (0, None, 0)
                x["_sv"] = liquidite.VERSION
            P[x["item_id"]] = x if ok else None          # None : deja jugee, pas assez recherchee (pas renotee)
            gardees += 1 if ok and liquidite.passe(x["_liq"], x["_med"], x["total"], x["_vieux"]) else 0
        _ETAT["sale"] = True
        _purger(P, maint)
    _completer()
    _ecrire_si_besoin()
    return gardees


def _completer(plafond=400):
    """23 nov 2026 au soir : les annonces entrees en vitrine avant la regle « pas une carte neuve » n'ont pas leur signal
    (_vieux) : on le lit dans l'index, par paquets, au lieu d'attendre qu'elles expirent (une annonce a prix fixe revue a
    chaque balayage n'expire jamais). Tant qu'il manque, l'annonce n'est pas montree."""
    # 24 nov 2026 : et les annonces dont les signaux viennent de l'ancien index (ventes comptees en double, ancienne cle de
    # carte : liquidite.VERSION) : relues des que le nouvel index est pret ; d'ici la, leurs anciens signaux servent encore
    with _VERROU:
        manque = [(k, x["titre"]) for k, x in _pool().items()
                  if x is not None and x.get("titre") and ("_vieux" not in x or x.get("_sv") != liquidite.VERSION)][:plafond]
    if not manque:
        return 0
    try:
        sig = liquidite.signaux([t for _, t in manque])
    except Exception as e:
        print("Vitrine (completer) : " + repr(e)[:160], flush=True)
        return 0
    if sig is None:
        return 0
    with _VERROU:
        P = _pool()
        for k, t in manque:
            if P.get(k) is not None and t in sig:
                P[k]["_liq"], P[k]["_med"], P[k]["_vieux"] = sig[t]
                P[k]["_sv"] = liquidite.VERSION
        _ETAT["sale"] = True
    return len(manque)


def _purger(P, maint):
    for k in [k for k, x in P.items() if x is not None and not _vivante(x, maint)]:
        del P[k]
    if len(P) > MAX * 4:                                # les « None » (deja jugees) : les plus vieilles partent
        for k in [k for k, x in P.items() if x is None][: len(P) - MAX * 3]:
            del P[k]
    vivantes = [k for k, x in P.items() if x is not None]
    if len(vivantes) > MAX:                             # 24 nov 2026 : les « Tres recherchees » partent avant les « A la une »
        for k in sorted(vivantes, key=lambda k: (_prouvee(P[k]), P[k].get("score") or 0, P[k].get("total") or 0))[: len(vivantes) - MAX]:
            del P[k]


def _prouvee(x):
    """L'annonce passe la regle prouvee du Radar Pro (liquide, pas neuve, jamais au-dessus de ce que la carte se vend)."""
    return liquidite.passe(x.get("_liq"), x.get("_med"), x.get("total"), x.get("_vieux"))


def _ecrire_si_besoin(forcer=False):
    if not _ETAT["sale"] or (not forcer and time.time() - _ETAT["ecrit"] < 60):
        return
    with _VERROU:
        d = dict(_pool())
        _ETAT["sale"], _ETAT["ecrit"] = False, time.time()
    try:
        tmp = _chemin() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, separators=(",", ":"))
        os.replace(tmp, _chemin())
    except OSError:
        pass


def liste(n=80, prix_min=None, prix_max=None):
    """Les meilleures cartes en vente maintenant : la note d'abord, puis les encans qui finissent bientot, puis les plus grosses."""
    maint = time.time()
    with _VERROU:
        L = [dict(x) for x in _pool().values() if x is not None and _vivante(x, maint)]
    return _sortir(L, n, prix_min, prix_max, True)


def recherchees(n=300, prix_min=None, prix_max=None):
    """24 nov 2026 : les autres annonces de la vitrine : la carte est A- ou mieux, mais l'annonce ne passe pas la regle prouvee
    (pas assez de ventes, carte neuve, ou plus chere que ce qu'elle se vend). La lettre SlabIQ, sans la preuve de revente."""
    maint = time.time()
    with _VERROU:
        L = [dict(x) for x in _pool().values() if x is not None and _vivante(x, maint)]
    return _sortir(L, n, prix_min, prix_max, False)


def _sortir(L, n, prix_min, prix_max, prouvees):
    pm = PRIX_MIN if prix_min is None else float(prix_min)
    L = [x for x in L if (x.get("total") or 0) >= pm and (not prix_max or (x.get("total") or 0) <= float(prix_max))
         and _prouvee(x) == prouvees and ("_vieux" in x or prouvees)]                # le prix d'un encan monte ; signal manquant : cachee
    L.sort(key=lambda x: (-(x.get("score") or 0), 0 if x.get("encan") else 1, _ts(x.get("fin")) or 9e12, -(x.get("total") or 0)))
    out = []
    for x in L[: max(1, int(n))]:
        x.pop("_liq", None), x.pop("_med", None), x.pop("_vieux", None), x.pop("_sv", None)         # jamais montres : seulement la lettre
        x["joueur_n"] = x.get("joueur")
        if prouvees:
            x["a_la_une"] = True
        out.append(x)
    return out


def etat():
    with _VERROU:
        P = _pool()
        v = [x for x in P.values() if x is not None]
    une = sum(1 for x in v if _prouvee(x))
    return {"cartes": une, "recherchees": len(v) - une, "jugees": len(P), "a_plus": sum(1 for x in v if (x.get("score") or 0) >= 92)}
