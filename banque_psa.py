"""
SLABCOACH - les donnees PSA : quelles cartes valent la peine d'etre gradees (26 nov 2026).

Mathieu : « savoir les cartes qui valent le plus la peine d'etre gradees [...] on partirait de toutes nos ventes des 3 derniers
mois, ou plus [...] de toutes les paralleles de cartes qui ont ete vendues en PSA 10. Puis on regarde la version raw, combien
elle a ete vendue en moyenne, versus la moyenne des vendus PSA 10 pour le meme genre de time frame. » Puis : « Good, on y va pour
le mega test pour donnees PSA, juste me dire quand le partir. »

Nos archives viennent des recherches de l'app (le Radar, les fiches, la banque Young Guns) : presque seulement des Young Guns,
peu de PSA 9, peu de paralleles. Cette collecte va chercher ce qui manque, sur le serveur (la cle CompSniper est dans Render) :

1. PHASE 1 - CE QUI SE VEND GRADE : pour chaque joueur du haut de l'indice SlabIQ (actifs d'abord), « <joueur> psa 10 » et
   « <joueur> psa 9 », 120 jours, page par page (50 ventes, les plus recentes d'abord), PAGES_MAX pages au plus.
2. PHASE 2 - LA VERSION RAW : chaque carte exacte vue au moins N10_MIN fois en PSA 10 (lue TITRE PAR TITRE avec le meme
   decodeur que les comps : cartes_match.cible_titre) : sa recherche sans la note (cartes_match.requete_ebay, la meme que l'app),
   PAGES_MAX_RAW pages au plus. Une recherche deja dans nos archives et fraiche n'est pas repayee.
3. UNE BASE A PART (banque_psa.sqlite) : « connor bedard psa 10 » melange toutes ses cartes. Rangee dans nos archives
   (base_ventes), une recherche pareille fausserait les tendances et les tests publies. Ici, une vente n'est JAMAIS comptee par
   sa recherche : seulement par son titre (la carte exacte, la note). Rien ne touche aux archives.
4. LES CREDITS : jamais plus que le plafond choisi par l'admin, ni que le budget du mois (LR_HISTORIQUE_MOIS, qu'on ne touche
   pas) moins la reserve de l'app (la meme que le mega test : LR_MEGA_RESERVE, 1 500 par defaut). 1 page = 1 credit, compte
   avec les autres.
5. ELLE NE PART PAS SEULE : c'est l'admin qui la lance. Une fois lancee, elle reprend seule ou elle etait (redemarrage, mois a
   sec) ; une recherche finie n'est jamais refaite.

Rien ici n'est montre au public (comps = admin seulement).
"""
import os
import sqlite3
import threading
import time
import unicodedata
import urllib.error
import uuid
from datetime import datetime, timedelta, timezone

JOURS = 365                          # 26 nov, 18 h 50 (Mathieu : « besoin de plus de data [...] au moins entre 500 et 1 000 » ; son choix :
                                     # « 12 mois + 500 joueurs ») : 12 mois (avant : 120 jours)
VERSION_PLAN = 2                     # 2 = 12 mois, 500 joueurs : une collecte finie avec l'ancien plan est ETENDUE quand l'admin la relance
AUTRES_MIN = 100                     # une recherche « <joueur> psa 10 » de 100 ventes et plus dont moins de 30 % nomment le joueur
AUTRES_PART = 0.30                   # (« cam york » -> Cam Schlittler, Yankees de New York) n'est pas etendue ;
AUTRES_PAGES = 2                     # et une recherche s'arrete apres 2 pages de suite ou moins de 15 % des ventes le nomment
AUTRES_PAGE_PART = 0.15
PAR_PAGE = 50
PAGES_MAX = 30                       # « <joueur> psa 10 » : 1 500 ventes au plus (les plus recentes)
PAGES_MAX_RAW = 8                    # la version raw d'une carte : 400 ventes au plus
PLAFOND_DEFAUT = 8000                # credits au plus pour toute la collecte
JOUEURS_N = 500
NOTES = ("psa 10", "psa 9")
N10_MIN = 4                          # ventes PSA 10 de la carte (120 jours) pour aller chercher sa version raw
RAW_MAX = 1500                       # recherches raw au plus
ARCHIVE_MIN = 20                     # la recherche raw est deja dans nos archives : 20 ventes dans la fenetre...
ARCHIVE_FRAIS_J = 10                 # ... dont une de 10 jours ou moins
REFUS_SUITE_MAX = 8
PAUSE_S = 0.3
VIVANTE_S = 180                      # un battement de moins de 3 minutes : une collecte tourne (dans ce processus ou un autre)
ATTENTES_S = (1, 2, 4, 8, 15, 30, 30, 30)        # une base occupee (« database is locked ») : on reessaie pendant 2 minutes
_verrou = threading.Lock()
ETAT = {"en_cours": False}
_MIGRE = {"fait": False}


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "banque_psa.sqlite")


# 26 nov 2026, 14 h 58 (journal, 22 s apres la reprise : « Exception in thread donnees-psa [...] sqlite3.OperationalError: database
# is locked ») : la collecte MOURAIT quand une base etait occupee plus de quelques secondes (ce jour-la : le calcul de la liste
# « A grader » lisait banque_psa.sqlite pendant des minutes ; historique.sqlite n'attend que 5 s), et son statut restait
# « en_cours » : c'est l'explication de la « reprise » de 13 h 28. Maintenant chaque lecture et chaque ecriture de la collecte
# REESSAIE (2 minutes au plus) ; une erreur imprevue ne tue plus le fil sans le dire : statut « erreur », reprise a l'heure.
def _tenace(f):
    def g(*a, **k):
        for attente in ATTENTES_S + (None,):
            try:
                return f(*a, **k)
            except sqlite3.OperationalError as e:
                if attente is None or not any(m in str(e).lower() for m in ("locked", "busy")):
                    raise
                time.sleep(attente if PAUSE_S else 0)
    g.__name__ = f.__name__
    g.__doc__ = f.__doc__
    return g


def _cx():
    c = sqlite3.connect(_chemin(), timeout=30)
    c.execute("CREATE TABLE IF NOT EXISTS plan (q TEXT PRIMARY KEY, phase INTEGER, joueur TEXT, ordre INTEGER, n10 INTEGER, debut TEXT, fin TEXT,"
              " pages INTEGER DEFAULT 0, ventes INTEGER DEFAULT 0, fini INTEGER DEFAULT 0, raison TEXT, le REAL, recu_min TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS ventes (cle TEXT PRIMARY KEY, q TEXT, joueur TEXT, titre TEXT, prix REAL, le TEXT)")
    c.execute("CREATE INDEX IF NOT EXISTS ventes_joueur ON ventes (joueur)")
    c.execute("CREATE TABLE IF NOT EXISTS collecte (id INTEGER PRIMARY KEY CHECK (id = 1), statut TEXT, plafond INTEGER, credits INTEGER,"
              " debut REAL, battement REAL, texte TEXT, erreur TEXT, raw_planifie INTEGER DEFAULT 0)")
    if not _MIGRE["fait"]:                                    # la base du 26 nov, 13 h 27, n'a pas la colonne du jeton
        for col in ("jeton TEXT", "version INTEGER"):          # version : le plan de la collecte (voir VERSION_PLAN)
            try:
                c.execute("ALTER TABLE collecte ADD COLUMN " + col)
            except sqlite3.OperationalError:
                pass
        _MIGRE["fait"] = True
    return c


@_tenace
def _run_lire():
    c = _cx()
    try:
        return c.execute("SELECT statut, plafond, credits, debut, battement, texte, erreur, raw_planifie, jeton, version FROM collecte WHERE id=1").fetchone()
    finally:
        c.close()


def _run():
    try:
        r = _run_lire()
    except sqlite3.Error:
        r = None
    return dict(zip(("statut", "plafond", "credits", "debut", "battement", "texte", "erreur", "raw_planifie", "jeton", "version"), r)) if r else {}


# 26 nov 2026, 13 h 28 (journal du serveur, 45 s apres le lancement par Mathieu : « Donnees PSA : reprise (en_cours) ») : la boucle
# de l'heure a relance une collecte qui venait de partir : le drapeau en memoire (ETAT) ne l'a pas arretee. Deux collectes en meme
# temps paieraient chaque page deux fois. Deux garde-fous, dans la BASE (vrais meme entre deux processus) :
#  1. le BATTEMENT : une collecte « en_cours » dont le battement a moins de VIVANTE_S secondes tourne : rien ne la relance ;
#  2. le JETON : chaque collecte ecrit le sien en partant et le relit avant chaque page ; s'il a change, une autre a pris le
#     relais : elle s'arrete sans rien toucher. Il n'en reste jamais qu'une.
def vivante(r=None):
    r = _run() if r is None else r
    return r.get("statut") == "en_cours" and time.time() - (r.get("battement") or 0) < VIVANTE_S


@_tenace
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


def _simple(nom):
    """« Juraj Slafkovský » -> « juraj slafkovsky » : les titres d'eBay n'ont presque jamais d'accents."""
    s = unicodedata.normalize("NFKD", str(nom or "")).encode("ascii", "ignore").decode("ascii")
    return " ".join(s.lower().replace("'", " ").replace(".", " ").split())


def _mots_joueur(nom):
    """Les mots du joueur dans une recherche, ecrits comme l'app les ecrit (cartes_match) : « Tim Stützle » -> « tim stutzle »."""
    try:
        import cartes_match
        m = cartes_match.cible(nom)["mots"]
        if len(m) >= 2:
            return " ".join(m)
        return cartes_match.joueur_du_titre(nom) or _simple(nom)
    except Exception:
        return _simple(nom)


def _aujourdhui():
    return datetime.now(timezone.utc).date()


def fenetre(aujourd=None):
    a = aujourd or _aujourdhui()
    return (a - timedelta(days=JOURS)).isoformat(), a.isoformat()


# -- 1. le plan ----------------------------------------------------------------------------------------------------------
def joueurs_cibles(n=JOUEURS_N):
    """Le haut de l'indice SlabIQ, actifs d'abord (ce sont leurs cartes recentes qu'on envoie chez PSA), puis les autres."""
    noms = []
    try:
        import indice_joueurs
        for actifs in (True, None):
            for x in indice_joueurs.top(n * 3, actifs=actifs) or []:
                nm = x.get("nom")
                if nm and len(_mots_joueur(nm).split()) >= 2 and nm not in noms:
                    noms.append(nm)
                if len(noms) >= n:
                    return noms
    except Exception as e:
        print("Donnees PSA (joueurs) : " + repr(e)[:120], flush=True)
    return noms[:n]


@_tenace
def construire_plan(joueurs=None):
    """Phase 1 : « <joueur> psa 10 » puis « <joueur> psa 9 » pour chaque joueur. -> nombre de recherches ajoutees."""
    joueurs = joueurs if joueurs is not None else joueurs_cibles()
    debut, fin = fenetre()
    n = 0
    with _verrou:
        c = _cx()
        try:
            for k, nom in enumerate(joueurs):
                for i, note in enumerate(NOTES):
                    q = _mots_joueur(nom) + " " + note
                    if c.execute("INSERT OR IGNORE INTO plan (q, phase, joueur, ordre, debut, fin) VALUES (?,1,?,?,?,?)",
                                 (q, nom, k * len(NOTES) + i, debut, fin)).rowcount:
                        n += 1
            c.commit()
        finally:
            c.close()
    return n


def _nomme(titre, joueur):
    try:
        import a_grader
        return a_grader._nomme(titre, joueur)
    except Exception:
        return True


@_tenace
def _parts_nommees():
    """Pour chaque recherche de la phase 1 : (ventes gardees, ventes qui nomment bien le joueur)."""
    c = _cx()
    try:
        rows = c.execute("SELECT q, joueur, titre FROM ventes WHERE q LIKE '% psa 10' OR q LIKE '% psa 9'").fetchall()
    finally:
        c.close()
    out = {}
    for k, (q, joueur, titre) in enumerate(rows):
        if k % 2000 == 1999:
            time.sleep(0.01)
        n = out.setdefault(q, [0, 0])
        n[0] += 1
        n[1] += 1 if _nomme(titre, joueur) else 0
    return out


def etendre_plan(joueurs=None):
    """26 nov 2026, 18 h 50 (Mathieu : « besoin de plus de data parce qu'on doit etre vraiment tres complet [...] au moins entre
    500 et 1 000 » ; son choix : « 12 mois + 500 joueurs »). La collecte du 26 nov (200 joueurs, 120 jours) n'est PAS refaite :
    1. chaque recherche finie recoit la TRANCHE D'AVANT (de 12 mois a la plus vieille vente recue, sinon a son ancien debut) :
       rien n'est paye deux fois ;
       pas celles qui ramenent surtout d'autres joueurs (« cam york » : du baseball), ni une raw arretee par ses pages (une carte
       tres vendue : ses ventes recentes suffisent), ni une raw deja dans nos archives ;
    2. les joueurs de plus (jusqu'a JOUEURS_N) entrent dans la phase 1, sur 12 mois ;
    3. la phase 2 sera replanifiee : la raw des cartes vues en PSA 10 sur 12 mois.
    -> {« tranches », « nouvelles », « autres_joueurs »}. Ne part jamais seule : c'est l'admin qui relance."""
    debut, fin = fenetre()
    joueurs = joueurs if joueurs is not None else joueurs_cibles()
    parts = _parts_nommees()
    return _etendre_ecrire(joueurs, parts, debut, fin)


@_tenace
def _etendre_ecrire(joueurs, parts, debut, fin):
    bilan_ = {"tranches": 0, "nouvelles": 0, "autres_joueurs": 0}
    with _verrou:
        c = _cx()
        try:
            for q, phase, d0, raison, fini, recu in c.execute("SELECT q, phase, debut, raison, fini, recu_min FROM plan").fetchall():
                if not fini or not d0 or d0 <= debut or str(raison or "").startswith("refusee"):
                    continue                                  # pas finie (elle reprendra telle quelle), deja aussi loin, ou refusee
                if phase == 1:
                    n, nn = parts.get(q, (0, 0))
                    if raison == "autres joueurs" or (n >= AUTRES_MIN and nn < AUTRES_PART * n):
                        c.execute("UPDATE plan SET raison='autres joueurs' WHERE q=?", (q,))
                        bilan_["autres_joueurs"] += 1
                        continue
                elif raison not in ("toutes les ventes", "fenetre atteinte"):
                    continue
                # la tranche finit ou les ventes recues se sont arretees (« jack hughes psa 10 », 26 nov : 42 ventes, la plus vieille
                # d'il y a 8 jours) : pas de trou entre les deux tranches ; sans vente recue, a l'ancien debut
                recu = str(recu or "")[:10]
                c.execute("UPDATE plan SET fini=0, pages=0, raison=NULL, debut=?, fin=? WHERE q=?", (debut, recu if d0 < recu <= fin else d0, q))
                bilan_["tranches"] += 1
            base = (c.execute("SELECT COALESCE(MAX(ordre), -1) FROM plan WHERE phase=1").fetchone()[0] or 0) + 1
            for k, nom in enumerate(joueurs):
                for i, note in enumerate(NOTES):
                    if c.execute("INSERT OR IGNORE INTO plan (q, phase, joueur, ordre, debut, fin) VALUES (?,1,?,?,?,?)",
                                 (_mots_joueur(nom) + " " + note, nom, base + k * len(NOTES) + i, debut, fin)).rowcount:
                        bilan_["nouvelles"] += 1
            c.execute("UPDATE collecte SET raw_planifie=0, version=? WHERE id=1", (VERSION_PLAN,))
            c.commit()
        finally:
            c.close()
    return bilan_


def carte_du_titre(titre, joueur, note="10"):
    """Un titre -> la recherche RAW de sa carte exacte (les mots de l'app, sans la note), ou None si ce n'est pas une carte seule
    de ce joueur, nommee (un set ou une parallele), gradee PSA <note>. Les memes regles que les comps (cartes_match) et que les
    tendances (tendance_sortes.autre_carte : un « + », un lot, une reedition -> ecartee ; on perd quelques ventes, jamais une fausse)."""
    import cartes_match
    import tendance_sortes
    try:
        ct = cartes_match.cible_titre(titre, joueur)
    except Exception:
        return None
    g = ct.get("grade") or {}
    if g.get("cie") != "psa" or str(g.get("note") or "") != str(note):
        return None
    if ct.get("autres_joueurs"):
        return None                                           # carte a plusieurs joueurs
    nom = (cartes_match.joueur_du_titre(joueur) or _simple(joueur)).split()
    if not nom or nom[-1] not in str(ct.get("joueur") or "").split():
        return None                                           # la carte d'un autre joueur
    if not ct.get("carte_nommee"):
        return None                                           # « connor bedard psa 10 rookie » : on ne sait pas quelle carte
    try:                                                      # le tri des comps accepte-t-il cette vente pour SA recherche ?
        if cartes_match.raisons_refus(cartes_match.cible(cartes_match.requete_ebay(ct)), titre):
            return None                                       # (un lot ecrit avec « + », la suite d'un set, une carte abimee...)
    except Exception:
        return None
    ct["grade"] = None
    q = cartes_match.requete_ebay(ct)
    if len(q.split()) < 3 or tendance_sortes.autre_carte(titre, q):
        return None                                           # un lot, une reedition
    return q


@_tenace
def _titres():
    c = _cx()
    try:
        return c.execute("SELECT joueur, titre FROM ventes WHERE joueur IS NOT NULL").fetchall()
    finally:
        c.close()


@_tenace
def _plan_vide():
    c = _cx()
    try:
        return not c.execute("SELECT COUNT(*) FROM plan").fetchone()[0]
    finally:
        c.close()


def cartes_psa10(n_min=N10_MIN, battre=None):
    """Les cartes exactes vues en PSA 10 dans la collecte -> [(recherche raw, joueur, ventes PSA 10)], les plus vendues d'abord."""
    rows = _titres()
    vues = {}
    for i, (joueur, titre) in enumerate(rows):
        if i % 500 == 499:
            time.sleep(0.01)                                  # des dizaines de milliers de titres : le serveur respire
            if battre and i % 5000 == 4999:
                battre()
        t = str(titre or "").lower()
        if "psa" not in t or "10" not in t:
            continue                                          # ni PSA ni 10 dans le titre : inutile de le decoder
        q = carte_du_titre(titre, joueur)
        if q:
            v = vues.setdefault(q, [joueur, 0])
            v[1] += 1
    return sorted(((q, j, n) for q, (j, n) in vues.items() if n >= n_min), key=lambda x: (-x[2], x[0]))


def _dans_archives(q, debut):
    """La recherche raw est-elle deja dans nos archives, et fraiche ? (la banque Young Guns relit « <joueur> young guns »)"""
    try:
        import base_ventes
        c = base_ventes._cx()
        try:
            n, dernier = c.execute("SELECT COUNT(*), MAX(le) FROM ventes WHERE q=? AND le >= ? AND prix > 0", (q, debut)).fetchone()
        finally:
            c.close()
    except Exception:
        return False
    frais = (_aujourdhui() - timedelta(days=ARCHIVE_FRAIS_J)).isoformat()
    return bool(n and n >= ARCHIVE_MIN and dernier and str(dernier)[:10] >= frais)


def construire_plan_raw(battre=None):
    """Phase 2 : la recherche raw de chaque carte vue assez souvent en PSA 10. -> nombre de recherches a faire."""
    _run_maj()
    debut, fin = fenetre()
    cartes = cartes_psa10(battre=battre)[:RAW_MAX]
    return _ecrire_plan_raw(cartes, debut, fin)


@_tenace
def _ecrire_plan_raw(cartes, debut, fin):
    n = 0
    with _verrou:
        c = _cx()
        try:
            for k, (q, joueur, n10) in enumerate(cartes):
                if c.execute("SELECT 1 FROM plan WHERE q=?", (q,)).fetchone():
                    continue
                if _dans_archives(q, debut):
                    c.execute("INSERT INTO plan (q, phase, joueur, ordre, n10, debut, fin, fini, raison, le) VALUES (?,2,?,?,?,?,?,1,'deja dans nos archives',?)",
                              (q, joueur, k, n10, debut, fin, time.time()))
                    continue
                c.execute("INSERT INTO plan (q, phase, joueur, ordre, n10, debut, fin) VALUES (?,2,?,?,?,?,?)", (q, joueur, k, n10, debut, fin))
                n += 1
            c.execute("UPDATE collecte SET raw_planifie=1 WHERE id=1")
            c.commit()
        finally:
            c.close()
    return n


# -- 2. la collecte ------------------------------------------------------------------------------------------------------
def _page(q, page, debut, fin):
    import mega_test
    return mega_test._page(q, page, debut, fin)             # la meme requete CompSniper que le mega test


def reserve_app():
    import mega_test
    return mega_test.reserve_app()


def credits_disponibles(plafond=None):
    """Ce que la collecte peut encore depenser : son plafond ET le budget du mois moins la reserve de l'app."""
    import historique
    r = _run()
    plafond = plafond if plafond is not None else (r.get("plafond") or PLAFOND_DEFAUT)
    return max(0, min(plafond - (r.get("credits") or 0), historique.budget_mois() - reserve_app() - historique.utilises()["mois"]))


def _texte(t, **kw):
    _run_maj(texte=t, battement=time.time(), **kw)


@_tenace
def _a_faire():
    c = _cx()
    try:
        return c.execute("SELECT q, phase, joueur, pages, debut, fin FROM plan WHERE fini=0 ORDER BY phase, ordre").fetchall()
    finally:
        c.close()


@_tenace
def _noter(q, joueur, ventes):
    """Les ventes dans NOTRE base (jamais dans les archives). Une vente n'entre qu'une fois (son numero d'annonce).
    -> le nombre de ventes nouvelles."""
    n = 0
    with _verrou:
        c = _cx()
        try:
            for x in ventes:
                cle = x.get("item_id") or (x["titre"] + "|" + x["le"])
                n += c.execute("INSERT OR IGNORE INTO ventes (cle, q, joueur, titre, prix, le) VALUES (?,?,?,?,?,?)",
                               (cle, q, joueur, x["titre"], x["prix"], x["le"])).rowcount
            c.commit()
        finally:
            c.close()
    return n


def collecter(plafond=None, arret=None, pause=None):
    """La collecte (en fond). Reprend : une recherche finie n'est jamais refaite ; une recherche commencee reprend a sa page
    suivante, avec la meme fenetre. -> le bilan."""
    r = _collecter(plafond, arret, PAUSE_S if pause is None else pause)
    return bilan() if r is None else r


def _collecter(plafond, arret, pause):
    import historique
    import vendues
    if not historique.actif():
        return {"ok": False, "erreur": "Clé CompSniper absente (COMPSNIPER_CLE)"}
    jeton = uuid.uuid4().hex
    with _verrou:
        r0 = _run()
        if ETAT["en_cours"] or vivante(r0):
            deja = True
        else:
            deja = False
            ETAT["en_cours"] = True
    if deja:
        return {**bilan(), "deja": True}
    plafond = int(plafond or r0.get("plafond") or PLAFOND_DEFAUT)
    if r0.get("statut") in (None, "aucune"):
        _run_maj(statut="en_cours", plafond=plafond, credits=0, debut=time.time(), battement=time.time(), texte="Le plan", erreur=None, jeton=jeton,
                 version=VERSION_PLAN)
    else:
        _run_maj(statut="en_cours", plafond=plafond, battement=time.time(), texte="Reprise", erreur=None, jeton=jeton)
    a_moi = lambda: _run().get("jeton") == jeton
    fin_statut = "interrompue"
    try:
        if _plan_vide() and not construire_plan():
            fin_statut = "erreur"
            _run_maj(erreur="Aucun joueur dans l'indice SlabIQ : rien à collecter")
            return None
        if (r0.get("version") or 1) < VERSION_PLAN and r0.get("statut") not in (None, "aucune") and not _plan_vide():
            _texte("Le plan : 12 mois, plus de joueurs")
            e_ = etendre_plan()
            print(f"Donnees PSA : plan etendu ({JOURS} jours, {JOUEURS_N} joueurs) : {e_['tranches']} recherches recoivent la tranche d'avant, "
                  f"{e_['nouvelles']} nouvelles, {e_['autres_joueurs']} laissees (d'autres joueurs)", flush=True)
        taux = vendues._taux_usd_cad() or 1.37
        refus_suite = 0
        while True:
            a_faire = _a_faire()
            if not a_faire:
                if not _run().get("raw_planifie"):
                    _texte("Phase 2 : les cartes vues en PSA 10")
                    try:
                        construire_plan_raw(battre=lambda: _run_maj(battement=time.time()))     # la phase 1 est finie : les versions raw
                    except Exception as e:
                        fin_statut = "erreur"
                        _run_maj(erreur="Phase 2 : " + repr(e)[:120])
                        return None
                    if not _run().get("raw_planifie"):
                        fin_statut = "erreur"
                        _run_maj(erreur="Phase 2 : le plan n'a pas pu etre ecrit")
                        return None
                    continue
                break
            for q, phase, joueur, pages, debut, fin in a_faire:
                pages_max = PAGES_MAX if phase == 1 else PAGES_MAX_RAW
                page = (pages or 0) + 1
                vus = set()
                autres_suite = 0
                while True:
                    if not a_moi():                           # une autre collecte a pris le relais : celle-ci s'arrete, sans rien toucher
                        fin_statut = None
                        return None
                    if arret and arret():
                        fin_statut = "arretee"
                        _texte("Arrêtée")
                        return None
                    if credits_disponibles(plafond) <= 0:
                        fin_statut = "plafond" if (_run().get("credits") or 0) >= plafond else "attente_mois"
                        _texte("Plafond de la collecte atteint" if fin_statut == "plafond" else "Budget du mois atteint : reprend le mois prochain")
                        return None
                    _texte(f"{q} · page {page}")
                    essais = 0
                    refusee = None
                    while True:
                        try:
                            d = _page(q, page, debut, fin)
                            refus_suite = 0
                            break
                        except urllib.error.HTTPError as e:
                            # comme le mega test (25 nov) : une page refusee (400, 404, 422) ferme CETTE recherche, sans credit ;
                            # 8 refus de suite : l'API a change, on arrete ; 429 / 5xx attendent et reessaient ; 401 / 403 arretent
                            if e.code in (400, 404, 422) and refus_suite < REFUS_SUITE_MAX:
                                refus_suite += 1
                                refusee = e.code
                                break
                            if (e.code == 429 or e.code >= 500) and essais < 5:
                                essais += 1
                                _texte(f"{q} · page {page} · CompSniper HTTP {e.code}, nouvel essai {essais}/5")
                                time.sleep(min(300, 30 * 2 ** (essais - 1)) if pause else 0)
                                continue
                            fin_statut = "erreur"
                            _run_maj(erreur=f"CompSniper HTTP {e.code}")
                            return None
                        except Exception as e:
                            if essais < 5:
                                essais += 1
                                time.sleep(min(300, 30 * 2 ** (essais - 1)) if pause else 0)
                                continue
                            fin_statut = "erreur"
                            _run_maj(erreur="CompSniper injoignable (" + type(e).__name__ + ")")
                            return None
                    if refusee:
                        _plan_maj(q, fini=1, raison=f"refusee (HTTP {refusee})", le=time.time())
                        break
                    _tenace(historique._compter)(False)       # 1 page = 1 credit, compte comme les autres
                    cr = (_run().get("credits") or 0) + 1
                    _run_maj(credits=cr, battement=time.time())
                    if cr % 100 == 0:                         # le journal du serveur : ou en est la collecte
                        print(f"Donnees PSA : {cr} credits (phase {phase} : {q}, page {page})", flush=True)
                    v = historique.lire_reponse(d, taux)
                    ids = {x.get("item_id") or (x["titre"] + "|" + x["le"]) for x in v}
                    neuves = ids - vus
                    vus |= ids
                    ajoutees = _noter(q, joueur, v) if v else 0
                    plus_vieux = min((x["le"] for x in v), default=None)
                    raison = None
                    # 26 nov 2026 (le fichier de la collecte : « cam york psa 10 » = 1 480 ventes de baseball et de football, 30 pages
                    # payees) : deux pages de suite ou presque personne ne nomme le joueur : la recherche s'arrete la
                    if phase == 1 and joueur and len(v) >= 20 and sum(1 for x in v if _nomme(x["titre"], joueur)) < AUTRES_PAGE_PART * len(v):
                        autres_suite += 1
                    else:
                        autres_suite = 0
                    if len((d or {}).get("results") or []) < PAR_PAGE * 0.9:
                        raison = "toutes les ventes"
                    elif not neuves:
                        raison = "page repetee"
                    elif autres_suite >= AUTRES_PAGES:
                        raison = "autres joueurs"
                    elif plus_vieux and plus_vieux < debut:
                        raison = "fenetre atteinte"
                    elif page >= pages_max:
                        raison = "pages max"
                    _page_faite(q, page, ajoutees, raison, plus_vieux)
                    if raison:
                        break
                    page += 1
                    time.sleep(pause)
                time.sleep(pause)
        if not a_moi():
            fin_statut = None
            return None
        fin_statut = "terminee"
        _texte("Terminée")
        return None
    except Exception as e:                                    # une erreur imprevue : on le dit, et la boucle de l'heure reprendra
        fin_statut = "erreur"
        print("Donnees PSA : arret imprevu : " + repr(e)[:200], flush=True)
        try:
            _run_maj(erreur="Arrêt imprévu : " + repr(e)[:120])
        except Exception:
            pass
        return None
    finally:
        ETAT["en_cours"] = False
        try:
            if fin_statut is None or not a_moi():
                print("Donnees PSA : une autre collecte a pris le relais, celle-ci s'arrete", flush=True)
            else:
                _run_maj(statut=fin_statut, battement=time.time())
                r = _run()
                print(f"Donnees PSA : {fin_statut} ({r.get('credits') or 0} credits{' ; ' + str(r.get('erreur')) if r.get('erreur') else ''})", flush=True)
        except Exception as e:
            print("Donnees PSA (fin) : " + repr(e)[:160], flush=True)


@_tenace
def _page_faite(q, page, ajoutees, raison, plus_vieux):
    with _verrou:
        c = _cx()
        try:
            c.execute("UPDATE plan SET pages=?, ventes=ventes+?, fini=?, raison=?, le=?, recu_min=MIN(COALESCE(recu_min, ?), ?) WHERE q=?",
                      (page, ajoutees, 1 if raison else 0, raison, time.time(), plus_vieux or "9999", plus_vieux or "9999", q))
            c.commit()
        finally:
            c.close()


@_tenace
def _plan_maj(q, **kw):
    with _verrou:
        c = _cx()
        try:
            c.execute("UPDATE plan SET " + ", ".join(k + "=?" for k in kw) + " WHERE q=?", list(kw.values()) + [q])
            c.commit()
        finally:
            c.close()


def lancer(plafond=None):
    """L'admin lance (ou relance) la collecte, en fond."""
    if ETAT["en_cours"] or vivante():
        return {**bilan(), "deja": True}
    import historique
    if not historique.actif():
        return {"ok": False, "erreur": "Clé CompSniper absente (COMPSNIPER_CLE)"}
    import contextvars
    ctx = contextvars.copy_context()
    threading.Thread(target=lambda: ctx.run(collecter, plafond), daemon=True, name="donnees-psa").start()
    return {"ok": True, "lancee": True}


def continuer_si_besoin():
    """Boucle du serveur (chaque heure) et demarrage : une collecte DEJA LANCEE par l'admin et coupee (redemarrage, erreur
    passagere, mois a sec) reprend seule. Jamais lancee, terminee, arretee ou au plafond : rien ne part."""
    if ETAT["en_cours"]:
        return None
    import historique
    if not historique.actif():
        return None
    r = _run()
    st = r.get("statut") or "aucune"
    if st not in ("en_cours", "interrompue", "attente_mois", "erreur"):
        return None
    if vivante(r):                                            # elle tourne (son battement est frais) : on ne la double jamais
        return None
    if st == "erreur" and time.time() - (r.get("battement") or 0) < 15 * 60:
        return None
    if credits_disponibles() <= 0:
        return None
    print("Donnees PSA : reprise (" + st + ")", flush=True)
    return lancer()


def bilan():
    import historique
    try:
        c = _cx()
        try:
            n, n_f, pg = c.execute("SELECT COUNT(*), COALESCE(SUM(fini),0), COALESCE(SUM(pages),0) FROM plan").fetchone()
            n1, n1_f = c.execute("SELECT COUNT(*), COALESCE(SUM(fini),0) FROM plan WHERE phase=1").fetchone()
            nv = c.execute("SELECT COUNT(*) FROM ventes").fetchone()[0]
            nj = c.execute("SELECT COUNT(DISTINCT joueur) FROM plan WHERE phase=1").fetchone()[0]
            raisons = dict(c.execute("SELECT raison, COUNT(*) FROM plan WHERE fini=1 GROUP BY raison").fetchall())
        finally:
            c.close()
    except sqlite3.Error:
        n = n_f = pg = n1 = n1_f = nv = nj = 0
        raisons = {}
    r = _run()
    vivant = ETAT["en_cours"] or vivante(r)
    return {"ok": True, "en_cours": bool(vivant), "statut": r.get("statut") or "aucune", "texte": r.get("texte"),
            "phase": 2 if r.get("raw_planifie") else 1, "joueurs": int(nj), "recherches": int(n), "recherches_finies": int(n_f),
            "cartes_raw": int(n - n1), "pages": int(pg), "ventes": int(nv), "raisons": raisons,
            "credits": r.get("credits") or 0, "plafond": r.get("plafond") or PLAFOND_DEFAUT, "debut": r.get("debut"),
            "battement": r.get("battement"), "erreur": r.get("erreur"), "reserve_app": reserve_app(), "jours": JOURS,
            "joueurs_vises": JOUEURS_N, "dispo": credits_disponibles(), "compsniper": historique.etat(),
            # une collecte faite avec l'ancien plan (120 jours, 200 joueurs) : la relancer l'ETEND (12 mois, 500 joueurs)
            "a_etendre": bool(n and (r.get("version") or 1) < VERSION_PLAN and r.get("statut") not in (None, "aucune"))}
