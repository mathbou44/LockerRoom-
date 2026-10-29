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
import os
import re
import secrets
import sqlite3
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
    "alarmes": {},                                              # 29 oct 2026 : les alertes cochees (voir alarmes.py)
    "nom_boutique": "Ma boutique",
    "equipe_fav": "",                                           # 26 oct 2026 : les accents de l'app aux couleurs de cette equipe
    "palette": "refractor",                                     # 27 oct 2026 : refractor + 5 paralleles
    "ia_photos_ok": False,                                      # 27 oct 2026 : permission explicite (Apple 5.1.2(i))
    "frais_ebay_pct": 13.25, "frais_ebay_fixe": 0.40,           # eBay Canada, cartes (a ajuster a ton compte)
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
CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY, nom TEXT, contact TEXT, credit REAL DEFAULT 0, note TEXT, cree_le TEXT);
CREATE TABLE IF NOT EXISTS consignataires (id INTEGER PRIMARY KEY, nom TEXT, contact TEXT, pct_boutique REAL, cree_le TEXT);
CREATE TABLE IF NOT EXISTS paiements_consignation (id INTEGER PRIMARY KEY, consignataire_id INTEGER, montant REAL, le TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS ventes_comptoir (id INTEGER PRIMARY KEY, le TEXT, sous_total REAL, taxes REAL, total REAL,
    paiement TEXT, client_id INTEGER, lignes TEXT);
CREATE TABLE IF NOT EXISTS rachats (id INTEGER PRIMARY KEY, le TEXT, client_id INTEGER, valeur REAL, offre REAL, mode TEXT, lignes TEXT);
CREATE TABLE IF NOT EXISTS depenses (id INTEGER PRIMARY KEY, le TEXT, categorie TEXT, montant REAL, note TEXT);
"""


def _maintenant():
    return datetime.now().isoformat(timespec="seconds")


_BASES_PRETES = set()      # 28 oct 2026 (vitesse) : schema et migrations verifies une fois par base et par demarrage


def _connecter(chemin=None):
    p = chemin or CHEMIN_DB
    c = sqlite3.connect(p, timeout=30)
    c.row_factory = sqlite3.Row
    if p in _BASES_PRETES and os.path.exists(p):
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
                     ("sport", "TEXT"), ("recrue", "INTEGER"), ("relique", "INTEGER"), ("cert", "TEXT"), ("photos", "TEXT")):
        if col not in cols:
            c.execute(f"ALTER TABLE cartes ADD COLUMN {col} {typ}")
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


def ebay_prix_actif():
    """27 oct 2026 - interrupteur du serveur (LOCKERROOM_EBAY_PRIX=0) : coupe d'un geste les fonctions de prix sur les
    ANNONCES eBay (deals, prix suggere d'une annonce, repere prix et comparables, « Mettre au prix du marche ») si eBay
    le demande (licence API §9.5) ou coupe nos cles. Valeur d'une carte, tendances, breaks, inventaire et comptoir
    continuent : ils ne dependent pas de l'API eBay."""
    return os.environ.get("LOCKERROOM_EBAY_PRIX", "1") != "0"


def est_ios():
    return _IOS.get()



def _niveau(resume, info):
    """bronze (gratuit) | silver (forfait intermediaire, plus tard) | gold (Pro, essai, offert, app locale)."""
    f = str((info or {}).get("forfait") or "").lower()
    if f in ("silver", "argent", "collector"):
        return "silver"
    return "gold" if (resume or {}).get("pro") else "bronze"

LIER = {}          # 28 oct 2026 : jetons a usage unique pour relier eBay depuis l'app iPhone (jeton -> (compte, le))

class Api:
    def __init__(self, chemin_db=None):
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
        # 24 oct 2026 - heberge : la campagne eBay Partner Network est celle de SlabCoach (serveur), pour tous les clients
        epn = re.sub(r"\D", "", os.environ.get("LOCKERROOM_EPN_CAMPID") or "")
        if epn:
            r["epn_campid"] = epn
        return r

    # -- taux de change du jour (24 oct 2026) : Banque du Canada, garde 12 h ; repli 0,70 ---------------
    def taux_change(self):
        """{"usd": 0.70, "date": "2026-10-23", "source": "Banque du Canada"} : 1 $ CA = usd $ US."""
        import comptes
        chemin = os.path.join(comptes.DONNEES, "taux_change.json")
        try:
            with open(chemin, encoding="utf-8") as f:
                c = json.load(f)
            if datetime.now().timestamp() - float(c.get("lu", 0)) < 12 * 3600:
                return c
        except (OSError, ValueError):
            c = None
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
            with open(chemin, "w", encoding="utf-8") as f:
                json.dump(c, f)
            return c
        except Exception:
            return c or {"usd": 0.70, "date": None, "source": "approximatif"}

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
        return {**forfaits.resume(), "multi": multi, "admin": self._est_admin(), "communaute": ventes_communaute.actif(),
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
        info = comptes.info(cid) or {}
        if info.get("stripe_abonnement") and (info.get("forfait") == "pro"):
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
        comptes.supprimer(cid)
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
        out = []
        for p in catalogue.liste():
            k = (cle, p["id"])
            if k not in self._EV_CACHE:
                prod = catalogue.charger(p["id"])
                self._EV_CACHE[k] = calcul.prix_catalogue(prod, boites=1)["ev_par_boite"]
            boite = valeur_produit.de(p["id"]).get("boite")       # 26 oct 2026 : vaut-il la peine d'ouvrir ?
            out.append(dict(p, ev_par_boite=self._EV_CACHE[k], prix_boite=boite, ouvrir=marche.verdict_ouvrir(self._EV_CACHE[k], boite)))
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
                "taches": s.get("taches"), "disque": s.get("disque")}

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

    def admin_remettre(self, cle):
        if not self._est_admin():
            return {"ok": False, "erreur": "Réservé à l'administrateur"}
        import admin
        return admin.remettre(str(cle or ""))

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

    def _est_admin(self):
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
        d = d or {}
        if not self._est_admin():
            return {"ok": False, "erreur": "Les produits sont ajoutés par SlabCoach pour tout le monde"}
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
            nom = re.sub(r"\s+", " ", str(d.get("nom") or "") or checklist_import.nom_devine(nom_f)).strip()
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
        catalogue.enregistrer_ajout(prod)
        self._EV_CACHE.clear()
        p2 = catalogue.charger(prod["id"]) or prod
        taux = p2.get("_taux") or {}
        return {"ok": True, "id": prod["id"], "nom": prod["nom"], "nb_cartes": len(prod["cartes"]), "nouveau": not existant, "modele": modele,
                "cotes_lues": n_cotes,
                "sous_ensembles": [{"nom": x["nom"], "groupe": x.get("groupe"), "nb_cartes": x.get("nb_cartes"), "tirage": x.get("tirage"),
                                    "par_boite": x.get("par_boite"), "taux": round(taux.get(x["nom"], 0), 4)} for x in prod["sous_ensembles"]]}

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
        for pl in res["places"]:
            self._noter_place(pl, demandes.get(pl["cle"]), stats.get(pl["cle"]))
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
                self._noter_place(pl, dj.get(pl["cle"]), sj.get(pl["cle"]))
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
    def _noter_place(pl, demande, stats):
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
        n_bonnes = sum(float(n) for v, n in dist if prix and float(v) >= prix)
        pl["p_carte_prix"] = round(1 - _m2.exp(-n_bonnes), 6) if prix else 0
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
                    "note", "client_id", "sport", "recrue", "relique", "cert", "photo", "photos")

    def inventaire_liste(self, filtres=None):
        f = filtres or {}
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
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(int(f.get("limite") or 500))
        with _verrou:
            c = self._db()
            try:
                out = _dicts(c.execute(sql, args))
            finally:
                c.close()
        defaut = self.reglages_lire().get("sport") or sports.DEFAUT
        # 24 oct 2026 - repere prix : ton prix face aux memes cartes en vente (sante : mediane, plus bas, nombre)
        with _verrou:
            c = self._db()
            try:
                marche = {r["item_number"]: r for r in _dicts(c.execute(
                    "SELECT item_number, mediane, n, bas, verdict, ecart, suggestion, maj FROM sante"))}
            finally:
                c.close()
        for r in out:
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
        if not d.get("titre"):
            d["titre"] = ebay_csv.titre_annonce(d)
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
        carte = {k: v for k, v in (d.get("carte") or {}).items() if k in self.CHAMPS_CARTE and k not in ("id", "photo", "photos", "statut")}
        try:
            refs = photos_cartes.sauver(d.get("photos") or [])
        except ValueError as e:
            return {"ok": False, "erreur": str(e)}
        titre = re.sub(r"\s+", " ", str(d.get("titre") or "")).strip()[:80]
        champs = {**carte, "titre": titre or None, "prix_demande": _float(d.get("prix")), "cout": _float(d.get("cout")),
                  "photo": refs[0] if refs else None, "photos": json.dumps(refs) if refs else None}
        if d.get("cid"):
            champs["id"] = d["cid"]
        else:
            champs["statut"] = "En stock"
        r = self.carte_sauver({k: v for k, v in champs.items() if v not in (None, "")})
        return {"ok": True, "id": r["id"], "photos": refs}

    def carte_photo_changer(self, cid, photo):
        """28 oct 2026 (Mathieu : « en tout temps il peut modifier la photo associee a la carte dans sa collection pour
        en prendre une meilleure ») : la nouvelle photo devient la premiere ; l'ancienne premiere est effacee du disque."""
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
        nouv = refs[:1] + avant[1:]
        self.carte_sauver({"id": cid, "photo": nouv[0], "photos": json.dumps(nouv)})
        if avant and avant[0] not in nouv:
            try:
                photos_cartes.supprimer([avant[0]])
            except Exception:
                pass
        return {"ok": True, "photo": nouv[0], "photos": nouv}

    def carte_supprimer(self, cid):
        import photos_cartes
        try:
            refs = json.loads((self.carte_lire(cid) or {}).get("photos") or "[]")
        except ValueError:
            refs = []
        photos_cartes.supprimer(refs if isinstance(refs, list) else [])
        with _verrou:
            c = self._db()
            try:
                c.execute("DELETE FROM cartes WHERE id=?", (cid,))
                c.commit()
            finally:
                c.close()
        return {"ok": True}

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
                    cons = c.execute("SELECT pct_boutique FROM consignataires WHERE id=?", (carte["consignataire_id"],)).fetchone()
                    pct = (cons["pct_boutique"] if cons else r["pct_consignation"]) / 100
                    pv["profit"] = round(pv["net"] * pct, 2)
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
        return {"ok": True, "crees": crees, "maj": maj, "lues": len(annonces)}

    def importer_ventes_ebay(self, texte):
        """Rapport « Orders » : marque les cartes vendues (par numero d'item),
        sans jamais compter deux fois la meme transaction."""
        try:
            ventes = ebay_csv.lire_ventes(texte)
        except ValueError as e:
            return {"ok": False, "erreur": str(e)}
        return self._maj_ventes(ventes)

    def _maj_ventes(self, ventes):
        r = self.reglages_lire()
        nouvelles = deja = sans_fiche = 0
        with _verrou:
            c = self._db()
            try:
                for v in ventes:
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
                                c.execute("UPDATE cartes SET frais=?, profit=? WHERE id=?",
                                          (v["frais_reels"], round(net - (dv["cout"] or 0), 2), dv["id"]))
                            c.execute("INSERT INTO ventes_ebay_vues VALUES (?)", (v["transaction_id"],))
                            deja += 1
                            continue
                    pv = calcul.profit_vente(v["prix"] or 0, (carte["cout"] if carte else 0) or 0, 0, v["port_charge"] or 0,
                                             r["frais_ebay_pct"] / 100, r["frais_ebay_fixe"])
                    if v.get("frais_reels") is not None:          # frais exacts d'eBay (API)
                        net = round((v["prix"] or 0) + (v["port_charge"] or 0) - v["frais_reels"], 2)
                        pv = {"frais": v["frais_reels"], "net": net, "profit": round(net - ((carte["cout"] if carte else 0) or 0), 2)}
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
            titre_c = a["titre"] + (" auto" if a.get("auto") and not cartes_match.decoder(a["titre"])["auto"] else "")
            q = (cartes_match.requete_ebay(cartes_match.cible_titre(titre_c, a.get("joueur"))) if carte else None) or sante.requete(a["titre"])
            try:
                res = ebay_compte.rechercher(q, a.get("categorie_ebay") or (CATEGORIE_CARTES if carte else None), limite=100)
            except (RuntimeError, OSError) as e:
                erreur = str(e)
                break
            if carte:
                _c, semblables, _e = cartes_match.filtrer_carte(titre_c, res, a.get("joueur"), exclure_id=a["item_number"])
                # 27 oct 2026 (Mathieu : « pas de faux prix ») : le marche d'une carte = ses ventes reelles SURES, pas les prix demandes
                try:
                    vs = [v for v in (vendues.memes_annonce(titre_c, fond=True).get("ventes") or []) if v.get("prix")]
                except Exception:
                    vs = []
                sure = _deals.valeur_sure(vs, titre_c)[0] if len(vs) >= 2 else None
                ev = sante.evaluer_vendues(a["prix_demande"], sure, len(vs), sante.age_jours(a.get("debut")), a.get("watchers"))
            else:
                semblables = [x for x in res if x["item_id"] != str(a["item_number"])]
                ev = sante.evaluer(a["prix_demande"], semblables, sante.age_jours(a.get("debut")), a.get("watchers"))
            totaux = sorted(round((x.get("prix_cad") or 0) + (x.get("port_cad") or 0), 2) for x in semblables if x.get("prix_cad"))
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
        p = round(max(p, plancher), 2)
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
        items = []
        for i in ids:
            a = actives.get(i)
            if not a or i in recents:
                continue
            prix, cout = _float(a.get("prix_demande")), _float(a.get("cout"))
            s_ = sante_.get(i) or {}
            pct = 10.0
            if prix and _float(s_.get("suggestion")) and s_["suggestion"] < prix:
                pct = max(5.0, min(25.0, round(100 * (1 - s_["suggestion"] / prix))))
            if prix and cout and prix * (1 - pct / 100) < cout:
                pct = max(5.0, int(1000 * (1 - cout / prix)) / 10) if cout < prix * 0.95 else None
            items.append({"item_number": i, "titre": a.get("titre"), "prix": prix, "photo": a.get("photo"), "watchers": a.get("watchers"),
                          "cout": cout, "carte_id": a.get("id"), "pct": pct, "mediane": s_.get("mediane"),
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
        if carte.get("item_number"):
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
                    c.execute("UPDATE cartes SET item_number=?, sku=?, statut='Listée', prix_demande=?, debut=? WHERE id=?",
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
        modele = {**annonces.MODELE_DEFAUT, **(r.get("modele_annonce") or {})}
        fp, ff = (r["frais_ebay_pct"] or 0) / 100, r["frais_ebay_fixe"] or 0
        prix, comps, n, note = None, [], 0, None
        if titre:
            try:
                cib = cartes_match.cible_titre(titre, c.get("joueur"))
                res = ebay_compte.rechercher(cartes_match.requete_ebay(cib) or titre, categorie=CATEGORIE_CARTES, limite=100, fond=False)
                _c, gardees, _e = cartes_match.filtrer_carte(titre, res, c.get("joueur"))
                tot = [round((x.get("prix_cad") or 0) + (x.get("port_cad") or 0), 2) for x in gardees if x.get("prix_cad")]
                med, garde = cartes_match.mediane_robuste(tot)
                n = len(garde)
                if med:
                    prix = {"marche": sante.prix_rond(med), "vite": sante.prix_rond(med * 0.90), "haut": sante.prix_rond(med * 1.10),
                            "mediane": med, "bas": garde[0], "max": garde[-1]}
                comps = sorted(({"titre": x["titre"], "total": round((x.get("prix_cad") or 0) + (x.get("port_cad") or 0), 2),
                                 "photo": x.get("photo"), "url": x.get("url")} for x in gardees if x.get("prix_cad")),
                               key=lambda x: abs(x["total"] - (med or 0)))[:8]
            except (RuntimeError, OSError) as e:
                note = str(e)
        franco = (langue or r.get("langue") or "fr") != "en"
        desc = annonces.description(c, titre, franco, modele["etat"], r.get("nom_boutique"), modele["retours"], modele["expedition"])
        jetons = ebay_compte._lire(ebay_compte.chemin_jetons())
        if not ebay_prix_actif():                # interrupteur : pas de prix suggere pour une annonce eBay
            prix, n, comps, note = None, 0, [], "Choisis ton prix"
        return {"ok": True, "titre": titre, "carte": c, "prix": prix, "n": n, "comps": comps, "note": note, "description": desc,
                "specifiques": annonces.specifiques(c), "modele": modele, "frais_pct": r["frais_ebay_pct"], "frais_fixe": ff,
                "etats": {k: v[2] if franco else v[1] for k, v in annonces.ETATS_BRUTS.items()},
                "net_marche": round(prix["marche"] * (1 - fp) - ff, 2) if prix else None,
                "promotion_ok": annonces.SCOPE_MARKETING in (jetons.get("scopes") or []), "psa_ok": __import__("psa").actif()}

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
        donnees = {**opts, "carte": carte, "titre": titre, "prix": prix, "description": d.get("description") or titre, "sku": sku,
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
            self.carte_sauver({k: v for k, v in champs.items() if v not in (None, "")})
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
        return {"ok": True, "cartes": out, "modele": {**__import__("annonces").MODELE_DEFAUT, **(self.reglages_lire().get("modele_annonce") or {})}}

    def serie_programmer(self, ids, debut, ecart_h=24, modele=None):
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
        try:
            annonces.debut_programme(heures[0].isoformat())
            annonces.debut_programme(heures[-1].isoformat())
        except ValueError as x:
            n_ok = int((_dt.now(_tz.utc) + _td(days=annonces.PROGRAMME_MAX_J) - t0).total_seconds() // (ecart * 3600)) + 1
            return {"ok": False, "erreur": str(x) + (f" : à ce rythme, {max(0, n_ok)} cartes au plus dans cette série" if n_ok < len(ids) else "")}
        r_ = self.reglages_lire()
        mod = {**annonces.MODELE_DEFAUT, **(r_.get("modele_annonce") or {}), **{k: v for k, v in (modele or {}).items() if k in annonces.MODELE_DEFAUT}}
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
        e = getattr(self, "_test_etat", None)
        if e and e.get("actif"):
            return {"ok": True, "deja": True, **e}
        self._test_etat = e = {"actif": True, "faits": 0, "total": int(n or 20), "creees": 0, "erreurs": []}

        def tache():
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
        return dict(getattr(self, "_test_etat", None) or {"actif": False})

    def ebay_synchroniser(self, jours=90):
        """Annonces actives + ventes des `jours` derniers jours, avec les frais reels."""
        try:
            annonces = ebay_compte.annonces_actives()
            ventes = [v for v in ebay_compte.commandes(int(jours or 90)) if not v.get("annulee")]
        except (RuntimeError, OSError, ValueError) as e:
            return {"ok": False, "erreur": str(e)}
        # 22 oct 2026 - 2e source (API Trading) : une vente que la nouvelle API n'a pas encore transmise
        # arrive quand meme ; les doublons entre les deux sources sont ecartes dans _maj_ventes.
        try:
            ventes += [v for v in ebay_compte.ventes_trading(min(30, int(jours or 30))) if not v.get("annulee")]
        except (RuntimeError, OSError, ValueError) as e:
            print(f"[synchro] ventes Trading ignorees : {e}", flush=True)
        a = self._maj_annonces(annonces)
        v = self._maj_ventes(ventes)
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
        return marche.fiche_joueur(self, nom)

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
        return r

    # -- 29 oct 2026 (Mathieu : « une alarme quand la carte de ma collection prend ou perd de la valeur ») --
    def valeur_suivi(self, cid, actif=None):
        import suivi_valeur
        if actif is None:
            return suivi_valeur.etat(self, cid)
        r = suivi_valeur.regler(self, cid, bool(actif))
        if actif and r.get("ok") and not r.get("reference"):
            import threading                          # pas encore de valeur : la premiere, tout de suite, en arriere-plan
            threading.Thread(target=lambda: self._suivi_premier(cid), daemon=True).start()
        return r

    def _suivi_premier(self, cid):
        import suivi_valeur
        try:
            carte = self.carte_lire(cid)
            v = suivi_valeur.valeur_actuelle(carte) if carte else None
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

    def watch_proches(self):
        """Boucle du serveur (5 min) : les encans suivis qui finissent bientot, relus sur eBay."""
        import watchlist
        return {"ok": True, "envoyees": watchlist.verifier(self, proches=True)}

    _TENDANCES = {"le": 0.0, "v": None}

    def tendances(self):
        """28 oct 2026 (vitesse) : 2 a 6 s de calcul, le meme resultat pour tous les comptes : garde 15 min."""
        import time as _t
        T = Api._TENDANCES
        if T["v"] is None or _t.time() - T["le"] > 900:
            T["v"], T["le"] = marche.tendances(), _t.time()
        return T["v"]

    def pouls(self, langue=None):
        """27 oct 2026 : le pouls du hobby (segments qui chauffent, mesures sur ventes reelles)."""
        import pouls
        return pouls.resume(langue or self.reglages_lire().get("langue") or "fr")

    def astuces(self, force=False, langue=None):
        """26 oct 2026 - « Le savais-tu ? » : astuces verifiees (calculees sur les vraies ventes ou sourcees), pour l'accueil."""
        import astuces
        rg = self.reglages_lire()
        return {"ok": True, "astuces": astuces.liste(self, rg.get("niveau"), bool(force), "en" if (langue or rg.get("langue")) == "en" else "fr")}

    def collection(self):
        return marche.collection(self)

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
        credit = min(_float(d.get("credit_utilise")) or 0, total)
        with _verrou:
            c = self._db()
            try:
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
    def _deals_fusion(self):
        import deals
        try:
            deals.chasser_si_besoin()
        except Exception:
            pass
        r = self.reglages_lire()
        fp, ff = (r["frais_ebay_pct"] or 0) / 100, r["frais_ebay_fixe"] or 0
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
            if g.get("encan") and not (maint_utc < str(g.get("fin") or "").replace("Z", "") <
                                       (datetime.utcnow() + timedelta(hours=deals.ENCAN_H)).isoformat()):   # fini, ou trop loin
                continue
            out.setdefault(g["item_id"], {**g, "source": "marche"})
        lst = []
        for x in out.values():
            if x["item_id"] in masques:
                continue
            # 26 oct 2026 : « −96 % » sur une carte a prix fixe = presque toujours une autre carte (pas la meme parallele,
            # pas le patch) : trop beau pour etre vrai, on ne le montre pas
            if not x.get("encan") and (x.get("ratio") or 1) < 0.15:
                continue
            x["gain"] = round((x.get("valeur") or 0) * (1 - fp) - ff - (x.get("total") or 0), 2)
            if not x.get("encan") and x["gain"] <= 1:          # 26 oct 2026 : pas de profit apres les frais : pas un deal
                continue
            x["rabais"] = round(100 * (1 - (x.get("ratio") or 1)))
            lst.append(x)
        return lst

    @staticmethod
    def _deals_filtrer(lst, f):
        """prix_min / prix_max (total, $ CA), rabais_min (%), gain_min ($), valeur_min ($), joueurs [..] (un des noms),
        sortes [recrue, auto, patch, numerotee, gradee, brute] (toutes demandees), avec_mise (encans avec au moins 1 mise)."""
        n = lambda k: _float(f.get(k))
        pmin, pmax, rmin, gmin, vmin = n("prix_min"), n("prix_max"), n("rabais_min"), n("gain_min"), n("valeur_min")
        joueurs = [cartes_match.norm(j) for j in (f.get("joueurs") or []) if str(j).strip()][:20]
        sortes = [x for x in (f.get("sortes") or []) if x in ("recrue", "auto", "patch", "numerotee", "gradee", "brute", "veteran", "hit")]
        out = []
        for x in lst:
            if pmin is not None and (x.get("total") or 0) < pmin or pmax is not None and (x.get("total") or 0) > pmax:
                continue
            if rmin is not None and (x.get("rabais") or 0) < rmin or gmin is not None and (x.get("gain") or 0) < gmin:
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
        rg = self.reglages_lire()
        fp_, ff_ = (rg["frais_ebay_pct"] or 0) / 100, rg["frais_ebay_fixe"] or 0
        par_sport = {}
        for x in tout:
            par_sport[x.get("sport") or "hockey"] = par_sport.get(x.get("sport") or "hockey", 0) + 1
        lst = [x for x in tout if not f.get("sports") or (x.get("sport") or "hockey") in f["sports"]]
        if f.get("type") == "fixe":
            lst = [x for x in lst if not x.get("encan")]
        elif f.get("type") == "encan":
            lst = [x for x in lst if x.get("encan")]
        # 25 oct 2026 (Mathieu : « une option de tri/filtre pour que l'utilisateur puisse customizer ses deals »)
        lst = self._deals_filtrer(lst, f)
        if f.get("vendeurs"):                     # 29 oct 2026 : « tous les deals des gros vendeurs »
            lst = [x for x in lst if x.get("flux") == "vendeurs"]
        tri = f.get("tri") or "rabais"
        # 26 oct 2026 (Mathieu : « ca ne fonctionne pas quand je selectionne biggest profit, price, ending soon ») : un
        # commentaire avalait les tris « prix » et « gain » (tout retombait sur « meilleur deal »)
        cles = {"rabais": lambda x: (1 if x.get("encan") else 0, x.get("ratio") or 1),     # prix fixe d'abord : la mise d'un encan monte
                "prix": lambda x: (x.get("total") or 0, x.get("ratio") or 1),
                "gain": lambda x: (-(x.get("gain") or 0), x.get("ratio") or 1),
                "recent": lambda x: str(x.get("vu_le") or ""),
                "fin": lambda x: (0, str(x.get("fin")), 0) if x.get("encan") else (1, "", -_ts(x.get("vu_le")))}
        lst.sort(key=cles.get(tri, cles["rabais"]), reverse=(tri == "recent"))
        if tri == "rabais" and not f.get("sortes") and not f.get("joueurs"):
            lst = _dl.melanger(lst)                # 28 oct 2026 : pas un mur de Young Guns
        if tri == "rabais":
            # 29 oct 2026 (Mathieu : « as-tu priorise les vendeurs qu'on a mentionnes, et apres le reste ? ») : leurs deals d'abord
            lst = [x for x in lst if x.get("flux") == "vendeurs"] + [x for x in lst if x.get("flux") != "vendeurs"]
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
                x["gain"] = round((x.get("valeur") or 0) * (1 - fp_) - ff_ - (x.get("total") or 0), 2)
                x["rabais"] = round(100 * (1 - (x.get("ratio") or 1)))
            sec = [x for x in self._deals_filtrer(sec, f) if x.get("encan") or x["gain"] > 1]
            if sec:
                lst, n, secours = sec, len(sec), True
                if not pro:
                    lst = lst[:forfaits.LIMITES["deals"]]
        pres = []
        ret_p = dd.get("retires") or {}
        for x in dd.get("pres") or []:
            if str(x.get("item_id")) in _d._bannis() or str(x.get("item_id")) in ret_p or not _d.encore_ouvert(x):
                continue
            y = dict(x, source="marche", gain=round((x.get("valeur") or 0) * (1 - fp_) - ff_ - (x.get("total") or 0), 2),
                     rabais=round(100 * (1 - (x.get("ratio") or 1))))
            pres.append(y)
        pres = [x for x in self._deals_filtrer(pres, f) if not f.get("sports") or (x.get("sport") or "hockey") in f["sports"]][:24 if pro else 6]
        # 29 oct 2026 (Mathieu : « je ne vois toujours pas les cartes non rookie ») : les encans de veterans et de legendes
        # des vendeurs suivis (Savage, Remi, Slab Sharks...), meme sans valeur verifiee ; jamais montres comme un deal
        ids_d = {str(x.get("item_id")) for x in lst}
        lim_s = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
        suivis = []
        for x in dd.get("suivis") or []:
            if str(x.get("item_id")) in ids_d or str(x.get("item_id")) in ret_p or str(x.get("item_id")) in _d._bannis() \
                    or not _d.encore_ouvert(x) or str(x.get("vu_le") or "") < lim_s:
                continue
            y = dict(x, source="marche")
            if y.get("valeur"):
                y["gain"] = round(y["valeur"] * (1 - fp_) - ff_ - (y.get("total") or 0), 2)
                y["rabais"] = round(100 * (1 - (y.get("total") or 0) / y["valeur"]))
            suivis.append(y)
        f_s = {k: v for k, v in f.items() if k in ("joueurs", "sortes", "prix_min", "prix_max")}
        suivis = [x for x in self._deals_filtrer(suivis, f_s) if not f.get("sports") or (x.get("sport") or "hockey") in f["sports"]]
        suivis.sort(key=lambda x: (0 if (x.get("sport") or "hockey") == "hockey" else 1, str(x.get("fin"))))   # 29 oct : le hockey d'abord
        suivis = suivis[:120 if pro else 6]
        return {"ok": True, "deals": lst[:240], "n": n, "pro": pro, "limite": None if pro else forfaits.LIMITES["deals"],
                "suivis": suivis,
                "pres": pres, "secours": secours, "secours_le": (dd.get("secours") or {}).get("le") if secours else None,
                "sports": par_sport, "maj": dd.get("maj"), "ebay": ebay_compte.statut().get("cles_ok"),
                "diag": _d.diagnostic(dd), "total": len(tout), "bassin": dd.get("bassin"), "nb_flux": len(_d.flux_liste()),
                "watch": self._watch_ids()}

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
        a = None
        try:
            a = ebay_compte.article(item_id)
        except (RuntimeError, OSError) as e:
            a = {"item_id": str(item_id), "titre": titre or "", "photos": [], "erreur": str(e)}
        t = a.get("titre") or titre or ""
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
        r = self.reglages_lire()
        fp, ff = (r["frais_ebay_pct"] or 0) / 100, r["frais_ebay_fixe"] or 0
        # 25 oct 2026 (Mathieu : « montre les last sold comps avec leurs photos aussi et le prix suggere »)
        try:
            if rapide:
                vc = {"ventes": [], "attente": True}
            else:                                          # 26 oct 2026 : les ventes de CETTE carte (pas de toute la recherche)
                vc = vendues.memes_annonce(t, q=q, n=16) if t else {"ventes": []}
        except Exception:
            vc = {"ventes": []}
        ventes = vc.get("ventes") or (self._mes_ventes_pareilles(t, item_id) if t else [])
        # 25 oct 2026 : la valeur = les ventes reelles (3 ou plus), sinon les annonces en vente
        # 26 oct 2026 (Mathieu : « encore pas un deal » : 6 annonces a 21 $, 1 vente a 3 $) : les annonces sont un PLAFOND ;
        # 1 ou 2 ventes : on les croit plus que les prix demandes ; aucune vente : pas de verdict deal / bon prix
        nb_v = vc.get("nb") or 0
        # 27 oct 2026 : pas (ou presque pas) de ventes de CETTE carte : celles de la meme carte par d'autres joueurs, en repere
        autres = None
        if not rapide and t and nb_v < 2:
            try:
                autres = vendues.autres_joueurs(t)
            except Exception:
                autres = None
        # 27 oct 2026 (Mathieu : « pas de faux deals ni de faux prix ») : une valeur SEULEMENT si les ventes reelles de
        # CETTE carte sont sures (deals.valeur_sure) ; les annonces ne font que la plafonner. Sinon : aucun « vaut ».
        import deals as _deals
        vm = _deals.valeur_sure([x for x in (vc.get("ventes") or []) if x.get("prix")], t or "")[0] if nb_v >= 2 else None
        if vm and med and n >= 3 and vm > med:
            vm = min(vm, round(med * 0.85, 2))
        valeur = vm
        juger = bool(vm)
        suggere = None
        if valeur and (vm or n >= 3):
            pv = sorted(x["prix"] for x in ventes if x.get("prix")) if vm else sorted(x["total"] for x in comps)
            vente = pv[max(0, int(len(pv) * 0.6) - 1)] if len(pv) >= 3 else valeur     # vendues : un peu au-dessus du milieu
            suggere = {"vente": round(vente if vm else min(vente, valeur), 2),
                       "achat_max": round(max(0.0, (valeur * (1 - fp) - ff) / 1.20), 2), "source": "vendues" if vm else "annonces"}
        # 26 oct 2026 (Mathieu : « les deals sont pas bons avec les last sold ») : la fenetre a les ventes de CETTE carte ;
        # si elles disent que ce n'est pas un deal, l'annonce sort des deals de tout le monde (et sa valeur est corrigee)
        if not rapide and total:
            try:
                import deals as _dl
                gain_v = round(valeur * (1 - fp) - ff - total, 2) if valeur and juger else None
                _dl.corriger(item_id, valeur if juger else None, gain_v, total)
            except Exception:
                pass
        if not ebay_prix_actif():                # interrupteur : l'annonce seule, sans valeur ni rabais
            return {"ok": True, "article": {**a, "total": total}, "comps": [], "n": 0, "coupe": True}
        return {"ok": True, "article": {**a, "total": total}, "comps": comps, "mediane": med, "n": n,
                "suggere": suggere, "ventes": ventes, "mediane_vendue": vc.get("mediane"), "nb_vendues": vc.get("nb") or len(ventes),
                "valeur": valeur, "valeur_source": "vendues" if vm else "annonces", "ventes_attente": bool(vc.get("attente")),
                "points": vc.get("points") or [], "tendance": vc.get("tendance"), "autres_joueurs": autres,
                "rabais": round(100 * (1 - total / valeur)) if total and valeur and juger else None,
                "gain": round(valeur * (1 - fp) - ff - total, 2) if total and valeur and juger else None,
                "peu_de_ventes": not juger}

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
               "nb": d.get("n") or g.get("n"), "recherche": g.get("q") or d.get("q"), "url": d.get("url") or g.get("url"),
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
        return {"mois": m0, "deals": deals[:24], "nb_deals": len(deals), "gain_deals": round(sum(max(0, d["gain"]) for d in deals), 2),
                "achats": {"n": len(achats), "depense": depense, "valeur": valeur,
                           "latent": round(sum(((a.get("valeur") or a.get("prix_demande") or 0) * (1 - fp) - ff - (a["cout"] or 0))
                                             for a in achats if a.get("valeur") or a.get("prix_demande")), 2)},
                "cles": ebay_compte.statut().get("cles_ok"), "ebay": ebay_compte.statut().get("connecte"),
                "nom_boutique": r["nom_boutique"]}

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
            x["gain"] = round(valeur * (1 - fp) - ff - x["total"], 2) if valeur else None
            x["hors_norme"] = x["total"] not in garde
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
