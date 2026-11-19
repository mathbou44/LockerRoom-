"""
SLABCOACH - la vitrine du Radar Pro (19 nov 2026).

Mathieu : « pourquoi le Radar Pro montre des cartes a 20 $ qu'on ne veut pas, et le Radar admin de belles cartes ? Le Pro doit
trouver les memes cartes que le Platine, ou presque ; c'est la version qu'on lance ».

Pourquoi l'ecart : le Radar admin voit ce que le chasseur balaie chaque heure (les gros vendeurs, les flux de hits et de recrues,
la categorie hockey : des dizaines de milliers d'annonces) ; le Pro ne cherchait que quelques joueurs (en feu, a decouvrir).
La vitrine garde, pendant ce meme balayage, les annonces dont la CARTE est tres recherchee (SlabIQ A et A+, jamais une base,
30 $ et plus) ; le Radar Pro les montre en premier (« A la une »).

Licence eBay : aucune valeur ni comparable n'entre ici. Le choix se fait sur la note SlabIQ de la carte (le titre, le bareme de
l'expert) ; le prix ne sert qu'au plancher de 30 $ que l'utilisateur peut changer. Les annonces sont gardees au plus 12 h (prix
fixe) ou jusqu'a la fin de l'encan, et le Radar relit la fiche en direct quand on l'ouvre.

Teste sur des ventes jamais vues (nov 2026) : une carte A ou A+ a garde au moins 90 % de son prix d'achat 70 % du temps (A- :
62 %, A+ seule : 82 %) ; le plancher de 30 $ ne change pas la precision et enleve les petites cartes.
"""
import json
import os
import re
import threading
import time
from datetime import datetime, timezone

NOTE_MIN = 86                      # A
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
    return os.path.join(comptes.DONNEES, "vitrine.json")


def _pool():
    if _ETAT["pool"] is None:
        try:
            with open(_chemin(), encoding="utf-8") as f:
                _ETAT["pool"] = json.load(f) or {}
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
        return 0
    try:
        import score_slab
        import sports
        score_slab.annoter_lot(neuves)
    except Exception as e:
        print("Vitrine (notes) : " + repr(e)[:160], flush=True)
        return 0
    gardees = 0
    with _VERROU:
        P = _pool()
        for x in neuves:
            ok = (x.get("score") or 0) >= NOTE_MIN and x.get("sorte") not in (None, "D") and x.get("joueur")
            try:
                ok = ok and sports.detecter(x.get("titre") or "", defaut="hockey") == "hockey"
            except Exception:
                pass
            P[x["item_id"]] = x if ok else None          # None : deja jugee, pas assez recherchee (on ne la renote pas)
            gardees += 1 if ok else 0
        _ETAT["sale"] = True
        _purger(P, maint)
    _ecrire_si_besoin()
    return gardees


def _purger(P, maint):
    for k in [k for k, x in P.items() if x is not None and not _vivante(x, maint)]:
        del P[k]
    if len(P) > MAX * 4:                                # les « None » (deja jugees) : les plus vieilles partent
        for k in [k for k, x in P.items() if x is None][: len(P) - MAX * 3]:
            del P[k]
    vivantes = [k for k, x in P.items() if x is not None]
    if len(vivantes) > MAX:
        for k in sorted(vivantes, key=lambda k: (P[k].get("score") or 0, P[k].get("total") or 0))[: len(vivantes) - MAX]:
            del P[k]


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
    pm = PRIX_MIN if prix_min is None else float(prix_min)
    L = [x for x in L if (x.get("total") or 0) >= pm and (not prix_max or (x.get("total") or 0) <= float(prix_max))]
    L.sort(key=lambda x: (-(x.get("score") or 0), 0 if x.get("encan") else 1, _ts(x.get("fin")) or 9e12, -(x.get("total") or 0)))
    out = []
    for x in L[: max(1, int(n))]:
        x["joueur_n"] = x.get("joueur")
        x["a_la_une"] = True
        out.append(x)
    return out


def etat():
    with _VERROU:
        P = _pool()
        v = [x for x in P.values() if x is not None]
    return {"cartes": len(v), "jugees": len(P), "a_plus": sum(1 for x in v if (x.get("score") or 0) >= 92)}
