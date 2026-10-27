"""
LOCKERROOM - avis « Marketplace Account Deletion » d'eBay (obligatoire en production).

eBay exige que chaque application qui garde des donnees de comptes eBay ecoute ces
avis : sans adresse qui repond, eBay desactive les cles de production.
  GET  /ebay/suppression-compte?challenge_code=...  -> {"challengeResponse": sha256(code + jeton + adresse)}
  POST /ebay/suppression-compte                      -> compte supprime chez eBay : signature verifiee, puis on efface

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


_CLES_PUBLIQUES = {}          # kid -> (cle PEM, digest, lu_le) : 1 h
TOPIC = "MARKETPLACE_ACCOUNT_DELETION"


def _cle_publique(kid):
    """Cle publique d'eBay pour ce kid (API Notification, jeton d'application)."""
    import time
    import urllib.parse
    import urllib.request
    import ebay_compte
    e = _CLES_PUBLIQUES.get(kid)
    if e and time.time() - e[2] < 3600:
        return e
    req = urllib.request.Request(ebay_compte._env()["api"] + "/commerce/notification/v1/public_key/" + urllib.parse.quote(kid, safe=""),
                                 headers={"Authorization": "Bearer " + ebay_compte.jeton_application(), "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read())
    brut = "".join(str(d.get("key") or "").replace("-----BEGIN PUBLIC KEY-----", "").replace("-----END PUBLIC KEY-----", "").split())
    pem = "-----BEGIN PUBLIC KEY-----\n" + "\n".join(brut[i:i + 64] for i in range(0, len(brut), 64)) + "\n-----END PUBLIC KEY-----\n"
    e = (pem, str(d.get("digest") or "SHA1").upper(), time.time())
    _CLES_PUBLIQUES[kid] = e
    return e


def signature_valide(corps, entete, lire_cle=None):
    """27 oct 2026 (revue) : l'avis vient-il vraiment d'eBay ? En-tete X-EBAY-SIGNATURE = base64(JSON {alg, kid, signature,
    digest}) ; signature ECDSA du corps brut avec la cle publique d'eBay. Sans signature valide : on ne supprime RIEN."""
    import base64
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    try:
        if isinstance(entete, bytes):
            entete = entete.decode("ascii", "ignore")
        h = json.loads(base64.b64decode(str(entete or "")))
        kid, sig = h.get("kid"), base64.b64decode(h.get("signature") or "")
        if not kid or not sig:
            return False
        pem, digest, _ = (lire_cle or _cle_publique)(kid)
        cle = serialization.load_pem_public_key(pem.encode())
        algo = hashes.SHA256() if "256" in str(h.get("digest") or digest) else hashes.SHA1()
    except Exception:
        return False
    corps = corps or b""
    essais = [corps]
    try:                                   # meme JSON, ecrit sans espaces (comme le SDK d'eBay)
        essais.append(json.dumps(json.loads(corps), separators=(",", ":"), ensure_ascii=False).encode())
    except ValueError:
        pass
    for m in essais:
        try:
            cle.verify(sig, m, ec.ECDSA(algo))
            return True
        except (InvalidSignature, ValueError):
            continue
    return False


def recevoir(corps, entete=None, lire_cle=None):
    """Compte supprime chez eBay -> True si l'avis est authentique (sinon False : 412, rien n'est touche).
    27 oct 2026 (revue de securite) : signature verifiee, sujet verifie, et on cherche le compte par son identifiant
    eBay (userId) seulement : un nom d'utilisateur est public et pourrait viser quelqu'un d'autre."""
    if not signature_valide(corps, entete, lire_cle):
        return False
    try:
        d = json.loads(corps or b"{}")
    except ValueError:
        return False
    if (d.get("metadata") or {}).get("topic") != TOPIC:
        return True                          # autre sujet : rien a faire, mais l'avis est recu
    data = (d.get("notification") or {}).get("data") or {}
    uid, nom = str(data.get("userId") or "").strip(), str(data.get("username") or "").strip()
    import comptes
    import ebay_compte
    trouves = 0
    if comptes.MULTI and uid:                # multi-comptes : tout le dossier du client disparait
        ix = set(comptes.lister())
        cids = set(comptes.par_champ("ebay_user_id", uid)) | {c for c in (comptes.id_pour(uid, e) for e in ebay_compte.ENVIRONNEMENTS) if c in ix}
        for cid in cids:                     # aussi un compte Apple / Google relie a ce compte eBay
            comptes.supprimer(cid)
        trouves = len(cids)
        if cids:
            try:
                import ventes_communaute
                ventes_communaute.rafraichir()
            except Exception:
                pass
    elif not comptes.MULTI:
        for env in ebay_compte.ENVIRONNEMENTS:
            chemin = os.path.join(ebay_compte.DOSSIER, ebay_compte.ENVIRONNEMENTS[env]["jetons"])
            j = ebay_compte._lire(chemin)
            if (uid and j.get("ebay_user_id") == uid) or (nom and str(j.get("compte") or "").lower() == nom.lower()):
                try:
                    os.remove(chemin)        # tous les jetons et reglages eBay de ce compte
                except OSError:
                    pass
                _effacer_donnees_ebay(env)
                trouves += 1
        if trouves:
            try:
                os.remove(os.path.join(ebay_compte.DOSSIER, "ebay_ecriture_journal.jsonl"))
            except OSError:
                pass
    # journal sans donnees personnelles : eBay avise pour TOUS les comptes supprimes, pas seulement les notres
    with open(CHEMIN_JOURNAL, "a", encoding="utf-8") as f:
        f.write(json.dumps({"le": datetime.now().isoformat(timespec="seconds"), "trouves": trouves}) + "\n")
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
        try:
            c.execute("DELETE FROM achats_ebay")       # ses achats eBay
        except sqlite3.OperationalError:
            pass
        for t in ("sante", "opportunites", "rachats_vus"):
            try:
                c.execute(f"DELETE FROM {t}")
            except sqlite3.OperationalError:
                pass
        c.commit()
    finally:
        c.close()
