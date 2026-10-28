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
    return {"titre": it.get("title") or "", "prix": round(cad, 2), "le": str(it.get("endedAt") or "")[:10], "ts": str(it.get("endedAt") or "")[:19],
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
    e = _ERREURS.get(q.lower())
    if e and time.time() - e[0] < 600:          # 27 oct 2026 (revue) : une recherche en erreur n'est pas refaite avant 10 min
        return {"ventes": [], "erreur": e[1]}
    taux = _taux_usd_cad()
    ventes, vus, erreur = [], {}, None
    for i, site in enumerate(sites()):
        if i and utilises_aujourdhui() >= plafond_jour() * (0.7 if fond else 1.0):
            break                                   # le budget du jour : le site principal d'abord
        d, err = _appel(q, site)
        if err:
            erreur = erreur or err
            if i == 0:
                _noter_erreur(q, err)
                return {"ventes": [], "erreur": err}
            continue
        for v in (_vers_vente(it, taux) for it in (d or {}).get("items") or []):
            if not v:
                continue
            v["site"] = site
            k = _id_vente(v)
            if k and k in vus:                      # la meme vente vue sur les deux sites : on la garde une fois
                continue
            if k:
                vus[k] = True
            ventes.append(v)
    _cache_ecrire(q.lower(), ventes)
    try:                                       # 26 oct 2026 - la base des ventes (tendances) garde tout, sans appel de plus
        import base_ventes
        base_ventes.noter(q, ventes)
    except Exception:
        pass
    return {"ventes": ventes, "erreur": None}


def sites():
    """28 oct 2026 (Mathieu : « Canada, y'en a énormément et c'est notre clientèle #1 ») : les ventes d'eBay.com ET
    d'eBay.ca (une recherche par site, fusionnees, doublons retires). LR_SOLDCOMPS_SITES pour changer (ex. « ebay.com »)."""
    l = [x.strip().lower() for x in (os.environ.get("LR_SOLDCOMPS_SITES") or "ebay.com,ebay.ca").split(",") if x.strip()]
    return [x for x in l if x in SITES_OK] or ["ebay.com"]


SITES_OK = {"ebay.com", "ebay.ca", "ebay.co.uk", "ebay.de", "ebay.fr", "ebay.it", "ebay.es", "ebay.com.au"}


def _id_vente(v):
    import re
    m = re.search(r"/itm/(?:[^/?]+/)?(\d{9,15})", str(v.get("url") or ""))
    return m.group(1) if m else None


def _appel(q, site):
    """Une requete SoldComps (compte au budget AVANT l'appel). -> (donnees, erreur)"""
    url = URL_API + "/v1/scrape?" + urllib.parse.urlencode({"keyword": q, "categoryId": CATEGORIE_CARTES, "count": NB_PAR_REQUETE,
                                                            "ebaySite": site, "hydrateBoa": "true"})
    with _verrou:
        attente = INTERVALLE_MIN_S - (time.time() - _DERNIER[0])
        if attente > 0:
            time.sleep(attente)
        _DERNIER[0] = time.time()
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + _cle(), "Accept": "application/json"})
    _compter()                                  # 27 oct 2026 (revue) : compte AVANT l'appel (un echec coute aussi au budget)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        return None, {401: "clé SoldComps refusée", 429: "quota SoldComps atteint"}.get(e.code, f"SoldComps HTTP {e.code}")
    except Exception as e:
        return None, "SoldComps injoignable (" + type(e).__name__ + ")"


_ERREURS = {}
_DERNIERE = {}


def derniere_erreur():
    """28 oct 2026 : pour l'admin, la derniere erreur de SoldComps (quota, cle, panne)."""
    return dict(_DERNIERE) if _DERNIERE else None


def _noter_erreur(q, err):
    if len(_ERREURS) > 2000:
        _ERREURS.clear()
    _ERREURS[q.lower()] = (time.time(), err)
    _DERNIERE.update(erreur=err, le=time.time())


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
    # 27 oct 2026 (revue) : la valeur affichee passe par les MEMES garde-fous que les deals (valeur_sure) : sinon aucune
    import deals
    med, _r = deals.valeur_sure([v for v in tout if v.get("prix")], texte if not requete else "")
    if not isinstance(med, (int, float)):
        med = None
    return {"ventes": tout[:n], "mediane": med, "valeur_sure": med is not None, "nb": len(tout), "derniere": tout[0]["le"] if tout else None,
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


def autres_joueurs(titre, n=12, fond=False):
    """27 oct 2026 (Mathieu : « Colton Parayko pas de comp, mais on peut montrer des ventes de joueurs de la meme carte ») :
    les ventes de la MEME carte (meme produit, insert, parallele, numerotation, auto, patch) par D'AUTRES joueurs.
    C'est un repere de prix (la valeur depend du joueur), jamais un verdict de deal."""
    import cartes_match
    cib = cartes_match.cible_titre(titre)
    j = cib.get("joueur")
    if cib.get("exclu") or not j:
        return None
    noms = set(j.split())
    cib2 = dict(cib, joueur=None, mots=[m for m in cib["mots"] if m not in noms],
                texte=" ".join(w for w in cib["texte"].split() if w not in noms))
    if not cib2["mots"]:
        return None
    q = cartes_match.requete_ebay(cib2)
    r = rechercher(q, fond=fond)
    l = []
    for v in r.get("ventes") or []:
        raisons = [x for x in cartes_match.raisons_refus(cib2, v.get("titre") or "") if not x.startswith(("autre joueur", "plusieurs joueurs"))]
        if raisons or not v.get("prix"):
            continue
        jv = cartes_match.joueur_du_titre(v.get("titre") or "")
        if jv and jv.split()[-1] in noms:
            continue                                       # le meme joueur : ce sont ses ventes, pas un repere
        l.append(dict(v, joueur=" ".join(w.capitalize() for w in (jv or "").split())))
    if not l:
        return {"ventes": [], "nb": 0, "q": q, "erreur": r.get("erreur")}
    l.sort(key=lambda v: str(v.get("le") or ""), reverse=True)
    prix = sorted(v["prix"] for v in l)
    return {"ventes": l[:n], "nb": len(l), "mediane": round(statistics.median(prix), 2), "min": prix[0], "max": prix[-1],
            "joueurs": len({v["joueur"] for v in l if v.get("joueur")}), "q": q}


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
