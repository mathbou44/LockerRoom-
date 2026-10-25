"""
LOCKERROOM - valeur des joueurs et des cartes (« l'algo LockerRoom »).

valeurs_joueurs.json (a cote de ce fichier), produit par valeurs_maj.py :
  {"maj": "...", "source": "...",
   "joueurs": {"Connor McDavid": 5.51, ...},        # demande : combien ses cartes se vendent
                                                    # par rapport a une carte equivalente (1,0 = moyen)
   "sous_ensembles": {"<id produit>": {"Young Guns": {"valeur": 7.4, "n": 312}, ...}}}
                                                    # valeur ($ CA) d'une carte de ce sous-ensemble
                                                    # pour un joueur a 1,0 (mediane de vraies ventes)

Valeur attendue d'une carte = valeur du sous-ensemble x demande du joueur.
Sans mesure : valeurs par defaut selon le genre de carte et sa rarete.
"""
import json
import math
import os
import re
import unicodedata

CHEMIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "valeurs_joueurs.json")
DEMANDE_INCONNUE = 0.5            # joueur sans ventes mesurees : un peu sous la mediane (0,59)
# $ CA pour un joueur a 1,0 - quand aucune vente ne mesure le sous-ensemble
DEFAUTS = {"base": 0.25, "insert": 1.0, "recrue": 6.0, "numerotee": 5.0, "auto": 20.0, "memo": 6.0, "auto_memo": 35.0}
_ETAT = {"mtime": None, "data": {"joueurs": {}, "sous_ensembles": {}}, "index": {}}


def norm_nom(n):
    t = "".join(c for c in unicodedata.normalize("NFKD", str(n or "")) if not unicodedata.combining(c)).lower()
    t = re.sub(r"\((?:d|f|g)\)|\bjr\.?|\bsr\.?", " ", t)
    return re.sub(r"[^a-z]+", " ", t).strip()


def _charger():
    try:
        mt = os.path.getmtime(CHEMIN)
    except OSError:
        return _ETAT["data"]
    if _ETAT["mtime"] != mt:
        try:
            with open(CHEMIN, encoding="utf-8") as f:
                d = json.load(f)
            _ETAT.update(mtime=mt, data=d, index={norm_nom(k): v for k, v in (d.get("joueurs") or {}).items()})
        except (OSError, ValueError):
            pass
    return _ETAT["data"]


def statut():
    d = _charger()
    se = d.get("sous_ensembles") or {}
    return {"maj": d.get("maj"), "source": d.get("source"), "nb_joueurs": len(d.get("joueurs") or {}),
            "nb_mesures": sum(len(v) for v in se.values()), "nb_ventes": d.get("nb_ventes")}


def demande(joueur):
    """Multiplicateur de demande ; carte a deux joueurs : moyenne des deux."""
    _charger()
    noms = [x for x in re.split(r"\s*/\s*|\s+&\s+", str(joueur or "")) if x.strip()]
    if not noms:
        return DEMANDE_INCONNUE
    vals = [_ETAT["index"].get(norm_nom(n), DEMANDE_INCONNUE) for n in noms]
    return sum(vals) / len(vals)


def connu(joueur):
    _charger()
    return norm_nom(joueur) in _ETAT["index"]


def valeur_sous_ensemble(prod, nom, se, taux, _prof=0):
    """(valeur $ pour un joueur a 1,0, mesuree?) d'une carte du sous-ensemble."""
    d = _charger()
    m = ((d.get("sous_ensembles") or {}).get(prod["id"]) or {}).get(nom)
    if m and m.get("valeur"):
        return float(m["valeur"]), True
    s = se.get(nom) or {}
    parent = s.get("parallele_de")
    tirage = s.get("tirage")
    if parent and parent in se and parent != nom and _prof < 6:
        vp, _ = valeur_sous_ensemble(prod, parent, se, taux, _prof + 1)
        if tirage:
            f = max(1.5, (1000.0 / max(1, tirage)) ** 0.6)
        else:
            tp, ts = taux.get(parent), taux.get(nom)
            f = math.sqrt(tp / ts) if tp and ts else 3.0
        return vp * min(60.0, max(1.0, f)), False
    v = DEFAUTS.get(s.get("groupe") or "base", 1.0)
    if tirage:
        v *= max(1.0, (250.0 / max(1, tirage)) ** 0.5)
    return v, False


def valeur_carte(prod, nom, joueur, se, taux, cache=None):
    """25 oct 2026 - la valeur d'UNE carte (sous-ensemble x joueur), mesuree sur les ventes reelles quand on les a
    (valeur_produit) ; une parallele = la valeur vendue du joueur dans le sous-ensemble parent x l'ecart du modele ;
    sinon l'ancien modele (valeur du sous-ensemble x demande du joueur). -> (valeur $ CA, mesuree ?)"""
    import valeur_produit
    cache = {} if cache is None else cache
    if nom not in cache:
        cache[nom] = valeur_sous_ensemble(prod, nom, se, taux)
    vref, mesure = cache[nom]
    noms = [x.strip() for x in re.split(r"\s*/\s*|\s+&\s+", str(joueur or "")) if x.strip()]
    if not noms:
        return vref * DEMANDE_INCONNUE, mesure
    vals, ok = [], False
    for j in noms:
        v, m = valeur_produit.valeur(prod, nom, j, None)
        if v is None:                                    # parallele : remonte au sous-ensemble mesure
            s, k, chaine = se.get(nom) or {}, nom, 0
            while v is None and s.get("parallele_de") and chaine < 6:
                k = s["parallele_de"]
                vp, m = valeur_produit.valeur(prod, k, j, None)
                if vp is not None:
                    if k not in cache:
                        cache[k] = valeur_sous_ensemble(prod, k, se, taux)
                    v = vp * (vref / cache[k][0]) if cache[k][0] else vp
                s, chaine = se.get(k) or {}, chaine + 1
        if v is None:
            dj = demande(j)
            if not connu(j):                              # recrue toute neuve : sa cote d'apres ses annonces
                dr = valeur_produit.demande_recrue(prod, j)
                dj = dr if dr is not None else dj
            # 26 oct 2026 : la demande d'un joueur (mesuree surtout sur ses recrues et ses hits) gonfle trop ses cartes de
            # base et ses inserts de veteran : la, elle compte a moitie (racine) ; recrues, autos et patchs : pleine
            g = (se.get(nom) or {}).get("groupe") or "base"
            if g in ("base", "insert"):
                dj = dj ** 0.5 if dj > 1 else dj
            v, m = vref * dj, mesure
        vals.append(v)
        ok = ok or m
    return sum(vals) / len(vals), ok
