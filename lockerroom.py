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
from datetime import datetime, timedelta

import calcul
import catalogue
import ebay_compte
import ebay_csv
import sante
import sports
import valeurs
import vision

DOSSIER = os.environ.get("LOCKERROOM_DONNEES") or os.path.dirname(os.path.abspath(__file__))   # heberge : disque persistant
CHEMIN_DB = os.path.join(DOSSIER, "lockerroom.db")
_verrou = threading.RLock()

REGLAGES_DEFAUT = {
    "nom_boutique": "Ma boutique",
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
    "langue": "",                # 24 oct 2026 - "fr" ou "en" (vide = celle du navigateur)
    "devise": "",                # 24 oct 2026 - "CAD" ou "USD" (affichage ; les montants restent gardes en $ CA)
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


def _connecter(chemin=None):
    c = sqlite3.connect(chemin or CHEMIN_DB, timeout=30)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    cols = {r[1] for r in c.execute("PRAGMA table_info(breaks)")}
    if "catalogue_id" not in cols:                 # 18 oct 2026 - break fait a partir du catalogue
        c.execute("ALTER TABLE breaks ADD COLUMN catalogue_id TEXT")
        c.commit()
    # 18 oct 2026 - sante de l'inventaire (tous les articles eBay)
    cols = {r[1] for r in c.execute("PRAGMA table_info(cartes)")}
    for col, typ in (("debut", "TEXT"), ("watchers", "INTEGER"), ("categorie_ebay", "TEXT"), ("photo", "TEXT"), ("vu_actif_le", "TEXT"),
                     ("sport", "TEXT")):
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
    c.commit()
    return c


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
        # 24 oct 2026 - heberge : la campagne eBay Partner Network est celle de LockerRoom (serveur), pour tous les clients
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
                                         headers={"User-Agent": "LockerRoom"})
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
        return {"multi": multi, "forfait": (info.get("forfait") or "gratuit") if multi else "pro",
                "statut": info.get("forfait_statut") or "", "fin": info.get("forfait_fin"),
                "annule": bool(info.get("forfait_annule")), "client": bool(info.get("stripe_client")),
                "paiements": paiements.actif(), "mode_paiement": paiements.mode(), "prix": prix,
                "photos_mois": photos.get("ce_mois"), "photos_limite": photos.get("limite"),
                "gratuit_photos": vision.QUOTA_GRATUIT}

    def abonnement_payer(self):
        import comptes
        import paiements
        cid = comptes.courant() if comptes.MULTI else None
        if not cid:
            return {"ok": False, "erreur": "Le forfait Pro se prend dans la version en ligne"}
        try:
            return {"ok": True, "url": paiements.creer_paiement(cid, (comptes.info(cid) or {}).get("stripe_client"))}
        except paiements.Erreur as e:
            return {"ok": False, "erreur": str(e)}

    def abonnement_gerer(self):
        import comptes
        import paiements
        cid = comptes.courant() if comptes.MULTI else None
        try:
            return {"ok": True, "url": paiements.portail((comptes.info(cid) or {}).get("stripe_client") if cid else None)}
        except paiements.Erreur as e:
            return {"ok": False, "erreur": str(e)}

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
        return vision.statut()

    def photo_identifier(self, photos):
        """1 ou 2 photos (devant, dos) -> fiche pre-remplie. Rien n'est enregistre : l'ecran montre
        la fiche (champs douteux en or) et l'utilisateur touche « Enregistrer »."""
        try:
            r = vision.identifier(photos if isinstance(photos, list) else [photos])
        except vision.Erreur as e:
            return {"ok": False, "erreur": str(e)}
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
        """Produits du catalogue + valeur attendue par boite (algo LockerRoom)."""
        cle = (valeurs.statut().get("maj"), tuple(sorted(os.listdir(catalogue.DOSSIER))) if os.path.isdir(catalogue.DOSSIER) else ())
        out = []
        for p in catalogue.liste():
            k = (cle, p["id"])
            if k not in self._EV_CACHE:
                prod = catalogue.charger(p["id"])
                self._EV_CACHE[k] = calcul.prix_catalogue(prod, boites=1)["ev_par_boite"]
            out.append(dict(p, ev_par_boite=self._EV_CACHE[k]))
        return {"produits": out, "valeurs": valeurs.statut()}

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
                    "note", "client_id", "sport")

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
            sql += " AND statut='En stock' AND COALESCE(emplacement,'')!='Magasin'"
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
        for r in out:
            if not r.get("sport"):
                r["sport"] = sports.detecter(r.get("titre"), r.get("equipe"), r.get("set_nom"), r.get("marque"), defaut=defaut)
        if f.get("sport"):
            out = [r for r in out if r["sport"] == f["sport"]]
        return out

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

    def carte_supprimer(self, cid):
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
        for a in a_faire[:int(n)]:
            q = sante.requete(a["titre"])
            try:
                semblables = [s for s in ebay_compte.rechercher(q, a.get("categorie_ebay")) if s["item_id"] != str(a["item_number"])]
            except (RuntimeError, OSError) as e:
                erreur = str(e)
                break
            ev = sante.evaluer(a["prix_demande"], semblables, sante.age_jours(a.get("debut")), a.get("watchers"))
            with _verrou:
                c = self._db()
                try:
                    c.execute("INSERT OR REPLACE INTO sante (item_number, maj, verdict, suggestion, mediane, n, ecart, requete, fait) "
                              "VALUES (?,?,?,?,?,?,?,?,0)", (a["item_number"], _maintenant(), ev["verdict"], ev["suggestion"], ev["mediane"],
                                                            ev["n"], ev["ecart"], q))
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
        for v in vendues:
            q = sante.requete(v["titre"])
            if not q or vus.get(q, "") > limite:
                continue
            if faites >= n:
                break
            faites += 1
            try:
                res = ebay_compte.rechercher(q, v.get("categorie_ebay"), prix_max=v["prix_vendu"] * sante.RACHAT_RATIO, recentes=True, limite=20)
            except (RuntimeError, OSError):
                break
            ops = sante.opportunites(v["prix_vendu"], res, exclure=mes)
            with _verrou:
                c = self._db()
                try:
                    c.execute("INSERT OR REPLACE INTO rachats_vus VALUES (?,?)", (q, _maintenant()))
                    for o in ops[:3]:
                        c.execute("INSERT OR IGNORE INTO opportunites (item_id, titre, total, url, photo, ref_titre, ref_prix, ratio, vu_le) "
                                  "VALUES (?,?,?,?,?,?,?,?,?)", (o["item_id"], o["titre"], o["total"], o["url"], o["photo"], v["titre"],
                                                                  v["prix_vendu"], o["ratio"], _maintenant()))
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
        with _verrou:
            c = self._db()
            try:
                if verdict == "racheter":
                    limite = (datetime.now() - timedelta(days=4)).isoformat()
                    return _dicts(c.execute("SELECT * FROM opportunites WHERE masque=0 AND vu_le >= ? ORDER BY ratio LIMIT 100", (limite,)))
                actives = {a["item_number"]: a for a in self._annonces_actives(c)}
                out = []
                for s in _dicts(c.execute("SELECT * FROM sante WHERE verdict=? AND fait=0", (verdict,))):
                    a = actives.get(s["item_number"])
                    if a:
                        out.append({**s, "titre": a["titre"], "prix": a["prix_demande"], "photo": a.get("photo"), "watchers": a.get("watchers"),
                                    "age": sante.age_jours(a.get("debut")), "carte_id": a["id"]})
            finally:
                c.close()
        cle = {"baisser": lambda x: -(x.get("ecart") or 0), "monter": lambda x: x.get("ecart") or 0,
               "traine": lambda x: -(x.get("age") or 0)}.get(verdict, lambda x: 0)
        return sorted(out, key=cle)

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
        import ebay_ecriture
        try:
            r = getattr(ebay_ecriture, fn)(*args, **kw)
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
            with _verrou:
                c = self._db()
                try:
                    c.execute("UPDATE cartes SET item_number=?, sku=?, statut='Listée', prix_demande=?, debut=? WHERE id=?",
                              (r["item_id"], sku, prix, _maintenant(), cid))
                    c.commit()
                finally:
                    c.close()
        return r

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
        bilan = {"annonces": a.get("lues"), "nouvelles_annonces": a.get("crees"), "ventes": v.get("nouvelles"),
                 "deja": v.get("deja"), "le": _maintenant()}
        ebay_compte.noter_synchro(bilan)
        return {"ok": True, **bilan}

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
                a_lister = c.execute("SELECT COUNT(*) FROM cartes WHERE statut='En stock' AND emplacement!='Magasin'").fetchone()[0]
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
    def accueil_live(self):
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
        n = nouvelles.pour(ordre[:3], joueurs[:300])
        st = ebay_compte.statut()
        pouls = []
        if st.get("connecte"):
            pouls.append({"id": "ebay", "nom": "eBay", "dernier": st.get("derniere_synchro"), "freq_min": 60,
                          "href": "#reglages", "note": "annonces, ventes, frais"})
        if st.get("cles_ok"):
            pouls.append({"id": "sante", "nom": "Tes prix", "dernier": sante_maj, "freq_min": 60, "href": "#sante"})
            pouls.append({"id": "deals", "nom": "Deals", "dernier": opp_maj, "freq_min": 60, "href": "#deals"})
        pouls.append({"id": "valeurs", "nom": "Joueurs", "dernier": valeurs.statut().get("maj"), "freq_min": 1440,
                      "href": "#reglages", "note": "chaque jour"})
        pouls.append({"id": "nouvelles", "nom": "Infos", "dernier": n.get("maj"), "freq_min": 120, "href": "#accueil"})
        for p in pouls:
            p["dernier"] = str(p["dernier"])[:19] if p.get("dernier") else None
        return {"ok": True, "nouvelles": n["items"], "sports": ordre[:3], "pouls": pouls,
                "maintenant": datetime.now().isoformat(timespec="seconds")}

    def acheteur_accueil(self):
        """Deals a acheter (annonces bien sous ce que la carte vaut), achats du mois, valeur du stock achete."""
        maint = datetime.now()
        m0 = maint.strftime("%Y-%m")
        r = self.reglages_lire()
        fp, ff = (r["frais_ebay_pct"] or 0) / 100, r["frais_ebay_fixe"] or 0
        limite = (maint - timedelta(days=4)).isoformat()
        with _verrou:
            c = self._db()
            try:
                opps = _dicts(c.execute("SELECT * FROM opportunites WHERE masque=0 AND vu_le >= ? ORDER BY ratio LIMIT 60", (limite,)))
                achats = _dicts(c.execute("SELECT * FROM cartes WHERE cout IS NOT NULL AND substr(cree_le,1,7)=?", (m0,)))
                dep = c.execute("SELECT COALESCE(SUM(montant),0) FROM depenses WHERE substr(le,1,7)=? AND categorie='achats'", (m0,)).fetchone()[0]
            finally:
                c.close()
        deals = []
        for o in opps:
            gain = round((o.get("ref_prix") or 0) * (1 - fp) - ff - (o.get("total") or 0), 2)
            deals.append({**o, "gain": gain, "rabais": round(100 * (1 - (o.get("ratio") or 1)))})
        deals.sort(key=lambda d: -d["gain"])
        depense = round(sum(a["cout"] or 0 for a in achats) + (dep or 0), 2)
        valeur = round(sum((a.get("valeur") or a.get("prix_demande") or 0) for a in achats), 2)
        return {"mois": m0, "deals": deals, "nb_deals": len(deals), "gain_deals": round(sum(max(0, d["gain"]) for d in deals), 2),
                "achats": {"n": len(achats), "depense": depense, "valeur": valeur,
                           "latent": round(sum(((a.get("valeur") or a.get("prix_demande") or 0) * (1 - fp) - ff - (a["cout"] or 0))
                                             for a in achats if a.get("valeur") or a.get("prix_demande")), 2)},
                "cles": ebay_compte.statut().get("cles_ok"), "ebay": ebay_compte.statut().get("connecte"),
                "nom_boutique": r["nom_boutique"]}

    def valeur_carte(self, q):
        """« Combien vaut cette carte ? » : annonces actives a prix fixe (eBay Browse, cache partage),
        prix median et le prix a ne pas depasser pour revendre avec profit (70 % du median)."""
        q = re.sub(r"\s+", " ", str(q or "")).strip()
        if len(q) < 3:
            return {"ok": False, "erreur": "Écris le joueur et la carte (ex. Bedard Young Guns)."}
        try:
            res = ebay_compte.rechercher(q, limite=50, fond=False)
        except (RuntimeError, OSError) as e:
            return {"ok": False, "erreur": str(e)}
        r = self.reglages_lire()
        fp, ff = (r["frais_ebay_pct"] or 0) / 100, r["frais_ebay_fixe"] or 0
        lst = []
        for a in res or []:
            total = round((a.get("prix_cad") or 0) + (a.get("port_cad") or 0), 2)
            if total > 0:
                lst.append({**a, "total": total})
        lst.sort(key=lambda x: x["total"])
        if not lst:
            return {"ok": True, "q": q, "n": 0, "annonces": []}
        t = [x["total"] for x in lst]
        med = t[len(t) // 2] if len(t) % 2 else round((t[len(t) // 2 - 1] + t[len(t) // 2]) / 2, 2)
        bon = round(med * sante.RACHAT_RATIO, 2)
        for x in lst:
            x["deal"] = x["total"] <= bon
            x["gain"] = round(med * (1 - fp) - ff - x["total"], 2)
        return {"ok": True, "q": q, "n": len(lst), "mediane": med, "bon_prix": bon, "min": t[0], "max": t[-1], "annonces": lst[:40]}

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
                opps = _dicts(c.execute("SELECT * FROM opportunites WHERE masque=0 AND vu_le >= ?", (limite,)))
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
        a_lister = [k for k in stock if k.get("statut") == "En stock" and (k.get("emplacement") or "") != "Magasin"]
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

        analysees = sum(1 for it in act if it in sante_)
        derniere = max((sv.get("maj") or "" for it, sv in sante_.items() if it in act), default=None)
        return {"hero": hero, "actions": actions, "coups": coups[:3],
                "stock": {"valeur": round(valeur, 2), "cout": round(cout, 2), "latent": round(latent, 2), "nb": len(stock),
                          "ages": {k: {"n": v[0], "montant": round(v[1], 2)} for k, v in ages.items()}},
                "vitesse": vitesse, "analyse": {"actives": len(actives), "analysees": analysees, "maj": derniere},
                "breaks_ouverts": [x for x in brk if x["statut"] != "ferme"][:5], "a_envoyer": a_env,
                "activites": self.activites(), "nom_boutique": r["nom_boutique"],
                "ebay": ebay_compte.statut().get("connecte"), "cles": ebay_compte.statut().get("cles_ok")}

    @staticmethod
    def _delai(v):
        try:
            a = datetime.fromisoformat(str(v.get("debut") or v.get("cree_le"))[:19].replace("Z", ""))
            b = datetime.fromisoformat(str(v.get("vendu_le"))[:19].replace("Z", ""))
            return max(0, (b - a).days)
        except (TypeError, ValueError):
            return None


def random_ordre(lots, graine):
    import random
    l = list(lots)
    random.Random(graine + ":reste").shuffle(l)
    return l
