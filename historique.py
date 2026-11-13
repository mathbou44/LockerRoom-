"""
SLABCOACH - l'historique des ventes de plus de 90 jours (7 nov 2026, Mathieu : « on va devoir avoir acces a une banque de
ventes d'au moins 6 mois » ; « utiliser l'API seulement pour les cartes sans comps de 3 mois »).

eBay (et SoldComps) ne montrent que les 90 derniers jours de ventes : un hit rare (une Nazar Future Watch Auto Inscribed,
une Ron Francis Clear Cut Outburst /25) n'a souvent AUCUNE vente dans cette fenetre. CompSniper (/v1/research/sold) donne
jusqu'a 3 ans. On l'appelle SEULEMENT quand SoldComps n'a pas trouve 2 ventes de la meme carte, avec un budget par mois
(LR_HISTORIQUE_MOIS) et par jour pour le chasseur (LR_HISTORIQUE_JOUR) ; chaque recherche est gardee 14 jours en cache et
ses ventes vont dans nos archives (base_ventes). Sans cle (COMPSNIPER_CLE dans Render), rien n'est appele.
"""
import json
import os
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

URL = "https://api.compsniper.com/v1/research/sold"
JOURS = 365                       # un an de ventes (la regle des hits : deals.JOURS_MAX_HITS)
CACHE_S = 14 * 86400
_verrou = threading.Lock()
_ERREUR = {"le": 0.0, "texte": None}


def _cle():
    return (os.environ.get("COMPSNIPER_CLE") or "").strip()


def actif():
    return bool(_cle())


def _env_int(nom, defaut):
    try:
        return max(0, int(os.environ.get(nom) or defaut))
    except ValueError:
        return defaut


def budget_mois():
    return _env_int("LR_HISTORIQUE_MOIS", 95)          # le forfait gratuit : 100 requetes par mois (une marge de 5)


def limite():
    """Ventes par requete (une page) : 50 ; LR_CS_LIMITE pour essayer plus si le forfait CompSniper le permet."""
    return min(200, max(10, _env_int("LR_CS_LIMITE", 50)))


def budget_jour():
    """Le chasseur de deals, par jour : LR_HISTORIQUE_JOUR, sinon ce qui reste du mois reparti sur les jours qui restent
    (x 2 : les encans finissent surtout certains soirs), 3 au moins. Les fiches ouvertes, elles, n'ont que le plafond du mois."""
    if os.environ.get("LR_HISTORIQUE_JOUR"):
        return _env_int("LR_HISTORIQUE_JOUR", 3)
    import calendar
    m = datetime.now(timezone.utc)
    reste_j = calendar.monthrange(m.year, m.month)[1] - m.day + 1
    reste = max(0, budget_mois() - utilises()["mois"])
    return max(3, min(reste, 2 * reste // max(1, reste_j)))


def _cx():
    import comptes
    c = sqlite3.connect(os.path.join(comptes.DONNEES, "historique.sqlite"), timeout=5)
    c.execute("CREATE TABLE IF NOT EXISTS cache (q TEXT PRIMARY KEY, le REAL, ventes TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS compteur (periode TEXT PRIMARY KEY, n INTEGER)")
    return c


def _periodes():
    m = datetime.now(timezone.utc)
    return m.strftime("%Y-%m"), m.strftime("%Y-%m-%d")


def utilises():
    mois, jour = _periodes()
    try:
        c = _cx()
        try:
            r = dict(c.execute("SELECT periode, n FROM compteur WHERE periode IN (?, ?, ?)", (mois, jour, "chasseur:" + jour)).fetchall())
        finally:
            c.close()
    except sqlite3.Error:
        r = {}
    return {"mois": r.get(mois, 0), "jour": r.get(jour, 0), "chasseur": r.get("chasseur:" + jour, 0)}


def part_autres_sports():
    """13 nov 2026 (Mathieu : « ~15 % (1 500/mois) » pour les autres sports, pour ne pas affamer le hockey) : la part du mois
    CompSniper que le baseball (et les sports a venir) peut prendre, ensemble. LR_CS_AUTRES_SPORTS en %."""
    try:
        return min(0.5, max(0.0, float(os.environ.get("LR_CS_AUTRES_SPORTS") or 15) / 100))
    except ValueError:
        return 0.15


def utilises_sports():
    """Les requetes du mois des sports autres que le hockey."""
    mois, _jour = _periodes()
    try:
        c = _cx()
        try:
            r = c.execute("SELECT n FROM compteur WHERE periode=?", ("sports:" + mois,)).fetchone()
        finally:
            c.close()
    except sqlite3.Error:
        return 0
    return r[0] if r else 0


def _autre_sport(sport):
    return bool(sport) and sport != "hockey"


def _compter(chasseur, sport=None):
    mois, jour = _periodes()
    c = _cx()
    try:
        for p in (mois, jour) + (("chasseur:" + jour,) if chasseur else ()) + (("sports:" + mois,) if _autre_sport(sport) else ()):
            c.execute("INSERT INTO compteur VALUES (?, 1) ON CONFLICT(periode) DO UPDATE SET n = n + 1", (p,))
        c.commit()
    finally:
        c.close()


def _cache(q, age_max=None):
    try:
        c = _cx()
        try:
            r = c.execute("SELECT le, ventes FROM cache WHERE q=?", (q,)).fetchone()
        finally:
            c.close()
    except sqlite3.Error:
        return None
    if r and time.time() - r[0] < (CACHE_S if age_max is None else age_max):
        try:
            return json.loads(r[1])
        except ValueError:
            return None
    return None


def lire_reponse(d, taux):
    """La reponse CompSniper -> nos ventes {titre, prix ($ CA), le, url, photo, item_id, source}. Les lignes d'agregat
    (sans prix ni date de vente) sont ignorees."""
    out = []
    for it in (d or {}).get("results") or []:
        if it.get("recordType") == "listing_aggregate":
            continue
        p = (it.get("soldPrice") or {})
        try:
            usd = float(p.get("amount"))
        except (TypeError, ValueError):
            continue
        le = it.get("soldDate") or it.get("lastSoldDate")
        if not usd or not le or not it.get("title"):
            continue
        k = taux if (p.get("currency") or "USD") == "USD" else 1.0
        out.append({"titre": it["title"], "prix": round(usd * k, 2), "le": str(le)[:10], "url": it.get("itemUrl"),
                    "photo": it.get("imageUrl"), "item_id": str(it.get("itemId") or "") or None, "source": "historique"})
    return out


def cle_q(q):
    return " ".join(str(q or "").lower().split())[:200]


def rechercher(q, chasseur=False, jours=JOURS, principal=False, cache_s=None, delai=None, sport=None):
    """Les ventes d'une recherche sur un an (une page de 50, les plus recentes d'abord). -> (ventes, erreur).
    12 nov 2026 (Mathieu : « je peux remplacer SoldComps par CompSniper ») : principal=True quand CompSniper est LA source
    des ventes (vendues.source()) : pas de plafond « chasseur » (vendues tient le budget du jour), seulement celui du mois ;
    cache_s : l'age maximal du cache (3 jours, comme SoldComps : les ventes d'hier comptent pour un deal)."""
    try:
        import lockerroom
        if not lockerroom.comps_permis():            # 10 nov 2026 : comps = admin seulement
            return [], "coupe"
    except Exception:
        pass
    q = cle_q(q)
    if not q or not actif():
        return [], "inactif"
    deja = _cache(q, cache_s)
    if deja is not None:
        return deja, None
    if time.time() - _ERREUR["le"] < 300 and _ERREUR["texte"]:
        return [], _ERREUR["texte"]                  # une panne / un quota : on attend 5 min
    u = utilises()
    if u["mois"] >= budget_mois() or (chasseur and not principal and u["chasseur"] >= budget_jour()):
        return [], "budget"
    if _autre_sport(sport) and utilises_sports() >= budget_mois() * part_autres_sports():
        return [], "budget"                          # 13 nov 2026 : le baseball a sa part (15 %), le hockey garde le reste
    fin = datetime.now(timezone.utc).date()
    p = {"keyword": q, "startDate": (fin - timedelta(days=jours)).isoformat(), "endDate": fin.isoformat(),
         "sort": "lastSoldDescending", "singleUnitOnly": "true", "limit": str(limite()), "page": "1"}
    req = urllib.request.Request(URL + "?" + urllib.parse.urlencode(p), headers={"Authorization": "Bearer " + _cle(), "Accept": "application/json"})
    # 9 nov 2026 (« les ventes reelles ne repondent pas : le chasseur est peut-etre en plein tour ») : un geste de
    # l'utilisateur n'attend pas derriere une requete du chasseur (3 s au plus, puis il passe quand meme)
    pris = _verrou.acquire() if chasseur else _verrou.acquire(timeout=3)
    try:
        try:
            with urllib.request.urlopen(req, timeout=delai or (30 if chasseur else 15)) as r:
                d = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                code = (json.loads(e.read().decode("utf-8")) or {}).get("code")
            except Exception:
                code = None
            err = {401: "clé CompSniper refusée", 429: "quota CompSniper atteint"}.get(e.code, f"CompSniper HTTP {e.code}") + (f" ({code})" if code else "")
            _ERREUR.update(le=time.time(), texte=err)
            return [], err
        except Exception as e:
            _ERREUR.update(le=time.time(), texte="CompSniper injoignable (" + type(e).__name__ + ")")
            return [], _ERREUR["texte"]
        _compter(chasseur and not principal, sport)         # une requete reussie = une requete du forfait (les echecs : gratuits)
    finally:
        if pris:
            _verrou.release()
    import vendues
    ventes = lire_reponse(d, vendues._taux_usd_cad() or 1.37)
    try:
        c = _cx()
        try:
            c.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?)", (q, time.time(), json.dumps(ventes, ensure_ascii=False)))
            c.commit()
        finally:
            c.close()
    except sqlite3.Error:
        pass
    try:
        import base_ventes
        base_ventes.noter(q, ventes)                 # nos archives : la prochaine fois, sans appel
    except Exception:
        pass
    return ventes, None


def carte(titre_ou_cib, chasseur=False):
    """Les ventes d'un an de LA carte (sa recherche habituelle, comme SoldComps). -> liste de ventes (toutes, a filtrer)."""
    import cartes_match
    cib = titre_ou_cib if isinstance(titre_ou_cib, dict) else cartes_match.cible_titre(titre_ou_cib)
    q = cartes_match.requete_ebay(cib)
    if not q:
        return []
    return rechercher(q, chasseur=chasseur)[0]


def etat():
    u = utilises()
    return {"actif": actif(), "mois": u["mois"], "budget_mois": budget_mois(), "chasseur_jour": u["chasseur"],
            "budget_jour": budget_jour(), "erreur": _ERREUR["texte"] if time.time() - _ERREUR["le"] < 6 * 3600 else None}
