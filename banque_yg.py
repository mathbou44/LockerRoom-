"""
SLABCOACH - la banque Young Guns (15 nov 2026, Mathieu : « SlabIQ doit choisir quel joueur et quelle carte acheter, a quel
moment, et pourquoi ; la Young Guns est la carte mere d'Upper Deck ; prends toute la data qu'il faut, il reste 8 000
credits ; fais tout »).

Les donnees pour entrainer SlabIQ sur le TIMING (nos 5 mois de ventes ne couvrent ni une saison ni un cycle de sorties) :
1. COLLECTE (admin, une fois, en fond, reprend ou elle s'etait arretee) : 18 mois de ventes des Young Guns de chaque joueur
   (raw et PSA 10), CompSniper, toutes les pages, dans un plafond de credits choisi par l'admin (et jamais au-dela du
   budget du mois LR_HISTORIQUE_MOIS, moins une reserve pour l'app). Les ventes vont aussi dans nos archives (base_ventes).
2. OFFRE (chaque jour) : le nombre d'annonces actives de la Young Guns de chaque joueur (eBay Browse, 1 appel par joueur)
   et le prix demande median : un flot d'annonces annonce souvent une baisse (etude du 15 nov : x1,4 avant une baisse).
3. NOUVELLES : chaque titre de nouvelle d'un joueur est garde (titre + lien + date seulement, jamais le texte), pour
   relier les mouvements de prix a leurs causes sur des mois.
4. EXPORT (admin) : un fichier .json.gz pour l'entrainement (ventes, offre, nouvelles).

Rien ici n'est montre au public : ce sont des donnees de travail de l'admin (comps = admin seulement).
"""
import gzip
import io
import json
import os
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

JOURS = 548                          # 18 mois
PAR_PAGE = 200                       # CompSniper : jusqu'a 200 par page si le forfait le permet (sinon 50)
PAGES_MAX = 40                       # par recherche (une YG tres vendue)
RESERVE_APP = 1000                   # credits du mois laisses a l'app (Radar, fiches)
RAFRAICHIR_PLAFOND = 450             # 15 nov 2026 : la mise a jour de la semaine (~1 900 credits par mois)
RAFRAICHIR_J = 7
PAUSE_S = 1.2
_verrou = threading.Lock()
ETAT = {"en_cours": False, "le": 0.0, "texte": None, "credits": 0, "ventes": 0, "joueurs_faits": 0, "joueurs_total": 0, "erreur": None}


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "banque_yg.sqlite")


def _cx():
    c = sqlite3.connect(_chemin(), timeout=10)
    c.execute("CREATE TABLE IF NOT EXISTS ventes (cle TEXT PRIMARY KEY, q TEXT, joueur TEXT, titre TEXT, prix_usd REAL, devise TEXT,"
              " prix_cad REAL, le TEXT, item_id TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS faits (q TEXT PRIMARY KEY, joueur TEXT, pages INTEGER, ventes INTEGER, fini INTEGER, le REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS offre (jour TEXT, joueur TEXT, annonces INTEGER, prix_median REAL, PRIMARY KEY (jour, joueur))")
    c.execute("CREATE TABLE IF NOT EXISTS nouvelles (lien TEXT PRIMARY KEY, joueur TEXT, titre TEXT, le TEXT, type TEXT, sens INTEGER)")
    # 15 nov 2026 (Mathieu : « j'ai clique il y a 30 min, on est en pleine recherche et ca dit clique encore ; on devrait voir
    # notre progression ») : la collecte en cours est gardee DANS LA BASE (pas en memoire) : un redemarrage du serveur (un
    # deploiement) ne l'efface plus, elle reprend toute seule, et la console montre toujours ou elle en est
    c.execute("CREATE TABLE IF NOT EXISTS rafraichi (q TEXT PRIMARY KEY, le REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS collecte (id INTEGER PRIMARY KEY CHECK (id = 1), statut TEXT, plafond INTEGER, credits INTEGER,"
              " debut REAL, battement REAL, texte TEXT, erreur TEXT, joueurs TEXT)")
    return c


def _run():
    try:
        c = _cx()
        try:
            r = c.execute("SELECT statut, plafond, credits, debut, battement, texte, erreur, joueurs FROM collecte WHERE id=1").fetchone()
        finally:
            c.close()
    except sqlite3.Error:
        r = None
    if not r:
        return {}
    d = dict(zip(("statut", "plafond", "credits", "debut", "battement", "texte", "erreur", "joueurs"), r))
    try:
        d["joueurs"] = json.loads(d["joueurs"] or "[]")
    except ValueError:
        d["joueurs"] = []
    return d


def _run_maj(**kw):
    with _verrou:
        c = _cx()
        try:
            if not c.execute("SELECT 1 FROM collecte WHERE id=1").fetchone():
                c.execute("INSERT INTO collecte (id, statut, credits) VALUES (1, 'aucune', 0)")
            if "joueurs" in kw:
                kw["joueurs"] = json.dumps(kw["joueurs"], ensure_ascii=False)
            if kw:
                c.execute("UPDATE collecte SET " + ", ".join(k + "=?" for k in kw) + " WHERE id=1", list(kw.values()))
            c.commit()
        finally:
            c.close()


# -- 1. la collecte CompSniper ------------------------------------------------------------------------------------------
def joueurs_cibles(n=160):
    """Les joueurs a collecter : le haut de l'indice SlabIQ (actifs d'abord : les Young Guns existent depuis 1990-91)."""
    noms = []
    try:
        import indice_joueurs
        for actifs in (True, None):
            for x in indice_joueurs.top(n * 3, actifs=actifs) or []:
                nm = x.get("nom")
                if nm and nm not in noms:
                    noms.append(nm)
                if len(noms) >= n:
                    return noms
    except Exception as e:
        print("Banque YG (joueurs) : " + repr(e)[:120], flush=True)
    return noms[:n]


def _requetes(nom):
    return [(nom, f"{nom} young guns"), (nom, f"{nom} young guns psa 10")]


def _page(q, page, par_page, debut=None):
    import historique
    fin = datetime.now(timezone.utc).date()
    p = {"keyword": q, "startDate": debut or (fin - timedelta(days=JOURS)).isoformat(), "endDate": fin.isoformat(),
         "sort": "lastSoldDescending", "singleUnitOnly": "true", "limit": str(par_page), "page": str(page)}
    req = urllib.request.Request(historique.URL + "?" + urllib.parse.urlencode(p),
                                 headers={"Authorization": "Bearer " + historique._cle(), "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8"))


def _lire(d, taux):
    out = []
    for it in (d or {}).get("results") or []:
        if it.get("recordType") == "listing_aggregate":
            continue
        p = it.get("soldPrice") or {}
        try:
            v = float(p.get("amount"))
        except (TypeError, ValueError):
            continue
        le = it.get("soldDate") or it.get("lastSoldDate")
        if not v or not le or not it.get("title"):
            continue
        dev = p.get("currency") or "USD"
        out.append({"titre": it["title"], "prix_usd": v if dev == "USD" else None, "devise": dev,
                    "prix_cad": round(v * (taux if dev == "USD" else 1.0), 2), "le": str(le)[:10],
                    "item_id": str(it.get("itemId") or "") or None, "url": it.get("itemUrl"), "photo": it.get("imageUrl")})
    return out


def credits_disponibles(plafond):
    import historique
    u = historique.utilises()["mois"]
    return max(0, min(plafond - (_run().get("credits") or 0), historique.budget_mois() - RESERVE_APP - u))


def _texte(t, **kw):
    ETAT["texte"] = t
    _run_maj(texte=t, battement=time.time(), **kw)


def collecter(plafond=6000, joueurs=None, arret=None):
    """La collecte (a lancer en fond). Reprend : une recherche finie n'est jamais refaite ; une recherche commencee reprend a
    sa page suivante. -> le bilan."""
    import historique
    import vendues
    if not historique.actif():
        return {"ok": False, "erreur": "Clé CompSniper absente (COMPSNIPER_CLE)"}
    taux = vendues._taux_usd_cad() or 1.37
    r0 = _run()
    reprise = r0.get("statut") == "en_cours"
    noms = joueurs or (r0.get("joueurs") if reprise and r0.get("joueurs") else None) or joueurs_cibles()
    ETAT.update(en_cours=True, le=time.time(), ventes=0, joueurs_faits=0, joueurs_total=len(noms), erreur=None, texte="Démarrage")
    if reprise:
        _run_maj(statut="en_cours", plafond=int(plafond), battement=time.time(), texte="Reprise", erreur=None, joueurs=noms)
    else:
        _run_maj(statut="en_cours", plafond=int(plafond), credits=0, debut=time.time(), battement=time.time(), texte="Démarrage", erreur=None, joueurs=noms)
    par_page = PAR_PAGE
    fin_statut = "en_cours"
    try:
        for k, nom in enumerate(noms):
            for joueur, q in _requetes(nom):
                c = _cx()
                try:
                    f = c.execute("SELECT pages, fini FROM faits WHERE q=?", (q,)).fetchone()
                finally:
                    c.close()
                if f and f[1]:
                    continue
                page = (f[0] if f else 0) + 1
                while page <= PAGES_MAX:
                    if arret and arret():
                        fin_statut = "arretee"
                        _texte("Arrêtée")
                        return bilan()
                    if credits_disponibles(plafond) <= 0:
                        fin_statut = "plafond"
                        _texte("Plafond de crédits atteint")
                        return bilan()
                    _texte(f"{nom} · page {page}")
                    essais = 0
                    while True:
                        try:
                            d = _page(q, page, par_page)
                            break
                        except urllib.error.HTTPError as e:
                            if e.code == 400 and par_page > 50:          # le forfait ne permet pas 200 par page
                                par_page = 50
                                continue
                            if e.code == 429 and essais < 3:
                                essais += 1
                                time.sleep(60 * essais)
                                continue
                            ETAT["erreur"] = f"CompSniper HTTP {e.code}"
                            fin_statut = "erreur"
                            _run_maj(erreur=ETAT["erreur"])
                            return bilan()
                        except Exception as e:
                            if essais < 2:
                                essais += 1
                                time.sleep(10)
                                continue
                            ETAT["erreur"] = "CompSniper injoignable (" + type(e).__name__ + ")"
                            fin_statut = "erreur"
                            _run_maj(erreur=ETAT["erreur"])
                            return bilan()
                    historique._compter(False)                # 1 page = 1 credit, compte comme les autres
                    ETAT["credits"] += 1
                    _run_maj(credits=(_run().get("credits") or 0) + 1, battement=time.time())
                    v = _lire(d, taux)
                    with _verrou:
                        c = _cx()
                        try:
                            c.executemany("INSERT OR IGNORE INTO ventes VALUES (?,?,?,?,?,?,?,?,?)",
                                          [((x["item_id"] or "") + "|" + x["le"] + "|" + x["titre"][:80], q, joueur, x["titre"], x["prix_usd"],
                                            x["devise"], x["prix_cad"], x["le"], x["item_id"]) for x in v])
                            fini = len(v) < par_page * 0.9 or page >= PAGES_MAX
                            c.execute("INSERT INTO faits VALUES (?,?,?,?,?,?) ON CONFLICT(q) DO UPDATE SET pages=excluded.pages, "
                                      "ventes=faits.ventes+excluded.ventes, fini=excluded.fini, le=excluded.le",
                                      (q, joueur, page, len(v), 1 if fini else 0, time.time()))
                            c.commit()
                        finally:
                            c.close()
                    ETAT["ventes"] += len(v)
                    try:
                        import base_ventes
                        base_ventes.noter(q, [{"titre": x["titre"], "prix": x["prix_cad"], "le": x["le"], "url": x["url"], "photo": x["photo"],
                                               "item_id": x["item_id"], "source": "historique"} for x in v])
                    except Exception:
                        pass
                    if fini:
                        break
                    page += 1
                    time.sleep(PAUSE_S)
            ETAT["joueurs_faits"] = k + 1
        fin_statut = "terminee"
        _texte("Terminée")
        return bilan()
    finally:
        ETAT["en_cours"] = False
        _run_maj(statut=fin_statut if fin_statut != "en_cours" else "interrompue", battement=time.time())


def _meta(k, v=None):
    with _verrou:
        c = _cx()
        try:
            if v is not None:
                c.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (k, str(v)))
                c.commit()
                return v
            r = c.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
            return r[0] if r else None
        finally:
            c.close()


def rafraichir(plafond=RAFRAICHIR_PLAFOND, arret=None):
    """15 nov 2026 (Mathieu : « on ne doit jamais arreter d'iterer et d'ameliorer SlabIQ ») : chaque semaine, les ventes
    RECENTES de chaque recherche de la banque (depuis sa derniere vente connue, 3 jours de marge, 60 jours au plus), les plus
    anciennes mises a jour d'abord, dans un plafond de credits (et jamais au-dela du budget du mois moins la reserve de l'app).
    Le moment de chaque joueur (moment_yg) reste ainsi a jour. -> {credits, ventes, requetes, fini}."""
    import historique
    import vendues
    if not historique.actif():
        return {"ok": False, "erreur": "Clé CompSniper absente (COMPSNIPER_CLE)"}
    if ETAT["en_cours"]:
        return {"ok": False, "erreur": "Collecte en cours"}
    taux = vendues._taux_usd_cad() or 1.37
    c = _cx()
    try:
        qs = c.execute("SELECT f.q, f.joueur, r.le FROM faits f LEFT JOIN rafraichi r ON r.q = f.q ORDER BY COALESCE(r.le, 0), f.q").fetchall()
        dern = dict(c.execute("SELECT q, MAX(le) FROM ventes GROUP BY q").fetchall())
    finally:
        c.close()
    auj = datetime.now(timezone.utc).date()
    cr = nv = nq = 0
    par_page = 50
    fini = True
    for q, joueur, _le in qs:
        if arret and arret():
            fini = False
            break
        d0 = auj - timedelta(days=60)
        try:
            d0 = max(d0, date.fromisoformat(str(dern.get(q) or "")[:10]) - timedelta(days=3))
        except ValueError:
            pass
        page = 1
        while page <= 10:
            if cr >= plafond or historique.budget_mois() - RESERVE_APP - historique.utilises()["mois"] <= 0:
                fini = False
                break
            try:
                d = _page(q, page, par_page, debut=d0.isoformat())
            except Exception as e:
                print("Banque YG (mise a jour) : " + repr(e)[:120], flush=True)
                fini = False
                break
            historique._compter(False)
            cr += 1
            v = _lire(d, taux)
            with _verrou:
                c = _cx()
                try:
                    c.executemany("INSERT OR IGNORE INTO ventes VALUES (?,?,?,?,?,?,?,?,?)",
                                  [((x["item_id"] or "") + "|" + x["le"] + "|" + x["titre"][:80], q, joueur, x["titre"], x["prix_usd"],
                                    x["devise"], x["prix_cad"], x["le"], x["item_id"]) for x in v])
                    c.commit()
                finally:
                    c.close()
            nv += len(v)
            try:
                import base_ventes
                base_ventes.noter(q, [{"titre": x["titre"], "prix": x["prix_cad"], "le": x["le"], "url": x["url"], "photo": x["photo"],
                                       "item_id": x["item_id"], "source": "historique"} for x in v])
            except Exception:
                pass
            if len(v) < par_page * 0.9:
                break
            page += 1
            time.sleep(PAUSE_S)
        if not fini:
            break
        nq += 1
        with _verrou:
            c = _cx()
            try:
                c.execute("INSERT OR REPLACE INTO rafraichi VALUES (?,?)", (q, time.time()))
                c.commit()
            finally:
                c.close()
    if fini:
        _meta("rafraichi_le", time.time())
    return {"ok": True, "credits": cr, "ventes": nv, "requetes": nq, "fini": fini}


def rafraichir_si_besoin():
    """Une fois par semaine (le reste de la semaine, s'il manquait des credits, reprend a la suivante)."""
    try:
        der = float(_meta("rafraichi_le") or 0)
    except ValueError:
        der = 0.0
    essai = float(_meta("rafraichi_essai") or 0)
    if time.time() - der < RAFRAICHIR_J * 86400 or time.time() - essai < 86400:
        return None
    _meta("rafraichi_essai", time.time())
    return rafraichir()


def reprendre_si_besoin():
    """Au demarrage du serveur : une collecte qui tournait (coupee par un redemarrage) reprend toute seule."""
    r = _run()
    if r.get("statut") in ("en_cours", "interrompue") and not ETAT["en_cours"]:
        import historique
        if historique.actif():
            _run_maj(statut="en_cours")
            print("Banque YG : reprise de la collecte", flush=True)
            return lancer(r.get("plafond") or 6000)
    return None


def lancer(plafond=6000):
    if ETAT["en_cours"]:
        return {"ok": True, "deja": True, **bilan()}
    import contextvars
    ctx = contextvars.copy_context()
    threading.Thread(target=lambda: ctx.run(collecter, int(plafond)), daemon=True, name="banque-yg").start()
    return {"ok": True, "lancee": True}


def bilan():
    try:
        c = _cx()
        try:
            n_v, n_j = c.execute("SELECT COUNT(*), COUNT(DISTINCT joueur) FROM ventes").fetchone()
            n_f = c.execute("SELECT COUNT(*) FROM faits WHERE fini=1").fetchone()[0]
            d0, d1 = c.execute("SELECT MIN(le), MAX(le) FROM ventes").fetchone()
            n_o = c.execute("SELECT COUNT(DISTINCT jour) FROM offre").fetchone()[0]
            n_n = c.execute("SELECT COUNT(*) FROM nouvelles").fetchone()[0]
        finally:
            c.close()
    except sqlite3.Error:
        n_v = n_j = n_f = n_o = n_n = 0
        d0 = d1 = None
    r = _run()
    noms = r.get("joueurs") or []
    faits_j = 0
    if noms:
        try:
            c = _cx()
            try:
                finies = {q for (q,) in c.execute("SELECT q FROM faits WHERE fini=1")}
            finally:
                c.close()
            faits_j = sum(1 for nm in noms if all(q in finies for _, q in _requetes(nm)))
        except sqlite3.Error:
            pass
    vivant = ETAT["en_cours"] or (r.get("statut") == "en_cours" and time.time() - (r.get("battement") or 0) < 180)
    return {"ok": True, "ventes": n_v, "joueurs": n_j, "recherches_finies": n_f, "du": d0, "au": d1, "jours_offre": n_o,
            "nouvelles": n_n, "en_cours": bool(vivant), "statut": r.get("statut") or "aucune", "texte": r.get("texte") or ETAT["texte"],
            "credits_cette_collecte": r.get("credits") or 0, "plafond": r.get("plafond"), "debut": r.get("debut"), "battement": r.get("battement"),
            "joueurs_faits": faits_j, "joueurs_total": len(noms), "erreur": r.get("erreur") or ETAT["erreur"]}


# -- 2. l'offre du jour (eBay Browse) ------------------------------------------------------------------------------------
def _offre_une(nom):
    import appels_ebay
    import ebay_compte
    appels_ebay.exiger("browse", True)
    p = {"q": f"{nom} young guns"[:100], "limit": 50, "category_ids": "261328"}
    req = urllib.request.Request(ebay_compte.url("recherche") + "?" + urllib.parse.urlencode(p),
                                 headers={"Authorization": "Bearer " + ebay_compte.jeton_application(), "Accept": "application/json",
                                          "X-EBAY-C-MARKETPLACE-ID": "EBAY_CA"})
    appels_ebay.compter("browse")
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read())
    prix = []
    for it in d.get("itemSummaries") or []:
        pr = it.get("price") or {}
        try:
            prix.append(float(pr.get("value")) * (ebay_compte._taux_vers_cad(pr.get("currency") or "CAD") or 0))
        except (TypeError, ValueError):
            pass
    prix = sorted(x for x in prix if x > 0)
    return int(d.get("total") or 0), (prix[len(prix) // 2] if prix else None)


def offre_du_jour(max_joueurs=160):
    """Une fois par jour : le nombre d'annonces actives de la YG de chaque joueur collecte. -> nombre de joueurs lus."""
    jour = date.today().isoformat()
    c = _cx()
    try:
        noms = [r[0] for r in c.execute("SELECT DISTINCT joueur FROM faits")]
        deja = {r[0] for r in c.execute("SELECT joueur FROM offre WHERE jour=?", (jour,))}
    finally:
        c.close()
    if not noms:
        noms = joueurs_cibles(max_joueurs)
    n = 0
    for nom in [x for x in noms if x not in deja][:max_joueurs]:
        try:
            tot, med = _offre_une(nom)
        except Exception as e:
            print("Banque YG (offre) : " + repr(e)[:120], flush=True)
            break
        with _verrou:
            c = _cx()
            try:
                c.execute("INSERT OR REPLACE INTO offre VALUES (?,?,?,?)", (jour, nom, tot, med))
                c.commit()
            finally:
                c.close()
        n += 1
        time.sleep(0.5)
    return n


# -- 3. les nouvelles (titre + lien + date) ------------------------------------------------------------------------------
def archiver_nouvelles(nouvelles_j):
    """nouvelles_j : la sortie de indice_joueurs._actu_par_joueur. Garde chaque titre une fois (cle = le lien)."""
    lignes = []
    for nom, na in (nouvelles_j or {}).items():
        types = {e.get("titre"): (e.get("type"), e.get("sens")) for e in na.get("evs") or []}
        for x in na.get("titres") or []:
            if x.get("titre") and x.get("lien"):
                ty, se = types.get(x["titre"], (None, None))
                lignes.append((x["lien"], nom, x["titre"][:200], str(x.get("date") or "")[:10], ty, se))
        for e in na.get("evs") or []:
            if e.get("titre") and e.get("lien"):
                lignes.append((e["lien"], nom, e["titre"][:200], str(e.get("date") or "")[:10], e.get("type"), e.get("sens")))
    if not lignes:
        return 0
    with _verrou:
        c = _cx()
        try:
            c.executemany("INSERT OR IGNORE INTO nouvelles VALUES (?,?,?,?,?,?)", lignes)
            c.commit()
        finally:
            c.close()
    return len(lignes)


# -- 4. l'export ------------------------------------------------------------------------------------------------------
def exporter():
    """-> (octets .json.gz, nom de fichier)"""
    c = _cx()
    try:
        d = {"genere": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "ventes": [dict(zip(("q", "joueur", "titre", "prix_usd", "devise", "prix_cad", "le", "item_id"), r))
                        for r in c.execute("SELECT q, joueur, titre, prix_usd, devise, prix_cad, le, item_id FROM ventes")],
             "offre": [dict(zip(("jour", "joueur", "annonces", "prix_median"), r)) for r in c.execute("SELECT jour, joueur, annonces, prix_median FROM offre")],
             "nouvelles": [dict(zip(("lien", "joueur", "titre", "le", "type", "sens"), r)) for r in c.execute("SELECT lien, joueur, titre, le, type, sens FROM nouvelles")]}
    finally:
        c.close()
    b = io.BytesIO()
    with gzip.GzipFile(fileobj=b, mode="wb") as g:
        g.write(json.dumps(d, ensure_ascii=False).encode("utf-8"))
    return b.getvalue(), "banque_yg_" + date.today().isoformat() + ".json.gz"
