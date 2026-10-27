"""
LOCKERROOM - compteur d'appels eBay et cache partage (21 oct 2026).

eBay limite les appels par APPLICATION (tous les clients ensemble), par jour :
Browse 5 000, Trading 5 000, Fulfillment 100 000, Identity 5 000, Offer 5 000
(developer.ebay.com/develop/get-started/api-call-limits ; relevables par
l'« Application Growth Check »). Ce module :
  - compte chaque appel, par API et par jour (journee du Pacifique, comme eBay) ;
  - garde une reserve pour les gestes du vendeur : les taches de fond (Sante,
    rachats, synchro) s'arretent avant la limite, jamais un tap ;
  - met en cache les recherches Browse : la meme carte cherchee par dix vendeurs
    = un seul appel.
"""
import hashlib
import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone

DOSSIER = os.environ.get("LOCKERROOM_DONNEES") or os.path.dirname(os.path.abspath(__file__))
CHEMIN_COMPTEUR = os.path.join(DOSSIER, "appels_ebay.json")
CHEMIN_CACHE = os.path.join(DOSSIER, "cache_ebay.sqlite")
LIMITES = {"browse": 5000, "trading": 5000, "fulfillment": 100000, "identity": 5000, "offer": 5000}
RESERVE_GESTES = 0.20          # 20 % de la journee gardes pour les taps du vendeur
# 27 oct 2026 (licence eBay §8.1 : donnees d'annonces de 6 h au plus) : 5 h au maximum, partout
DUREE_CACHE_S = {"marche": 5 * 3600, "recentes": 5 * 3600, "encheres": 3600, "flux": 3000}     # flux : chasseur de deals (chaque heure)
_verrou = threading.Lock()


def _jour():
    # eBay remet les compteurs a zero a minuit, heure du Pacifique (UTC-8, approx. sans l'heure d'ete)
    return (datetime.now(timezone.utc) - timedelta(hours=8)).date().isoformat()


def _lire():
    try:
        with open(CHEMIN_COMPTEUR, encoding="utf-8") as f:
            d = json.load(f) or {}
    except (OSError, ValueError):
        d = {}
    if d.get("jour") != _jour():
        d = {"jour": _jour(), "appels": {}, "cache": {"hits": 0, "miss": 0}, "limites": d.get("limites") or {}}
    return d


def _ecrire(d):
    tmp = CHEMIN_COMPTEUR + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f)
    os.replace(tmp, CHEMIN_COMPTEUR)


def limite(api):
    return int((_lire().get("limites") or {}).get(api) or LIMITES.get(api, 5000))


def compter(api, n=1):
    with _verrou:
        d = _lire()
        d["appels"][api] = d["appels"].get(api, 0) + n
        _ecrire(d)


def utilises(api):
    return int(_lire()["appels"].get(api, 0))


def budget_ok(api, fond=True):
    """Tache de fond : s'arrete a 80 % de la limite. Geste du vendeur : jusqu'a 100 %."""
    plafond = limite(api) * ((1 - RESERVE_GESTES) if fond else 1.0)
    return utilises(api) < plafond


def exiger(api, fond=True):
    if not budget_ok(api, fond):
        raise RuntimeError("Limite quotidienne d'appels eBay presque atteinte : reprise automatique demain"
                           if fond else "Limite quotidienne d'appels eBay atteinte : réessaie demain")


def resume():
    d = _lire()
    c = d.get("cache") or {}
    total = (c.get("hits") or 0) + (c.get("miss") or 0)
    return {"jour": d["jour"], "appels": {api: {"utilises": d["appels"].get(api, 0), "limite": limite(api)} for api in LIMITES},
            "cache_pct": round(100 * (c.get("hits") or 0) / total) if total else None}


# -- cache des recherches Browse (resultats publics : aucune donnee de compte) -----------------
def _cx():
    c = sqlite3.connect(CHEMIN_CACHE, timeout=30)
    c.execute("CREATE TABLE IF NOT EXISTS recherches (cle TEXT PRIMARY KEY, le REAL, resultats TEXT)")
    return c


def cle_recherche(env, **p):
    return hashlib.sha256(json.dumps({"env": env, **p}, sort_keys=True).encode()).hexdigest()


def cache_lire(cle, genre="marche"):
    c = _cx()
    try:
        r = c.execute("SELECT le, resultats FROM recherches WHERE cle=?", (cle,)).fetchone()
    finally:
        c.close()
    ok = r and time.time() - r[0] < DUREE_CACHE_S.get(genre, 24 * 3600)
    with _verrou:
        d = _lire()
        d.setdefault("cache", {"hits": 0, "miss": 0})["hits" if ok else "miss"] += 1
        _ecrire(d)
    return json.loads(r[1]) if ok else None


def cache_ecrire(cle, resultats):
    c = _cx()
    try:
        c.execute("INSERT OR REPLACE INTO recherches VALUES (?,?,?)", (cle, time.time(), json.dumps(resultats)))
        c.execute("DELETE FROM recherches WHERE le < ?", (time.time() - 3 * 86400,))
        c.commit()
    finally:
        c.close()
