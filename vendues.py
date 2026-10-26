"""
LOCKERROOM - les « last sold » eBay (25 oct 2026).

Mathieu : « ou sont tous les last sold comp ? » puis « utiliser sold comp ? » et « base-toi toujours sur les
last sold et non aux cartes en vente uniquement, car tres souvent les prix demandes sont bien plus chers ».

Source : SoldComps (sold-comps.com), le meme compte que Hall of Cardz (forfait mensuel partage) :
  - cle : SOLDCOMPS_CLE (Render) ou soldcomps_cle.txt a cote du code (jamais sur GitHub, jamais envoyee a l'ecran) ;
  - une recherche = jusqu'a 240 ventes eBay ; offre acceptee : le vrai prix (hydrateBoa), sinon ecartee ;
  - cache 3 jours par recherche (tous les comptes) et plafond par jour (LR_SOLDCOMPS_JOUR, 150 par defaut)
    pour ne pas manger le quota de HoC ;
  - prix en $ US sur eBay.com -> $ CA (taux de la Banque du Canada), port non compris (comme 130point).
Plus les ventes reelles de la communaute SlabCoach (ventes_communaute). Les MEMES cartes seulement (cartes_match).
"""
import json
import os
import sqlite3
import statistics
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

URL_API = "https://api.sold-comps.com"
CATEGORIE_CARTES = "261328"
NB_PAR_REQUETE = 240
CACHE_S = 3 * 86400
INTERVALLE_MIN_S = 1.05
_verrou = threading.Lock()
_DERNIER = [0.0]


def _cle():
    c = (os.environ.get("SOLDCOMPS_CLE") or "").strip()
    if c:
        return c
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "soldcomps_cle.txt"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def actif():
    return bool(_cle())


def plafond_jour():
    try:
        return int(os.environ.get("LR_SOLDCOMPS_JOUR") or 150)
    except ValueError:
        return 150


def _cx():
    import comptes
    c = sqlite3.connect(os.path.join(comptes.DONNEES, "cache_vendues.sqlite"), timeout=30)
    c.execute("CREATE TABLE IF NOT EXISTS cache (q TEXT PRIMARY KEY, le REAL, ventes TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS compteur (jour TEXT PRIMARY KEY, n INTEGER)")
    return c


def _cache_lire(q):
    try:
        c = _cx()
        try:
            r = c.execute("SELECT le, ventes FROM cache WHERE q=?", (q,)).fetchone()
        finally:
            c.close()
        if r and time.time() - r[0] < CACHE_S:
            return json.loads(r[1])
    except (sqlite3.Error, ValueError):
        pass
    return None


def _cache_ecrire(q, ventes):
    with _verrou:
        c = _cx()
        try:
            c.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?)", (q, time.time(), json.dumps(ventes)))
            c.commit()
        finally:
            c.close()


def utilises_aujourdhui():
    try:
        c = _cx()
        try:
            r = c.execute("SELECT n FROM compteur WHERE jour=?", (datetime.now().strftime("%Y-%m-%d"),)).fetchone()
        finally:
            c.close()
        return int(r[0]) if r else 0
    except sqlite3.Error:
        return 0


def _compter():
    with _verrou:
        c = _cx()
        try:
            j = datetime.now().strftime("%Y-%m-%d")
            c.execute("INSERT INTO compteur VALUES (?, 1) ON CONFLICT(jour) DO UPDATE SET n = n + 1", (j,))
            c.commit()
        finally:
            c.close()


def _num(v):
    try:
        return float(str(v).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None


def _taux_usd_cad():
    try:
        import lockerroom
        return 1 / float(lockerroom.Api.taux_change(None)["usd"])
    except Exception:
        return 1.38


def _vers_vente(it, taux):
    prix, dev = None, it.get("soldCurrency") or "USD"
    if it.get("bestOfferAccepted"):
        if it.get("boaHydrated") and it.get("boaAcceptedPrice") is not None:
            prix, dev = _num(it.get("boaAcceptedPrice")), it.get("boaAcceptedCurrency") or dev
    else:
        prix = _num(it.get("soldPrice"))
    if not prix or prix <= 0:
        return None
    cad = prix * (taux if dev == "USD" else 1.0) if dev in ("USD", "CAD") else None
    if cad is None:
        return None
    return {"titre": it.get("title") or "", "prix": round(cad, 2), "le": str(it.get("endedAt") or "")[:10],
            "photo": it.get("thumbnailUrl"), "url": it.get("url"), "offre": bool(it.get("bestOfferAccepted")),
            "mises": it.get("bidCount"), "source": "eBay"}


def en_cache(q):
    """Les ventes d'une recherche si elles sont en cache (3 jours), sinon None : jamais d'appel SoldComps."""
    return _cache_lire(" ".join(str(q or "").split())[:120].lower())


def rechercher(q, fond=True):
    """Ventes eBay d'une recherche (toutes cartes confondues : filtrer ensuite). {ventes, erreur, cache}."""
    q = " ".join(str(q or "").split())[:120]
    if not q:
        return {"ventes": [], "erreur": None}
    deja = _cache_lire(q.lower())
    if deja is not None:
        return {"ventes": deja, "erreur": None, "cache": True}
    if not actif():
        return {"ventes": [], "erreur": "inactif"}
    if utilises_aujourdhui() >= plafond_jour() * (0.7 if fond else 1.0):     # les taps passent avant les taches de fond
        return {"ventes": [], "erreur": "plafond du jour"}
    url = URL_API + "/v1/scrape?" + urllib.parse.urlencode({"keyword": q, "categoryId": CATEGORIE_CARTES, "count": NB_PAR_REQUETE,
                                                            "ebaySite": "ebay.com", "hydrateBoa": "true"})
    with _verrou:
        attente = INTERVALLE_MIN_S - (time.time() - _DERNIER[0])
        if attente > 0:
            time.sleep(attente)
        _DERNIER[0] = time.time()
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + _cle(), "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            d = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"ventes": [], "erreur": {401: "clé SoldComps refusée", 429: "quota SoldComps atteint"}.get(e.code, f"SoldComps HTTP {e.code}")}
    except Exception as e:
        return {"ventes": [], "erreur": "SoldComps injoignable (" + type(e).__name__ + ")"}
    _compter()
    taux = _taux_usd_cad()
    ventes = [v for v in (_vers_vente(it, taux) for it in (d or {}).get("items") or []) if v]
    _cache_ecrire(q.lower(), ventes)
    try:                                       # 26 oct 2026 - la base des ventes (tendances) garde tout, sans appel de plus
        import base_ventes
        base_ventes.noter(q, ventes)
    except Exception:
        pass
    return {"ventes": ventes, "erreur": None}


def memes(texte, requete=True, n=24, fond=False, exclure_titre=None):
    """Les MEMES cartes vendues (eBay via SoldComps + communaute SlabCoach), les plus recentes d'abord.
    texte = ce que l'utilisateur a tape (requete=True) ou le titre d'une annonce (requete=False).
    -> {ventes, mediane, nb, derniere, source, erreur}"""
    import cartes_match
    import ventes_communaute
    cib = cartes_match.cible(texte) if requete else cartes_match.cible_titre(texte)
    q = cartes_match.requete_ebay(cib) or texte
    r = rechercher(q, fond=fond) if q else {"ventes": [], "erreur": None}
    ebay = [v for v in r.get("ventes") or [] if not cartes_match.raisons_refus(cib, v["titre"])]
    try:
        comm = (ventes_communaute.chercher(texte, requete=requete, n=40) or {}).get("ventes") or []
    except Exception:
        comm = []
    tout = ebay + [{**v, "source": "SlabCoach"} for v in comm]
    tout.sort(key=lambda v: str(v.get("le") or ""), reverse=True)
    prix = [v["prix"] for v in tout if v.get("prix")]
    med = None
    if prix:
        med, _g = cartes_match.mediane_robuste(prix) if len(prix) >= 4 else (round(statistics.median(prix), 2), prix)
    return {"ventes": tout[:n], "mediane": med, "nb": len(tout), "derniere": tout[0]["le"] if tout else None,
            "ebay": len(ebay), "communaute": len(comm), "erreur": r.get("erreur") if not tout else None,
            "points": [[v.get("le"), v["prix"]] for v in tout[:200] if v.get("le") and v.get("prix")],
            "tendance": tendance(tout)}


def memes_annonce(titre, q=None, n=24, fond=False):
    """26 oct 2026 - les ventes de la MEME carte qu'une annonce. Avec q (la recherche du chasseur de deals, deja en
    cache) : ses ventes filtrees par le titre de l'annonce (meme parallele, meme numero) ; s'il y en a moins de 3,
    la recherche faite a partir du titre."""
    import cartes_match
    if q:
        try:
            cib_q = cartes_match.cible(q)
            r = rechercher(cartes_match.requete_ebay(cib_q) or q, fond=fond)
            cib = cartes_match.cible_titre(titre)
            l = [v for v in r.get("ventes") or [] if not cartes_match.raisons_refus(cib, v["titre"])]
            if len(l) >= 3:
                l.sort(key=lambda v: str(v.get("le") or ""), reverse=True)
                prix = [v["prix"] for v in l]
                med = cartes_match.mediane_robuste(prix)[0] if len(prix) >= 4 else round(statistics.median(prix), 2)
                return {"ventes": l[:n], "mediane": med, "nb": len(l), "derniere": l[0]["le"], "ebay": len(l), "communaute": 0,
                        "erreur": None, "points": [[v.get("le"), v["prix"]] for v in l[:200] if v.get("le")], "tendance": tendance(l)}
        except Exception:
            pass
    return memes(titre, requete=False, n=n, fond=fond)


def tendance(ventes, jours=30):
    """26 oct 2026 - % de variation : mediane des ventes des `jours` derniers jours vs les `jours`*2 d'avant.
    None s'il n'y a pas assez de ventes des deux cotes (3 chacune)."""
    from datetime import timedelta
    auj = datetime.now()
    d1, d2 = (auj - timedelta(days=jours)).strftime("%Y-%m-%d"), (auj - timedelta(days=jours * 3)).strftime("%Y-%m-%d")
    recent = [v["prix"] for v in ventes if v.get("prix") and str(v.get("le") or "") >= d1]
    avant = [v["prix"] for v in ventes if v.get("prix") and d2 <= str(v.get("le") or "") < d1]
    if len(recent) < 3 or len(avant) < 3:
        return None
    a, b = statistics.median(avant), statistics.median(recent)
    return {"pct": round(100 * (b - a) / a) if a else None, "recent": round(b, 2), "avant": round(a, 2), "n": len(recent) + len(avant)}


def statut():
    return {"actif": actif(), "aujourdhui": utilises_aujourdhui(), "plafond": plafond_jour()}
