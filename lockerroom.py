"""
LOCKERROOM - logique de l'app (breakers, boutique eBay, boutique physique,
bilan). Une seule base SQLite (lockerroom.db, a cote de ce fichier). Chaque
methode publique de Api est appelee par l'ecran via POST /api/<methode>.

Separee de Hall of Cardz : aucune dependance a 130point, Scrapfly, Gixen ni
aux cles de Mathieu. Rien n'est publie ni achete sur eBay : l'app lit des
rapports CSV que le vendeur telecharge lui-meme et prepare des brouillons.
"""
import csv
import hashlib
import io
import json
import math
import os
import re
import secrets
import sqlite3
import statistics
import threading
import unicodedata
import time
from datetime import datetime, timedelta, timezone

import calcul
import catalogue
import ebay_compte
import ebay_csv
import nouvelles   # 24 oct 2026 : importe ici, avant les taches de fond (Render : « partially initialized module »)
import sante
import sports
import valeurs
import vision
# 25 oct 2026 - Render : « partially initialized module 'valeurs_maj' » (deux fils importaient le meme module en
# meme temps). Tous les modules importes ici, une seule fois, au demarrage, avant les taches de fond.
import admin  # noqa: E402
import annonces  # noqa: E402
import cartes_match  # noqa: E402
import checklist_import  # noqa: E402
import comptes  # noqa: E402
import deals  # noqa: E402
import demandes  # noqa: E402
import forfaits  # noqa: E402
import nouveaux_produits  # noqa: E402
import gts  # noqa: E402
import paiements  # noqa: E402
import valeurs_maj  # noqa: E402
import marche  # noqa: E402
import valeur_produit  # noqa: E402
import vendues  # noqa: E402
import ventes_communaute  # noqa: E402

_VERROU_IMG = threading.Lock()
# 27 oct 2026 - photos de tiers (Upper Deck, GTS, annonces eBay hors contexte) : seulement avec une licence (=1)
IMAGES_TIERCES = os.environ.get("LOCKERROOM_IMAGES_TIERCES") == "1"

DOSSIER = os.environ.get("LOCKERROOM_DONNEES") or os.path.dirname(os.path.abspath(__file__))   # heberge : disque persistant
CHEMIN_DB = os.path.join(DOSSIER, "lockerroom.db")
_verrou = threading.RLock()
CATEGORIE_CARTES = "261328"   # eBay : Sports Trading Card Singles

REGLAGES_DEFAUT = {
    "prix_auto": {},                                            # 27 oct 2026 : mode Auto des prix eBay (voir prix_auto_regler)
    "tuto_vendeur": 0, "tuto_acheteur": 0,                      # 31 oct 2026 : le tour de l'app deja vu (par compte)
    "watch": {},                                                # 29 oct 2026 : alarmes de la watchlist (voir watchlist.regler)
    "photo_studio": True,
    "flou_niveau": 2,                                           # 30 oct 2026 : fond flou 1 leger, 2 moyen, 3 fort
    "ramassage": [],
    "pays": "CA",                # 8 nov 2026 : d'ou l'utilisateur achete (CA | US) : taxes, douanes et deals de son pays d'abord
    # 30 oct 2026 (Mathieu : « la personne qui a le profil doit pouvoir personnaliser ses deals un peu ») :
    # collectionne : recrues | veterans | legendes | hits | gradees (vide = tout) ; favoris : joueurs ou equipes
    "deals_profil": {},                                            # 30 oct 2026 : vendeurs ou l'acheteur ramasse sur place (pas de port)                                       # 29 oct 2026 : photo studio (fond clair) ou les photos telles quelles
    "alarmes": {},                                              # 29 oct 2026 : les alertes cochees (voir alarmes.py)
    "nom_boutique": "Ma boutique",
    "equipe_fav": "",                                           # 26 oct 2026 : les accents de l'app aux couleurs de cette equipe
    "palette": "refractor",                                     # 27 oct 2026 : refractor + 5 paralleles
    "ia_photos_ok": False,                                      # 27 oct 2026 : permission explicite (Apple 5.1.2(i))
    "ia_entrainement_ok": False,                                # 3 nov 2026 : photos d'examen gardees pour entrainer l'IA (OUI explicite)
    "frais_ebay_pct": 13.25, "frais_ebay_fixe": 0.40,           # eBay Canada, cartes (a ajuster a ton compte)
    "frais_auto": True,                                          # 9 nov 2026 : le % suit les frais reels de tes ventes eBay
    "frais_break_pct": 10.9, "frais_break_fixe": 0.30,          # plateforme de live (ex. commission + paiement)
    "taxes_pct": 14.975,                                        # TPS + TVQ (Quebec)
    "marge_break": 25, "plancher_place": 1, "arrondi_place": 1,
    "pct_consignation": 20, "bonus_credit": 10,
    "paliers_rachat": [[10, 30], [50, 50], [200, 60], [999999, 70]],
    "description_ebay": "",
    "activites": None,           # 22 oct 2026 - onglets visibles {"breaks":bool,"magasin":bool} ; None = deduit des donnees
    "mode": "",                  # 22 oct 2026 - "vendeur" ou "acheteur" (vide = a choisir a la 1re ouverture)
    "epn_campid": "",
    "langue": "",
    "partage_ventes": None,       # 27 oct 2026 : on DEMANDE (oui / non) ; sans reponse, rien n'est partage
    "budget_mois": 0,            # 25 oct 2026 - acheteur : budget du mois ($ CA), 0 = aucun
    "niveau": "",                # 26 oct 2026 - questionnaire : debutant | retour | moyen | expert (adapte les conseils)
    "objectif": "",              #   collection | profit | breaks | tout      # 25 oct 2026 - mes ventes (anonymes) aident les prix vendus de la communaute                # 24 oct 2026 - "fr" ou "en" (vide = celle du navigateur)
    "devise": "",                # 24 oct 2026 - "CAD" ou "USD" (affichage ; les montants restent gardes en $ CA)
    "modele_annonce": None,      # 24 oct 2026 - choix gardes pour la prochaine annonce (expedition, retours, offres, promotion)
    "sport": "hockey",           # 23 oct 2026 - sport principal (quand l'app hesite : voir sports.py)            # 21 oct 2026 - eBay Partner Network : liens d'achat suivis (affiliation)
}

LOGO_MAX = 400_000                       # caracteres de la data URL (~300 Ko d'image)
_RE_LOGO = re.compile(r"^data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS reglages (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS produits (id INTEGER PRIMARY KEY, nom TEXT, saison TEXT, format TEXT, cout_boite REAL,
    par_boite TEXT, cree_le TEXT);
CREATE TABLE IF NOT EXISTS checklist (id INTEGER PRIMARY KEY, produit_id INTEGER, numero TEXT, joueur TEXT, equipe TEXT,
    categorie TEXT, tirage INTEGER, recrue INTEGER, auto INTEGER, relique INTEGER);
CREATE TABLE IF NOT EXISTS etoiles (joueur TEXT PRIMARY KEY, etoiles INTEGER);
CREATE TABLE IF NOT EXISTS breaks (id INTEGER PRIMARY KEY, nom TEXT, produit_id INTEGER, mode TEXT, boites REAL,
    cout REAL, frais_pct REAL, frais_fixe REAL, port_paye REAL DEFAULT 0, statut TEXT, jeton TEXT, empreinte TEXT,
    tirage TEXT, cree_le TEXT, ferme_le TEXT);
CREATE TABLE IF NOT EXISTS places (id INTEGER PRIMARY KEY, break_id INTEGER, cle TEXT, libelle TEXT, prix REAL,
    acheteur TEXT, vendu INTEGER DEFAULT 0, paye INTEGER DEFAULT 0, lot TEXT, ordre INTEGER);
CREATE TABLE IF NOT EXISTS frappes (id INTEGER PRIMARY KEY, break_id INTEGER, carte TEXT, joueur TEXT, equipe TEXT,
    valeur REAL, place_id INTEGER, envoye INTEGER DEFAULT 0, suivi TEXT, tirage_multi TEXT, cree_le TEXT);
CREATE TABLE IF NOT EXISTS cartes (id INTEGER PRIMARY KEY, titre TEXT, joueur TEXT, annee TEXT, marque TEXT, set_nom TEXT,
    numero TEXT, parallele TEXT, tirage INTEGER, auto INTEGER DEFAULT 0, grade TEXT, equipe TEXT, cout REAL, valeur REAL,
    prix_demande REAL, emplacement TEXT, statut TEXT, item_number TEXT, sku TEXT, consignataire_id INTEGER, source TEXT,
    canal TEXT, prix_vendu REAL, frais REAL, port_paye REAL, port_charge REAL, profit REAL, client_id INTEGER,
    cree_le TEXT, vendu_le TEXT, note TEXT, consignation_payee INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS ventes_ebay_vues (transaction_id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS frais_observes (transaction_id TEXT PRIMARY KEY, le TEXT, base REAL, frais REAL);
CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY, nom TEXT, contact TEXT, credit REAL DEFAULT 0, note TEXT, cree_le TEXT);
CREATE TABLE IF NOT EXISTS consignataires (id INTEGER PRIMARY KEY, nom TEXT, contact TEXT, pct_boutique REAL, cree_le TEXT);
CREATE TABLE IF NOT EXISTS paiements_consignation (id INTEGER PRIMARY KEY, consignataire_id INTEGER, montant REAL, le TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS ventes_comptoir (id INTEGER PRIMARY KEY, le TEXT, sous_total REAL, taxes REAL, total REAL,
    paiement TEXT, client_id INTEGER, lignes TEXT);
CREATE TABLE IF NOT EXISTS rachats (id INTEGER PRIMARY KEY, le TEXT, client_id INTEGER, valeur REAL, offre REAL, mode TEXT, lignes TEXT);
CREATE TABLE IF NOT EXISTS depenses (id INTEGER PRIMARY KEY, le TEXT, categorie TEXT, montant REAL, note TEXT);
CREATE TABLE IF NOT EXISTS soumissions (id INTEGER PRIMARY KEY, compagnie TEXT, service TEXT, numero TEXT, envoyee_le TEXT,
    retour_prevu TEXT, cout_carte REAL, statut TEXT, cree_le TEXT, revenue_le TEXT, valeurs TEXT, suivi TEXT, mode TEXT);
"""


def _envoi_net():
    """6 nov 2026 : le materiel d'envoi d'une carte revendue (deals.ENVOI_NET) : compte dans le profit des deals."""
    import deals as _d
    return _d.ENVOI_NET


def _net_rev(valeur):
    """7 nov 2026 : ce qui reste de la revente d'un deal (deals.net_revente : frais eBay sur prix + port, pub, envoi)."""
    import deals as _d
    return _d.net_revente(valeur)


def _paye(total, x=None):
    """7 nov 2026 : ce que tu paies vraiment (mise ou prix + port, taxes de l'achat comprises : deals.cout_achat) ;
    8 nov : hors Canada, les frais d'importation de l'annonce x (deals.taxe_de)."""
    import deals as _d
    return _d.cout_achat(total, _d.taxe_de(x) if x is not None else None)


def _maintenant():
    return datetime.now().isoformat(timespec="seconds")


_BASES_PRETES = set()      # 28 oct 2026 (vitesse) : schema et migrations verifies une fois par base et par demarrage


def _connecter(chemin=None):
    p = chemin or CHEMIN_DB
    existe = os.path.exists(p)                 # 3 nov 2026 (revue) : AVANT connect (qui cree le fichier vide) : un compte
    c = sqlite3.connect(p, timeout=30)         # supprime puis recree dans le meme processus n'avait plus de tables
    c.row_factory = sqlite3.Row
    if p in _BASES_PRETES and existe:
        return c
    c.executescript(SCHEMA)
    # 28 oct 2026 (vitesse) : index des places et frappes (la liste des breaks faisait 4 sous-requetes par break)
    c.executescript("CREATE INDEX IF NOT EXISTS places_break ON places(break_id, vendu); "
                    "CREATE INDEX IF NOT EXISTS frappes_break ON frappes(break_id, envoye);")
    cols = {r[1] for r in c.execute("PRAGMA table_info(breaks)")}
    if "catalogue_id" not in cols:                 # 18 oct 2026 - break fait a partir du catalogue
        c.execute("ALTER TABLE breaks ADD COLUMN catalogue_id TEXT")
        c.commit()
    # 18 oct 2026 - sante de l'inventaire (tous les articles eBay)
    cols = {r[1] for r in c.execute("PRAGMA table_info(cartes)")}
    for col, typ in (("debut", "TEXT"), ("watchers", "INTEGER"), ("categorie_ebay", "TEXT"), ("photo", "TEXT"), ("vu_actif_le", "TEXT"),
                     ("sport", "TEXT"), ("recrue", "INTEGER"), ("relique", "INTEGER"), ("cert", "TEXT"), ("photos", "TEXT"),
                     ("vues", "INTEGER"), ("impressions", "INTEGER"), ("trafic_le", "TEXT"), ("photos_orig", "TEXT"), ("studio_v", "INTEGER"),
                     ("etat_json", "TEXT"), ("etat_le", "TEXT"), ("envoi_json", "TEXT"), ("soumission_id", "INTEGER"),
                     ("a_finir_le", "TEXT"), ("valeur_annonces", "REAL"), ("valeur_annonces_n", "INTEGER"),
                     ("valeur_annonces_le", "TEXT")):         # 9 nov 2026 : repere prix sans vente (annonces pareilles - 10 %)         # 9 nov 2026 : preparee pour la vente, pas encore sur eBay (onglet « A finir »)            # 1er nov 2026 - l'etat estime (pre-gradation)   # 31 oct 2026 - vues des annonces
        if col not in cols:
            c.execute(f"ALTER TABLE cartes ADD COLUMN {col} {typ}")
    # 1er nov 2026 - soumissions : les colonnes ajoutees apres coup
    so_cols = {r[1] for r in c.execute("PRAGMA table_info(soumissions)")}
    for col in ("valeurs", "suivi", "mode"):
        if so_cols and col not in so_cols:
            c.execute(f"ALTER TABLE soumissions ADD COLUMN {col} TEXT")
    # 23 oct 2026 - autres sports : le sport du produit et du break (equipes de sa ligue)
    for table in ("produits", "breaks"):
        if "sport" not in {r[1] for r in c.execute(f"PRAGMA table_info({table})")}:
            c.execute(f"ALTER TABLE {table} ADD COLUMN sport TEXT")
    c.executescript("""CREATE TABLE IF NOT EXISTS sante (item_number TEXT PRIMARY KEY, maj TEXT, verdict TEXT, suggestion REAL,
        mediane REAL, n INTEGER, ecart REAL, requete TEXT, fait INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS rachats_vus (cle TEXT PRIMARY KEY, maj TEXT);
        CREATE TABLE IF NOT EXISTS opportunites (item_id TEXT PRIMARY KEY, titre TEXT, total REAL, url TEXT, photo TEXT,
        ref_titre TEXT, ref_prix REAL, ratio REAL, vu_le TEXT, masque INTEGER DEFAULT 0);""")
    # 26 oct 2026 (Mathieu : « les faux deals sont encore presents ?? ») : les rachats calcules avec l'ancienne reference
    # (ta vente d'avant au lieu des ventes eBay de la meme carte) sont effaces une fois ; ils se refont tout seuls
    c.execute("CREATE TABLE IF NOT EXISTS migrations (nom TEXT PRIMARY KEY, le TEXT)")
    if not c.execute("SELECT 1 FROM migrations WHERE nom='rachats_ventes_reelles'").fetchone():
        c.execute("DELETE FROM opportunites")
        c.execute("DELETE FROM rachats_vus")
        c.execute("INSERT INTO migrations VALUES ('rachats_ventes_reelles', ?)", (datetime.now().isoformat(timespec="seconds"),))
        c.commit()
    # 27 oct 2026 (Mathieu : « impossible que je sois 90 % au-dessus du marche ») : le repere prix se juge maintenant sur les
    # ventes reelles sures ; ceux d'avant (prix demandes) sont effaces une fois et se refont tout seuls
    if not c.execute("SELECT 1 FROM migrations WHERE nom='sante_ventes_reelles'").fetchone():
        c.execute("DELETE FROM sante")
        c.execute("INSERT INTO migrations VALUES ('sante_ventes_reelles', ?)", (datetime.now().isoformat(timespec="seconds"),))
        c.commit()
    # 24 oct 2026 - les comparables gardes (memes cartes) : repere prix dans l'inventaire et comps au tap
    for table, col, typ in (("sante", "comps", "TEXT"), ("sante", "bas", "REAL"), ("opportunites", "comps", "TEXT"),
                            ("opportunites", "sport", "TEXT"), ("opportunites", "mediane", "REAL")):
        if col not in {r[1] for r in c.execute(f"PRAGMA table_info({table})")}:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
    c.commit()
    _BASES_PRETES.add(p)
    return c


def _opp_ok(titre):
    """25 oct 2026 : un « deal » de rachat n'est jamais un lot, une checklist ou une carte a plusieurs joueurs
    (« Young Guns Teamates Schaefer » affiche a -99 % sur l'accueil)."""
    t = cartes_match.norm(titre or "")
    return not (cartes_match.decoder(titre or "").get("exclu") or re.search(r"\bchecklists?\b|\bcl\b", t))


def _dicts(lignes):
    return [dict(r) for r in lignes]


def _bool(v):
    return 1 if str(v).strip().lower() in ("1", "true", "oui", "yes", "o", "y", "x") else 0


def _int(v):
    try:
        return int(float(str(v).replace("/", "").strip()))
    except (TypeError, ValueError):
        return None


def _float(v):
    try:
        return float(str(v).replace(",", ".").replace("$", "").strip())
    except (TypeError, ValueError):
        return None


def chemin_db_env():
    """21 oct 2026 - sandbox : sa propre base, jamais melangee aux vraies donnees.
    Multi-comptes : la base du client de la session, dans SON dossier."""
    import comptes
    d = comptes.dossier() or DOSSIER
    if d == DOSSIER:
        return CHEMIN_DB if ebay_compte.environnement() == "production" else os.path.join(DOSSIER, "lockerroom_sandbox.db")
    return os.path.join(d, "lockerroom.db" if ebay_compte.environnement() == "production" else "lockerroom_sandbox.db")


# 26 oct 2026 - app iPhone (App Store) : le serveur sait qu'une requete vient de l'app (User-Agent « LockerRoomiOS »).
# Au Canada, Apple interdit d'y vendre le Pro autrement que par ses achats integres : dans l'app, rien a acheter.
import contextvars as _cv  # noqa: E402
_IOS = _cv.ContextVar("lockerroom_ios", default=False)


def marquer_ios(oui):
    _IOS.set(bool(oui))


_API_REF = []


def vue_simulee():
    """10 nov 2026 (Mathieu : « une place dans admin ou je peux switcher de ma version a celle des users reguliers et Pro ») :
    l'admin voit l'app comme un utilisateur (« pro » ou « gratuit ») ; None = sa vraie vue. Dans la session du navigateur
    seulement (posee par admin_vue, reserve au vrai admin) ; jamais pour les taches de fond."""
    try:
        from flask import has_request_context, session
        if has_request_context():
            v = session.get("vue_admin")
            return v if v in ("pro", "gratuit") else None
    except Exception:
        pass
    return None


def ebay_prix_actif(api=None):
    """27 oct 2026 - interrupteur du serveur (LOCKERROOM_EBAY_PRIX=0) : coupe d'un geste les fonctions de prix sur les
    ANNONCES eBay (deals, prix suggere d'une annonce, repere prix et comparables, « Mettre au prix du marche ») si eBay
    le demande (licence API §9.5) ou coupe nos cles. Valeur d'une carte, tendances, breaks, inventaire et comptoir
    continuent : ils ne dependent pas de l'API eBay.
    10 nov 2026 (Mathieu : « legaux a 100 % », choix 1) : juger le prix d'une ANNONCE eBay (deal, rabais, mise max, prix
    suggere, verdict de tes annonces, alertes de deals) = l'outil de prix que la licence reserve a l'accord ecrit d'eBay
    (§8.5 c, §9.5). Pour le lancement : l'ADMIN seulement. LR_PRIX_EBAY_PUBLIC=1 apres l'accord d'eBay."""
    if os.environ.get("LOCKERROOM_EBAY_PRIX", "1") == "0":
        return False
    if os.environ.get("LR_PRIX_EBAY_PUBLIC") == "1":
        return True
    if vue_simulee():
        return False
    try:
        import comptes
        if not comptes.MULTI:
            return True                         # le PC de Mathieu (une seule personne : l'admin)
        a = api or (_API_REF[0] if _API_REF else None)
        return bool(a is not None and a._est_admin())
    except Exception:
        return False


def comps_permis(api=None):
    """10 nov 2026 (Mathieu : « pour les comps on va garder ca seulement admin, mettre le tout de cote pour la version
    officielle de lancement », « 100 % legale avec nos cles eBay ») : les ventes recoltees sur eBay (SoldComps, CompSniper,
    TheCardAPI, nos archives) et tout ce qu'on en tire (valeur d'une carte, gradations, tendances, pouls, valeur de la
    collection) : l'ADMIN seulement. Les taches de fond globales (chasseur de deals de l'admin, base des ventes) continuent.
    LR_COMPS_PUBLICS=1 pour les rouvrir a tous (seulement avec l'accord ecrit d'eBay ou une source sous licence)."""
    if os.environ.get("LR_COMPS_PUBLICS") == "1":
        return True
    if vue_simulee():
        return False
    try:
        import comptes
        if not comptes.MULTI or not comptes.courant():
            return True                         # le PC de Mathieu, ou une tache de fond sans compte (admin)
        a = api or (_API_REF[0] if _API_REF else None)
        return bool(a is not None and a._est_admin())
    except Exception:
        return False


def prix_annonces_permis():
    """10 nov 2026 (Mathieu : « assure-toi qu'on soit legaux a 100 % ») : licence de l'API eBay §9.5 (« utiliser le
    contenu eBay, seul ou avec de l'information de tiers, pour suggerer ou modeliser des prix » : interdit sans accord
    ecrit). Aucun prix, repere ou mediane n'est calcule a partir des ANNONCES lues par l'API. Les annonces restent
    montrees telles quelles (permis : chercher et parcourir les annonces). LR_PRIX_ANNONCES=1 seulement avec l'accord."""
    return os.environ.get("LR_PRIX_ANNONCES") == "1"


def est_ios():
    return _IOS.get()



def _niveau(resume, info):
    """bronze (gratuit) | silver (forfait intermediaire, plus tard) | gold (Pro, essai, offert, app locale)."""
    f = str((info or {}).get("forfait") or "").lower()
    if f in ("silver", "argent", "collector"):
        return "silver"
    return "gold" if (resume or {}).get("pro") else "bronze"

LIER = {}          # 28 oct 2026 : jetons a usage unique pour relier eBay depuis l'app iPhone (jeton -> (compte, le))

STUDIO_V = 2
# 3 nov 2026 (Mathieu : « COSMIC » et « BEAM » affiches comme joueurs) : des mots de sets et d'inserts qui ne sont jamais un nom
_MOTS_INSERTS = set("""cosmic planetary pursuit sun moon chrome refractor prizm mosaic select optic sapphire update heritage stadium club
team beam finest bowman draft topps panini donruss contenders certified spectra immaculate national treasures flawless obsidian
phoenix revolution absolute elite prestige score leaf upper deck series signature signatures autograph autographs auto rookie
rookies future watch young guns canvas exclusives high gloss clear cut black white borderless splendor allure ice metal universe
platinum premier artifacts credentials tableau ultimate collection sp authentic spx parkhurst o-pee-chee opc fleer skybox
galaxy galactic cosmos stars star legends legend inception dynasty archives gallery tribute museum diamond kings""".split())


def _nom_majuscules(titre):
    """Le premier « Prenom Nom » (2-3 mots qui commencent par une majuscule) qui n'est ni un set, ni un insert, ni une equipe."""
    import cartes_match as _cm
    if _cm._EQUIPES_MOTS["t"] is None:
        _cm._EQUIPES_MOTS["t"] = _cm._mots_equipes()
    exclus = _MOTS_INSERTS | _cm._EQUIPES_MOTS["t"] | set(getattr(_cm, "GENERIQUES", set())) | set(getattr(_cm, "VIDES", set())) | \
        {"psa", "bgs", "sgc", "cgc", "tag", "rc", "gem", "mint", "nm", "mt", "ssp", "sp", "auto", "patch", "jersey", "lot"}
    mots = re.findall(r"[A-Za-z][A-Za-z'.\-]*", str(titre or ""))
    seq = []
    for m in mots + ["."]:
        ok = m[:1].isupper() and len(m) > 1 and m.lower().strip(".") not in exclus
        if ok:
            seq.append(m)
            continue
        if len(seq) >= 2:
            return " ".join(seq[:3]).lower()
        seq = []
    return None
_RE_RELIQUE = re.compile(r"patch|relic|jersey|memorabilia|swatch|game[- ]used|game[- ]worn|patch-?tacular|materials?\b|threads|fabric", re.I)          # 31 oct 2026 : version du recadrage studio (2 : cartes couchees reconnues, carte centree)


def popularite(cartes, maint=None):
    """31 oct 2026 - l'interet des acheteurs pour TES annonces eBay : les suivis (« j'aime » / watchers) et les vues (30 j).
    Populaires : 2 suivis et plus, ou deux fois plus de vues que tes annonces typiques (30 vues minimum).
    A liquider : en ligne depuis 30 jours ou plus, 0 suivi, et peu de vues (moins de la moitie du typique) ou vues inconnues.
    Aucune annonce en ligne : None (l'ecran garde « Se vend en » et « Dorment »)."""
    maint = maint or datetime.now()
    l = [x for x in cartes if x.get("statut") == "Listée" and x.get("item_number")
         and not (x.get("debut") and str(x["debut"])[:19] > maint.isoformat()[:19])]
    if not l:
        return {"populaires": None, "liquider": None, "populaires_ids": [], "liquider_ids": []}
    vues = sorted(int(x["vues"]) for x in l if x.get("vues") is not None)
    med = statistics.median(vues) if len(vues) >= 3 else None
    def age(x):
        try:
            return (maint - datetime.fromisoformat(str(x.get("debut") or x.get("cree_le"))[:19].replace("Z", ""))).days
        except (TypeError, ValueError):
            return None
    def pop(x):
        w, v = int(x.get("watchers") or 0), x.get("vues")
        return w >= 2 or (v is not None and med is not None and v >= 30 and v >= 2 * med)
    pops = sorted((x for x in l if pop(x)), key=lambda x: (-(int(x.get("watchers") or 0)), -(int(x.get("vues") or 0))))
    def froid(x):
        a, v = age(x), x.get("vues")
        if a is None or a < 30 or int(x.get("watchers") or 0) > 0:
            return False
        return v is None or med is None or v < max(10, med / 2)
    liq = sorted((x for x in l if froid(x)), key=lambda x: -(age(x) or 0))
    return {"populaires": len(pops), "liquider": len(liq), "populaires_ids": [x["id"] for x in pops[:40]],
            "liquider_ids": [x["id"] for x in liq[:40]], "vues_mediane": med,
            "top": ({"id": pops[0]["id"], "joueur": pops[0].get("joueur"),
                     "watchers": int(pops[0].get("watchers") or 0), "vues": pops[0].get("vues")} if pops else None)}



def effacer_compte(cid):
    """3 nov 2026 (revue de securite) : TOUT ce qui part avec un compte, quel que soit le chemin (dans l'app, avis eBay) :
    l'abonnement Stripe annule, l'acces Apple retire, ses exemples d'entrainement, puis son dossier et ceux des anciens
    comptes relies qui renvoyaient vers lui (sinon une reconnexion les rouvrait)."""
    import comptes
    import paiements
    ix = {c: (comptes.info(c) or {}) for c in comptes.lister()}
    groupe = [cid] + [c for c in ix if c != cid and comptes.resoudre(c) == cid]
    for c in groupe:
        info = ix.get(c) or {}
        if info.get("stripe_abonnement"):        # 3 nov 2026 (revue) : meme impaye ou incomplet, on l'annule
            try:
                paiements._appel("DELETE", "subscriptions/" + str(info["stripe_abonnement"]))
            except Exception as e:
                try:
                    import admin
                    admin.noter_erreur("compte_supprimer stripe", e)
                except Exception:
                    pass
        if info.get("apple_rt"):                 # 27 oct 2026 : Sign in with Apple -> acces retire chez Apple aussi
            try:
                import auth_tiers
                auth_tiers.revoquer_apple(comptes.dechiffrer(info["apple_rt"]))
            except Exception as e:
                try:
                    import admin
                    admin.noter_erreur("compte_supprimer apple", e)
                except Exception:
                    pass
        try:                                       # 3 nov 2026 : ses exemples de la banque d'entrainement aussi
            import entrainement
            entrainement.retirer_compte(c)
        except Exception as e:
            print("Entrainement (compte supprime) : " + repr(e), flush=True)
        # 3 nov 2026 (revue de securite) : ce qu'il a laisse dans les fichiers partages (messages, vendeurs perso, votes)
        for nom, f in (("demandes", lambda: __import__("demandes").retirer_compte(c)),
                       ("vendeurs perso", lambda: __import__("deals").regler_vendeurs_perso(c, [])),
                       ("votes", lambda: __import__("cartes_match").retirer_votant(c))):
            try:
                f()
            except Exception as e:
                print(f"Compte supprime ({nom}) : " + repr(e), flush=True)
    for c in groupe[1:] + [cid]:
        comptes.supprimer(c)
    return groupe

AFFICHER_APRES_J = 90                  # 5 nov 2026 : en stock depuis plus de 3 mois -> « A mettre sur eBay »


RABAIS_ANNONCES = 0.10          # 8 nov 2026 : sans vente, le prix suggere = la mediane des annonces pareilles moins 10 %


class Api:
    def __init__(self, chemin_db=None):
        _API_REF[:] = [self]                 # 10 nov 2026 : ebay_prix_actif() sait si c'est l'admin
        self._chemin_fixe = chemin_db            # tests : base imposee
        with _verrou:
            _connecter(self.chemin_db).close()

    @property
    def chemin_db(self):
        return self._chemin_fixe or chemin_db_env()

    def _db(self):
        return _connecter(self.chemin_db)

    # -- reglages ------------------------------------------------------------------------
    def reglages_lire(self):
        r = dict(REGLAGES_DEFAUT)
        with _verrou:
            c = self._db()
            try:
                for k, v in c.execute("SELECT k, v FROM reglages"):
                    if k in REGLAGES_DEFAUT:
                        r[k] = json.loads(v)
                    elif k == "logo":                      # l'image reste a part (logo_lire) : juste sa version
                        r["logo_v"] = hashlib.md5(v.encode()).hexdigest()[:10]
            finally:
                c.close()
        r.setdefault("logo_v", "")
        # 30 oct 2026 : un modele jamais touche (ancien defaut 30 g, sans dimensions) prend le colis Expedited Lite
        m = r.get("modele_annonce")
        if isinstance(m, dict) and int(float(m.get("poids_g") or 0)) == 30 and not any(m.get(k) for k in ("longueur_cm", "largeur_cm", "hauteur_cm")):
            import annonces
            r["modele_annonce"] = {**m, "poids_g": annonces.LITE["poids_g"],
                                   **dict(zip(("longueur_cm", "largeur_cm", "hauteur_cm"), annonces.LITE["dims"]))}
        # 24 oct 2026 - heberge : la campagne eBay Partner Network est celle de SlabCoach (serveur), pour tous les clients
        epn = re.sub(r"\D", "", os.environ.get("LOCKERROOM_EPN_CAMPID") or "")
        if epn:
            r["epn_campid"] = epn
        return r

    # -- taux de change du jour (24 oct 2026) : Banque du Canada, garde 12 h ; repli 0,70 ---------------
    _TAUX = {"c": None, "lu": 0.0, "fond": False}

    @staticmethod
    def _taux_lire_bdc(chemin, ancien):
        try:
            import urllib.request
            req = urllib.request.Request("https://www.bankofcanada.ca/valet/observations/FXUSDCAD/json?recent=1",
                                         headers={"User-Agent": "SlabCoach"})
            with urllib.request.urlopen(req, timeout=8) as r:
                d = json.loads(r.read())
            obs = (d.get("observations") or [])[-1]
            usd_cad = float(obs["FXUSDCAD"]["v"])                    # 1 $ US = x $ CA
            c = {"usd": round(1 / usd_cad, 4), "date": obs.get("d"), "source": "Banque du Canada",
                 "lu": datetime.now().timestamp()}
        except Exception:
            # 4 nov 2026 (vitesse) : en panne, on garde l'ancien taux et on reessaie dans une heure (plus 8 s a chaque appel)
            c = dict(ancien or {"usd": 0.70, "date": None, "source": "approximatif"}, lu=datetime.now().timestamp() - 11 * 3600)
        try:
            tmp = chemin + ".%d.tmp" % os.getpid()
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(c, f)
            os.replace(tmp, chemin)
        except OSError:
            pass
        return c

    def taux_change(self):
        """{"usd": 0.70, "date": "2026-10-23", "source": "Banque du Canada"} : 1 $ CA = usd $ US.
        4 nov 2026 (vitesse) : garde en memoire ; perime -> l'ancien tout de suite et la Banque du Canada relue en fond."""
        import comptes
        T = Api._TAUX
        chemin = os.path.join(comptes.DONNEES, "taux_change.json")
        maint = datetime.now().timestamp()
        c = T["c"] if T["c"] and maint - T["lu"] < 300 else None
        if c is None:
            try:
                with open(chemin, encoding="utf-8") as f:
                    c = json.load(f)
            except (OSError, ValueError):
                c = None
            if c:
                T.update(c=c, lu=maint)
        if c and maint - float(c.get("lu", 0)) < 12 * 3600:
            return c
        if c:                                                         # perime : relu en fond, l'ancien en attendant
            if not T["fond"]:
                T["fond"] = True

                def fond():
                    try:
                        T.update(c=Api._taux_lire_bdc(chemin, c), lu=datetime.now().timestamp())
                    finally:
                        T["fond"] = False
                threading.Thread(target=fond, daemon=True).start()
            return c
        c = Api._taux_lire_bdc(chemin, None)
        T.update(c=c, lu=maint)
        return c

    # -- forfait et abonnement Pro (24 oct 2026, Stripe : voir paiements.py) --------------------
    def forfait(self):
        """Ce que voit le client : son forfait, ses photos du mois, le prix du Pro. Jamais une cle."""
        import comptes
        import paiements
        multi = bool(comptes.MULTI and comptes.courant())
        info = comptes.info(comptes.courant()) if multi else {}
        try:
            photos = vision.statut()
        except Exception:
            photos = {}
        try:
            prix = paiements.prix_affiche()
        except Exception:
            prix = None
        import forfaits
        import ventes_communaute
        adm_c = self._est_admin_compte()
        # 9 nov 2026 : un compte qui vient d'etre cree (30 min) : l'app demande s'il y en a deja un sur un autre appareil
        try:
            neuf = bool(multi and info.get("cree_le") and datetime.now() - datetime.fromisoformat(str(info["cree_le"])[:19]) < timedelta(minutes=30)
                        and not info.get("identites_reliees_vu"))
        except ValueError:
            neuf = False
        return {**forfaits.resume(), "multi": multi, "compte_neuf": neuf, "admin": self._est_admin(), "admin_reel": self._est_admin(reel=True), "vue": vue_simulee() or "admin", "comps": comps_permis(self), "admin_a_verifier": adm_c and not self._est_admin(),
                "admin_verif_active": adm_c and comptes.MULTI and self._admin_verif_possible(), "communaute": ventes_communaute.actif(),
                # 27 oct 2026 - revue legale : logos et photos de la LNH = marques et contenu de la LNH (conditions : usage
                # non commercial) -> coupes par defaut ; seulement avec une licence (LOCKERROOM_LOGOS_LNH=1)
                "logos_lnh": os.environ.get("LOCKERROOM_LOGOS_LNH") == "1",
                "username": info.get("username") if multi else None,           # 26 oct 2026 : « Bonjour ... » sur l'accueil
                "forfait": (info.get("forfait") or "gratuit") if multi else "pro",
                "statut": info.get("forfait_statut") or "", "fin": info.get("forfait_fin"),
                "annule": bool(info.get("forfait_annule")), "client": bool(info.get("stripe_client")),
                "paiements": paiements.actif(), "mode_paiement": paiements.mode(), "prix": prix,
                "photos_mois": photos.get("ce_mois"), "photos_limite": photos.get("limite"),
                "gratuit_photos": vision.QUOTA_GRATUIT, "ios": est_ios(), "demo": bool(info.get("demo")),
                "push": __import__("apns").actif(),
                # 26 oct 2026 (Mathieu : « bronze pour la version de base, gold pour Pro, eventuellement silver ») :
                # la couleur du logo et du badge ; « silver » est pret pour un futur forfait intermediaire
                "niveau": _niveau(forfaits.resume(), info)}

    # -- 26 oct 2026 : app iPhone ---------------------------------------------------------------------------------
    def push_enregistrer(self, jeton, plateforme="ios"):
        """Le jeton de notifications de cet iPhone (l'utilisateur a accepte), garde dans SON compte."""
        jeton = re.sub(r"[^0-9a-fA-F]", "", str(jeton or ""))[:200]
        if len(jeton) < 32:
            return {"ok": False, "erreur": "Jeton invalide"}
        with _verrou:
            c = self._db()
            try:
                c.execute("CREATE TABLE IF NOT EXISTS push_jetons (jeton TEXT PRIMARY KEY, plateforme TEXT, le TEXT)")
                c.execute("INSERT OR REPLACE INTO push_jetons VALUES (?,?,?)", (jeton, str(plateforme or "ios")[:10], _maintenant()))
                c.commit()
            finally:
                c.close()
        try:                                       # un iPhone ajoute depuis une session admin confirmee devient de confiance
            import comptes
            if comptes.MULTI and self._est_admin_compte() and self._admin_verifie():
                self._jetons_admin(ajouter=jeton)
        except Exception:
            pass
        return {"ok": True}

    def _push(self, titre, texte, donnees=None):
        """Envoie a tous les iPhone du compte courant ; oublie les jetons perimes."""
        import apns
        if not apns.actif():
            return 0
        with _verrou:
            c = self._db()
            try:
                c.execute("CREATE TABLE IF NOT EXISTS push_jetons (jeton TEXT PRIMARY KEY, plateforme TEXT, le TEXT)")
                jetons = [r[0] for r in c.execute("SELECT jeton FROM push_jetons")]
            finally:
                c.close()
        n, perimes = 0, []
        for j in jetons:
            r = apns.envoyer(j, titre, texte, donnees)
            n += r == "ok"
            if r == "perime":
                perimes.append(j)
        if perimes:
            with _verrou:
                c = self._db()
                try:
                    c.executemany("DELETE FROM push_jetons WHERE jeton=?", [(j,) for j in perimes])
                    c.commit()
                finally:
                    c.close()
        return n

    def compte_supprimer(self, confirmation=None):
        """Apple 5.1.1(v) : supprimer son compte DANS l'app. Annule l'abonnement Stripe, efface tout son dossier
        (base, jetons eBay chiffres, reglages) ; ses ventes partagees anonymement restent anonymes."""
        import comptes
        import paiements
        cid = comptes.courant() if comptes.MULTI else None
        if not cid:
            return {"ok": False, "erreur": "Rien à supprimer sur ce PC"}
        if str(confirmation or "").strip().upper() not in ("SUPPRIMER", "DELETE"):
            return {"ok": False, "erreur": "Écris SUPPRIMER pour confirmer"}
        effacer_compte(cid)
        return {"ok": True, "deconnecter": True}

    def abonnement_payer(self):
        import comptes
        import paiements
        cid = comptes.courant() if comptes.MULTI else None
        if est_ios():
            return {"ok": False, "erreur": "Non disponible dans l’app iPhone"}
        if not cid:
            return {"ok": False, "erreur": "Le forfait Pro se prend dans la version en ligne"}
        e = comptes.info(cid) or {}
        if e.get("forfait") == "pro" and (e.get("stripe_abonnement") or e.get("forfait_source") == "apple"):   # pas un 2e abonnement
            return {"ok": False, "erreur": "Ton forfait Pro est déjà actif : gère-le dans « Gérer mon abonnement »", "deja_pro": True}
        try:
            return {"ok": True, "url": paiements.creer_paiement(cid, e.get("stripe_client"))}
        except paiements.Erreur as e:
            return {"ok": False, "erreur": str(e)}

    def abonnement_gerer(self):
        import comptes
        import paiements
        cid = comptes.courant() if comptes.MULTI else None
        if est_ios():
            return {"ok": False, "erreur": "Non disponible dans l’app iPhone"}
        if cid and (comptes.info(cid) or {}).get("forfait_source") == "apple":
            return {"ok": False, "erreur": "Ton Pro est pris avec ton identifiant Apple : gère-le dans Réglages de l’iPhone › ton nom › Abonnements"}
        try:
            return {"ok": True, "url": paiements.portail((comptes.info(cid) or {}).get("stripe_client") if cid else None)}
        except paiements.Erreur as e:
            return {"ok": False, "erreur": str(e)}

    # -- 27 oct 2026 : verification d'un certificat PSA (voir psa.py), un a la fois, a la demande du vendeur ---------
    def psa_cert(self, cert):
        import psa
        return psa.verifier(cert)

    # -- 27 oct 2026 : achat integre Apple (voir achats_apple.py) -------------------------------------------------
    def apple_achat_info(self):
        """Pour l'app iPhone : le produit a acheter et le jeton (UUID) qui relie l'achat a CE compte."""
        import achats_apple
        import comptes
        import forfaits
        cid = comptes.courant() if comptes.MULTI else None
        if not cid:
            return {"ok": False, "erreur": "Connecte-toi pour prendre le Pro"}
        e = forfaits.etat()
        return {"ok": True, "produit": achats_apple.produit(), "jeton": achats_apple.jeton_compte(cid),
                "pro_ailleurs": bool(e.get("payant") and e.get("source") != "apple") or bool(e.get("offert")),
                "pro_apple": bool(e.get("payant") and e.get("source") == "apple")}

    def apple_achat_valider(self, jws):
        """Transaction signee par Apple (achat, renouvellement vu par l'app) -> forfait du compte."""
        import achats_apple
        import comptes
        import forfaits
        cid = comptes.courant() if comptes.MULTI else None
        if not cid:
            return {"ok": False, "erreur": "Connecte-toi pour prendre le Pro"}
        try:
            ch = achats_apple.valider(jws, cid, comptes)
        except achats_apple.Refus as e:
            return {"ok": False, "erreur": str(e)}
        return {"ok": True, "pro": ch["forfait"] == "pro", **forfaits.resume()}

    def apple_achats_restaurer(self, liste):
        """« Restaurer mes achats » : les transactions de l'identifiant Apple ; la plus recente valide gagne."""
        import achats_apple
        import comptes
        import forfaits
        cid = comptes.courant() if comptes.MULTI else None
        if not cid:
            return {"ok": False, "erreur": "Connecte-toi pour restaurer"}
        bons, erreur = [], None
        for jws in (liste or [])[:20]:
            try:
                tx = achats_apple.verifier_jws(jws)
                achats_apple.champs_transaction(tx)
                bons.append((tx.get("expiresDate") or 0, jws))
            except achats_apple.Refus as e:
                erreur = str(e)
        if not bons:
            return {"ok": False, "erreur": "Aucun abonnement SlabCoach Pro trouvé pour cet identifiant Apple" if not erreur or "autre" in erreur else erreur}
        try:
            ch = achats_apple.valider(max(bons)[1], cid, comptes)
        except achats_apple.Refus as e:
            return {"ok": False, "erreur": str(e)}
        return {"ok": True, "pro": ch["forfait"] == "pro", **forfaits.resume()}

    # -- logo de la boutique (23 oct 2026) : une petite image (data URL, reduite par l'ecran) ------
    def logo_lire(self):
        with _verrou:
            c = self._db()
            try:
                row = c.execute("SELECT v FROM reglages WHERE k='logo'").fetchone()
            finally:
                c.close()
        return {"logo": json.loads(row[0]) if row else None}

    def logo_sauver(self, data_url=None):
        """data URL PNG/JPEG/WebP de 400 Ko au plus ; None ou "" = retirer le logo."""
        with _verrou:
            c = self._db()
            try:
                if not data_url:
                    c.execute("DELETE FROM reglages WHERE k='logo'")
                else:
                    if len(data_url) > LOGO_MAX or not _RE_LOGO.match(data_url):
                        raise ValueError("Logo invalide : une image PNG ou JPEG de moins de 300 Ko")
                    c.execute("INSERT OR REPLACE INTO reglages VALUES ('logo', ?)", (json.dumps(data_url),))
                c.commit()
            finally:
                c.close()
        return self.reglages_lire()

    def reglages_sauver(self, nouveaux):
        if (nouveaux or {}).get("ia_entrainement_ok") is False and self.reglages_lire().get("ia_entrainement_ok"):
            try:                                   # 3 nov 2026 : le OUI retire -> ses exemples quittent la banque sur-le-champ
                import entrainement
                entrainement.retirer_moi()
            except Exception as e:
                print("Entrainement (retrait) : " + repr(e), flush=True)
        nouveaux = dict(nouveaux or {})
        if "frais_ebay_pct" in nouveaux and "frais_auto" not in nouveaux:
            try:                                   # 9 nov 2026 : un % change a la main -> l'ajustement automatique s'arrete
                if abs(float(nouveaux["frais_ebay_pct"]) - float(self.reglages_lire()["frais_ebay_pct"])) > 0.001:
                    nouveaux["frais_auto"] = False
            except (TypeError, ValueError):
                pass
        with _verrou:
            c = self._db()
            try:
                for k, v in (nouveaux or {}).items():
                    if k in REGLAGES_DEFAUT:
                        c.execute("INSERT OR REPLACE INTO reglages VALUES (?,?)", (k, json.dumps(v)))
                c.commit()
            finally:
                c.close()
        return self.reglages_lire()

    # -- sports (23 oct 2026) : devine, sinon le sport principal des Reglages ----------------
    def sport_de(self, d, defaut=None):
        d = d or {}
        defaut = defaut or self.reglages_lire().get("sport") or sports.DEFAUT
        bonus = {"hockey": 3} if d.get("joueur") and valeurs.connu(d.get("joueur")) else None
        return sports.detecter(d.get("titre"), d.get("equipe"), d.get("marque"), d.get("set_nom"), d.get("parallele"),
                               d.get("nom"), defaut=defaut, bonus=bonus)

    # -- « une photo, un bouton » (23 oct 2026) : voir vision.py ---------------------------------
    def photo_statut(self):
        import cardsight
        return {**vision.statut(), "cardsight": cardsight.actif()}

    def photo_identifier(self, photos):
        """1 ou 2 photos (devant, dos) -> fiche pre-remplie. Rien n'est enregistre : l'ecran montre
        la fiche (champs douteux en or) et l'utilisateur touche « Enregistrer »."""
        if not self.reglages_lire().get("ia_photos_ok"):      # 27 oct 2026 : rien ne part chez l'IA sans un OUI explicite
            return {"ok": False, "erreur": "Permission de lecture par l’IA requise", "consentement_requis": True}
        try:
            r = vision.identifier(photos if isinstance(photos, list) else [photos])
        except vision.Erreur as e:
            # 28 oct 2026 : l'admin voit la vraie raison (code et message d'Anthropic, sans la cle)
            return {"ok": False, "erreur": str(e), **({"detail": vision.derniere_erreur()} if self._est_admin() else {})}
        try:                                   # 28 oct 2026 : CardSight AI confirme les champs douteux (si CARDSIGHT_CLE)
            import cardsight
            if cardsight.actif() and not r.get("cache"):
                img = vision._decoder((photos if isinstance(photos, list) else [photos])[0])[0]
                r["champs"], r["a_verifier"], src = cardsight.completer(r["champs"], r.get("a_verifier"), img)
                if src:
                    r["complement"] = src
        except Exception as e:
            print("CardSight : " + repr(e), flush=True)
        ch = r["champs"]
        ch["sport"] = sports.valide(ch.get("sport")) if ch.get("sport") else self.sport_de(ch)
        if not ch.get("titre"):
            ch["titre"] = ebay_csv.titre_annonce(ch)
        return r

    def sports_liste(self):
        return {"sports": sports.liste(), "principal": self.reglages_lire().get("sport") or sports.DEFAUT}

    def equipes(self, sport=None):
        s = sports.valide(sport or self.reglages_lire().get("sport"))
        return [{"code": k, "nom": v[0], "division": v[1], "sport": s}
                for k, v in sorted(sports.equipes(s).items(), key=lambda kv: kv[1][0])]

    # -- produits et checklists --------------------------------------------------------------
    def produits_liste(self):
        with _verrou:
            c = self._db()
            try:
                out = _dicts(c.execute("SELECT p.*, (SELECT COUNT(*) FROM checklist k WHERE k.produit_id=p.id) AS nb_cartes "
                                       "FROM produits p ORDER BY p.id DESC"))
            finally:
                c.close()
        defaut = self.reglages_lire().get("sport") or sports.DEFAUT
        for p in out:
            p["par_boite"] = json.loads(p["par_boite"] or "{}")
            p["sport"] = p.get("sport") or sports.detecter(p.get("nom"), defaut=defaut)
        return out

    def produit_sauver(self, p):
        p = p or {}
        sport = sports.valide(p.get("sport")) if p.get("sport") else self.sport_de({"nom": p.get("nom")})
        vals = (p.get("nom") or "Nouveau produit", p.get("saison") or "", p.get("format") or "Boîte hobby",
                _float(p.get("cout_boite")) or 0.0, json.dumps(p.get("par_boite") or {}), sport)
        with _verrou:
            c = self._db()
            try:
                if p.get("id"):
                    c.execute("UPDATE produits SET nom=?, saison=?, format=?, cout_boite=?, par_boite=?, sport=? WHERE id=?", vals + (p["id"],))
                    pid = p["id"]
                else:
                    pid = c.execute("INSERT INTO produits (nom, saison, format, cout_boite, par_boite, sport, cree_le) VALUES (?,?,?,?,?,?,?)",
                                    vals + (_maintenant(),)).lastrowid
                c.commit()
            finally:
                c.close()
        return {"ok": True, "id": pid}

    def produit_supprimer(self, pid):
        with _verrou:
            c = self._db()
            try:
                c.execute("DELETE FROM checklist WHERE produit_id=?", (pid,))
                c.execute("DELETE FROM produits WHERE id=?", (pid,))
                c.commit()
            finally:
                c.close()
        return {"ok": True}

    def checklist(self, pid):
        with _verrou:
            c = self._db()
            try:
                return _dicts(c.execute("SELECT * FROM checklist WHERE produit_id=? ORDER BY id", (pid,)))
            finally:
                c.close()

    def checklist_importer(self, pid, texte, remplacer=True):
        """CSV ou texte colle (virgule, point-virgule ou tabulation). Colonnes
        reconnues : numero/#, joueur/player, equipe/team, categorie/set/insert,
        tirage/serial (/99), recrue/rookie, auto, relique/memorabilia."""
        texte = (texte or "").strip()
        if not texte:
            return {"ok": False, "erreur": "Rien à importer"}
        sep = max([",", ";", "\t"], key=lambda s: texte.splitlines()[0].count(s))
        lecteur = csv.reader(io.StringIO(texte), delimiter=sep)
        lignes = [l for l in lecteur if any(x.strip() for x in l)]
        entete = [re.sub(r"[^a-z#/]", "", calcul._sans_accents(h)) for h in lignes[0]]

        def col(*noms):
            for i, h in enumerate(entete):
                if any(h == n or h.startswith(n) for n in noms):
                    return i
            return None
        i_num, i_j, i_e = col("#", "numero", "no", "card", "carte"), col("joueur", "player", "nom", "name"), col("equipe", "team")
        i_cat, i_t = col("categorie", "set", "insert", "subset", "type"), col("tirage", "serial", "/", "numbered", "print")
        i_r, i_a, i_rel = col("recrue", "rookie", "rc"), col("auto"), col("relique", "memorabilia", "relic", "patch", "jersey")
        if i_j is None:
            return {"ok": False, "erreur": "Colonne « joueur » (ou « player ») introuvable dans la 1re ligne"}
        rangs = []
        for l in lignes[1:]:
            g = lambda i: (l[i].strip() if i is not None and i < len(l) else "")
            if not g(i_j):
                continue
            cat = g(i_cat)
            tirage = _int(g(i_t)) if g(i_t) else None
            m = re.search(r"/\s*(\d{1,4})\b", cat)
            if not tirage and m:
                tirage = int(m.group(1))
            rangs.append((pid, g(i_num), g(i_j), g(i_e), cat or "Base", tirage,
                          _bool(g(i_r)) or int(bool(re.search(r"young guns|rookie|recrue", cat, re.I))),
                          _bool(g(i_a)) or int(bool(re.search(r"\bauto", cat, re.I))),
                          _bool(g(i_rel)) or int(bool(re.search(r"jersey|patch|relic|memorabilia", cat, re.I)))))
        with _verrou:
            c = self._db()
            try:
                if remplacer:
                    c.execute("DELETE FROM checklist WHERE produit_id=?", (pid,))
                c.executemany("INSERT INTO checklist (produit_id, numero, joueur, equipe, categorie, tirage, recrue, auto, relique) "
                              "VALUES (?,?,?,?,?,?,?,?,?)", rangs)
                c.commit()
            finally:
                c.close()
        return {"ok": True, "nb": len(rangs)}

    def etoiles_lire(self, pid):
        with _verrou:
            c = self._db()
            try:
                joueurs = [r[0] for r in c.execute("SELECT DISTINCT joueur FROM checklist WHERE produit_id=? ORDER BY joueur", (pid,))]
                e = {r[0]: r[1] for r in c.execute("SELECT joueur, etoiles FROM etoiles")}
            finally:
                c.close()
        return [{"joueur": j, "etoiles": e.get(j, 3)} for j in joueurs]

    def etoiles_sauver(self, valeurs):
        with _verrou:
            c = self._db()
            try:
                for j, n in (valeurs or {}).items():
                    c.execute("INSERT OR REPLACE INTO etoiles VALUES (?,?)", (j, max(1, min(5, int(n)))))
                c.commit()
            finally:
                c.close()
        return {"ok": True}

    # -- calculateur ------------------------------------------------------------------------
    def calculer_prix(self, params):
        p = params or {}
        r = self.reglages_lire()
        prod = next((x for x in self.produits_liste() if x["id"] == p.get("produit_id")), None)
        if not prod:
            return {"ok": False, "erreur": "Choisis un produit"}
        ck = self.checklist(prod["id"])
        if not ck:
            return {"ok": False, "erreur": "Ce produit n'a pas encore de checklist : importe-la d'abord"}
        etoiles = {x["joueur"]: x["etoiles"] for x in self.etoiles_lire(prod["id"])}
        res = calcul.prix_places(
            ck, boites=_float(p.get("boites")) or 1, cout_boite=_float(p.get("cout_boite")) or prod["cout_boite"] or 0,
            marge=(_float(p.get("marge")) if p.get("marge") not in (None, "") else r["marge_break"]) / 100,
            frais_pct=(_float(p.get("frais_pct")) if p.get("frais_pct") not in (None, "") else r["frais_break_pct"]) / 100,
            frais_fixe=_float(p.get("frais_fixe")) if p.get("frais_fixe") not in (None, "") else r["frais_break_fixe"],
            mode=p.get("mode") or "equipes", par_boite=prod["par_boite"], etoiles=etoiles,
            plancher=_float(p.get("plancher")) if p.get("plancher") not in (None, "") else r["plancher_place"],
            arrondi=_float(p.get("arrondi")) or r["arrondi_place"], sport=prod.get("sport"))
        res.update(ok=True, produit=prod)
        return res

    def equipes_lnh(self):
        return [{"code": k, "nom": v[0], "division": v[1]} for k, v in sorted(calcul.EQUIPES_LNH.items(), key=lambda kv: kv[1][0])]

    # -- catalogue (cle en main) -------------------------------------------------------------
    _EV_CACHE = {}

    def catalogue_liste(self):
        """Produits du catalogue + valeur attendue par boite (algo SlabCoach)."""
        ajouts = catalogue.dossier_ajouts()
        cle = (valeurs.statut().get("maj"), tuple(sorted(os.listdir(catalogue.DOSSIER))) if os.path.isdir(catalogue.DOSSIER) else (),
               tuple(sorted((f, os.path.getmtime(os.path.join(ajouts, f))) for f in os.listdir(ajouts))) if os.path.isdir(ajouts) else ())
        try:
            cle = cle + (os.path.getmtime(valeur_produit._chemin()),)
        except OSError:
            pass
        if getattr(self, "_EV_CLE", None) != cle:                  # 4 nov 2026 : les anciennes cles ne s'empilent plus
            Api._EV_CLE = cle
            self._EV_CACHE.clear()
        out = []
        for p in catalogue.liste():
            k = (cle, p["id"])
            ev = self._EV_CACHE.get(k)                 # 4 nov 2026 : lu une fois (un autre fil peut vider le cache entre-temps)
            if ev is None:
                ev = calcul.prix_catalogue(catalogue.charger(p["id"]), boites=1)["ev_par_boite"]
                self._EV_CACHE[k] = ev
            boite = valeur_produit.de(p["id"]).get("boite")       # 26 oct 2026 : vaut-il la peine d'ouvrir ?
            out.append(dict(p, ev_par_boite=ev, prix_boite=boite, ouvrir=marche.verdict_ouvrir(ev, boite)))
        return {"produits": out, "valeurs": valeurs.statut()}

    # -- 24 oct 2026 : checklists Excel de Beckett (telechargees par l'utilisateur, deposees dans l'app) -----------
    # -- 25 oct 2026 : la console admin (abonnes, sante, catalogue, demandes) ------------------------------
    def deals_vendeurs(self, liste=None):
        """29 oct 2026 - admin : les vendeurs eBay suivis par le chasseur de deals (pseudos exacts). Sans liste : la lire."""
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        import deals as _d
        if liste is not None:
            if isinstance(liste, str):
                liste = re.split(r"[\s,;]+", liste)
            return {"ok": True, "vendeurs": _d.regler_vendeurs(liste)}
        return {"ok": True, "vendeurs": _d.vendeurs_suivis()}

    def deals_vendeurs_liste(self):
        """30 oct 2026 - pour tous : les gros vendeurs suivis (prioritaires d'abord) et ceux ou l'utilisateur ramasse."""
        import deals as _d
        vs = sorted(_d.vendeurs_suivis(), key=lambda v: _d.rang_vendeur(v))
        return {"ok": True, "vendeurs": vs, "ramassage": sorted(self._chez_ramassage())}

    def deals_ramassage(self, liste):
        """Les vendeurs ou l'utilisateur ramasse sur place : le port ne compte pas dans ses deals."""
        l = [re.sub(r"[^A-Za-z0-9._-]", "", str(v))[:64].lower() for v in (liste or [])][:40]
        self.reglages_sauver({"ramassage": [v for v in l if v]})
        return self.deals_vendeurs_liste()

    PROFIL_COLL = ("recrues", "veterans", "legendes", "hits", "gradees")

    def deals_profil_lire(self):
        import deals as _d
        import comptes
        import forfaits
        p = self.reglages_lire().get("deals_profil")
        p = p if isinstance(p, dict) else {}
        perso = ((_d.lire_vite().get("vendeurs_perso") or {}).get(str(comptes.courant() if comptes.MULTI else "local")) or [])
        return {"ok": True, "collectionne": [x for x in p.get("collectionne") or [] if x in self.PROFIL_COLL],
                "favoris": p.get("favoris") or [], "prix_min": p.get("prix_min"), "prix_max": p.get("prix_max"),
                "vendeurs": perso, "pro": forfaits.est_pro(), "vendeurs_max": _d.VENDEURS_PERSO_MAX,
                "favoris_max": self.FAVORIS_MAX_PRO if forfaits.est_pro() else self.FAVORIS_MAX,
                "favoris_max_pro": self.FAVORIS_MAX_PRO}

    FAVORIS_MAX = 5                       # 9 nov 2026 (Mathieu : « max de 5 en non pro et 20 en pro »)
    FAVORIS_MAX_PRO = 20

    def deals_profil_regler(self, d):
        import deals as _d
        import comptes
        import forfaits
        d = d or {}
        fav = d.get("favoris")
        if isinstance(fav, str):
            fav = re.split(r"[,;\n]+", fav)
        fav = list(dict.fromkeys(re.sub(r"\s+", " ", str(x)).strip()[:40] for x in (fav or []) if str(x).strip()))
        # 31 oct 2026 (Mathieu : « 3 pour le compte gratuit et au moins 10 pour les payants ») : mes joueurs suivis
        fmax = self.FAVORIS_MAX_PRO if forfaits.est_pro() else self.FAVORIS_MAX
        coupes = fav[fmax:]
        fav = fav[:fmax]
        p = {"collectionne": [x for x in d.get("collectionne") or [] if x in self.PROFIL_COLL], "favoris": fav,
             "prix_min": _float(d.get("prix_min")) or None, "prix_max": _float(d.get("prix_max")) or None}
        if p["prix_min"] and p["prix_max"] and p["prix_min"] > p["prix_max"]:
            p["prix_min"], p["prix_max"] = p["prix_max"], p["prix_min"]
        self.reglages_sauver({"deals_profil": p})
        if coupes:
            return {**self.deals_profil_lire(), "ok": False, "pro_requis": not forfaits.est_pro(),
                    "erreur": (f"{fmax} joueurs suivis au plus" + (f" ({self.FAVORIS_MAX_PRO} avec Pro)" if not forfaits.est_pro() else "")
                               + " : " + ", ".join(coupes) + " pas ajouté" + ("s" if len(coupes) > 1 else ""))}
        if "vendeurs" in d:
            v = d.get("vendeurs")
            if isinstance(v, str):
                v = re.split(r"[\s,;]+", v)
            if v and not forfaits.est_pro():
                return {**self.deals_profil_lire(), "ok": False, "erreur": "Tes vendeurs à toi font partie de Pro", "pro_requis": True}
            _d.regler_vendeurs_perso(comptes.courant() if comptes.MULTI else "local", v or [])
        return self.deals_profil_lire()

    def _profil_deals(self):
        """Le profil de deals du compte, pret a appliquer (None = rien de regle)."""
        p = self.reglages_lire().get("deals_profil")
        if not isinstance(p, dict) or not any(p.get(k) for k in ("collectionne", "favoris", "prix_min", "prix_max")):
            return None
        return p

    @staticmethod
    def _norm_fav(t):
        t = unicodedata.normalize("NFKD", str(t or "").lower())
        return " " + re.sub(r"[^a-z0-9]+", " ", "".join(c for c in t if not unicodedata.combining(c))).strip() + " "

    def _appliquer_profil(self, lst, p):
        """Ce que je collectionne (filtre), mon budget par carte (filtre), mes favoris (devant, avec une etoile)."""
        if not p:
            return lst
        import cartes_match
        import deals as _d
        coll = set(p.get("collectionne") or [])
        epoques, sortes = coll & {"recrues", "veterans", "legendes"}, coll & {"hits", "gradees"}
        pmin, pmax = p.get("prix_min"), p.get("prix_max")
        favs = [self._norm_fav(f) for f in p.get("favoris") or [] if len(str(f).strip()) >= 3]
        out = []
        for x in lst:
            t = x.get("titre") or ""
            if pmin and (x.get("total") or 0) < pmin or pmax and (x.get("total") or 0) > pmax:
                continue
            if coll:
                c = cartes_match._decoder_memo(t)
                an = c.get("annee")
                ep = "recrues" if _d.est_recrue(t) else ("legendes" if an and int(an) < 1995 else "veterans")
                if epoques and ep not in epoques:
                    continue
                if sortes:
                    hit = bool(c.get("auto") or c.get("patch") or (c.get("serie") is not None and int(c.get("serie")) <= 99))
                    if not (("hits" in sortes and hit) or ("gradees" in sortes and c.get("grade"))):
                        continue
            if favs:
                n = self._norm_fav(t + " " + str(x.get("joueur") or ""))
                if any(f in n for f in favs):
                    x = dict(x, favori=True)
            out.append(x)
        if favs:
            out = [x for x in out if x.get("favori")] + [x for x in out if not x.get("favori")]
        return out

    def _joueurs_a_moi(self):
        """Les joueurs de MON inventaire (normalises), pour mettre leurs deals un peu plus haut."""
        try:
            c = self._db()
            try:
                l = [r[0] for r in c.execute("SELECT DISTINCT joueur FROM cartes WHERE joueur IS NOT NULL AND joueur != '' LIMIT 300")]
            finally:
                c.close()
        except Exception:
            return []
        return [self._norm_fav(j) for j in l if len(str(j).strip()) >= 4]

    def _varier_deals(self, lst, bloc=6):
        """9 nov 2026 (Mathieu : « adapter les deals aux preferences, pour que tout le monde n'ait pas les memes cartes, les
        memes deals ») : l'ordre du « meilleur deal » reste le meme a grands traits (favoris d'abord, puis par paquets de
        qualite semblable), mais DANS chaque paquet de 6, l'ordre change d'un compte a l'autre (et d'un jour a l'autre) :
        deux personnes ne voient pas les memes deals en tete au meme moment. Les joueurs de mon inventaire montent en tete
        de leur paquet (x["a_moi"]). Les groupes (recrue ou non, de mon pays ou non, gros vendeur ou non) ne se melangent pas."""
        import comptes
        import deals as _d
        if len(lst) < 3:
            return lst
        cle = f"{comptes.courant() if comptes.MULTI else 'local'}|{datetime.now():%Y-%m-%d}"
        mes = self._joueurs_a_moi()
        h = lambda x: hashlib.sha256(f"{cle}|{x.get('item_id') or x.get('titre')}".encode()).hexdigest()
        for i, x in enumerate(lst):
            if mes and not x.get("favori"):
                n = self._norm_fav(str(x.get("titre") or "") + " " + str(x.get("joueur") or ""))
                if any(j in n for j in mes):
                    lst[i] = dict(x, a_moi=True)
        favs = [x for x in lst if x.get("favori")]
        reste = [x for x in lst if not x.get("favori")]
        groupe = lambda x: (bool(x.get("recrue")), bool(x.get("etranger")), _d.rang_honnete(x) == 3, bool(x.get("encan")))
        out, run = [], []
        def vider():
            for k in range(0, len(run), bloc):
                out.extend(sorted(run[k:k + bloc], key=lambda x: (not x.get("a_moi"), h(x))))
            run.clear()
        for x in reste:
            if run and groupe(run[-1]) != groupe(x):
                vider()
            run.append(x)
        vider()
        return favs + out

    def deals_recharger(self):
        """28 oct 2026 - admin : un tour du chasseur de deals tout de suite."""
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        import deals as _d
        return {**_d.recharger(), "etat": self.deals_etat()}

    def deals_chasser_vedettes(self):
        """29 oct 2026 - admin : un tour seulement pour les veterans, les legendes et les jeunes de 2e a 4e annee."""
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        import deals as _d
        return {**_d.chasser_vedettes(), "etat": self.deals_etat()}

    def deals_tour(self):
        """29 oct 2026 - admin : ou en est le chasseur (leger : l'ecran Deals le demande a chaque ouverture)."""
        if not self._est_admin():
            return {"ok": False}
        import deals as _d
        return {"ok": True, **_d.tour()}

    def deals_tester_vendeurs(self):
        """29 oct 2026 - admin : ce qu'eBay renvoie maintenant pour chaque vendeur suivi, et pourquoi un encan est garde."""
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        import deals as _d
        return _d.tester_vendeurs()

    def deals_etat(self):
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        import deals as _d
        # 28 oct 2026 : la reconnaissance photo aussi (modele utilise, derniere erreur d'Anthropic sans la cle)
        return {**_d.etat(), "vision_modele": vision._MODELE_OK["m"] or vision.MODELE, "vision_erreur": vision.derniere_erreur()}

    def admin_resume(self):
        """Tout ce que la console affiche au premier coup d'oeil."""
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        import admin
        import demandes
        import nouveaux_produits
        a = admin.abonnes()
        dm = demandes.liste("ouvertes")
        s = admin.sante()
        return {"ok": True, "abonnes": {k: v for k, v in a.items() if k != "comptes"},
                "demandes": {"ouvertes": dm["ouvertes"], "nouvelles": dm["nouvelles"]},
                "a_ajouter": len(nouveaux_produits.liste()), "erreurs_24h": sum(1 for e in s["erreurs"] if str(e["le"]) > (datetime.now() - timedelta(days=1)).isoformat()),
                "ebay": s["ebay"], "version": s["version"], "vendues": vendues.statut(), "photos": s.get("photos"),
                "taches": s.get("taches"), "disque": s.get("disque"), "veille": self._veille_resume(),
                "demande_legale": self._demande_legale_statut(), "banc": self._banc_resume()}

    @staticmethod
    def _banc_resume():
        try:
            import banc
            return banc.resume()
        except Exception as e:
            return {"erreur": str(e)[:120]}

    def admin_banc_lancer(self):
        """10 nov 2026 : relancer le banc de validation tout de suite (admin)."""
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        import banc
        banc._ETAT["le"] = 0.0
        if banc._ETAT["en_cours"]:
            return {"ok": True, "deja": True}
        d = banc.lire()
        if d.get("dernier"):
            d = dict(d)
            d["dernier"] = dict(d["dernier"], le="")       # force une nouvelle passe aujourd'hui
            banc._ecrire(d)
        return {"ok": True, "lance": banc.passe_si_besoin()}

    @staticmethod
    def _demande_legale_statut():
        try:
            import demande_legale
            return demande_legale.statut()
        except Exception as e:
            return {"erreur": str(e)[:120]}

    @staticmethod
    def _veille_resume():
        try:
            import veille_ebay
            return veille_ebay.resume()
        except Exception as e:
            return {"erreur": str(e)[:120]}

    def veille_ebay_maintenant(self):
        """Admin : refaire la veille eBay tout de suite (frais, regles, douanes)."""
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        import veille_ebay
        r = veille_ebay.rafraichir()
        return dict(r, veille=veille_ebay.resume())

    def deals_pourquoi(self, lien, titre=None, prix=None):
        """8 nov 2026 (Mathieu : « on aurait du capter ca », une Martone Young Guns vendue 28 $) : POURQUOI une annonce n'est
        pas sortie dans les deals, etape par etape (admin). lien = lien ou numero eBay ; une annonce terminee ne se relit plus
        chez eBay : son titre et son prix suffisent (titre, prix). Ventes : le cache, sinon UNE recherche (geste de l'admin).
        -> {ok, etapes: [{ok, quoi, detail}], verdict}"""
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        import cartes_match
        import deals as _d
        import re as _re
        et = []
        add = lambda ok, quoi, det="": et.append({"ok": ok, "quoi": quoi, "detail": det})
        m = _re.search(r"(?<!\d)(\d{9,15})(?!\d)", str(lien or ""))
        a = None
        if m:
            try:
                a = ebay_compte.article(m.group(1), fond=False, frais=True)
            except Exception as e:
                add(None, "Annonce eBay", "pas relue (" + str(e)[:80] + ") : terminée ? Le titre et le prix tapés servent")
        if a is None:
            if not titre:
                return {"ok": False, "erreur": "Annonce terminée ou introuvable : entre aussi son titre et son prix"}
            a = {"titre": titre, "prix_cad": _float(prix) or 0, "port_cad": None, "encan": True, "item_id": m.group(1) if m else ""}
        t = a.get("titre") or ""
        total = _d._total(a)
        maint = datetime.now(timezone.utc)
        if a.get("vendeur") is not None and a.get("fin"):
            add(True, "Annonce", f"{'encan' if a.get('encan') else 'prix fixe'} · {a.get('mises') or 0} mise(s) · {round(total or 0, 2)} $ port compris · vendeur {a.get('vendeur')} ({a.get('vendeur_score')})")
            if a.get("encan"):
                ok = _d.encan_admis(a, maint)
                add(ok, "Fenêtre des encans", "dans la fenêtre (24 h et au moins 1 mise ; 5 j chez Savage, Remi, CF31)" if ok else
                    "hors fenêtre : finie, plus de 24 h avant la fin, ou aucune mise")
            pm = _d.petit_ou_moyen(a)
            add(pm, "Balayage des petits vendeurs", "petit ou moyen vendeur : balayé" if pm else "très gros vendeur : pas dans le balayage (seulement les recherches de cartes)")
            if a.get("encan") and total:
                add(None, "Couverture", ("encans hockey de " + str(_d.BALAYAGE_PRIX_MIN) + " $ et plus : couverts sur 24 h") if total >= _d.BALAYAGE_PRIX_MIN
                    else "mise sous " + str(_d.BALAYAGE_PRIX_MIN) + " $ : vue seulement dans les dernières heures (les milliers d'encans à 1 $ passent avant)")
            if _d.vendeur_risque(a):
                add(False, "Vendeur", "écarté : vendeur à risque (peu d'évaluations ou trop de négatives)")
        cib = cartes_match.cible_titre(t)
        if cib.get("exclu") or not cib.get("joueur"):
            add(False, "Carte reconnue", "lot ou joueur non reconnu dans le titre")
            return {"ok": True, "etapes": et, "verdict": "Pas jugée : le titre ne dit pas assez quelle carte c'est.", "titre": t}
        add(not cartes_match.abimee(t), "Carte reconnue", f"{cib.get('joueur')} · recherche « {cartes_match.requete_ebay(cib)} »" + (" · ABÎMÉE : écartée" if cartes_match.abimee(t) else ""))
        ventes = []
        try:
            vs = vendues.memes(t, requete=False, fond=False)
            ventes = [v for v in vs.get("ventes") or [] if v.get("prix")]
            if vs.get("erreur"):
                add(None, "Ventes (SoldComps)", str(vs["erreur"]))
        except Exception as e:
            add(None, "Ventes (SoldComps)", str(e)[:100])
        try:
            cand = _d.bassin_partage().candidats(cib)
        except Exception:
            cand = []
        va = _d.valeur_ou_saison(a, ventes + cand, [], cib=cib)
        memes = _d.memes_ventes(cib, ventes + cand)
        if not va:
            add(False, "Valeur", f"aucune valeur sûre : {len(memes)} vente(s) de la même carte (il en faut 3, ou 2 pour un hit ancien)")
            return {"ok": True, "etapes": et, "verdict": "Pas un deal : pas assez de ventes de cette carte pour une valeur sûre.", "titre": t}
        v, src, n = va[0], va[1], va[2]
        add(True, "Valeur", f"{round(v)} $ · {n} vente(s) · source {src}")
        tx = _d.taxe_de(a)
        pmx = _d.prix_max(v, taxe=tx)
        port = a.get("port_cad")
        mise_max = round(pmx - _d.port_eff(port), 2)
        mise = round((total or 0) - (port or 0), 2)
        okp = bool(total) and total <= pmx
        add(okp, "Prix", f"{'mise' if a.get('encan') else 'prix'} {mise} $ · mise max {mise_max} $ (30 % et 15 $ de profit au moins, taxes {round(tx * 100)} % et port compris)")
        verdict = ("C'est un deal à ce prix : il aurait dû sortir si l'annonce était dans la fenêtre et balayée." if okp
                   else f"Pas un deal à ce prix : il fallait {mise_max} $ ou moins (la carte vaut environ {round(v)} $).")
        return {"ok": True, "etapes": et, "verdict": verdict, "titre": t, "valeur": v, "mise_max": mise_max}

    def admin_abonnes(self):
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        import admin
        return {"ok": True, **admin.abonnes()}

    def admin_offrir_pro(self, cid, jours=None):
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        import admin
        return admin.offrir_pro(str(cid), None if jours is None else int(_float(jours) or 0))

    def admin_prolonger_essai(self, cid, jours=7):
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        import admin
        return admin.prolonger_essai(str(cid), int(_float(jours) or 7))

    def admin_entrainement(self):
        """3 nov 2026 : la banque d'entrainement de l'analyseur (combien d'exemples, avec vraie note, sous-notes, gros plans)."""
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        import entrainement
        return {"ok": True, **entrainement.stats(), "export": "/admin/entrainement.zip"}

    def admin_reference_ajouter(self, d):
        """3 nov 2026 : une carte gradee de reference (photos, note, defaut connu) dans la banque d'entrainement."""
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        import entrainement
        r = entrainement.ajouter_reference(d or {})
        return {**r, **({"stats": entrainement.stats()} if r.get("ok") else {})}

    def admin_sante(self):
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        import admin
        return {"ok": True, **admin.sante()}

    def admin_catalogue(self):
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        import admin
        return {"ok": True, **admin.catalogue_etat()}

    def admin_contributions(self):
        """31 oct 2026 : les checklists des utilisateurs en attente (la validation automatique a trouve quelque chose)."""
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        import comptes
        import contributions
        l = contributions.liste_attente()
        for x in l:
            e = comptes.info(x.get("compte")) or {} if comptes.MULTI else {}
            x["par"] = e.get("ebay_username") or e.get("username") or None
        return {"ok": True, "attente": l}

    def admin_contribution(self, pid, action):
        """action : publier | refuser (en attente) | retirer (publie par un utilisateur). Rien n'est efface."""
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        import contributions
        f = {"publier": contributions.publier, "refuser": contributions.refuser, "retirer": contributions.retirer}.get(str(action))
        if not f:
            return {"ok": False, "erreur": "Action inconnue"}
        r = f(pid)
        self._EV_CACHE.clear()
        return r

    def admin_remettre(self, cle):
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        import admin
        return admin.remettre(str(cle or ""))

    def activite_page(self, page):
        """9 nov 2026 : l'app dit quel ecran est ouvert (la route seulement), pour le tableau d'activite de l'admin."""
        try:
            import activite
            import comptes
            activite.noter_page(page, comptes.courant())
        except Exception:
            pass
        return {"ok": True}

    def admin_activite(self, jours=30):
        """9 nov 2026 (Mathieu : « un statsboard : l'activite, les pages les plus utilisees, les fonctions les moins
        utilisees, tous les commentaires regroupes par categorie, ce qui est a faire »)."""
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        import activite
        import admin
        import demandes
        try:
            jours = max(1, min(90, int(jours or 30)))
        except (TypeError, ValueError):
            jours = 30
        fonctions = [n for n in dir(type(self)) if not n.startswith("_") and callable(getattr(type(self), n, None))]
        act = activite.resume(jours, fonctions)
        a = admin.abonnes()
        # les commentaires (demandes), regroupes par categorie de l'agent, avec ce qui est a faire
        items = demandes.lire().get("items") or []
        lim = (datetime.now() - timedelta(days=jours)).isoformat()
        cats = {}
        for x in items:
            if str(x.get("le") or "") < lim:
                continue
            ia = x.get("ia") or {}
            c = ia.get("categorie") or "a_trier"
            g = cats.setdefault(c, {"categorie": c, "n": 0, "ouvertes": 0, "a_faire": []})
            g["n"] += 1
            if x.get("statut") in ("nouveau", "en_cours"):
                g["ouvertes"] += 1
                if ia.get("a_faire") and not ia.get("pareil_que"):
                    g["a_faire"].append({"id": x["id"], "priorite": ia.get("priorite") or 3, "resume": ia.get("resume") or str(x.get("texte") or "")[:120],
                                         "a_faire": ia.get("a_faire"), "le": x.get("le")})
        for g in cats.values():
            g["a_faire"].sort(key=lambda y: (y["priorite"], str(y["le"])))
            g["a_faire"] = g["a_faire"][:12]
        return {"ok": True, **act, "abonnes": {k: v for k, v in a.items() if k != "comptes"},
                "commentaires": sorted(cats.values(), key=lambda g: (-g["ouvertes"], -g["n"]))}

    def admin_demandes(self, statut="ouvertes"):
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        import demandes
        import vision
        return {"ok": True, "agent": vision.disponible(), **demandes.liste(statut or None)}

    def admin_repondre(self, did, texte=None, statut=None):
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        import demandes
        return demandes.repondre(str(did), texte, statut)

    def admin_trier(self, did):
        """Relance l'agent sur une demande (apres une panne, ou pour un nouveau brouillon)."""
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        import demandes
        ia = demandes.trier(str(did))
        return {"ok": bool(ia), "ia": ia, **({} if ia else {"erreur": "L'agent n'a pas répondu (clé Anthropic absente ou budget du mois atteint)"})}

    def admin_brief(self):
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        import demandes
        return {"ok": True, "texte": demandes.brief()}

    # -- demandes des utilisateurs (tous les comptes) --
    def demande_envoyer(self, d):
        import comptes
        import demandes
        d = d or {}
        cid = comptes.courant() if comptes.MULTI else "local"
        info = comptes.info(cid) if comptes.MULTI else {}
        return demandes.envoyer(d.get("type"), d.get("texte"), cid, (info or {}).get("username"),
                                d.get("langue") or self.reglages_lire().get("langue") or "fr", d.get("page"))

    def demandes_reponses(self):
        import comptes
        import demandes
        return demandes.mes_reponses(comptes.courant() if comptes.MULTI else "local")

    def demande_lue(self, did):
        import comptes
        import demandes
        return demandes.marquer_lu(comptes.courant() if comptes.MULTI else "local", str(did))

    # -- 24 oct 2026 : ne manquer aucun nouveau produit (eBay chaque semaine + demandes des utilisateurs) --------
    def produits_a_ajouter(self):
        import nouveaux_produits
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        d = nouveaux_produits.lire()
        return {"ok": True, "produits": nouveaux_produits.liste(), "maj": d.get("maj")}

    def produits_detecter(self):
        import nouveaux_produits
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        return nouveaux_produits.detecter()

    def produit_ignorer(self, cle):
        import nouveaux_produits
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        return nouveaux_produits.ignorer(str(cle or ""))

    def produit_demander(self, nom, sport=None):
        import comptes
        import nouveaux_produits
        return nouveaux_produits.demander(nom, sport or self.reglages_lire().get("sport"), comptes.courant() if comptes.MULTI else "local")

    def admin_vue(self, vue=None):
        """10 nov 2026 : l'admin choisit sa vue : « admin » (la sienne), « pro » ou « gratuit » (comme un utilisateur).
        Seul le VRAI admin peut changer ; la vue simulee ne donne jamais plus que ce qu'un utilisateur a."""
        if not self._est_admin(reel=True):
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        try:
            from flask import has_request_context, session
            if vue is not None and has_request_context():
                if vue in ("pro", "gratuit"):
                    session["vue_admin"] = vue
                else:
                    session.pop("vue_admin", None)
        except Exception:
            pass
        return {"ok": True, "vue": vue_simulee() or "admin"}

    def _est_admin(self, reel=False):
        if not reel and vue_simulee() and self._est_admin0():
            return False                         # 10 nov 2026 : l'admin regarde l'app comme un utilisateur
        return self._est_admin0()

    def _est_admin0(self):
        """L'admin, pour de vrai : un compte admin (_est_admin_compte) ET, en ligne, la 2e verification de CETTE session.
        8 nov 2026 (Mathieu : « ultra securise », « oui pour la validation cell ») : un compte admin vole (temoin de session
        copie, telephone emprunte...) n'ouvre pas la console : il faut le code envoye sur l'iPhone de l'admin (ou le code
        de secours LOCKERROOM_ADMIN_CODE de Render). Sans iPhone relie ni code de secours, la verification ne peut pas
        avoir lieu : l'admin garde l'acces (jamais bloque dehors) et la console lui demande d'en activer une."""
        if not self._est_admin_compte():
            return False
        import comptes
        if not comptes.MULTI:
            return True
        return self._admin_verifie() or not self._admin_verif_possible()

    _ADMIN_CODES = {}
    ADMIN_VERIF_S = 30 * 86400            # une session confirmee le reste 30 jours

    def _admin_verifie(self):
        try:
            from flask import has_request_context, session
            if not has_request_context():
                return True                    # taches de fond (pas une requete d'un navigateur)
            return time.time() - float(session.get("admin2_le") or 0) < self.ADMIN_VERIF_S
        except Exception:
            return False

    def _jetons_admin(self, ajouter=None):
        """Les iPhone de CONFIANCE pour le code admin. Un temoin de session vole pourrait enregistrer SON telephone
        (push_enregistrer) puis recevoir le code : seuls comptent les jetons deja la au premier usage (l'iPhone de
        l'admin) et ceux enregistres depuis une session admin deja confirmee."""
        try:
            with _verrou:
                c = self._db()
                try:
                    c.execute("CREATE TABLE IF NOT EXISTS push_jetons (jeton TEXT PRIMARY KEY, plateforme TEXT, le TEXT)")
                    c.execute("CREATE TABLE IF NOT EXISTS push_admin (jeton TEXT PRIMARY KEY, le TEXT)")
                    if not c.execute("SELECT 1 FROM push_admin WHERE jeton='*init*'").fetchone() and \
                            c.execute("SELECT 1 FROM push_jetons LIMIT 1").fetchone():     # le 1er iPhone relie : celui de l'admin
                        c.execute("INSERT OR IGNORE INTO push_admin VALUES ('*init*', ?)", (_maintenant(),))
                        c.execute("INSERT OR IGNORE INTO push_admin SELECT jeton, ? FROM push_jetons", (_maintenant(),))
                    if ajouter:
                        c.execute("INSERT OR IGNORE INTO push_admin VALUES (?, ?)", (ajouter, _maintenant()))
                    c.commit()
                    return [r[0] for r in c.execute("SELECT a.jeton FROM push_admin a JOIN push_jetons j ON j.jeton = a.jeton")]
                finally:
                    c.close()
        except Exception:
            return []

    def _admin_verif_possible(self):
        import apns
        return bool(os.environ.get("LOCKERROOM_ADMIN_CODE")) or (apns.actif() and bool(self._jetons_admin()))

    def admin_verif_envoyer(self):
        """Envoie un code a 6 chiffres (5 min) sur l'iPhone de l'admin (notification)."""
        import apns
        import comptes
        import secrets as _s
        if not self._est_admin_compte():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        cid = comptes.courant() or "local"
        code = f"{_s.randbelow(10 ** 6):06d}"
        self._ADMIN_CODES[cid] = {"h": hashlib.sha256(code.encode()).hexdigest(), "fin": time.time() + 300, "essais": 0}
        n = 0
        if apns.actif():
            for j in self._jetons_admin():
                if apns.envoyer(j, "SlabCoach · code admin", f"Ton code : {code} (5 min). Si ce n'est pas toi, ignore ce message.") == "ok":
                    n += 1
        return {"ok": True, "envoye": n, "secours": bool(os.environ.get("LOCKERROOM_ADMIN_CODE"))}

    def admin_verif_valider(self, code):
        import comptes
        import hmac as _h
        from flask import session
        if not self._est_admin_compte():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        cid = comptes.courant() or "local"
        brut = str(code or "").strip()
        e = self._ADMIN_CODES.get(cid)
        ok = False
        if e and time.time() < e["fin"] and e["essais"] < 5:
            e["essais"] += 1
            ok = _h.compare_digest(hashlib.sha256(re.sub(r"\D", "", brut).encode()).hexdigest(), e["h"])
        secours = os.environ.get("LOCKERROOM_ADMIN_CODE") or ""
        if not ok and secours and len(secours) >= 8:
            k = ("secours", cid)
            n = self._ADMIN_CODES.setdefault(k, {"essais": 0, "le": time.time()})
            if time.time() - n["le"] > 900:
                n.update(essais=0, le=time.time())
            if n["essais"] < 5:
                n["essais"] += 1
                ok = _h.compare_digest(brut, secours)
        if not ok:
            return {"ok": False, "erreur": "Code invalide ou expiré"}
        self._ADMIN_CODES.pop(cid, None)
        session["admin2_le"] = time.time()
        return {"ok": True}

    def _est_admin_compte(self):
        """Qui ajoute les produits au catalogue (pour TOUS les comptes) : le PC de Mathieu, et en ligne les comptes eBay
        listes dans LOCKERROOM_ADMINS (Render). Les utilisateurs n'ont jamais de fichier a telecharger."""
        import comptes
        if not comptes.MULTI:
            return True
        # 27 oct 2026 (revue de securite) : seulement une identite VERIFIEE. Le nom d'un compte Apple / Google est choisi
        # par la personne (on pourrait s'appeler comme l'admin) : il ne compte pas. Valent : le pseudo eBay confirme par eBay,
        # ou l'identifiant du compte SlabCoach.
        cid = comptes.courant()
        e = comptes.info(cid) or {}
        verifies = {cid, e.get("ebay_username")}
        if e.get("env") in ("production", "sandbox"):          # compte cree par « Se connecter avec eBay »
            verifies.add(e.get("username"))
        verifies = {str(x).strip().lower() for x in verifies if x}
        admins = {x.strip().lower() for x in os.environ.get("LOCKERROOM_ADMINS", "").split(",") if x.strip()}
        return bool(verifies & admins)

    def catalogue_importer(self, d):
        """d : {fichier (data URL ou base64), nom_fichier, produit_id (produit existant) | nom, saison, marque, sport}."""
        import base64
        import checklist_import
        import comptes
        import contributions
        d = dict(d or {})
        # 31 oct 2026 (Mathieu : « si un breaker veut un produit, il upload l'Excel ; notre programme s'occupe du reste, le
        # publie pour les autres utilisateurs et le valide aussi ») : tout le monde peut envoyer une checklist. Un utilisateur
        # ne remplace jamais un produit existant ; la validation automatique decide : publie, ou en attente pour l'admin.
        admin = self._est_admin()
        compte = (comptes.courant() if comptes.MULTI else "local") or "?"
        if not admin:
            d.pop("produit_id", None)
            if not contributions.quota_prendre(compte):
                return {"ok": False, "erreur": f"{contributions.MAX_JOUR} fichiers par jour au plus : réessaie demain"}
        brut_txt = str(d.get("fichier") or "")
        brut_txt = brut_txt.split(",", 1)[1] if brut_txt.startswith("data:") else brut_txt
        try:
            brut = base64.b64decode(brut_txt)
        except (ValueError, TypeError):
            return {"ok": False, "erreur": "Fichier illisible"}
        if not brut or len(brut) > 12_000_000:
            return {"ok": False, "erreur": "Fichier vide ou trop lourd (12 Mo au plus)"}
        nom_f = str(d.get("nom_fichier") or "checklist.xlsx")
        existant = catalogue.charger(d.get("produit_id")) if d.get("produit_id") else None
        sport = sports.valide(d.get("sport") or (existant or {}).get("sport") or self.reglages_lire().get("sport"))
        try:
            lu = checklist_import.lire(brut, nom_f, sport)
        except Exception as e:
            return {"ok": False, "erreur": "Fichier non reconnu : " + type(e).__name__}
        if lu["lignes"] < 5:
            return {"ok": False, "erreur": "Aucune checklist reconnue dans ce fichier (il faut le .xlsx ou .csv de GTS ou Beckett)"}
        modele = None
        if existant:
            prod = checklist_import.fusionner(existant, lu)
        else:
            # 30 oct 2026 (Mathieu : « l'app doit reconnaitre directement le produit avec le Excel ») : le nom du fichier s'il
            # dit la saison, sinon le titre ecrit dans le fichier (GTS / Beckett), puis le produit du catalogue qui y correspond
            nom_fic = checklist_import.nom_devine(nom_f)
            if not re.search(r"(19|20)\d{2}", nom_fic) and lu.get("titre_doc"):
                nom_fic = checklist_import.nom_devine(lu["titre_doc"])
            nom = re.sub(r"\s+", " ", str(d.get("nom") or "") or nom_fic).strip()
            pid0 = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode().lower()).strip("-")[:60]
            existant = catalogue.charger(pid0)        # meme produit deja au catalogue : on le met a jour
            if not existant:
                cle_n = (checklist_import._mots_ligne(nom), (re.search(r"(19|20)\d{2}", nom) or [""])[0])
                for x in catalogue.liste():
                    if (checklist_import._mots_ligne(x.get("nom")), (re.search(r"(19|20)\d{2}", str(x.get("nom"))) or [""])[0]) == cle_n:
                        existant = catalogue.charger(x["id"])
                        break
            if not existant:                         # 25 oct 2026 : « Upper Deck SP Authentic » = « SP Authentic »
                x = checklist_import.produit_semblable(nom, catalogue.liste())
                existant = catalogue.charger(x["id"]) if x else None
            if len(nom) < 4:
                return {"ok": False, "erreur": "Donne le nom du produit (ex. 2025-26 Upper Deck Series 2)"}
            pid = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode().lower()).strip("-")[:60]
            saison = d.get("saison") or (re.search(r"(19|20)\d{2}(-\d{2})?", nom) or [None])[0]
            prod = {"id": pid, "nom": nom, "saison": saison, "marque": d.get("marque") or nom.split()[1] if len(nom.split()) > 1 else "",
                    "sport": sport, "sortie": datetime.now().strftime("%Y-%m"),
                    "formats": [{"format": "Boîte hobby", "paquets": None, "cartes_par_paquet": None, "boites_par_caisse": 12}],
                    "sous_ensembles": lu["sous_ensembles"], "groupes_boite": [], "cartes": lu["cartes"],
                    "notes": ["Checklist importée (" + nom_f + ") : cotes par boîte à compléter"], "sources": []}
            if existant and not admin:                # un utilisateur ne remplace jamais un produit du catalogue
                if len(existant.get("cartes") or []) >= len(lu["cartes"]) * 0.9:
                    return {"ok": True, "deja": True, "id": existant["id"], "nom": existant["nom"], "nb_cartes": len(existant.get("cartes") or [])}
                prod = checklist_import.fusionner(existant, lu)       # plus complet que le notre : l'admin decide
                try:
                    verif = checklist_import.verifier(lu)
                except Exception:
                    verif = {"ok": [], "alertes": []}
                contributions.mettre_en_attente(prod, compte, ["Mise à jour d’un produit déjà au catalogue : " + str(len(lu["cartes"]))
                                                               + " cartes lues, " + str(len(existant.get("cartes") or [])) + " chez nous"],
                                                nom_f, maj_de=existant["id"], verif=verif)
                return {"ok": True, "attente": True, "id": prod["id"], "nom": prod["nom"], "nb_cartes": len(prod["cartes"]),
                        "raisons": ["Ce produit est déjà au catalogue : SlabCoach compare ta version et l’ajoute si elle est plus complète"]}
            if existant:
                prod = checklist_import.fusionner(existant, lu)
            else:
                autres = []
                for x in catalogue.liste():
                    try:
                        autres.append(catalogue.charger(x["id"]))
                    except Exception:
                        continue
                prod, modele = checklist_import.cotes_modele(prod, autres)
        # 25 oct 2026 - les cotes hobby de la checklist (GTS : « 1:2 h » = 6 Young Guns par boite de 12 paquets)
        n_cotes = checklist_import.par_boite_depuis_cotes(prod)
        src = "gogts.net" if re.search(r"gts|stated odds", nom_f + " " + json.dumps([x.get("cotes") for x in lu["sous_ensembles"]][:3]), re.I) \
            or any(x.get("cote_hobby") for x in lu["sous_ensembles"]) else "beckett.com"
        prod["sources"] = list(dict.fromkeys((prod.get("sources") or []) + [src + " (" + nom_f + ")"]))
        try:
            verif = checklist_import.verifier(lu)
        except Exception:
            verif = {"ok": [], "alertes": []}
        if not admin:
            raisons = contributions.valider(prod, verif, sport)
            if raisons:
                contributions.mettre_en_attente(prod, compte, raisons, nom_f, verif=verif)
                return {"ok": True, "attente": True, "id": prod["id"], "nom": prod["nom"], "nb_cartes": len(prod["cartes"]), "raisons": raisons}
            prod["contribue"] = {"compte": compte, "le": datetime.now().isoformat(timespec="seconds")}
        catalogue.enregistrer_ajout(prod)
        self._EV_CACHE.clear()
        p2 = catalogue.charger(prod["id"]) or prod
        taux = p2.get("_taux") or {}
        e_c = catalogue.etat_cotes(p2)
        return {"ok": True, "publie": not admin, "id": prod["id"], "nom": prod["nom"], "nb_cartes": len(prod["cartes"]), "nouveau": not existant, "modele": modele,
                "verification": verif,
                "manquantes": e_c["manquantes"], "estimees": e_c["estimees"], "non_publiees": e_c["non_publiees"],
                "cotes_lues": n_cotes,
                "sous_ensembles": [{"nom": x["nom"], "groupe": x.get("groupe"), "nb_cartes": x.get("nb_cartes"), "tirage": x.get("tirage"),
                                    "par_boite": x.get("par_boite"), "taux": round(taux.get(x["nom"], 0), 4)} for x in prod["sous_ensembles"]]}

    # 30 oct 2026 (Mathieu : « une liste des produits populaires, classes par sport, je clique et je mets le fichier ;
    # un petit dashboard avec les dates de sortie Upper Deck et Topps ») : le calendrier public des sorties, et pour
    # chaque produit : deja au catalogue (avec ses cotes) ou pas
    def admin_sorties(self, force=False):
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        import checklist_import
        import sorties
        r = sorties.lister(force=bool(force))
        cat = catalogue.liste()
        for x in r.get("produits") or []:
            p = checklist_import.produit_semblable(re.sub(r"\s+(hockey|baseball|basketball|football|soccer)\b", "", x["nom"], flags=re.I), cat)
            x["catalogue_id"] = p["id"] if p else None
            x["complete"] = bool(p and p.get("complete"))
            x["dans"] = sorties.jours(x.get("date"))
        return r

    # 25 oct 2026 - Mathieu : « essaie d'aller chercher toutes les checklists comme celle-ci » (gogts.net).
    def gts_liste(self, force=False):
        """Les checklists GTS recentes, et pour chacune : deja au catalogue ou pas."""
        import checklist_import
        import gts
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        try:
            r = gts.lister("hockey", force=bool(force))
        except Exception as e:
            return {"ok": False, "erreur": "gogts.net injoignable (" + type(e).__name__ + ")", "produits": []}
        cat = catalogue.liste()
        out = []
        for x in r.get("produits") or []:
            p = checklist_import.produit_semblable(x["nom"], cat)
            out.append({**x, "au_catalogue": (p or {}).get("id"), "nom_catalogue": (p or {}).get("nom"),
                        "ligue": next((l for l in ("AHL", "PWHL", "CHL", "USA") if l in x["nom"].split()), None)})
        return {"ok": r.get("ok", True), "erreur": r.get("erreur"), "produits": out, "maj": r.get("maj")}

    def gts_importer(self, url, nom=None):
        """Telecharge l'Excel d'une page produit GTS et l'importe (meme chemin qu'un fichier depose)."""
        import base64
        import gts
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        if not gts._sur(url):
            return {"ok": False, "erreur": "Adresse refusée (gogts.net seulement)"}
        try:
            brut, nom_f = gts.telecharger(url)
        except ValueError as e:
            return {"ok": False, "erreur": str(e)}
        except Exception as e:
            return {"ok": False, "erreur": "Téléchargement impossible (" + type(e).__name__ + ")"}
        slug_nom = gts.nom_de_slug(str(url).rstrip("/").rsplit("/", 1)[-1])[0]
        r = self.catalogue_importer({"fichier": base64.b64encode(brut).decode(), "nom_fichier": nom_f, "sport": "hockey",
                                     "nom": nom or slug_nom})
        if r.get("ok"):
            try:
                import nouveaux_produits
                nouveaux_produits.retirer_gts(url)
            except Exception:
                pass
        return r

    def checklist_cotes(self, pid, cotes=None, boites_par_caisse=None):
        """Les cotes par boite (« Young Guns : 6 », « Auto : 1 ») d'un produit importe, tapees par l'utilisateur."""
        if not self._est_admin():
            return {"ok": False, "erreur": "Les produits sont ajoutés par SlabCoach pour tout le monde"}
        prod = catalogue.charger(pid)
        if not prod:
            return {"ok": False, "erreur": "Produit introuvable dans le catalogue"}
        prod = {k: v for k, v in prod.items() if not k.startswith("_")}
        for x in prod.get("sous_ensembles") or []:
            if x["nom"] in (cotes or {}):
                v = _float((cotes or {})[x["nom"]])
                x["par_boite"] = v if v and v > 0 else None
        if _float(boites_par_caisse):
            prod["formats"] = [{**((prod.get("formats") or [{}])[0]), "boites_par_caisse": int(_float(boites_par_caisse))}]
        catalogue.enregistrer_ajout(prod)
        self._EV_CACHE.clear()
        return {"ok": True, "id": pid}

    def catalogue_checklist(self, pid):
        prod = catalogue.charger(pid)
        if not prod:
            return []
        vus, out = set(), []
        for c in prod["cartes"]:
            k = (c.get("joueur"), c.get("equipe"))
            if k in vus or not c.get("joueur"):
                continue
            vus.add(k)
            out.append({"joueur": c["joueur"], "equipe": c.get("equipe") or "", "categorie": c.get("sous_ensemble") or ""})
        return out

    def calculer_catalogue(self, params):
        p = params or {}
        r = self.reglages_lire()
        prod = catalogue.charger(p.get("produit_id"))
        if not prod:
            return {"ok": False, "erreur": "Produit introuvable dans le catalogue"}

        def f(cle, defaut):
            v = _float(p.get(cle))
            return defaut if v is None else v
        res = calcul.prix_catalogue(
            prod, boites=f("boites", 1) or 1, cout_boite=f("cout_boite", 0), marge=f("marge", r["marge_break"]) / 100,
            frais_pct=f("frais_pct", r["frais_break_pct"]) / 100, frais_fixe=f("frais_fixe", r["frais_break_fixe"]),
            mode=p.get("mode") or "equipes", plancher=f("plancher", r["plancher_place"]), arrondi=f("arrondi", r["arrondi_place"]) or 1,
            sport=prod.get("sport") or "hockey")
        fmt = (prod.get("formats") or [{}])[0]
        res.update(ok=True, valeurs=valeurs.statut(),
                   produit={"id": prod["id"], "nom": prod["nom"], "format": fmt.get("format"), "boites_par_caisse": fmt.get("boites_par_caisse"),
                            "sortie": prod.get("sortie"), "catalogue": True})
        return res

    def analyse_break(self, params):
        """24 oct 2026 (Mathieu : « break analyser dans seller et acheteur ») - pour un produit du catalogue (checklists
        officielles extraites dans catalogue/*.json) :
          vendeur  : prix de chaque place selon le cout des boites, le profit voulu et la decote (les places partent
                     souvent ~15 % sous le prix voulu : le prix affiche en tient compte) ;
          acheteur : les hits (autos, patchs) les plus susceptibles de sortir, joueur par joueur, et leur valeur ;
                     produit sans hit garanti : les recrues. Vue equipes aussi (valeur attendue, prix demande)."""
        import forfaits
        p = params or {}
        if not forfaits.produit_permis(str(p.get("produit_id") or "")):
            return {"ok": False, "erreur": "L'analyse de tous les produits est dans le forfait Pro.", "pro_requis": True}
        r = self.reglages_lire()
        prod = catalogue.charger(p.get("produit_id"))
        if not prod:
            return {"ok": False, "erreur": "Produit introuvable dans le catalogue"}

        def f(cle, defaut):
            v = _float(p.get(cle))
            return defaut if v is None else v
        sport = prod.get("sport") or "hockey"
        boites = max(1, min(120, int(f("boites", 1) or 1)))
        decote = max(0.0, min(0.6, f("decote", 15) / 100))
        frais_pct, frais_fixe = f("frais_pct", r["frais_break_pct"]) / 100, f("frais_fixe", r["frais_break_fixe"])
        arrondi = f("arrondi", r["arrondi_place"]) or 1
        args = dict(boites=boites, cout_boite=f("cout_boite", 0), marge=f("marge", r["marge_break"]) / 100,
                    frais_pct=frais_pct, frais_fixe=frais_fixe, plancher=f("plancher", r["plancher_place"]), arrondi=arrondi, sport=sport)
        mode = p.get("mode") or "equipes"
        # 25 oct 2026 : les valeurs viennent des ventes reelles du produit (mesurees en arriere-plan, 7 jours) ;
        # sans cout entre, le prix d'une boite = ses ventes recentes
        mes = valeur_produit.mesurer_si_besoin(prod) or {}
        boite_marche = mes.get("boite")
        cout_estime = None
        if p.get("cout_boite") in (None, "", 0, "0"):
            if boite_marche:
                args["cout_boite"] = cout_estime = boite_marche
            else:                                # ni cout ni ventes de boites : la valeur attendue d'une boite
                ev0 = calcul.prix_catalogue(prod, mode=mode, **{**args, "cout_boite": 0}).get("ev_par_boite") or 0
                args["cout_boite"] = cout_estime = round(ev0, 2)
        res = calcul.prix_catalogue(prod, mode=mode, garder_dist=True, **args)
        # le prix affiche : celui qui donne le profit voulu meme si les places partent `decote` plus bas
        n = len(res["places"]) or 1
        for pl in res["places"]:
            pl["prix_vise"] = pl["prix"]
            pl["prix"] = calcul.arrondi_rond(pl["prix"] / max(0.4, 1 - decote), arrondi)    # 28 oct : prix ronds (5 et 0)
        total = round(sum(pl["prix"] for pl in res["places"]), 2)
        res["total"] = total
        res["profit_plein"] = round(total * (1 - frais_pct) - frais_fixe * n - res["cout"], 2)
        res["profit_estime"] = round(total * (1 - decote) * (1 - frais_pct) - frais_fixe * n - res["cout"], 2)
        res["decote"] = round(decote * 100, 1)
        demandes = {str(k): _float(v) for k, v in (p.get("prix_demandes") or {}).items() if _float(v)}
        stats = self._stats_checklist(prod, mode, sport)
        # 31 oct 2026 (Mathieu : « pas normal que Boston soit dans les derniers avec Hagens », vue acheteur) : sans prix du
        # breaker, la barre « une carte qui vaut ta place » etait le prix ESTIME de chaque place, lui-meme proportionnel a
        # la valeur : les equipes cheres (celles des grosses recrues) devaient franchir une barre plus haute et tombaient en
        # bas, les equipes pas cheres montaient. Maintenant la barre est la MEME pour toutes : le prix moyen d'une place.
        # Avec le prix du breaker entre pour une equipe, c'est ce prix-la (le vrai rapport qualite-prix).
        barre = round(total / n, 2) if n else None
        for pl in res["places"]:
            self._noter_place(pl, demandes.get(pl["cle"]), stats.get(pl["cle"]), barre)
        self._scores_relatifs(res["places"])
        # 25 oct 2026 (Mathieu : acheteur = « des scores », joueurs ET equipes) : la meme chose, place par joueur
        joueurs = None
        if p.get("acheteur"):
            rj = calcul.prix_catalogue(prod, mode="joueurs", garder_dist=True, **args)
            sj = self._stats_checklist(prod, "joueurs", sport)
            dj = {str(k): _float(v) for k, v in (p.get("prix_joueurs") or {}).items() if _float(v)}
            joueurs = [pl for pl in rj["places"] if (pl.get("part_brute") or pl["ev"]) > 0]   # 29 oct : la part exacte (l'ev arrondi cachait des joueurs a 1 boite)
            for pl in joueurs:
                pl["prix"] = calcul.arrondi_rond(pl["prix"] / max(0.4, 1 - decote), arrondi)
                self._noter_place(pl, dj.get(pl["cle"]), sj.get(pl["cle"]), barre)
                pl["equipe"] = (sj.get(pl["cle"]) or {}).get("equipe")
            self._scores_relatifs(joueurs)
            joueurs.sort(key=lambda x: -x["score"])
            joueurs = joueurs[:400]          # 29 oct : tous (recherche d'un joueur dans l'ecran) ; l'ecran en montre 60
        fmt = (prod.get("formats") or [{}])[0]
        return {**res, "ok": True, "hits": self._hits_produit(prod, boites), "boites": boites, "mode": mode,
                "joueurs": joueurs, "prix_boite_marche": boite_marche, "cout_boite": args["cout_boite"], "cout_estime": cout_estime,
                "ventes_actives": vendues.actif(),
                "valeurs_mesurees": bool(mes.get("sous")), "valeurs_maj": mes.get("maj"),
                "produit": {"id": prod["id"], "nom": prod["nom"], "saison": prod.get("saison"), "marque": prod.get("marque"),
                            "format": fmt.get("format"), "boites_par_caisse": fmt.get("boites_par_caisse"), "sport": sport,
                            "preliminaire": bool(prod.get("preliminaire"))}}

    @staticmethod
    def _noter_place(pl, demande, stats, barre=None):
        """Score d'une place pour l'acheteur (0-100) : la chance de rembourser son prix (au moins une carte qui vaut
        le prix paye) et la valeur attendue / prix. Sans prix demande : le prix estime d'un breaker."""
        prix = demande or pl["prix"] or 0
        dist = pl.pop("_dist", [])
        pl["prix_compare"] = prix
        if demande:
            pl["demande"] = demande
        pl["valeur_ratio"] = round(pl["ev"] / prix, 2) if prix else None
        pl["p_rembourse"] = calcul.chance_rembourser(dist, prix) if prix else 0
        # 29 oct 2026 (Mathieu : « les rookies sont de loin les plus presents, explique ta logique » ; choix : « un hit qui
        # vaut ta place ») : la chance de tirer AU MOINS UNE carte qui vaut, a elle seule, le prix de la place
        import math as _m2
        seuil = demande or barre or prix
        pl["barre"] = round(seuil, 2) if seuil else None
        n_bonnes = sum(float(n) for v, n in dist if seuil and float(v) >= seuil)
        pl["p_carte_prix"] = round(1 - _m2.exp(-n_bonnes), 6) if seuil else 0
        # 31 oct 2026 (vue acheteur, « chance recrue » : Florida 2e avec Benning et Alscher, Boston absent) : une recrue
        # ordinaire a 1 $ comptait autant que la Young Guns de Hagens. Maintenant : la chance d'au moins UNE recrue qui
        # vaut, a elle seule, la meme barre (le prix moyen d'une place, ou le prix du breaker)
        dist_r = pl.pop("_dist_r", [])
        n_rec = sum(float(n) for v, n in dist_r if seuil and float(v) >= seuil)
        pl["p_recrue_prix"] = round(1 - _m2.exp(-n_rec), 6) if seuil else 0
        # 31 oct 2026 (Mathieu : « Hagens, Frondell et Martone sont les trois plus recherches ») : une chance (« au moins une
        # recrue qui vaut X ») met a egalite une Young Guns de 90 $ et une de 16 $. La valeur esperee des recrues, elle, suit
        # leur vrai prix : c'est elle qui classe les places pour les recrues
        pl["ev_recrue"] = round(sum(float(v) * float(n) for v, n in dist_r), 2)
        # 26 oct 2026 (Mathieu : « la chance de tomber sur une numerotee, patch, auto, auto-patch, SSP, pas la chance de
        # rembourser la mise ») : le score = 50 % la chance d'au moins un hit + 50 % la valeur attendue / le prix
        # (score provisoire : _scores_relatifs le refait sur la liste entiere)
        pl["score"] = round(100 * min(1.0, (pl["valeur_ratio"] or 0) / 1.5), 2)
        top = sorted(dist, key=lambda x: -x[0])[:1]
        pl["meilleure_valeur"] = round(top[0][0], 2) if top else None
        # 26 oct 2026 (Mathieu : « l'utilisateur doit savoir comment tu as calcule le tout ») : ce qui peut sortir,
        # sous-ensemble par sous-ensemble : nombre attendu, chance d'en avoir au moins une, valeur d'une carte
        det = pl.pop("_detail", {}) or {}
        import math as _m
        pl["cartes_possibles"] = [{"sous": k, "attendu": round(v[0], 3), "chance": round(1 - _m.exp(-v[0]), 6), "valeur": round(v[1], 2),
                                   "part_ev": round(100 * v[2] / pl["ev"], 1) if pl["ev"] else 0, "ventes": v[3]}
                                  for k, v in sorted(det.items(), key=lambda kv: -kv[1][2])[:8] if v[2] > 0]
        pl["seuil_revente"] = calcul.SEUIL_REVENTE
        pl.update({k: v for k, v in (stats or {}).items() if k != "equipe"})

    @staticmethod
    def _scores_relatifs(liste):
        """29 oct 2026 (Mathieu, choix : « un hit qui vaut ta place ») : le score = la chance de tirer au moins UNE carte qui
        vaut a elle seule le prix de la place (prix du breaker s'il est entre, sinon le prix estime). 100 = la meilleure
        place de la liste. Avant (27-29 oct) : les hits par dollar, qui mettaient en haut des places de legendes presque
        gratuites dont les autos valent 10-20 $ ; les recrues, qui ont le plus de cartes qui valent cher, remontent."""
        mx = max([pl.get("p_carte_prix") or 0 for pl in liste] + [1e-12])
        for pl in liste:
            pl["hit_par_dollar"] = None
            pl["score"] = round(100 * (pl.get("p_carte_prix") or 0) / mx, 2)

    @staticmethod
    def _stats_checklist(prod, mode, sport):
        """Par equipe (ou joueur) : combien de joueurs dans le produit, de recrues, de cartes numerotees, de patchs,
        d'autos et de SSP dans la checklist (ce que l'acheteur peut esperer)."""
        se = {s["nom"]: s for s in prod.get("sous_ensembles") or []}
        out = {}
        for c in prod.get("cartes") or []:
            s = se.get(c.get("sous_ensemble")) or {}
            if s.get("parallele_de"):
                continue                                   # une parallele n'est pas une carte de plus dans la checklist
            if mode == "joueurs":
                cles = [x.strip() for x in str(c.get("joueur") or "").split("/") if x.strip()]
            else:
                cles = list(dict.fromkeys(calcul.code_equipe(e, sport) for e in re.split(r"\s*/\s*|\s*,\s*", str(c.get("equipe") or "")) if e.strip()))
            g = s.get("groupe") or "base"
            for k in cles:
                d = out.setdefault(k, {"_j": set(), "_r": set(), "nb_numerotees": 0, "nb_patchs": 0, "nb_autos": 0, "nb_ssp": 0,
                                       "equipe": c.get("equipe"), "nb_cartes": 0, "nb_versions": 0})
                d["nb_cartes"] += 1
                if c.get("joueur"):
                    d["_j"].add(c["joueur"])
                    if g == "recrue" or c.get("recrue"):
                        d["_r"].add(c["joueur"])
                if c.get("tirage") or s.get("tirage"):
                    d["nb_numerotees"] += 1
                if c.get("memo") or g in ("memo", "auto_memo"):
                    d["nb_patchs"] += 1
                if c.get("auto") or g in ("auto", "auto_memo"):
                    d["nb_autos"] += 1
                if re.search(r"\bssp\b|short print", s.get("nom") or "", re.I):
                    d["nb_ssp"] += 1
        # 26 oct 2026 : les versions = chaque carte x ses paralleles (les paralleles reprennent la liste du parent) ;
        # par categorie de hit : [versions, versions dont le fabricant ne publie pas la cote (absentes du calcul)]
        taux = prod.get("_taux") or {}
        for d in out.values():
            d["versions_cat"] = {}
        par = {}
        for c in prod.get("cartes") or []:
            par.setdefault(c.get("sous_ensemble"), []).append(c)
        for nom, s in se.items():
            lc = par.get(nom)
            if not lc:
                k, ch = s.get("parallele_de"), 0
                while k and not par.get(k) and ch < 6:
                    k, ch = (se.get(k) or {}).get("parallele_de"), ch + 1
                lc = par.get(k) or []
            for c in lc:
                if mode == "joueurs":
                    cles = [x.strip() for x in str(c.get("joueur") or "").split("/") if x.strip()]
                else:
                    cles = list(dict.fromkeys(calcul.code_equipe(e, sport) for e in re.split(r"\s*/\s*|\s*,\s*", str(c.get("equipe") or "")) if e.strip()))
                cats = calcul.categories_carte(c, s)
                sans_cote = (taux.get(nom) or 0) <= 0
                for k2 in cles:
                    if k2 in out:
                        out[k2]["nb_versions"] += 1
                        for cat in list(cats) + (["hit"] if cats else []):
                            vc = out[k2]["versions_cat"].setdefault(cat, [0, 0])
                            vc[0] += 1
                            vc[1] += 1 if sans_cote else 0
        for d in out.values():
            d["nb_joueurs"], d["nb_recrues"] = len(d.pop("_j")), len(d.pop("_r"))
        return out

    def break_ventes_joueur(self, params):
        """26 oct 2026 (Mathieu : « les ventes moyennes de ce joueur, la meme maniere pour tous ») : ses ventes eBay
        reelles dans CE produit, classees par categorie de hit (ventes_joueur : la meme regle pour chaque joueur)."""
        import forfaits
        import ventes_joueur
        if not comps_permis(self):              # 10 nov 2026 : comps = admin seulement
            return {"ok": True, "coupe": True, "categories": [], "ventes": []}
        p = params or {}
        if not forfaits.produit_permis(str(p.get("produit_id") or "")):
            return {"ok": False, "erreur": "L'analyse de tous les produits est dans le forfait Pro.", "pro_requis": True}
        prod = catalogue.charger(p.get("produit_id"))
        if not prod:
            return {"ok": False, "erreur": "Produit introuvable dans le catalogue"}
        if not vendues.actif():
            return {"ok": False, "erreur": "Les ventes réelles s'activent avec SoldComps."}
        return ventes_joueur.ventes(prod, str(p.get("joueur") or ""))

    def _hits_produit(self, prod, boites):
        """Joueur par joueur : ses autos / patchs attendus dans le break, la chance d'en sortir au moins un et leur valeur."""
        import math
        se = {s["nom"]: s for s in prod.get("sous_ensembles") or []}
        taux = prod["_taux"]
        lignes = catalogue.cartes_attendues(prod, boites)
        groupes = ("auto", "memo", "auto_memo")
        hits = [(c, s, n) for c, s, n in lignes if (s.get("groupe") in groupes) or c.get("auto") or c.get("memo")]
        genre = "hits"
        if sum(n for _c, _s, n in hits) < 0.3 * float(boites):   # pas de hit garanti (ex. Series 1) : les recrues
            hits = [(c, s, n) for c, s, n in lignes if s.get("groupe") == "recrue" or c.get("recrue")]
            genre = "recrues"
        cache, par = {}, {}
        for c, s, n in hits:
            for j in [x.strip() for x in str(c.get("joueur") or "").split("/") if x.strip()]:
                d = par.setdefault(j, {"joueur": j, "equipe": c.get("equipe"), "n": 0.0, "ev": 0.0, "cartes": {}})
                part = 1.0 / max(1, len(str(c.get("joueur")).split("/")))
                v = n * part * valeurs.valeur_carte(prod, s["nom"], j, se, taux, cache)[0]       # 25 oct 2026 : ventes reelles
                d["n"] += n * part
                d["ev"] += v
                d["cartes"][s["nom"]] = d["cartes"].get(s["nom"], 0.0) + v
        out = []
        for d in par.values():
            if d["n"] <= 0:
                continue
            out.append({"joueur": d["joueur"], "equipe": d["equipe"], "chance": round(1 - math.exp(-d["n"]), 3),
                        "valeur": round(d["ev"] / d["n"], 2), "ev": round(d["ev"], 2),
                        "meilleure": max(d["cartes"].items(), key=lambda kv: kv[1])[0]})
        out.sort(key=lambda x: -x["ev"])                   # chance x valeur : ce qui vaut le plus d'etre vise
        return {"genre": genre, "joueurs": out[:30]}

    # -- images (24 oct 2026, « ajoute toujours le plus d'images possible ») : photos d'annonces eBay, en cache ------
    def _cache_images(self):
        import comptes
        ch = os.path.join(comptes.DONNEES, "images_cartes.json")
        try:
            with open(ch, encoding="utf-8") as fi:
                return ch, json.load(fi)
        except (OSError, ValueError):
            return ch, {}

    def _image_pour(self, cle, q, doit=None, cache=None):
        ch, d = cache or self._cache_images()
        e = d.get(cle)
        if e and (time.time() - e.get("le", 0)) < 14 * 86400:
            return e.get("url")
        url = None
        try:
            for a in ebay_compte.rechercher(q, limite=20, fond=False):
                if a.get("photo") and (not doit or all(m in a["titre"].lower() for m in doit)):
                    url = a["photo"]
                    break
        except (RuntimeError, OSError):
            return None
        with _VERROU_IMG:
            d[cle] = {"url": url, "le": time.time()}
            tmp = ch + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fo:
                json.dump(d, fo)
            os.replace(tmp, ch)
        return url

    def images_produits(self, ids=None):
        """La photo de la boite de chaque produit. 26 oct 2026 (Mathieu : « de meilleures photos du produit, voir sur
        upperdeck.com ») : l'image officielle d'upperdeck.com, sinon celle de la page GTS du produit (30 jours) ;
        sinon une annonce eBay (14 jours)."""
        # 27 oct 2026 - revue legale (Mathieu : « trouve des sources autorisees, sinon enleve les images ») : les photos
        # d'upperdeck.com, de gogts.net et des annonces eBay (hors de leur annonce) ne sont pas a nous. L'ecran montre
        # le visuel SlabCoach du produit (saison + nom) a la place.
        if not IMAGES_TIERCES:
            return {}
        from concurrent.futures import ThreadPoolExecutor
        cache = self._cache_images()
        ch, d = cache
        prods = [pr for pr in catalogue.liste() if not ids or pr["id"] in ids]

        def un(pr):
            e = d.get("off:" + pr["id"])
            if e and time.time() - e.get("le", 0) < (30 if e.get("url") else 3) * 86400:
                return pr["id"], e.get("url")
            try:
                url = self._photo_officielle(pr["nom"])
            except Exception:
                url = None
            with _VERROU_IMG:
                d["off:" + pr["id"]] = {"url": url, "le": time.time()}
                tmp = ch + ".tmp"
                with open(tmp, "w", encoding="utf-8") as fo:
                    json.dump(d, fo)
                os.replace(tmp, ch)
            return pr["id"], url
        with ThreadPoolExecutor(max_workers=4) as ex:
            out = {k: u for k, u in ex.map(un, prods) if u}
        for pr in prods:
            if pr["id"] not in out:
                nom = re.sub(r"^(\d{4})-(\d{2})", r"\1-\2", pr["nom"])
                out[pr["id"]] = self._image_pour("prod:" + pr["id"], f"{nom} hobby box sealed",
                                                 [pr["saison"].split("-")[0], "box"], cache)
        return out

    @staticmethod
    def _photo_officielle(nom):
        """upperdeck.com (WordPress : recherche puis l'image de partage de la page), sinon la page GTS du produit."""
        import html as _html
        import urllib.parse
        import urllib.request

        def get(url, n=600_000):
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (SlabCoach)", "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=8) as r:
                return r.read(n).decode("utf-8", "ignore")

        def og(page):
            m = re.search(r"""<meta[^>]+property=["']og:image(?::secure_url)?["'][^>]+content=["']([^"']+)["']""", page, re.I) \
                or re.search(r"""<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:image["']""", page, re.I)
            return _html.unescape(m.group(1)) if m else None
        saison = (re.search(r"(19|20)\d{2}-\d{2}|(19|20)\d{2}", nom) or [""])[0]
        court = re.sub(r"^((?:19|20)\d{2}(?:-\d{2})?)\s+(Upper Deck\s+)?", r"\1 ", nom).strip()
        mots = [w.lower() for w in re.sub(r"(19|20)\d{2}(-\d{2})?", " ", court).split() if len(w) > 1]
        try:
            q = urllib.parse.urlencode({"search": court + " hockey", "per_page": 10})
            res = json.loads(get("https://upperdeck.com/wp-json/wp/v2/search?" + q)) or []
            meilleur, sc_m = None, -99
            for x in res:
                t = _html.unescape(str(x.get("title") or "")).lower()
                if saison and saison not in t and saison.replace("-", "/") not in t:
                    continue
                sc = sum(2 for w in mots if w in t) - 3 * bool(re.search(r"blaster|retail|tin\b|mega|hanger|checklist|fat pack|value", t))
                if sc > sc_m:
                    meilleur, sc_m = x, sc
            if meilleur and sc_m >= 2 * max(1, len(mots) - 1) and str(meilleur.get("url") or "").startswith("https://upperdeck.com"):
                u = og(get(meilleur["url"]))
                if u and urllib.parse.urlparse(u).hostname and urllib.parse.urlparse(u).hostname.endswith("upperdeck.com"):
                    return u
        except Exception:
            pass
        try:                                          # la page GTS du produit (deja connue par la liste des checklists)
            import checklist_import
            import gts
            l = gts._lire().get("hockey", {}).get("produits") or []
            p = next((x for x in l if checklist_import.produit_semblable(x["nom"], [{"nom": nom}])), None)
            if p:
                u = og(gts._get(p["url"]).decode("utf-8", "ignore"))
                fichier = urllib.parse.unquote(str(u or "").rsplit("/", 1)[-1]).lower()
                if u and gts._sur(u) and (any(w in fichier for w in mots) or saison[:4] in fichier):
                    return u
        except Exception:
            pass
        return None

    def portraits_joueurs(self, joueurs):
        """26 oct 2026 (Mathieu : « les images doivent etre celles des joueurs et non de la carte ») : le portrait officiel
        de la LNH (recherche publique de joueurs, puis la fiche du joueur), garde 30 jours. Seulement si Mathieu active
        le contenu officiel LNH (LOCKERROOM_LOGOS_LNH=1 : marques et photos de la LNH, sa decision)."""
        if os.environ.get("LOCKERROOM_LOGOS_LNH") != "1":        # 27 oct 2026 : coupe par defaut (revue legale)
            return {}
        import urllib.parse
        import urllib.request
        cache = self._cache_images()
        ch, d = cache

        def un(j):
            cle = "lnh:" + cartes_match.norm(j)
            e = d.get(cle)
            if e and (time.time() - e.get("le", 0)) < 30 * 86400:
                return j, e.get("url")
            url = None
            try:
                q = urllib.parse.urlencode({"culture": "en-us", "limit": 8, "q": j})      # actifs ET espoirs repeches
                req = urllib.request.Request("https://search.d3.nhle.com/api/v1/search/player?" + q, headers={"User-Agent": "SlabCoach"})
                with urllib.request.urlopen(req, timeout=8) as r:
                    res = json.loads(r.read().decode("utf-8")) or []
                n = cartes_match.norm(j)
                cands = [x for x in res if cartes_match.norm(x.get("name") or "") == n]
                cands.sort(key=lambda x: (not x.get("active"), str(x.get("lastSeasonId") or "")), reverse=False)
                pid = next((x.get("playerId") for x in cands), None)
                if pid:
                    req = urllib.request.Request(f"https://api-web.nhle.com/v1/player/{pid}/landing", headers={"User-Agent": "SlabCoach"})
                    with urllib.request.urlopen(req, timeout=8) as r:
                        url = (json.loads(r.read().decode("utf-8")) or {}).get("headshot")
                    if url and re.search(r"default|silhouette|placeholder", url, re.I):
                        url = None                          # pas de vraie photo : l'ecran met ses initiales
            except Exception:
                url = None
            with _VERROU_IMG:
                d[cle] = {"url": url, "le": time.time() if url else time.time() - 23 * 86400}      # pas trouve : reessaie dans 7 j
                tmp = ch + ".tmp"
                with open(tmp, "w", encoding="utf-8") as fo:
                    json.dump(d, fo)
                os.replace(tmp, ch)
            return j, url
        from concurrent.futures import ThreadPoolExecutor
        liste = [x for x in dict.fromkeys(str(y) for y in (joueurs or []) if y)][:40]
        with ThreadPoolExecutor(max_workers=6) as ex:
            return {j: u for j, u in ex.map(un, liste) if u}

    def images_joueurs(self, produit_id, joueurs, genre="hits"):
        """La carte (auto / patch, ou recrue) de chaque joueur dans ce produit : une photo par joueur, 12 au plus."""
        prod = catalogue.charger(produit_id)
        if not prod or not IMAGES_TIERCES:          # 27 oct 2026 : vignettes aux initiales (photos d'annonces = pas a nous)
            return {}
        cache = self._cache_images()
        mot = "auto" if genre == "hits" else "rookie"
        liste = [j for j in dict.fromkeys(str(x) for x in (joueurs or []) if x)][:40]   # 40 : une vedette par equipe

        def une(j):
            nom_fam = j.split("/")[0].split()[-1].lower()
            return j, self._image_pour(f"j:{produit_id}:{j}", f"{j.split('/')[0]} {prod['nom']} {mot}", [nom_fam], cache)
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=6) as ex:          # en parallele : 32 equipes en quelques secondes
            return dict(ex.map(une, liste))

    def valeurs_statut(self):
        return valeurs.statut()

    def valeurs_maj(self, source=None):
        """Recalcule valeurs_joueurs.json depuis la source (prototype : Hall of Cardz sur ce PC)."""
        import valeurs_maj
        try:
            return valeurs_maj.construire(source)
        except FileNotFoundError:
            return {"ok": False, "erreur": "Source des valeurs introuvable sur ce PC"}

    # -- breaks -----------------------------------------------------------------------------------
    def break_supprimer(self, bid):
        with _verrou:
            c = self._db()
            try:
                c.execute("DELETE FROM frappes WHERE break_id=?", (bid,))
                c.execute("DELETE FROM places WHERE break_id=?", (bid,))
                c.execute("DELETE FROM breaks WHERE id=?", (bid,))
                c.commit()
            finally:
                c.close()
        return {"ok": True}

    def break_creer(self, d):
        """d : {nom, produit_id, mode, boites, cout, frais_pct, frais_fixe, places:[{cle, libelle, prix}]}
        mode « aleatoire » : places = nb de places au meme prix, lots = les equipes."""
        d = d or {}
        jeton = secrets.token_urlsafe(9)
        with _verrou:
            c = self._db()
            try:
                cat = d.get("catalogue_id") or (d.get("produit_id") if isinstance(d.get("produit_id"), str) and not str(d.get("produit_id")).isdigit() else None)
                pid = None if cat else d.get("produit_id")
                sport = d.get("sport")
                if not sport and cat:
                    sport = (catalogue.charger(cat) or {}).get("sport") or "hockey"
                elif not sport and pid:
                    row = c.execute("SELECT nom, sport FROM produits WHERE id=?", (pid,)).fetchone()
                    sport = row and (row["sport"] or sports.detecter(row["nom"], defaut=None))
                sport = sports.valide(sport or self.reglages_lire().get("sport"))
                bid = c.execute("INSERT INTO breaks (nom, produit_id, mode, boites, cout, frais_pct, frais_fixe, statut, jeton, cree_le, catalogue_id, sport) "
                                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                                (d.get("nom") or "Break", pid, d.get("mode") or "equipes", _float(d.get("boites")) or 1,
                                 _float(d.get("cout")) or 0, _float(d.get("frais_pct")) or 0, _float(d.get("frais_fixe")) or 0,
                                 "ouvert", jeton, _maintenant(), cat, sport)).lastrowid
                if d.get("mode") == "aleatoire":
                    n = int(d.get("nb_places") or len(sports.equipes(sport)))
                    prix = _float(d.get("prix_place")) or 0
                    for i in range(n):
                        c.execute("INSERT INTO places (break_id, cle, libelle, prix, ordre) VALUES (?,?,?,?,?)",
                                  (bid, f"P{i + 1}", f"Place {i + 1}", prix, i))
                else:
                    for i, pl in enumerate(d.get("places") or []):
                        c.execute("INSERT INTO places (break_id, cle, libelle, prix, ordre) VALUES (?,?,?,?,?)",
                                  (bid, pl.get("cle"), pl.get("libelle") or pl.get("nom") or pl.get("cle"), _float(pl.get("prix")) or 0, i))
                c.commit()
            finally:
                c.close()
        return {"ok": True, "id": bid, "jeton": jeton}

    def breaks_liste(self):
        with _verrou:
            c = self._db()
            try:
                out = _dicts(c.execute(
                    "SELECT b.*, (SELECT COUNT(*) FROM places p WHERE p.break_id=b.id) AS nb_places, "
                    "(SELECT COUNT(*) FROM places p WHERE p.break_id=b.id AND p.vendu=1) AS nb_vendues, "
                    "(SELECT COALESCE(SUM(prix),0) FROM places p WHERE p.break_id=b.id AND p.vendu=1) AS revenus, "
                    "(SELECT COUNT(*) FROM frappes f WHERE f.break_id=b.id AND f.envoye=0 AND f.place_id IS NOT NULL) AS a_envoyer "
                    "FROM breaks b ORDER BY b.id DESC"))
            finally:
                c.close()
        for b in out:
            b.update(calcul.profit_break(b["revenus"], b["nb_vendues"], b["cout"], (b["frais_pct"] or 0) / 100,
                                         b["frais_fixe"] or 0, b["port_paye"] or 0))
        return out

    def break_detail(self, bid):
        with _verrou:
            c = self._db()
            try:
                b = c.execute("SELECT * FROM breaks WHERE id=?", (bid,)).fetchone()
                if not b:
                    return {"ok": False, "erreur": "Break introuvable"}
                b = dict(b)
                places = _dicts(c.execute("SELECT * FROM places WHERE break_id=? ORDER BY ordre", (bid,)))
                frappes = _dicts(c.execute("SELECT * FROM frappes WHERE break_id=? ORDER BY id DESC", (bid,)))
            finally:
                c.close()
        b["tirage"] = json.loads(b["tirage"]) if b.get("tirage") else None
        vendues = [p for p in places if p["vendu"]]
        b["bilan"] = calcul.profit_break(sum(p["prix"] for p in vendues), len(vendues), b["cout"], (b["frais_pct"] or 0) / 100,
                                         b["frais_fixe"] or 0, b["port_paye"] or 0)
        return {"ok": True, "break": b, "places": places, "frappes": frappes}

    def break_maj(self, bid, champs):
        ok = {k: v for k, v in (champs or {}).items() if k in ("nom", "port_paye", "cout", "statut", "frais_pct", "frais_fixe")}
        for k in ("port_paye", "cout", "frais_pct", "frais_fixe"):
            if k in ok:
                ok[k] = _float(ok[k]) or 0.0
        if not ok:
            return {"ok": False}
        with _verrou:
            c = self._db()
            try:
                c.execute(f"UPDATE breaks SET {', '.join(k + '=?' for k in ok)} WHERE id=?", list(ok.values()) + [bid])
                if ok.get("statut") == "ferme":
                    c.execute("UPDATE breaks SET ferme_le=? WHERE id=?", (_maintenant(), bid))
                c.commit()
            finally:
                c.close()
        return {"ok": True}

    def place_maj(self, place_id, champs):
        ok = {k: v for k, v in (champs or {}).items() if k in ("acheteur", "vendu", "paye", "prix")}
        if "prix" in ok:
            ok["prix"] = _float(ok["prix"]) or 0.0
        if "acheteur" in ok and ok["acheteur"] and "vendu" not in ok:
            ok["vendu"] = 1
        if not ok:
            return {"ok": False}
        with _verrou:
            c = self._db()
            try:
                c.execute(f"UPDATE places SET {', '.join(k + '=?' for k in ok)} WHERE id=?", list(ok.values()) + [place_id])
                c.commit()
            finally:
                c.close()
        return {"ok": True}

    def break_engager(self, bid):
        """Avant le tirage : publie l'empreinte de la graine (engagement)."""
        graine = secrets.token_hex(16)
        import hashlib
        with _verrou:
            c = self._db()
            try:
                # 4 nov 2026 (revue) : un tirage fait n'est jamais efface ; une empreinte deja publiee reste la meme
                b = c.execute("SELECT empreinte, tirage FROM breaks WHERE id=?", (bid,)).fetchone()
                if not b:
                    return {"ok": False, "erreur": "Break introuvable"}
                try:
                    t = json.loads(b["tirage"] or "null") or {}
                except ValueError:
                    t = {}
                if t.get("resultat"):
                    return {"ok": False, "erreur": "Le tirage est déjà fait"}
                if b["empreinte"] and t.get("graine_secrete"):
                    return {"ok": True, "empreinte": b["empreinte"]}
                c.execute("UPDATE breaks SET empreinte=?, tirage=? WHERE id=?",
                          (hashlib.sha256(graine.encode()).hexdigest(), json.dumps({"graine_secrete": graine}), bid))
                c.commit()
            finally:
                c.close()
        return {"ok": True}

    def break_tirage(self, bid):
        """Mode aleatoire : attribue les equipes aux places vendues, au hasard,
        avec la graine engagee (ou une nouvelle). Horodate et publie."""
        d = self.break_detail(bid)
        if not d.get("ok"):
            return d
        b = d["break"]
        if b["mode"] != "aleatoire":
            return {"ok": False, "erreur": "Le tirage sert aux breaks en équipes aléatoires"}
        if b.get("tirage") and b["tirage"].get("resultat"):
            return {"ok": False, "erreur": "Le tirage est déjà fait"}
        vendues = [p for p in d["places"] if p["vendu"]]
        if not vendues:
            return {"ok": False, "erreur": "Aucune place vendue"}
        lots = list(sports.equipes(b.get("sport")).keys())
        graine = (b.get("tirage") or {}).get("graine_secrete")
        t = calcul.tirage([p["id"] for p in vendues], lots, graine)
        par_place = {}
        for paire in t["resultat"]:
            par_place.setdefault(paire["participant"], []).append(paire["lot"])
        # plus d'equipes que de places : les equipes restantes sont distribuees a tour de role
        restants = lots[len(vendues):] if len(vendues) < len(lots) else []
        if restants:
            melange = [x["lot"] for x in t["resultat"]]
            reste = [l for l in random_ordre(lots, t["graine"]) if l not in melange]
            for i, l in enumerate(reste):
                par_place[vendues[i % len(vendues)]["id"]].append(l)
        with _verrou:
            c = self._db()
            try:
                for pid, equipes in par_place.items():
                    c.execute("UPDATE places SET lot=? WHERE id=?", (",".join(e for e in equipes if e), pid))
                c.execute("UPDATE breaks SET tirage=?, empreinte=?, statut='tire' WHERE id=?",
                          (json.dumps({"graine": t["graine"], "empreinte": t["empreinte"], "le": _maintenant(),
                                       "methode": t["methode"], "lots": lots, "participants": [p["id"] for p in vendues],
                                       "resultat": [{"place": k, "equipes": v} for k, v in par_place.items()]}),
                           t["empreinte"], bid))
                c.commit()
            finally:
                c.close()
        return {"ok": True}

    def _place_de_equipe(self, places, mode, equipe, joueur, sport=None):
        code = calcul.code_equipe(equipe, sport)
        for p in places:
            if mode == "joueurs" and joueur and str(p["cle"]).strip().lower() == str(joueur).strip().lower():
                return p
            if mode == "divisions" and p["cle"] == calcul.division(code, sport):
                return p
            if mode == "equipes" and p["cle"] == code:
                return p
            if mode == "aleatoire" and code and code in str(p.get("lot") or "").split(","):
                return p
        return None

    def frappe_ajouter(self, bid, d):
        """Carte frappee pendant le break -> attribuee a la bonne place. Une
        carte a 2 equipes (« MTL/TOR ») : pile ou face horodate."""
        d = d or {}
        det = self.break_detail(bid)
        if not det.get("ok"):
            return det
        b, places = det["break"], det["places"]
        sport = b.get("sport")
        brutes = [calcul.code_equipe(e, sport) for e in re.split(r"\s*[/,]\s*", str(d.get("equipe") or "")) if e.strip()]
        connues = [e for e in brutes if e in sports.equipes(sport)]
        equipes = list(dict.fromkeys(connues or brutes))          # sans doublon, dans l'ordre
        multi = None
        if len(equipes) > 1:
            pf = calcul.pile_ou_face(equipes)
            multi = json.dumps({"options": equipes, "gagnant": pf["gagnant"], "graine": pf["graine"], "le": _maintenant()})
            equipe = pf["gagnant"]
        else:
            equipe = equipes[0] if equipes else ""
        place = self._place_de_equipe(places, b["mode"], equipe, d.get("joueur"), sport)
        with _verrou:
            c = self._db()
            try:
                fid = c.execute("INSERT INTO frappes (break_id, carte, joueur, equipe, valeur, place_id, tirage_multi, cree_le) "
                                "VALUES (?,?,?,?,?,?,?,?)",
                                (bid, d.get("carte") or "", d.get("joueur") or "", calcul.code_equipe(equipe, sport),
                                 _float(d.get("valeur")), place["id"] if place else None, multi, _maintenant())).lastrowid
                c.commit()
            finally:
                c.close()
        return {"ok": True, "id": fid, "place": place, "pile_ou_face": json.loads(multi) if multi else None}

    def frappe_maj(self, fid, champs):
        ok = {k: v for k, v in (champs or {}).items() if k in ("envoye", "suivi", "place_id", "valeur", "carte")}
        if not ok:
            return {"ok": False}
        with _verrou:
            c = self._db()
            try:
                c.execute(f"UPDATE frappes SET {', '.join(k + '=?' for k in ok)} WHERE id=?", list(ok.values()) + [fid])
                c.commit()
            finally:
                c.close()
        return {"ok": True}

    def frappe_supprimer(self, fid):
        with _verrou:
            c = self._db()
            try:
                c.execute("DELETE FROM frappes WHERE id=?", (fid,))
                c.commit()
            finally:
                c.close()
        return {"ok": True}

    def break_envois(self, bid):
        """Par acheteur : ses places et ses cartes frappees, a envoyer."""
        d = self.break_detail(bid)
        if not d.get("ok"):
            return d
        par_place = {p["id"]: p for p in d["places"]}
        acheteurs = {}
        for f in d["frappes"]:
            p = par_place.get(f["place_id"])
            nom = (p or {}).get("acheteur") or ("(place non vendue)" if p else "(sans place)")
            a = acheteurs.setdefault(nom, {"acheteur": nom, "places": set(), "cartes": [], "a_envoyer": 0})
            if p:
                a["places"].add(p["libelle"] + (f" ({p['lot']})" if p.get("lot") else ""))
            a["cartes"].append(f)
            a["a_envoyer"] += 0 if f["envoye"] else 1
        out = sorted(({**a, "places": sorted(a["places"])} for a in acheteurs.values()), key=lambda a: -a["a_envoyer"])
        return {"ok": True, "acheteurs": out}

    def break_csv_envois(self, bid):
        e = self.break_envois(bid)
        s = io.StringIO()
        w = csv.writer(s)
        w.writerow(["Acheteur", "Places", "Carte", "Joueur", "Équipe", "Valeur", "Envoyée", "Suivi"])
        for a in e.get("acheteurs") or []:
            for f in a["cartes"]:
                w.writerow([a["acheteur"], " | ".join(a["places"]), f["carte"], f["joueur"], f["equipe"],
                            f["valeur"] or "", "oui" if f["envoye"] else "non", f["suivi"] or ""])
        return {"ok": True, "csv": s.getvalue(), "nom": f"envois_break_{bid}.csv"}

    def break_public(self, jeton):
        """Page de transparence (lecture seule) : places, prix, tirage, cartes."""
        with _verrou:
            c = self._db()
            try:
                b = c.execute("SELECT id FROM breaks WHERE jeton=?", (jeton,)).fetchone()
            finally:
                c.close()
        if not b:
            return None
        d = self.break_detail(b["id"])
        br = d["break"]
        t = br.get("tirage") or {}
        if t.get("graine_secrete"):
            t = {"engage": True}             # la graine reste secrete jusqu'au tirage
        prod = next((p for p in self.produits_liste() if p["id"] == br["produit_id"]), None)
        lignes_ck = self.checklist(prod["id"]) if prod else []
        if not prod and br.get("catalogue_id"):
            pc = catalogue.charger(br["catalogue_id"])
            if pc:
                prod = {"nom": pc["nom"], "format": (pc.get("formats") or [{}])[0].get("format") or "Boîte"}
                lignes_ck = [{"equipe": c.get("equipe"), "recrue": 1 if c.get("recrue") else 0, "auto": 1 if c.get("auto") else 0,
                              "tirage": c.get("tirage")} for c in pc["cartes"]]
        resume = {}
        if prod:
            for k in lignes_ck:
                for code in dict.fromkeys(calcul.code_equipe(e, br.get("sport")) for e in re.split(r"\s*[/,]\s*", str(k["equipe"] or "?")) if e.strip()):
                    r = resume.setdefault(code, {"nb": 0, "recrues": 0, "autos": 0, "numerotees": 0})
                    r["nb"] += 1
                    r["recrues"] += k["recrue"] or 0
                    r["autos"] += k["auto"] or 0
                    r["numerotees"] += 1 if k["tirage"] else 0

        def masque(nom):
            nom = str(nom or "")
            return (nom[:2] + "•" * max(1, len(nom) - 3) + nom[-1:]) if len(nom) > 3 else ("•" * len(nom))
        return {"nom": br["nom"], "mode": br["mode"], "cree_le": br["cree_le"], "statut": br["statut"],
                "sport": sports.valide(br.get("sport")), "equipes": {k: v[0] for k, v in sports.equipes(br.get("sport")).items()},
                "empreinte": br.get("empreinte"), "tirage": t, "produit": prod and {"nom": prod["nom"], "format": prod["format"]},
                "boites": br["boites"],
                "places": [{"cle": p["cle"], "libelle": p["libelle"], "prix": p["prix"], "acheteur": masque(p["acheteur"]) if p["vendu"] else None,
                            "lot": p["lot"], "id": p["id"]} for p in d["places"]],
                "frappes": [{"carte": f["carte"], "joueur": f["joueur"], "equipe": f["equipe"], "place_id": f["place_id"],
                             "pile_ou_face": json.loads(f["tirage_multi"]) if f["tirage_multi"] else None, "le": f["cree_le"]}
                            for f in d["frappes"]],
                "resume_equipes": resume}

    # -- inventaire -------------------------------------------------------------------------------
    CHAMPS_CARTE = ("titre", "joueur", "annee", "marque", "set_nom", "numero", "parallele", "tirage", "auto", "grade", "equipe",
                    "cout", "valeur", "prix_demande", "emplacement", "statut", "item_number", "sku", "consignataire_id", "source",
                    "note", "client_id", "sport", "recrue", "relique", "cert", "photo", "photos", "photos_orig", "studio_v")

    def inventaire_liste(self, filtres=None):
        f = filtres or {}
        try:
            self._reparer_soumissions()
        except Exception as e:
            print("Soumissions (reparation) : " + repr(e), flush=True)
        sql, args = "SELECT * FROM cartes WHERE 1=1", []
        if f.get("statut"):
            sql += " AND statut=?"
            args.append(f["statut"])
        if f.get("dispo"):
            sql += " AND statut!='Vendue'"
        if f.get("consignation"):
            sql += " AND consignataire_id IS NOT NULL"
        if f.get("sans_cout"):                       # 22 oct 2026 - « Cout manquant » de l'accueil
            sql += " AND statut!='Vendue' AND cout IS NULL"
        if f.get("a_lister"):
            sql += " AND statut='En stock' AND COALESCE(emplacement,'') NOT IN ('Magasin','Collection')"
        if f.get("emplacement"):
            sql += " AND emplacement=?"
            args.append(f["emplacement"])
        if f.get("q"):
            sql += " AND (titre LIKE ? OR joueur LIKE ? OR set_nom LIKE ? OR sku LIKE ?)"
            args += [f"%{f['q']}%"] * 4
        if f.get("sport"):                           # 4 nov 2026 (revue) : avant la limite (le sport devine est refiltre plus bas)
            sql += " AND (sport=? OR sport IS NULL OR sport='')"
            args.append(f["sport"])
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(max(1, min(5000, int(f.get("limite") or 2000))))      # 4 nov 2026 : 500 cachait le reste d'un gros inventaire
        with _verrou:
            c = self._db()
            try:
                # 4 nov 2026 (vitesse) : sans l'examen complet de chaque carte (des dizaines de Ko) : la note seulement
                cols = [r[1] for r in c.execute("PRAGMA table_info(cartes)") if r[1] != "etat_json"]
                sel = ", ".join('"%s"' % k for k in cols) + (", json_extract(etat_json, '$.note_min') AS _nmin, json_extract(etat_json, '$.note_max') AS _nmax"
                                                              if len(cols) < len([1 for _ in c.execute("PRAGMA table_info(cartes)")]) else "")
                try:
                    out = _dicts(c.execute(sql.replace("SELECT *", "SELECT " + sel, 1), args))
                except sqlite3.OperationalError:       # etat_json pas en JSON valide quelque part : l'ancienne lecture
                    out = _dicts(c.execute(sql, args))
            finally:
                c.close()
        defaut = self.reglages_lire().get("sport") or sports.DEFAUT
        try:                                     # 3 nov 2026 : la variation du prix de chaque carte (7, 30, 90 jours)
            import tendance_cartes
            tend = tendance_cartes.lire(self)
        except Exception as e:
            print("Tendance des cartes (lecture) : " + repr(e), flush=True)
            tend = {}
        for r_ in out:
            if r_.get("statut") != "Vendue" and r_.get("id") in tend:
                r_["tendance"] = tend[r_["id"]]
        # 24 oct 2026 - repere prix : ton prix face aux memes cartes en vente (sante : mediane, plus bas, nombre)
        with _verrou:
            c = self._db()
            try:
                marche = {r["item_number"]: r for r in _dicts(c.execute(
                    "SELECT item_number, mediane, n, bas, verdict, ecart, suggestion, maj FROM sante"))}
            finally:
                c.close()
        for r in out:
            # 1er nov 2026 (Mathieu : « dans la vue collection, chaque carte comme dans un slab, le score = celui calcule par
            # l'IA ») : la note estimee seulement (min, max), pas tout l'examen (lourd)
            nmin, nmax = r.pop("_nmin", None), r.pop("_nmax", None)
            if nmin is not None:
                r["note_ia"] = {"min": nmin, "max": nmax if nmax is not None else nmin}
            ej = r.pop("etat_json", None)
            if ej:
                try:
                    e = json.loads(ej) or {}
                except ValueError:
                    e = {}
                if e.get("note_min") is not None:
                    r["note_ia"] = {"min": e.get("note_min"), "max": e.get("note_max") if e.get("note_max") is not None else e.get("note_min")}
            if not r.get("sport"):
                r["sport"] = sports.detecter(r.get("titre"), r.get("equipe"), r.get("set_nom"), r.get("marque"), defaut=defaut)
            m = marche.get(r.get("item_number")) if r.get("statut") != "Vendue" else None
            if m and m.get("mediane"):
                r["marche"] = {k: m[k] for k in ("mediane", "n", "bas", "verdict", "ecart", "suggestion", "maj")}
        import forfaits                          # Gratuit : le repere prix sur 3 cartes (les autres : « Pro »)
        if not ebay_prix_actif():                # interrupteur : pas de repere prix sur les annonces eBay
            for r_ in out:
                r_.pop("marche", None)
        elif not forfaits.est_pro():
            vus = 0
            for r in out:
                if r.get("marche"):
                    vus += 1
                    if vus > forfaits.LIMITES["repere"]:
                        r.pop("marche")
                        r["marche_pro"] = True
        # 5 nov 2026 (Mathieu : « les cartes achetees il y a plus de 3 mois : un tag pour les afficher sur eBay ») : une carte
        # en stock, pas sur eBay, ni en collection ni en envoi, achetee (achat eBay relie, sinon entree dans l'app) il y a
        # plus de 90 jours -> « A mettre sur eBay »
        try:
            with _verrou:
                c = self._db()
                try:
                    c.execute(self._SQL_ACHATS)
                    achat_le = {r[0]: r[1] for r in c.execute("SELECT carte_id, MIN(date) FROM achats_ebay WHERE carte_id IS NOT NULL GROUP BY carte_id")}
                finally:
                    c.close()
        except Exception:
            achat_le = {}
        lim90 = (datetime.now() - timedelta(days=AFFICHER_APRES_J)).strftime("%Y-%m-%d")
        for r in out:
            le = str(achat_le.get(r.get("id")) or r.get("cree_le") or "")[:10]
            r["achete_le"] = le or None
            r["a_afficher"] = bool(le and le <= lim90 and r.get("statut") == "En stock"
                                   and (r.get("emplacement") or "") not in ("Collection", "eBay") and not r.get("envoi_json"))
        for r in out:                            # 9 nov 2026 : preparee pour la vente, pas encore sur eBay
            r["a_finir"] = bool(r.get("a_finir_le") and r.get("statut") == "En stock" and not r.get("item_number")
                                and (r.get("emplacement") or "") not in ("Collection", "eBay") and not r.get("envoi_json"))
        if f.get("a_afficher"):
            out = [r for r in out if r.get("a_afficher")]
        if f.get("a_finir"):
            out = [r for r in out if r.get("a_finir")]
        if f.get("sport"):
            out = [r for r in out if r["sport"] == f["sport"]]
        return out

    def carte_comps(self, item_number):
        """Les memes cartes en vente (gardees par cartes_match) pour une de tes annonces."""
        if not ebay_prix_actif():
            return {"ok": True, "comps": [], "n": 0, "coupe": True}
        with _verrou:
            c = self._db()
            try:
                r = c.execute("SELECT comps, mediane, n, bas, maj, requete FROM sante WHERE item_number=?", (str(item_number),)).fetchone()
            finally:
                c.close()
        if not r:
            return {"ok": True, "comps": [], "n": 0}
        try:
            comps = json.loads(r["comps"] or "[]")
        except ValueError:
            comps = []
        # 27 oct 2026 (licence eBay §8.1) : des annonces eBay de plus de 6 h ne sont plus montrees (la mediane, elle, vient
        # des ventes reelles)
        try:
            vieux = (datetime.now() - datetime.fromisoformat(str(r["maj"])[:19])).total_seconds() > 6 * 3600
        except (TypeError, ValueError):
            vieux = True
        if vieux:
            return {"ok": True, "comps": [], "mediane": r["mediane"], "n": r["n"], "bas": None, "maj": r["maj"],
                    "requete": r["requete"], "a_rafraichir": True}
        return {"ok": True, "comps": comps, "mediane": r["mediane"], "n": r["n"], "bas": r["bas"], "maj": r["maj"], "requete": r["requete"]}

    def _photos_vendues(self, n=25):
        """Cartes vendues sans photo : la photo de l'annonce terminee (Trading GetItem, 90 jours). Peu d'appels par synchro."""
        with _verrou:
            c = self._db()
            try:
                lst = [r[0] for r in c.execute("SELECT item_number FROM cartes WHERE statut='Vendue' AND item_number IS NOT NULL "
                                               "AND COALESCE(photo,'')='' ORDER BY vendu_le DESC LIMIT ?", (int(n),))]
            finally:
                c.close()
        faites = 0
        for item in lst:
            try:
                u = ebay_compte.photo_item(item)
            except (RuntimeError, OSError):
                break
            with _verrou:
                c = self._db()
                try:
                    c.execute("UPDATE cartes SET photo=? WHERE item_number=? AND COALESCE(photo,'')=''", (u or "-", item))
                    c.commit()
                finally:
                    c.close()
            faites += 1
        return faites

    def carte_sauver(self, d):
        d = {k: v for k, v in (d or {}).items() if k in self.CHAMPS_CARTE or k == "id"}
        for k in ("cout", "valeur", "prix_demande"):
            if k in d:
                d[k] = _float(d[k])
        if "tirage" in d:
            d["tirage"] = _int(d["tirage"])
        # 4 nov 2026 (revue) : une mise a jour partielle (statut, prix...) n'efface plus le titre ; vide expres -> refait
        # avec toute la fiche
        if not d.get("id"):
            if not d.get("titre"):
                d["titre"] = ebay_csv.titre_annonce(d)
        elif "titre" in d and not d.get("titre"):
            d["titre"] = ebay_csv.titre_annonce(dict(self.carte_lire(d["id"]) or {}, **{k: v for k, v in d.items() if k != "titre"}))
        # 23 oct 2026 - sport devine (titre, equipe, produit, joueur connu), sinon le sport principal
        if d.get("sport"):
            d["sport"] = sports.valide(d["sport"])
        elif not d.get("id"):                 # a la creation seulement : un choix fait a la main reste
            d["sport"] = self.sport_de(d)
        with _verrou:
            c = self._db()
            try:
                if d.get("id"):
                    cid = d.pop("id")
                    if d:
                        if "item_number" in d:       # 4 nov 2026 : une NOUVELLE annonce n'a pas encore ete vue chez eBay
                            c.execute("UPDATE cartes SET vu_actif_le=NULL WHERE id=? AND COALESCE(item_number,'')<>?",
                                      (cid, str(d.get("item_number") or "")))
                        c.execute(f"UPDATE cartes SET {', '.join(k + '=?' for k in d)} WHERE id=?", list(d.values()) + [cid])
                else:
                    d.setdefault("statut", "En stock")
                    d.setdefault("emplacement", "Réserve")
                    d["cree_le"] = _maintenant()
                    cid = c.execute(f"INSERT INTO cartes ({', '.join(d)}) VALUES ({', '.join('?' * len(d))})", list(d.values())).lastrowid
                c.commit()
            finally:
                c.close()
        return {"ok": True, "id": cid}

    def carte_lire(self, cid):
        with _verrou:
            c = self._db()
            try:
                r = c.execute("SELECT * FROM cartes WHERE id=?", (cid,)).fetchone()
            finally:
                c.close()
        return dict(r) if r else {}

    def carte_garder(self, d):
        """27 oct 2026 - assistant de vente, « Garder dans mon inventaire » : la carte preparee (fiche, titre, prix, photos
        studio) entre dans l'inventaire (En stock), prete a publier plus tard d'un tap. Rien ne part chez eBay."""
        import photos_cartes
        d = dict(d or {})
        # 9 nov 2026 (Mathieu : le lot « Server unreachable » quand il quitte l'app 2 s) : l'app refait l'envoi au retour ; la
        # cle de l'envoi fait qu'une carte deja gardee (la reponse s'etait perdue) n'est jamais creee en double
        cle = str(d.get("cle") or "")
        cle = cle if re.fullmatch(r"[A-Za-z0-9_-]{8,40}", cle) and not d.get("cid") else ""
        if cle:
            c = self._db()
            try:
                c.execute("CREATE TABLE IF NOT EXISTS garder_cles (cle TEXT PRIMARY KEY, id INTEGER, le REAL)")
                c.execute("DELETE FROM garder_cles WHERE le < ?", (time.time() - 86400,))
                c.commit()
                row = c.execute("SELECT id FROM garder_cles WHERE cle=?", (cle,)).fetchone()
            finally:
                c.close()
            deja = self.carte_lire(row[0]) if row else None
            if deja:
                try:
                    ph = json.loads(deja.get("photos") or "[]")
                except ValueError:
                    ph = []
                return {"ok": True, "id": deja["id"], "photos": ph, "deja": True}
        carte = {k: v for k, v in (d.get("carte") or {}).items() if k in self.CHAMPS_CARTE and k not in ("id", "photo", "photos", "photos_orig", "studio_v", "statut")}
        try:
            refs = photos_cartes.sauver(d.get("photos") or [])
            # 31 oct 2026 (Mathieu : « les photos pas deja modifiees comme dans seller ») : on montre la photo studio ;
            # l'originale est gardee a cote pour refaire le fond (et son niveau de flou) au moment de vendre
            orig = d.get("originales") or []
            refs_o = photos_cartes.sauver(orig) if orig and list(orig) != list(d.get("photos") or []) else []
        except ValueError as e:
            return {"ok": False, "erreur": str(e)}
        titre = re.sub(r"\s+", " ", str(d.get("titre") or "")).strip()[:80]
        champs = {**carte, "titre": titre or None, "prix_demande": _float(d.get("prix")), "cout": _float(d.get("cout")),
                  "photo": refs[0] if refs else None, "photos": json.dumps(refs) if refs else None,
                  "photos_orig": json.dumps(refs_o) if refs_o else None, "studio_v": STUDIO_V if refs_o else None}
        if d.get("cid"):
            champs["id"] = d["cid"]
        else:
            champs["statut"] = "En stock"
        r = self.carte_sauver({k: v for k, v in champs.items() if v not in (None, "")})
        # 9 nov 2026 (Mathieu : « un onglet pending : la personne part avant de finir, elle revient et reprend ses cartes pour
        # les mettre sur eBay en lot ») : une carte preparee pour la VENTE (pas la collection) est marquee « a finir »
        if not d.get("cid") and (carte.get("emplacement") or "") != "Collection":
            c = self._db()
            try:
                c.execute("UPDATE cartes SET a_finir_le=? WHERE id=?", (datetime.now().strftime("%Y-%m-%d %H:%M"), r["id"]))
                c.commit()
            finally:
                c.close()
        if cle:
            c = self._db()
            try:
                c.execute("INSERT OR REPLACE INTO garder_cles VALUES (?,?,?)", (cle, r["id"], time.time()))
                c.commit()
            finally:
                c.close()
        return {"ok": True, "id": r["id"], "photos": refs, "achat_lie": self._lier_achat_choisi(r["id"], d.get("achat"))}

    def _fusionner_depuis(self, source):
        """9 nov 2026 (Mathieu : 2 comptes, « Mathieu Bourassa » sur le cell et « hallofcardz » sur l'ordi ; « un moyen beton
        pour que ca n'arrive pas aux utilisateurs ») : quand une connexion (Apple, Google) d'un AUTRE compte est reliee a
        celui-ci, ses cartes (collection, inventaire, a finir), leurs photos et sa watchlist sont copiees ici, sans doublon.
        L'ancien compte garde tout (rien n'est efface) et renvoie ensuite vers celui-ci. Prive (jamais appele par l'app)."""
        import photos_cartes
        import shutil
        import sqlite3
        import watchlist as _wl
        cible = comptes.courant()
        if not cible or not source or source == cible or source not in comptes.lister():
            return {"ok": False, "erreur": "rien a fusionner"}
        if comptes.info(source).get("fusionne_dans"):
            return {"ok": True, "deja": True}
        with comptes.utiliser(source):
            ch_src, ph_src = self.chemin_db, photos_cartes.dossier()
        cartes, wl = [], []
        if os.path.isfile(ch_src):
            c = sqlite3.connect(ch_src, timeout=30)
            c.row_factory = sqlite3.Row
            try:
                for t, l in (("cartes", cartes), ("watchlist", wl)):
                    try:
                        l += [dict(r) for r in c.execute(f"SELECT * FROM {t}")]
                    except sqlite3.OperationalError:
                        pass
            finally:
                c.close()
        ph_dst = photos_cartes.dossier()

        def copier(ref):
            nom = str(ref or "").rsplit("/", 1)[-1]
            if photos_cartes._NOM.fullmatch(nom) and os.path.isfile(os.path.join(ph_src, nom)) and not os.path.exists(os.path.join(ph_dst, nom)):
                shutil.copy2(os.path.join(ph_src, nom), os.path.join(ph_dst, nom))
        n_c = n_w = 0
        with _verrou:
            c = self._db()
            try:
                cols = [r[1] for r in c.execute("PRAGMA table_info(cartes)") if r[1] != "id"]
                deja_items = {r[0] for r in c.execute("SELECT item_number FROM cartes WHERE item_number IS NOT NULL")}
                deja_t = {(r[0] or "", r[1] or "") for r in c.execute("SELECT titre, photo FROM cartes")}
                for k in cartes:
                    if (k.get("item_number") and k["item_number"] in deja_items) or ((k.get("titre") or "", k.get("photo") or "") in deja_t):
                        continue
                    for champ in ("photo", "photos", "photos_orig"):
                        v = k.get(champ)
                        try:
                            refs = json.loads(v) if champ != "photo" and v else ([v] if v else [])
                        except ValueError:
                            refs = []
                        for r_ in refs if isinstance(refs, list) else []:
                            copier(r_)
                    d = {x: k.get(x) for x in cols if x in k}
                    for x in ("soumission_id", "consignataire_id", "client_id"):     # des liens vers des tables de l'autre compte
                        if x in d:
                            d[x] = None
                    c.execute(f"INSERT INTO cartes ({', '.join(d)}) VALUES ({', '.join('?' * len(d))})", list(d.values()))
                    n_c += 1
                c.commit()
            finally:
                c.close()
        if wl:
            c = _wl._cx(self)
            try:
                wcols = [r[1] for r in c.execute("PRAGMA table_info(watchlist)")]
                for w in wl:
                    d = {x: w.get(x) for x in wcols if x in w}
                    n_w += c.execute(f"INSERT OR IGNORE INTO watchlist ({', '.join(d)}) VALUES ({', '.join('?' * len(d))})", list(d.values())).rowcount
                c.commit()
            finally:
                c.close()
        comptes.maj(source, fusionne_dans=cible, fusionne_le=datetime.now().isoformat(timespec="seconds"))
        print(f"Fusion de comptes : {n_c} cartes, {n_w} suivies", flush=True)
        return {"ok": True, "cartes": n_c, "watchlist": n_w}

    def scan_decouper(self, devant, dos=None):
        """9 nov 2026 (Mathieu : les cartes scannees a l'ordi, plusieurs par page) : une page de numeriseur -> une photo par
        carte (et, si on donne aussi le scan des dos, chaque dos avec son devant). Rien n'est lu par l'IA ici (gratuit)."""
        import examen
        import photos_cartes
        import scans

        def ouvrir(u):
            brut = examen.data_url_octets(u)
            if len(brut) > 40_000_000:
                raise ValueError("Scan trop lourd (40 Mo au plus)")
            im = examen.ouvrir(brut)
            if im.size[0] * im.size[1] > photos_cartes.MAX_PIXELS:
                im.thumbnail((8000, 8000))
            return im
        try:
            dv = scans.decouper(ouvrir(devant))
            ds = scans.decouper(ouvrir(dos)) if dos else []
        except (ValueError, OSError) as e:
            return {"ok": False, "erreur": str(e) or "Scan illisible"}
        if not dv:
            return {"ok": False, "erreur": "Aucune carte trouvée sur ce scan : laisse un peu d’espace entre les cartes, couvercle fermé"}
        paires = scans.apparier(dv, ds) if ds else [None] * len(dv)
        cartes = [{"devant": scans.jpeg_data_url(c["image"], cote=2400), "dos": scans.jpeg_data_url(ds[j]["image"], cote=2400) if j is not None else None,
                   "centre": c["centre"]} for c, j in zip(dv, paires)]
        return {"ok": True, "cartes": cartes, "n": len(cartes), "dos_sans_devant": max(0, len(ds) - sum(1 for j in paires if j is not None))}

    def cartes_a_finir_retirer(self, ids):
        """9 nov 2026 : « Retirer de À finir » : la carte reste dans l'inventaire, elle ne compte plus comme a finir."""
        ids = [int(i) for i in (ids or []) if str(i).isdigit()][:500]
        if not ids:
            return {"ok": True, "n": 0}
        c = self._db()
        try:
            c.execute(f"UPDATE cartes SET a_finir_le=NULL WHERE id IN ({','.join('?' * len(ids))})", ids)
            c.commit()
        finally:
            c.close()
        return {"ok": True, "n": len(ids)}

    def carte_photo_changer(self, cid, photo, index=0):
        """28 oct 2026 (Mathieu : « en tout temps il peut modifier la photo associee a la carte dans sa collection pour
        en prendre une meilleure ») : la nouvelle photo devient la premiere ; l'ancienne premiere est effacee du disque.
        9 nov 2026 (« changer la photo ne me donne pas acces a ma bibliotheque ») : index 1 = le dos (ajoute s'il manque)."""
        try:
            index = 1 if int(index or 0) == 1 else 0
        except (TypeError, ValueError):
            index = 0
        import photos_cartes
        carte = self.carte_lire(cid)
        if not carte:
            return {"ok": False, "erreur": "Carte introuvable"}
        try:
            refs = photos_cartes.sauver([photo])
        except ValueError as e:
            return {"ok": False, "erreur": str(e)}
        if not refs:
            return {"ok": False, "erreur": "Photo illisible : reprends-la"}
        try:
            avant = json.loads(carte.get("photos") or "[]")
            avant = avant if isinstance(avant, list) else []
        except ValueError:
            avant = []
        if not avant and carte.get("photo"):
            avant = [carte["photo"]]
        if index == 1 and not avant:
            index = 0                                        # pas de devant : la photo devient le devant
        remplace = lambda l: (l[:index] + refs[:1] + l[index + 1:]) if len(l) > index else (l + refs[:1])
        nouv = remplace(list(avant))
        maj = {"id": cid, "photo": nouv[0], "photos": json.dumps(nouv)}
        try:
            orig = json.loads(carte.get("photos_orig") or "[]")
        except ValueError:
            orig = []
        if isinstance(orig, list) and orig:                  # la nouvelle photo devient aussi l'originale de cette face
            if len(orig) > index and orig[index] not in nouv:
                try:
                    photos_cartes.supprimer([orig[index]])
                except Exception:
                    pass
            maj["photos_orig"] = json.dumps(remplace(list(orig)))
        self.carte_sauver(maj)
        if len(avant) > index and avant[index] not in nouv:
            try:
                photos_cartes.supprimer([avant[index]])
            except Exception:
                pass
        return {"ok": True, "photo": nouv[0], "photos": nouv}

    def carte_photos_studio(self, cid, photos, v=None):
        """31 oct 2026 (Mathieu : « la photo est pas centree », puis « mauvais cropping de la photo de face ») : les cartes
        gardees avant la photo studio, ou recadrees par une version plus ancienne du recadrage (studio_v). L'ecran recadre
        dans le telephone A PARTIR DES ORIGINALES et envoie le resultat ici ; les originales restent gardees a cote."""
        import photos_cartes
        v = int(v or 1)
        carte = self.carte_lire(cid)
        if not carte:
            return {"ok": False, "erreur": "Carte introuvable"}
        if carte.get("photos_orig") and int(carte.get("studio_v") or 0) >= v:
            return {"ok": True, "deja": True}
        lire = lambda k: (lambda x: x if isinstance(x, list) else [])(json.loads(carte.get(k) or "[]"))
        try:
            avant, orig = lire("photos"), lire("photos_orig")
        except ValueError:
            avant, orig = [], []
        avant = avant or ([carte["photo"]] if carte.get("photo") else [])
        base = orig or avant
        photos = list(photos or [])[:len(base)]
        if not base or not photos:
            return {"ok": False, "erreur": "Aucune photo"}
        try:
            refs = photos_cartes.sauver(photos)
        except ValueError as e:
            return {"ok": False, "erreur": str(e)}
        if len(refs) != len(photos):
            return {"ok": False, "erreur": "Photo illisible"}
        refs += base[len(refs):]
        self.carte_sauver({"id": cid, "photo": refs[0], "photos": json.dumps(refs), "photos_orig": json.dumps(base), "studio_v": v})
        vieux = [x for x in avant if x not in refs and x not in base] if orig else []      # l'ancien recadrage seulement
        if vieux:
            try:
                photos_cartes.supprimer(vieux)
            except Exception:
                pass
        return {"ok": True, "photos": refs}

    def carte_etat(self, cid, forcer=False, langue=None, d=None):
        """L'etat estime d'une carte (pre-gradation). d (facultatif) = {photos: [devant, dos] (data URL : les photos
        d'EXAMEN prises pour l'occasion), quads: [coins devant, coins dos] (0..1000, trouves dans le telephone), rasante:
        data URL}. Sans photos : celles de la fiche (les originales : la photo studio met un halo qui cache les aretes).
        1er nov 2026 (Mathieu : « je veux qu'on soit PARFAIT ») : zooms des coins et des bords, centrage mesure, regles de
        coherence, calibration sur les vraies notes revenues de PSA, et ce que les utilisateurs ont confirme ou rejete."""
        import base64
        import etat_verite
        import photos_cartes
        d = dict(d or {})
        carte = self.carte_lire(cid)
        if not carte:
            return {"ok": False, "erreur": "Carte introuvable"}
        try:
            refs = json.loads(carte.get("photos_orig") or "[]") or json.loads(carte.get("photos") or "[]") or ([carte["photo"]] if carte.get("photo") else [])
        except ValueError:
            refs = []
        refs = [r for r in refs if photos_cartes.chemin(r)][:2]
        try:
            garde = json.loads(carte.get("etat_json") or "null")
        except ValueError:
            garde = None
        precision = etat_verite.precision()
        if forcer is None:                     # lecture seule (l'ecran demande ce qui est garde, sans payer une analyse)
            if garde and (garde.get("examen") or garde.get("photos") == refs):
                garde = self._recentrer(cid, garde)       # 2 nov 2026 : aretes et centrage refaits une fois (sans IA)
                try:                                      # 9 nov 2026 : les points des defauts sur la vraie arete
                    garde = self._caler_defauts(cid, garde)
                except Exception as e_:
                    print("Calage des defauts : " + repr(e_), flush=True)
                garde = self._sans_texture_relique(carte, garde)
                garde = self._coherent(garde)
                return {"ok": True, **garde, "le": carte.get("etat_le"), "precision": precision}
            try:
                q = vision.statut_etat()
            except Exception:
                q = {}
            return {"ok": True, "aucun": True, "photos_changees": bool(garde), "quota": q, "precision": precision}
        if not self.reglages_lire().get("ia_photos_ok"):
            return {"ok": False, "erreur": "Permission de lecture par l’IA requise", "consentement_requis": True}
        try:                                   # 3 nov 2026 (revue de securite) : le quota AVANT tout travail sur les images
            if vision.disponible():
                vision._verifier_etat()
        except vision.Erreur as e:
            return {"ok": False, "erreur": str(e)}
        examen_ = bool(d.get("photos"))
        nouveaux = []                          # 3 nov 2026 (revue) : les photos gardees par CET appel (effacees s'il echoue)
        _entrees = {str(x) for x in (d.get("photos") or []) + [d.get("rasante"), d.get("rasante2")]
                    + [g.get("photo") for g in (d.get("gros_plans") or []) if isinstance(g, dict)] if x}
        _neufs = lambda: [r for r in nouveaux if str(r).startswith("/mes-photos/") and str(r) not in _entrees]   # jamais une photo deja gardee
        if examen_:                            # photos d'examen : gardees a part (les photos de la fiche ne changent pas)
            try:
                refs = photos_cartes.sauver(list(d["photos"])[:2])
                nouveaux += [r for r in refs if r not in (garde or {}).get("photos", [])]
                ras_ref = photos_cartes.sauver([d["rasante"]] + ([d["rasante2"]] if d.get("rasante2") else [])) if d.get("rasante") else []
                nouveaux += ras_ref
                # 3 nov 2026 : les gros plans des coins (facultatifs), gardes avec l'examen
                import bareme as _b
                gps = []
                for g in (d.get("gros_plans") or [])[:8]:
                    if isinstance(g, dict) and g.get("photo") and g.get("coin") in _b.COINS and g.get("face") in ("devant", "dos") \
                            and not any(x["face"] == g["face"] and x["coin"] == g["coin"] for x in gps):
                        rr = photos_cartes.sauver([g["photo"]])
                        nouveaux += rr
                        if rr:
                            gps.append({"face": g["face"], "coin": g["coin"], "ref": rr[0]})
            except ValueError as e:
                photos_cartes.supprimer(_neufs())
                return {"ok": False, "erreur": str(e)}
        else:
            ras_ref, gps = [], []
        if not refs:
            return {"ok": False, "erreur": "Ajoute une photo de la carte (devant, et dos si possible)"}
        lire_b64 = lambda r: "data:image/jpeg;base64," + base64.b64encode(open(photos_cartes.chemin(r), "rb").read()).decode()
        photos = [lire_b64(r) for r in refs]
        quads = [q if isinstance(q, list) and len(q) == 4 else None for q in (d.get("quads") or [])][:2]
        quads = self._affiner_quads(refs, quads)         # 2 nov 2026 : les aretes ajustees sur la photo pleine resolution
        try:
            res = vision.etat(photos, langue or self.reglages_lire().get("langue") or "fr", quads=quads,
                              rasante=lire_b64(ras_ref[0]) if ras_ref else None,
                              rasante2=lire_b64(ras_ref[1]) if len(ras_ref) > 1 else None,
                              gros_plans=[{"face": g["face"], "coin": g["coin"], "photo": lire_b64(g["ref"])} for g in gps],
                              calibration=etat_verite.calibration(), regles=etat_verite.regles(),
                              contexte={"titre": carte.get("titre"), "relique": bool(carte.get("relique")) or bool(_RE_RELIQUE.search(str(carte.get("titre") or "") + " " + str(carte.get("parallele") or ""))),
                                        "auto": bool(carte.get("auto")), "slab": bool(d.get("slab"))})
        except vision.Erreur as e:
            photos_cartes.supprimer(_neufs())
            return {"ok": False, "erreur": str(e)}
        except Exception:
            photos_cartes.supprimer(_neufs())
            raise
        res = {k: v for k, v in res.items() if k not in ("ok", "cache")}
        qu = res.pop("quads_utilises", None) or []          # 3 nov 2026 (revue) : le contour trouve par l'app, s'il n'y en avait pas
        # 9 nov 2026 (Mathieu : « le cercle encercle rien ; c'est le coin qu'il faut encercler ») : le contour AFFINE par
        # l'examen (celui que l'IA a vu, aretes trouvees sur la photo pleine resolution) passe avant le contour approximatif du
        # telephone : les zooms des defauts tombent sur la vraie arete
        quads = [(qu[i] if i < len(qu) and qu[i] else q) for i, q in enumerate(quads + [None] * (len(refs) - len(quads)))][:len(refs)]
        res.update(photos=refs, quads=quads, examen=examen_, rasante=ras_ref[0] if ras_ref else None, rasante2=ras_ref[1] if len(ras_ref) > 1 else None)
        if gps:
            q_ = {(g.get("face"), g.get("coin")): g for g in res.pop("gros_plans_q", None) or []}
            res["gros_plans"] = [dict(g, net=(q_.get((g["face"], g["coin"])) or {}).get("net")) for g in gps]
        else:
            res.pop("gros_plans_q", None)
        # 3 nov 2026 : l'image du RELIEF (une photo rasante, ou la difference de deux eclairages), gardee pour l'ecran
        if ras_ref:
            try:
                import examen as _ex
                import mesures as _mz
                ims = [_ex.ouvrir(open(photos_cartes.chemin(r), "rb").read()) for r in ras_ref[:2]]
                rl = _mz.difference_eclairages(ims[0], ims[1]) if len(ims) > 1 else {"image": _mz.relief(ims[0])}
                if rl and rl.get("image") is not None:
                    res["relief_img"] = photos_cartes.sauver(["data:image/jpeg;base64," + base64.b64encode(_ex.jpeg(rl["image"], 1200, 85)).decode()])[0]
                    res["relief_deux"] = len(ims) > 1
            except Exception as x:
                print("Relief : " + repr(x), flush=True)
        res["centrage_vue"] = self._reperes_vue(self._centrage_vue(refs, quads), res.get("centrage_reperes"))
        res["centrage_algo"] = self.CENTRAGE_ALGO
        anciens = [v.get("img") for v in ((garde or {}).get("centrage_vue") or {}).values() if v.get("img")]
        if garde and garde.get("examen"):      # l'ancien examen : ses photos a lui ne servent plus
            anciens += [x for x in (garde.get("photos") or []) + [garde.get("rasante"), garde.get("rasante2"), garde.get("relief_img")]
                        + [g.get("ref") for g in garde.get("gros_plans") or []] if x and x not in refs]
        le = _maintenant()
        with _verrou:
            c = self._db()
            try:
                c.execute("UPDATE cartes SET etat_json=?, etat_le=? WHERE id=?", (json.dumps(res, ensure_ascii=False), le, cid))
                c.commit()
            finally:
                c.close()
        if anciens:
            try:
                photos_cartes.supprimer(anciens)
            except Exception:
                pass
        # 5 nov 2026 (Mathieu : « une fois la photo evaluee, reduire la qualite pour prendre moins de place ») : l'examen est
        # fait (zooms pleine resolution envoyes a l'IA) : les photos sont allegees en arriere-plan (2400 px ; gros plans 1800)
        try:
            f_ = [photos_cartes.chemin(r) for r in list(refs) + list(ras_ref)]
            g_ = [photos_cartes.chemin(g["ref"]) for g in gps]
            # 7 nov 2026 : le devant et le dos restent en pleine resolution (le zoom de la fiche) tant que le disque a de la place
            hd = photos_cartes.garder_hd()
            threading.Thread(target=lambda: ((None if hd else photos_cartes.alleger(f_)), photos_cartes.alleger(g_, cote=1800)), daemon=True).start()
        except Exception as x:
            print("Allegement : " + repr(x), flush=True)
        return {"ok": True, **res, "le": le, "precision": precision}

    CENTRAGE_ALGO = 6                 # 9 nov 2026 : + l axe de symetrie, largeurs l / r corrigees, > 80/20 a verifier

    @staticmethod
    def _coherent(e):
        """2 nov 2026 (Mathieu : « comment la note finale est 8-9 avec juste des 9 et 9,5 ? ») : un examen d'avant le bareme
        fixe : les sous-notes ramenees sur l'echelle PSA (pas de 9,5) et la note globale recalculee avec la meme regle que
        les nouveaux (bareme.globale). On dit que c'est une ancienne analyse : la refaire donne les raisons precises."""
        import bareme
        if not e or e.get("bareme") or not e.get("notes"):
            return e
        notes = {k: (bareme.psa(v) if isinstance(v, (int, float)) else None) for k, v in (e.get("notes") or {}).items()}
        # 3 nov 2026 : un centrage MESURE (ratios gardes) donne sa note par les tolerances PSA, pas l'estime de l'ancienne IA
        import examen
        ok_r = lambda r: r if re.fullmatch(r"\d{2}/\d{2}", str(r or "").strip()) else None
        gd, hb, ds = ok_r(e.get("centrage_gd")), ok_r(e.get("centrage_hb")), ok_r(e.get("centrage_dos"))
        if gd or hb:
            big = lambda r: (lambda a, b: f"{max(a, b)}/{min(a, b)}")(*map(int, r.split("/"))) if r else None
            nc = examen.note_centrage({"gd": big(gd), "hb": big(hb)}, {"gd": big(ds)} if ds else None)
            if nc is not None:
                notes["centrage"] = float(nc)
        vs = [v for v in notes.values() if v is not None]
        if not vs:
            return e
        g = min(vs)                                # l'ancienne IA mettait 9 par prudence, pas pour un defaut vu
        bas = g
        if any(d.get("gravite") == "a verifier" and not d.get("masque") for d in e.get("defauts") or []):
            bas = bareme.psa(g - 1)                # des points incertains : la note s'ils se confirment
        return dict(e, notes=notes, note_max=g, note_min=bas, ancienne=True)

    @staticmethod
    def _sans_texture_relique(carte, e):
        """2 nov 2026 (Mathieu : « ce n'est pas une scratch de surface, c'est une patch ») : un ancien examen d'une carte a
        patch : les « rayures / taches / autres » de surface incertaines ou legeres (la texture du tissu, d'avant la regle)
        ne sont plus montrees. Le prochain examen les classe lui-meme (sur_relique)."""
        if not e or not e.get("defauts") or e.get("regle_relique"):
            return e
        if not (carte.get("relique") or _RE_RELIQUE.search(str(carte.get("titre") or "") + " " + str(carte.get("parallele") or ""))):
            return e
        tex = lambda d: d.get("zone") == "surface" and d.get("type") in ("rayure", "tache", "autre", "ligne d'impression") \
            and d.get("gravite") in ("a verifier", "leger")
        if not any(tex(d) for d in e["defauts"]):
            return e
        return dict(e, defauts=[dict(d, masque=True) if tex(d) else d for d in e["defauts"]])     # les numeros (avis) restent

    def _recentrer(self, cid, e):
        """2 nov 2026 (Mathieu : « ameliorer la detection des rebords ») : un examen fait avec l'ancienne detection : les
        aretes ajustees sur la photo et le centrage remesure par symetrie, une seule fois, sans repayer l'IA. Jamais si
        l'utilisateur a deja ajuste le contour ou les lignes a la main."""
        import photos_cartes
        cv0 = e.get("centrage_vue") or {}
        if e.get("centrage_algo") == self.CENTRAGE_ALGO or e.get("contour_manuel") or any(v.get("manuel") for v in cv0.values()) \
                or not e.get("quads") or not e.get("photos"):
            return e
        try:
            refs = list(e["photos"])
            quads = self._affiner_quads(refs, list(e["quads"]))
            cv = self._centrage_vue(refs, quads)
        except Exception as x:
            print("Centrage (refait) : " + repr(x), flush=True)
            return e
        anciens = [v.get("img") for v in cv0.values() if v.get("img")]
        e = dict(e, quads=quads, centrage_vue=cv, centrage_algo=self.CENTRAGE_ALGO)
        if not e.get("mesures"):                           # 3 nov 2026 : les mesures de l'app, sans repayer l'IA
            m = self._mesures_photos(refs, quads)
            if m:
                e["mesures"] = m
        with _verrou:
            c = self._db()
            try:
                c.execute("UPDATE cartes SET etat_json=? WHERE id=?", (json.dumps(e, ensure_ascii=False), cid))
                c.commit()
            finally:
                c.close()
        if anciens:
            try:
                photos_cartes.supprimer(anciens)
            except Exception:
                pass
        for face in ("devant", "dos"):
            if (cv.get(face) or {}).get("gd") or (cv.get(face) or {}).get("hb"):
                r = self.carte_centrage(cid, face, None)
                if r.get("ok"):
                    e = {k: v for k, v in r.items() if k != "ok"}
        return e

    def _caler_defauts(self, cid, e):
        """9 nov 2026 : un examen enregistre avant le calage : ses defauts de coin et de bord recales sur la vraie arete
        (une seule fois, sans IA). Avant le 9 nov (13 h 45), la bande du bord GAUCHE etait tournee a l'envers : la position
        lue par l'IA etait inversee (haut <-> bas) ; elle est remise a l'endroit au passage."""
        import examen
        import photos_cartes
        import vision
        ds = e.get("defauts") or []
        # v3 (9 nov, 15 h) : aussi le long du bord, vers la tranche blanche ; refait meme si une version d'avant l'a cale
        a_caler = any(str(d.get("zone") or "").startswith(("coin ", "bord ")) and d.get("cale_v") != 4 for d in ds)
        if not e.get("contre_verif") or (not a_caler and e.get("centrage_assaini")):
            return e
        refs = list(e.get("photos") or [])
        quads = list(e.get("quads") or []) + [None] * max(0, len(refs) - len(e.get("quads") or []))
        if not refs:
            return e
        e = json.loads(json.dumps(e))
        # 9 nov 2026 (« Dos 88/12 » sur la Willander) : un centrage enregistre au-dela de 80/20 est un mauvais repere : retire
        # (montre « a verifier » dans la grille), jamais affiche comme une mesure
        r80 = lambda r_: bool(re.fullmatch(r"\d{2}/\d{2}", str(r_ or ""))) and max(int(v) for v in str(r_).split("/")) > 80
        for k in ("centrage_gd", "centrage_hb", "centrage_dos"):
            if r80(e.get(k)):
                e[k] = ""
        for fc, v in (e.get("centrage_vue") or {}).items():
            if not isinstance(v, dict) or v.get("manuel"):
                continue
            for ax, k1, k2 in (("gd", "l", "r"), ("hb", "t", "b")):
                a_, b_ = v.get(k1), v.get(k2)
                if a_ is not None and b_ is not None and (a_ + b_) > 0 and 100 * max(a_, b_) / (a_ + b_) > 80:
                    g_ = round(100 * max(a_, b_) / (a_ + b_))
                    v["verifier_" + ax] = f"{g_}/{100 - g_}"
                    v[k1] = v[k2] = v[ax] = None
        e["centrage_assaini"] = True
        ims = []
        for r in refs[:2]:
            ch = photos_cartes.chemin(r)
            try:
                with open(ch, "rb") as f:
                    ims.append(examen.ouvrir(f.read()))
            except Exception:
                ims.append(None)
        for j_, im_ in enumerate(ims):                       # pas de contour garde : l'app le trouve sur la photo
            if im_ is not None and j_ < len(quads) and not quads[j_]:
                try:
                    import mesures
                    q0 = mesures.trouver_carte(im_)
                    quads[j_] = examen.affiner_quad(im_, q0, 0.03) if q0 else None
                except Exception:
                    pass
        if not e.get("bandes_v2"):
            for d in e["defauts"]:
                q = quads[1 if d.get("photo") == 1 else 0] if quads else None
                if d.get("zone") == "bord gauche" and q and len(q) == 4:
                    # la position le long du bord gauche, de haut en bas (0..1) -> son miroir
                    y0, y1 = q[0][1], q[3][1]
                    t = (float(d.get("y") or 0) - y0) / ((y1 - y0) or 1)
                    t = 1 - max(0.0, min(1.0, t))
                    d["x"], d["y"] = vision._bil(q, 0.01, t)
                    d.pop("cale", None)
                    d.pop("cale_v", None)
                    a_caler = True
            e["bandes_v2"] = True
        if a_caler:
            vision.caler_defauts(e, ims, quads, refaire=True)
            if any(quads) and not any(e.get("quads") or []):
                e["quads"] = quads
            for d in e["defauts"]:                           # meme sans calage possible : une seule tentative (v2)
                if str(d.get("zone") or "").startswith(("coin ", "bord ")):
                    d["cale_v"] = 4
        c = self._db()
        try:
            c.execute("UPDATE cartes SET etat_json=? WHERE id=?", (json.dumps(e, ensure_ascii=False), cid))
            c.commit()
        finally:
            c.close()
        return e

    @staticmethod
    def _mesures_photos(refs, quads):
        """Les mesures de mesures.py (blanc aux coins et aux bords, qualite de la photo) d'apres les photos gardees."""
        import examen
        import photos_cartes
        out = {}
        for j, ref in enumerate(refs[:2]):
            q = quads[j] if j < len(quads) else None
            ch = photos_cartes.chemin(ref)
            if not q or not ch:
                continue
            try:
                with open(ch, "rb") as f:
                    im = examen.ouvrir(f.read())
                c = examen.redresser(im, q)
                z = examen.redresser(im, q, 0.03, examen.COTE_ZOOM)
                m = examen._mesurer(im, q, c, z) or {}
                u = m.get("usure") or {}
                out["devant" if j == 0 else "dos"] = {"coins": u.get("coins") or {}, "bords": u.get("bords") or {},
                                                      "px_mm": (m.get("qualite") or {}).get("px_mm"), "qualite": m.get("qualite"),
                                                      "silhouette": m.get("silhouette")}
            except Exception as e:
                print("Mesures (photos) : " + repr(e), flush=True)
        return out

    @staticmethod
    def _reperes_vue(cv, reperes):
        """2 nov 2026 (Mathieu : « on doit voir le centrage et tes points de repere : ecriture, bord de la patch ») : chaque axe
        de la grille porte le NOM de son repere. Mesure par l'app : le nom donne par l'IA si elle a vu le meme repere (a 3 %
        pres), sinon « ligne imprimee ». Pas mesure par l'app : le repere de l'IA (lu sur la regle de la carte redressee)."""
        import examen
        cv = dict(cv or {})
        for r in reperes or []:
            face = "devant" if r.get("photo") == 0 else "dos"
            v = dict(cv.get(face) or {})
            if not v.get("img"):
                continue
            a, b = r["debut"] / 1000, 1 - r["fin"] / 1000
            k1, k2 = ("l", "r") if r["axe"] == "gd" else ("t", "b")
            if v.get(k1) is None or v.get(k2) is None:
                v[k1], v[k2] = round(a, 4), round(b, 4)
                v["source_" + r["axe"]] = "ia"
                v["repere_" + r["axe"]] = r.get("element") or ""
            elif abs(v[k1] - a) <= 0.03 and abs(v[k2] - b) <= 0.03:
                v["repere_" + r["axe"]] = r.get("element") or ""
            v.update(examen.ratios(v.get("l"), v.get("r"), v.get("t"), v.get("b")))
            cv[face] = v
        for v in cv.values():
            for ax, k in (("gd", "l"), ("hb", "t")):
                if v.get(k) is not None:
                    v.setdefault("source_" + ax, "app")
                    if not v.get("repere_" + ax):
                        v["repere_" + ax] = "ligne imprimée"
        return cv

    @staticmethod
    def _affiner_quads(refs, quads, recherche=0.04, manuel=False):
        """2 nov 2026 (Mathieu : « ameliorer la detection des rebords ») : chaque contour envoye par le telephone, ajuste sur
        les vraies aretes de la photo (examen.affiner_quad). Un contour qu'on ne peut pas ameliorer reste tel quel."""
        import examen
        import photos_cartes
        if not examen.disponible():
            return quads
        out = []
        for j, q in enumerate(quads or []):
            ch = photos_cartes.chemin(refs[j]) if j < len(refs) else None
            if not q or not ch:
                out.append(q)
                continue
            try:
                with open(ch, "rb") as f:
                    im_ = examen.ouvrir(f.read())
                qa = examen.affiner_quad(im_, q, recherche)
                # 3 nov 2026 (Mathieu : le gros plan d'un coin montrait le fond) : si l'app trouve un contour qui tranche
                # nettement mieux (un vieux contour decale), elle le garde
                try:
                    import mesures
                    if not manuel:                   # 3 nov 2026 (revue) : un contour place a la main n'est jamais remplace
                        qa = mesures.meilleur_contour(im_, qa)
                except Exception as e2:
                    print("Contour (meilleur) : " + repr(e2), flush=True)
                out.append(qa)
            except Exception as e:
                print("Contour (ajuste) : " + repr(e), flush=True)
                out.append(q)
        return out

    @staticmethod
    def _centrage_vue(refs, quads):
        """La carte redressee de chaque face (gardee) et ses bordures trouvees : l'ecran trace la grille de centrage dessus."""
        import base64
        import examen
        import photos_cartes
        out = {}
        if not examen.disponible():
            return out
        for j, ref in enumerate(refs[:2]):
            q = quads[j] if j < len(quads) else None
            ch = photos_cartes.chemin(ref)
            if not q or not ch:
                continue
            try:
                with open(ch, "rb") as f:
                    c = examen.redresser(examen.ouvrir(f.read()), q)
                if c is None:
                    continue
                img = photos_cartes.sauver(["data:image/jpeg;base64," + base64.b64encode(examen.jpeg(c, 1200, 90)).decode()])
                det = dict(examen.centrage_detail(c) or {})
                # 3 nov 2026 (Mathieu : « les evaluations doivent etre plus precises ») : un axe sans bordure symetrique est
                # mesure par les paires d'elements imprimes en miroir (fiables, et pas un decentrage de design a verifier)
                try:
                    import mesures
                    mp = mesures.centrage(c) or {}
                    for ax, k1, k2, s1, s2 in (("gd", "l", "r", "l", "r"), ("hb", "t", "b", "t", "b_")):
                        x = mp.get(ax)
                        # 3 nov 2026 (pratique, Suzuki Orange Checkers : la symetrie lisait 62/38 en haut/bas, la carte est
                        # a ~52/48) : 2 paires ou plus d'accord l'emportent sur la symetrie ; sinon, seulement si rien d'autre
                        if not x or x.get("a_verifier") or x.get("fiabilite") not in ("haute", "moyenne"):
                            continue
                        if det.get(ax) and x.get("fiabilite") != "haute":
                            continue
                        det[k1], det[k2], det[ax] = round(x[s1], 4), round(x[s2], 4), x["ratio"]
                        det["source_" + ax] = "paires"
                    # un fort decentrage (> 60/40) mesure sur un element de design, pas sur une bordure unie : peut-etre le
                    # dessin de la carte -> pas compte dans la note, montre « a verifier »
                    for ax, k1, k2 in (("gd", "l", "r"), ("hb", "t", "b")):
                        g_ = det.get(ax)
                        # 9 nov 2026 : au-dela de 80/20, toujours a verifier (un mauvais repere, presque toujours)
                        if g_ and int(str(g_).split("/")[0]) > 60 and (int(str(g_).split("/")[0]) > 80 or (det.get("source_" + ax) != "paires"
                                and not mesures.bordure_unie(c, ax, det.get(k1), det.get(k2)))):
                            det["verifier_" + ax] = g_
                            det[ax] = det[k1] = det[k2] = None
                except Exception as e2:
                    print("Centrage (paires) : " + repr(e2), flush=True)
                out["devant" if j == 0 else "dos"] = {"img": img[0] if img else None, "ratio": round(c.size[0] / c.size[1], 4), **det}
            except Exception as e:
                print("Centrage (vue) : " + repr(e), flush=True)
        return out

    def carte_centrage(self, cid, face, d):
        """1er nov 2026 : la grille de centrage ajustee a la main (les 4 lignes sur le cadre imprime, en fraction de la carte)
        -> les ratios, la sous-note de centrage (tolerances PSA) et la fourchette, mis a jour."""
        import examen
        carte = self.carte_lire(cid)
        try:
            e = json.loads((carte or {}).get("etat_json") or "null")
        except ValueError:
            e = None
        if not e or face not in ("devant", "dos"):
            return {"ok": False, "erreur": "Aucun examen pour cette carte"}
        vue = e.setdefault("centrage_vue", {}).setdefault(face, {})
        if d is None:                                  # « remettre la mesure de l'app »
            vue.pop("manuel", None)
            for k in ("l", "r", "t", "b"):
                vue[k] = vue.pop("auto_" + k, vue.get(k))
        else:
            for k in ("l", "r", "t", "b"):
                v = _float((d or {}).get(k))
                if v is None or not 0 <= v <= 0.45:
                    return {"ok": False, "erreur": "Place les 4 lignes sur le cadre imprimé"}
                if not vue.get("manuel"):
                    vue["auto_" + k] = vue.get(k)
                vue[k] = round(v, 4)
            vue["manuel"] = True
        rt = examen.ratios(vue.get("l"), vue.get("r"), vue.get("t"), vue.get("b"))
        vue.update(rt)
        dev, dos = (e["centrage_vue"].get("devant") or {}), (e["centrage_vue"].get("dos") or {})
        n = examen.note_centrage({"gd": dev.get("gd"), "hb": dev.get("hb")} if dev.get("gd") or dev.get("hb") else None,
                                 {"gd": dos.get("gd"), "hb": dos.get("hb")} if dos.get("gd") or dos.get("hb") else None)
        if face == "devant":
            e["centrage_gd"], e["centrage_hb"] = rt["gd"] or "", rt["hb"] or ""
        else:
            e["centrage_dos"] = rt["gd"] or rt["hb"] or ""
        if n is not None:
            notes = e.setdefault("notes", {})
            notes["centrage"] = float(n)
            e["centrage_mesure"] = True
            qui = "ajusté par toi" if (dev.get("manuel") or dos.get("manuel")) else "mesuré par l’app"
            e.setdefault("explications", {})["centrage"] = qui + " : " + " · ".join(x for x in (dev.get("gd"), dev.get("hb")) if x) + \
                ((" · dos " + (dos.get("gd") or dos.get("hb"))) if (dos.get("gd") or dos.get("hb")) else "")
            # 3 nov 2026 (revue) : la fourchette refaite avec le bareme (la pire sous-note), pas seulement rabaissee : un
            # centrage corrige a la main peut aussi la remonter
            import bareme as _bar
            hi = _bar.globale(notes) or 9.0
            if any(d_.get("gravite") not in ("a verifier",) and not d_.get("masque") for d_ in e.get("defauts") or []):
                hi = min(hi, 9.0)
            bas_ = {**notes, **{k: v for k, v in (e.get("notes_bas") or {}).items() if v is not None}}
            lo = _bar.globale(bas_) or hi
            if not e.get("notes_bas") and any(d_.get("gravite") == "a verifier" and not d_.get("masque") for d_ in e.get("defauts") or []):
                lo = min(lo, _bar.psa(hi - 1))           # ancien examen sans bas de fourchette par categorie : la regle de _coherent
            e["note_max"] = hi
            e["note_min"] = min(lo, hi)
        with _verrou:
            c = self._db()
            try:
                c.execute("UPDATE cartes SET etat_json=? WHERE id=?", (json.dumps(e, ensure_ascii=False), cid))
                c.commit()
            finally:
                c.close()
        return {"ok": True, **e}

    def carte_contour(self, cid, face, quad):
        """2 nov 2026 (Mathieu : « les chiffres ne sont pas a la bonne place ») : le contour de la carte corrige a la main sur la
        photo d'examen (4 coins, 0..1000, haut-gauche puis sens horaire) -> la carte redressee de nouveau, le centrage remesure
        (sous-note et fourchette), les numeros replaces par l'ecran. Rien n'est repaye a l'IA."""
        import photos_cartes
        carte = self.carte_lire(cid)
        try:
            e = json.loads((carte or {}).get("etat_json") or "null")
        except ValueError:
            e = None
        if not e or face not in ("devant", "dos"):
            return {"ok": False, "erreur": "Aucun examen pour cette carte"}
        j = 0 if face == "devant" else 1
        refs = list(e.get("photos") or [])
        if j >= len(refs):
            return {"ok": False, "erreur": "Pas de photo pour ce côté"}
        try:
            q = [[max(0, min(1000, int(round(float(x))))), max(0, min(1000, int(round(float(y)))))] for x, y in quad][:4]
        except (TypeError, ValueError):
            q = []
        if len(q) != 4:
            return {"ok": False, "erreur": "Place les 4 coins sur la carte"}
        aire = abs(sum(q[i][0] * q[(i + 1) % 4][1] - q[(i + 1) % 4][0] * q[i][1] for i in range(4))) / 2
        if aire < 40000:                                   # moins de 4 % de la photo : un clic de travers
            return {"ok": False, "erreur": "Le contour est trop petit : place les coins sur ceux de la carte"}
        q = self._affiner_quads(refs[:j + 1], [None] * j + [q], 0.015, manuel=True)[j] or q      # colle aux aretes, a 1,5 % pres
        quads = list(e.get("quads") or [])
        while len(quads) <= j:
            quads.append(None)
        quads[j] = q
        e["quads"] = quads
        vue = self._centrage_vue(refs[:j + 1], [None] * j + [q]).get(face)
        ancienne = ((e.get("centrage_vue") or {}).get(face) or {}).get("img")
        cv = e.setdefault("centrage_vue", {})
        if vue:
            cv[face] = vue
        else:
            cv.pop(face, None)
        e["contour_manuel"] = sorted(set((e.get("contour_manuel") or []) + [face]))
        with _verrou:
            c = self._db()
            try:
                c.execute("UPDATE cartes SET etat_json=? WHERE id=?", (json.dumps(e, ensure_ascii=False), cid))
                c.commit()
            finally:
                c.close()
        if ancienne and ancienne != (vue or {}).get("img"):
            try:
                photos_cartes.supprimer([ancienne])
            except Exception:
                pass
        if vue:
            return self.carte_centrage(cid, face, None)       # ratios, sous-note de centrage et fourchette, remesures
        return {"ok": True, **e}

    def carte_etat_avis(self, cid, i, vrai):
        """Un defaut signale : l'utilisateur le voit (vrai) ou non (faux). Garde avec l'examen, et compte (sans photo, sans
        nom) dans ce que l'analyseur apprend : les defauts « a verifier » souvent rejetes deviennent plus exigeants."""
        import etat_verite
        carte = self.carte_lire(cid)
        try:
            e = json.loads((carte or {}).get("etat_json") or "null")
        except ValueError:
            e = None
        if not e:
            return {"ok": False, "erreur": "Aucun examen pour cette carte"}
        try:
            d = (e.get("defauts") or [])[int(i)]
        except (TypeError, ValueError, IndexError):
            return {"ok": False, "erreur": "Défaut introuvable"}
        avis = e.setdefault("avis", {})
        avant = avis.get(str(i))
        v = None if vrai is None else bool(vrai)
        if v is None:
            avis.pop(str(i), None)
        else:
            avis[str(i)] = v
        etat_verite.avis(d, avant, v)
        with _verrou:
            c = self._db()
            try:
                c.execute("UPDATE cartes SET etat_json=? WHERE id=?", (json.dumps(e, ensure_ascii=False), cid))
                c.commit()
            finally:
                c.close()
        if v is not None and self.reglages_lire().get("ia_entrainement_ok"):
            try:                                   # 3 nov 2026 : un defaut confirme / rejete = une etiquette pour l'entrainement
                import entrainement
                entrainement.ajouter(carte, e, raison="avis")
            except Exception as x:
                print("Entrainement (avis) : " + repr(x), flush=True)
        return {"ok": True, "avis": avis}

    # -- 1er nov 2026 (Mathieu : « les cartes de la collection qu'on envoie se faire grader, et celles qu'on envoie en
    # consignation : la carte va en encan, comme chez un consignataire ») : le SUIVI de l'envoi. La carte reste dans la
    # collection ; elle porte l'envoi (ou, quand, combien) et l'app avertit quand c'est en retard.
    COMPAGNIES = ("PSA", "BGS", "SGC", "CGC", "TAG", "Autre")

    def carte_envoi(self, cid, d=None):
        """d = {type: 'gradation'|'encan', ...} pour envoyer ; d = None (ou {retour: ...}) pour la revenue."""
        carte = self.carte_lire(cid)
        if not carte:
            return {"ok": False, "erreur": "Carte introuvable"}
        d = dict(d or {})
        jour = lambda v: str(v)[:10] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(v or "")[:10]) else None
        txt = lambda v, n: re.sub(r"\s+", " ", str(v or "")).strip()[:n] or None
        maj = {}
        if not d or d.get("retour") is not None:
            try:
                avant = json.loads(carte.get("envoi_json") or "null") or {}
            except ValueError:
                avant = {}
            r = d.get("retour") or {}
            # revenue du gradage : le cout de gradation s'ajoute au cout de la carte ; la note lue (si donnee) va dans la fiche
            if avant.get("type") == "gradation":
                try:                           # 1er nov 2026 : la vraie note, comparee a l'examen d'avant l'envoi
                    import etat_verite
                    etat_verite.noter(carte.get("etat_json"), r.get("grade"), avant.get("compagnie"), r.get("sous_notes"))
                except Exception:
                    pass
                # 3 nov 2026 : la banque d'entrainement (seulement avec le OUI) : photos d'examen + mesures + vraie note
                if (r.get("grade") or r.get("sous_notes")) and self.reglages_lire().get("ia_entrainement_ok"):
                    try:
                        import entrainement
                        entrainement.ajouter(carte, carte.get("etat_json"), {**r, "compagnie": avant.get("compagnie")})
                    except Exception as e:
                        print("Entrainement (retour) : " + repr(e), flush=True)
                if avant.get("cout") and r.get("garder_cout", True):
                    maj["cout"] = round((carte.get("cout") or 0) + float(avant["cout"]), 2)
                g = txt(r.get("grade"), 20)
                if g:
                    maj["grade"] = g
                    if r.get("cert"):
                        maj["cert"] = txt(r.get("cert"), 20)
            maj["envoi_json"] = None
        else:
            t = d.get("type")
            if t == "gradation":
                cie = d.get("compagnie") if d.get("compagnie") in self.COMPAGNIES else "PSA"
                e = {"type": t, "compagnie": cie, "service": txt(d.get("service"), 30), "soumission": txt(d.get("soumission"), 30),
                     "envoye_le": jour(d.get("envoye_le")) or datetime.now().strftime("%Y-%m-%d"), "retour_prevu": jour(d.get("retour_prevu")),
                     "cout": _float(d.get("cout"))}
            elif t == "encan":
                if not txt(d.get("chez"), 40):
                    return {"ok": False, "erreur": "Écris chez qui la carte est consignée"}
                com = _float(d.get("commission"))
                e = {"type": t, "chez": txt(d.get("chez"), 40), "envoye_le": jour(d.get("envoye_le")) or datetime.now().strftime("%Y-%m-%d"),
                     "commission": max(0.0, min(60.0, com)) if com is not None else None, "reserve": _float(d.get("reserve")),
                     "fin_encan": jour(d.get("fin_encan")), "lien": txt(d.get("lien"), 300) if str(d.get("lien") or "").startswith("https://") else None,
                     "alerte_jours": int(_float(d.get("alerte_jours")) or 45)}
            else:
                return {"ok": False, "erreur": "Type d'envoi inconnu"}
            maj["envoi_json"] = json.dumps({k: v for k, v in e.items() if v not in (None, "")}, ensure_ascii=False)
        with _verrou:
            c = self._db()
            try:
                c.execute("UPDATE cartes SET " + ", ".join(f"{k}=?" for k in maj) + " WHERE id=?", (*maj.values(), cid))
                c.commit()
            finally:
                c.close()
        return {"ok": True, "carte": self.carte_lire(cid)}

    # -- 1er nov 2026 (Mathieu : une app concurrente prepare les soumissions PSA ; « soumissions groupees ») : plusieurs
    # cartes de la collection -> UNE soumission (compagnie, service, numero, dates, cout par carte). La valeur declaree
    # (assurance) de chaque carte = sa valeur connue (sinon son cout). Liste exportable a recopier dans le formulaire de
    # la compagnie ; retour de toute la soumission d'un coup (notes et certificats).
    def _soumission_envoi(self, so, cid, valeur):
        return {"type": "gradation", "soumission_id": so["id"], "compagnie": so["compagnie"], "service": so.get("service"),
                "soumission": so.get("numero"), "envoye_le": so.get("envoyee_le"), "retour_prevu": so.get("retour_prevu"),
                "cout": so.get("cout_carte"), "valeur_declaree": valeur, "suivi": so.get("suivi"),
                "etape": "preparation" if so.get("statut") == "preparation" else None}

    def soumission_creer(self, d):
        d = dict(d or {})
        ids = []
        for x in d.get("cartes") or []:
            try:
                ids.append(int(x))
            except (TypeError, ValueError):
                continue
        ids = list(dict.fromkeys(ids))[:200]
        if not ids:
            return {"ok": False, "erreur": "Choisis au moins une carte"}
        jour = lambda v: str(v)[:10] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(v or "")[:10]) else None
        txt = lambda v, n: re.sub(r"\s+", " ", str(v or "")).strip()[:n] or None
        so = {"compagnie": d.get("compagnie") if d.get("compagnie") in self.COMPAGNIES else "PSA", "service": txt(d.get("service"), 30),
              "numero": txt(d.get("numero"), 30), "envoyee_le": jour(d.get("envoyee_le")) or datetime.now().strftime("%Y-%m-%d"),
              "retour_prevu": jour(d.get("retour_prevu")), "cout_carte": _float(d.get("cout_carte")),
              "statut": "preparation" if d.get("preparation") else "envoyee", "mode": txt(d.get("mode"), 20)}
        if so["statut"] == "preparation" and not d.get("envoyee_le"):
            so["envoyee_le"] = None
        decl = d.get("valeurs") or {}
        with _verrou:
            c = self._db()
            try:
                cartes = {r["id"]: dict(r) for r in c.execute("SELECT id, valeur, cout, statut, grade, envoi_json FROM cartes WHERE id IN (%s)"
                                                              % ",".join("?" * len(ids)), ids)}
                pris = [i for i in ids if i in cartes and cartes[i]["statut"] != "Vendue" and not cartes[i]["envoi_json"]]
                if not pris:
                    return {"ok": False, "erreur": "Ces cartes sont déjà envoyées ou vendues"}
                cur = c.execute("INSERT INTO soumissions (compagnie, service, numero, envoyee_le, retour_prevu, cout_carte, statut, cree_le, mode) "
                                "VALUES (?,?,?,?,?,?,?,?,?)", (so["compagnie"], so["service"], so["numero"], so["envoyee_le"], so["retour_prevu"],
                                                               so["cout_carte"], so["statut"], _maintenant(), so["mode"]))
                so["id"] = cur.lastrowid
                vals = {}
                for i in pris:
                    v = _float(decl.get(str(i))) or cartes[i]["valeur"] or cartes[i]["cout"]
                    vals[str(i)] = round(v, 2) if v else None
                    e = {k: x for k, x in self._soumission_envoi(so, i, vals[str(i)]).items() if x not in (None, "")}
                    c.execute("UPDATE cartes SET envoi_json=?, soumission_id=? WHERE id=?", (json.dumps(e, ensure_ascii=False), so["id"], i))
                c.execute("UPDATE soumissions SET valeurs=? WHERE id=?", (json.dumps(vals), so["id"]))
                c.commit()
            finally:
                c.close()
        return {"ok": True, "id": so["id"], "n": len(pris), "ignorees": len(ids) - len(pris)}

    def _reparer_soumissions(self):
        """4 nov 2026 (Mathieu : « ca dit At grading mais j'ai rien rentre ») : fermer l'assistant a la derniere etape
        envoyait la soumission. Une soumission « envoyee » sans numero ni suivi n'a jamais ete envoyee : elle redevient
        « a soumettre » (et ses cartes aussi). Le bouton « C'est envoye » exige l'un des deux depuis toujours. Seulement les
        soumissions de l'assistant (mode choisi) : le formulaire simple peut enregistrer un envoi sans numero, expres."""
        with _verrou:
            c = self._db()
            try:
                try:
                    sos = _dicts(c.execute("SELECT * FROM soumissions WHERE statut='envoyee' AND COALESCE(numero,'')='' AND COALESCE(suivi,'')='' "
                                           "AND COALESCE(mode,'')<>''"))
                except sqlite3.OperationalError:
                    return 0
                for so in sos:
                    so = dict(so, statut="preparation", envoyee_le=None)
                    c.execute("UPDATE soumissions SET statut='preparation', envoyee_le=NULL WHERE id=?", (so["id"],))
                    try:
                        vals = json.loads(so.get("valeurs") or "{}") or {}
                    except ValueError:
                        vals = {}
                    for (cid,) in c.execute("SELECT id FROM cartes WHERE soumission_id=? AND envoi_json IS NOT NULL", (so["id"],)).fetchall():
                        e = {k: v for k, v in self._soumission_envoi(so, cid, vals.get(str(cid))).items() if v not in (None, "")}
                        c.execute("UPDATE cartes SET envoi_json=? WHERE id=?", (json.dumps(e, ensure_ascii=False), cid))
                if sos:
                    c.commit()
                return len(sos)
            finally:
                c.close()

    def soumissions_liste(self):
        self._reparer_soumissions()
        with _verrou:
            c = self._db()
            try:
                sos = _dicts(c.execute("SELECT * FROM soumissions ORDER BY id DESC LIMIT 60"))
                cartes = _dicts(c.execute("SELECT id, joueur, titre, annee, marque, set_nom, numero, parallele, tirage, auto, valeur, cout, grade, cert, "
                                          "photo, soumission_id, envoi_json, etat_json FROM cartes WHERE soumission_id IS NOT NULL"))
            finally:
                c.close()
        vals = {so["id"]: (json.loads(so.get("valeurs") or "{}") or {}) for so in sos}
        par = {}
        for x in cartes:
            sid = x["soumission_id"]
            try:
                et = json.loads(x.get("etat_json") or "null") or {}
            except ValueError:
                et = {}
            par.setdefault(sid, []).append({**{k: v for k, v in x.items() if k not in ("envoi_json", "soumission_id", "etat_json")},
                                            "valeur_declaree": (vals.get(sid) or {}).get(str(x["id"])), "revenue": not x.get("envoi_json"),
                                            "etat": {"min": et.get("note_min"), "max": et.get("note_max"), "n": len(et.get("defauts") or [])} if et.get("note_min") else None,
                                            "texte": self._texte_soumission(x)})
        auj = datetime.now().strftime("%Y-%m-%d")
        out = []
        for so in sos:
            l = par.get(so["id"], [])
            if not l:
                continue
            if so["statut"] == "annulee":
                continue
            out.append({**{k: v for k, v in so.items() if k != "valeurs"}, "cartes": l, "n": len(l), "valeur_declaree": round(sum(x.get("valeur_declaree") or 0 for x in l), 2),
                        "cout_total": round((so.get("cout_carte") or 0) * len(l), 2),
                        "retard": bool(so["statut"] == "envoyee" and so.get("retour_prevu") and so["retour_prevu"] < auj)})
        return {"ok": True, "soumissions": out}

    def soumission_maj(self, sid, d):
        """Change le numero, le service, les dates ou le cout d'une soumission (et de ses cartes)."""
        d = dict(d or {})
        l = next((x for x in self.soumissions_liste()["soumissions"] if x["id"] == int(sid)), None)
        if not l:
            return {"ok": False, "erreur": "Soumission introuvable"}
        jour = lambda v: str(v)[:10] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(v or "")[:10]) else None
        txt = lambda v, n: re.sub(r"\s+", " ", str(v or "")).strip()[:n] or None
        so = {"id": l["id"], "compagnie": d.get("compagnie") if d.get("compagnie") in self.COMPAGNIES else l["compagnie"],
              "service": txt(d.get("service"), 30) if "service" in d else l.get("service"),
              "numero": txt(d.get("numero"), 30) if "numero" in d else l.get("numero"),
              "envoyee_le": jour(d.get("envoyee_le")) or l.get("envoyee_le"),
              "retour_prevu": jour(d.get("retour_prevu")) if "retour_prevu" in d else l.get("retour_prevu"),
              "cout_carte": _float(d.get("cout_carte")) if "cout_carte" in d else l.get("cout_carte"),
              "suivi": txt(d.get("suivi"), 40) if "suivi" in d else l.get("suivi"),
              "mode": txt(d.get("mode"), 20) if "mode" in d else l.get("mode"), "statut": l["statut"]}
        if d.get("envoyer") and l["statut"] == "preparation":       # l'assistant : « c'est parti »
            if not so.get("numero") and not so.get("suivi"):          # 4 nov 2026 : rien d'entre -> pas envoyee
                return {"ok": False, "erreur": "Entre au moins le numéro de soumission ou de suivi"}
            so["statut"] = "envoyee"
            so["envoyee_le"] = jour(d.get("envoyee_le")) or datetime.now().strftime("%Y-%m-%d")
        vals = {str(x["id"]): x.get("valeur_declaree") for x in l["cartes"]}
        for k, v in (d.get("valeurs") or {}).items():
            if str(k) in vals:
                vals[str(k)] = _float(v)
        with _verrou:
            c = self._db()
            try:
                c.execute("UPDATE soumissions SET compagnie=?, service=?, numero=?, envoyee_le=?, retour_prevu=?, cout_carte=?, suivi=?, mode=?, "
                          "statut=?, valeurs=? WHERE id=?",
                          (so["compagnie"], so["service"], so["numero"], so["envoyee_le"], so["retour_prevu"], so["cout_carte"], so["suivi"],
                           so["mode"], so["statut"], json.dumps(vals), so["id"]))
                for x in l["cartes"]:
                    if x.get("revenue"):
                        continue
                    e = {k: v for k, v in self._soumission_envoi(so, x["id"], vals.get(str(x["id"]))).items() if v not in (None, "")}
                    c.execute("UPDATE cartes SET envoi_json=? WHERE id=? AND envoi_json IS NOT NULL", (json.dumps(e, ensure_ascii=False), x["id"]))
                c.commit()
            finally:
                c.close()
        return {"ok": True}

    def soumission_annuler(self, sid):
        """Une soumission en preparation (rien d'envoye) : les cartes redeviennent libres. La soumission reste, marquee annulee."""
        l = next((x for x in self.soumissions_liste()["soumissions"] if x["id"] == int(sid)), None)
        if not l or l["statut"] != "preparation":
            return {"ok": False, "erreur": "Seule une soumission pas encore envoyée peut être annulée"}
        with _verrou:
            c = self._db()
            try:
                c.execute("UPDATE cartes SET envoi_json=NULL, soumission_id=NULL WHERE soumission_id=?", (int(sid),))
                c.execute("UPDATE soumissions SET statut='annulee' WHERE id=?", (int(sid),))
                c.commit()
            finally:
                c.close()
        return {"ok": True}

    @staticmethod
    def _texte_soumission(x):
        """La carte telle qu'on la cherche dans le formulaire de la compagnie : annee, marque, set, numero, joueur, variante."""
        t = " ".join(str(v) for v in (x.get("annee"), x.get("marque"), x.get("set_nom"), ("#" + str(x["numero"])) if x.get("numero") else None,
                                       x.get("joueur"), x.get("parallele"), ("/" + str(x["tirage"])) if x.get("tirage") else None,
                                       "Auto" if x.get("auto") else None) if v)
        return re.sub(r"\s+", " ", t).strip() or (x.get("titre") or "")

    def valeur_gradee(self, cid, note=None, compagnie="PSA"):
        """1er nov 2026 : PSA demande la valeur de la carte APRES gradation (« max insured value »). Les ventes reelles de la
        meme carte gradee a la note visee (l'etat estime, sinon 9). -> {valeur, n, note} ; valeur None si pas assez de ventes."""
        carte = self.carte_lire(cid)
        if not carte:
            return {"ok": False, "erreur": "Carte introuvable"}
        try:
            et = json.loads(carte.get("etat_json") or "null") or {}
        except ValueError:
            et = {}
        n = _float(note) or et.get("note_max") or 9
        n = 10 if n >= 9.75 else int(n) if float(n).is_integer() else n
        cie = compagnie if compagnie in ("PSA", "BGS", "SGC", "CGC", "TAG") else "PSA"
        import suivi_valeur
        t = suivi_valeur._titre(carte)
        if len(t) < 6:
            return {"ok": True, "valeur": None, "n": 0, "note": n}
        try:
            r = vendues.memes(f"{t} {cie} {n}", requete=False, n=24)
        except Exception as e:
            return {"ok": False, "erreur": str(e)}
        vs = [v for v in r.get("ventes") or [] if v.get("prix")]
        val = r.get("mediane")                   # 3 nov 2026 (revue) : seulement une valeur SURE (jamais la mediane d'une vente)
        return {"ok": True, "valeur": val, "n": len(vs), "note": n, "compagnie": cie, "sure": bool(r.get("mediane"))}

    def gradation_rentabilite(self, cid, compagnie="PSA", port=None):
        """3 nov 2026 (Mathieu : « on peut juste faire ca pour assister l'utilisateur pour grader avec PSA ? C'est pas
        assez ») : est-ce que ca vaut la peine de grader CETTE carte ? (gradation.py). Les ventes gradees de 2 a 4 notes,
        lues en parallele."""
        import gradation
        from concurrent.futures import ThreadPoolExecutor
        carte = self.carte_lire(cid)
        if not carte:
            return {"ok": False, "erreur": "Carte introuvable"}
        try:
            et = json.loads(carte.get("etat_json") or "null") or {}
        except ValueError:
            et = {}
        bas, haut = et.get("note_min"), et.get("note_max")
        if haut is None:
            return {"ok": True, "verdict": "examiner", "valeur_raw": carte.get("valeur")}
        notes = sorted(gradation.probas(bas, haut))
        with ThreadPoolExecutor(max_workers=4) as ex:
            # 3 nov 2026 (revue) : chaque fil garde le compte de la requete (sinon : la base du serveur, multi-comptes)
            import contextvars
            ctxs = {g: contextvars.copy_context() for g in notes}          # copies faites ICI (fil de la requete)
            res = dict(zip(notes, ex.map(lambda g: ctxs[g].run(self.valeur_gradee, cid, g, compagnie), notes)))
        vals = {g: {"valeur": r.get("valeur"), "n": r.get("n", 0)} for g, r in res.items() if r and r.get("ok")}
        rg = self.reglages_lire()
        taux = ebay_compte._taux_vers_cad("USD") or 1.38
        cie = "TAG" if str(compagnie or "").upper() == "TAG" else "PSA"
        out = gradation.calculer(_float(carte.get("valeur")), vals, bas, haut, taux, (rg["frais_ebay_pct"] or 0) / 100,
                                 rg["frais_ebay_fixe"] or 0, 1, _float(port), compagnie=cie, taxes_pct=_float(rg.get("taxes_pct")) or 0)
        out.update(valeur_raw=_float(carte.get("valeur")), bas=bas, haut=haut, compagnie=cie, ancienne=bool(et.get("ancienne") or not et.get("bareme")))
        return out

    def gradation_comparer(self, cid):
        """3 nov 2026 (Mathieu : « TAG aussi ; l'utilisateur choisit au debut ; un moyen leger de l'informer sur la meilleure
        decision ») : PSA et TAG cote a cote pour CETTE carte : gain attendu, cout, delai, et combien de ventes gradees
        appuient le calcul. Le meilleur choix : le plus gros gain attendu, a condition d'avoir assez de ventes."""
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as ex:
            import contextvars
            ctx = [contextvars.copy_context(), contextvars.copy_context()]
            r = dict(zip(("PSA", "TAG"), ex.map(lambda i_c: ctx[i_c[0]].run(self.gradation_rentabilite, cid, i_c[1]), enumerate(("PSA", "TAG")))))
        out = {}
        for c, x in r.items():
            if not x or not x.get("ok"):
                out[c] = {"ok": False}
                continue
            sv = x.get("service") or {}
            out[c] = {"ok": True, "verdict": x.get("verdict"), "gain": x.get("gain"), "cout": x.get("cout"), "service": sv.get("nom"),
                      "jours": sv.get("jours"), "valeur_esperee": x.get("valeur_esperee"), "ventes": sum(l.get("n") or 0 for l in x.get("lignes") or []),
                      "retour_prevu": x.get("retour_prevu")}
        ok = {c: v for c, v in out.items() if v.get("ok") and v.get("gain") is not None and v.get("verdict") not in ("pas_assez", "examiner")}
        meilleur = max(ok, key=lambda c: ok[c]["gain"]) if ok else None
        raison = None
        if meilleur and len(ok) == 2:
            autre = "TAG" if meilleur == "PSA" else "PSA"
            d = ok[meilleur]["gain"] - ok[autre]["gain"]
            raison = "gain" if d >= 15 else "egal"
            if raison == "egal":                       # a gain egal : la revente la plus sure (plus de ventes) ou le plus rapide
                meilleur = max(ok, key=lambda c: (ok[c]["ventes"], -((ok[c]["jours"] or [999])[0])))
                raison = "ventes"
        elif meilleur:
            raison = "seul"                            # l'autre n'a pas assez de ventes pour juger : revente moins sure
        return {"ok": True, "examiner": all(v.get("verdict") == "examiner" for v in out.values() if v.get("ok")), "compagnies": out,
                "meilleur": meilleur, "raison": raison, "valeur_raw": _float((self.carte_lire(cid) or {}).get("valeur"))}

    def soumission_retour(self, sid, notes=None):
        """Toute la soumission revient : chaque carte recoit sa note et son certificat (si donnes) ; le cout de gradation
        s'ajoute a son cout. notes = {id_carte: {grade, cert}}."""
        notes = notes or {}
        l = next((x for x in self.soumissions_liste()["soumissions"] if x["id"] == int(sid)), None)
        if not l:
            return {"ok": False, "erreur": "Soumission introuvable"}
        n = 0
        for x in l["cartes"]:
            if x.get("revenue"):
                continue
            r = notes.get(str(x["id"])) or {}
            if self.carte_envoi(x["id"], {"retour": {"grade": r.get("grade"), "cert": r.get("cert"), "sous_notes": r.get("sous_notes"),
                                                     "lien": r.get("lien")}}).get("ok"):
                n += 1
        with _verrou:
            c = self._db()
            try:
                c.execute("UPDATE soumissions SET statut='revenue', revenue_le=? WHERE id=?", (_maintenant(), int(sid)))
                c.commit()
            finally:
                c.close()
        return {"ok": True, "n": n}

    def soumission_csv(self, sid):
        """La liste a recopier dans le formulaire de la compagnie (CSV)."""
        import csv
        import io
        l = next((x for x in self.soumissions_liste()["soumissions"] if x["id"] == int(sid)), None)
        if not l:
            return {"ok": False, "erreur": "Soumission introuvable"}
        f = io.StringIO()
        w = csv.writer(f)
        w.writerow(["#", "Year", "Brand", "Set", "Card #", "Player", "Variety / Parallel", "Serial", "Declared value (CAD)"])
        for i, x in enumerate(l["cartes"], 1):
            w.writerow([i, x.get("annee") or "", x.get("marque") or "", x.get("set_nom") or "", x.get("numero") or "", x.get("joueur") or x.get("titre") or "",
                        x.get("parallele") or "", ("/" + str(x["tirage"])) if x.get("tirage") else "", x.get("valeur_declaree") or ""])
        nom = f"soumission-{l['compagnie']}-{l.get('numero') or l['id']}.csv"
        return {"ok": True, "csv": f.getvalue(), "nom": re.sub(r"[^A-Za-z0-9._-]+", "-", nom)}

    def envois_en_cours(self):
        """Les cartes au gradage ou en consignation, avec ce qui est en retard. -> {gradation: [...], encan: [...]}"""
        with _verrou:
            c = self._db()
            try:
                l = _dicts(c.execute("SELECT id, joueur, titre, valeur, envoi_json FROM cartes WHERE envoi_json IS NOT NULL AND statut != 'Vendue'"))
            finally:
                c.close()
        auj = datetime.now().strftime("%Y-%m-%d")
        out = {"gradation": [], "encan": []}
        for x in l:
            try:
                e = json.loads(x.pop("envoi_json") or "null") or {}
            except ValueError:
                continue
            if e.get("type") not in out:
                continue
            jours = (datetime.now() - datetime.fromisoformat(e.get("envoye_le") or auj)).days
            if e["type"] == "gradation":
                retard = bool(not e.get("etape") and e.get("retour_prevu") and e["retour_prevu"] < auj)
            else:
                retard = bool((e.get("fin_encan") and e["fin_encan"] < auj) or (not e.get("fin_encan") and jours > int(e.get("alerte_jours") or 45)))
            out[e["type"]].append({**x, **e, "jours": jours, "retard": retard})
        return {"ok": True, **out}

    def _actions_envois(self):
        """Pour « A faire » : les envois en retard (gradation passee la date prevue ; encan termine ou trop long)."""
        try:
            e = self.envois_en_cours()
        except Exception:
            return []
        out = []
        g = [x for x in e["gradation"] if x["retard"]]
        if g:
            out.append({"cle": "gradation", "n": len(g), "titre": "Gradation en retard", "montant": None,
                        "texte": "date de retour passée : vérifie la soumission", "lien": "#inventaire/collection", "ton": "or", "rang": 30})
        p = {x.get("soumission_id") for x in e["gradation"] if x.get("etape") == "preparation"}
        if p:
            out.append({"cle": "a_soumettre", "n": len(p), "titre": "Soumission à finir", "montant": None,
                        "texte": "l’assistant t’attend : valeurs, emballage, envoi", "lien": "#inventaire/collection", "ton": "acc", "rang": 20})
        a = [x for x in e["encan"] if x["retard"]]
        if a:
            out.append({"cle": "encan", "n": len(a), "titre": "Encan à suivre", "montant": None,
                        "texte": "terminé ou trop long : vérifie la vente et le paiement", "lien": "#inventaire/collection", "ton": "or", "rang": 30})
        return out

    def carte_supprimer(self, cid):
        import photos_cartes
        refs = []
        for k in ("photos", "photos_orig"):
            try:
                x = json.loads((self.carte_lire(cid) or {}).get(k) or "[]")
            except ValueError:
                x = []
            refs += [r for r in (x if isinstance(x, list) else []) if r not in refs]
        try:                                       # 3 nov 2026 : les photos de l'examen aussi (rasantes, relief, gros plans, gabarits)
            e = json.loads((self.carte_lire(cid) or {}).get("etat_json") or "null") or {}
            refs += [r for r in (e.get("photos") or []) + [e.get("rasante"), e.get("rasante2"), e.get("relief_img")]
                     + [g.get("ref") for g in e.get("gros_plans") or []] + [v.get("img") for v in (e.get("centrage_vue") or {}).values() if isinstance(v, dict)]
                     if r and str(r).startswith("/mes-photos/") and r not in refs]
        except (ValueError, AttributeError):
            pass
        photos_cartes.supprimer(refs)
        with _verrou:
            c = self._db()
            try:
                c.execute("DELETE FROM cartes WHERE id=?", (cid,))
                c.commit()
            finally:
                c.close()
        return {"ok": True}

    def cartes_retirer(self, ids, ebay=True):
        """8 nov 2026 (Mathieu : « les cartes a retirer de mon inventaire devraient aussi se supprimer dans eBay, et je peux
        les selectionner dans l'app ») : retire une ou plusieurs cartes ; celles en vente sur eBay voient leur annonce
        terminee d'abord. Si eBay refuse, la carte RESTE (on ne perd pas la trace d'une annonce encore active).
        -> {ok, retirees, terminees, erreurs: [{id, titre, erreur}]}"""
        out = {"ok": True, "retirees": 0, "terminees": 0, "erreurs": []}
        for cid in list(dict.fromkeys(int(i) for i in (ids or []) if str(i).strip().lstrip("-").isdigit()))[:200]:
            c = self.carte_lire(cid)
            if not c:
                continue
            if ebay and c.get("item_number") and c.get("statut") == "Listée":
                r = self._ecrire_ebay("terminer", c["item_number"])
                if not r.get("ok"):
                    out["erreurs"].append({"id": cid, "titre": c.get("titre"), "erreur": r.get("erreur") or "eBay a refusé"})
                    continue
                out["terminees"] += 1
            self.carte_supprimer(cid)
            out["retirees"] += 1
        out["ok"] = not out["erreurs"] or out["retirees"] > 0
        return out

    def carte_vendre(self, cid, d):
        """d : {canal: 'eBay'|'Magasin'|'Break'|'Autre', prix, port_paye, port_charge, frais (optionnel), date, client_id}"""
        d = d or {}
        r = self.reglages_lire()
        with _verrou:
            c = self._db()
            try:
                carte = c.execute("SELECT * FROM cartes WHERE id=?", (cid,)).fetchone()
                if not carte:
                    return {"ok": False, "erreur": "Carte introuvable"}
                prix = _float(d.get("prix")) or 0
                canal = d.get("canal") or "eBay"
                if canal == "eBay":
                    pv = calcul.profit_vente(prix, carte["cout"] or 0, _float(d.get("port_paye")) or 0, _float(d.get("port_charge")) or 0,
                                             r["frais_ebay_pct"] / 100, r["frais_ebay_fixe"])
                else:
                    frais = _float(d.get("frais")) or 0
                    net = prix - frais - (_float(d.get("port_paye")) or 0)
                    pv = {"frais": frais, "net": net, "profit": round(net - (carte["cout"] or 0), 2)}
                if carte["consignataire_id"]:
                    # carte en consignation : le profit de la boutique est sa commission
                    pv["profit"] = round(pv["net"] * self._pct_boutique(c, carte["consignataire_id"], r), 2)
                c.execute("UPDATE cartes SET statut='Vendue', canal=?, prix_vendu=?, frais=?, port_paye=?, port_charge=?, profit=?, "
                          "vendu_le=?, client_id=? WHERE id=?",
                          (canal, prix, pv["frais"], _float(d.get("port_paye")) or 0, _float(d.get("port_charge")) or 0, pv["profit"],
                           d.get("date") or _maintenant(), d.get("client_id"), cid))
                c.commit()
            finally:
                c.close()
        return {"ok": True, **pv}

    def importer_annonces_ebay(self, texte):
        """Rapport « All active listings » : cree ou met a jour les cartes « Listée »."""
        try:
            annonces = ebay_csv.lire_annonces(texte)
        except ValueError as e:
            return {"ok": False, "erreur": str(e)}
        return self._maj_annonces(annonces)

    def _maj_annonces(self, annonces):
        crees = maj = 0
        defaut_sport = self.reglages_lire().get("sport") or sports.DEFAUT
        with _verrou:
            c = self._db()
            try:
                vu = _maintenant()
                for a in annonces:
                    ex = c.execute("SELECT id FROM cartes WHERE item_number=?", (a["item_number"],)).fetchone()
                    if ex:
                        c.execute("UPDATE cartes SET prix_demande=?, statut=CASE WHEN statut='Vendue' THEN statut ELSE 'Listée' END, "
                                  "emplacement='eBay', debut=COALESCE(?, debut), watchers=COALESCE(?, watchers), "
                                  "categorie_ebay=COALESCE(?, categorie_ebay), photo=COALESCE(?, photo), vu_actif_le=? WHERE id=?",
                                  (a["prix"], a.get("debut") or None, a.get("watchers"), a.get("categorie") or None,
                                   a.get("photo") or None, vu, ex["id"]))
                        maj += 1
                    else:
                        c.execute("INSERT INTO cartes (titre, prix_demande, item_number, sku, statut, emplacement, source, cree_le, "
                                  "debut, watchers, categorie_ebay, photo, vu_actif_le, sport) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                  (a["titre"], a["prix"], a["item_number"], a["sku"], "Listée", "eBay", "import eBay", _maintenant(),
                                   a.get("debut") or None, a.get("watchers"), a.get("categorie") or None, a.get("photo") or None, vu,
                                   sports.detecter(a["titre"], defaut=defaut_sport)))
                        crees += 1
                c.commit()
            finally:
                c.close()
        return {"ok": True, "crees": crees, "maj": maj, "lues": len(annonces), "vu": vu}

    def _annonces_terminees(self, vu, n_lues):
        """4 nov 2026 (revue) : une annonce terminee sans vente (plus dans les annonces actives d'eBay) restait « Listée »
        pour toujours. Apres une synchro complete : vue avant, plus vue maintenant, pas vendue -> de retour En stock.
        Prudent : rien en sandbox, rien si eBay n'a rendu aucune annonce (panne), ni s'il en manquerait plus que d'actives."""
        if not vu or ebay_compte.environnement() != "production":     # sandbox / donnees de test : jamais
            return 0
        with _verrou:
            c = self._db()
            try:
                # absente depuis plus de 24 h seulement : une vente met du temps a arriver dans les commandes d'eBay
                lim = (datetime.fromisoformat(str(vu)[:19]) - timedelta(hours=24)).isoformat(timespec="seconds")
                l = [r[0] for r in c.execute("SELECT id FROM cartes WHERE statut='Listée' AND item_number IS NOT NULL "
                                             "AND vu_actif_le IS NOT NULL AND vu_actif_le < ?", (lim,))]
                if not l or not n_lues or len(l) > max(2, n_lues):
                    return 0
                # le numero d'annonce reste (une vente en retard la retrouve) ; « Mettre en vente » accepte une carte En stock
                c.executemany("UPDATE cartes SET statut='En stock', emplacement='Réserve' WHERE id=? AND statut='Listée'", [(i,) for i in l])
                c.commit()
                return len(l)
            finally:
                c.close()

    def _maj_trafic(self, item_ids):
        """31 oct 2026 (Mathieu : « le nombre de vues et de likes de l'annonce : les plus populaires, et celles a liquider »).
        Les vues des 30 derniers jours (API Analytics d'eBay). Rien si le compte n'a pas donne l'acces : on garde les suivis."""
        t = ebay_compte.trafic(item_ids, 30)
        if not t:
            return 0
        with _verrou:
            c = self._db()
            try:
                le = _maintenant()
                for i, d in t.items():
                    c.execute("UPDATE cartes SET vues=?, impressions=?, trafic_le=? WHERE item_number=?",
                              (d.get("vues"), d.get("impressions"), le, str(i)))
                c.commit()
            finally:
                c.close()
        return len(t)

    def importer_ventes_ebay(self, texte):
        """Rapport « Orders » : marque les cartes vendues (par numero d'item),
        sans jamais compter deux fois la meme transaction."""
        try:
            ventes = ebay_csv.lire_ventes(texte)
        except ValueError as e:
            return {"ok": False, "erreur": str(e)}
        return self._maj_ventes(ventes)

    @staticmethod
    def _pct_boutique(c, cons_id, r):
        """La part de la boutique sur une carte en consignation (0..1) : celle du consignataire, sinon celle des reglages."""
        cons = c.execute("SELECT pct_boutique FROM consignataires WHERE id=?", (cons_id,)).fetchone()
        p = cons["pct_boutique"] if cons and cons["pct_boutique"] is not None else r.get("pct_consignation")
        return (_float(p) or 0) / 100

    def frais_calibrer(self):
        """9 nov 2026 (Mathieu : « toujours etre a jour sur les tarifs eBay, a tous les jours ») : le % des frais eBay de ce
        compte suit ce qu'eBay lui a VRAIMENT facture (frais de chaque commande, 120 derniers jours, 5 ventes au moins) :
        (frais - frais par commande) / (prix + port). Un % change a la main (Reglages) n'est plus touche (frais_auto)."""
        r = self.reglages_lire()
        lim = (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d")
        with _verrou:
            c = self._db()
            try:
                lignes = c.execute("SELECT base, frais FROM frais_observes WHERE le >= ? AND base > 0", (lim,)).fetchall()
            finally:
                c.close()
        fixe = float(r.get("frais_ebay_fixe") or 0.40)
        pcts = [(f - (fixe if b > 10 else 0.30)) / b for b, f in lignes if b <= 7500 and f is not None]
        pcts = [p for p in pcts if 0.03 <= p <= 0.30]
        if len(pcts) < 5:
            return {"ok": True, "n": len(pcts), "change": False}
        import statistics as _st
        pct = round(_st.median(pcts) * 100, 2)
        if not 5 <= pct <= 25:
            return {"ok": True, "n": len(pcts), "change": False, "suggere": pct}
        if not r.get("frais_auto", True):
            return {"ok": True, "n": len(pcts), "change": False, "suggere": pct, "manuel": True}
        if abs(pct - float(r.get("frais_ebay_pct") or 0)) < 0.1:
            return {"ok": True, "n": len(pcts), "change": False, "pct": pct}
        self.reglages_sauver({"frais_ebay_pct": pct, "frais_auto": True})
        return {"ok": True, "n": len(pcts), "change": True, "avant": r.get("frais_ebay_pct"), "pct": pct}

    def _maj_ventes(self, ventes):
        r = self.reglages_lire()
        nouvelles = deja = sans_fiche = 0
        with _verrou:
            c = self._db()
            try:
                for v in ventes:
                    if v.get("frais_reels") is not None and (v.get("prix") or 0) > 0 and not v.get("annulee"):
                        # 9 nov 2026 : les frais REELS d'eBay de chaque commande (pour suivre ses tarifs : frais_calibrer)
                        c.execute("INSERT OR IGNORE INTO frais_observes VALUES (?,?,?,?)", (v["transaction_id"], (v.get("date") or _maintenant())[:10],
                                  round((v["prix"] or 0) + (v.get("port_charge") or 0), 2), v["frais_reels"]))
                    if c.execute("SELECT 1 FROM ventes_ebay_vues WHERE transaction_id=?", (v["transaction_id"],)).fetchone():
                        deja += 1
                        continue
                    carte = c.execute("SELECT * FROM cartes WHERE item_number=? AND statut!='Vendue' ORDER BY id LIMIT 1",
                                      (v["item_number"],)).fetchone()
                    # 22 oct 2026 - meme vente deja recue par l'autre source (Trading / commandes) : pas de doublon ;
                    # si celle-ci porte les frais reels, ils remplacent l'estimation.
                    if not carte and v["item_number"]:
                        dv = c.execute("SELECT * FROM cartes WHERE item_number=? AND statut='Vendue' AND canal='eBay' "
                                       "ORDER BY vendu_le DESC LIMIT 1", (v["item_number"],)).fetchone()
                        if dv and abs((datetime.fromisoformat((dv["vendu_le"] or "2000-01-01")[:10])
                                       - datetime.fromisoformat((v["date"] or _maintenant())[:10])).days) <= 7:
                            if v.get("frais_reels") is not None:
                                net = round((v["prix"] or 0) + (v["port_charge"] or 0) - v["frais_reels"], 2)
                                pr = round(net * self._pct_boutique(c, dv["consignataire_id"], r), 2) if dv["consignataire_id"] \
                                    else round(net - (dv["cout"] or 0), 2)
                                c.execute("UPDATE cartes SET frais=?, profit=? WHERE id=?", (v["frais_reels"], pr, dv["id"]))
                            c.execute("INSERT INTO ventes_ebay_vues VALUES (?)", (v["transaction_id"],))
                            deja += 1
                            continue
                    pv = calcul.profit_vente(v["prix"] or 0, (carte["cout"] if carte else 0) or 0, 0, v["port_charge"] or 0,
                                             r["frais_ebay_pct"] / 100, r["frais_ebay_fixe"])
                    if v.get("frais_reels") is not None:          # frais exacts d'eBay (API)
                        net = round((v["prix"] or 0) + (v["port_charge"] or 0) - v["frais_reels"], 2)
                        pv = {"frais": v["frais_reels"], "net": net, "profit": round(net - ((carte["cout"] if carte else 0) or 0), 2)}
                    if carte and carte["consignataire_id"]:      # 4 nov 2026 (revue) : synchro eBay / CSV aussi : la commission
                        pv["profit"] = round(pv["net"] * self._pct_boutique(c, carte["consignataire_id"], r), 2)
                    if carte:
                        c.execute("UPDATE cartes SET statut='Vendue', canal='eBay', prix_vendu=?, port_charge=?, frais=?, profit=?, "
                                  "vendu_le=? WHERE id=?", (v["prix"], v["port_charge"] or 0, pv["frais"], pv["profit"],
                                                           v["date"] or _maintenant(), carte["id"]))
                    else:
                        sans_fiche += 1
                        c.execute("INSERT INTO cartes (titre, item_number, statut, emplacement, canal, prix_vendu, port_charge, frais, "
                                  "profit, vendu_le, source, cree_le) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                                  (v["titre"], v["item_number"], "Vendue", "eBay", "eBay", v["prix"], v["port_charge"] or 0,
                                   pv["frais"], pv["profit"], v["date"] or _maintenant(), "import eBay", _maintenant()))
                    c.execute("INSERT INTO ventes_ebay_vues VALUES (?)", (v["transaction_id"],))
                    nouvelles += 1
                c.commit()
            finally:
                c.close()
        return {"ok": True, "nouvelles": nouvelles, "deja": deja, "sans_fiche": sans_fiche}

    def exporter_brouillons(self, ids):
        ids = [int(i) for i in (ids or [])]
        if not ids:
            return {"ok": False, "erreur": "Choisis des cartes"}
        with _verrou:
            c = self._db()
            try:
                cartes = _dicts(c.execute(f"SELECT * FROM cartes WHERE id IN ({','.join('?' * len(ids))})", ids))
            finally:
                c.close()
        return {"ok": True, "csv": ebay_csv.fichier_brouillons(cartes, self.reglages_lire().get("description_ebay") or ""),
                "nom": f"brouillons_ebay_{datetime.now():%Y%m%d_%H%M}.csv", "nb": len(cartes)}

    # -- sante de l'inventaire (toutes categories) -----------------------------------------------
    def _annonces_actives(self, c):
        """Annonces vues actives a la derniere synchro (ou importees) - les autres sont terminees."""
        dern = c.execute("SELECT MAX(vu_actif_le) FROM cartes").fetchone()[0]
        if not dern:
            return []
        return _dicts(c.execute("SELECT * FROM cartes WHERE statut='Listée' AND item_number IS NOT NULL AND vu_actif_le >= ?",
                                (dern[:10],)))

    def sante_rafraichir(self, n=40):
        """Compare n annonces au marche (les jamais vues, puis les plus anciennes) et cherche
        les rachats possibles pour les articles bien vendus. 1 appel API par annonce."""
        with _verrou:
            c = self._db()
            try:
                actives = self._annonces_actives(c)
                vus = {r[0]: r[1] for r in c.execute("SELECT item_number, maj FROM sante")}
            finally:
                c.close()
        limite = (datetime.now() - timedelta(days=3)).isoformat()
        a_faire = sorted((a for a in actives if vus.get(a["item_number"], "") < limite), key=lambda a: vus.get(a["item_number"], ""))
        faits, erreur = 0, None
        import cartes_match
        import deals as _deals
        for a in a_faire[:int(n)]:
            carte = cartes_match.est_carte(a["titre"])                        # 24 oct 2026 : une carte -> seulement la MEME carte
            # 27 oct 2026 (Forsberg Fabrics AUTO compare a des Fabrics sans auto) : l'auto connue de la fiche compte meme si le
            # titre ne le dit pas
            import suivi_valeur as _sv
            titre_c = _sv._titre(a)                                          # 9 nov 2026 : + parallele et numerotation de la fiche
            q = (cartes_match.requete_ebay(cartes_match.cible_titre(titre_c, a.get("joueur"))) if carte else None) or sante.requete(a["titre"])
            try:
                res = ebay_compte.rechercher(q, a.get("categorie_ebay") or (CATEGORIE_CARTES if carte else None), limite=100)
            except (RuntimeError, OSError) as e:
                erreur = str(e)
                break
            if carte:
                _c, semblables, _e = cartes_match.filtrer_carte(titre_c, res, a.get("joueur"), exclure_id=a["item_number"])
                if a.get("id"):                  # 9 nov 2026 : le repere « annonces » de la carte, sans recherche de plus
                    try:
                        self._repere_annonces(a, titre_c, semblables)
                    except Exception:
                        pass
                # 27 oct 2026 (Mathieu : « pas de faux prix ») : le marche d'une carte = ses ventes reelles SURES, pas les prix demandes
                try:                         # 6 nov 2026 : 90 derniers jours, sans tes achats (comme l'inventaire)
                    vs = self._ventes_inventaire([v for v in (vendues.memes_annonce(titre_c, fond=True).get("ventes") or []) if v.get("prix")])
                except Exception:
                    vs = []
                sure = _deals.valeur_sure(vs, titre_c)[0] if len(vs) >= 2 else None
                ev = sante.evaluer_vendues(a["prix_demande"], sure, len(vs), sante.age_jours(a.get("debut")), a.get("watchers"))
            else:
                semblables = [x for x in res if x["item_id"] != str(a["item_number"])]
                # 10 nov 2026 (licence eBay §9.5) : sans accord d'eBay, les annonces pareilles ne donnent plus de verdict
                # ni de prix suggere (seulement « traine » : l'age de TON annonce) ; elles restent montrees
                ev = sante.evaluer(a["prix_demande"], semblables if prix_annonces_permis() else [], sante.age_jours(a.get("debut")), a.get("watchers"))
            totaux = [] if not prix_annonces_permis() else sorted(round((x.get("prix_cad") or 0) + (x.get("port_cad") or 0), 2) for x in semblables if x.get("prix_cad"))
            comps = sorted(({"titre": x["titre"], "total": round((x.get("prix_cad") or 0) + (x.get("port_cad") or 0), 2),
                             "photo": x.get("photo"), "url": x.get("url")} for x in semblables if x.get("prix_cad")), key=lambda x: x["total"])[:12]
            with _verrou:
                c = self._db()
                try:
                    c.execute("INSERT OR REPLACE INTO sante (item_number, maj, verdict, suggestion, mediane, n, ecart, requete, fait, comps, bas) "
                              "VALUES (?,?,?,?,?,?,?,?,0,?,?)", (a["item_number"], _maintenant(), ev["verdict"], ev["suggestion"], ev["mediane"],
                                                            ev["n"], ev["ecart"], q, json.dumps(comps, ensure_ascii=False),
                                                            totaux[0] if totaux else None))
                    c.commit()
                finally:
                    c.close()
            faits += 1
        rach = 0 if erreur else self._chercher_rachats(max(5, int(n) // 4))
        return {"ok": erreur is None, "evaluees": faits, "restantes": max(0, len(a_faire) - faits), "rachats": rach, "erreur": erreur}

    def _chercher_rachats(self, n):
        depuis = (datetime.now() - timedelta(days=180)).isoformat()
        with _verrou:
            c = self._db()
            try:
                vendues = _dicts(c.execute("SELECT titre, prix_vendu, categorie_ebay FROM cartes WHERE statut='Vendue' AND prix_vendu >= 20 "
                                           "AND vendu_le >= ? ORDER BY vendu_le DESC LIMIT 300", (depuis,)))
                vus = {r[0]: r[1] for r in c.execute("SELECT cle, maj FROM rachats_vus")}
                mes = {r[0] for r in c.execute("SELECT item_number FROM cartes WHERE item_number IS NOT NULL")}
            finally:
                c.close()
        limite = (datetime.now() - timedelta(hours=12)).isoformat()
        trouvees = 0
        faites = 0
        import cartes_match
        for v in vendues:
            carte = cartes_match.est_carte(v["titre"])
            q = (cartes_match.requete_ebay(cartes_match.cible_titre(v["titre"])) if carte else None) or sante.requete(v["titre"])
            if not q or vus.get(q, "") > limite:
                continue
            if faites >= n:
                break
            faites += 1
            try:
                res = ebay_compte.rechercher(q, v.get("categorie_ebay") or (CATEGORIE_CARTES if carte else None),
                                             prix_max=v["prix_vendu"] * sante.RACHAT_RATIO, recentes=True, limite=50)
            except (RuntimeError, OSError):
                break
            ref = v["prix_vendu"]
            if carte:
                _c, res, _e = cartes_match.filtrer_carte(v["titre"], res)
                # 26 oct 2026 : la reference = les ventes recentes de la meme carte (pas seulement notre vente d'avant,
                # qui peut etre un coup de chance) ; on garde la plus basse des deux
                try:
                    import vendues
                    vm = vendues.memes(v["titre"], requete=False, n=8, fond=True)
                    if (vm.get("nb") or 0) >= 3 and vm.get("mediane"):
                        ref = min(ref, vm["mediane"])
                except Exception:
                    pass
            ops = sante.opportunites(ref, res, exclure=mes)
            with _verrou:
                c = self._db()
                try:
                    c.execute("INSERT OR REPLACE INTO rachats_vus VALUES (?,?)", (q, _maintenant()))
                    for o in ops[:3]:
                        c.execute("INSERT OR IGNORE INTO opportunites (item_id, titre, total, url, photo, ref_titre, ref_prix, ratio, vu_le) "
                                  "VALUES (?,?,?,?,?,?,?,?,?)", (o["item_id"], o["titre"], o["total"], o["url"], o["photo"], v["titre"],
                                                                  ref, o["ratio"], _maintenant()))
                        trouvees += 1
                    c.commit()
                finally:
                    c.close()
        return trouvees

    def sante_resume(self):
        """Les 4 compteurs de l'accueil."""
        with _verrou:
            c = self._db()
            try:
                actives = {a["item_number"] for a in self._annonces_actives(c)}
                compte = {"baisser": 0, "monter": 0, "traine": 0, "ok": 0}
                for item, verdict, fait in c.execute("SELECT item_number, verdict, fait FROM sante"):
                    if item in actives and not fait and verdict in compte:
                        compte[verdict] += 1
                limite = (datetime.now() - timedelta(days=4)).isoformat()
                compte["racheter"] = c.execute("SELECT COUNT(*) FROM opportunites WHERE masque=0 AND vu_le >= ?", (limite,)).fetchone()[0]
                evaluees = c.execute("SELECT COUNT(*) FROM sante").fetchone()[0]
            finally:
                c.close()
        return {"compte": compte, "actives": len(actives), "evaluees": min(evaluees, len(actives)),
                "ebay": ebay_compte.statut().get("connecte"), "cles": ebay_compte.statut().get("cles_ok")}

    def sante_liste(self, verdict):
        if not ebay_prix_actif():
            return []
        with _verrou:
            c = self._db()
            try:
                if verdict == "racheter":
                    limite = (datetime.now() - timedelta(days=4)).isoformat()
                    return [o for o in _dicts(c.execute("SELECT * FROM opportunites WHERE masque=0 AND vu_le >= ? ORDER BY ratio LIMIT 100", (limite,)))
                            if _opp_ok(o.get("titre"))]
                actives = {a["item_number"]: a for a in self._annonces_actives(c)}
                out = []
                for s in _dicts(c.execute("SELECT * FROM sante WHERE verdict=? AND fait=0", (verdict,))):
                    a = actives.get(s["item_number"])
                    if a:
                        out.append({**s, "titre": a["titre"], "prix": a["prix_demande"], "photo": a.get("photo"), "watchers": a.get("watchers"),
                                    "age": sante.age_jours(a.get("debut")), "carte_id": a["id"], "cout": a.get("cout")})
            finally:
                c.close()
        cle = {"baisser": lambda x: -(x.get("ecart") or 0), "monter": lambda x: x.get("ecart") or 0,
               "traine": lambda x: -(x.get("age") or 0)}.get(verdict, lambda x: 0)
        out = sorted(out, key=cle)
        import forfaits                          # 27 oct 2026 (revue) : Gratuit = le repere prix sur 3 cartes, ici aussi
        if not forfaits.est_pro():
            for x in out[forfaits.LIMITES["repere"]:]:
                for k in ("mediane", "suggestion", "ecart", "bas", "n"):
                    x.pop(k, None)
                x["marche_pro"] = True
        return out

    def sante_fait(self, item_number):
        """Le vendeur a traite la suggestion : cachee jusqu'a la prochaine evaluation."""
        with _verrou:
            c = self._db()
            try:
                c.execute("UPDATE sante SET fait=1 WHERE item_number=?", (str(item_number),))
                c.execute("UPDATE opportunites SET masque=1 WHERE item_id=?", (str(item_number),))
                c.commit()
            finally:
                c.close()
        return {"ok": True}

    # -- prix eBay en un tap, ou en automatique (27 oct 2026) ------------------------------------
    # Mathieu : « une maniere rapide de modifier ses prix, un clic par annonce ou toutes d'un coup, ou une solution cle en
    # main qui agit directement dans eBay ». « Tout appliquer » : l'ecran envoie chaque prix (ebay_changer_prix) apres UNE
    # confirmation. Mode Auto (Pro, choisi par le vendeur) : une fois par jour, les prix conseilles sont appliques dans
    # eBay, dans ses limites : jamais plus de max_pct % par jour, jamais sous son plancher ni sous son cout + marge,
    # au plus max_jour annonces ; chaque changement est note (journal) et il recoit un resume.
    PRIX_AUTO_DEFAUT = {"actif": False, "baisser": True, "monter": True, "max_pct": 15, "max_jour": 25, "plancher": 1.0, "marge_min_pct": 0}

    def _chemin_prix_auto(self):
        import comptes
        return os.path.join(comptes.dossier() or comptes.DONNEES, "prix_auto.json")

    def _prix_auto_etat(self):
        try:
            with open(self._chemin_prix_auto(), encoding="utf-8") as f:
                return json.load(f) or {}
        except (OSError, ValueError):
            return {}

    def prix_auto_lire(self):
        import forfaits
        r = self.reglages_lire().get("prix_auto")
        cfg = {**self.PRIX_AUTO_DEFAUT, **(r if isinstance(r, dict) else {})}
        e = self._prix_auto_etat()
        return {**cfg, "pro": forfaits.est_pro(), "dernier": e.get("dernier"), "journal": (e.get("journal") or [])[-30:][::-1]}

    def prix_auto_regler(self, d):
        d = d or {}
        cfg = {**self.PRIX_AUTO_DEFAUT, **{k: v for k, v in (self.reglages_lire().get("prix_auto") or {}).items() if k in self.PRIX_AUTO_DEFAUT}}
        borne = lambda v, a, b, defaut: max(a, min(b, _float(v) if _float(v) is not None else defaut))
        if "actif" in d:
            import forfaits
            if d["actif"] and not forfaits.est_pro():
                return {"ok": False, "erreur": "Le mode Auto des prix fait partie de Pro", "pro_requis": True}
            cfg["actif"] = bool(d["actif"])
            if cfg["actif"]:
                cfg["active_le"] = _maintenant()
        for k in ("baisser", "monter"):
            if k in d:
                cfg[k] = bool(d[k])
        if "max_pct" in d:
            cfg["max_pct"] = round(borne(d["max_pct"], 3, 30, 15))
        if "max_jour" in d:
            cfg["max_jour"] = int(borne(d["max_jour"], 1, 100, 25))
        if "plancher" in d:
            cfg["plancher"] = round(borne(d["plancher"], 0.99, 100000, 1.0), 2)
        if "marge_min_pct" in d:
            cfg["marge_min_pct"] = round(borne(d["marge_min_pct"], -50, 300, 0))
        self.reglages_sauver({"prix_auto": cfg})
        return {"ok": True, **self.prix_auto_lire()}

    @staticmethod
    def _prix_cible(a, cfg):
        """Le prix a mettre pour une annonce, dans les limites du vendeur (None = ne rien changer)."""
        avant, sug = _float(a.get("prix")), _float(a.get("suggestion"))
        if not avant or not sug or avant <= 0:
            return None
        m = cfg["max_pct"] / 100
        p = max(avant * (1 - m), min(avant * (1 + m), sug))
        cout = _float(a.get("cout"))
        plancher = max(cfg["plancher"], cout * (1 + cfg["marge_min_pct"] / 100) if cout else 0, 0.99)
        # 29 oct 2026 (Mathieu : « toujours des multiples de 5 ») : le multiple de 5 le plus proche, du meme cote du prix
        # actuel et dans la limite du jour ; aucun -> on ne change rien
        lo, hi = avant * (1 - m), avant * (1 + m)
        mult = [5.0 * k for k in range(max(1, math.ceil(lo / 5.0)), math.floor(hi / 5.0) + 1)]
        mult = [x for x in mult if (x < avant if p < avant else x > avant)]
        if not mult:
            return None
        p = min(mult, key=lambda x: abs(x - p))
        if p < plancher:
            p = max(5.0, 5.0 * math.ceil(plancher / 5.0))
        if abs(p - avant) < max(0.5, avant * 0.02):
            return None                                   # trop petit pour valoir un changement
        return p

    def prix_auto_appliquer(self, force=False):
        """Appele chaque heure par le serveur : au plus une fois par 20 h, seulement si le vendeur l'a choisi (et Pro)."""
        import forfaits
        cfg = {**self.PRIX_AUTO_DEFAUT, **(self.reglages_lire().get("prix_auto") or {})}
        if not cfg.get("actif") or not forfaits.est_pro():
            return {"ok": True, "faits": 0, "raison": "inactif"}
        e = self._prix_auto_etat()
        if not force and e.get("dernier") and (datetime.now() - datetime.fromisoformat(e["dernier"])).total_seconds() < 20 * 3600:
            return {"ok": True, "faits": 0, "raison": "deja fait aujourd'hui"}
        if not ebay_compte.statut().get("ecriture"):
            return {"ok": False, "faits": 0, "erreur": "Reconnecte eBay pour que le mode Auto change tes prix"}
        cands = (self.sante_liste("baisser") if cfg["baisser"] else []) + (self.sante_liste("monter") if cfg["monter"] else [])
        journal, faits = e.get("journal") or [], 0
        for a in cands:
            if faits >= cfg["max_jour"]:
                break
            p = self._prix_cible(a, cfg)
            if p is None:
                continue
            r = self.ebay_changer_prix(a["item_number"], p)
            journal.append({"le": _maintenant(), "item": a["item_number"], "titre": (a.get("titre") or "")[:80], "avant": a.get("prix"),
                            "apres": p, "ok": bool(r.get("ok")), "erreur": None if r.get("ok") else str(r.get("erreur") or "")[:120]})
            faits += 1 if r.get("ok") else 0
        e = {"dernier": _maintenant(), "journal": journal[-200:]}
        with open(self._chemin_prix_auto(), "w", encoding="utf-8") as f:
            json.dump(e, f)
        if faits:
            try:
                self._push("Prix ajustés sur eBay", f"SlabCoach a ajusté {faits} prix selon le marché, dans tes limites.", {"lien": "#sante/auto"})
            except Exception:
                pass
        return {"ok": True, "faits": faits}

    # -- offres aux acheteurs interesses (28 oct 2026, API Negotiation d'eBay) ------------------
    def offres_liste(self, force=False):
        """Les annonces qu'un acheteur surveille ou a laissees dans son panier, avec un rabais conseille.
        Rabais conseille : l'ecart avec le marche si l'annonce est trop chere (5 a 25 %), sinon 10 % ; jamais sous le cout."""
        import ebay_offres
        st = ebay_compte.statut()
        if not st.get("connecte"):
            return {"ok": False, "erreur": "Compte eBay non connecté", "items": []}
        r = ebay_offres.eligibles(force=bool(force))
        if not r.get("ok"):
            return {**r, "items": []}
        ids, recents = set(r.get("ids") or []), ebay_offres.recentes()
        with _verrou:
            c = self._db()
            try:
                actives = {a["item_number"]: a for a in self._annonces_actives(c)}
                sante_ = {x["item_number"]: x for x in _dicts(c.execute("SELECT item_number, verdict, suggestion, mediane FROM sante"))}
            finally:
                c.close()
        rg = self.reglages_lire()
        fp, ff = (rg.get("frais_ebay_pct") or 0) / 100, rg.get("frais_ebay_fixe") or 0
        items = []
        for i in ids:
            a = actives.get(i)
            if not a or i in recents:
                continue
            prix, cout0 = _float(a.get("prix_demande")), _float(a.get("cout"))
            # 4 nov 2026 (revue) : « jamais sous le cout » apres les frais eBay (le prix qu'il faut pour recuperer le cout)
            cout = round((cout0 + ff) / (1 - fp), 2) if cout0 and fp < 1 else cout0
            s_ = sante_.get(i) or {}
            pct = 10.0
            if prix and _float(s_.get("suggestion")) and s_["suggestion"] < prix:
                pct = max(5.0, min(25.0, round(100 * (1 - s_["suggestion"] / prix))))
            if prix and cout and prix * (1 - pct / 100) < cout:
                pct = max(5.0, int(1000 * (1 - cout / prix)) / 10) if cout < prix * 0.95 else None
            items.append({"item_number": i, "titre": a.get("titre"), "prix": prix, "photo": a.get("photo"), "watchers": a.get("watchers"),
                          "cout": cout0, "carte_id": a.get("id"), "pct": pct, "mediane": s_.get("mediane"),
                          "sous_cout": pct is None})
        items.sort(key=lambda x: (x["sous_cout"], -(x.get("watchers") or 0), -(x.get("prix") or 0)))
        return {"ok": True, "items": items, "marche": r.get("marche"), "le": r.get("le"), "n_ebay": len(ids)}

    def offres_envoyer(self, item_number, pct, message=None):
        """Un tap = une offre a TOUS les acheteurs interesses d'une annonce (eBay les previent). Gratuit : 3 par jour."""
        import ebay_offres
        import forfaits
        try:
            forfaits.verifier("offres_jour")
        except forfaits.LimiteAtteinte as e:
            return {"ok": False, "erreur": str(e), "pro_requis": True}
        if not ebay_compte.statut().get("ecriture"):
            return {"ok": False, "erreur": "Reconnecte eBay pour envoyer des offres depuis l'app."}
        r = ebay_offres.envoyer(item_number, pct, message)
        if r.get("ok"):
            forfaits.compter("offres_jour")
        return r

    def offres_compte(self):
        """Pour l'accueil : combien d'annonces ont des acheteurs interesses (garde d'une heure, aucun appel eBay ici)."""
        import ebay_offres
        g = (ebay_offres._lire().get("eligibles") or {})
        rec = ebay_offres.recentes()
        return {"n": len([i for i in g.get("ids") or [] if i not in rec]), "le": g.get("le")}

    # -- compte eBay (OAuth officiel) -----------------------------------------------------------
    def ebay_statut(self):
        return ebay_compte.statut()

    def ebay_cles_sauver(self, d):
        d = d or {}
        return ebay_compte.sauver_cles(d.get("app_id"), d.get("cert_id"), d.get("runame"))

    def ebay_url_connexion(self):
        try:
            return ebay_compte.url_connexion()
        except RuntimeError as e:
            return {"ok": False, "erreur": str(e)}

    # 2 nov 2026 (Mathieu : « un utilisateur doit voir la meme chose sur son ordi que sur son cell ») ------------------------
    def code_appareil(self):
        """Un code a 6 chiffres (10 min) qui ouvre CE compte sur un autre appareil (slabcoach.com/auth/code)."""
        cid = comptes.courant()
        if not cid or not comptes.MULTI:
            return {"ok": False, "erreur": "Connexion requise"}
        return {"ok": True, "code": comptes.code_creer(cid), "expire_s": 600}

    def connexions(self):
        """Les facons d'ouvrir ce compte : Apple, Google, eBay (sans rien montrer d'autre que oui / non et le courriel)."""
        cid = comptes.courant()
        if not cid:
            return {"ok": False, "erreur": "Connexion requise"}
        e = comptes.info(cid)
        ids = set(e.get("identites") or [])
        env = str(e.get("env") or "")
        out = {"apple": env == "apple" or any(x.startswith("apple:") for x in ids),
               "google": env == "google" or any(x.startswith("google:") for x in ids),
               "ebay": bool(e.get("ebay_user_id")) or env in ("production", "sandbox"),
               "courriel": e.get("courriel") or None}
        try:
            import auth_tiers
            out["offerts"] = [f for f in ("apple", "google") if f in auth_tiers.actifs()]
        except Exception:
            out["offerts"] = []
        return {"ok": True, **out}

    def connexion_jeton_lier(self, fournisseur):
        """Un jeton a usage unique (10 min) pour relier Apple ou Google a CE compte (/auth/<fournisseur>?lier=...)."""
        if fournisseur not in ("apple", "google"):
            return {"ok": False, "erreur": "Connexion inconnue"}
        r = self.ebay_jeton_lier()
        if not r.get("ok"):
            return r
        return {"ok": True, "jeton": r["jeton"], "url": f"/auth/{fournisseur}?lier={r['jeton']}"}

    def ebay_jeton_lier(self):
        """28 oct 2026 : un jeton a usage unique (10 min) pour relier eBay dans le navigateur securise de l'iPhone."""
        cid = comptes.courant()
        if not cid:
            return {"ok": False, "erreur": "Connexion requise"}
        import secrets as _s
        import time as _t
        for k in [k for k, v in LIER.items() if _t.time() - v[1] > 600]:
            LIER.pop(k, None)
        j = _s.token_urlsafe(24)
        LIER[j] = (cid, _t.time())
        return {"ok": True, "jeton": j}

    def ebay_terminer(self, texte, etat=None):
        try:
            return ebay_compte.terminer_connexion(texte, etat)
        except RuntimeError as e:
            return {"ok": False, "erreur": str(e)}

    def ebay_deconnecter(self):
        return ebay_compte.deconnecter()

    # -- 21 oct 2026 : sandbox / production + ecriture eBay (toujours un tap du vendeur) -------
    def ebay_environnement(self, env):
        r = ebay_compte.changer_environnement(env)
        with _verrou:
            _connecter(self.chemin_db).close()
        return r

    def _ecrire_ebay(self, fn, *args, **kw):
        import importlib
        import ebay_ecriture
        mod, nom = (importlib.import_module(fn.split(".")[0]), fn.split(".")[1]) if "." in fn else (ebay_ecriture, fn)
        try:
            r = getattr(mod, nom)(*args, **kw)
        except (RuntimeError, ValueError, OSError) as e:
            r = {"ok": False, "erreur": str(e)}
        except Exception as e:                      # jamais une erreur muette
            r = {"ok": False, "erreur": f"{type(e).__name__} : {e}"}
        # journal des ecritures eBay (diagnostic) : ni jeton ni cle, seulement le resultat
        try:
            import comptes
            with open(os.path.join(comptes.dossier() or DOSSIER, "ebay_ecriture_journal.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps({"le": _maintenant(), "env": ebay_compte.environnement(), "action": fn,
                                    "ok": r.get("ok"), "erreur": r.get("erreur"), "item_id": r.get("item_id"),
                                    "creees": r.get("creees"), "erreurs": (r.get("erreurs") or [])[:5]},
                                   ensure_ascii=False) + "\n")
        except OSError:
            pass
        return r

    def ebay_publier(self, cid, prix=None, verifier=False):
        """Met UNE carte de l'inventaire en vente (photo de la fiche, details deja remplis)."""
        import forfaits
        try:                                     # 27 oct 2026 (revue) : meme limite du Gratuit que l'ecran Vendre
            forfaits.verifier("annonces_mois")
        except forfaits.LimiteAtteinte as e:
            return {"ok": False, "erreur": str(e), "pro_requis": True}
        with _verrou:
            c = self._db()
            try:
                carte = c.execute("SELECT * FROM cartes WHERE id=?", (cid,)).fetchone()
            finally:
                c.close()
        if not carte:
            return {"ok": False, "erreur": "Carte introuvable"}
        carte = dict(carte)
        if carte.get("item_number") and carte.get("statut") == "Listée":   # 4 nov 2026 : une annonce terminee se remet en vente
            return {"ok": False, "erreur": "Déjà sur eBay"}
        prix = _float(prix) or carte.get("prix_demande") or carte.get("valeur")
        if not prix:
            return {"ok": False, "erreur": "Indique un prix"}
        r_ = self.reglages_lire()
        carte["sport"] = carte.get("sport") or self.sport_de(carte)          # 23 oct 2026 - Sport / League eBay
        photos = [carte["photo"]] if str(carte.get("photo") or "").startswith("https://") else []
        sku = carte.get("sku") or f"LR-{carte['id']}"
        r = self._ecrire_ebay("publier", carte, prix, photos, r_.get("description_ebay") or "",
                              expedition=r_.get("expedition_ebay") or None, sku=sku, verifier_seulement=bool(verifier))
        if r.get("ok") and r.get("item_id"):
            forfaits.compter("annonces_mois")
            with _verrou:
                c = self._db()
                try:
                    c.execute("UPDATE cartes SET item_number=?, sku=?, statut='Listée', prix_demande=?, debut=?, vu_actif_le=NULL WHERE id=?",
                              (r["item_id"], sku, prix, _maintenant(), cid))
                    c.commit()
                finally:
                    c.close()
        return r

    # -- « Vendre » (24 oct 2026) : une annonce complete a partir des photos (voir annonces.py) ----------
    def annonce_preparer(self, champs, langue=None):
        """Champs de la carte (lus sur la photo ou tapes) -> titre, prix suggere (memes cartes), description, details.
        Rien n'est publie ni enregistre ici."""
        import annonces
        import cartes_match
        import forfaits
        try:                                     # 27 oct 2026 (revue) : le quota eBay est partage par tous les comptes
            forfaits.verifier("preparer_jour")
        except forfaits.LimiteAtteinte as e:
            return {"ok": False, "erreur": str(e), "pro_requis": True}
        forfaits.compter("preparer_jour")
        c = {k: v for k, v in (champs or {}).items() if not str(k).startswith("_")}
        c["sport"] = c.get("sport") or self.sport_de(c)
        titre = annonces.titre_optimise(c) if (c.get("joueur") or c.get("set_nom")) else str(c.get("titre") or "")[:80]
        r = self.reglages_lire()
        modele = annonces.modele(r.get("modele_annonce"))
        fp, ff = (r["frais_ebay_pct"] or 0) / 100, r["frais_ebay_fixe"] or 0
        prix, comps, n, note, source, vendues_l = None, [], 0, None, None, []
        bassin_v = []                            # 10 nov 2026 : les ventes deja lues, pour les cartes similaires
        vendu, affiche = None, None             # 30 oct 2026 : les 2 reperes montres au vendeur (ventes et annonces)
        # 30 oct 2026 (Mathieu : « proposer un prix selon les last sold ») : d'abord les VENTES reelles de la meme carte
        # (SoldComps, cache 3 jours : souvent gratuit) ; les annonces en vente seulement s'il n'y a aucune vente
        if titre and ebay_prix_actif():
            try:
                import vendues
                vs = vendues.memes(titre, requete=False, fond=False, n=24)
                brutes = [v for v in vs.get("ventes") or [] if v.get("prix")]
                bassin_v = list(brutes)
                # 8 nov 2026 (Mathieu : « le 25 $ de ma Anders Lee, c'est MA carte ») : jamais tes propres achats eBay (ni la
                # vente au prix paye pour cette carte), et les 90 derniers jours seulement, comme la valeur de l'inventaire
                try:
                    carte_i = self.carte_lire(int(c["id"])) if str(c.get("id") or "").isdigit() else None
                except Exception:
                    carte_i = None
                ventes = self._ventes_inventaire(brutes, carte_i or None)
                vendues_l = [{"titre": v.get("titre"), "prix": v.get("prix"), "le": v.get("le"), "url": v.get("url"), "photo": v.get("photo")} for v in ventes[:10]]
                sure = len(ventes) >= 3 and len(ventes) == len(brutes) and bool(vs.get("mediane"))
                base = (vs.get("mediane") if sure else None) or (cartes_match.mediane_robuste([v["prix"] for v in ventes[:5]])[0] if ventes else None)
                if ventes:
                    vendu = {"mediane": round(base, 2) if base else None, "n": len(ventes), "sure": sure}
                if base:
                    m_ = sante.prix_rond(base)
                    prix = {"marche": m_, "vite": max(5.0, sante.prix_rond(base * 0.90, plafond=m_)), "haut": max(m_ + 5, sante.prix_rond(base * 1.10)),
                            "mediane": round(base, 2), "bas": min(v["prix"] for v in ventes[:12]), "max": max(v["prix"] for v in ventes[:12])}
                    n, source = len(ventes), ("vendues" if sure else "vendues_peu")
            except Exception as e:
                note = str(e)[:120]
        if titre and not prix and ebay_prix_actif():
            # 10 nov 2026 (Mathieu : « c'est le prix suggere qui va etre difficile », licence eBay §9.5 : les annonces lues
            # par l'API ne doivent pas servir a modeliser un prix) : sans ventes de LA carte, les VENTES des cartes proches
            # d'abord (saisons voisines, autre numerotation ou parallele, inscription), dites comme telles
            try:
                ap = self._prix_similaires(titre, c.get("joueur"), bassin_v)
                if ap:
                    val, src_, n_, vv = ap
                    m_ = sante.prix_rond(val)
                    prix = {"marche": m_, "vite": max(5.0, sante.prix_rond(val * 0.90, plafond=m_)), "haut": max(m_ + 5, sante.prix_rond(val * 1.10)),
                            "mediane": round(val, 2), "bas": min(v["prix"] for v in vv), "max": max(v["prix"] for v in vv)}
                    n, source = n_, "similaires"
                    vendu = {"mediane": round(val, 2), "n": n_, "sure": False, "similaires": src_}
                    vendues_l = [{k: v.get(k) for k in ("titre", "prix", "le", "url", "photo", "note")} for v in vv[:10]]
            except Exception as e:
                print("Preparer (similaires) : " + repr(e), flush=True)
        if titre:
            try:
                cib = cartes_match.cible_titre(titre, c.get("joueur"))
                res = ebay_compte.rechercher(cartes_match.requete_ebay(cib) or titre, categorie=CATEGORIE_CARTES, limite=100, fond=False)
                _c, gardees, _e = cartes_match.filtrer_carte(titre, res, c.get("joueur"))
                tot = [round((x.get("prix_cad") or 0) + (x.get("port_cad") or 0), 2) for x in gardees if x.get("prix_cad")]
                med, garde = cartes_match.mediane_robuste(tot)
                if med and prix_annonces_permis():
                    affiche = {"mediane": round(med, 2), "bas": round(min(tot), 2), "n": len(tot)}
                if med and not prix and prix_annonces_permis():   # aucune vente : les memes cartes en vente
                    # 8 nov 2026 (Mathieu : « si aucun autre comp, mettre 10 % moins cher que la mediane des memes cartes
                    # affichees ») : les annonces demandent souvent trop ; le marche = leur mediane moins 10 %
                    n = len(garde)
                    b_ = round(med * (1 - RABAIS_ANNONCES), 2)
                    m_ = sante.prix_rond(b_)
                    prix = {"marche": m_, "vite": max(5.0, sante.prix_rond(b_ * 0.90, plafond=m_)), "haut": max(m_ + 5, sante.prix_rond(b_ * 1.10)),
                            "mediane": b_, "bas": garde[0], "max": garde[-1], "annonces_mediane": round(med, 2)}
                    source = "annonces"
                comps = sorted(({"titre": x["titre"], "total": round((x.get("prix_cad") or 0) + (x.get("port_cad") or 0), 2),
                                 "photo": x.get("photo"), "url": x.get("url")} for x in gardees if x.get("prix_cad")),
                               key=lambda x: abs(x["total"] - (med or 0)))[:8]
            except Exception as e:               # 9 nov 2026 (Mathieu : « erreur de serveur » apres le titre) : eBay qui
                note = str(e)[:120]              # repond mal ne bloque jamais la vente : pas de comps, l'annonce continue
                print("Preparer (annonces eBay) : " + repr(e), flush=True)
        franco = (langue or r.get("langue") or "fr") != "en"
        desc = annonces.description(c, titre, franco, modele["etat"], r.get("nom_boutique"), modele["retours"], modele["expedition"])
        # 30 oct 2026 : une description par livraison (l'ecran montre celle qui partira vraiment : politique eBay, suivi > 30 $...)
        descs = {k: annonces.description(c, titre, franco, modele["etat"], r.get("nom_boutique"), modele["retours"], k)
                 for k in ("lettre", "suivi", "gratuit", "politique")}
        try:
            jetons = ebay_compte._lire(ebay_compte.chemin_jetons())
        except Exception:
            jetons = {}
        if not ebay_prix_actif():                # interrupteur : pas de prix suggere pour une annonce eBay
            prix, n, comps, note = None, 0, [], "Choisis ton prix"
        return {"ok": True, "titre": titre, "carte": c, "prix": prix, "n": n, "comps": comps, "note": note, "description": desc, "descriptions": descs,
                "source_prix": source, "vendues": vendues_l, "vendu": vendu, "affiche": affiche,
                "specifiques": annonces.specifiques(c), "modele": modele, "frais_pct": r["frais_ebay_pct"], "frais_fixe": ff,
                "etats": {k: v[2] if franco else v[1] for k, v in annonces.ETATS_BRUTS.items()},
                "net_marche": round(prix["marche"] * (1 - fp) - ff, 2) if prix else None,
                "promotion_ok": annonces.SCOPE_MARKETING in ((jetons or {}).get("scopes") or []), "psa_ok": __import__("psa").actif()}

    def _prix_similaires(self, titre, joueur=None, ventes=None):
        """10 nov 2026 : la valeur d'une carte SANS ventes, a partir des ventes des cartes proches (jamais des annonces) :
        nos archives du joueur (un an), le bassin des deals s'il est deja en memoire, puis UNE recherche large (joueur +
        produit) si rien. Memes regles prudentes que les deals (saisons voisines -20 %, similaires -25 %, inscription :
        la carte sans inscription comme plancher). -> (valeur, source, n, ventes) ou None."""
        import cartes_match
        import deals as _d
        cib = cartes_match.cible_titre(titre, joueur)
        if cib.get("exclu") or not cib.get("joueur"):
            return None
        a = {"titre": titre}
        pool = list(ventes or []) + vendues.archives_joueur(cib["joueur"])
        b = _d._BASSIN.get("b")                  # jamais rebati ici (250 000 ventes : trop long pour un geste)
        if b is not None:
            try:
                pool += b.candidats(_d.cible_large(dict(cib, annee=None)))
            except Exception:
                pass

        def essai(p):
            return _d.valeur_autre_saison(a, p, cib) or _d.valeur_approx(a, p, cib)
        va = essai(pool)
        if not va:
            q = cartes_match.requete_ebay(_d.cible_large(dict(cib, inscr=False) if cib.get("inscr") else cib))
            if q:
                r = vendues.rechercher(q, fond=False)
                if r.get("ventes"):
                    va = essai(pool + list(r["ventes"]))
        if not va or not va[0] or not va[3]:
            return None
        return va

    def annonce_publier(self, d, verifier=False):
        """La carte + l'annonce : photos chez eBay, verification (frais), puis creation sur un 2e tap.
        La carte entre dans l'inventaire (Listée) ; promotion % ensuite si choisie."""
        import annonces
        import forfaits
        d = dict(d or {})
        try:
            forfaits.verifier("annonces_mois")
        except forfaits.LimiteAtteinte as e:
            return {"ok": False, "erreur": str(e), "pro_requis": True}
        st = ebay_compte.statut()
        if not st.get("connecte"):
            return {"ok": False, "erreur": "Compte eBay non connecté"}
        if not st.get("ecriture"):
            return {"ok": False, "erreur": "Reconnecte eBay pour mettre en vente et changer tes prix depuis l'app."}
        prix = _float(d.get("prix"))
        if not prix or prix < 0.99:
            return {"ok": False, "erreur": "Indique un prix"}
        titre = re.sub(r"\s+", " ", str(d.get("titre") or "")).strip()[:80]
        if len(titre) < 10:
            return {"ok": False, "erreur": "Ajoute un titre"}
        carte = {k: v for k, v in (d.get("carte") or {}).items() if k in self.CHAMPS_CARTE}
        carte["sport"] = carte.get("sport") or self.sport_de(carte)
        r_ = self.reglages_lire()
        exp = r_.get("expedition_ebay") if isinstance(r_.get("expedition_ebay"), dict) else {}
        cp = exp.get("code_postal") or "H2X 1Y4"
        try:
            photos = annonces.photos_ebay(d.get("photos") or [])
        except (RuntimeError, ValueError, OSError) as e:
            return {"ok": False, "erreur": str(e)}
        if not photos:
            return {"ok": False, "erreur": "Ajoute une photo de la carte"}
        sku = d.get("sku") or ("LR-" + secrets.token_hex(4))
        opts = {**annonces.MODELE_DEFAUT, **{k: d[k] for k in annonces.MODELE_DEFAUT if k in d}}
        try:                                          # 29 oct 2026 : publication programmee (ScheduleTime d'eBay)
            debut_utc = annonces.debut_programme(d.get("debut"))
        except ValueError as e:
            return {"ok": False, "erreur": str(e)}
        donnees = {**opts, "carte": carte, "titre": titre, "prix": prix, "description": annonces.texte_html(d.get("description")) or titre, "sku": sku,
                   "debut_utc": debut_utc}
        r = self._ecrire_ebay("annonces.publier", donnees, photos, cp, verifier_seulement=bool(verifier))
        r["photos"] = photos                          # deja chez eBay : renvoyees au 2e tap (pas televersees deux fois)
        r["sku"] = sku
        if not r.get("ok") or verifier:
            return r
        if r.get("item_id"):
            forfaits.compter("annonces_mois")
            champs = {**carte, "titre": titre, "prix_demande": prix, "statut": "Listée", "item_number": r["item_id"], "sku": sku,
                      "photo": photos[0], "cout": _float(d.get("cout"))}
            if d.get("cid"):
                champs["id"] = d["cid"]
            rs_ = self.carte_sauver({k: v for k, v in champs.items() if v not in (None, "")})
            r["achat_lie"] = self._lier_achat_choisi(rs_.get("id"), d.get("achat"))
            with _verrou:
                c = self._db()
                try:
                    c.execute("UPDATE cartes SET debut=? WHERE item_number=?", (debut_utc or _maintenant(), r["item_id"]))
                    c.commit()
                finally:
                    c.close()
            pct = _float(d.get("promotion")) or 0
            r["debut"] = debut_utc
            if pct > 0 and debut_utc:
                # 29 oct 2026 : une annonce programmee n'est pas encore active : la promotion s'ajoute toute seule quand
                # elle passe en ligne (boucle de l'heure)
                self._promo_attente(r["item_id"], pct, debut_utc)
                r["promotion"] = pct
                r["promotion_attente"] = True
            elif pct > 0:
                p = self._ecrire_ebay("annonces.promouvoir", r["item_id"], pct)
                r["promotion"] = p.get("promotion") if p.get("ok") else None
                if not p.get("ok"):
                    r.setdefault("avertissements", []).append(p.get("erreur"))
                elif p.get("avertissement"):
                    r.setdefault("avertissements", []).append(p["avertissement"])
            if d.get("memoriser", True):
                self.reglages_sauver({"modele_annonce": {k: opts[k] for k in annonces.MODELE_DEFAUT}})
        return r

    # -- 29 oct 2026 (Mathieu : « le bon shipping policy, 250 g 16 x 23 x 3 cm, promo 2 %, offres, description… et les
    # ceduler sur une vingtaine de jours, une apres l'autre, pour ne pas toutes les mettre en meme temps ») --
    def ebay_politiques(self, force=False):
        """Les politiques d'expedition / retours / paiement du vendeur chez eBay (Business Policies)."""
        import annonces
        if not ebay_compte.statut().get("connecte"):
            return {"ok": False, "erreur": "Compte eBay non connecté"}
        try:
            return annonces.politiques(bool(force))
        except (RuntimeError, OSError) as e:
            return {"ok": False, "erreur": str(e)}

    def _serie_chemin(self):
        import comptes
        return os.path.join(comptes.dossier() or DOSSIER, "serie_annonces.json")

    def serie_candidates(self):
        """Les cartes pretes a publier : en stock (pas sur eBay, pas vendues), avec un titre, un prix et une photo."""
        out = []
        for c in self.inventaire_liste({}) or []:
            if c.get("statut") in ("Vendue", "Listée") or c.get("item_number"):
                continue
            try:
                ph = json.loads(c.get("photos") or "[]") or ([c["photo"]] if c.get("photo") else [])
            except ValueError:
                ph = [c["photo"]] if c.get("photo") else []
            prix = c.get("prix_demande") or (sante.prix_rond(c["valeur"]) if c.get("valeur") else None)
            out.append({"id": c["id"], "titre": c.get("titre") or ebay_csv.titre_annonce(c), "prix": prix, "photo": c.get("photo"),
                        "nb_photos": len(ph), "emplacement": c.get("emplacement"),
                        "manque": [m for m, ok in (("prix", bool(prix)), ("photo", bool(ph)), ("titre", len(str(c.get("titre") or "")) >= 10)) if not ok]})
        return {"ok": True, "cartes": out, "modele": __import__("annonces").modele(self.reglages_lire().get("modele_annonce"))}

    def serie_programmer(self, ids, debut, ecart_h=24, modele=None, debuts=None):
        """Programme les cartes choisies sur eBay, une apres l'autre : la 1re a « debut », puis une toutes les ecart_h
        heures. Chaque annonce : titre, prix, photos, description, details, politiques eBay, colis, offres, promotion
        (le modele d'annonce). Tout se fait en arriere-plan ; serie_etat() suit l'avancement."""
        import annonces
        import comptes
        import threading
        from datetime import datetime as _dt, timedelta as _td, timezone as _tz
        st = ebay_compte.statut()
        if not st.get("connecte") or not st.get("ecriture"):
            return {"ok": False, "erreur": "Reconnecte eBay pour publier depuis l'app."}
        e = self.serie_etat()
        if e.get("en_cours"):
            return {"ok": False, "erreur": "Une série est déjà en cours"}
        ids = [int(i) for i in (ids or [])][:200]
        if not ids:
            return {"ok": False, "erreur": "Choisis au moins une carte"}
        try:
            ecart = max(0.25, float(ecart_h or 24))
            t0 = _dt.fromisoformat(str(debut).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return {"ok": False, "erreur": "Date de départ invalide"}
        if t0.tzinfo is None:
            t0 = t0.replace(tzinfo=_tz.utc)
        heures = [t0 + _td(hours=ecart * i) for i in range(len(ids))]
        # 5 nov 2026 (Mathieu : « une journee entre chaque carte et, au bout du maximum d'eBay, on recommence au debut ») :
        # le calendrier « etale » est calcule dans l'app (une carte par jour sur les 21 jours, puis un 2e tour plus tot
        # dans la journee...) ; ici on verifie chaque heure
        if debuts:
            try:
                hs = [_dt.fromisoformat(str(x).replace("Z", "+00:00")) for x in list(debuts)[:len(ids)]]
            except (TypeError, ValueError):
                return {"ok": False, "erreur": "Calendrier invalide"}
            if len(hs) != len(ids):
                return {"ok": False, "erreur": "Calendrier incomplet"}
            heures = [h if h.tzinfo else h.replace(tzinfo=_tz.utc) for h in hs]
            try:
                for h in heures:
                    annonces.debut_programme(h.isoformat())
            except ValueError as x:
                return {"ok": False, "erreur": str(x)}
        try:
            annonces.debut_programme(min(heures).isoformat())
            annonces.debut_programme(max(heures).isoformat())
        except ValueError as x:
            n_ok = int((_dt.now(_tz.utc) + _td(days=annonces.PROGRAMME_MAX_J) - t0).total_seconds() // (ecart * 3600)) + 1
            return {"ok": False, "erreur": str(x) + (f" : à ce rythme, {max(0, n_ok)} cartes au plus dans cette série" if n_ok < len(ids) else "")}
        r_ = self.reglages_lire()
        mod = annonces.modele(r_.get("modele_annonce"), modele)
        if modele:
            self.reglages_sauver({"modele_annonce": {k: mod[k] for k in annonces.MODELE_DEFAUT}})
        plan = [{"id": i, "debut": h.astimezone(_tz.utc).isoformat()} for i, h in zip(ids, heures)]
        etat = {"en_cours": True, "total": len(plan), "faites": 0, "erreurs": [], "plan": plan, "lance_le": _maintenant()}
        self._serie_ecrire(etat)
        compte = comptes.courant()

        def tache():
            with comptes.utiliser(compte):
                franco = (r_.get("langue") or "fr") != "en"
                for p in plan:
                    c = self.carte_lire(p["id"])
                    err = None
                    if not c:
                        err = "carte introuvable"
                    elif c.get("statut") in ("Vendue", "Listée"):
                        err = "déjà sur eBay ou vendue"
                    else:
                        try:
                            ph = json.loads(c.get("photos") or "[]") or ([c["photo"]] if c.get("photo") else [])
                        except ValueError:
                            ph = [c["photo"]] if c.get("photo") else []
                        titre = (c.get("titre") or ebay_csv.titre_annonce(c) or "")[:80]
                        prix = c.get("prix_demande") or (sante.prix_rond(c["valeur"]) if c.get("valeur") else None)
                        desc = annonces.description(c, titre, franco, mod["etat"], r_.get("nom_boutique"), mod["retours"], mod["expedition"])
                        d = {**mod, "carte": {k: v for k, v in c.items() if k in self.CHAMPS_CARTE}, "titre": titre, "prix": prix,
                             "description": desc, "photos": ph, "cid": c["id"], "cout": c.get("cout"), "sku": c.get("sku"),
                             "debut": p["debut"], "memoriser": False}
                        try:
                            r = self.annonce_publier(d)
                            if not r.get("ok"):
                                err = r.get("erreur") or "eBay"
                            else:
                                p["item_id"] = r.get("item_id")
                        except Exception as x:
                            err = f"{type(x).__name__} : {x}"
                    etat["faites"] += 1
                    if err:
                        etat["erreurs"].append({"id": p["id"], "titre": (c or {}).get("titre"), "erreur": str(err)[:200]})
                    self._serie_ecrire(etat)
                etat["en_cours"] = False
                etat["fini_le"] = _maintenant()
                self._serie_ecrire(etat)
        threading.Thread(target=tache, daemon=True, name="serie-annonces").start()
        return {"ok": True, **etat}

    def annonce_reviser(self, cid, d):
        """Modifier une annonce deja chez eBay (programmee ou en ligne) : titre, prix, heure de mise en ligne."""
        import annonces
        c = self.carte_lire(cid)
        if not c or not c.get("item_number"):
            return {"ok": False, "erreur": "Cette carte n'a pas d'annonce eBay"}
        d = d or {}
        titre = re.sub(r"\s+", " ", str(d.get("titre") or "")).strip()[:80] or None
        prix = _float(d.get("prix"))
        try:
            debut_utc = annonces.debut_programme(d.get("debut")) if d.get("debut") else None
        except ValueError as e:
            return {"ok": False, "erreur": str(e)}
        if titre is not None and len(titre) < 10:
            return {"ok": False, "erreur": "Ajoute un titre"}
        r = self._ecrire_ebay("annonces.reviser", c["item_number"], titre, prix, debut_utc)
        if r.get("ok"):
            ch = {"id": cid}
            if titre:
                ch["titre"] = titre
            if prix:
                ch["prix_demande"] = prix
            if len(ch) > 1:
                self.carte_sauver(ch)
            if debut_utc:
                cx = self._db()
                try:
                    cx.execute("UPDATE cartes SET debut=? WHERE id=?", (debut_utc, cid))
                    cx.commit()
                finally:
                    cx.close()
        return r

    def serie_etat(self):
        try:
            with open(self._serie_chemin(), encoding="utf-8") as f:
                e = json.load(f)
        except (OSError, ValueError):
            return {"ok": True, "en_cours": False}
        if e.get("en_cours") and str(e.get("lance_le") or "") < (datetime.now() - timedelta(hours=3)).isoformat():
            e["en_cours"] = False                      # redemarrage du serveur pendant une serie
        return {"ok": True, **e}

    def _serie_ecrire(self, e):
        p = self._serie_chemin()
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            json.dump(e, f, ensure_ascii=False)
        os.replace(p + ".tmp", p)

    # -- 31 oct 2026 (Mathieu : « la promotion de 2 % pour eBay n'a pas fonctionne pour Mercer ») --------------------
    def annonce_promotion(self, cid, pct=None):
        """La promotion eBay d'une carte en vente : son etat chez eBay (pct=None), ou la promouvoir au % choisi."""
        import annonces
        c = self._db()
        try:
            r = c.execute("SELECT item_number, debut FROM cartes WHERE id=?", (int(cid),)).fetchone()
        finally:
            c.close()
        if not r or not r[0]:
            return {"ok": False, "erreur": "Cette carte n'est pas en vente sur eBay"}
        item_id = str(r[0])
        if not ebay_compte.statut().get("connecte"):
            return {"ok": False, "erreur": "Compte eBay non connecté"}
        attente = None
        c = self._db()
        try:
            c.execute(self._PROMOS)
            a = c.execute("SELECT pct, debut, essais FROM promos_attente WHERE item_id=?", (item_id,)).fetchone()
            attente = {"pct": a[0], "debut": a[1], "essais": a[2]} if a else None
        finally:
            c.close()
        if pct is not None:
            pct = _float(pct) or 0
            if r[1] and str(r[1]) > datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"):
                self._promo_attente(item_id, pct, r[1])                   # pas encore en ligne : au moment de la mise en ligne
                return {"ok": True, "item_id": item_id, "attente": {"pct": pct, "debut": r[1], "essais": 0}, "promue": False}
            p = self._ecrire_ebay("annonces.promouvoir", item_id, pct)
            if not p.get("ok"):
                return {"ok": False, "erreur": p.get("erreur") or "Promotion refusée par eBay"}
            c = self._db()
            try:
                c.execute(self._PROMOS)
                c.execute("DELETE FROM promos_attente WHERE item_id=?", (item_id,))
                c.commit()
            finally:
                c.close()
            attente = None
        s_ = self._ecrire_ebay("annonces.promo_statut", item_id)
        if not s_.get("ok"):
            return {"ok": False, "erreur": s_.get("erreur") or "eBay injoignable"}
        s_["attente"] = attente
        if pct is not None and p.get("avertissement"):
            s_["avertissement"] = p["avertissement"]
        return s_

    _PROMOS = "CREATE TABLE IF NOT EXISTS promos_attente (item_id TEXT PRIMARY KEY, pct REAL, debut TEXT, essais INTEGER DEFAULT 0)"

    def _promo_attente(self, item_id, pct, debut):
        c = self._db()
        try:
            c.execute(self._PROMOS)
            c.execute("INSERT OR REPLACE INTO promos_attente (item_id, pct, debut, essais) VALUES (?,?,?,0)", (str(item_id), pct, debut))
            c.commit()
        finally:
            c.close()

    def promos_attente_appliquer(self):
        """Boucle de l'heure : la promotion des annonces programmees qui sont maintenant en ligne (6 essais au plus)."""
        maint = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        c = self._db()
        try:
            c.execute(self._PROMOS)
            lst = [dict(x) for x in c.execute("SELECT * FROM promos_attente WHERE debut <= ?", (maint,))]
        finally:
            c.close()
        faits = 0
        for x in lst:
            p = self._ecrire_ebay("annonces.promouvoir", x["item_id"], x["pct"])
            c = self._db()
            try:
                if p.get("ok") or x["essais"] >= 5:
                    c.execute("DELETE FROM promos_attente WHERE item_id=?", (x["item_id"],))
                    faits += 1 if p.get("ok") else 0
                    if not p.get("ok"):
                        print("Promotion programmee abandonnee :", x["item_id"], p.get("erreur"), flush=True)
                else:
                    c.execute("UPDATE promos_attente SET essais=essais+1 WHERE item_id=?", (x["item_id"],))
                c.commit()
            finally:
                c.close()
        return faits

    def ebay_changer_prix(self, item_number, prix):
        r = self._ecrire_ebay("changer_prix", item_number, prix)
        if r.get("ok"):
            with _verrou:
                c = self._db()
                try:
                    c.execute("UPDATE cartes SET prix_demande=? WHERE item_number=?", (r["prix"], str(item_number)))
                    c.execute("UPDATE sante SET fait=1 WHERE item_number=?", (str(item_number),))
                    c.commit()
                finally:
                    c.close()
        return r

    def ebay_prix_lot(self, items):
        """29 oct 2026 (Mathieu : « un moyen rapide de corriger le prix des annonces sur eBay, tres rapide et efficace ») :
        plusieurs prix changes d'un geste (l'ecran « Corriger mes prix »), 4 a la fois. Seul le prix change ; une annonce
        programmee (pas encore en ligne) passe par la revision. -> {ok, faits, resultats:[{item_number, ok, prix, erreur}]}"""
        import contextvars
        from concurrent.futures import ThreadPoolExecutor
        lst = []
        for x in (items or [])[:60]:
            if not isinstance(x, dict):
                continue
            iid, p = str(x.get("item_number") or "").strip(), _float(x.get("prix"))
            if iid and p:
                lst.append((iid, round(p, 2), x.get("id") if x.get("programmee") else None))
        if not lst:
            return {"ok": False, "erreur": "Aucun prix à changer", "faits": 0, "resultats": []}

        def un(t):
            iid, p, cid = t
            try:
                r = self.annonce_reviser(cid, {"prix": p}) if cid else self.ebay_changer_prix(iid, p)
            except Exception as e:                       # jamais une erreur muette
                r = {"ok": False, "erreur": f"{type(e).__name__} : {e}"}
            return {"item_number": iid, "ok": bool(r.get("ok")), "prix": p, "erreur": None if r.get("ok") else str(r.get("erreur") or "eBay")[:160]}
        with ThreadPoolExecutor(max_workers=4) as ex:     # chaque appel garde le compte de l'utilisateur (contexte copie)
            taches = [(contextvars.copy_context(), t) for t in lst]          # copie faite ICI (fil de la requete)
            res = list(ex.map(lambda j: j[0].run(un, j[1]), taches))
        return {"ok": True, "faits": sum(1 for r in res if r["ok"]), "resultats": res}

    def ebay_miser(self, item_id, montant):
        """Mise MAXIMUM sur une enchere. Un tap = une mise ; jamais programmee ni automatique."""
        return self._ecrire_ebay("miser", item_id, montant)

    def ebay_appels(self):
        """Appels eBay du jour (toute l'application) face aux limites, et efficacite du cache."""
        import appels_ebay
        return appels_ebay.resume()

    def ebay_avis_statut(self):
        import ebay_avis
        return ebay_avis.statut()

    def ebay_avis_regler(self, adresse):
        import ebay_avis
        a = str(adresse or "").strip()
        if a and not a.startswith("https://"):
            return {"ok": False, "erreur": "L'adresse doit commencer par https:// (eBay l'exige)"}
        ebay_avis.reglage(a)
        return {"ok": True, **ebay_avis.statut()}

    def ebay_avis_jeton(self):
        """Pour le coller dans developer.ebay.com (bouton Copier) : jamais affiche en clair."""
        import ebay_avis
        return {"ok": True, "jeton": ebay_avis.reglage()["jeton"]}

    def ebay_donnees_test(self, n=20):
        """Lance la creation en arriere-plan (une seule a la fois) ; suivre avec ebay_donnees_test_etat."""
        # 3 nov 2026 (revue de securite) : l'etat de la tache est celui du COMPTE (pas de l'objet partage par tous), et la
        # tache garde le compte (contexte copie)
        import contextvars
        etats = self.__dict__.setdefault("_test_etats", {})
        k = comptes.courant() or "local"
        e = etats.get(k)
        if e and e.get("actif"):
            return {"ok": True, "deja": True, **e}
        etats[k] = e = {"actif": True, "faits": 0, "total": int(n or 20), "creees": 0, "erreurs": []}
        ctx = contextvars.copy_context()

        def tache():
            ctx.run(_tache)

        def _tache():
            try:
                def prog(i, total):
                    e.update(faits=i, total=total)
                r = self._ecrire_ebay("donnees_test", int(n or 20), progression=prog)
                e.update(creees=r.get("creees") or 0, erreurs=r.get("erreurs") or ([r["erreur"]] if r.get("erreur") else []),
                         faits=e["total"])
                if r.get("creees"):
                    s = self.ebay_synchroniser(30)
                    e["synchro"] = {k: s.get(k) for k in ("annonces", "ventes")}
            finally:
                e["actif"] = False
        threading.Thread(target=tache, daemon=True, name="annonces_test").start()
        return {"ok": True, **e}

    def ebay_livraison_us_tests(self):
        """Sandbox : ajoute la livraison vers les E.-U. aux annonces de test deja en ligne."""
        return self._ecrire_ebay("livraison_us_tests")

    def ebay_donnees_test_etat(self):
        return dict((self.__dict__.get("_test_etats") or {}).get(comptes.courant() or "local") or {"actif": False})

    def ebay_synchroniser(self, jours=90):
        """Annonces actives + ventes des `jours` derniers jours, avec les frais reels."""
        try:
            annonces = ebay_compte.annonces_actives()
            ventes = [v for v in ebay_compte.commandes(int(jours or 90)) if not v.get("annulee")]
        except (RuntimeError, OSError, ValueError) as e:
            return {"ok": False, "erreur": str(e)}
        # 22 oct 2026 - 2e source (API Trading) : une vente que la nouvelle API n'a pas encore transmise
        # arrive quand meme ; les doublons entre les deux sources sont ecartes dans _maj_ventes.
        trading_ok = True
        try:
            ventes += [v for v in ebay_compte.ventes_trading(min(30, int(jours or 30))) if not v.get("annulee")]
        except (RuntimeError, OSError, ValueError) as e:
            trading_ok = False
            print(f"[synchro] ventes Trading ignorees : {e}", flush=True)
        a = self._maj_annonces(annonces)
        try:                                     # 31 oct 2026 - les vues de chaque annonce (30 j), si le compte a donne l'acces
            self._maj_trafic([x["item_number"] for x in annonces if x.get("item_number")])
        except Exception as e:
            print(f"[synchro] vues des annonces : {e}", flush=True)
        v = self._maj_ventes(ventes)
        try:
            a["terminees"] = self._annonces_terminees(a.get("vu"), len(annonces)) if trading_ok else 0
        except Exception as e:
            print(f"[synchro] annonces terminees : {e}", flush=True)
        try:                                     # 25 oct 2026 - le cout d'achat : les achats eBay du compte
            cx = self.couts_depuis_achats()
        except Exception as e:
            cx = {"relies": 0}
            print(f"[synchro] couts depuis les achats eBay : {e}", flush=True)
        try:                                     # 24 oct 2026 - « mettre des images sur les sold aussi »
            self._photos_vendues(25)
        except Exception as e:
            print(f"[synchro] photos des ventes : {e}", flush=True)
        bilan = {"annonces": a.get("lues"), "nouvelles_annonces": a.get("crees"), "ventes": v.get("nouvelles"),
                 "deja": v.get("deja"), "couts_relies": cx.get("relies"), "le": _maintenant()}
        ebay_compte.noter_synchro(bilan)
        return {"ok": True, **bilan}

    def guide_donnees(self):
        """25 oct 2026 - pour le guide du hobby : les joueurs les plus recherches (indice de demande SlabCoach)
        et les recrues de la saison (le produit le plus recent du catalogue, ses Young Guns les plus chers)."""
        d = valeurs._charger() or {}
        top = sorted((d.get("joueurs") or {}).items(), key=lambda kv: -float(kv[1] or 0))[:12]
        prods = sorted(catalogue.liste(), key=lambda p: str(p.get("saison") or "") + str(p.get("sortie") or ""), reverse=True)
        recrues, nom_prod = [], None
        for p in prods[:3]:
            try:
                prod = catalogue.charger(p["id"])
            except Exception:
                continue
            se = {x["nom"]: x for x in prod.get("sous_ensembles") or []}
            yg = [c for c in prod.get("cartes") or [] if (se.get(c.get("sous_ensemble")) or {}).get("groupe") == "recrue"
                  and not (se.get(c.get("sous_ensemble")) or {}).get("parallele_de") and c.get("joueur")]
            if not yg:
                continue
            taux = prod.get("_taux") or {}
            cache, vals = {}, {}
            for c in yg:
                v, _m = valeurs.valeur_carte(prod, c["sous_ensemble"], c["joueur"], se, taux, cache)
                if v > vals.get(c["joueur"], (0, ""))[0]:
                    vals[c["joueur"]] = (round(v, 2), c.get("equipe") or "", c["sous_ensemble"], _m)
            recrues = [{"joueur": j, "valeur": v[0], "equipe": v[1], "carte": v[2], "mesuree": v[3]}
                       for j, v in sorted(vals.items(), key=lambda kv: (-kv[1][0], -valeurs.demande(kv[0])))[:10]]
            nom_prod = prod["nom"]
            break
        return {"ok": True, "joueurs": [{"joueur": j, "demande": round(float(v), 2)} for j, v in top], "recrues": recrues, "produit": nom_prod}

    # -- 26 oct 2026 : fiche joueur, alertes, tendances, collection, calendrier (marche.py) ---------------------------
    def joueur_fiche(self, nom):
        r = marche.fiche_joueur(self, nom)
        if isinstance(r, dict) and r.get("ok") and not comps_permis(self):
            # 10 nov 2026 (comps = admin seulement) : le joueur, ses cartes (tirage, groupe), sa recrue, ses alertes ; sans
            # valeur ni vente ni tendance de prix, ni deal
            for c_ in r.get("cartes") or []:
                c_.pop("valeur", None)
                c_.pop("mesuree", None)
            r.update(ventes=[], points=[], mediane=None, nb_ventes=0, tendance=None, deals=[], demande=None, coupe=True)
            return r
        try:                                            # 5 nov 2026 : son indice de ventes repetees (indices.py)
            import indices
            i = indices.joueur((r or {}).get("joueur") or nom) if isinstance(r, dict) and r.get("ok") else None
            if i:
                r["indice_rs"] = {**{k: i[k] for k in ("v4", "v13", "v52", "n_paires", "n_cartes", "fin", "confiance")}, "points": i["points"][-53:]}
        except Exception as e:
            print("Indice joueur : " + repr(e), flush=True)
        return r

    def alerte_ajouter(self, q, prix_max):
        return marche.alerte_ajouter(self, q, prix_max)

    def alertes_liste(self):
        return marche.alertes_liste(self)

    def alerte_supprimer(self, aid):
        return marche.alerte_supprimer(self, aid)

    def notifications_lues(self):
        return marche.notifications_lues(self)

    def alertes_verifier(self):
        import alarmes
        if not alarmes.reglages(self)["prix_cible"]:          # 29 oct 2026 : decochee dans « Mes alertes »
            return {"ok": True, "alertes": 0, "nouvelles": 0, "coupee": True}
        return marche.verifier_alertes(self)

    # 29 oct 2026 (Mathieu : « l'utilisateur doit pouvoir regler ses alarmes de maniere simple » ; « il peut les cocher »)
    def alarmes_lire(self):
        import alarmes
        return {"ok": True, "alarmes": alarmes.reglages(self)}

    def alarmes_regler(self, d=None):
        import alarmes
        return {"ok": True, "alarmes": alarmes.regler(self, d or {})}

    def alarmes_mes_joueurs(self):
        import alarmes
        return {"ok": True, "envoyees": alarmes.mes_joueurs(self)}

    def alarmes_verifier(self):
        import alarmes
        r = {"ok": True, "envoyees": alarmes.verifier(self)}
        try:                                    # 29 oct 2026 : la watchlist (le reste de l'heure ; les fins d'encans : boucle de 5 min)
            import watchlist
            r["watchlist"] = watchlist.verifier(self)
        except Exception as e:
            print("Watchlist : " + repr(e), flush=True)
        try:                                    # 29 oct 2026 : la promotion des annonces programmees passees en ligne
            r["promos"] = self.promos_attente_appliquer()
        except Exception as e:
            print("Promos programmees : " + repr(e), flush=True)
        try:                                    # 29 oct 2026 : l'alerte de valeur des cartes de la collection (chaque semaine par carte)
            import suivi_valeur
            r["valeur"] = suivi_valeur.verifier(self)
        except Exception as e:
            print("Suivi valeur : " + repr(e), flush=True)
        try:                                    # 3 nov 2026 : la variation du prix de chaque carte (une fois par jour, sans credit)
            import tendance_cartes
            r["tendances"] = tendance_cartes.maj(self)
        except Exception as e:
            print("Tendance des cartes : " + repr(e), flush=True)
        return r

    # -- 29 oct 2026 (Mathieu : « une alarme quand la carte de ma collection prend ou perd de la valeur ») --
    def valeur_suivi(self, cid, actif=None):
        import suivi_valeur
        if actif is None:
            return suivi_valeur.etat(self, cid)
        r = suivi_valeur.regler(self, cid, bool(actif))
        if actif and r.get("ok") and not r.get("reference"):
            import threading                          # pas encore de valeur : la premiere, tout de suite, en arriere-plan
            import contextvars
            ctx_ = contextvars.copy_context()                    # 3 nov 2026 (revue) : le fil garde le compte
            threading.Thread(target=lambda: ctx_.run(self._suivi_premier, cid), daemon=True).start()
        return r

    def carte_valeur(self, cid):
        """31 oct 2026 (Mathieu : « pourquoi on voit pas la valeur de ma carte (mediane des last sold) ») : la valeur d'une
        carte de la collection = ses ventes reelles (la meme carte : meme parallele, meme numerotation). Valeur sure (2 ventes
        et plus qui se tiennent) sinon la mediane de ce qu'on a, en disant combien de ventes. Gardee si la carte n'en avait pas."""
        import suivi_valeur
        carte = self.carte_lire(cid)
        if not carte:
            return {"ok": False, "erreur": "Carte introuvable"}
        t = suivi_valeur._titre(carte)
        if len(t) < 6:
            return {"ok": True, "valeur": None, "n": 0}
        try:
            r = vendues.memes_annonce(t, n=24)
        except Exception as e:
            return {"ok": False, "erreur": str(e)}
        vs = self._ventes_inventaire([v for v in (r.get("ventes") or []) if v.get("prix")], carte)
        if not vs:                      # rien de neuf (ou recherche indisponible) : la derniere valeur connue reste, dite comme telle
            return {"ok": True, "valeur": carte.get("valeur"), "n": 0, "gardee": carte.get("valeur") is not None, "erreur": r.get("erreur"),
                    **self._repere_annonces(carte, t)}
        sure, _pv = deals.valeur_sure(vs, t)
        val = sure if sure else round(statistics.median(float(v["prix"]) for v in vs), 2)
        # 5 nov 2026 (comme la CL Value) : des ventes qui datent -> la valeur suit l'indice du joueur depuis (indices.py)
        val, ajust = self._valeur_vieillie(val, _pv if sure and isinstance(_pv, list) else vs, carte)
        # 9 nov 2026 (revue « aucun faux indice ») : une valeur tiree d'une ou deux ventes qui ne se tiennent pas n'est pas
        # gardee (elle donnerait un faux « trop cher » dans l'inventaire) ; seulement une valeur sure ou 3 ventes et plus
        if sure or (carte.get("valeur") is None and len(vs) >= 3):
            self.carte_sauver({"id": cid, "valeur": val})
        recentes = sorted(vs, key=lambda v: str(v.get("le") or ""), reverse=True)
        approx = self._repere_annonces(carte, t) if not (sure or len(vs) >= 3) else {}
        return {"ok": True, "valeur": val, "n": len(vs), "sure": bool(sure), "derniere": (recentes[0].get("le") or "")[:10] or None,
                "ajustee": ajust, **approx}

    def _repere_annonces(self, carte, titre=None, res=None):
        # 10 nov 2026 (Mathieu : « legaux a 100 % ») : licence de l'API eBay §9.5 : les annonces lues par l'API ne servent
        # plus a calculer un prix. Coupe par defaut ; LR_PRIX_ANNONCES=1 seulement avec l'accord ecrit d'eBay.
        if not prix_annonces_permis():
            return {}
        return self._repere_annonces0(carte, titre, res)

    def _repere_annonces0(self, carte, titre=None, res=None):
        """9 nov 2026 (Mathieu : « pourquoi on ne voit toujours pas si la carte est dans le bon range de prix ? ») : sans ventes
        reelles sures, le repere = la mediane des MEMES cartes en vente sur eBay moins 10 % (comme le prix suggere : les annonces
        demandent souvent trop), 3 annonces et plus. Garde sur la carte (dit comme tel dans l'app : « annonces »)."""
        import cartes_match
        import suivi_valeur
        t = titre or suivi_valeur._titre(carte)
        try:
            if res is None:
                if not cartes_match.est_carte(t):
                    return {}
                cib = cartes_match.cible_titre(t, carte.get("joueur"))
                res = ebay_compte.rechercher(cartes_match.requete_ebay(cib) or t, categorie=CATEGORIE_CARTES, limite=100, fond=False)
                _c, res, _e = cartes_match.filtrer_carte(t, res, carte.get("joueur"), exclure_id=carte.get("item_number"))
            tot = [round((x.get("prix_cad") or 0) + (x.get("port_cad") or 0), 2) for x in res if x.get("prix_cad")]
            med, garde = cartes_match.mediane_robuste(tot)
        except Exception as e:
            print("Repere annonces : " + repr(e), flush=True)
            return {}
        if not med or len(garde) < 3:
            return {}
        v = round(med * (1 - RABAIS_ANNONCES), 2)
        if carte.get("id"):
            c = self._db()
            try:
                c.execute("UPDATE cartes SET valeur_annonces=?, valeur_annonces_n=?, valeur_annonces_le=? WHERE id=?",
                          (v, len(garde), datetime.now().strftime("%Y-%m-%d"), carte["id"]))
                c.commit()
            finally:
                c.close()
        return {"approx": v, "n_annonces": len(garde)}

    JOURS_INVENTAIRE = 90

    def _ventes_inventaire(self, vs, carte=None, jours=None):
        """6 nov 2026 (Mathieu : « pour eviter de prendre mes achats en consideration et etre pres du marche actuel, prendre
        seulement les ventes des 3 derniers mois pour l'ajustement du prix des cartes dans l'inventaire ») : les ventes qui
        servent a la valeur d'une carte de l'inventaire : 90 jours au plus (meme un hit), et jamais un de tes achats eBay
        (son numero d'annonce ; pour la carte elle-meme, aussi la vente au prix paye, a 2 jours de son achat)."""
        jours = jours or self.JOURS_INVENTAIRE
        ids, propres = set(), []
        try:
            c = self._db()
            try:
                c.execute(self._SQL_ACHATS)
                for iid, cout, date, cid in c.execute("SELECT item_id, cout, date, carte_id FROM achats_ebay"):
                    if iid:
                        ids.add(str(iid))
                    if carte and cid is not None and cid == carte.get("id") and cout and date:
                        propres.append((str(date)[:10], float(cout)))
            finally:
                c.close()
        except Exception as e:
            print("Ventes inventaire (achats) : " + repr(e), flush=True)

        def mon_achat(v):
            iv = str(v.get("item_id") or "") or vendues._id_vente(v) or ""
            if iv and iv in ids:
                return True
            try:
                p, d = float(v.get("prix")), datetime.fromisoformat(str(v.get("le"))[:10])
            except (TypeError, ValueError):
                return False
            for da, cout in propres:
                try:
                    if abs((d - datetime.fromisoformat(da)).days) <= 2 and abs(p - cout) <= max(1.0, 0.05 * cout):
                        return True
                except ValueError:
                    pass
            return False
        return [v for v in vs or [] if deals._jours(v) <= jours and not mon_achat(v)]

    @staticmethod
    def _valeur_vieillie(val, ventes, carte):
        """La valeur des ventes, ajustee par l'indice du joueur si ces ventes datent (mediane des dates > 14 jours)."""
        try:
            import indices
            ds = sorted(str(v.get("le") or "")[:10] for v in ventes or [] if v.get("le"))
            if not ds or not val:
                return val, None
            return indices.ajuster(val, ds[len(ds) // 2], (carte or {}).get("joueur"), (carte or {}).get("sport"))
        except Exception as e:
            print("Valeur vieillie : " + repr(e), flush=True)
            return val, None

    def _suivi_premier(self, cid):
        import suivi_valeur
        try:
            carte = self.carte_lire(cid)
            v = suivi_valeur.valeur_actuelle(carte, api=self) if carte else None
            if v:
                suivi_valeur._maj(self, cid, reference=v, derniere=v, verifie_le=datetime.now().isoformat(timespec="seconds"))
                c = self._db()
                try:
                    c.execute("UPDATE cartes SET valeur=? WHERE id=? AND valeur IS NULL", (v, cid))
                    c.commit()
                finally:
                    c.close()
        except Exception as e:
            print("Suivi valeur (1re) : " + repr(e), flush=True)

    # -- 29 oct 2026 (Mathieu : « une etoile pour l'enregistrer dans une watchlist ») --
    def watch_ajouter(self, x):
        import watchlist
        return watchlist.ajouter(self, x)

    def watch_retirer(self, item_id):
        import watchlist
        return watchlist.retirer(self, item_id)

    def watch_liste(self):
        import watchlist
        return watchlist.liste(self)

    def watch_regler(self, d):
        import watchlist
        return watchlist.regler(self, d)

    def watch_vers_ebay(self, ids=None):
        """31 oct 2026 : envoie la watchlist de l'app dans la watchlist eBay du compte connecte (un geste de l'utilisateur)."""
        import watchlist
        return watchlist.vers_ebay(self, ids)

    def watch_gixen(self):
        """31 oct 2026 : les mises rapides (Gixen), pour l'admin seulement."""
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'admin"}
        import watchlist
        return watchlist.gixen(self)

    def watch_preparer(self):
        """31 oct 2026 (Mathieu : « SlabCoach prepare la mise ; l'utilisateur entre son montant, ca ouvre eBay ; il lui
        reste juste a dire oui ») : les encans de la watchlist prets a miser (pour tous ; rien n'est mise par SlabCoach)."""
        import watchlist
        return watchlist.preparer(self)

    def watch_mise_max(self, item_id, valeur=None):
        import watchlist
        return watchlist.mise_max(self, item_id, valeur)

    def watch_proches(self):
        """Boucle du serveur (5 min) : les encans suivis qui finissent bientot, relus sur eBay."""
        import watchlist
        return {"ok": True, "envoyees": watchlist.verifier(self, proches=True)}

    _TENDANCES = {"le": 0.0, "v": None}
    _DEMARRE = time.time()                                  # 3 nov 2026 : le demarrage du serveur (le calme des 3 premieres minutes)
    _TENDANCES_VERROU = threading.Lock()

    def tendances(self):
        """28 oct 2026 (vitesse) : 2 a 6 s de calcul, le meme resultat pour tous les comptes : garde 15 min."""
        if not comps_permis(self):              # 10 nov 2026 : comps = admin seulement (lancement)
            return {"ok": True, "coupe": True, "hausses": [], "baisses": [], "plus_vendues": [], "indice": None}
        # 3 nov 2026 (Render : « health check timed out ») : le calcul (plusieurs secondes, 1 seul serveur) ne bloque plus une
        # requete : la derniere version est servie tout de suite et la nouvelle se calcule a cote, une seule a la fois
        import threading as _th
        import time as _t
        import comptes as _cp
        T = Api._TENDANCES
        ch = os.path.join(_cp.DONNEES, "tendances_cache.json")
        if T["v"] is None:                                   # au demarrage : la derniere version gardee sur le disque
            with Api._TENDANCES_VERROU:
                if T["v"] is None:
                    try:
                        with open(ch, encoding="utf-8") as f:
                            g = json.load(f)
                        T["v"], T["le"] = g["v"], float(g.get("le") or 0)
                    except (OSError, ValueError, KeyError, TypeError):
                        pass
        # 3 nov 2026 (Mathieu : « tellement long apres une mise a jour ») : le calcul complet (toute la base des ventes) est
        # lourd ; aux 60 min (une tendance sur 14 jours ne bouge pas en 15 min), et jamais dans les 3 minutes apres un
        # demarrage si une version est deja gardee
        calme = T["v"] is not None and _t.time() - Api._DEMARRE < deals.CALME_S
        if (T["v"] is None or _t.time() - T["le"] > 3600) and not T.get("calcul") and not calme:
            T["calcul"] = True

            def refaire():
                try:
                    v = marche.tendances()
                    T["v"], T["le"] = v, _t.time()
                    try:
                        tmp = ch + ".tmp"
                        with open(tmp, "w", encoding="utf-8") as f:
                            json.dump({"le": T["le"], "v": v}, f, ensure_ascii=False)
                        os.replace(tmp, ch)
                    except (OSError, TypeError, ValueError):
                        pass
                except Exception as e:
                    print("Tendances : " + repr(e), flush=True)
                finally:
                    T["calcul"] = False
            _th.Thread(target=refaire, daemon=True, name="tendances").start()
        if T["v"] is None:                                   # le tout premier calcul : l'ecran dit d'attendre un peu
            return {"ok": False, "hausses": [], "baisses": [], "plus_vendues": [], "records": [], "calcul": True}
        return T["v"]

    def pouls(self, langue=None):
        """27 oct 2026 : le pouls du hobby (segments qui chauffent, mesures sur ventes reelles)."""
        if not comps_permis(self):              # 10 nov 2026 : comps = admin seulement (lancement)
            return {"ok": True, "coupe": True, "segments": []}
        import pouls
        return pouls.resume(langue or self.reglages_lire().get("langue") or "fr")

    def astuces(self, force=False, langue=None):
        """26 oct 2026 - « Le savais-tu ? » : astuces verifiees (calculees sur les vraies ventes ou sourcees), pour l'accueil."""
        import astuces
        if not comps_permis(self):              # 10 nov 2026 : astuces calculees sur les ventes = admin seulement
            return {"ok": True, "astuces": [], "coupe": True}
        rg = self.reglages_lire()
        return {"ok": True, "astuces": astuces.liste(self, rg.get("niveau"), bool(force), "en" if (langue or rg.get("langue")) == "en" else "fr")}

    def collection(self):
        return marche.collection(self)

    # 1er nov 2026 (Mathieu : « CollX et Collectr, on doit etre mieux ») : la collection par sets, sa valeur dans le temps, l'export
    def collection_sets(self):
        import collection_sets
        return collection_sets.sets(self)

    def collection_checklist(self, pid, sous):
        import collection_sets
        return collection_sets.checklist(self, pid, sous)

    def collection_valeur(self):
        if not comps_permis(self):              # 10 nov 2026 : comps = admin seulement (lancement)
            return {"ok": True, "coupe": True}
        import collection_sets
        return collection_sets.valeur(self)

    def collection_csv(self):
        import collection_sets
        return collection_sets.csv_texte(self)

    def calendrier(self):
        return marche.calendrier()

    def conseils(self, force=False, langue=None):
        """26 oct 2026 - la zone Conseils de l'accueil (IA, 6 h par compte ; sinon par regles)."""
        import conseils
        r = self.reglages_lire()
        return conseils.obtenir(self, mode=r.get("mode") or "vendeur", langue=langue or r.get("langue") or "fr", force=bool(force))

    def budget_etat(self):
        """25 oct 2026 (Mathieu : « qu'il fasse un choix éclairé avec ses sous durement gagnés tout en s'assurant qu'il
        ne dépasse pas son budget ») : budget du mois, ce qui est deja depense (achats eBay du compte, synchro) et le reste."""
        r = self.reglages_lire()
        budget = float(r.get("budget_mois") or 0)
        m0 = datetime.now().strftime("%Y-%m")
        c = self._db()
        try:
            c.execute("CREATE TABLE IF NOT EXISTS achats_ebay (item_id TEXT, n INTEGER, titre TEXT, cout REAL, devise TEXT, "
                      "date TEXT, carte_id INTEGER, PRIMARY KEY (item_id, n))")
            l = _dicts(c.execute("SELECT titre, cout, date FROM achats_ebay WHERE date LIKE ? ORDER BY date DESC", (m0 + "%",)))
        finally:
            c.close()
        dep = round(sum(x["cout"] or 0 for x in l), 2)
        return {"ok": True, "mois": m0, "budget": budget, "depense": dep, "reste": round(budget - dep, 2) if budget else None,
                "nb_achats": len(l), "achats": l[:8], "pct": round(100 * dep / budget) if budget else None}

    def couts_depuis_achats(self, achats=None):
        """25 oct 2026 - le cout d'acquisition des cartes ACHETEES sur eBay (comme Hall of Cardz) : chaque achat
        (role acheteur, 90 jours) est relie a la carte de l'inventaire qui lui ressemble le plus (meme joueur, meme
        carte, mise en vente apres l'achat), et son cout reel paye devient le cout de la carte. Une carte achetee
        ailleurs : l'utilisateur entre son cout lui-meme. Jamais un cout deja entre n'est remplace."""
        import difflib
        if achats is None:
            achats = ebay_compte.achats(90)
        taux = 1 / float(self.taux_change().get("usd") or 0.72)                  # 1 $ US -> $ CA
        res = {"achats": len(achats), "relies": 0}
        with _verrou:
            c = self._db()
            try:
                c.execute("CREATE TABLE IF NOT EXISTS achats_ebay (item_id TEXT, n INTEGER, titre TEXT, cout REAL, devise TEXT, "
                          "date TEXT, carte_id INTEGER, PRIMARY KEY (item_id, n))")
                for x in achats:
                    if x.get("cout_total") is None:
                        continue
                    cout = x["cout_total"] / max(1, x.get("quantite") or 1)
                    cout = round(cout * (taux if (x.get("devise") or "CAD") == "USD" else 1.0), 2)
                    for k in range(max(1, x.get("quantite") or 1)):
                        c.execute("INSERT OR IGNORE INTO achats_ebay (item_id, n, titre, cout, devise, date) VALUES (?,?,?,?,?,?)",
                                  (str(x["item_id"]), k, x.get("titre") or "", cout, "CAD", x.get("date")))
                libres = _dicts(c.execute("SELECT rowid AS rid, * FROM achats_ebay WHERE carte_id IS NULL"))
                cartes = _dicts(c.execute("SELECT id, titre, joueur, cree_le, debut FROM cartes WHERE COALESCE(cout, 0) = 0 "
                                          "AND COALESCE(titre, '') <> ''"))
                pris = {r[0] for r in c.execute("SELECT carte_id FROM achats_ebay WHERE carte_id IS NOT NULL")}
                for a in sorted(libres, key=lambda z: str(z.get("date") or "")):
                    cib = cartes_match.cible_titre(a["titre"])
                    meilleur, score_m = None, 0.0
                    for k in cartes:
                        if k["id"] in pris:
                            continue
                        quand = str(k.get("debut") or k.get("cree_le") or "")[:10]
                        if quand and a.get("date") and quand < str(a["date"])[:10]:
                            continue                                   # mise en vente avant l'achat : pas cette carte
                        if cartes_match.raisons_refus(cib, k["titre"]):
                            continue
                        sc = difflib.SequenceMatcher(None, cartes_match.norm(a["titre"]), cartes_match.norm(k["titre"])).ratio()
                        if sc > score_m:
                            meilleur, score_m = k, sc
                    if meilleur and score_m >= 0.45:
                        c.execute("UPDATE cartes SET cout=?, note=TRIM(COALESCE(note,'') || ' Coût : achat eBay #' || ?) WHERE id=? "
                                  "AND COALESCE(cout,0)=0", (a["cout"], a["item_id"], meilleur["id"]))
                        c.execute("UPDATE achats_ebay SET carte_id=? WHERE rowid=?", (meilleur["id"], a["rid"]))
                        pris.add(meilleur["id"])
                        res["relies"] += 1
                c.commit()
            finally:
                c.close()
        return {"ok": True, **res}

    # 30 oct 2026 (Mathieu : « relie a mon inventaire : j'ai des cartes d'inventaire reliees a mes achats ») : sur la fiche
    # d'une carte, l'achat eBay qui lui est relie (date, cout, lien) ; sinon les achats non relies qui lui ressemblent, un
    # tap pour relier (le cout paye devient le cout de la carte). Les achats : 90 jours (limite d'eBay), lus a la synchro.
    _SQL_ACHATS = ("CREATE TABLE IF NOT EXISTS achats_ebay (item_id TEXT, n INTEGER, titre TEXT, cout REAL, devise TEXT, "
                   "date TEXT, carte_id INTEGER, PRIMARY KEY (item_id, n))")

    def achats_carte(self, carte_id):
        import difflib
        cid = int(carte_id or 0)
        c = self._db()
        try:
            c.execute(self._SQL_ACHATS)
            k = c.execute("SELECT id, titre, joueur FROM cartes WHERE id=?", (cid,)).fetchone()
            vide = not c.execute("SELECT 1 FROM achats_ebay LIMIT 1").fetchone()
        finally:
            c.close()
        if not k:
            return {"ok": False, "erreur": "Carte introuvable"}
        if vide and ebay_compte.statut().get("connecte"):
            try:                                          # premiere fois : on lit les achats tout de suite (un appel Trading)
                self.couts_depuis_achats()
            except Exception:
                pass
        c = self._db()
        try:
            self._achats_table(c)
            lie = _dicts(c.execute("SELECT item_id, n, titre, cout, date, photo FROM achats_ebay WHERE carte_id=?", (cid,)))
            libres = _dicts(c.execute("SELECT item_id, n, titre, cout, date, photo FROM achats_ebay WHERE carte_id IS NULL ORDER BY date DESC"))
            nb = c.execute("SELECT COUNT(*) FROM achats_ebay").fetchone()[0]
        finally:
            c.close()
        t = cartes_match.norm(k[1] or "")
        cib = cartes_match.cible_titre(k[1] or "", k[2] or None) if (k[1] or k[2]) else None
        fam = (cartes_match.norm(k[2] or "") or (cib or {}).get("joueur") or "").split()[-1:] 
        for a in libres:                                   # le meme joueur d'abord, puis la meme carte, puis le titre
            ta = cartes_match.norm(a["titre"] or "")
            joueur_ = bool(fam and re.search(r"\b" + re.escape(fam[0]) + r"\b", ta))
            # 5 nov 2026 (Mathieu : « l'app doit reconnaitre si la carte a deja ete achetee et demander de la matcher ») :
            # la MEME carte (meme joueur et aucune raison de refus) : l'app pose la question elle-meme
            a["meme_carte"] = bool(joueur_ and cib and not cartes_match.raisons_refus(cib, a["titre"] or ""))
            a["photo"] = a["photo"] if a.get("photo") and a["photo"] != "-" else None
            a["score"] = round((0.5 if joueur_ else 0)
                               + (0.3 if a["meme_carte"] else 0)
                               + 0.2 * difflib.SequenceMatcher(None, t, ta).ratio(), 3)
        libres.sort(key=lambda a: -a["score"])
        return {"ok": True, "lie": lie[0] if lie else None, "suggestions": libres[:30], "nb_achats": nb,
                "ebay": bool(ebay_compte.statut().get("connecte"))}

    def achat_relier(self, carte_id, item_id, n=0):
        cid = int(carte_id or 0)
        with _verrou:
            c = self._db()
            try:
                c.execute(self._SQL_ACHATS)
                a = c.execute("SELECT cout, carte_id FROM achats_ebay WHERE item_id=? AND n=?", (str(item_id), int(n or 0))).fetchone()
                if not a:
                    return {"ok": False, "erreur": "Achat introuvable"}
                if a[1] and a[1] != cid:
                    return {"ok": False, "erreur": "Cet achat est déjà relié à une autre carte"}
                if not c.execute("SELECT 1 FROM cartes WHERE id=?", (cid,)).fetchone():
                    return {"ok": False, "erreur": "Carte introuvable"}
                c.execute("UPDATE achats_ebay SET carte_id=NULL WHERE carte_id=?", (cid,))
                c.execute("UPDATE achats_ebay SET carte_id=? WHERE item_id=? AND n=?", (cid, str(item_id), int(n or 0)))
                c.execute("UPDATE cartes SET cout=? WHERE id=?", (a[0], cid))
                c.commit()
            finally:
                c.close()
        return {"ok": True, "cout": a[0]}

    def achat_delier(self, carte_id):
        with _verrou:
            c = self._db()
            try:
                c.execute(self._SQL_ACHATS)
                c.execute("UPDATE achats_ebay SET carte_id=NULL WHERE carte_id=?", (int(carte_id or 0),))
                c.commit()
            finally:
                c.close()
        return {"ok": True}

    # 5 nov 2026 (Mathieu : « quand je gagne des cartes, elles devraient se retrouver dans une zone achats de l'inventaire ;
    # quand je mets en ligne une carte achetee avant, elle est reliee directement ») : la liste des achats eBay (90 jours,
    # lus a chaque synchro), un tap pour en faire une carte de l'inventaire (cout = le vrai prix paye) ; et a la vente,
    # les achats qui ressemblent a la carte, un tap pour les relier.
    def _lier_achat_choisi(self, cid, achat):
        if not cid or not isinstance(achat, dict) or not achat.get("item_id"):
            return None
        r = self.achat_relier(cid, achat.get("item_id"), achat.get("n") or 0)
        return {"cout": r.get("cout")} if r.get("ok") else None

    def _achats_photos(self, l, n=12):
        """Les photos des achats qui n'en ont pas (GetItem, en fond, quelques-unes a la fois)."""
        manque = [a for a in l if not a.get("photo")][:n]
        if not manque or not ebay_compte.statut().get("connecte"):
            return
        import contextvars
        ctx = contextvars.copy_context()

        def tache():
            for a in manque:
                try:
                    ph = ebay_compte.photo_item(a["item_id"]) or "-"
                except Exception:
                    ph = "-"
                with _verrou:
                    c = self._db()
                    try:
                        c.execute("UPDATE achats_ebay SET photo=? WHERE item_id=?", (ph if isinstance(ph, str) else (ph[0] if ph else "-"), str(a["item_id"])))
                        c.commit()
                    finally:
                        c.close()
        threading.Thread(target=lambda: ctx.run(tache), daemon=True, name="photos-achats").start()

    def _achats_table(self, c):
        c.execute(self._SQL_ACHATS)
        if "photo" not in {r[1] for r in c.execute("PRAGMA table_info(achats_ebay)")}:
            c.execute("ALTER TABLE achats_ebay ADD COLUMN photo TEXT")

    def achats_liste(self, force=False):
        """-> {achats: [{item_id, n, titre, cout, date, photo, carte_id, carte_titre, carte_statut}], a_ajouter, ebay, maj}"""
        if force and ebay_compte.statut().get("connecte"):
            try:
                self.couts_depuis_achats()
            except Exception as e:
                print("Achats eBay : " + repr(e), flush=True)
        with _verrou:
            c = self._db()
            try:
                self._achats_table(c)
                vide = not c.execute("SELECT 1 FROM achats_ebay LIMIT 1").fetchone()
            finally:
                c.close()
        if vide and not force and ebay_compte.statut().get("connecte"):
            return self.achats_liste(True)
        c = self._db()
        try:
            self._achats_table(c)
            l = _dicts(c.execute("SELECT a.item_id, a.n, a.titre, a.cout, a.date, a.photo, a.carte_id, k.titre AS carte_titre, "
                                 "k.statut AS carte_statut FROM achats_ebay a LEFT JOIN cartes k ON k.id = a.carte_id "
                                 "ORDER BY (a.carte_id IS NOT NULL), a.date DESC LIMIT 400"))
        finally:
            c.close()
        for a in l:
            if a.get("carte_id") and not a.get("carte_titre"):
                a["carte_id"] = None                    # la carte a ete effacee : l'achat redevient libre
            if a.get("photo") == "-":
                a["photo"] = None
        self._achats_photos([a for a in l if not a.get("carte_id")])
        return {"ok": True, "achats": l, "a_ajouter": sum(1 for a in l if not a.get("carte_id")),
                "ebay": bool(ebay_compte.statut().get("connecte"))}

    def achat_vers_inventaire(self, item_id, n=0, emplacement=None):
        """Un achat eBay -> une carte de l'inventaire (En stock), cout = le prix paye, titre et photo de l'annonce."""
        with _verrou:
            c = self._db()
            try:
                self._achats_table(c)
                a = c.execute("SELECT titre, cout, date, photo, carte_id FROM achats_ebay WHERE item_id=? AND n=?",
                              (str(item_id), int(n or 0))).fetchone()
            finally:
                c.close()
        if not a:
            return {"ok": False, "erreur": "Achat introuvable"}
        if a["carte_id"] and self.carte_lire(a["carte_id"]):
            return {"ok": True, "id": a["carte_id"], "deja": True}
        titre = re.sub(r"\s+", " ", str(a["titre"] or "")).strip()[:80] or "Carte achetée sur eBay"
        d = {"titre": titre, "cout": a["cout"], "statut": "En stock", "source": "achat eBay",
             "emplacement": emplacement if emplacement in ("Collection", "Réserve", "Magasin") else "Réserve",
             "joueur": cartes_match.joueur_du_titre(titre) or None, "note": f"Achat eBay #{item_id} ({a['date'] or ''})".strip()}
        if a["photo"] and a["photo"] != "-" and str(a["photo"]).startswith("https://"):
            d["photo"] = a["photo"]
        r = self.carte_sauver({k: v for k, v in d.items() if v not in (None, "")})
        with _verrou:
            c = self._db()
            try:
                c.execute("UPDATE achats_ebay SET carte_id=? WHERE item_id=? AND n=?", (r["id"], str(item_id), int(n or 0)))
                c.commit()
            finally:
                c.close()
        return {"ok": True, "id": r["id"]}

    def _mes_achats_titre(self, titre, item_id=None):
        """9 nov 2026 (Mathieu : « quand j'affiche une carte, l'app doit chercher si on l'a deja achetee : pour le prix paye
        (profit) et pour ne pas prendre notre achat dans les comps, tout sauf notre deal ») : (achats de la MEME carte, les 3
        plus recents ; numeros d'annonce de TOUS tes achats ; cette annonce-ci est un de tes achats)."""
        t = str(titre or "").strip()
        try:
            c = self._db()
            try:
                self._achats_table(c)
                tous = _dicts(c.execute("SELECT item_id, n, titre, cout, date, photo, carte_id FROM achats_ebay ORDER BY date DESC LIMIT 3000"))
            finally:
                c.close()
        except Exception as e:
            print("Mes achats : " + repr(e), flush=True)
            return [], set(), False
        ids = {str(a["item_id"]) for a in tous if a.get("item_id")}
        exact = bool(item_id) and str(item_id) in ids
        memes = []
        if len(t) >= 6:
            cib = cartes_match.cible_titre(t)
            nom = (cib.get("joueur") or "").split()[-1:]
            for a in tous:
                ta = cartes_match.norm(a["titre"] or "")
                if str(a.get("item_id")) == str(item_id or "-") or (nom and re.search(r"\b" + re.escape(nom[0]) + r"\b", ta)
                                                                   and not cartes_match.raisons_refus(cib, a["titre"] or "")):
                    a["photo"] = a["photo"] if a.get("photo") and a["photo"] != "-" else None
                    a["cette_annonce"] = str(a.get("item_id")) == str(item_id or "-")
                    memes.append(a)
                    if len(memes) >= 3:
                        break
        return memes, ids, exact

    @staticmethod
    def _sans_mes_achats(vs, memes, ids):
        """Les comps sans tes achats : son numero d'annonce, ou (achat de la meme carte) une vente au prix paye a 2 jours."""
        def mien(v):
            iv = str(v.get("item_id") or "") or (vendues._id_vente(v) or "")
            if iv and iv in ids:
                return True
            try:
                p, d = float(v.get("prix")), datetime.fromisoformat(str(v.get("le"))[:10])
            except (TypeError, ValueError):
                return False
            for a in memes:
                try:
                    if a.get("cout") and abs((d - datetime.fromisoformat(str(a["date"])[:10])).days) <= 2 \
                            and abs(p - float(a["cout"])) <= max(1.0, 0.05 * float(a["cout"])):
                        return True
                except (TypeError, ValueError):
                    pass
            return False
        out = [v for v in vs or [] if not mien(v)]
        return out, len(vs or []) - len(out)

    def achats_suggerer(self, titre):
        """A la vente : les achats pas encore relies qui ressemblent a ce titre (meme carte d'abord). -> {achats: [...]}"""
        import difflib
        t = str(titre or "").strip()
        if len(t) < 6:
            return {"ok": True, "achats": []}
        c = self._db()
        try:
            self._achats_table(c)
            libres = _dicts(c.execute("SELECT item_id, n, titre, cout, date, photo FROM achats_ebay WHERE carte_id IS NULL ORDER BY date DESC LIMIT 400"))
        finally:
            c.close()
        cib = cartes_match.cible_titre(t)
        nom = (cib.get("joueur") or "").split()[-1:]
        out = []
        for a in libres:
            ta = cartes_match.norm(a["titre"] or "")
            if nom and not re.search(r"\b" + re.escape(nom[0]) + r"\b", ta):
                continue                                 # pas le meme joueur : jamais propose
            meme = not cartes_match.raisons_refus(cib, a["titre"] or "")
            a["meme_carte"] = meme
            a["photo"] = a["photo"] if a.get("photo") and a["photo"] != "-" else None
            a["score"] = round((0.6 if meme else 0) + 0.4 * difflib.SequenceMatcher(None, cartes_match.norm(t), ta).ratio(), 3)
            out.append(a)
        out.sort(key=lambda a: -a["score"])
        return {"ok": True, "achats": out[:4]}

    # -- comptoir (boutique physique) -----------------------------------------------------------
    def comptoir_vente(self, d):
        """d : {lignes: [{carte_id?, description, prix}], paiement, client_id, taxes (bool), credit_utilise}"""
        d = d or {}
        r = self.reglages_lire()
        lignes = [l for l in (d.get("lignes") or []) if _float(l.get("prix")) is not None]
        if not lignes:
            return {"ok": False, "erreur": "Panier vide"}
        sous_total = round(sum(_float(l["prix"]) for l in lignes), 2)
        taxes = round(sous_total * r["taxes_pct"] / 100, 2) if d.get("taxes", True) else 0.0
        total = round(sous_total + taxes, 2)
        credit = max(0.0, min(_float(d.get("credit_utilise")) or 0, total))
        with _verrou:
            c = self._db()
            try:
                # 4 nov 2026 (revue) : le credit utilise ne depasse pas celui du client (et il faut un client)
                if credit:
                    cl = c.execute("SELECT credit FROM clients WHERE id=?", (d.get("client_id"),)).fetchone() if d.get("client_id") else None
                    credit = round(min(credit, max(0.0, (cl["credit"] or 0) if cl else 0.0)), 2)
                vid = c.execute("INSERT INTO ventes_comptoir (le, sous_total, taxes, total, paiement, client_id, lignes) VALUES (?,?,?,?,?,?,?)",
                                (_maintenant(), sous_total, taxes, total, d.get("paiement") or "Comptant", d.get("client_id"),
                                 json.dumps(lignes))).lastrowid
                if credit and d.get("client_id"):
                    c.execute("UPDATE clients SET credit = MAX(0, COALESCE(credit,0) - ?) WHERE id=?", (credit, d["client_id"]))
                c.commit()
            finally:
                c.close()
        for l in lignes:
            if l.get("carte_id"):
                self.carte_vendre(l["carte_id"], {"canal": "Magasin", "prix": l["prix"], "client_id": d.get("client_id")})
        return {"ok": True, "id": vid, "sous_total": sous_total, "taxes": taxes, "total": total, "a_payer": round(total - credit, 2)}

    def rachat_calculer(self, valeurs):
        r = self.reglages_lire()
        paliers = [(float(s), float(p) / 100) for s, p in r["paliers_rachat"]]
        return calcul.offre_rachat(valeurs or [], paliers, r["bonus_credit"] / 100)

    def rachat_accepter(self, d):
        """d : {lignes: [{titre, joueur, valeur}], mode: 'comptant'|'credit', client_id}. Les cartes
        entrent en inventaire avec leur cout = l'offre payee."""
        d = d or {}
        lignes = d.get("lignes") or []
        offre = self.rachat_calculer([l.get("valeur") for l in lignes])
        credit = d.get("mode") == "credit"
        if credit and not d.get("client_id"):            # 4 nov 2026 (revue) : un credit va a quelqu'un
            return {"ok": False, "erreur": "Choisis le client qui reçoit le crédit"}
        facteur = (offre["credit"] / offre["comptant"]) if (credit and offre["comptant"]) else 1.0
        with _verrou:
            c = self._db()
            try:
                c.execute("INSERT INTO rachats (le, client_id, valeur, offre, mode, lignes) VALUES (?,?,?,?,?,?)",
                          (_maintenant(), d.get("client_id"), offre["valeur"], offre["credit"] if credit else offre["comptant"],
                           "credit" if credit else "comptant", json.dumps(lignes)))
                if credit and d.get("client_id"):
                    c.execute("UPDATE clients SET credit = COALESCE(credit,0) + ? WHERE id=?", (offre["credit"], d["client_id"]))
                c.commit()
            finally:
                c.close()
        for l, o in zip(lignes, offre["lignes"]):
            self.carte_sauver({"titre": l.get("titre") or l.get("joueur") or "Carte rachetée", "joueur": l.get("joueur"),
                               "valeur": o["valeur"], "cout": round(o["offre"] * facteur, 2), "source": "rachat",
                               "emplacement": "Magasin", "client_id": d.get("client_id")})
        return {"ok": True, **offre, "paye": offre["credit"] if credit else offre["comptant"], "mode": "credit" if credit else "comptant"}

    def clients_liste(self):
        with _verrou:
            c = self._db()
            try:
                return _dicts(c.execute("SELECT * FROM clients ORDER BY nom"))
            finally:
                c.close()

    def client_sauver(self, d):
        d = d or {}
        with _verrou:
            c = self._db()
            try:
                if d.get("id"):
                    c.execute("UPDATE clients SET nom=?, contact=?, note=? WHERE id=?", (d.get("nom"), d.get("contact"), d.get("note"), d["id"]))
                    cid = d["id"]
                else:
                    cid = c.execute("INSERT INTO clients (nom, contact, note, credit, cree_le) VALUES (?,?,?,0,?)",
                                    (d.get("nom") or "Client", d.get("contact"), d.get("note"), _maintenant())).lastrowid
                c.commit()
            finally:
                c.close()
        return {"ok": True, "id": cid}

    def consignataires_liste(self):
        """Avec le montant du (cartes vendues pas encore payees)."""
        r = self.reglages_lire()
        with _verrou:
            c = self._db()
            try:
                out = _dicts(c.execute("SELECT * FROM consignataires ORDER BY nom"))
                for k in out:
                    pct = (k["pct_boutique"] if k["pct_boutique"] is not None else r["pct_consignation"]) / 100
                    vendues = _dicts(c.execute("SELECT prix_vendu, frais, port_paye FROM cartes WHERE consignataire_id=? "
                                               "AND statut='Vendue' AND consignation_payee=0", (k["id"],)))
                    k["du"] = round(sum(((v["prix_vendu"] or 0) - (v["frais"] or 0) - (v["port_paye"] or 0)) * (1 - pct) for v in vendues), 2)
                    k["nb_vendues"] = len(vendues)
                    k["nb_en_vente"] = c.execute("SELECT COUNT(*) FROM cartes WHERE consignataire_id=? AND statut!='Vendue'",
                                                 (k["id"],)).fetchone()[0]
            finally:
                c.close()
        return out

    def consignataire_sauver(self, d):
        d = d or {}
        with _verrou:
            c = self._db()
            try:
                if d.get("id"):
                    c.execute("UPDATE consignataires SET nom=?, contact=?, pct_boutique=? WHERE id=?",
                              (d.get("nom"), d.get("contact"), _float(d.get("pct_boutique")), d["id"]))
                    cid = d["id"]
                else:
                    cid = c.execute("INSERT INTO consignataires (nom, contact, pct_boutique, cree_le) VALUES (?,?,?,?)",
                                    (d.get("nom") or "Consignataire", d.get("contact"), _float(d.get("pct_boutique")), _maintenant())).lastrowid
                c.commit()
            finally:
                c.close()
        return {"ok": True, "id": cid}

    def consignation_payer(self, cons_id):
        du = next((k["du"] for k in self.consignataires_liste() if k["id"] == cons_id), 0)
        with _verrou:
            c = self._db()
            try:
                c.execute("UPDATE cartes SET consignation_payee=1 WHERE consignataire_id=? AND statut='Vendue'", (cons_id,))
                c.execute("INSERT INTO paiements_consignation (consignataire_id, montant, le) VALUES (?,?,?)", (cons_id, du, _maintenant()))
                c.commit()
            finally:
                c.close()
        return {"ok": True, "paye": du}

    # -- depenses et bilan ---------------------------------------------------------------------------
    def depense_ajouter(self, d):
        d = d or {}
        with _verrou:
            c = self._db()
            try:
                c.execute("INSERT INTO depenses (le, categorie, montant, note) VALUES (?,?,?,?)",
                          (d.get("le") or _maintenant()[:10], d.get("categorie") or "Autre", _float(d.get("montant")) or 0, d.get("note")))
                c.commit()
            finally:
                c.close()
        return {"ok": True}

    def bilan(self, mois=None):
        """mois « AAAA-MM » (defaut : ce mois-ci). Revenus et profit par canal."""
        mois = mois or datetime.now().strftime("%Y-%m")
        out = {"mois": mois, "canaux": {}, "depenses": 0.0}
        with _verrou:
            c = self._db()
            try:
                for canal, rev, prof, nb in c.execute(
                        "SELECT canal, SUM(prix_vendu), SUM(profit), COUNT(*) FROM cartes WHERE statut='Vendue' AND substr(vendu_le,1,7)=? "
                        "GROUP BY canal", (mois,)):
                    out["canaux"][canal or "Autre"] = {"revenus": round(rev or 0, 2), "profit": round(prof or 0, 2), "nb": nb}
                ventes_libres = c.execute("SELECT lignes FROM ventes_comptoir WHERE substr(le,1,7)=?", (mois,)).fetchall()
                libre = sum(_float(l.get("prix")) or 0 for (lj,) in ventes_libres for l in json.loads(lj) if not l.get("carte_id"))
                if libre:
                    m = out["canaux"].setdefault("Magasin", {"revenus": 0.0, "profit": 0.0, "nb": 0})
                    m["revenus"] = round(m["revenus"] + libre, 2)
                    m["profit"] = round(m["profit"] + libre, 2)       # article sans cout connu
                taxes = c.execute("SELECT COALESCE(SUM(taxes),0) FROM ventes_comptoir WHERE substr(le,1,7)=?", (mois,)).fetchone()[0]
                out["taxes_percues"] = round(taxes, 2)
                out["depenses"] = round(c.execute("SELECT COALESCE(SUM(montant),0) FROM depenses WHERE substr(le,1,7)=?",
                                                  (mois,)).fetchone()[0], 2)
                out["rachats"] = round(c.execute("SELECT COALESCE(SUM(offre),0) FROM rachats WHERE substr(le,1,7)=? AND mode='comptant'",
                                                 (mois,)).fetchone()[0], 2)
            finally:
                c.close()
        brk = [b for b in self.breaks_liste() if str(b["cree_le"] or "")[:7] == mois]
        if brk:
            out["canaux"]["Breaks"] = {"revenus": round(sum(b["revenus"] for b in brk), 2),
                                       "profit": round(sum(b["profit"] for b in brk), 2), "nb": len(brk)}
        out["revenus"] = round(sum(v["revenus"] for v in out["canaux"].values()), 2)
        out["profit"] = round(sum(v["profit"] for v in out["canaux"].values()) - out["depenses"], 2)
        return out

    def ventes_analyse(self, periode="90"):
        """5 nov 2026 (Mathieu : « une section pour mes solds et faire une analyse profit ») : les cartes vendues sur une
        periode (« 30 », « 90 », « 365 », « tout » ou « AAAA-MM ») : revenus, profit, marge, retour sur le cout, delai de
        vente, profit par mois (12 mois), par type (gradee / raw), sport, canal, joueur ; meilleures ventes et pertes.
        Le profit ne compte que les ventes dont le cout est connu (les autres sont comptees a part : a relier)."""
        p = str(periode or "90").strip()
        if re.fullmatch(r"\d{4}-\d{2}", p):
            cond, args = "substr(vendu_le,1,7)=?", [p]
        elif p == "tout":
            cond, args = "1=1", []
        else:
            j = int(p) if p.isdigit() and 0 < int(p) <= 3650 else 90
            p = str(j)
            cond, args = "date(substr(vendu_le,1,10)) >= date('now', ?)", [f"-{j} days"]
        c = self._db()
        try:
            self._achats_table(c)
            cols = {r[1] for r in c.execute("PRAGMA table_info(cartes)")}
            sp = "sport" if "sport" in cols else "NULL AS sport"
            sel = (f"SELECT id, titre, joueur, annee, set_nom, parallele, tirage, auto, grade, {sp}, cout, prix_vendu, frais, profit, canal, "
                   "cree_le, vendu_le, photo, (SELECT MIN(date) FROM achats_ebay a WHERE a.carte_id=cartes.id) AS achete_le "
                   "FROM cartes WHERE statut='Vendue' AND vendu_le IS NOT NULL")
            l = _dicts(c.execute(sel + f" AND {cond} ORDER BY vendu_le DESC", args))
            douze = _dicts(c.execute("SELECT substr(vendu_le,1,7) AS m, COUNT(*) AS nb, SUM(prix_vendu) AS rev, "
                                     "SUM(CASE WHEN cout IS NOT NULL THEN profit END) AS prof FROM cartes WHERE statut='Vendue' "
                                     "AND date(substr(vendu_le,1,10)) >= date('now','start of month','-11 months') GROUP BY m ORDER BY m"))
        finally:
            c.close()

        def jour(x):
            try:
                return datetime.fromisoformat(str(x)[:10])
            except (TypeError, ValueError):
                return None
        for v in l:
            v["sans_cout"] = v.get("cout") is None
            if v["sans_cout"]:
                v["profit"] = None
            d0, d1 = jour(v.get("achete_le") or v.get("cree_le")), jour(v.get("vendu_le"))
            v["jours"] = (d1 - d0).days if d0 and d1 and d1 >= d0 else None

        def resume(g):
            ac = [v for v in g if not v["sans_cout"]]
            rev = round(sum(_float(v.get("prix_vendu")) or 0 for v in g), 2)
            rev_c = sum(_float(v.get("prix_vendu")) or 0 for v in ac)
            cout = sum(_float(v.get("cout")) or 0 for v in ac)
            prof = round(sum(_float(v.get("profit")) or 0 for v in ac), 2)
            return {"nb": len(g), "revenus": rev, "profit": prof, "avec_cout": len(ac),
                    "marge": round(100 * prof / rev_c, 1) if rev_c > 0 else None,
                    "roi": round(100 * prof / cout, 1) if cout > 0 else None}

        def par(cle, n=8):
            grp = {}
            for v in l:
                grp.setdefault(cle(v) or "Autre", []).append(v)
            out = [{"nom": k, **resume(g)} for k, g in grp.items()]
            out.sort(key=lambda x: (-(x["profit"] or 0), -x["revenus"]))
            return out[:n]
        k = resume(l)
        ac = [v for v in l if not v["sans_cout"]]
        js = sorted(v["jours"] for v in l if v["jours"] is not None)
        k.update(frais=round(sum(_float(v.get("frais")) or 0 for v in l), 2),
                 cout=round(sum(_float(v.get("cout")) or 0 for v in ac), 2),
                 profit_moyen=round(k["profit"] / len(ac), 2) if ac else None,
                 jours_median=js[len(js) // 2] if js else None,
                 sans_cout=sum(1 for v in l if v["sans_cout"]),
                 revenus_sans_cout=round(sum(_float(v.get("prix_vendu")) or 0 for v in l if v["sans_cout"]), 2),
                 pertes=sum(1 for v in ac if (_float(v.get("profit")) or 0) < 0))
        champs = ("id", "titre", "joueur", "annee", "set_nom", "parallele", "grade", "sport", "cout", "prix_vendu", "frais", "profit",
                  "canal", "vendu_le", "photo", "jours", "sans_cout")
        court = lambda v: {x: v.get(x) for x in champs}
        tri = sorted(ac, key=lambda v: -(_float(v.get("profit")) or 0))
        return {"ok": True, "periode": p, "kpis": k,
                "par_mois": [{"mois": m["m"], "nb": m["nb"], "revenus": round(m["rev"] or 0, 2), "profit": round(m["prof"] or 0, 2)} for m in douze],
                "par_type": par(lambda v: "Gradée" if str(v.get("grade") or "").strip() else "Raw", 2),
                "par_sport": par(lambda v: v.get("sport")),
                "par_canal": par(lambda v: v.get("canal")),
                "par_joueur": [x for x in par(lambda v: v.get("joueur"), 40) if x["nom"] != "Autre"][:8],
                "meilleures": [court(v) for v in tri[:5] if (_float(v.get("profit")) or 0) > 0],
                "pertes": [court(v) for v in reversed(tri[-5:]) if (_float(v.get("profit")) or 0) < 0],
                "liste": [court(v) for v in l[:500]], "total_liste": len(l)}

    def bilan_csv(self, mois=None):
        mois = mois or datetime.now().strftime("%Y-%m")
        s = io.StringIO()
        w = csv.writer(s)
        w.writerow(["Date", "Canal", "Description", "Revenu", "Frais", "Coût", "Profit"])
        with _verrou:
            c = self._db()
            try:
                for v in c.execute("SELECT * FROM cartes WHERE statut='Vendue' AND substr(vendu_le,1,7)=? ORDER BY vendu_le", (mois,)):
                    w.writerow([v["vendu_le"][:10], v["canal"], v["titre"], v["prix_vendu"], v["frais"], v["cout"], v["profit"]])
                # 4 nov 2026 (revue) : les ventes au comptoir sans fiche (une ligne ecrite a la main) comptent aussi
                for vc in c.execute("SELECT le, lignes FROM ventes_comptoir WHERE substr(le,1,7)=? ORDER BY le", (mois,)):
                    try:
                        lg = json.loads(vc["lignes"] or "[]")
                    except ValueError:
                        lg = []
                    for l in lg:
                        if not l.get("carte_id") and _float(l.get("prix")) is not None:
                            w.writerow([str(vc["le"])[:10], "Magasin", l.get("description") or "Vente au comptoir", _float(l["prix"]), 0, "", _float(l["prix"])])
                for d in c.execute("SELECT * FROM depenses WHERE substr(le,1,7)=?", (mois,)):
                    w.writerow([d["le"], "Dépense", f"{d['categorie']} {d['note'] or ''}".strip(), "", "", d["montant"], -d["montant"]])
            finally:
                c.close()
        for b in self.breaks_liste():
            if str(b["cree_le"] or "")[:7] == mois:
                w.writerow([b["cree_le"][:10], "Break", b["nom"], b["revenus"], b["frais"], b["cout"], b["profit"]])
        return {"ok": True, "csv": s.getvalue(), "nom": f"bilan_{mois}.csv"}

    # -- accueil --------------------------------------------------------------------------------------
    def tableau_bord(self):
        b = self.bilan()
        with _verrou:
            c = self._db()
            try:
                stock = c.execute("SELECT COUNT(*), COALESCE(SUM(COALESCE(valeur, prix_demande, cout, 0)),0), COALESCE(SUM(cout),0) "
                                  "FROM cartes WHERE statut!='Vendue'").fetchone()
                a_lister = c.execute("SELECT COUNT(*) FROM cartes WHERE statut='En stock' AND COALESCE(emplacement,'') NOT IN ('Magasin','Collection')").fetchone()[0]
            finally:
                c.close()
        brk = self.breaks_liste()
        return {"mois": b, "stock": {"nb": stock[0], "valeur": round(stock[1], 2), "cout": round(stock[2], 2)},
                "a_lister": a_lister,
                "breaks_ouverts": [x for x in brk if x["statut"] != "ferme"][:5],
                "a_envoyer": sum(x["a_envoyer"] for x in brk),
                "consignation_du": round(sum(k["du"] for k in self.consignataires_liste()), 2),
                "nom_boutique": self.reglages_lire()["nom_boutique"]}


    # -- accueil « faire de l'argent » (22 oct 2026) ----------------------------------------------
    # Etudes dashboard : 3-5 chiffres en haut, chacun avec sa comparaison ; puis les actions
    # classees par $ ; le detail est un tap plus loin. Un vendeur veut savoir : combien je fais,
    # est-ce mieux qu'avant, et quoi faire MAINTENANT pour en faire plus.
    def _serie_profit(self, c, mois):
        """Profit cumule jour par jour du mois (cartes vendues + breaks - depenses)."""
        jours = {}
        for d, p in c.execute("SELECT substr(vendu_le,9,2), SUM(COALESCE(profit,0)) FROM cartes WHERE statut='Vendue' "
                              "AND substr(vendu_le,1,7)=? GROUP BY 1", (mois,)):
            jours[int(d or 1)] = jours.get(int(d or 1), 0) + (p or 0)
        for d, m in c.execute("SELECT substr(le,9,2), SUM(montant) FROM depenses WHERE substr(le,1,7)=? GROUP BY 1", (mois,)):
            jours[int(d or 1)] = jours.get(int(d or 1), 0) - (m or 0)
        return jours

    def activites(self):
        """Onglets a montrer : ce que le vendeur fait vraiment (reglage, sinon deduit de ses donnees)."""
        r = self.reglages_lire().get("activites")
        if isinstance(r, dict):
            return {"breaks": bool(r.get("breaks")), "magasin": bool(r.get("magasin"))}
        with _verrou:
            c = self._db()
            try:
                brk = c.execute("SELECT COUNT(*) FROM breaks").fetchone()[0]
                mag = c.execute("SELECT (SELECT COUNT(*) FROM ventes_comptoir) + (SELECT COUNT(*) FROM rachats) "
                                "+ (SELECT COUNT(*) FROM consignataires) + (SELECT COUNT(*) FROM clients)").fetchone()[0]
            finally:
                c.close()
        return {"breaks": brk > 0, "magasin": mag > 0}

    # -- 22 oct 2026 (Mathieu : « la meme app, tu choisis l'option vendeur ou acheteur pour separer
    # les fonctions et alleger le tout ; ca doit etre sexy et simple ») - volet ACHETEUR ------------
    # -- 23 oct 2026 : accueil « plein controle » (nouvelles + pouls des mises a jour), repris de Hall of Cardz --
    def accueil_live(self, langue=None):
        import nouvelles
        try:
            nouvelles.rafraichir_si_besoin()
        except Exception:
            pass
        r = self.reglages_lire()
        principal = sports.valide(r.get("sport"))
        with _verrou:
            c = self._db()
            try:
                lignes = _dicts(c.execute("SELECT titre, joueur, equipe, set_nom, marque, sport FROM cartes "
                                          "WHERE statut!='Vendue' ORDER BY id DESC LIMIT 1500"))
                sante_maj = (c.execute("SELECT MAX(maj) FROM sante").fetchone() or [None])[0]
                opp_maj = (c.execute("SELECT MAX(vu_le) FROM opportunites").fetchone() or [None])[0]
            finally:
                c.close()
        compte = {}
        joueurs = []
        for k in lignes:
            sp = k.get("sport") or sports.detecter(k.get("titre"), k.get("equipe"), k.get("set_nom"), k.get("marque"), defaut=principal)
            compte[sp] = compte.get(sp, 0) + 1
            if k.get("joueur") and k["joueur"] not in joueurs:
                joueurs.append(k["joueur"])
        ordre = sorted(compte, key=lambda x: -compte[x])
        if principal not in ordre:
            ordre.insert(0, principal)
        lg = langue if langue in ("fr", "en") else (r.get("langue") or "fr")
        try:                                     # les nouvelles ne doivent jamais bloquer l'accueil
            n = nouvelles.pour(ordre[:3], joueurs[:300], langue=lg)
        except Exception as e:
            print("Nouvelles accueil : " + repr(e), flush=True)
            n = {"items": [], "maj": None}
        st = ebay_compte.statut()
        pouls = []
        if st.get("connecte"):
            pouls.append({"id": "ebay", "nom": "eBay", "dernier": st.get("derniere_synchro"), "freq_min": 60,
                          "href": "#reglages", "note": "annonces, ventes, frais"})
        if st.get("cles_ok"):
            pouls.append({"id": "sante", "nom": "Tes prix", "dernier": sante_maj, "freq_min": 60, "href": "#sante"})
            pouls.append({"id": "deals", "nom": "Deals", "dernier": opp_maj, "freq_min": 60, "href": "#deals"})
        auto = True                              # 27 oct 2026 : recalculees chaque jour depuis les ventes SoldComps
        pouls.append({"id": "valeurs", "nom": "Joueurs", "dernier": valeurs.statut().get("maj"), "freq_min": 1440 if auto else 10080,
                      "href": "#reglages", "note": "chaque jour" if auto else "chaque semaine"})
        pouls.append({"id": "nouvelles", "nom": "Infos", "dernier": n.get("maj"), "freq_min": 120, "href": "#accueil"})
        for p in pouls:
            p["dernier"] = str(p["dernier"])[:19] if p.get("dernier") else None
        return {"ok": True, "nouvelles": n["items"], "sports": ordre[:3], "pouls": pouls,
                "maintenant": datetime.now().isoformat(timespec="seconds")}

    # -- deals (24 oct 2026) : les tiens (rachats de ce que tu as vendu) + ceux du chasseur partage (deals.py) --
    _ETIQ = {}
    _VAL_CACHE = {}

    @classmethod
    def _valeur_en_cache(cls, x, calculer=True):
        """30 oct 2026 (Mathieu : « les cartes de Savage n'ont pas de % ni de comps ») : un encan garde sans valeur prend
        celle des ventes deja connues de LA MEME carte (le cache des ventes : 3 jours, aucun credit). -> (valeur, n) | None.
        Garde 15 min par annonce."""
        import deals as _dl
        import vendues
        k = str(x.get("item_id"))
        e = cls._VAL_CACHE.get(k)
        if e and time.time() - e[0] < cls.VAL_CACHE_S:
            return e[1]
        if not calculer:
            # 4 nov 2026 (vitesse) : perimee -> l'ancienne valeur tout de suite (recalculee en fond par l'appelant)
            return e[1] if e else None
        r = None
        try:
            cib = cartes_match.cible_titre(x.get("titre") or "")
            q = (cartes_match.requete_ebay(cib) or "").strip()
            v = vendues.en_cache(q) if q else None
            if v:
                va = _dl.valeur_ou_saison({"titre": x.get("titre"), "item_id": k}, v, [], cib=cib)
                if va:
                    r = (va[0], va[2])
        except Exception:
            r = None
        if len(cls._VAL_CACHE) > 20000:                  # la plus vieille moitie, pas tout d'un coup
            for z in list(cls._VAL_CACHE)[:10000]:
                cls._VAL_CACHE.pop(z, None)
        cls._VAL_CACHE[k] = (time.time(), r)
        return r

    # 31 oct 2026 (Mathieu : « Server error » sur Deals, « tres tres lent ») : l'ecran Deals calculait la valeur de CHAQUE encan
    # suivi sans valeur (jusqu'a 2 500) pendant la requete : 18 s sur un ordinateur rapide, plus d'une minute sur Render,
    # et la requete tombait. Maintenant : au plus VAL_BUDGET_S de calcul par requete ; le reste se calcule en arriere-plan
    # (un seul fil, doucement) et apparait a la prochaine ouverture. Les valeurs sont gardees 1 h (ventes en cache : 3 jours).
    VAL_CACHE_S = 3600
    VAL_BUDGET_S = 0.2                 # 4 nov 2026 (vitesse) : le reste se calcule en fond
    _VAL_FIL = {"en_cours": False}

    @classmethod
    def _valeurs_en_fond(cls, items):
        if cls._VAL_FIL["en_cours"] or not items:
            return
        cls._VAL_FIL["en_cours"] = True

        def tache():
            try:
                for x in items:
                    cls._valeur_en_cache(x)
                    time.sleep(0.01)                     # laisse passer les ecrans des utilisateurs
            finally:
                cls._VAL_FIL["en_cours"] = False
        threading.Thread(target=tache, daemon=True, name="valeurs-suivis").start()

    @classmethod
    def _etiquette_deal(cls, titre, joueur=None):
        """« 2025-26 Tim Hortons Next Gen Phenoms Michael Misa #NG-7 San Jose » -> (« Michael Misa », « 2025-26 Tim Hortons
        Next Gen Phenoms »). Le joueur reconnu, sinon (None, titre)."""
        r = cls._ETIQ.get((titre, joueur))
        if r is None:
            j = cartes_match.joueur_du_titre(titre, joueur)
            if not joueur and j and (set(j.split()) & _MOTS_INSERTS or len(j.split()) < 2):
                j = _nom_majuscules(titre) or j            # 3 nov 2026 : « COSMIC », « BEAM » : un nom d'insert, pas un joueur
            cap = lambda w: re.sub(r"^(Mc|O')([a-z])", lambda m: m.group(1) + m.group(2).upper(), w.capitalize()) if len(w) > 3 else w.capitalize()
            nom = " ".join(cap(w) for w in j.split()) if j and len(j) < 40 else None
            reste = titre
            if nom:
                reste = re.sub(r"(?i)\b" + r"\s+".join(re.escape(w) for w in j.split()) + r"\b", " ", titre)
            reste = re.sub(r"#\s*\S+", " ", reste)
            if cartes_match._EQUIPES_MOTS["t"] is None:
                cartes_match._EQUIPES_MOTS["t"] = cartes_match._mots_equipes()
            eq = cartes_match._EQUIPES_MOTS["t"] | {"st.", "st"}
            mots = re.sub(r"\s+", " ", reste).strip(" -·,").split()
            while len(mots) > 2 and cartes_match.norm(mots[-1]) in eq:     # l'equipe en fin de titre (San Jose Sharks)
                mots.pop()
            reste = " ".join(mots)
            r = cls._ETIQ[(titre, joueur)] = (nom, reste[:60])
            if len(cls._ETIQ) > 20000:
                cls._ETIQ.clear()
        return r

    @staticmethod
    def _ramasser(x, chez):
        """30 oct 2026 (Mathieu : « Remi, Savage et CF31, je peux aller pick up sur place ») : chez un vendeur ou
        l'utilisateur ramasse, le port ne compte pas : prix, rabais et mise max sans livraison."""
        if not chez or str(x.get("vendeur") or "").lower() not in chez:
            return x
        port = float(x.get("port") or 0)
        y = dict(x, ramassage=True, port=0.0)
        if port:
            y["total"] = round(max(0.0, (x.get("total") or 0) - port), 2)
            if y.get("valeur"):
                y["ratio"] = round(y["total"] / y["valeur"], 3)
            if y.get("mise_max") is not None:
                y["mise_max"] = round(y["mise_max"] + port, 2)
        return y

    def _chez_ramassage(self):
        return {str(v).strip().lower() for v in (self.reglages_lire().get("ramassage") or []) if str(v).strip()}

    def _deals_fusion(self):
        import deals
        try:
            deals.chasser_si_besoin()
        except Exception:
            pass
        r = self.reglages_lire()
        fp, ff = (r["frais_ebay_pct"] or 0) / 100, r["frais_ebay_fixe"] or 0
        pays = str(r.get("pays") or "CA").upper()
        pays = pays if pays in deals.PAYS else "CA"
        limite = (datetime.now() - timedelta(days=4)).isoformat()
        with _verrou:
            c = self._db()
            try:
                c.execute("CREATE TABLE IF NOT EXISTS deals_masques (item_id TEXT PRIMARY KEY)")
                masques = {x[0] for x in c.execute("SELECT item_id FROM deals_masques")}
                # 26 oct 2026 (Mathieu : « les faux deals sont encore presents ?? ») : les « rachats » (une annonce comparee a
                # TA vente d'avant, pas aux ventes eBay de la meme carte) ne sont plus des deals : ils restent dans Sante
                opps = []
            finally:
                c.close()
        out = {}
        for o in opps:
            out[o["item_id"]] = {"item_id": o["item_id"], "titre": o["titre"], "total": o["total"], "photo": o.get("photo"), "url": o["url"],
                                 "valeur": o.get("ref_prix"), "ratio": o.get("ratio") or 1, "encan": False, "fin": None, "vu_le": o.get("vu_le"),
                                 "sport": sports.detecter(o.get("titre"), defaut=r.get("sport") or sports.DEFAUT), "source": "ventes",
                                 "comps": json.loads(o["comps"]) if o.get("comps") else [], "ref_titre": o.get("ref_titre")}
        maint_utc = datetime.utcnow().isoformat()
        for g in deals.lire_vite().get("deals") or []:
            if not deals.valide(g):
                continue
            if g.get("encan") and not (maint_utc < str(g.get("fin") or "").replace("Z", "") and deals.encan_admis(g)):
                continue                       # fini, trop loin (7 nov : 24 h, 5 jours chez Savage, Remi, CF31) ou sans mise
            out.setdefault(g["item_id"], {**g, "source": "marche"})
        lst = []
        chez = self._chez_ramassage()
        for x in out.values():
            if x["item_id"] in masques:
                continue
            x = self._ramasser(x, chez)
            x["_pays"] = pays                     # 9 nov 2026 : taxes et douanes du pays de l'acheteur
            # 26 oct 2026 : « −96 % » sur une carte a prix fixe = presque toujours une autre carte (pas la meme parallele,
            # pas le patch) : trop beau pour etre vrai, on ne le montre pas
            if not x.get("encan") and (x.get("ratio") or 1) < (0.25 if (x.get("valeur") or 0) >= 400 else 0.15):
                continue                     # 5 nov 2026 (Fantilli Signature Materials a 253 $ « vaut 1 393 $ ») : une carte de 400 $+
                                             # a prix fixe sous 25 % de sa valeur, c'est presque toujours une autre carte
            x["gain"] = round(_net_rev(x.get("valeur") or 0) - _paye(x.get("total") or 0, x), 2)
            x["taxe_achat"] = deals.taxe_de(x)                 # 8 nov 2026 : l'ecran compte les memes frais (importation)
            if not x.get("encan") and x["gain"] <= 1:          # 26 oct 2026 : pas de profit apres les frais : pas un deal
                continue
            x["rabais"] = round(100 * (1 - (x.get("ratio") or 1)))
            lst.append(x)
        return lst

    @staticmethod
    def _gain_affiche(x, fp=None, ff=None):
        """Le profit que l'ecran affiche : un encan, a la mise max (port compris) ; un prix fixe, au prix demande."""
        if x.get("encan") and x.get("mise_max") is not None and x.get("valeur") and fp is not None:
            import deals as _dlg
            return _net_rev(x["valeur"]) - _paye(float(x["mise_max"]) + _dlg.port_eff(x.get("port")), x)
        return x.get("gain") or 0

    @staticmethod
    def _deals_filtrer(lst, f):
        """prix_min / prix_max (total, $ CA), rabais_min (%), gain_min ($), valeur_min ($), joueurs [..] (un des noms),
        sortes [recrue, auto, patch, numerotee, gradee, brute] (toutes demandees), avec_mise (encans avec au moins 1 mise)."""
        n = lambda k: _float(f.get(k))
        pmin, pmax, rmin, gmin, vmin = n("prix_min"), n("prix_max"), n("rabais_min"), n("gain_min"), n("valeur_min")
        joueurs = [cartes_match.norm(j) for j in (f.get("joueurs") or []) if str(j).strip()][:20]
        sortes = [x for x in (f.get("sortes") or []) if x in ("recrue", "auto", "patch", "numerotee", "gradee", "brute", "veteran", "hit")]
        # 9 nov 2026 (Mathieu : « dans nos filtres, ne pas mettre un pays x ou y ») : les pays de provenance exclus
        exclus = {str(p_).upper()[:2] for p_ in (f.get("pays_exclus") or []) if re.fullmatch(r"[A-Za-z]{2}", str(p_ or ""))}
        out = []
        for x in lst:
            if exclus and str(x.get("lieu") or "").upper()[:2] in exclus:
                continue
            if pmin is not None and (x.get("total") or 0) < pmin or pmax is not None and (x.get("total") or 0) > pmax:
                continue
            if rmin is not None and (x.get("rabais") or 0) < rmin:
                continue
            if gmin is not None and Api._gain_affiche(x, f.get("_fp"), f.get("_ff")) < gmin:
                continue
            if vmin is not None and (x.get("valeur") or 0) < vmin:
                continue
            if f.get("avec_mise") and x.get("encan") and not x.get("mises"):
                continue
            t = cartes_match.norm(x.get("titre") or "")
            if joueurs and not any(j in t or j.split()[-1] in t.split() for j in joueurs):
                continue
            if sortes:
                d = cartes_match._decoder_memo(x.get("titre") or "")
                a = {"recrue": bool(d.get("rc")) or "young guns" in t or "rookie" in t, "auto": bool(d.get("auto")),
                     "patch": bool(d.get("patch")), "numerotee": d.get("serie") is not None, "gradee": bool(d.get("grade")),
                     "brute": not d.get("grade")}
                # 28 oct 2026 (Mathieu : « encore que des rookies ») : veterans / legendes (pas une recrue) et hits
                # 29 oct 2026 (« pas juste des rookies premiere annee ») : une RC vintage de legende ou une Young Guns de
                # 2023-24 (joueur de 3e/4e annee) compte comme veteran / legende ; seulement les recrues de l'annee n'y sont pas
                import deals as _dlr
                a["veteran"] = not _dlr.recrue_recente(t, d.get("rc"), d.get("annee"))
                a["hit"] = a["auto"] or a["patch"] or (d.get("serie") is not None and int(d["serie"]) <= 99)
                if not all(a[s_] for s_ in sortes):
                    continue
            out.append(x)
        return out

    def deals_liste(self, f=None):
        def _ts(v):
            try:
                return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
            except ValueError:
                return 0.0
        """Filtres : sports [..], type fixe|encan, tri rabais|fin|prix|gain|recent. Gratuit : les 5 meilleurs."""
        import forfaits
        f = f or {}
        if not ebay_prix_actif():
            return {"ok": True, "deals": [], "pres": [], "n": 0, "total": 0, "pro": forfaits.est_pro(), "limite": None,
                    "secours": False, "sports": {}, "coupe": True}
        import deals as _dl
        # 27 oct 2026 (revue) : verifie AUSSI a la lecture (meme si le chasseur est en panne) : vu il y a 6 h au plus, encan pas fini
        lim_l = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
        tout = [x for x in self._deals_fusion() if _dl.encore_ouvert(x) and (x.get("source") != "marche" or str(x.get("vu_le") or "") >= lim_l)]
        # 6 nov 2026 (Mathieu : « mettre a jour les max bid au plus vite ») : la mise max de chaque deal refaite a la lecture
        # avec la regle d'aujourd'hui (30 % de profit net) ; un prix fixe qui ne laisse plus ce profit n'est plus un deal
        tout = [_dl.a_jour(x) for x in tout if _dl.encan_admis(x)]        # 7 nov : 24 h et une mise (sauf Savage, Remi, CF31)
        rg = self.reglages_lire()
        pays = str(rg.get("pays") or "CA").upper()
        pays = pays if pays in _dl.PAYS else "CA"
        tout = [x for x in tout if x.get("encan") or not (x.get("valeur") and x.get("total") and x["total"] > _dl.prix_max(x["valeur"], taxe=_dl.taxe_de(x)))]
        # 2 nov 2026 (Mathieu : « quand le prix suggere est depasse par le bid actuel, ce n'est plus un deal, il ne devrait plus
        # etre la ») : la mise du moment (hors port) au-dessus de la mise max -> hors des deals, tout de suite a la lecture
        tout = [x for x in tout if not (x.get("encan") and x.get("mise_max") is not None and x.get("total")
                                        and float(x["total"]) - float(x.get("port") or 0) > float(x["mise_max"]) + 0.5)]
        fp_, ff_ = (rg["frais_ebay_pct"] or 0) / 100, rg["frais_ebay_fixe"] or 0
        # 4 nov 2026 (Mathieu : « pourquoi je vois encore les cartes en bas du montant du filtre ») : le profit minimum d'un
        # encan se compare au profit AFFICHE (a la mise max), pas a celui de la mise du moment (1 $ : toujours enorme)
        f = dict(f, _fp=fp_, _ff=ff_)
        # 8 nov 2026 (Mathieu : « prioriser les deals canadiens pour un Canadien et americains pour un Americain, a cause des
        # tarifs douaniers ») : les taxes et frais d'importation de SON pays, et la mise max qui va avec
        for x in tout:
            x["_pays"] = pays
            x["etranger"] = _dl.etranger(x)
            if pays != "CA" and x.get("encan") and x.get("valeur") and not x.get("mise_perso"):
                x["mise_max"] = round(_dl.prix_max(x["valeur"], taxe=_dl.taxe_de(x)) - _dl.port_eff(x.get("port")), 2)
            x["taxe_achat"] = _dl.taxe_de(x)
        for x in tout:
            if x.get("valeur") and x.get("total") is not None:
                x["gain"] = round(_net_rev(x["valeur"]) - _paye(x.get("total") or 0, x), 2)
                x["rabais"] = round(100 * (1 - (x.get("total") or 0) / x["valeur"]))
        par_sport = {}
        for x in tout:
            par_sport[x.get("sport") or "hockey"] = par_sport.get(x.get("sport") or "hockey", 0) + 1
        par_pays = {}                                     # 9 nov 2026 : les pays de provenance (le filtre « pas ce pays »)
        for x in tout:
            p_ = str(x.get("lieu") or "").upper()[:2]
            if re.fullmatch(r"[A-Z]{2}", p_):
                par_pays[p_] = par_pays.get(p_, 0) + 1
        lst = [x for x in tout if not f.get("sports") or (x.get("sport") or "hockey") in f["sports"]]
        if f.get("type") == "fixe":
            lst = [x for x in lst if not x.get("encan")]
        elif f.get("type") == "encan":
            lst = [x for x in lst if x.get("encan")]
        # 25 oct 2026 (Mathieu : « une option de tri/filtre pour que l'utilisateur puisse customizer ses deals »)
        lst = self._deals_filtrer(lst, f)
        lst = self._avec_chances(lst)
        if f.get("vendeurs"):                     # 29 oct 2026 : « tous les deals des gros vendeurs »
            lst = [x for x in lst if x.get("flux") == "vendeurs"]
        tri = f.get("tri") or "rabais"
        # 26 oct 2026 (Mathieu : « ca ne fonctionne pas quand je selectionne biggest profit, price, ending soon ») : un
        # commentaire avalait les tris « prix » et « gain » (tout retombait sur « meilleur deal »)
        cles = {"rabais": lambda x: (1 if x.get("encan") else 0, x.get("ratio") or 1),     # prix fixe d'abord : la mise d'un encan monte
                "prix": lambda x: (x.get("total") or 0, x.get("ratio") or 1),
                "gain": lambda x: (-Api._gain_affiche(x, fp_, ff_), x.get("ratio") or 1),       # le profit affiche
                "recent": lambda x: str(x.get("vu_le") or ""),
                "fin": lambda x: (0, str(x.get("fin")), 0) if x.get("encan") else (1, "", -_ts(x.get("vu_le")))}
        lst.sort(key=cles.get(tri, cles["rabais"]), reverse=(tri == "recent"))
        if tri == "rabais" and not f.get("sortes") and not f.get("joueurs"):
            lst = _dl.melanger(lst)                # 28 oct 2026 : pas un mur de Young Guns
        if tri == "rabais":
            # 29 oct 2026 (Mathieu : « as-tu priorise les vendeurs qu'on a mentionnes, et apres le reste ? ») : leurs deals d'abord
            # 30 oct 2026 : Savage, Remi, CF31, Slab Sharks, puis les autres vendeurs suivis, puis le reste
            lst = sorted(lst, key=lambda x: _dl.rang_vendeur(x.get("vendeur")) if x.get("flux") == "vendeurs" else 6)
        # 2 nov 2026 (Mathieu : « favoriser les places honnetes et les petits vendeurs ; Probstein et DC Sports en dernier ») :
        # dans chaque tri, les petits vendeurs d'abord, les maisons a volume a la toute fin (l'ordre du tri est garde a
        # l'interieur de chaque groupe)
        if tri in ("rabais", "gain"):
            lst = sorted(lst, key=lambda x: (_dl.rang_honnete(x) == 3, _dl.rang_honnete(x) if not (x.get("flux") == "vendeurs" and _dl.rang_vendeur(x.get("vendeur")) <= 3) else 0))
        else:
            lst = sorted(lst, key=lambda x: _dl.rang_honnete(x) == 3)
        for x in lst:
            x["recrue"] = _dl.est_recrue(x.get("titre"))
        if tri == "rabais" and not f.get("sortes"):
            # 31 oct 2026 (Mathieu : « je mets plus gros profit et je me retrouve avec des gros profits dans le bas ») :
            # en « profit » et en « prix », un seul classement, tout melange ; les veterans d'abord : le tri par defaut seulement
            # 29 oct 2026 (Mathieu : « encore que des caliss de rookies dans tes deals ») : veterans, legendes et jeunes de
            # 2e a 4e annee d'abord (hits compris) ; les recrues de l'annee ensuite (le chip « Recrues » les montre seules)
            lst = [x for x in lst if not x["recrue"]] + [x for x in lst if x["recrue"]]
        elif tri in ("fin", "recent") and not f.get("sortes") and not f.get("joueurs"):
            # 3 nov 2026 (Mathieu : « que des rookies ou Young Guns dans les deals... ENCORE », en « Finit bientot ») : en
            # « finit bientot » et « nouveaux » aussi (pas en profit ni en prix : la, un seul classement, comme demande), une recrue de l'annee n'en suit jamais une autre tant qu'il reste un veteran ou une legende
            # (l'ordre du tri est garde dans chaque groupe ; les maisons a volume restent a la fin)
            def entrelacer(l):
                v, r, out = [x for x in l if not x["recrue"]], [x for x in l if x["recrue"]], []
                while v or r:
                    if v:
                        out.append(v.pop(0))
                    if r:
                        out.append(r.pop(0))
                return out
            fin = [x for x in lst if _dl.rang_honnete(x) == 3]
            # 3 nov 2026 (revue) : en « finit bientot », les encans restent devant les prix fixes (entrelaces chacun de son cote)
            par = (lambda l: entrelacer([x for x in l if x.get("encan")]) + entrelacer([x for x in l if not x.get("encan")])) if tri == "fin" else entrelacer
            lst = par([x for x in lst if _dl.rang_honnete(x) != 3]) + par(fin)
        if tri in ("rabais", "gain", "recent"):
            lst = [x for x in lst if not x.get("etranger")] + [x for x in lst if x.get("etranger")]    # 8 nov : son pays d'abord
        prof = self._profil_deals()                      # 30 oct 2026 : mon profil de deals (Reglages)
        lst = self._appliquer_profil(lst, prof)
        if tri == "rabais":
            lst = self._varier_deals(lst)                # 9 nov 2026 : chacun son ordre (et ses joueurs a lui d'abord)
        lst = self._objectif_deals(lst, f)
        n = len(lst)
        pro = forfaits.est_pro()
        if not pro:
            lst = lst[:forfaits.LIMITES["deals"]]
        import deals as _d
        # 27 oct 2026 (Mathieu : « les users doivent TOUJOURS voir quelque chose, sinon ils vont decrocher ») :
        #   - pas de deal en ce moment : la derniere bonne liste (secours), encore fraiche (6 h) et revalidee ;
        #   - « a surveiller » : 15 a 30 % sous la valeur (meme valeur sure), jamais affiche comme un deal.
        dd = _d.lire_vite()
        secours = False
        if not tout and (dd.get("secours") or {}).get("deals"):
            lim6 = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
            ret = dd.get("retires") or {}            # 27 oct 2026 (revue) : ni vendu / retire, ni encan fini
            sec = [dict(x, source="marche") for x in dd["secours"]["deals"] if str(x.get("vu_le") or "") >= lim6 and _d.valide(x)
                   and str(x.get("item_id")) not in ret and _d.encore_ouvert(x)]
            for x in sec:
                x["gain"] = round(_net_rev(x.get("valeur") or 0) - _paye(x.get("total") or 0, x), 2)
                x["rabais"] = round(100 * (1 - (x.get("ratio") or 1)))
            sec = [x for x in self._deals_filtrer(sec, f) if x.get("encan") or x["gain"] > 1]
            if sec:
                lst, n, secours = sec, len(sec), True
                if not pro:
                    lst = lst[:forfaits.LIMITES["deals"]]
        pres = []
        ret_p = dd.get("retires") or {}
        for x in dd.get("pres") or []:
            if str(x.get("item_id")) in _d._bannis() or str(x.get("item_id")) in ret_p or not _d.encore_ouvert(x) or not _d.encan_admis(x):
                continue
            x = _dl.a_jour(x)
            y = dict(x, source="marche", gain=round(_net_rev(x.get("valeur") or 0) - _paye(x.get("total") or 0, x), 2),
                     rabais=round(100 * (1 - (x.get("ratio") or 1))))
            pres.append(y)
        pres = self._appliquer_profil([x for x in self._deals_filtrer(pres, f) if not f.get("sports") or (x.get("sport") or "hockey") in f["sports"]], prof)[:24 if pro else 6]
        # 29 oct 2026 (Mathieu : « je ne vois toujours pas les cartes non rookie ») : les encans de veterans et de legendes
        # des vendeurs suivis (Savage, Remi, Slab Sharks...), meme sans valeur verifiee ; jamais montres comme un deal
        ids_d = {str(x.get("item_id")) for x in lst}
        lim_s = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
        suivis, chez_s = [], self._chez_ramassage()
        fin_calcul, plus_tard = time.time() + self.VAL_BUDGET_S, []
        for x in dd.get("suivis") or []:
            if str(x.get("item_id")) in ids_d or str(x.get("item_id")) in ret_p or str(x.get("item_id")) in _d._bannis() \
                    or not _d.encore_ouvert(x) or not _d.encan_admis(x) or str(x.get("vu_le") or "") < lim_s:
                continue
            if not x.get("valeur"):
                vc = self._valeur_en_cache(x, calculer=time.time() < fin_calcul)
                e_ = self._VAL_CACHE.get(str(x.get("item_id")))
                if not e_ or time.time() - e_[0] >= self.VAL_CACHE_S:      # absente ou perimee : en fond
                    plus_tard.append(x)
                if vc:
                    x = dict(x, valeur=vc[0], n=vc[1], mise_max=round(_dl.prix_max(vc[0], taxe=_dl.taxe_de(x)) - _dl.port_eff(x.get("port")), 2))
            y = self._ramasser(dict(_dl.a_jour(x), source="marche", recrue=bool(x.get("recrue"))), chez_s)
            # 5 nov 2026 (Mathieu : « il doit toujours y avoir une analyse si elle est dans les deals ») : un encan sans valeur
            # (ses ventes se calculent en fond) n'est pas montre ; il arrive dans les deals des que sa valeur est connue
            if not y.get("valeur"):
                continue
            if y.get("valeur"):
                y["gain"] = round(_net_rev(y["valeur"]) - _paye(y.get("total") or 0, y), 2)
                y["taxe_achat"] = _dl.taxe_de(y)
                y["rabais"] = round(100 * (1 - (y.get("total") or 0) / y["valeur"]))
                # 31 oct 2026 (Mathieu : « se faire retirer du dashboard si ce n'est plus un deal ») : valeur connue et mise
                # au-dessus de 70 % de celle-ci -> pas un deal : hors de l'ecran Deals (la watchlist, elle, le montre en rouge)
                if (y.get("total") or 0) > _dl.prix_max(y["valeur"], taxe=_dl.taxe_de(y)):
                    continue
            suivis.append(y)
        self._valeurs_en_fond(plus_tard)
        # 31 oct 2026 (Mathieu : « assure-toi que le filtre fonctionne lorsqu'applique ») : TOUS les filtres s'appliquent aussi
        # aux encans des gros vendeurs : rabais minimum (un encan sans valeur verifiee n'a pas de rabais -> cache), une mise
        # au moins, prix fixe seulement (-> aucun encan)
        f_s = {k: v for k, v in f.items() if k in ("joueurs", "sortes", "prix_min", "prix_max", "rabais_min", "avec_mise", "gain_min", "_fp", "_ff")}
        if _float(f.get("rabais_min")) or _float(f.get("gain_min")):
            suivis = [x for x in suivis if x.get("valeur")]
        if f.get("type") == "fixe":
            suivis = []
        suivis = [x for x in self._deals_filtrer(suivis, f_s) if not f.get("sports") or (x.get("sport") or "hockey") in f["sports"]]
        suivis = self._avec_chances(suivis)
        suivis.sort(key=lambda x: (0 if (x.get("sport") or "hockey") == "hockey" else 1, _dl.rang_vendeur(x.get("vendeur")), str(x.get("fin"))))
        suivis = self._appliquer_profil(suivis, prof)
        suivis = self._objectif_deals(suivis, f)
        suivis = suivis[:_dl._env_int("LR_SUIVIS_ECRAN", 300) if pro else 6]
        # 30 oct 2026 (Mathieu : « l'etiquette du deal : le nom du joueur en haut, son % sous la mediane des dernieres ventes
        # et le prix actuel, comme ces slabs ») : le joueur et la carte, separes, pour l'etiquette
        for x in [*lst[:240], *suivis, *pres]:
            if "joueur_n" not in x:
                # 2 nov 2026 (« COSMIC » au lieu de LeBron James) : le joueur connu du deal d'abord, s'il est dans le titre
                jd = str(x.get("joueur") or "").strip()
                x["joueur_n"], x["carte_n"] = self._etiquette_deal(x.get("titre") or "", jd if jd and cartes_match.norm(jd) in cartes_match.norm(x.get("titre") or "") else None)
        # 31 oct 2026 (Mathieu : « les deals n'apparaissent pas au fur et a mesure, ca reste a 35 ») : un encan d'un gros vendeur
        # qui vient de recevoir sa valeur et qui est a 70 % ou moins de celle-ci est un deal : il compte dans le nombre
        n_su = sum(1 for x in suivis if x.get("valeur") and (x.get("total") or 0) <= _dl.prix_max(x["valeur"], taxe=_dl.taxe_de(x)))
        return {"ok": True, "deals": lst[:240], "n": n + n_su, "n_encans_valorises": n_su, "pro": pro, "limite": None if pro else forfaits.LIMITES["deals"],
                "suivis": suivis,
                "pres": pres, "secours": secours, "secours_le": (dd.get("secours") or {}).get("le") if secours else None,
                "sports": par_sport, "pays_dispo": par_pays, "maj": dd.get("maj"), "ebay": ebay_compte.statut().get("cles_ok"),
                "diag": _d.diagnostic(dd), "total": len(tout), "bassin": dd.get("bassin"), "nb_flux": len(_d.flux_liste()),
                "watch": self._watch_ids()}

    @staticmethod
    def _avec_chances(lst):
        """5 nov 2026 (Mathieu : « je perds mon temps a miser sur des cartes qui montent en fou ; subtilement ») : un encan
        dont le genre finit presque toujours au-dessus de la mise max n'est pas montre ; les autres gardent leur chance
        (une ligne dans la fiche). Rien ne change tant qu'on n'a pas assez d'encans finis (chances.py)."""
        try:
            import chances
        except Exception:
            return lst
        out = []
        for x in lst:
            if x.get("encan") and x.get("mise_max") is not None:
                c = chances.chance(x)
                if chances.a_cacher(x, c):
                    continue
                if c:
                    x = dict(x, chance={"p": c[0], "n": c[1], "niveau": c[2]})
            out.append(x)
        return out

    DESIR_COLLECTION = 45            # en mode collection : la carte doit etre au moins « recherchee » (score 45/100)
    REVENTE_VENTES_MIN = 4           # en mode revente : au moins 4 ventes reelles de la meme carte (elle se vend souvent)

    def _objectif_deals(self, lst, f):
        """31 oct 2026 (Mathieu : « la difference entre un inventaire a vendre rapidement et un inventaire de collection ») :
        revente = ce qui se revend vite (assez de ventes de la meme carte), le plus gros profit d'abord ;
        collection = ce qui est rare et recherche (score de desirabilite), le plus desirable d'abord. Sans objectif : tout,
        avec le score affiche."""
        import desirabilite
        obj = (f or {}).get("objectif") or ""
        out = []
        for x in lst:
            # le nombre de ventes de la meme carte qui ont servi a sa valeur (le chasseur les a deja comptees : rien a relire)
            nv = x.get("n") or len(x.get("vendues") or [])
            d = desirabilite.score(x.get("titre") or "", valeur=x.get("valeur"), ventes=nv if x.get("valeur") else None)
            y = dict(x, desir=d["score"], desir_raisons=d["raisons"])
            if obj == "collection" and d["score"] < self.DESIR_COLLECTION:
                continue
            if obj == "revente" and x.get("valeur") and (x.get("n") or 0) < self.REVENTE_VENTES_MIN:
                continue
            out.append(y)
        tri = (f or {}).get("tri") or "rabais"
        if obj == "collection" and tri == "rabais":
            out.sort(key=lambda x: -x["desir"])
        elif obj == "revente" and tri == "rabais":
            out.sort(key=lambda x: -(x.get("gain") or 0))
        return out

    def inventaire_tableaux(self):
        """31 oct 2026 : deux tableaux, deux facons de penser.
        A vendre : combien, ce que ca vaut, le temps reel pour vendre (tes ventes des 6 derniers mois), ce qui dort (60 j+).
        Collection : la valeur et son evolution (3, 6, 12 mois quand l'historique les couvre), les cartes les plus desirables,
        les plus fortes hausses (suivi de valeur)."""
        import desirabilite
        maint = datetime.now()
        with _verrou:
            c = self._db()
            try:
                dispo = _dicts(c.execute("SELECT * FROM cartes WHERE statut IN ('En stock','Listée')"))
                vendues = _dicts(c.execute("SELECT cree_le, vendu_le FROM cartes WHERE statut='Vendue' AND vendu_le >= ?",
                                           ((maint - timedelta(days=183)).strftime("%Y-%m-%d"),)))
                try:
                    hist = _dicts(c.execute("SELECT jour, valeur FROM valeur_historique ORDER BY jour"))
                except Exception:
                    hist = []
                try:
                    suivis = _dicts(c.execute("SELECT carte_id, reference, derniere FROM suivi_valeur WHERE actif=1 AND reference > 0 AND derniere > 0"))
                except Exception:
                    suivis = []
            finally:
                c.close()
        coll = [x for x in dispo if (x.get("emplacement") or "") == "Collection"]
        av = [x for x in dispo if (x.get("emplacement") or "") not in ("Collection",)]
        jours = []
        for x in vendues:
            try:
                d = (datetime.fromisoformat(str(x["vendu_le"])[:19]) - datetime.fromisoformat(str(x["cree_le"])[:19])).days
                if d >= 0:
                    jours.append(d)
            except (TypeError, ValueError):
                continue
        lim = (maint - timedelta(days=60)).isoformat()
        dorment = sorted((x for x in av if x.get("cree_le") and str(x["cree_le"]) < lim), key=lambda x: str(x["cree_le"]))
        vente = {"n": len(av), "valeur": round(sum((x.get("prix_demande") or x.get("valeur") or 0) for x in av), 2),
                 "delai_median": round(statistics.median(jours)) if len(jours) >= 3 else None, "n_vendues": len(jours),
                 "dorment": len(dorment), "dorment_ids": [x["id"] for x in dorment[:30]]}
        vente.update(popularite(av, maint))
        try:
            vente["analytics"] = ebay_compte.a_analytics()
        except Exception:
            vente["analytics"] = False
        var = {}
        if hist:
            der = hist[-1]
            for k, j in (("3m", 91), ("6m", 182), ("12m", 365)):
                ref = next((h for h in hist if h["jour"] >= (maint - timedelta(days=j)).strftime("%Y-%m-%d")), None)
                if ref and ref["valeur"] and (datetime.fromisoformat(der["jour"]) - datetime.fromisoformat(ref["jour"])).days >= j * 0.8:
                    var[k] = round(100 * (der["valeur"] / ref["valeur"] - 1), 1)
        scores = []
        for x in coll:
            vc = desirabilite.ventes_connues(x.get("titre") or "") if len(coll) <= 300 else None
            d = desirabilite.score(x.get("titre") or "", carte=x, ventes=vc[0] if vc else None, jours=vc[1] if vc else None)
            scores.append({"id": x["id"], "joueur": x.get("joueur") or x.get("titre"), "score": d["score"], "raisons": d["raisons"],
                           "valeur": x.get("valeur"), "photo": None})
        scores.sort(key=lambda s: -s["score"])
        par_id = {x["id"]: x for x in coll}
        hausses = sorted(({"id": s["carte_id"], "joueur": (par_id.get(s["carte_id"]) or {}).get("joueur"),
                           "pct": round(100 * (s["derniere"] / s["reference"] - 1))} for s in suivis if s["carte_id"] in par_id),
                         key=lambda h: -h["pct"])
        collection = {"n": len(coll), "valeur": round(sum((x.get("valeur") or 0) for x in coll), 2),
                      "cout": round(sum((x.get("cout") or 0) for x in coll), 2), "variation": var,
                      "desir_moyen": round(statistics.mean([s["score"] for s in scores])) if scores else None,
                      "top": scores[:3], "hausses": [h for h in hausses if h["pct"] > 0][:3]}
        return {"ok": True, "vente": vente, "collection": collection}

    def _watch_ids(self):
        try:
            import watchlist
            return watchlist.ids(self)
        except Exception:
            return []

    def annonce_detail(self, item_id, titre=None, rapide=False, q=None):
        """26 oct 2026 (Mathieu : « beaucoup trop long à charger ») : l'ecran demande d'abord la version rapide
        (annonce + memes cartes en vente, sans les ventes), puis la complete (+ ventes reelles) qui la remplace."""
        """24 oct 2026 (Mathieu : « comme Hall of Cardz, une fenetre dans l'app qui ouvre avec l'annonce eBay et les comps
        sous celle-ci avec leurs images ») : l'annonce (photos, prix, vendeur, fin) + les MEMES cartes en vente."""
        import cartes_match
        t0_ = time.time()
        a = None
        try:
            # 7 nov 2026 (Mathieu : « pourquoi les prix ne se mettent pas a jour quand je refresh ? ») : la fiche ouverte par
            # l'utilisateur relit l'annonce sur eBay (cache de 3 min au lieu d'une heure : la mise d'un encan bouge)
            a = ebay_compte.article(item_id, frais=True)
        except (RuntimeError, OSError) as e:
            a = {"item_id": str(item_id), "titre": titre or "", "photos": [], "erreur": str(e)}
        t = a.get("titre") or titre or ""
        if a.get("prix_cad") and a.get("port_cad") is None:     # 3 nov 2026 (revue) : port pas affiche -> estime, comme les deals
            import deals as _dlp
            a["port_cad"], a["port_estime"] = _dlp.PORT_INCONNU, True
        comps, med, n = [], None, 0
        if t:
            try:
                carte = cartes_match.est_carte(t)
                cib = cartes_match.cible_titre(t) if carte else None
                q = (cartes_match.requete_ebay(cib) if cib else None) or sante.requete(t)
                res = ebay_compte.rechercher(q, categorie=CATEGORIE_CARTES if carte else None, limite=100, fond=False)
                if carte:
                    _c, memes, _e = cartes_match.filtrer_carte(t, res, exclure_id=item_id)
                else:
                    memes = [x for x in res if str(x.get("item_id")) != str(item_id)]
                tot = lambda x: round((x.get("prix_cad") or 0) + (x.get("port_cad") or 0), 2)
                med, garde = cartes_match.mediane_robuste([tot(x) for x in memes])
                n = len(garde)
                comps = sorted(({"item_id": x["item_id"], "titre": x["titre"], "total": tot(x), "photo": x.get("photo"), "url": x.get("url"),
                                 "encan": x.get("encan"), "fin": x.get("fin")} for x in memes if x.get("prix_cad")),
                               key=lambda x: abs(x["total"] - (med or 0)))[:12]
            except (RuntimeError, OSError) as e:
                a.setdefault("erreur_comps", str(e))
        total = round((a.get("prix_cad") or 0) + (a.get("port_cad") or 0), 2) if a.get("prix_cad") else None
        # 2 nov 2026 (Mathieu : « le prix doit updater dans les 2 affichages ») : le prix lu en direct remplace celui du deal
        maj_deal = None
        if total and not a.get("erreur"):
            try:
                import deals as _dl0
                maj_deal = _dl0.maj_prix(item_id, total, a.get("port_cad"), a.get("mises"), a.get("fin"), achat_=_dl0.achat(a))
            except Exception as e:
                print("Deals (prix fiche) : " + repr(e), flush=True)
        r = self.reglages_lire()
        fp, ff = (r["frais_ebay_pct"] or 0) / 100, r["frais_ebay_fixe"] or 0
        if isinstance(a, dict) and str(r.get("pays") or "CA").upper() == "US":
            a = dict(a, _pays="US")                    # 9 nov 2026 : un acheteur aux Etats-Unis (taxes et douanes de son pays)
        # 25 oct 2026 (Mathieu : « montre les last sold comps avec leurs photos aussi et le prix suggere »)
        try:
            if rapide:
                # 8 nov 2026 (« accelerer la vitesse a laquelle on voit les comps ») : les ventes deja connues tout de suite
                # (cache et archives, aucun appel) ; la recherche fraiche suit et les remplace
                vc = dict(vendues.memes_cache(t, q=q) if t else {"ventes": []}, attente=True)
            else:                                          # 26 oct 2026 : les ventes de CETTE carte (pas de toute la recherche)
                vc = vendues.memes_annonce(t, q=q, n=16) if t else {"ventes": []}
        except Exception:
            vc = {"ventes": []}
        mes_achats, mes_ids, deja_achetee = self._mes_achats_titre(t, item_id) if t else ([], set(), False)
        if vc.get("ventes"):                   # 9 nov 2026 : tes achats ne sont jamais des comps (« tout sauf notre deal »)
            vc["ventes"], n_mes = self._sans_mes_achats(vc["ventes"], mes_achats, mes_ids)
            if n_mes:
                vc["nb"] = max(0, (vc.get("nb") or 0) - n_mes)
                vc["mes_retirees"] = n_mes
        ventes = vc.get("ventes") or (self._mes_ventes_pareilles(t, item_id) if t else [])
        # 25 oct 2026 : la valeur = les ventes reelles (3 ou plus), sinon les annonces en vente
        # 26 oct 2026 (Mathieu : « encore pas un deal » : 6 annonces a 21 $, 1 vente a 3 $) : les annonces sont un PLAFOND ;
        # 1 ou 2 ventes : on les croit plus que les prix demandes ; aucune vente : pas de verdict deal / bon prix
        nb_v = vc.get("nb") or 0
        # 27 oct 2026 : pas (ou presque pas) de ventes de CETTE carte : celles de la meme carte par d'autres joueurs, en repere
        autres = None
        # 7 nov 2026 (la fiche qui « reste a charger ») : les ventes d'autres joueurs (une recherche de plus) seulement s'il
        # reste du temps : la fiche doit revenir en moins de 30 s
        if not rapide and t and nb_v < 2 and time.time() - t0_ < 12:
            try:
                autres = vendues.autres_joueurs(t)
            except Exception:
                autres = None
        # 27 oct 2026 (Mathieu : « pas de faux deals ni de faux prix ») : une valeur SEULEMENT si les ventes reelles de
        # CETTE carte sont sures (deals.valeur_sure) ; les annonces ne font que la plafonner. Sinon : aucun « vaut ».
        import deals as _deals
        # 30 oct 2026 (Mathieu : « les comps n'ont toujours pas update ») : on dit POURQUOI il n'y a pas de valeur (aucune
        # vente trouvee, ventes trop vieilles, trop differentes...) au lieu d'un « pas assez de ventes » pour tout
        vs_ = _deals.valeur_sure([x for x in (vc.get("ventes") or []) if x.get("prix")], t or "") if nb_v >= 2 else (None, "pas assez de ventes")
        vm = vs_[0]
        # 7 nov 2026 (Mathieu : « utiliser l'API seulement pour les cartes sans comps de 3 mois ») : pas de valeur sure avec les
        # 90 jours d'eBay -> l'historique d'un an (CompSniper, budget du mois), une seule fois par carte (cache 14 jours)
        hist_ = []
        if not vm and not rapide and t and time.time() - t0_ < 18:
            try:
                import historique
                if historique.actif():
                    hist_ = historique.carte(t)
                    cib_h = cartes_match.cible_titre(t)
                    memes_h = [x for x in hist_ if x.get("prix") and not cartes_match.raisons_refus(cib_h, x.get("titre") or "")]
                    if memes_h:
                        vus_h = {str(x.get("url") or "") for x in ventes if x.get("url")}
                        tout_h = [x for x in (vc.get("ventes") or []) if x.get("prix")] + [x for x in memes_h if str(x.get("url") or "") not in vus_h]
                        vs_ = _deals.valeur_sure(tout_h, t)
                        vm = vs_[0]
                        ventes = sorted(tout_h, key=lambda x: str(x.get("le") or ""), reverse=True)[:16]
                        nb_v = len(tout_h)
            except Exception as e:
                print("Historique (fiche) : " + repr(e), flush=True)
        pourquoi = None if vm else (vc.get("erreur") or (vs_[1] if isinstance(vs_[1], str) else None))
        if vm and med and n >= 3:                 # 3 nov 2026 (revue) : le meme plafond que le chasseur (deals.valeur_annonce)
            vm = min(vm, round(med * 0.85, 2))
        valeur = vm
        juger = bool(vm)
        # 7 nov 2026 (Mathieu : « la Ron Francis : mettre les annees a cote pour la meme carte, montrer les cartes similaires
        # mais dire a l'utilisateur qu'il n'y a pas de comp ») : aucune vente sure de SA saison -> les saisons voisines
        saison_v = None
        if not vm and not rapide and t and not (vc.get("erreur_ebay") or vc.get("erreur")) and time.time() - t0_ < 22:
            try:
                saison_v = vendues.autres_saisons(t, extra=hist_)
            except Exception as e:
                print("Ventes (autres saisons) : " + repr(e), flush=True)
            if saison_v:
                valeur, juger = saison_v[0], True
                ventes = saison_v[3]
                pourquoi = None
        # 7 nov 2026 (« les no sales : analyser les cartes similaires et donner un prix approximatif ») : ensuite, les cartes
        # similaires du meme joueur (meme produit, autre numerotation / annee / parallele)
        if not vm and not saison_v and not rapide and t and not (vc.get("erreur_ebay") or vc.get("erreur")) and time.time() - t0_ < 22:
            try:
                saison_v = vendues.similaires(t, extra=hist_)
            except Exception as e:
                print("Ventes (similaires) : " + repr(e), flush=True)
            if saison_v:
                valeur, juger = saison_v[0], True
                ventes = saison_v[3]
                pourquoi = None
        suggere = None
        if saison_v:
            suggere = {"vente": valeur, "achat_max": round(max(0.0, _deals.prix_max(valeur, taxe=_deals.taxe_de(a))), 2), "source": saison_v[1]}
        elif valeur and (vm or n >= 3):
            pv = sorted(x["prix"] for x in ventes if x.get("prix")) if vm else sorted(x["total"] for x in comps)
            vente = pv[max(0, int(len(pv) * 0.6) - 1)] if len(pv) >= 3 else valeur     # vendues : un peu au-dessus du milieu
            suggere = {"vente": round(vente if vm else min(vente, valeur), 2),
                       # 2 nov 2026 (« pourquoi le max bid change ? ») : la meme regle que les deals et la watchlist (70 %)
                       "achat_max": round(max(0.0, _deals.prix_max(valeur, taxe=_deals.taxe_de(a))), 2), "source": "vendues" if vm else "annonces"}
        # 26 oct 2026 (Mathieu : « les deals sont pas bons avec les last sold ») : la fenetre a les ventes de CETTE carte ;
        # si elles disent que ce n'est pas un deal, l'annonce sort des deals de tout le monde (et sa valeur est corrigee)
        # 3 nov 2026 : ventes PAS LUES (SoldComps en panne, budget du jour) : on ne corrige rien (avant : le deal etait retire
        # pour tout le monde a la moindre panne) ; et la fiche reprend la valeur que le chasseur avait trouvee avec les ventes
        panne = bool(vc.get("erreur_ebay") or vc.get("erreur"))        # eBay pas lu (meme avec une vente SlabCoach)
        chasseur = None
        if panne and not juger:
            try:
                import deals as _dl1
                x_ = next((g for g in (_dl1.lire().get("deals") or []) if str(g.get("item_id")) == str(item_id) and g.get("valeur")), None)
                if x_:
                    chasseur = {"valeur": x_["valeur"], "le": x_.get("vu_le")}
                    valeur, juger = x_["valeur"], True
                    suggere = {"vente": valeur, "achat_max": round(max(0.0, _deals.prix_max(valeur, taxe=_deals.taxe_de(a))), 2), "source": "chasseur"}
            except Exception as e:
                print("Deals (valeur du chasseur) : " + repr(e), flush=True)
        if not rapide and total and not panne:
            try:
                import deals as _dl
                gain_v = round(_net_rev(valeur) - _paye(total, a), 2) if valeur and juger else None
                _dl.corriger(item_id, valeur if juger else None, gain_v, total)
            except Exception:
                pass
        if valeur and juger:                     # 5 nov 2026 : la valeur trouvee ici sert aussi a la watchlist (sa mise max)
            try:
                import watchlist as _wl
                # 6 nov 2026 (« les mises sont hautes vis-a-vis la mediane des last sold ») : des ventes relues a l'instant
                # remplacent l'ancienne valeur ; celle du chasseur (ventes pas relues) ne remplit qu'une valeur manquante
                _wl.valeur_trouvee(self, item_id, valeur, remplacer=bool(vm) and not panne)
            except Exception as e:
                print("Watchlist (valeur de la fiche) : " + repr(e), flush=True)
        # 7 nov 2026 (Mathieu : « pourquoi il prend en consideration le shipping ? c'est CF31 ») : chez un vendeur ou tu
        # ramasses (Reglages des deals), la fiche compte comme la tuile : sans le port (prix, rabais, profit, mise max).
        # Le deal partage (corriger, maj_prix) garde le vrai port : les autres comptes ne ramassent pas.
        ram = bool(a.get("vendeur")) and str(a.get("vendeur")).lower() in self._chez_ramassage()
        if ram and total:
            port_r = float(a.get("port_cad") or 0)
            a = dict(a, port_cad=0.0, port_estime=False, ramassage=True, port_reel=port_r)
            total = round(max(0.0, total - port_r), 2)
        if not ebay_prix_actif():                # interrupteur : l'annonce seule, sans valeur ni rabais
            return {"ok": True, "article": {**a, "total": total}, "comps": [], "n": 0, "coupe": True}
        return {"ok": True, "article": {**a, "total": total}, "comps": comps, "mediane": med, "n": n, "deal_retire": bool(maj_deal and maj_deal.get("retire")),
                "suggere": suggere, "ventes": ventes, "mediane_vendue": None if saison_v else vc.get("mediane"),
                "nb_vendues": len(ventes) if saison_v else vc.get("nb") or len(ventes),
                "valeur": valeur, "valeur_source": "chasseur" if chasseur else "vendues" if vm else saison_v[1] if saison_v else "annonces",
                "saisons": sorted({v.get("saison") for v in (saison_v or [0, 0, 0, []])[3] if v.get("saison")}) or None,
                "saison_carte": _deals.saison(cartes_match.cible_titre(t or "").get("annee")) if saison_v else None,
                "ventes_attente": bool(vc.get("attente")),
                "valeur_chasseur": chasseur, "ventes_panne": panne, "vieux_cache": bool(vc.get("vieux_cache")),
                "points": vc.get("points") or [], "tendance": vc.get("tendance"), "autres_joueurs": autres,
                "rabais": round(100 * (1 - total / valeur)) if total and valeur and juger else None,
                "taxe_achat": _deals.taxe_de(a), "etranger": _deals.etranger(a),
                "gain": round(_net_rev(valeur) - _paye(total, a), 2) if total and valeur and juger else None,
                "peu_de_ventes": not juger, "pourquoi": pourquoi if not juger else None, "nb_trouvees": nb_v,
                "mes_achats": mes_achats, "deja_achetee": deja_achetee, "mes_retirees": vc.get("mes_retirees") or 0}

    def _mes_ventes_pareilles(self, titre, item_id=None, n=8):
        """Les MEMES cartes deja vendues par ce compte (vraies ventes, avec photo) : {titre, prix, le, photo}."""
        nom = str(cartes_match.joueur_du_titre(titre) or "").split()[-1:] or [""]
        nom = nom[0]
        if not nom or len(nom) < 3:
            return []
        c = self._db()
        try:
            l = _dicts(c.execute("SELECT id, titre, joueur, prix_vendu, port_charge, vendu_le, photo, item_number FROM cartes "
                                 "WHERE statut='Vendue' AND prix_vendu > 0 AND (titre LIKE ? OR joueur LIKE ?) ORDER BY vendu_le DESC LIMIT 200",
                                 (f"%{nom}%", f"%{nom}%")))
        except sqlite3.Error:
            return []
        finally:
            c.close()
        _c, memes, _e = cartes_match.filtrer_carte(titre, [{**x, "item_id": x.get("item_number") or ("c" + str(x["id"])), "titre": x.get("titre") or x.get("joueur") or ""} for x in l],
                                                   exclure_id=item_id)
        return [{"titre": x["titre"], "prix": round((x.get("prix_vendu") or 0) + (x.get("port_charge") or 0), 2), "le": x.get("vendu_le"),
                 "photo": x.get("photo") if str(x.get("photo") or "") not in ("", "-") else None} for x in memes[:n]]

    def deal_masquer(self, item_id):
        with _verrou:
            c = self._db()
            try:
                c.execute("CREATE TABLE IF NOT EXISTS deals_masques (item_id TEXT PRIMARY KEY)")
                c.execute("INSERT OR IGNORE INTO deals_masques VALUES (?)", (str(item_id),))
                c.execute("UPDATE opportunites SET masque=1 WHERE item_id=?", (str(item_id),))
                c.commit()
            finally:
                c.close()
        return {"ok": True}

    def deal_signaler(self, d):
        """26 oct 2026 (Mathieu : « encore pas un deal ... une option pas un deal : l'annonce disparait et ca nous laisse
        savoir quoi modifier ») : masque l'annonce, et la signale a l'admin avec tout le calcul (l'agent l'analyse).
        Signale par l'admin : retiree des deals de TOUT le monde."""
        import comptes
        import deals
        import demandes
        d = d or {}
        iid = str(d.get("item_id") or "")
        if not iid:
            return {"ok": False, "erreur": "Annonce inconnue"}
        self.deal_masquer(iid)
        g = next((x for x in deals.lire_vite().get("deals") or [] if str(x.get("item_id")) == iid), {})
        ctx = {"item_id": iid, "titre": d.get("titre") or g.get("titre"), "prix": d.get("total") or g.get("total"),
               "valeur_calculee": d.get("valeur") or g.get("valeur"), "source_valeur": d.get("valeur_source") or g.get("valeur_source"),
               "nb": d.get("n") or g.get("n"), "recherche": g.get("q") or d.get("q"), "url": (d.get("url") if re.match(r"https://([a-z0-9-]+\.)*ebay\.[a-z.]+/", str(d.get("url") or "")) else None) or g.get("url"),
               "ventes": [{k: v.get(k) for k in ("titre", "prix", "le")} for v in (d.get("ventes") or g.get("vendues") or [])[:8]],
               "annonces": [{k: v.get(k) for k in ("titre", "total")} for v in (d.get("comps") or g.get("comps") or [])[:8]]}
        raison = str(d.get("raison") or "").strip()[:300]
        texte = f"Pas un deal ({raison or 'sans raison'}) : {str(ctx['titre'] or '')[:140]} à {ctx['prix']} $ « vaut » {ctx['valeur_calculee']} $ ({ctx['source_valeur'] or '?'})"
        cid = comptes.courant() if comptes.MULTI else "local"
        info = comptes.info(cid) if comptes.MULTI else {}
        r = demandes.envoyer("pas_deal", texte, cid, (info or {}).get("username"), self.reglages_lire().get("langue") or "fr", "deals",
                             contexte=ctx)
        if self._est_admin():
            deals.bannir(iid)
        return {"ok": True, "signale": bool(r.get("ok"))}

    def demandes_mes(self):
        import comptes
        import demandes
        return {"ok": True, "items": demandes.mes_demandes(comptes.courant() if comptes.MULTI else "local")}

    def acheteur_accueil(self):
        """Deals a acheter (annonces bien sous ce que la carte vaut), achats du mois, valeur du stock achete."""
        maint = datetime.now()
        m0 = maint.strftime("%Y-%m")
        r = self.reglages_lire()
        fp, ff = (r["frais_ebay_pct"] or 0) / 100, r["frais_ebay_fixe"] or 0
        with _verrou:
            c = self._db()
            try:
                achats = _dicts(c.execute("SELECT * FROM cartes WHERE cout IS NOT NULL AND substr(cree_le,1,7)=?", (m0,)))
                dep = c.execute("SELECT COALESCE(SUM(montant),0) FROM depenses WHERE substr(le,1,7)=? AND categorie='achats'", (m0,)).fetchone()[0]
            finally:
                c.close()
        deals = self._deals_fusion()                  # 24 oct 2026 - tes rachats + le chasseur partage
        for d_ in deals:
            d_["ref_prix"] = d_.get("valeur")
        deals.sort(key=lambda d: -d["gain"])
        depense = round(sum(a["cout"] or 0 for a in achats) + (dep or 0), 2)
        valeur = round(sum((a.get("valeur") or a.get("prix_demande") or 0) for a in achats), 2)
        # 28 oct 2026 (vitesse) : l'accueil en montre au plus 24 ; avant, les ~800 deals partaient a chaque ouverture (1,6 Mo)
        try:                                          # 31 oct 2026 : + les encans des gros vendeurs valorises sous 70 %
            import deals as _dv
            ids_ = {str(x.get("item_id")) for x in deals}
            n_su = sum(1 for x in (_dv.lire_vite().get("suivis") or []) if x.get("valeur") and str(x.get("item_id")) not in ids_
                       and _dv.encore_ouvert(x) and (x.get("total") or 0) <= _dv.prix_max(x["valeur"], taxe=_dv.taxe_de(x)))
        except Exception:
            n_su = 0
        return {"mois": m0, "deals": deals[:24], "nb_deals": len(deals) + n_su, "gain_deals": round(sum(max(0, d["gain"]) for d in deals), 2),
                "achats": {"n": len(achats), "depense": depense, "valeur": valeur,
                           "latent": round(sum(((a.get("valeur") or a.get("prix_demande") or 0) * (1 - fp) - ff - (a["cout"] or 0))
                                             for a in achats if a.get("valeur") or a.get("prix_demande")), 2)},
                "cles": ebay_compte.statut().get("cles_ok"), "ebay": ebay_compte.statut().get("connecte"),
                "nom_boutique": r["nom_boutique"], "actions": self._actions_envois()}

    def carte_gradations(self, texte, requete=True):
        """8 nov 2026 : la variation de prix en % de la MEME carte, par gradation (brute, PSA 10, 9, 8...), pour la fiche."""
        texte = re.sub(r"\s+", " ", str(texte or "")).strip()[:200]
        if len(texte) < 3:
            return {"ok": False, "erreur": "Carte inconnue"}
        try:
            return vendues.par_gradation(texte, requete=bool(requete), fond=False)
        except Exception as e:
            return {"ok": False, "erreur": type(e).__name__}

    def valeur_carte(self, q):
        """« Combien vaut cette carte ? » : annonces actives a prix fixe (eBay Browse, cache partage).
        24 oct 2026 : seulement la MEME carte (cartes_match : variante, gradation, auto, patch, numerotation,
        lots ecartes) ; prix median sans les extremes ; le prix a ne pas depasser pour revendre (70 %)."""
        import cartes_match
        import forfaits
        q = re.sub(r"\s+", " ", str(q or "")).strip()
        if len(q) < 3:
            return {"ok": False, "erreur": "Écris le joueur et la carte (ex. Bedard Young Guns)."}
        try:
            forfaits.verifier("valeur_jour")
        except forfaits.LimiteAtteinte as e:
            return {"ok": False, "erreur": str(e), "pro_requis": True}
        c = cartes_match.cible(q)
        q_ebay = cartes_match.requete_ebay(c) or q
        try:
            res = ebay_compte.rechercher(q_ebay, categorie=CATEGORIE_CARTES, limite=200, fond=False)
        except (RuntimeError, OSError) as e:
            return {"ok": False, "erreur": str(e)}
        r = self.reglages_lire()
        fp, ff = (r["frais_ebay_pct"] or 0) / 100, r["frais_ebay_fixe"] or 0
        lst = []
        for a in res or []:
            total = round((a.get("prix_cad") or 0) + (a.get("port_cad") or 0), 2)
            if total > 0:
                lst.append({**a, "total": total})
        _c, gardees, ecartees = cartes_match.filtrer(q, lst)
        gardees.sort(key=lambda x: x["total"])
        compris = cartes_match.resume(c)
        raisons = {}
        for x in ecartees:
            raisons[x["raison"]] = raisons.get(x["raison"], 0) + 1
        base = {"ok": True, "q": q, "compris": compris, "n_ecartees": len(ecartees),
                "raisons": sorted(raisons.items(), key=lambda kv: -kv[1])[:6],
                "ecartees": [{k: x.get(k) for k in ("item_id", "titre", "total", "photo", "url", "raison")} for x in ecartees[:30]]}
        forfaits.compter("valeur_jour")
        # 25 oct 2026 (Mathieu : « base-toi toujours sur les last sold ») : la valeur = ventes reelles
        try:
            base["vendues"] = vendues.memes(q, requete=True, n=24)
        except Exception as e:
            base["vendues"] = {"ventes": [], "mediane": None, "nb": 0, "erreur": type(e).__name__}
        # 27 oct 2026 (Mathieu : « pas de faux prix ») : une valeur SEULEMENT si les ventes reelles sont sures (deals.valeur_sure :
        # numeros speciaux ecartes, ventes recentes, coherentes). Jamais une valeur tiree des prix demandes.
        import deals as _deals
        # 9 nov 2026 (Mathieu : « tout sauf notre deal ») : tes achats de cette carte : montres a part, jamais dans les comps
        mes_achats, mes_ids, _ex = self._mes_achats_titre(q)
        base["mes_achats"] = mes_achats
        if base["vendues"].get("ventes"):
            base["vendues"]["ventes"], n_mes = self._sans_mes_achats(base["vendues"]["ventes"], mes_achats, mes_ids)
            if n_mes:
                base["vendues"]["nb"] = len(base["vendues"]["ventes"])
                base["vendues"]["mes_retirees"] = n_mes
                pr = sorted(float(v["prix"]) for v in base["vendues"]["ventes"] if v.get("prix"))
                base["vendues"]["mediane"] = (pr[len(pr) // 2] if len(pr) % 2 else round((pr[len(pr) // 2 - 1] + pr[len(pr) // 2]) / 2, 2)) if pr else None
        vs = [v for v in (base["vendues"].get("ventes") or []) if v.get("prix")]
        vm = _deals.valeur_sure(vs, q)[0] if len(vs) >= 2 else None
        base["valeur_sure"] = bool(vm)
        if not gardees:
            return {**base, "n": 0, "annonces": [], "valeur": vm, "valeur_source": "vendues" if vm else None,
                    "bon_prix": round(vm * sante.RACHAT_RATIO, 2) if vm else None}
        med, garde = cartes_match.mediane_robuste([x["total"] for x in gardees])
        valeur = vm
        bon = round(valeur * sante.RACHAT_RATIO, 2) if valeur else None
        for x in gardees:
            x["deal"] = bool(bon) and x["total"] <= bon
            x["bon"] = bool(valeur) and (not x["deal"]) and x["total"] <= valeur          # « bon prix » : sous la valeur vendue
            x["gain"] = round(_net_rev(valeur) - _paye(x["total"], x), 2) if valeur else None
            x["hors_norme"] = x["total"] not in garde
        if not prix_annonces_permis():          # 10 nov 2026 (licence eBay §9.5) : aucun chiffre tire des annonces
            for x in gardees:
                x.pop("hors_norme", None)
            return {**base, "n": len(gardees), "mediane": None, "valeur": valeur, "valeur_source": "vendues" if vm else None,
                    "bon_prix": bon, "min": None, "max": None, "annonces": gardees[:40]}
        return {**base, "n": len(gardees), "mediane": med, "valeur": valeur, "valeur_source": "vendues" if vm else None,
                "bon_prix": bon, "min": garde[0], "max": garde[-1], "annonces": gardees[:40]}

    def valeur_signaler(self, q, item_id, titre, bonne=False):
        """« Pas la bonne carte » (ou « c'est la bonne ») : l'app apprend, pour tout le monde."""
        import cartes_match
        import comptes
        return cartes_match.apprendre(q, item_id, titre, bool(bonne), votant=comptes.courant(),
                                      confiance=(not comptes.MULTI) or self._est_admin())

    def accueil(self):
        maint = datetime.now()
        m0 = maint.strftime("%Y-%m")
        m1 = (maint.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        r = self.reglages_lire()
        fp, ff = (r["frais_ebay_pct"] or 0) / 100, r["frais_ebay_fixe"] or 0
        b0, b1 = self.bilan(m0), self.bilan(m1)
        brk = self.breaks_liste()
        with _verrou:
            c = self._db()
            try:
                s0, s1 = self._serie_profit(c, m0), self._serie_profit(c, m1)
                for b in brk:
                    mo, j = str(b["cree_le"] or "")[:7], int(str(b["cree_le"] or "0000-00-01")[8:10] or 1)
                    if mo in (m0, m1):
                        cible = s0 if mo == m0 else s1
                        cible[j] = cible.get(j, 0) + (b["profit"] or 0)
                actives = self._annonces_actives(c)
                sante_ = {x["item_number"]: x for x in _dicts(c.execute("SELECT * FROM sante"))}
                limite = (maint - timedelta(days=4)).isoformat()
                opps = [o for o in _dicts(c.execute("SELECT * FROM opportunites WHERE masque=0 AND vu_le >= ?", (limite,))) if _opp_ok(o.get("titre"))]
                stock = _dicts(c.execute("SELECT * FROM cartes WHERE statut!='Vendue'"))
                d30 = (maint - timedelta(days=30)).isoformat()
                d90 = (maint - timedelta(days=90)).isoformat()
                vendues90 = _dicts(c.execute("SELECT * FROM cartes WHERE statut='Vendue' AND vendu_le >= ?", (d90,)))
            finally:
                c.close()

        # -- courbe : cumul du mois vs le mois passe, et l'ecart « a pareille date »
        def cumul(jours, n):
            t, out = 0.0, []
            for j in range(1, n + 1):
                t += jours.get(j, 0)
                out.append(round(t, 2))
            return out
        auj = maint.day
        nb1 = (maint.replace(day=1) - timedelta(days=1)).day
        c0, c1 = cumul(s0, auj), cumul(s1, nb1)
        pareil = c1[min(auj, nb1) - 1] if c1 else 0
        hero = {"profit": b0["profit"], "revenus": b0["revenus"], "mois": m0, "mois_passe": m1,
                "profit_passe": b1["profit"], "pareille_date": round(pareil, 2),
                "ecart": round(b0["profit"] - pareil, 2), "courbe": c0, "courbe_passe": c1,
                "nb_ventes": sum(v["nb"] for v in b0["canaux"].values()),
                "marge": round(100 * b0["profit"] / b0["revenus"]) if b0["revenus"] else None}

        # -- stock : valeur marche, gain latent, argent qui dort
        act = {a["item_number"]: a for a in actives}
        valeur = cout = latent = 0.0
        sans_cout = 0
        ages = {"frais": [0, 0.0], "moyen": [0, 0.0], "vieux": [0, 0.0]}
        for k in stock:
            sv = sante_.get(k.get("item_number")) or {}
            v = sv.get("mediane") or k.get("valeur") or k.get("prix_demande") or k.get("cout") or 0
            valeur += v
            if k.get("cout"):
                cout += k["cout"]
                latent += v * (1 - fp) - ff - k["cout"]
            elif k.get("item_number") in act:
                sans_cout += 1
        for a in actives:
            age = sante.age_jours(a.get("debut") or a.get("cree_le"))
            cle = "frais" if age is None or age < 30 else ("moyen" if age < 90 else "vieux")
            ages[cle][0] += 1
            ages[cle][1] += a.get("prix_demande") or 0

        # -- vitesse de vente (eBay) : taux d'ecoulement 30 j et delai median
        v30 = [v for v in vendues90 if str(v.get("vendu_le") or "") >= d30]
        delais = sorted(d for d in (self._delai(v) for v in vendues90) if d is not None)
        vitesse = {"ventes_30j": len(v30), "actives": len(actives),
                   "ecoulement": round(100 * len(v30) / (len(v30) + len(actives))) if (v30 or actives) else None,
                   "delai_median": delais[len(delais) // 2] if delais else None}

        # -- actions classees par argent
        def somme(lst, f):
            return round(sum(f(x) for x in lst), 2)
        par = {"baisser": [], "monter": [], "traine": []}
        for it, sv in sante_.items():
            if it in act and not sv.get("fait") and sv.get("verdict") in par:
                par[sv["verdict"]].append({**sv, "prix": act[it].get("prix_demande") or 0})
        actions = []
        a_env = sum(x["a_envoyer"] for x in brk)
        if a_env:
            actions.append({"cle": "envoyer", "n": a_env, "titre": "À envoyer", "montant": None, "texte": "acheteurs qui attendent",
                            "lien": "#breaks/liste", "ton": "rouge", "rang": 1e9})
        if par["baisser"]:
            m = somme(par["baisser"], lambda x: x["prix"])
            actions.append({"cle": "baisser", "n": len(par["baisser"]), "titre": "Trop chères", "montant": m,
                            "texte": "à débloquer en baissant", "lien": "#sante/baisser", "ton": "rouge", "rang": m})
        if par["monter"]:
            m = somme(par["monter"], lambda x: max(0, (x.get("suggestion") or 0) - x["prix"]))
            actions.append({"cle": "monter", "n": len(par["monter"]), "titre": "Sous le marché", "montant": m,
                            "texte": "de plus en montant", "lien": "#sante/monter", "ton": "vert", "rang": m * 3})
        if opps:
            m = somme(opps, lambda o: max(0, (o.get("ref_prix") or 0) * (1 - fp) - ff - (o.get("total") or 0)))
            actions.append({"cle": "racheter", "n": len(opps), "titre": "Bonnes affaires", "montant": m,
                            "texte": "à gagner en revendant", "lien": "#sante/racheter", "ton": "acc", "rang": m * 2})
        if par["traine"]:
            m = somme(par["traine"], lambda x: x["prix"])
            actions.append({"cle": "traine", "n": len(par["traine"]), "titre": "Ça dort", "montant": m,
                            "texte": "immobilisés, à relancer", "lien": "#sante/traine", "ton": "or", "rang": m * 0.5})
        # 28 oct 2026 : une carte de collection (gardee, pas a vendre) n'est jamais « a mettre en ligne »
        a_lister = [k for k in stock if k.get("statut") == "En stock" and (k.get("emplacement") or "") not in ("Magasin", "Collection")]
        if a_lister:
            m = somme(a_lister, lambda k: k.get("valeur") or k.get("cout") or 0)
            actions.append({"cle": "lister", "n": len(a_lister), "titre": "Pas en vente", "montant": m or None,
                            "texte": "de stock à mettre en ligne", "lien": "#inventaire/stock", "ton": "acc", "rang": m})
        du = round(sum(k["du"] for k in self.consignataires_liste()), 2)
        if du > 0:
            actions.append({"cle": "consignation", "n": None, "titre": "Consignation", "montant": du, "texte": "à payer aux consignataires",
                            "lien": "#comptoir/consignation", "ton": "", "rang": 0})
        if sans_cout:
            actions.append({"cle": "couts", "n": sans_cout, "titre": "Coût manquant", "montant": None,
                            "texte": "ajoute-le : profit exact", "lien": "#inventaire/sans-cout", "ton": "", "rang": -1})
        try:                                     # 28 oct 2026 : acheteurs interesses (API Negotiation, garde d'une heure)
            no = self.offres_compte()["n"]
            if no:
                actions.append({"cle": "offres", "n": no, "titre": "Acheteurs intéressés", "montant": None,
                                "texte": "envoie-leur une offre en un tap", "lien": "#offres", "ton": "vert", "rang": 50})
        except Exception:
            pass
        actions += self._actions_envois()
        actions.sort(key=lambda a: -a["rang"])

        # -- meilleurs coups (30 j) : ce qui marche, pour en racheter
        coups = []
        for v in v30:
            if v.get("profit") is None:
                continue
            coups.append({"titre": v["titre"], "profit": round(v["profit"], 2), "prix": v.get("prix_vendu"),
                          "roi": round(100 * v["profit"] / v["cout"]) if v.get("cout") else None,
                          "jours": self._delai(v), "photo": v.get("photo"), "id": v["id"]})
        coups.sort(key=lambda x: -x["profit"])

        try:                                     # 26 oct 2026 : la valeur de la collection, un point par jour
            marche.noter_collection(self, valeur, cout, len(stock))
        except Exception:
            pass
        try:                                     # 1er nov 2026 : la valeur de la COLLECTION seule, un point par jour
            import collection_sets
            collection_sets.noter(self)
        except Exception:
            pass
        analysees = sum(1 for it in act if it in sante_)
        derniere = max((sv.get("maj") or "" for it, sv in sante_.items() if it in act), default=None)
        # 28 oct 2026 (Mathieu : « donner des infos sur la valeur de sa collection et si le joueur est en feu », mais simple) :
        # UN seul indice, le joueur de TES cartes qui est le plus en feu (LNH, 5 derniers matchs)
        chaud = None
        try:
            import nhl
            mes = {}
            for k in stock:
                j = cartes_match.norm(k.get("joueur") or "")
                if j:
                    mes[j] = mes.get(j, 0) + 1
            for f in nhl.chauds():
                n = mes.get(cartes_match.norm(f["joueur"]))
                if n:
                    chaud = {"joueur": f["joueur"], "points": f["points"], "matchs": f["matchs"], "n": n}
                    break
        except Exception:
            chaud = None
        coll_n = sum(1 for k in stock if k.get("statut") == "En stock" and (k.get("emplacement") or "") == "Collection")
        return {"hero": hero, "actions": actions, "coups": coups[:3], "chaud": chaud, "collection_n": coll_n,
                "stock": {"valeur": round(valeur, 2), "cout": round(cout, 2), "latent": round(latent, 2), "nb": len(stock),
                          "ages": {k: {"n": v[0], "montant": round(v[1], 2)} for k, v in ages.items()}},
                "vitesse": vitesse, "analyse": {"actives": len(actives), "analysees": analysees, "maj": derniere},
                "breaks_ouverts": [x for x in brk if x["statut"] != "ferme"][:5], "a_envoyer": a_env,
                "activites": self.activites(), "nom_boutique": r["nom_boutique"],
                "ebay": ebay_compte.statut().get("connecte"), "cles": ebay_compte.statut().get("cles_ok")}

    @staticmethod
    def _delai(v):
        try:
            # 24 oct 2026 : seulement la vraie date de mise en vente (cree_le = date d'import -> « vend en 0 j »)
            a = datetime.fromisoformat(str(v.get("debut"))[:19].replace("Z", ""))
            b = datetime.fromisoformat(str(v.get("vendu_le"))[:19].replace("Z", ""))
            return (b - a).days if b >= a else None
        except (TypeError, ValueError):
            return None


def random_ordre(lots, graine):
    import random
    l = list(lots)
    random.Random(graine + ":reste").shuffle(l)
    return l
