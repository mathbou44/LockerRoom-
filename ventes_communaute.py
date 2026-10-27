"""
LOCKERROOM - les vraies ventes de la communaute (25 oct 2026).

Mathieu : « ou sont tous les last sold comp ? on compare juste aux comparables eBay en ce moment ».
eBay ne donne les ventes terminees (Marketplace Insights) qu'aux grands partenaires. SlabCoach a mieux :
les ventes REELLES des comptes eBay connectes a l'app (deja importees dans chaque inventaire), mises en commun.

  - anonymes : ni vendeur, ni acheteur, ni numero d'annonce ; juste titre, prix vendu (+ port), date, photo ;
  - production seulement (jamais le sandbox) ; 365 derniers jours ;
  - chaque compte peut refuser (Reglages : « Partager mes ventes, anonymes ») ;
  - refait chaque jour en arriere-plan ; lecture : les MEMES cartes (cartes_match), les plus recentes d'abord.
"""
import hashlib
import json
import os
import re
import secrets
import sqlite3
import statistics
import threading
import time
from datetime import datetime, timedelta

FRAICHEUR_S = 24 * 3600
JOURS = 365
_verrou = threading.Lock()
_ETAT = {"en_cours": False}


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "ventes_communaute.sqlite")


def _sel():
    """Sel secret (sur le disque du serveur) : la cle d'une vente ne permet pas de retrouver le compte."""
    import comptes
    ch = os.path.join(comptes.DONNEES, ".sel_ventes")
    try:
        with open(ch, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        s = secrets.token_hex(16)
        with open(ch, "w", encoding="utf-8") as f:
            f.write(s)
        return s


def _cx():
    c = sqlite3.connect(_chemin(), timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS ventes (cle TEXT PRIMARY KEY, titre TEXT, titre_n TEXT, prix REAL, vendu_le TEXT, "
              "photo TEXT, sport TEXT, maj TEXT)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_ventes_le ON ventes(vendu_le)")
    c.execute("CREATE TABLE IF NOT EXISTS etat (k TEXT PRIMARY KEY, v TEXT)")
    return c


def _bases():
    """[(compte, chemin de la base de production)] : chaque client en ligne, ou la base du PC."""
    import comptes
    if comptes.MULTI:
        out = []
        for cid in comptes.lister():
            info = comptes.info(cid) or {}
            if info.get("env") and info.get("env") != "production":
                continue
            ch = os.path.join(comptes.DOSSIER_COMPTES, cid, "lockerroom.db")
            if os.path.exists(ch):
                out.append((cid, ch))
        return out
    import lockerroom
    return [("local", lockerroom.CHEMIN_DB)] if os.path.exists(lockerroom.CHEMIN_DB) else []


def _partage(c):
    """Le compte partage-t-il ses ventes ? 27 oct 2026 (Apple 5.1.1(ii), Loi 25) : seulement apres un OUI clair ;
    sans reponse, non (Reglages : « partage_ventes »)."""
    try:
        r = c.execute("SELECT v FROM reglages WHERE k='partage_ventes'").fetchone()
        return False if r is None else json.loads(r[0]) is True
    except (sqlite3.Error, ValueError):
        return False


def rafraichir():
    import cartes_match
    sel = _sel()
    depuis = (datetime.now() - timedelta(days=JOURS)).strftime("%Y-%m-%d")
    ici = datetime.now().isoformat(timespec="seconds")
    n = comptes_n = 0
    lignes = []
    for cid, ch in _bases():
        try:
            src = sqlite3.connect("file:" + ch + "?mode=ro", uri=True, timeout=10)
            src.row_factory = sqlite3.Row
            if not _partage(src):
                src.close()
                continue
            cols = {r[1] for r in src.execute("PRAGMA table_info(cartes)")}       # vieille base : colonnes manquantes
            sel_ = ", ".join(k if k in cols else f"NULL AS {k}" for k in ("id", "item_number", "titre", "joueur", "prix_vendu",
                                                                        "port_charge", "vendu_le", "photo", "sport"))
            rows = src.execute(f"SELECT {sel_} FROM cartes WHERE statut='Vendue' AND prix_vendu > 0 AND COALESCE(vendu_le,'') >= ?",
                               (depuis,)).fetchall()
            src.close()
        except sqlite3.Error as e:
            print("Ventes communaute (" + str(cid)[:6] + ") : " + str(e), flush=True)
            continue
        comptes_n += 1
        for r in rows:
            titre = r["titre"] or r["joueur"] or ""
            if not titre or not cartes_match.est_carte(titre):
                continue
            cle = hashlib.sha256(f"{sel}|{cid}|{r['item_number'] or r['id']}".encode()).hexdigest()[:24]
            photo = r["photo"] if str(r["photo"] or "").startswith("http") else None        # jamais une photo privee (data:)
            lignes.append((cle, titre[:200], cartes_match.norm(titre), round(float(r["prix_vendu"] or 0), 2),     # 27 oct 2026 : sans le port, comme les ventes SoldComps
                           str(r["vendu_le"] or "")[:10], photo, r["sport"], ici))
            n += 1
    with _verrou:
        c = _cx()
        try:
            c.execute("DELETE FROM ventes")                # refait au complet : un compte qui refuse disparait aussi
            c.executemany("INSERT OR REPLACE INTO ventes VALUES (?,?,?,?,?,?,?,?)", lignes)
            c.execute("INSERT OR REPLACE INTO etat VALUES ('maj', ?)", (ici,))
            c.execute("INSERT OR REPLACE INTO etat VALUES ('comptes', ?)", (str(comptes_n),))
            c.commit()
        finally:
            c.close()
    return {"ok": True, "ventes": n, "comptes": comptes_n}


def statut():
    try:
        c = _cx()
        try:
            e = dict(c.execute("SELECT k, v FROM etat").fetchall())
            n = c.execute("SELECT COUNT(*) FROM ventes").fetchone()[0]
        finally:
            c.close()
        return {"maj": e.get("maj"), "comptes": int(e.get("comptes") or 0), "ventes": n}
    except sqlite3.Error:
        return {"maj": None, "comptes": 0, "ventes": 0}


def rafraichir_si_besoin():
    st = statut()
    try:
        age = time.time() - datetime.fromisoformat(str(st.get("maj"))).timestamp()
    except ValueError:
        age = 1e9
    if age < FRAICHEUR_S or _ETAT["en_cours"]:
        return False
    _ETAT["en_cours"] = True

    def tache():
        try:
            rafraichir()
        except Exception as e:
            print("Ventes communaute : " + repr(e), flush=True)
        finally:
            _ETAT["en_cours"] = False
    threading.Thread(target=tache, daemon=True, name="ventes_communaute").start()
    return True


def chercher(titre, requete=False, n=12):
    """Les MEMES cartes vendues : {ventes:[{titre, prix, le, photo}], mediane, nb, derniere}.
    titre = le titre d'une annonce, ou (requete=True) ce que l'utilisateur a tape (« will smith young guns »)."""
    import cartes_match
    joueur = str(cartes_match.joueur_du_titre(titre) or "")
    nom = (joueur.split() or [""])[-1]
    if len(nom) < 3:
        return {"ventes": [], "mediane": None, "nb": 0}
    try:
        c = _cx()
        try:
            rows = [dict(r) for r in c.execute("SELECT titre, prix, vendu_le, photo FROM ventes WHERE titre_n LIKE ? "
                                               "ORDER BY vendu_le DESC LIMIT 400", (f"%{nom}%",))]
        finally:
            c.close()
    except sqlite3.Error:
        return {"ventes": [], "mediane": None, "nb": 0}
    if requete:
        cib = cartes_match.cible(titre)
        memes = [r for r in rows if not cartes_match.raisons_refus(cib, r["titre"] or "")]
    else:
        _c, memes, _e = cartes_match.filtrer_carte(titre, [{**r, "item_id": str(i)} for i, r in enumerate(rows)])
    prix = [x["prix"] for x in memes if x.get("prix")]
    med = round(statistics.median(prix), 2) if len(prix) >= 2 else (prix[0] if prix else None)
    return {"ventes": [{"titre": x["titre"], "prix": x["prix"], "le": x["vendu_le"], "photo": x.get("photo")} for x in memes[:n]],
            "mediane": med, "nb": len(memes), "derniere": memes[0]["vendu_le"] if memes else None}
