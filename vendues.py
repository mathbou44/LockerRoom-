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



def _coupe():
    """10 nov 2026 : comps = admin seulement pour le lancement (lockerroom.comps_permis)."""
    try:
        import lockerroom
        return not lockerroom.comps_permis()
    except Exception:
        return False

def _cs_actif():
    try:
        import historique
        return historique.actif()
    except Exception:
        return False


def source():
    """12 nov 2026 (Mathieu : « je peux remplacer SoldComps par CompSniper ») : la source principale des ventes.
    LR_VENTES_SOURCE (Render) = « compsniper » ou « soldcomps » pour choisir ; sinon SoldComps s'il a sa cle, CompSniper
    s'il n'y a plus que lui (on retire SOLDCOMPS_CLE : la bascule se fait toute seule)."""
    v = (os.environ.get("LR_VENTES_SOURCE") or "").strip().lower()
    if v == "compsniper" and _cs_actif():
        return "compsniper"
    if _cle():
        return "soldcomps"
    return "compsniper" if _cs_actif() else "soldcomps"


def actif():
    return bool(_cle()) or _cs_actif()


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
    if source() == "compsniper":
        return _plafond_cs()
    try:
        base = int(os.environ.get("LR_SOLDCOMPS_JOUR") or 150)
    except ValueError:
        base = 150
    return budget_du_jour(base)


def _plafond_cs():
    """CompSniper principal : le budget du jour = ce qui reste du mois (LR_HISTORIQUE_MOIS) reparti sur les jours qui
    restent, ajuste au jour de la semaine (le jeudi plus). Les credits deja pris aujourd'hui restent dans le calcul."""
    import calendar
    import historique
    m = datetime.utcnow()
    u = historique.utilises()
    reste_j = calendar.monthrange(m.year, m.month)[1] - m.day + 1
    reste = max(0, historique.budget_mois() - (u["mois"] - u["jour"]))
    return min(reste, budget_du_jour(max(1, reste // max(1, reste_j)))) if reste else 0


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


def _rembourser(usage=None, cpt=None):
    """9 nov 2026 (SoldComps : « les requetes en echec ne comptent pas et ne sont pas facturees ») : un appel en echec rend
    son credit a NOTRE budget du jour (avant : une panne de SoldComps brulait tout le budget en quelques minutes)."""
    with _verrou:
        c = _cx()
        try:
            j = jour()
            for k in [j] + ([j + ":" + cpt] if cpt else []) + ([j + ":" + usage] if usage else []):
                c.execute("UPDATE compteur SET n = MAX(0, n - 1) WHERE jour=?", (k,))
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


# 9 nov 2026 (Mathieu : « les comps chient encore », la fiche d'une annonce : « les ventes reelles ne repondent pas ») : un
# geste de l'utilisateur n'attend pas SoldComps plus de 15 s par appel (la fiche fait parfois 3 ou 4 recherches de suite)
DELAI_TAP = 15


def _secours(q, fond, usage=None):
    """9 nov 2026 (Mathieu, panne chez SoldComps : « on doit avoir une alternative, on est trop dependant ») : quand
    SoldComps ne repond pas et qu'on n'a rien en cache, un geste de l'utilisateur passe par CompSniper (l'historique d'un
    an, budget du mois) : les memes ventes eBay, une autre source. Jamais pour les taches de fond (budget du mois).
    10 nov 2026 (« le plus de sources possible, une de base et les autres pour raffiner et sauver ») : puis TheCardAPI
    (aussi pour les verifications de deals, sur sa part du jour)."""
    if not fond and source() != "compsniper":         # CompSniper principal : deja essaye (et son budget du jour)
        try:
            import historique
            if historique.actif():
                ventes, err = historique.rechercher(q)
                if not err and ventes:
                    depuis = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")      # comme SoldComps : 90 jours
                    v90 = [v for v in ventes if str(v.get("le") or "") >= depuis] or ventes
                    return {"ventes": v90, "erreur": None, "secours": "compsniper"}
        except Exception as e:
            print("Ventes (secours CompSniper) : " + repr(e), flush=True)
    if fond and usage not in ("verif", "prio"):
        return None
    try:
        import thecardapi
        ventes, err = thecardapi.rechercher(q, limite=100, usage="tap" if not fond else "secours", delai=DELAI_TAP if not fond else 20)
        if not err and ventes:
            try:
                import base_ventes
                base_ventes.noter(q, ventes)
            except Exception:
                pass
            return {"ventes": ventes, "erreur": None, "secours": "thecardapi"}
    except Exception as e:
        print("Ventes (secours TheCardAPI) : " + repr(e), flush=True)
    return None


_POOL = []


def raffiner_lancer(q):
    """10 nov 2026 : les ventes que TheCardAPI a de PLUS (les derniers jours surtout), lues EN MEME TEMPS que SoldComps
    (aucune attente de plus). Un geste de l'utilisateur seulement. -> un futur, ou None (inactif)."""
    try:
        import thecardapi
        if not q or not thecardapi.actif():
            return None
        if not _POOL:
            from concurrent.futures import ThreadPoolExecutor
            _POOL.append(ThreadPoolExecutor(max_workers=4, thread_name_prefix="raffiner"))
        return _POOL[0].submit(thecardapi.rechercher, q, None, 50, "raffiner", 10)
    except Exception as e:
        print("Ventes (raffiner) : " + repr(e), flush=True)
        return None


def raffiner(q, ventes, futur):
    """Ajoute aux ventes celles du futur (raffiner_lancer), doublons retires (meme numero d'annonce)."""
    if futur is None:
        return ventes
    try:
        extra, err = futur.result(timeout=12)
    except Exception:
        return ventes
    if err or not extra:
        return ventes
    vus = {_id_vente(v) or v.get("url") for v in ventes}
    neuves = [v for v in extra if (_id_vente(v) or v.get("url")) not in vus]
    if neuves:
        try:
            import base_ventes
            base_ventes.noter(q, neuves)
        except Exception:
            pass
    return ventes + neuves


def rechercher(q, fond=True, usage=None):
    """Ventes eBay d'une recherche (toutes cartes confondues : filtrer ensuite). {ventes, erreur, cache}."""
    if _coupe():
        return {"ventes": [], "erreur": None, "coupe": True}
    q = " ".join(str(q or "").split())[:120]
    if not q:
        return {"ventes": [], "erreur": None}
    deja = _cache_lire(q.lower())
    if deja is not None:
        return {"ventes": deja, "erreur": None, "cache": True}
    if not actif():
        return {"ventes": [], "erreur": "inactif"}
    if not _budget_ok(fond, usage):                 # les taps passent avant les taches de fond
        return _secours(q, fond, usage) or {"ventes": [], "erreur": "plafond du jour"}
    cpt = _compte_cle() if not fond else None
    if cpt and utilises_aujourdhui(cpt) >= part_compte():
        # 3 nov 2026 (revue de securite) : un seul compte ne vide pas le budget de tout le monde (titres inventes, en boucle)
        return {"ventes": [], "erreur": "plafond du jour"}
    if source() == "compsniper":
        r_cs = _par_compsniper(q, fond, usage, cpt)
        if r_cs is not None:
            return r_cs                         # None : CompSniper en erreur et SoldComps encore la (jusqu'au 18 nov) : en secours
    # 3 nov 2026 (revue) : SoldComps en panne -> les taches de fond attendent 2 minutes au lieu de bruler des credits
    # (chaque essai compte avant l'appel) sur d'autres cartes ; les gestes de l'utilisateur essaient quand meme
    if fond and time.time() < _PANNE[0]:
        vieux = _cache_lire(q.lower(), age_max=45 * 86400)
        return {"ventes": vieux, "erreur": None, "cache": True, "vieux_cache": True} if vieux else \
            (_secours(q, fond, usage) or {"ventes": [], "erreur": "SoldComps injoignable (panne)"})
    if not fond and time.time() < _PANNE[0] and _PANNE_N[0] >= 2:
        if time.time() - _TAP_PANNE[0] < 60:    # 9 nov 2026 : « ne pas reessayer vite » (SoldComps) : les ventes deja lues
            vieux = _cache_lire(q.lower(), age_max=45 * 86400)
            return {"ventes": vieux, "erreur": None, "cache": True, "vieux_cache": True} if vieux else (_secours(q, fond, usage) or {"ventes": [], "erreur": "Ventes réelles momentanément indisponibles (panne chez le fournisseur)"})
        _TAP_PANNE[0] = time.time()
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
    # 11 nov 2026 (SoldComps : « eBay.com, .co.uk et .com.au sont revenus ; les autres sites recuperent encore ») : un site
    # secondaire en panne (eBay.ca) est saute 30 min ; avant, chaque recherche l'attendait 25 s et toute la chasse ralentissait
    les_sites = [st for k_, st in enumerate(les_sites) if k_ == 0 or time.time() >= _SITE_PANNE.get(st, 0)]
    pre = {}
    if not fond and len(les_sites) > 1 and utilises_aujourdhui() + len(les_sites) <= plafond_jour():
        # 28 oct 2026 (vitesse du scan) : une demande de l'utilisateur interroge les deux sites EN MEME TEMPS (avant : l'un
        # apres l'autre, ~1 s d'attente en plus) ; les taches de fond gardent le rythme d'un appel par seconde
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=len(les_sites)) as ex:
            pre = dict(zip(les_sites, ex.map(lambda st: _appel(q, st, attendre=False, usage=usage, compte=cpt, delai=DELAI_TAP), les_sites)))
    for i, site in enumerate(les_sites):
        if site not in pre and i and not _budget_ok(fond, usage):
            break                                   # le budget du jour : le site principal d'abord
        # 29 oct 2026 (Mathieu : « des credits depenses dans le vide ») : une verification de deal interroge eBay.ca
        # seulement si eBay.com n'a pas deja 3 ventes : 1 credit au lieu de 2 la plupart du temps
        if site not in pre and i and usage == "verif" and len(ventes) >= 3:
            break
        d, err = pre[site] if site in pre else _appel(q, site, usage=usage, compte=cpt, delai=25 if fond else DELAI_TAP)
        if err:
            if i and ("injoignable" in str(err) or "HTTP 5" in str(err)):
                _SITE_PANNE[site] = time.time() + 1800              # le site secondaire : on le saute 30 min
                continue
            erreur = erreur or err
            # 3 nov 2026 (Mathieu, Jordan Beam Team : « pourquoi ca sort rien ? », SoldComps TimeoutError) : eBay.com en
            # panne mais eBay.ca lu en meme temps -> on garde eBay.ca au lieu de tout jeter
            if i == 0 and not any(not e2 for s2, (d2, e2) in pre.items() if s2 != site):
                _noter_erreur(q, err)
                vieux = _cache_lire(q.lower(), age_max=45 * 86400)        # les ventes lues dans les 45 derniers jours
                if vieux:
                    return {"ventes": vieux, "erreur": None, "cache": True, "vieux_cache": True}
                return _secours(q, fond, usage) or {"ventes": [], "erreur": err}
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
        sec = _secours(q, fond, usage)
        if sec:
            return sec
    return {"ventes": ventes, "erreur": erreur if (erreur and not ventes) else None, "partiel": bool(erreur)}


def _par_compsniper(q, fond, usage, cpt):
    """12 nov 2026 : CompSniper comme source principale : UNE requete = un an de ventes (eBay ; la regle des 90 jours
    reste dans le jugement des deals, les hits gardent un an). Meme budget du jour, memes compteurs (verif, prio, compte)
    que SoldComps ; une recherche deja en cache chez CompSniper (3 jours) ne compte pas."""
    import historique
    neuf = historique._cache(historique.cle_q(q), CACHE_S) is None
    if neuf:
        if fond:
            with _verrou:                      # 60 requetes / minute chez CompSniper : les taches de fond, une par seconde
                attente = INTERVALLE_MIN_S - (time.time() - _DERNIER[0])
                if attente > 0:
                    time.sleep(attente)
                _DERNIER[0] = time.time()
        _compter(usage, cpt)
        ventes, err = historique.rechercher(q, chasseur=fond, principal=True, cache_s=CACHE_S, delai=25 if fond else DELAI_TAP)
        if err:
            try:
                _rembourser(usage, cpt)        # un echec n'est pas facture
            except Exception:
                pass
    else:
        ventes, err = historique.rechercher(q, principal=True, cache_s=CACHE_S)
    if err:
        if err == "budget":
            err = "plafond du jour"
        if _cle() and err not in ("plafond du jour", "coupe", "inactif"):
            return None                        # 12 nov 2026 : SoldComps encore actif (jusqu'au 18 nov) : il prend le relais
        _noter_erreur(q, err)
        vieux = _cache_lire(q.lower(), age_max=45 * 86400)
        if vieux:
            return {"ventes": vieux, "erreur": None, "cache": True, "vieux_cache": True}
        if fond and usage not in ("verif", "prio"):
            return {"ventes": [], "erreur": err}
        try:
            import thecardapi
            v2, e2 = thecardapi.rechercher(q, limite=100, usage="tap" if not fond else "secours", delai=DELAI_TAP if not fond else 20)
            if not e2 and v2:
                return {"ventes": v2, "erreur": None, "secours": "thecardapi"}
        except Exception:
            pass
        return {"ventes": [], "erreur": err}
    out = []
    for v in ventes or []:
        v = dict(v)
        v.setdefault("ts", v.get("le"))
        v["site"] = "compsniper"
        out.append(v)
    _cache_ecrire(q.lower(), out)
    if neuf:
        comparer_lancer(q, out)
    return {"ventes": out, "erreur": None, "source": "compsniper"}


# 12 nov 2026 (Mathieu : « garde tout ce qui est SoldComps [...] quelques jours vont suffire pour voir si CompSniper est assez
# precis pour qu'on le garde avec les 50 resultats ») : tant que SoldComps repond encore (jusqu'au 18 nov), une partie des
# recherches CompSniper est refaite chez SoldComps (eBay.com, 90 jours) et les deux sont comparees : les ventes de SoldComps
# que CompSniper a aussi, l'ecart de mediane, la vente la plus recente de chacun, les recherches coupees a 50. L'admin voit
# le bilan (tuile « Ordre des credits »). LR_COMPARER_JOUR : combien par jour (15 ; 0 = arrete).
COMPARER_MAX = 300
_COMP_VERROU = threading.Lock()
_COMP_JOUR = {"jour": None, "n": 0}


def _id_item(v):
    import re
    m = re.search(r"/itm/(?:[^/?#]+/)?(\d{9,})", str(v.get("url") or ""))
    return m.group(1) if m else (str(v.get("item_id")) if v.get("item_id") else None)


def _comp_chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "comparaison_sources.json")


def comparer_lancer(q, ventes_cs):
    if not _cle():
        return
    try:
        n_max = int(os.environ.get("LR_COMPARER_JOUR") or 15)
    except ValueError:
        n_max = 15
    j = jour()
    with _COMP_VERROU:
        if _COMP_JOUR["jour"] != j:
            _COMP_JOUR.update(jour=j, n=0)
        if _COMP_JOUR["n"] >= n_max:
            return
        _COMP_JOUR["n"] += 1
    threading.Thread(target=comparer, args=(q, list(ventes_cs)), daemon=True).start()


def comparer(q, ventes_cs, appel=None):
    """Une recherche refaite chez SoldComps (hors budget du jour : SoldComps est deja paye jusqu'au 18 nov) -> une ligne de
    comparaison gardee dans comparaison_sources.json."""
    try:
        if appel is None:
            url = URL_API + "/v1/scrape?" + urllib.parse.urlencode({"keyword": q, "categoryId": CATEGORIE_CARTES, "count": NB_PAR_REQUETE,
                                                                    "ebaySite": "ebay.com", "hydrateBoa": "true"})
            req = urllib.request.Request(url, headers={"Authorization": "Bearer " + _cle(), "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.loads(r.read().decode("utf-8"))
        else:
            d = appel(q)
        taux = _taux_usd_cad()
        sc = [v for v in (_vers_vente(it, taux) for it in (d or {}).get("items") or []) if v]
    except Exception as e:
        print("Comparaison des sources : " + repr(e)[:200], flush=True)
        return None
    depuis = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    cs90 = [v for v in ventes_cs if str(v.get("le") or "") >= depuis]
    ids_cs = {_id_item(v) for v in ventes_cs} - {None}
    ids_sc = [_id_item(v) for v in sc]
    communs = sum(1 for i in ids_sc if i and i in ids_cs)
    med = lambda l: round(statistics.median([v["prix"] for v in l if v.get("prix")]), 2) if any(v.get("prix") for v in l) else None
    ligne = {"le": datetime.now().isoformat(timespec="seconds"), "q": q[:120], "sc": len(sc), "cs": len(ventes_cs), "cs90": len(cs90),
             "communs": communs, "coupe": len(ventes_cs) >= 50, "med_sc": med(sc), "med_cs90": med(cs90),
             "der_sc": max((str(v.get("le") or "") for v in sc), default="") or None,
             "der_cs": max((str(v.get("le") or "") for v in ventes_cs), default="") or None}
    with _COMP_VERROU:
        try:
            with open(_comp_chemin(), encoding="utf-8") as f:
                l = json.load(f) or []
        except (OSError, ValueError):
            l = []
        l = (l + [ligne])[-COMPARER_MAX:]
        try:
            with open(_comp_chemin() + ".tmp", "w", encoding="utf-8") as f:
                json.dump(l, f, ensure_ascii=False)
            os.replace(_comp_chemin() + ".tmp", _comp_chemin())
        except OSError:
            pass
    return ligne


def comparaison_resume():
    """Le bilan CompSniper contre SoldComps : sur les ventes que SoldComps voit (eBay.com, 90 jours), combien CompSniper les a
    aussi ; l'ecart des medianes ; qui a la vente la plus fraiche ; combien de recherches CompSniper sont coupees a 50."""
    try:
        with open(_comp_chemin(), encoding="utf-8") as f:
            l = json.load(f) or []
    except (OSError, ValueError):
        l = []
    if not l:
        return {"n": 0}
    tot_sc = sum(x["sc"] for x in l)
    ecarts = [abs(x["med_cs90"] - x["med_sc"]) / x["med_sc"] for x in l if x.get("med_sc") and x.get("med_cs90")]
    plus_frais = {"cs": sum(1 for x in l if (x.get("der_cs") or "") > (x.get("der_sc") or "")),
                  "sc": sum(1 for x in l if (x.get("der_sc") or "") > (x.get("der_cs") or "")),
                  "egal": sum(1 for x in l if (x.get("der_sc") or "") == (x.get("der_cs") or ""))}
    rien_cs = sum(1 for x in l if x["sc"] and not x["cs90"])
    rien_sc = sum(1 for x in l if x["cs90"] and not x["sc"])
    return {"n": len(l), "depuis": l[0]["le"], "couverture": round(sum(x["communs"] for x in l) / tot_sc, 3) if tot_sc else None,
            "ecart_median": round(statistics.median(ecarts), 3) if ecarts else None, "plus_frais": plus_frais,
            "coupees": sum(1 for x in l if x.get("coupe")), "rien_cs": rien_cs, "rien_sc": rien_sc,
            "ventes_sc": tot_sc, "ventes_cs90": sum(x["cs90"] for x in l), "derniers": l[-8:][::-1]}


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


def _appel(q, site, attendre=True, usage=None, compte=None, delai=25):
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
    _compter(usage, compte)                     # 27 oct 2026 (revue) : compte AVANT l'appel (deux appels en meme temps)
    try:
        with urllib.request.urlopen(req, timeout=delai) as r:
            d = json.loads(r.read().decode("utf-8"))
        _PANNE_N[0] = 0                         # ca repond : fin de la panne
        return d, None
    except urllib.error.HTTPError as e:
        err = {401: "clé SoldComps refusée", 429: "quota SoldComps atteint"}.get(e.code, f"SoldComps HTTP {e.code}")
    except Exception as e:
        err = "SoldComps injoignable (" + type(e).__name__ + ")"
    try:
        _rembourser(usage, compte)              # 9 nov 2026 : un echec n'est pas facture par SoldComps : pas compte non plus
    except Exception:
        pass
    return None, err


_ERREURS = {}
_SITE_PANNE = {}                 # 11 nov 2026 : un site eBay secondaire en panne chez SoldComps -> jusqu'a quand on le saute
_DERNIERE = {}
_PANNE = [0.0]                   # SoldComps ne repond pas : les taches de fond attendent jusqu'a cette heure
_PANNE_N = [0]                   # 9 nov 2026 : echecs de suite (l'attente grandit)
_TAP_PANNE = [0.0]               # 9 nov 2026 : pendant une panne, un geste de l'utilisateur essaie au plus une fois par minute


def derniere_erreur():
    """28 oct 2026 : pour l'admin, la derniere erreur de SoldComps (quota, cle, panne)."""
    return dict(_DERNIERE) if _DERNIERE else None


def _noter_erreur(q, err):
    if len(_ERREURS) > 2000:
        _ERREURS.clear()
    # 3 nov 2026 : une panne passagere (delai depasse) n'est bloquee qu'une minute ; un refus (cle, quota) 10 minutes
    _ERREURS[q.lower()] = (time.time() - (540 if "injoignable" in str(err) else 0), err)
    # 9 nov 2026 (SoldComps : « eBay refuse nos recherches ; ralentissez les essais ») : une panne (injoignable, quota,
    # erreur 5xx ou refus d'eBay) -> les taches de fond attendent de plus en plus longtemps (2, 5, 15, puis 30 min) tant
    # qu'elle dure ; une recherche qui repond remet tout a zero
    if "injoignable" in str(err) or "quota" in str(err) or "HTTP" in str(err):
        _PANNE_N[0] += 1
        _PANNE[0] = time.time() + (120, 300, 900, 1800)[min(3, _PANNE_N[0] - 1)]
    _DERNIERE.update(erreur=err, le=time.time())


def archives(cib, jours=365, max_=400, ignorer=()):
    """7 nov 2026 (Mathieu : une Nazar Future Watch Auto Inscribed « aucune vente trouvee », 130point en a 6 : eBay et
    SoldComps ne montrent que les 90 derniers jours de ventes) : les ventes de la MEME carte gardees dans nos archives
    (base_ventes : chaque recherche y depose toutes ses ventes), jusqu'a un an. Rien n'est appele : aucun credit."""
    if _coupe():
        return []
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
        k = _id_vente({"url": u}) or u or f"{t}|{le}|{p}"
        if k in vus or not p or [x for x in cartes_match.raisons_refus(cib, t or "") if x not in ignorer]:
            continue
        vus.add(k)
        out.append({"titre": t, "prix": p, "le": le, "photo": ph, "url": u, "offre": bool(of), "source": "archives"})
        if len(out) >= max_:
            break
    return out


def archives_joueur(joueur, jours=365, max_=1500):
    """10 nov 2026 (prix suggere sans ventes de LA carte) : les ventes BRUTES d'un joueur dans nos archives (toutes ses
    cartes), les plus recentes d'abord ; le tri (saisons voisines, cartes similaires) se fait ensuite. Aucun appel."""
    if _coupe():
        return []
    nom = [w for w in str(joueur or "").split() if len(w) >= 3]
    if not nom:
        return []
    depuis = (datetime.now() - timedelta(days=jours)).strftime("%Y-%m-%d")
    try:
        import comptes
        import base_ventes
        ch = os.path.join(comptes.DONNEES, "base_ventes.sqlite")
        if not os.path.exists(ch):
            return []
        base_ventes._cx().close()
        c = sqlite3.connect(ch, timeout=3)
        try:
            l = c.execute("SELECT titre, prix, le, photo, url FROM ventes WHERE le >= ? AND titre LIKE ? ORDER BY le DESC LIMIT ?",
                          (depuis, "%" + nom[-1].lower() + "%", max_)).fetchall()
        finally:
            c.close()
    except Exception:
        return []
    return [{"titre": t, "prix": p, "le": le, "photo": ph, "url": u, "source": "archives"} for t, p, le, ph, u in l if p]


# 8 nov 2026 (Mathieu, une analyse de Sports Card Investor : « up 53 % en PSA 9, 41 % en PSA 8 ») : la MEME carte, chaque
# gradation a part (brute, PSA 10, PSA 9...), pour la courbe de variation en % de la fiche
_GRADES = ("gradée", "pas gradée", "autre gradation")


def par_gradation(texte, requete=True, fond=False, jours=365):
    """-> {ok, series: [{cle, nom, n, points: [[date, prix]], derniere: {prix, le}}], carte}. Une recherche SoldComps (cache
    partage), plus nos archives (jusqu'a un an). Les 4 gradations les plus vendues (3 ventes au moins chacune)."""
    if _coupe():
        return {"ok": True, "series": [], "coupe": True}
    import cartes_match
    cib = cartes_match.cible(texte) if requete else cartes_match.cible_titre(texte)
    if cib.get("exclu") or not (cib.get("joueur") or cib.get("mots")):
        return {"ok": False, "erreur": "Carte pas reconnue"}
    c0 = dict(cib, grade=None, veut_grade=False)
    q = cartes_match.requete_ebay(c0) or texte
    r = rechercher(q, fond=fond) if q else {"ventes": []}
    l = [v for v in r.get("ventes") or [] if v.get("prix") and not [x for x in cartes_match.raisons_refus(c0, v.get("titre") or "") if x not in _GRADES]]
    l += archives(c0, jours=jours, max_=600, ignorer=_GRADES)
    groupes, vus = {}, set()
    for v in l:
        k = v.get("url") or f"{v.get('titre')}|{v.get('le')}|{v.get('prix')}"
        if k in vus or not v.get("le") or cartes_match.abimee(v.get("titre") or ""):
            continue
        vus.add(k)
        g = cartes_match.decoder(v.get("titre") or "").get("grade")
        if g and not g.get("note"):
            continue                                     # « PSA » sans note : on ne sait pas laquelle
        cle = f"{g['cie']} {g['note']}" if g else "brute"
        groupes.setdefault(cle, []).append([str(v["le"])[:10], round(float(v["prix"]), 2)])
    nom = lambda k: "Brute" if k == "brute" else k.upper().replace("BECKETT", "BGS")
    def rang(k):
        if k == "brute":
            return (0, 0)
        try:
            return (1, -float(k.split()[-1]))
        except ValueError:
            return (2, 0)
    gs = sorted(((k, v) for k, v in groupes.items() if len(v) >= 3), key=lambda kv: -len(kv[1]))[:4]
    series = []
    for k, pts in sorted(gs, key=lambda kv: rang(kv[0])):
        pts.sort(key=lambda p: p[0])
        series.append({"cle": k, "nom": nom(k), "n": len(pts), "points": pts[-300:], "derniere": {"prix": pts[-1][1], "le": pts[-1][0]}})
    return {"ok": True, "series": series, "carte": cartes_match.resume(c0),
            "erreur": r.get("erreur")}


def memes(texte, requete=True, n=24, fond=False, exclure_titre=None):
    """Les MEMES cartes vendues (eBay via SoldComps + communaute SlabCoach), les plus recentes d'abord.
    texte = ce que l'utilisateur a tape (requete=True) ou le titre d'une annonce (requete=False).
    -> {ventes, mediane, nb, derniere, source, erreur}"""
    if _coupe():
        return {"ventes": [], "mediane": None, "valeur_sure": False, "nb": 0, "derniere": None, "ebay": 0, "communaute": 0,
                "erreur": None, "coupe": True, "points": [], "tendance": None}
    import cartes_match
    import ventes_communaute
    cib = cartes_match.cible(texte) if requete else cartes_match.cible_titre(texte)
    q = cartes_match.requete_ebay(cib) or texte
    futur = raffiner_lancer(q) if q and not fond else None        # 10 nov 2026 : TheCardAPI en meme temps que SoldComps
    r = rechercher(q, fond=fond) if q else {"ventes": [], "erreur": None}
    brut = r.get("ventes") or []
    if r.get("secours") != "thecardapi":
        brut = raffiner(q, brut, futur)
    ebay = [v for v in brut if not cartes_match.raisons_refus(cib, v["titre"])]
    try:
        comm = (ventes_communaute.chercher(texte, requete=requete, n=40) or {}).get("ventes") or []
    except Exception:
        comm = []
    tout = ebay + [{**v, "source": "SlabCoach"} for v in comm]
    # 7 nov 2026 : + nos propres archives (eBay ne montre que 90 jours de ventes). 10 nov 2026 : aussi pour une recherche
    # tapee quand les fournisseurs n'ont rien rendu (panne) : ce qu'on a deja vu vaut mieux que rien
    if not requete or (not ebay and r.get("erreur")):
        vus_u = {_id_vente(v) or str(v.get("url") or "") for v in tout if v.get("url")}
        tout += [v for v in archives(cib) if (_id_vente(v) or str(v.get("url") or "")) not in vus_u]
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


def memes_cache(titre, q=None, n=16, age_max=14 * 86400):
    """8 nov 2026 (Mathieu : « accelerer la vitesse a laquelle on voit les comps ») : les ventes de la MEME carte deja connues,
    SANS aucun appel (le cache des recherches, souvent rempli par le chasseur de deals, et nos archives) : la fiche les
    montre tout de suite, pendant que la vraie recherche se fait. -> {ventes, mediane, nb} (ventes vides si rien)."""
    if _coupe():
        return {"ventes": [], "mediane": None, "nb": 0, "coupe": True}
    import cartes_match
    cib = cartes_match.cible_titre(titre)
    if cib.get("exclu") or not cib.get("joueur"):
        return {"ventes": [], "nb": 0}
    qs = []
    if q:
        qs.append(cartes_match.requete_ebay(cartes_match.cible(q)) or q)
    qs.append(cartes_match.requete_ebay(cib))
    l, vus = [], set()
    for qq in qs:
        qq = " ".join(str(qq or "").split())[:120].lower()
        for v in (_cache_lire(qq, age_max=age_max) if qq else None) or []:
            k = v.get("url") or f"{v.get('titre')}|{v.get('le')}|{v.get('prix')}"
            if v.get("prix") and k not in vus and not cartes_match.raisons_refus(cib, v.get("titre") or ""):
                vus.add(k)
                l.append(v)
    for v in archives(cib, jours=120, max_=60):
        k = v.get("url") or f"{v.get('titre')}|{v.get('le')}|{v.get('prix')}"
        if k not in vus:
            vus.add(k)
            l.append(v)
    l = _sans_aberrants(l)
    l.sort(key=lambda v: str(v.get("le") or ""), reverse=True)
    if not l:
        return {"ventes": [], "nb": 0}
    prix = [v["prix"] for v in l]
    med = cartes_match.mediane_robuste(prix)[0] if len(prix) >= 4 else round(statistics.median(prix), 2)
    return {"ventes": l[:n], "mediane": med, "nb": len(l), "derniere": l[0].get("le"), "provisoire": True,
            "points": [[v.get("le"), v["prix"]] for v in l[:200] if v.get("le")]}


def autres_saisons(titre, fond=False, extra=None):
    """7 nov 2026 (Mathieu : la Ron Francis 2024-25 Clear Cut Outburst Auto /25 sans aucune vente : « mettre les annees a
    cote pour la meme carte, montrer les cartes similaires, mais dire qu'il n'y a pas de comp ») : les ventes de la meme
    carte des saisons voisines (la recherche des ventes ne contient jamais l'annee : le meme appel, deja en cache).
    -> deals.valeur_autre_saison (valeur, « autre_saison », n, ventes avec leur « saison ») ou None."""
    if _coupe():
        return None
    import cartes_match
    import deals
    cib = cartes_match.cible_titre(titre)
    if cib.get("exclu") or not cib.get("joueur") or not cib.get("annee"):
        return None
    q = cartes_match.requete_ebay(cib)
    if not q:
        return None
    r = rechercher(q, fond=fond)
    return deals.valeur_autre_saison({"titre": titre}, [v for v in (r.get("ventes") or []) + list(extra or []) if v.get("prix")], cib)


def similaires(titre, fond=False, extra=None):
    """7 nov 2026 (Mathieu : « les no sales : analyser les cartes similaires et donner un prix approximatif ») : les ventes du
    meme joueur, meme produit / insert (recherche large : sans annee, numerotation ni parallele), puis deals.valeur_approx.
    -> (valeur, « approx », n, ventes) ou None."""
    if _coupe():
        return None
    import cartes_match
    import deals
    cib = cartes_match.cible_titre(titre)
    if cib.get("exclu") or not cib.get("joueur"):
        return None
    l = []
    # 8 nov 2026 : une inscription : aussi la meme carte sans le mot « inscribed » (le plancher de deals.valeur_inscr_plancher)
    sans_i = (cartes_match.requete_ebay(dict(cib, inscr=False)),) if cib.get("inscr") else ()
    for q in dict.fromkeys(x for x in (cartes_match.requete_ebay(cib), cartes_match.requete_ebay(deals.cible_large(cib))) + sans_i if x):
        l += [v for v in rechercher(q, fond=fond).get("ventes") or [] if v.get("prix")]
    l += archives(dict(cib, annee=None, serie=None, veut_serie=False, paralleles=set()), max_=200)
    l += [v for v in extra or [] if v.get("prix")]
    return deals.valeur_approx({"titre": titre}, l, cib)


def autres_joueurs(titre, n=12, fond=False):
    """27 oct 2026 (Mathieu : « Colton Parayko pas de comp, mais on peut montrer des ventes de joueurs de la meme carte ») :
    les ventes de la MEME carte (meme produit, insert, parallele, numerotation, auto, patch) par D'AUTRES joueurs.
    C'est un repere de prix (la valeur depend du joueur), jamais un verdict de deal."""
    if _coupe():
        return {"ventes": [], "nb": 0, "q": None, "erreur": None, "coupe": True}
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


def tendance(ventes, jours=None):
    """26 oct 2026 - % de variation : mediane des ventes des `jours` derniers jours vs les `jours`*2 d'avant.
    None s'il n'y a pas assez de ventes des deux cotes (3 chacune).
    10 nov 2026 : la fenetre gagnante du banc de validation (banc.recette_tendance), 30 jours sinon."""
    from datetime import timedelta
    if jours is None:
        try:
            import banc
            jours = int(banc.recette_tendance().get("jours") or 30)
        except Exception:
            jours = 30
    auj = datetime.now()
    d1, d2 = (auj - timedelta(days=jours)).strftime("%Y-%m-%d"), (auj - timedelta(days=jours * 3)).strftime("%Y-%m-%d")
    recent = [v["prix"] for v in ventes if v.get("prix") and str(v.get("le") or "") >= d1]
    avant = [v["prix"] for v in ventes if v.get("prix") and d2 <= str(v.get("le") or "") < d1]
    if len(recent) < 3 or len(avant) < 3:
        return None
    a, b = statistics.median(avant), statistics.median(recent)
    return {"pct": round(100 * (b - a) / a) if a else None, "recent": round(b, 2), "avant": round(a, 2), "n": len(recent) + len(avant)}


def statut():
    d = {"actif": actif(), "source": source(), "aujourdhui": utilises_aujourdhui(), "plafond": plafond_jour(), "poids_jour": poids_aujourdhui(),
         "poids_semaine": poids_jours()}
    # 10 nov 2026 : toutes les sources de ventes, pour l'admin (base, raffiner, sauver, archives)
    try:
        import thecardapi
        d["thecardapi"] = thecardapi.statut()
    except Exception:
        pass
    try:
        import historique
        d["compsniper"] = {"actif": historique.actif()}
    except Exception:
        pass
    return d
