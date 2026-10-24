"""
LOCKERROOM - avis « Marketplace Account Deletion » d'eBay (obligatoire en production).

eBay exige que chaque application qui garde des donnees de comptes eBay ecoute ces
avis : sans adresse qui repond, eBay desactive les cles de production.
  GET  /ebay/suppression-compte?challenge_code=...  -> {"challengeResponse": sha256(code + jeton + adresse)}
  POST /ebay/suppression-compte                      -> compte supprime chez eBay : on oublie ses jetons

Reglage (ebay_avis.json, a cote de ce fichier) : l'adresse PUBLIQUE exacte (https://...)
et le jeton de verification (32 a 80 caracteres) - les deux sont colles dans
developer.ebay.com > Alerts & Notifications.
"""
import hashlib
import json
import os
import secrets
from datetime import datetime

DOSSIER = os.environ.get("LOCKERROOM_DONNEES") or os.path.dirname(os.path.abspath(__file__))
CHEMIN = os.path.join(DOSSIER, "ebay_avis.json")
CHEMIN_JOURNAL = os.path.join(DOSSIER, "ebay_avis_journal.jsonl")


def _lire():
    try:
        with open(CHEMIN, encoding="utf-8") as f:
            c = json.load(f) or {}
    except (OSError, ValueError):
        c = {}
    # 24 oct 2026 - heberge (Render) : le jeton et l'adresse viennent du serveur, rien a regler dans l'app.
    # Jeton : LOCKERROOM_EBAY_AVIS_JETON (32 a 80 lettres, chiffres, _ ou -), le meme que dans developer.ebay.com.
    # Adresse : LOCKERROOM_EBAY_AVIS_ADRESSE, sinon l'adresse publique donnee par Render.
    j = (os.environ.get("LOCKERROOM_EBAY_AVIS_JETON") or "").strip()
    if j:
        c["jeton"] = j
    a = (os.environ.get("LOCKERROOM_EBAY_AVIS_ADRESSE") or "").strip()
    if not a and os.environ.get("RENDER_EXTERNAL_URL"):
        a = os.environ["RENDER_EXTERNAL_URL"].strip().rstrip("/") + "/ebay/suppression-compte"
    if a:
        c["adresse"] = a
    return c


def jeton_valide(j):
    import re
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{32,80}", j or ""))


def reglage(adresse=None):
    c = _lire()
    if not c.get("jeton"):
        c["jeton"] = secrets.token_urlsafe(48)[:64].replace("-", "_")
    if adresse is not None:
        c["adresse"] = str(adresse).strip()
    with open(CHEMIN, "w", encoding="utf-8") as f:
        json.dump(c, f)
    return c


def statut():
    c = _lire()
    return {"adresse": c.get("adresse") or "", "jeton_fin": ("•••• " + c["jeton"][-4:]) if c.get("jeton") else "",
            "pret": bool(c.get("adresse", "").startswith("https://") and c.get("jeton"))}


def reponse_defi(code):
    c = _lire()
    if not c.get("jeton"):
        c = reglage()
    if not c.get("adresse"):
        raise RuntimeError("Adresse publique des avis eBay non configurée")
    h = hashlib.sha256((str(code) + c["jeton"] + c["adresse"]).encode("utf-8")).hexdigest()
    return {"challengeResponse": h}


def recevoir(corps):
    """Compte supprime chez eBay : journalise et retire les jetons de ce compte.
    (Verification de la signature x-ebay-signature : a ajouter avec la cle publique
    de l'API Notification avant la mise en production multi-comptes.)"""
    try:
        d = json.loads(corps or b"{}")
    except ValueError:
        d = {}
    data = (d.get("notification") or {}).get("data") or {}
    with open(CHEMIN_JOURNAL, "a", encoding="utf-8") as f:
        f.write(json.dumps({"le": datetime.now().isoformat(timespec="seconds"), "topic": (d.get("metadata") or {}).get("topic"),
                            "username": data.get("username"), "userId": data.get("userId")}) + "\n")
    import comptes
    import ebay_compte
    if comptes.MULTI:                    # multi-comptes : tout le dossier du client disparait
        for cid in comptes.par_username(data.get("username")):
            comptes.supprimer(cid)
        return True
    for env in ebay_compte.ENVIRONNEMENTS:
        chemin = os.path.join(ebay_compte.DOSSIER, ebay_compte.ENVIRONNEMENTS[env]["jetons"])
        j = ebay_compte._lire(chemin)
        if j.get("compte") and data.get("username") and j.get("compte").lower() == str(data.get("username")).lower():
            for k in ("access_token", "access_expire_a", "refresh_token", "refresh_expire_a", "compte", "scopes"):
                j.pop(k, None)
            ebay_compte._ecrire(chemin, j)
            _effacer_donnees_ebay(env)
    return True


def _effacer_donnees_ebay(env):
    """Le compte eBay connecte a ete supprime chez eBay : on efface ce qui vient de lui
    (annonces et ventes importees d'eBay). Ce que le vendeur a saisi lui-meme reste."""
    import sqlite3
    import lockerroom
    chemin = lockerroom.CHEMIN_DB if env == "production" else os.path.join(lockerroom.DOSSIER, "lockerroom_sandbox.db")
    if not os.path.exists(chemin):
        return
    c = sqlite3.connect(chemin, timeout=30)
    try:
        c.execute("DELETE FROM cartes WHERE source LIKE '%ebay%'")
        c.execute("UPDATE cartes SET item_number=NULL WHERE item_number IS NOT NULL")
        c.execute("DELETE FROM ventes_ebay_vues")
        for t in ("sante", "opportunites", "rachats_vus"):
            try:
                c.execute(f"DELETE FROM {t}")
            except sqlite3.OperationalError:
                pass
        c.commit()
    finally:
        c.close()
