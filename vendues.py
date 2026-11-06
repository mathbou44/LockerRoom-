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
from datetime import datetime, timedelta

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


# 3 nov 2026 (Mathieu : « le jeudi, beaucoup d'encheres finissent ; on pourrait modifier la limite pour cette journee ? ») :
# le budget du jour suit le jour de la semaine (Montreal), SANS changer le total de la semaine : le jeudi recoit plus, le
# mercredi un peu plus (les encans du jeudi se verifient la veille aussi), les autres jours un peu moins. LR_POIDS_JOURS
# (Render) pour changer, ex. « jeu:1.6,mer:1.2,dim:1.2 » : les jours non nommes se partagent le reste (total = 7 jours).
JOURS = ("lun", "mar", "mer", "jeu", "ven", "sam", "dim")
POIDS_DEFAUT = "jeu:1.6,mer:1.2"


def poids_jours():
    """-> {jour: poids}, moyenne 1 sur la semaine."""
    explicites = {}
    for x in str(os.environ.get("LR_POIDS_JOURS") or POIDS_DEFAUT).split(","):
        k, _s, v = x.strip().partition(":")
        try:
            if k.strip()[:3].lower() in JOURS:
                explicites[k.strip()[:3].lower()] = max(0.3, min(3.0, float(v)))
        except ValueError:
            pass
    reste = [j for j in JOURS if j not in explicites]
    autre = max(0.3, (7 - sum(explicites.values())) / len(reste)) if reste else 1.0
    p = {j: explicites.get(j, autre) for j in JOURS}
    tot = sum(p.values())
    return {j: round(v * 7 / tot, 3) for j, v in p.items()}


def poids_aujourdhui():
    try:
        from zoneinfo import ZoneInfo
        wd = datetime.now(ZoneInfo("America/Toronto")).weekday()
    except Exception:
        wd = (datetime.utcnow() - timedelta(hours=4)).weekday()
    return poids_jours()[JOURS[wd]]


def budget_du_jour(base):
    """Un budget par jour (SoldComps, verifications) ajuste au jour de la semaine ; meme total sur 7 jours."""
    if not base or base <= 0:
        return 0                                   # un budget a zero reste a zero (aucun appel)
    return max(1, int(round(base * poids_aujourdhui())))


def plafond_jour():
    try:
        base = int(os.environ.get("LR_SOLDCOMPS_JOUR") or 150)
    except ValueError:
        base = 150
    return budget_du_jour(base)


def _cx():
    import comptes
    ch = os.path.join(comptes.DONNEES, "cache_vendues.sqlite")
    neuf = ch not in _FAITES or not os.path.exists(ch)
    c = sqlite3.connect(ch, timeout=30)
    if neuf:     # 4 nov 2026 (vitesse) : les tables une fois par processus
        c.execute("CREATE TABLE IF NOT EXISTS cache (q TEXT PRIMARY KEY, le REAL, ventes TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS compteur (jour TEXT PRIMARY KEY, n INTEGER)")
        _FAITES.add(ch)
    if not _MIGRE:
        _migrer(c)
    return c


_MIGRE = []
_FAITES = set()


def _migrer(c):
    """29 oct 2026 : passage du jour UTC au jour de Montreal. Une seule fois : les credits deja depenses aujourd'hui
    (compteur UTC du moment) sont repris dans le jour de Montreal, pour que le changement ne redonne pas un budget neuf."""
    try:
        if not c.execute("SELECT 1 FROM compteur WHERE jour='mtl:migre'").fetchone():
            j_utc, j = datetime.utcnow().strftime("%Y-%m-%d"), jour()
            for suf in ("", ":verif"):
                r = c.execute("SELECT n FROM compteur WHERE jour=?", (j_utc + suf,)).fetchone()
                if r and r[0]:
                    c.execute("INSERT INTO compteur VALUES (?, ?) ON CONFLICT(jour) DO UPDATE SET n = MAX(n, excluded.n)", (j + suf, int(r[0])))
            c.execute("INSERT OR IGNORE INTO compteur VALUES ('mtl:migre', 1)")
            c.commit()
        _MIGRE.append(1)
    except sqlite3.Error:
        pass


def _cache_lire(q, age_max=None):
    try:
        c = _cx()
        try:
            r = c.execute("SELECT le, ventes FROM cache WHERE q=?", (q,)).fetchone()
        finally:
            c.close()
        if r and time.time() - r[0] < (CACHE_S if age_max is None else age_max):
            return json.loads(r[1])
    except (sqlite3.Error, ValueError):
        pass
    return None


def _cache_ecrire(q, ventes, age=0):
    """age : le resultat compte comme vieux de `age` secondes (un resultat partiel : 10 minutes de cache)."""
    with _verrou:
        c = _cx()
        try:
            c.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?)", (q, time.time() - age, json.dumps(ventes)))
            c.commit()
        finally:
            c.close()


def jour():
    """29 oct 2026 : le jour du budget est celui de Montreal (minuit), comme l'admin et le chasseur (avant : le jour du
    serveur, en UTC : le compteur repartait a 20 h et les deux budgets ne parlaient pas du meme jour)."""
    try:
        from zoneinfo import ZoneInfo
        j = datetime.now(ZoneInfo("America/Toronto")).strftime("%Y-%m-%d")
    except Exception:
        j = (datetime.utcnow() - timedelta(hours=4)).strftime("%Y-%m-%d")
    return "mtl:" + j                          # cle distincte des anciens jours UTC (sinon demain partirait a 706)


def _compte_cle():
    """Le compte de la requete (multi-comptes), pour sa part du budget du jour : « c:<empreinte> »."""
    import hashlib
    import comptes
    cid = comptes.courant() if comptes.MULTI else None
    return ("c:" + hashlib.sha256(str(cid).encode()).hexdigest()[:12]) if cid else None


def part_compte():
    """Ce qu'un compte peut depenser par jour en recherches (20 % du budget du jour, 20 au moins ; LR_SOLDCOMPS_COMPTE)."""
    try:
        v = int(os.environ.get("LR_SOLDCOMPS_COMPTE") or 0)
    except ValueError:
        v = 0
    return v or max(20, int(plafond_jour() * 0.20))


def utilises_aujourdhui(usage=None):
    """Requetes SoldComps du jour ; usage="verif" : celles des verifications de deals seulement.
    29 oct 2026 (Mathieu : « il ne faut plus que cela arrive ») : si le compteur ne peut pas etre lu, on fait comme si le
    budget etait epuise (avant : 0, donc aucune limite). Jamais de credits depenses a l'aveugle."""
    for essai in range(3):
        try:
            c = _cx()
            try:
                r = c.execute("SELECT n FROM compteur WHERE jour=?", (jour() + (":" + usage if usage else ""),)).fetchone()
            finally:
                c.close()
            return int(r[0]) if r else 0
        except sqlite3.Error:
            time.sleep(0.2 * (essai + 1))
    return 10 ** 9


def _compter(usage=None, cpt=None):
    with _verrou:
        c = _cx()
        try:
            j = jour()
            c.execute("INSERT INTO compteur VALUES (?, 1) ON CONFLICT(jour) DO UPDATE SET n = n + 1", (j,))
            if cpt:
                c.execute("INSERT INTO compteur VALUES (?, 1) ON CONFLICT(jour) DO UPDATE SET n = n + 1", (j + ":" + cpt,))
            if usage:
                c.execute("INSERT INTO compteur VALUES (?, 1) ON CONFLICT(jour) DO UPDATE SET n = n + 1", (j + ":" + usage,))
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


# 28 oct 2026 (admin : « SoldComps 706 / 700 », 15 245 verifications de deals refusees) : les autres taches de fond (valeurs
# des produits, chasse par joueur, repere des prix) avaient mange tout le budget du jour avant le soir. Maintenant elles ont
# au plus la moitie du budget de fond ; l'autre moitie est gardee aux verifications de deals. Et eBay.ca seulement pour les
# recherches des utilisateurs et les verifications de deals (les autres taches : eBay.com, 1 requete au lieu de 2).
PART_AUTRES_FOND = 0.25          # 29 oct 2026 : 0,35 -> 0,25 : les verifications de deals (encans) passent d'abord


def _budget_ok(fond, usage):
    tot, pl = utilises_aujourdhui(), plafond_jour()
    if not fond:
        return tot < pl
    if tot >= pl * 0.7:
        return False
    # 30 oct 2026 : « prio » = la reserve des 4 vendeurs prioritaires (deals.PRIO_VERIF_JOUR) : comme les verifications
    return usage in ("verif", "prio") or (tot - utilises_aujourdhui("verif") - utilises_aujourdhui("prio")) < pl * PART_AUTRES_FOND


def rechercher(q, fond=True, usage=None):
    """Ventes eBay d'une recherche (toutes cartes confondues : filtrer ensuite). {ventes, erreur, cache}."""
    q = " ".join(str(q or "").split())[:120]
    if not q:
        return {"ventes": [], "erreur": None}
    deja = _cache_lire(q.lower())
    if deja is not None:
        return {"ventes": deja, "erreur": None, "cache": True}
    if not actif():
        return {"ventes": [], "erreur": "inactif"}
    if not _budget_ok(fond, usage):                 # les taps passent avant les taches de fond
        return {"ventes": [], "erreur": "plafond du jour"}
    cpt = _compte_cle() if not fond else None
    if cpt and utilises_aujourdhui(cpt) >= part_compte():
        # 3 nov 2026 (revue de securite) : un seul compte ne vide pas le budget de tout le monde (titres inventes, en boucle)
        return {"ventes": [], "erreur": "plafond du jour"}
    # 3 nov 2026 (revue) : SoldComps en panne -> les taches de fond attendent 2 minutes au lieu de bruler des credits
    # (chaque essai compte avant l'appel) sur d'autres cartes ; les gestes de l'utilisateur essaient quand meme
    if fond and time.time() < _PANNE[0]:
        vieux = _cache_lire(q.lower(), age_max=45 * 86400)
        return {"ventes": vieux, "erreur": None, "cache": True, "vieux_cache": True} if vieux else {"ventes": [], "erreur": "SoldComps injoignable (panne)"}
    e = _ERREURS.get(q.lower())
    if e and not fond and "injoignable" in str(e[1]) and time.time() - (e[0] + 540) > 15:
        e = None                                # 3 nov 2026 : « Reessayer » apres une panne passagere : on reessaie vraiment
    if e and time.time() - e[0] < 600:
        vieux = _cache_lire(q.lower(), age_max=45 * 86400)          # 3 nov 2026 (revue) : les ventes deja lues, en secours
        if vieux:
            return {"ventes": vieux, "erreur": None, "cache": True, "vieux_cache": True}          # 27 oct 2026 (revue) : une recherche en erreur n'est pas refaite avant 10 min
        return {"ventes": [], "erreur": e[1]}
    taux = _taux_usd_cad()
    ventes, vus, erreur = [], {}, None
    les_sites = sites() if (not fond or usage == "verif") else sites()[:1]
    pre = {}
    if not fond and len(les_sites) > 1 and utilises_aujourdhui() + len(les_sites) <= plafond_jour():
        # 28 oct 2026 (vitesse du scan) : une demande de l'utilisateur interroge les deux sites EN MEME TEMPS (avant : l'un
        # apres l'autre, ~1 s d'attente en plus) ; les taches de fond gardent le rythme d'un appel par seconde
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=len(les_sites)) as ex:
            pre = dict(zip(les_sites, ex.map(lambda st: _appel(q, st, attendre=False, usage=usage, compte=cpt), les_sites)))
    for i, site in enumerate(les_sites):
        if site not in pre and i and not _budget_ok(fond, usage):
            break                                   # le budget du jour : le site principal d'abord
        # 29 oct 2026 (Mathieu : « des credits depenses dans le vide ») : une verification de deal interroge eBay.ca
        # seulement si eBay.com n'a pas deja 3 ventes : 1 credit au lieu de 2 la plupart du temps
        if site not in pre and i and usage == "verif" and len(ventes) >= 3:
            break
        d, err = pre[site] if site in pre else _appel(q, site, usage=usage, compte=cpt)
        if err:
            erreur = erreur or err
            # 3 nov 2026 (Mathieu, Jordan Beam Team : « pourquoi ca sort rien ? », SoldComps TimeoutError) : eBay.com en
            # panne mais eBay.ca lu en meme temps -> on garde eBay.ca au lieu de tout jeter
            if i == 0 and not any(not e2 for s2, (d2, e2) in pre.items() if s2 != site):
                _noter_erreur(q, err)
                vieux = _cache_lire(q.lower(), age_max=45 * 86400)        # les ventes lues dans les 45 derniers jours
                if vieux:
                    return {"ventes": vieux, "erreur": None, "cache": True, "vieux_cache": True}
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
    # 3 nov 2026 (revue) : un resultat PARTIEL (un site en panne) n'est pas garde 3 jours et n'ecrase pas des ventes deja lues
    if not erreur:
        _cache_ecrire(q.lower(), ventes)
    elif ventes and not _cache_lire(q.lower(), age_max=45 * 86400):
        _cache_ecrire(q.lower(), ventes, age=CACHE_S - 600)
    try:                                       # 26 oct 2026 - la base des ventes (tendances) garde tout, sans appel de plus
        import base_ventes
        base_ventes.noter(q, ventes)
    except Exception:
        pass
    # un site en panne et l'autre sans vente : on ne sait pas (pas « aucune vente ») ; les ventes deja lues en secours
    if erreur and not ventes:
        vieux = _cache_lire(q.lower(), age_max=45 * 86400)
        if vieux:
            return {"ventes": vieux, "erreur": None, "cache": True, "vieux_cache": True}
    return {"ventes": ventes, "erreur": erreur if (erreur and not ventes) else None, "partiel": bool(erreur)}


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


def _appel(q, site, attendre=True, usage=None, compte=None):
    """Une requete SoldComps (compte au budget AVANT l'appel). -> (donnees, erreur)"""
    url = URL_API + "/v1/scrape?" + urllib.parse.urlencode({"keyword": q, "categoryId": CATEGORIE_CARTES, "count": NB_PAR_REQUETE,
                                                            "ebaySite": site, "hydrateBoa": "true"})
    if attendre:
        with _verrou:
            attente = INTERVALLE_MIN_S - (time.time() - _DERNIER[0])
            if attente > 0:
                time.sleep(attente)
            _DERNIER[0] = time.time()
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + _cle(), "Accept": "application/json"})
    _compter(usage, compte)                     # 27 oct 2026 (revue) : compte AVANT l'appel (un echec coute aussi au budget)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        return None, {401: "clé SoldComps refusée", 429: "quota SoldComps atteint"}.get(e.code, f"SoldComps HTTP {e.code}")
    except Exception as e:
        return None, "SoldComps injoignable (" + type(e).__name__ + ")"


_ERREURS = {}
_DERNIERE = {}
_PANNE = [0.0]                   # SoldComps ne repond pas : les taches de fond attendent jusqu'a cette heure


def derniere_erreur():
    """28 oct 2026 : pour l'admin, la derniere erreur de SoldComps (quota, cle, panne)."""
    return dict(_DERNIERE) if _DERNIERE else None


def _noter_erreur(q, err):
    if len(_ERREURS) > 2000:
        _ERREURS.clear()
    # 3 nov 2026 : une panne passagere (delai depasse) n'est bloquee qu'une minute ; un refus (cle, quota) 10 minutes
    _ERREURS[q.lower()] = (time.time() - (540 if "injoignable" in str(err) else 0), err)
    if "injoignable" in str(err) or "quota" in str(err):
        _PANNE[0] = time.time() + 120
    _DERNIERE.update(erreur=err, le=time.time())


def archives(cib, jours=365, max_=400):
    """7 nov 2026 (Mathieu : une Nazar Future Watch Auto Inscribed « aucune vente trouvee », 130point en a 6 : eBay et
    SoldComps ne montrent que les 90 derniers jours de ventes) : les ventes de la MEME carte gardees dans nos archives
    (base_ventes : chaque recherche y depose toutes ses ventes), jusqu'a un an. Rien n'est appele : aucun credit."""
    import cartes_match
    import base_ventes
    nom = [w for w in (cib.get("joueur") or "").split() if len(w) >= 3]
    if not nom:
        return []
    depuis = (datetime.now() - timedelta(days=jours)).strftime("%Y-%m-%d")
    try:
        import comptes
        ch = os.path.join(comptes.DONNEES, "base_ventes.sqlite")
        if not os.path.exists(ch):
            return []
        base_ventes._cx().close()                           # les tables (une fois par processus)
        c = sqlite3.connect(ch, timeout=3)                  # une lecture : jamais 30 s d'attente derriere une ecriture du chasseur
        try:
            l = c.execute("SELECT titre, prix, le, photo, url, offre FROM ventes WHERE le >= ? AND titre LIKE ? "
                          "ORDER BY le DESC LIMIT ?", (depuis, "%" + nom[-1].lower() + "%", max_ * 5)).fetchall()
        finally:
            c.close()
    except Exception:
        return []
    out, vus = [], set()
    for t, p, le, ph, u, of in l:
        k = u or f"{t}|{le}|{p}"
        if k in vus or not p or cartes_match.raisons_refus(cib, t or ""):
            continue
        vus.add(k)
        out.append({"titre": t, "prix": p, "le": le, "photo": ph, "url": u, "offre": bool(of), "source": "archives"})
        if len(out) >= max_:
            break
    return out


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
    if not requete:                             # 7 nov 2026 : + nos propres archives (eBay ne montre que 90 jours de ventes)
        vus_u = {str(v.get("url") or "") for v in tout if v.get("url")}
        tout += [v for v in archives(cib) if str(v.get("url") or "") not in vus_u]
    if not requete:                             # 4 nov 2026 : la fiche d'une annonce (une seule carte precise)
        tout = _sans_aberrants(tout)
    tout.sort(key=lambda v: str(v.get("le") or ""), reverse=True)
    # 27 oct 2026 (revue) : la valeur affichee passe par les MEMES garde-fous que les deals (valeur_sure) : sinon aucune
    import deals
    med, _r = deals.valeur_sure([v for v in tout if v.get("prix")], texte if not requete else "")
    if not isinstance(med, (int, float)):
        med = None
    return {"ventes": tout[:n], "mediane": med, "valeur_sure": med is not None, "nb": len(tout), "derniere": tout[0]["le"] if tout else None,
            "ebay": len(ebay), "communaute": len(comm), "erreur": r.get("erreur") if not tout else None, "vieux_cache": bool(r.get("vieux_cache")),
            "erreur_ebay": r.get("erreur"),
            "points": [[v.get("le"), v["prix"]] for v in tout[:200] if v.get("le") and v.get("prix")],
            "tendance": tendance(tout)}


def _sans_aberrants(l, facteur=4.0):
    """4 nov 2026 (Mathieu : une Jordan Beam Team a 2 000 $ montree avec des ventes a 3 $ et 24 $ : « pas toute la bonne
    carte ») : avec 4 ventes et plus, une vente 4 fois sous ou au-dessus de la mediane n'est pas la meme carte."""
    if len(l) < 4:
        return l
    m = statistics.median(v["prix"] for v in l if v.get("prix")) if any(v.get("prix") for v in l) else None
    if not m:
        return l
    return [v for v in l if v.get("prix") and m / facteur <= v["prix"] <= m * facteur]


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
            l = _sans_aberrants([v for v in r.get("ventes") or [] if not cartes_match.raisons_refus(cib, v["titre"])])
            if len(l) >= 3:
                l.sort(key=lambda v: str(v.get("le") or ""), reverse=True)
                prix = [v["prix"] for v in l]
                med = cartes_match.mediane_robuste(prix)[0] if len(prix) >= 4 else round(statistics.median(prix), 2)
                return {"ventes": l[:n], "mediane": med, "nb": len(l), "derniere": l[0]["le"], "ebay": len(l), "communaute": 0,
                        "erreur": None, "points": [[v.get("le"), v["prix"]] for v in l[:200] if v.get("le")], "tendance": tendance(l)}
        except Exception:
            pass
    return memes(titre, requete=False, n=n, fond=fond)


def autres_saisons(titre, fond=False):
    """7 nov 2026 (Mathieu : la Ron Francis 2024-25 Clear Cut Outburst Auto /25 sans aucune vente : « mettre les annees a
    cote pour la meme carte, montrer les cartes similaires, mais dire qu'il n'y a pas de comp ») : les ventes de la meme
    carte des saisons voisines (la recherche des ventes ne contient jamais l'annee : le meme appel, deja en cache).
    -> deals.valeur_autre_saison (valeur, « autre_saison », n, ventes avec leur « saison ») ou None."""
    import cartes_match
    import deals
    cib = cartes_match.cible_titre(titre)
    if cib.get("exclu") or not cib.get("joueur") or not cib.get("annee"):
        return None
    q = cartes_match.requete_ebay(cib)
    if not q:
        return None
    r = rechercher(q, fond=fond)
    return deals.valeur_autre_saison({"titre": titre}, [v for v in r.get("ventes") or [] if v.get("prix")], cib)


def similaires(titre, fond=False):
    """7 nov 2026 (Mathieu : « les no sales : analyser les cartes similaires et donner un prix approximatif ») : les ventes du
    meme joueur, meme produit / insert (recherche large : sans annee, numerotation ni parallele), puis deals.valeur_approx.
    -> (valeur, « approx », n, ventes) ou None."""
    import cartes_match
    import deals
    cib = cartes_match.cible_titre(titre)
    if cib.get("exclu") or not cib.get("joueur"):
        return None
    l = []
    for q in dict.fromkeys(x for x in (cartes_match.requete_ebay(cib), cartes_match.requete_ebay(deals.cible_large(cib))) if x):
        l += [v for v in rechercher(q, fond=fond).get("ventes") or [] if v.get("prix")]
    l += archives(dict(cib, annee=None, serie=None, veut_serie=False, paralleles=set()), max_=200)
    return deals.valeur_approx({"titre": titre}, l, cib)


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
    return {"actif": actif(), "aujourdhui": utilises_aujourdhui(), "plafond": plafond_jour(), "poids_jour": poids_aujourdhui(),
            "poids_semaine": poids_jours()}
