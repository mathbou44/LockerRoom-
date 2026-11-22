"""
SLABCOACH - le mega test : 3 ans de ventes de la MEME carte (22 nov 2026).

Mathieu : « fais le mega test CompSniper ». Ce qui est prouve (bulletin, 5 dates) : une carte du Radar Pro se revend pres de son
prix 60 a 71 % du temps (hasard 6 a 12 %). Ce qui ne l'est pas : que l'ACHETEUR fait de l'argent. Nos archives ne couvrent que
~5 mois : trop court pour juger un achat a 3, 6 ou 12 mois sur plusieurs saisons. CompSniper (/v1/research/sold) donne jusqu'a
3 ans (1 095 jours) ; la cle est dans Render seulement, donc la collecte tourne ICI, sur le serveur.

1. LE PLAN : les cartes exactes de nos archives (la recherche « q » de chaque carte : cartes_match.requete_ebay, la meme que
   SoldComps et le chasseur), les plus vendues d'abord, a 30 $ et plus (le prix minimum du Radar), au moins 3 ventes en un an
   (une carte jamais revendue ne peut rien prouver). Les recherches larges (« sortes ») sont ecartees : un test se fait sur la
   carte exacte (lecon du 21 nov).
2. LA COLLECTE : chaque recherche, page par page (50 ventes, les plus recentes d'abord), jusqu'a 1 095 jours en arriere. On ne
   repaie pas ce qu'on a deja : la fenetre s'arrete a la plus vieille vente deja connue de cette recherche (2 jours de marge).
   Les ventes vont dans nos archives (base_ventes) : l'export de l'admin et tous les tests les voient.
3. LES CREDITS : jamais plus que le budget du mois (LR_HISTORIQUE_MOIS, qu'on ne touche pas : c'est Mathieu), moins une reserve
   pour l'app (LR_MEGA_RESERVE, 1 500 par defaut), ni plus que le plafond de la collecte. Un mois a sec : la collecte attend le
   mois suivant et reprend seule (boucle du serveur, chaque heure). Un redemarrage (deploiement) : elle reprend ou elle etait.
4. LA SONDE (le tout premier tour) : 5 credits, les 5 cartes les plus vendues, leurs ventes d'il y a 2 a 3 ans seulement. Rien de
   plus vieux que 2 ans : on ne met pas le forfait (statut « essai_rate », l'admin decide). Sinon : le vrai test part tout seul.
5. GARDE-FOUS : une page qui ne rend que des ventes deja vues (l'API ignore la page) termine la recherche ; au plus
   PAGES_MAX pages par recherche (une carte tres vendue ne mange pas le forfait) ; 1 page = 1 credit, compte avec les autres.

Rien ici n'est montre au public (comps = admin seulement). Les resultats du test : outils/mega_test.py, sur l'export.
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
from datetime import date, datetime, timedelta, timezone

import reseau

JOURS = 1095                         # 3 ans : le maximum de CompSniper
PAR_PAGE = 50
PAGES_MAX = 80                       # 4 000 ventes au plus par recherche (22 nov : 30 -> 80, Mathieu a pris 50 000 credits :
                                     # les Young Guns tres vendues vont enfin jusqu'a 3 ans)
PLAFOND_DEFAUT = 8000                # credits au plus pour toute la collecte (le forfait : 10 000 par mois)
PLAN_MAX = 3000                      # recherches au plus dans le plan
VENTES_MIN = 3                       # ventes en un an dans nos archives, au moins
DEJA_MIN = 10                        # une recherche avec 10 ventes connues : on ne repaie pas sa periode connue
PAUSE_S = 0.3                        # 22 nov : 1,2 -> 0,3 s entre les pages (un 429 attend et reessaie seul)
SONDE_N = 5                          # avant le vrai test : 5 credits, 5 cartes, leurs ventes d'il y a 2 a 3 ans seulement
SONDE_JOURS = 730
_verrou = threading.Lock()
ETAT = {"en_cours": False}


def reserve_app():
    try:
        return max(0, int(os.environ.get("LR_MEGA_RESERVE") or 1500))
    except ValueError:
        return 1500


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "mega_test.sqlite")


def _cx():
    c = sqlite3.connect(_chemin(), timeout=10)
    c.execute("CREATE TABLE IF NOT EXISTS plan (q TEXT PRIMARY KEY, ordre INTEGER, n_an INTEGER, prix REAL, plus_vieille TEXT, "
              "debut TEXT, fin TEXT, pages INTEGER DEFAULT 0, ventes INTEGER DEFAULT 0, fini INTEGER DEFAULT 0, raison TEXT, le REAL, recu_min TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS collecte (id INTEGER PRIMARY KEY CHECK (id = 1), statut TEXT, plafond INTEGER, credits INTEGER,"
              " debut REAL, battement REAL, texte TEXT, erreur TEXT)")
    return c


def _run():
    try:
        c = _cx()
        try:
            r = c.execute("SELECT statut, plafond, credits, debut, battement, texte, erreur FROM collecte WHERE id=1").fetchone()
        finally:
            c.close()
    except sqlite3.Error:
        r = None
    return dict(zip(("statut", "plafond", "credits", "debut", "battement", "texte", "erreur"), r)) if r else {}


def _run_maj(**kw):
    with _verrou:
        c = _cx()
        try:
            if not c.execute("SELECT 1 FROM collecte WHERE id=1").fetchone():
                c.execute("INSERT INTO collecte (id, statut, credits) VALUES (1, 'aucune', 0)")
            if kw:
                c.execute("UPDATE collecte SET " + ", ".join(k + "=?" for k in kw) + " WHERE id=1", list(kw.values()))
            c.commit()
        finally:
            c.close()


# -- 1. le plan ----------------------------------------------------------------------------------------------------------
def _larges():
    """Les recherches qui melangent des cartes differentes : jamais dans le mega test."""
    import base_ventes
    out = set(base_ventes.SORTES_Q)
    try:
        c = base_ventes._cx()
        try:
            out |= {q for (q,) in c.execute("SELECT q FROM plan WHERE carte='sorte' OR cible LIKE 'sorte %'")}
        finally:
            c.close()
    except sqlite3.Error:
        pass
    return out


def _sans_joueur(q):
    """22 nov 2026 (« psa 10 rookie » avait pris 28 pages) : une recherche sans nom de joueur melange des cartes differentes."""
    try:
        import cartes_match
        j = cartes_match.joueur_du_titre(q or "")
    except Exception:
        return False
    return len(str(j or "").split()) < 2


def construire_plan(n_max=PLAN_MAX, aujourd=None):
    """Les recherches de nos archives (hockey), les plus vendues d'abord. -> nombre de recherches dans le plan."""
    import base_ventes
    aujourd = aujourd or datetime.now(timezone.utc).date()
    d_an = (aujourd - timedelta(days=365)).isoformat()
    try:
        prix_min = float(__import__("lockerroom").Api.RADAR_PRIX_MIN)
    except Exception:
        prix_min = 30.0
    larges = _larges()
    c = base_ventes._cx()
    try:
        rows = c.execute("SELECT q, COUNT(*), MIN(le) FROM ventes WHERE le >= ? AND prix > 0 GROUP BY q HAVING COUNT(*) >= ?",
                         (d_an, VENTES_MIN)).fetchall()
        vieilles = dict(c.execute("SELECT q, MIN(le) FROM ventes GROUP BY q").fetchall())
        prix = {}
        for q, n, _d in rows:
            if q in larges or not q or len(q.split()) < 2 or _sans_joueur(q):
                continue
            ps = [p for (p,) in c.execute("SELECT prix FROM ventes WHERE q=? AND le >= ? AND prix > 0", (q, d_an))]
            if ps:
                prix[q] = (n, statistics.median(ps))
    finally:
        c.close()
    choix = sorted(((q, n, p) for q, (n, p) in prix.items() if p >= prix_min), key=lambda x: (-x[1], -x[2], x[0]))[:n_max]
    with _verrou:
        c = _cx()
        try:
            for k, (q, n, p) in enumerate(choix):
                c.execute("INSERT INTO plan (q, ordre, n_an, prix, plus_vieille) VALUES (?,?,?,?,?) ON CONFLICT(q) DO UPDATE SET "
                          "ordre=excluded.ordre, n_an=excluded.n_an, prix=excluded.prix", (q, k, n, round(p, 2), vieilles.get(q)))
            c.commit()
        finally:
            c.close()
    return len(choix)


def fenetre(plus_vieille, n_connues, aujourd=None):
    """(debut, fin) a demander : 3 ans en arriere, jusqu'a aujourd'hui, ou jusqu'a la plus vieille vente deja connue (+ 2 jours)
    quand on en connait deja assez. None : rien a demander."""
    aujourd = aujourd or datetime.now(timezone.utc).date()
    debut = aujourd - timedelta(days=JOURS)
    fin = aujourd
    if plus_vieille and n_connues >= DEJA_MIN:
        try:
            fin = min(aujourd, date.fromisoformat(str(plus_vieille)[:10]) + timedelta(days=2))
        except ValueError:
            pass
    if fin <= debut:
        return None
    return debut.isoformat(), fin.isoformat()


# -- 2. la collecte ------------------------------------------------------------------------------------------------------
def _page(q, page, debut, fin):
    import historique
    p = {"keyword": q, "startDate": debut, "endDate": fin, "sort": "lastSoldDescending", "singleUnitOnly": "true",
         "limit": str(PAR_PAGE), "page": str(page)}
    req = urllib.request.Request(historique.URL + "?" + urllib.parse.urlencode(p),
                                 headers={"Authorization": "Bearer " + historique._cle(), "Accept": "application/json"})
    with reseau.ouvrir(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8"))


def credits_disponibles(plafond=None):
    """Ce que la collecte peut encore depenser : le plafond de la collecte ET le budget du mois moins la reserve de l'app."""
    import historique
    r = _run()
    plafond = plafond if plafond is not None else (r.get("plafond") or PLAFOND_DEFAUT)
    return max(0, min(plafond - (r.get("credits") or 0), historique.budget_mois() - reserve_app() - historique.utilises()["mois"]))


def _texte(t, **kw):
    _run_maj(texte=t, battement=time.time(), **kw)


def _a_faire():
    c = _cx()
    try:
        return c.execute("SELECT q, plus_vieille, pages, debut, fin FROM plan WHERE fini=0 ORDER BY ordre").fetchall()
    finally:
        c.close()


def _connues(q):
    import base_ventes
    try:
        c = base_ventes._cx()
        try:
            return c.execute("SELECT COUNT(*) FROM ventes WHERE q=?", (q,)).fetchone()[0]
        finally:
            c.close()
    except sqlite3.Error:
        return 0


def _plan_maj(q, **kw):
    with _verrou:
        c = _cx()
        try:
            c.execute("UPDATE plan SET " + ", ".join(k + "=?" for k in kw) + " WHERE q=?", list(kw.values()) + [q])
            c.commit()
        finally:
            c.close()


def collecter(plafond=None, arret=None, pause=None):
    """La collecte (en fond). Reprend : une recherche finie n'est jamais refaite ; une recherche commencee reprend a sa page
    suivante, avec la meme fenetre. -> le bilan (lu apres que le statut final est ecrit)."""
    r = _collecter(plafond, arret, PAUSE_S if pause is None else pause)
    return bilan() if r is None else r


def _collecter(plafond, arret, pause):
    import historique
    import vendues
    import base_ventes
    if not historique.actif():
        return {"ok": False, "erreur": "Clé CompSniper absente (COMPSNIPER_CLE)"}
    if ETAT["en_cours"]:
        return {"ok": True, "deja": True, **bilan()}
    ETAT["en_cours"] = True
    r0 = _run()
    plafond = int(plafond or r0.get("plafond") or PLAFOND_DEFAUT)
    reprise = r0.get("statut") not in (None, "aucune", "terminee")
    if reprise:
        _run_maj(statut="en_cours", plafond=plafond, battement=time.time(), texte="Reprise", erreur=None)
    else:
        _run_maj(statut="en_cours", plafond=plafond, credits=0, debut=time.time(), battement=time.time(), texte="Le plan", erreur=None)
    fin_statut = "interrompue"
    try:
        c = _cx()
        try:
            vide = not c.execute("SELECT COUNT(*) FROM plan").fetchone()[0]
        finally:
            c.close()
        if vide:
            construire_plan()
        with _verrou:                                  # 22 nov : PAGES_MAX monte -> les cartes coupees au plafond de pages reprennent
            c = _cx()
            try:
                c.execute("UPDATE plan SET fini=0, raison=NULL WHERE raison='pages max' AND pages < ?", (PAGES_MAX,))
                for (q_,) in c.execute("SELECT q FROM plan WHERE fini=0").fetchall():
                    if _sans_joueur(q_):
                        c.execute("UPDATE plan SET fini=1, raison='sans joueur' WHERE q=?", (q_,))
                c.commit()
            finally:
                c.close()
        taux = vendues._taux_usd_cad() or 1.37
        for q, plus_vieille, pages, debut, fin in _a_faire():
            if not debut:
                f = fenetre(plus_vieille, _connues(q))
                if not f:
                    _plan_maj(q, fini=1, raison="deja couverte", le=time.time())
                    continue
                debut, fin = f
                _plan_maj(q, debut=debut, fin=fin)
            page = (pages or 0) + 1
            vus = set()
            while True:
                if arret and arret():
                    fin_statut = "arretee"
                    _texte("Arrêtée")
                    return None
                dispo = credits_disponibles(plafond)
                if dispo <= 0:
                    r = _run()
                    fin_statut = "plafond" if (r.get("credits") or 0) >= plafond else "attente_mois"
                    _texte("Plafond de la collecte atteint" if fin_statut == "plafond" else "Budget du mois atteint : reprend le mois prochain")
                    return None
                _texte(f"{q} · page {page}")
                essais = 0
                while True:
                    try:
                        d = _page(q, page, debut, fin)
                        break
                    except urllib.error.HTTPError as e:
                        # 22 nov 2026 (« CompSniper HTTP 503 », arrete 35 min) : une panne passagere (429, 5xx) attend et reessaie :
                        # 30 s, 1, 2, 4 puis 5 min
                        if (e.code == 429 or e.code >= 500) and essais < 5:
                            essais += 1
                            _texte(f"{q} · page {page} · CompSniper HTTP {e.code}, nouvel essai {essais}/5")
                            time.sleep(min(300, 30 * 2 ** (essais - 1)))
                            continue
                        fin_statut = "erreur"
                        _run_maj(erreur=f"CompSniper HTTP {e.code}")
                        return None
                    except Exception as e:
                        if essais < 5:
                            essais += 1
                            time.sleep(min(300, 30 * 2 ** (essais - 1)))
                            continue
                        fin_statut = "erreur"
                        _run_maj(erreur="CompSniper injoignable (" + type(e).__name__ + ")")
                        return None
                historique._compter(False)                    # 1 page = 1 credit, compte comme les autres
                _run_maj(credits=(_run().get("credits") or 0) + 1, battement=time.time())
                v = historique.lire_reponse(d, taux)
                ids = {x.get("item_id") or (x["titre"] + x["le"]) for x in v}
                neuves = ids - vus
                vus |= ids
                if v:
                    try:
                        base_ventes.noter(q, v, sport="hockey")
                    except Exception as e:
                        print("Mega test (archives) : " + repr(e)[:120], flush=True)
                plus_vieux = min((x["le"] for x in v), default=None)
                raison = None
                if len((d or {}).get("results") or []) < PAR_PAGE * 0.9:
                    raison = "toutes les ventes"
                elif not neuves:
                    raison = "page repetee"
                elif plus_vieux and plus_vieux < debut:
                    raison = "3 ans atteints"
                elif page >= PAGES_MAX:
                    raison = "pages max"
                c = _cx()
                try:
                    c.execute("UPDATE plan SET pages=?, ventes=ventes+?, fini=?, raison=?, le=?, recu_min=MIN(COALESCE(recu_min, ?), ?) WHERE q=?",
                              (page, len(neuves), 1 if raison else 0, raison, time.time(), plus_vieux or "9999", plus_vieux or "9999", q))
                    c.commit()
                finally:
                    c.close()
                if raison:
                    break
                page += 1
                time.sleep(pause)
            time.sleep(pause)
        fin_statut = "terminee"
        _texte("Terminée")
        return None
    finally:
        ETAT["en_cours"] = False
        _run_maj(statut=fin_statut, battement=time.time())


def _tour(plafond=None):
    """Un tour en fond : la sonde d'abord (le tout premier tour seulement), puis la collecte."""
    r = _run()
    if (r.get("statut") or "aucune") == "aucune":
        v = sonder()
        if not v["ok"]:
            if v["credits"]:                                 # CompSniper a repondu, sans ventes de plus de 2 ans : on s'arrete
                _run_maj(statut="essai_rate", texte=v["texte"], credits=v["credits"], battement=time.time())
            else:                                            # pas de reponse ou pas de credits : on reessaiera
                _run_maj(texte=v["texte"], battement=time.time())
            return None
        _run_maj(statut="interrompue", plafond=int(plafond or r.get("plafond") or PLAFOND_DEFAUT), texte=v["texte"], credits=v["credits"],
                 debut=time.time())
    return collecter(plafond)


def lancer(plafond=None):
    if ETAT["en_cours"]:
        return {"ok": True, "deja": True, **bilan()}
    import historique
    if not historique.actif():
        return {"ok": False, "erreur": "Clé CompSniper absente (COMPSNIPER_CLE)"}
    import contextvars
    ctx = contextvars.copy_context()
    threading.Thread(target=lambda: ctx.run(_tour, plafond), daemon=True, name="mega-test").start()
    return {"ok": True, "lancee": True}


def continuer_si_besoin():
    """Boucle du serveur (chaque heure) et demarrage : le test part tout seul (Mathieu l'a demande le 22 nov), par la sonde ;
    une collecte coupee (redemarrage) ou a sec (budget du mois) reprend des qu'il y a des credits. LR_MEGA_AUTO=0 : jamais seul."""
    if ETAT["en_cours"] or os.environ.get("LR_MEGA_AUTO") == "0":
        return None
    import historique
    if not historique.actif():
        return None
    r = _run()
    st = r.get("statut") or "aucune"
    if st in ("terminee", "plafond", "arretee", "essai_rate"):
        return None
    if st == "erreur" and time.time() - (r.get("battement") or 0) < 15 * 60:
        return None                                          # une erreur : on reessaie au prochain tour (chaque heure), 15 min au moins apres
    if credits_disponibles() <= 0:
        if st == "aucune":
            _run_maj(texte="En attente de crédits (budget du mois LR_HISTORIQUE_MOIS moins la réserve de l'app)", battement=time.time())
        return None
    print("Mega test : tour (" + st + ")", flush=True)
    return lancer()


def sonder(n=SONDE_N):
    """Avant de mettre le forfait : CompSniper donne-t-il vraiment les ventes d'il y a 2 a 3 ans ? Une page par carte (les plus
    vendues du plan), fenetre de -1 095 a -730 jours. Leurs ventes vont dans nos archives. -> {ok, texte, credits}."""
    import historique
    import vendues
    import base_ventes
    c = _cx()
    try:
        if not c.execute("SELECT COUNT(*) FROM plan").fetchone()[0]:
            c.close()
            construire_plan()
            c = _cx()
        qs = [q for (q,) in c.execute("SELECT q FROM plan ORDER BY ordre LIMIT ?", (n,))]
    finally:
        c.close()
    if not qs:
        return {"ok": False, "texte": "Essai : aucune carte dans le plan", "credits": 0}
    auj = datetime.now(timezone.utc).date()
    d0, d1 = (auj - timedelta(days=JOURS)).isoformat(), (auj - timedelta(days=SONDE_JOURS)).isoformat()
    taux = vendues._taux_usd_cad() or 1.37
    cr, vieux, nv = 0, None, 0
    for q in qs:
        if credits_disponibles(PLAFOND_DEFAUT) <= 0:
            break
        try:
            d = _page(q, 1, d0, d1)
        except Exception as e:
            print("Mega test (essai) : " + repr(e)[:120], flush=True)
            continue
        historique._compter(False)
        cr += 1
        v = historique.lire_reponse(d, taux)
        if v:
            nv += len(v)
            try:
                base_ventes.noter(q, v, sport="hockey")
            except Exception:
                pass
            m = min(x["le"] for x in v)
            vieux = m if vieux is None or m < vieux else vieux
    if not cr:
        return {"ok": False, "texte": "Essai : CompSniper n'a pas répondu (ou pas de crédits ce mois-ci)", "credits": 0}
    if not vieux or vieux > d1:
        return {"ok": False, "texte": f"Essai raté : aucune vente de plus de 2 ans pour {len(qs)} cartes très vendues ({cr} crédits)", "credits": cr}
    return {"ok": True, "texte": f"Essai réussi : {nv} ventes d'il y a 2 à 3 ans ({cr} crédits), jusqu'au {vieux}", "credits": cr}


def bilan():
    import historique
    try:
        c = _cx()
        try:
            n, n_f, pg, nv = c.execute("SELECT COUNT(*), COALESCE(SUM(fini),0), COALESCE(SUM(pages),0), COALESCE(SUM(ventes),0) FROM plan").fetchone()
            raisons = dict(c.execute("SELECT raison, COUNT(*) FROM plan WHERE fini=1 GROUP BY raison").fetchall())
        finally:
            c.close()
    except sqlite3.Error:
        n = n_f = pg = nv = 0
        raisons = {}
    r = _run()
    vivant = ETAT["en_cours"] or (r.get("statut") == "en_cours" and time.time() - (r.get("battement") or 0) < 180)
    return {"ok": True, "en_cours": bool(vivant), "statut": r.get("statut") or "aucune", "texte": r.get("texte"),
            "cartes": n, "cartes_finies": int(n_f), "pages": int(pg), "ventes": int(nv), "raisons": raisons,
            "credits": r.get("credits") or 0, "plafond": r.get("plafond") or PLAFOND_DEFAUT, "debut": r.get("debut"),
            "battement": r.get("battement"), "erreur": r.get("erreur"), "reserve_app": reserve_app(), "jours": JOURS,
            "dispo": credits_disponibles(), "compsniper": historique.etat()}
