"""
SLABCOACH - achat integre Apple (In-App Purchase, StoreKit 2) - 27 oct 2026.

Pourquoi : Apple (regles 3.1.1 et 3.1.3(b)) refuse qu'une app iPhone debloque un Pro achete sur le site si ce Pro ne
peut pas aussi s'acheter DANS l'app. Le Pro se prend donc aussi avec l'identifiant Apple, dans l'app iPhone.

Comment :
  - l'app (plugin @capgo/native-purchases) achete le produit APPLE_IAP_PRODUIT avec un « appAccountToken » : un UUID
    tire du compte SlabCoach (jeton_compte), qui relie l'achat a CE compte ;
  - StoreKit 2 renvoie la transaction SIGNEE par Apple (JWS). Le serveur la verifie lui-meme, sans cle a configurer :
    chaine de certificats jusqu'a la racine Apple Root CA - G3 (epinglee ici), extensions Apple (OID) sur le
    certificat de signature et l'intermediaire, dates, puis la signature ES256 ;
  - ensuite Apple previent le serveur de chaque renouvellement, annulation, remboursement (App Store Server
    Notifications v2, route /apple/notifications, meme verification) ;
  - filet de securite : un Pro Apple dont la date de fin est passee (+ 3 jours) redevient Gratuit tout seul
    (forfaits.etat), meme si un avis d'Apple se perd.
Rien de secret ici : la racine d'Apple est publique (empreinte SHA-256 publiee par Apple).
"""
import base64
import hashlib
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

BUNDLE = os.environ.get("APPLE_BUNDLE_ID") or "com.slabcoach.app"
PRODUIT_DEFAUT = "com.slabcoach.app.pro.mensuel"
# Apple Root CA - G3 (https://www.apple.com/certificateauthority/), empreinte SHA-256 publiee par Apple
RACINE_G3 = (
    "MIICQzCCAcmgAwIBAgIILcX8iNLFS5UwCgYIKoZIzj0EAwMwZzEbMBkGA1UEAwwSQXBwbGUgUm9vdCBDQSAtIEczMSYwJAYDVQQL"
    "DB1BcHBsZSBDZXJ0aWZpY2F0aW9uIEF1dGhvcml0eTETMBEGA1UECgwKQXBwbGUgSW5jLjELMAkGA1UEBhMCVVMwHhcNMTQwNDMw"
    "MTgxOTA2WhcNMzkwNDMwMTgxOTA2WjBnMRswGQYDVQQDDBJBcHBsZSBSb290IENBIC0gRzMxJjAkBgNVBAsMHUFwcGxlIENlcnRp"
    "ZmljYXRpb24gQXV0aG9yaXR5MRMwEQYDVQQKDApBcHBsZSBJbmMuMQswCQYDVQQGEwJVUzB2MBAGByqGSM49AgEGBSuBBAAiA2IA"
    "BJjpLz1AcqTtkyJygRMc3RCV8cWjTnHcFBbZDuWmBSp3ZHtfTjjTuxxEtX/1H7YyYl3J6YRbTzBPEVoA/VhYDKX1DyxNB0cTddqX"
    "l5dvMVztK517IDvYuVTZXpmkOlEKMaNCMEAwHQYDVR0OBBYEFLuw3qFYM4iapIqZ3r6966/ayySrMA8GA1UdEwEB/wQFMAMBAf8w"
    "DgYDVR0PAQH/BAQDAgEGMAoGCCqGSM49BAMDA2gAMGUCMQCD6cHEFl4aXTQY2e3v9GwOAEZLuN+yRhHFD/3meoyhpmvOwgPUnPWT"
    "xnS4at+qIxUCMG1mihDK1A3UT82NQz60imOlM27jbdoXt2QfyFMm+YhidDkLF1vLUagM6BgD56KyKA==")
EMPREINTE_G3 = "63343abfb89a6a03ebb57e9b3f5fa7be7c4f5c756f3017b3a8c488c3653e9179"
OID_FEUILLE = x509.ObjectIdentifier("1.2.840.113635.100.6.11.1")   # certificat de signature App Store
OID_INTER = x509.ObjectIdentifier("1.2.840.113635.100.6.2.1")      # intermediaire Apple WWDR
_ESPACE = uuid.UUID("6c1f0f8e-3b8d-4f43-9a2e-7d5c2b1a9e01")       # ne jamais changer : relie les achats aux comptes
GRACE_FIN_S = 3 * 86400            # un avis d'Apple en retard ne coupe pas le Pro tout de suite
_verrou = threading.Lock()


class Refus(Exception):
    """Transaction ou avis refuse (signature, produit, compte...)."""


def produit():
    return (os.environ.get("APPLE_IAP_PRODUIT") or PRODUIT_DEFAUT).strip()


def sandbox_permis():
    """L'equipe d'Apple teste avec des achats « Sandbox » : permis par defaut (sinon l'app serait refusee)."""
    return os.environ.get("APPLE_IAP_SANDBOX", "1") != "0"


def jeton_compte(cid):
    """L'UUID qui relie un achat Apple a un compte SlabCoach (rien de lisible : derive de l'identifiant opaque)."""
    return str(uuid.uuid5(_ESPACE, "slabcoach:" + str(cid)))


def _b64u(s):
    s = str(s)
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _racines():
    der = base64.b64decode(RACINE_G3)
    if hashlib.sha256(der).hexdigest() != EMPREINTE_G3:          # garde-fou : la racine epinglee n'a pas ete touchee
        raise Refus("racine Apple alteree")
    return [x509.load_der_x509_certificate(der)]


def _signe_par(cert, emetteur):
    try:
        cert.verify_directly_issued_by(emetteur)
        return True
    except (ValueError, TypeError, InvalidSignature):
        return False


def _valide_le(cert, quand):
    debut = getattr(cert, "not_valid_before_utc", None) or cert.not_valid_before.replace(tzinfo=timezone.utc)
    fin = getattr(cert, "not_valid_after_utc", None) or cert.not_valid_after.replace(tzinfo=timezone.utc)
    return debut <= quand <= fin


def _a_extension(cert, oid):
    try:
        cert.extensions.get_extension_for_oid(oid)
        return True
    except x509.ExtensionNotFound:
        return False


def verifier_chaine(feuille, inter, quand, racines=None):
    """Comme la bibliotheque officielle d'Apple (verifyCertificateChainWithoutCaching), sans OCSP."""
    racines = racines if racines is not None else _racines()
    racine = next((r for r in racines if inter.issuer == r.subject and _signe_par(inter, r)), None)
    if racine is None:
        raise Refus("chaine : pas signee par Apple")
    if feuille.issuer != inter.subject or not _signe_par(feuille, inter):
        raise Refus("chaine : certificat de signature invalide")
    try:
        if not inter.extensions.get_extension_for_class(x509.BasicConstraints).value.ca:
            raise Refus("chaine : intermediaire pas une autorite")
    except x509.ExtensionNotFound:
        raise Refus("chaine : intermediaire pas une autorite")
    if not _a_extension(feuille, OID_FEUILLE) or not _a_extension(inter, OID_INTER):
        raise Refus("chaine : extensions Apple absentes")
    for c in (feuille, inter, racine):
        if not _valide_le(c, quand):
            raise Refus("chaine : certificat expire")
    return feuille.public_key()


def verifier_jws(jws, racines=None):
    """JWS signe par l'App Store -> son contenu (dict). Refus si quoi que ce soit cloche."""
    try:
        t64, c64, s64 = str(jws or "").split(".")
        tete, corps = json.loads(_b64u(t64)), json.loads(_b64u(c64))
        if tete.get("alg") != "ES256":
            raise Refus("algorithme refuse")
        x5c = tete.get("x5c") or []
        if len(x5c) != 3:
            raise Refus("chaine : 3 certificats attendus")
        feuille, inter = (x509.load_der_x509_certificate(base64.b64decode(x)) for x in x5c[:2])
        sig = _b64u(s64)
    except Refus:
        raise
    except Exception:
        raise Refus("signature Apple illisible")
    if len(sig) != 64:
        raise Refus("signature Apple illisible")
    sd = corps.get("signedDate") or (corps.get("data") or {}).get("signedDate")
    quand = datetime.fromtimestamp(sd / 1000, tz=timezone.utc) if isinstance(sd, (int, float)) else datetime.now(timezone.utc)
    cle = verifier_chaine(feuille, inter, quand, racines)
    der = encode_dss_signature(int.from_bytes(sig[:32], "big"), int.from_bytes(sig[32:], "big"))
    try:
        cle.verify(der, (t64 + "." + c64).encode(), ec.ECDSA(hashes.SHA256()))
    except InvalidSignature:
        raise Refus("signature Apple invalide")
    return corps


def champs_transaction(tx, maintenant=None):
    """Transaction Apple deja verifiee -> champs du compte. Refus si ce n'est pas notre Pro."""
    if tx.get("bundleId") != BUNDLE:
        raise Refus("autre app")
    if tx.get("productId") != produit():
        raise Refus("autre produit")
    env = tx.get("environment") or "Production"
    if env != "Production" and not sandbox_permis():
        raise Refus("achat de test refuse en production")
    m = maintenant or time.time()
    exp = tx.get("expiresDate")
    fin = int(exp / 1000) if isinstance(exp, (int, float)) else None
    revoque = bool(tx.get("revocationDate"))
    actif = bool(fin and fin > m and not revoque)
    return {"forfait": "pro" if actif else "gratuit", "forfait_source": "apple",
            "forfait_statut": "active" if actif else ("revoked" if revoque else "expired"),
            "forfait_fin": fin, "apple_tx_orig": str(tx.get("originalTransactionId") or ""), "apple_env": env}


def _relier(cid, champs, comptes):
    """Un abonnement Apple = un compte SlabCoach. Le Pro de Stripe n'est jamais retire par un avis d'Apple."""
    info = comptes.info(cid) or {}
    if champs["forfait"] != "pro" and info.get("forfait") == "pro" and info.get("forfait_source") != "apple":
        return False                                   # Pro paye sur le site : pas touche
    comptes.maj(cid, apple_jeton=jeton_compte(cid), **champs)
    return True


def valider(jws, cid, comptes, racines=None, maintenant=None):
    """L'app envoie une transaction apres un achat ou une restauration -> champs ecrits (ou Refus)."""
    tx = verifier_jws(jws, racines)
    ch = champs_transaction(tx, maintenant)
    jt = tx.get("appAccountToken")
    if jt and str(jt).lower() != jeton_compte(cid):
        raise Refus("Cet abonnement Apple est relié à un autre compte SlabCoach")
    autres = [c for c in comptes.par_champ("apple_tx_orig", ch["apple_tx_orig"]) if c != cid]
    if autres and ch["apple_tx_orig"]:
        raise Refus("Cet abonnement Apple est relié à un autre compte SlabCoach")
    with _verrou:
        _relier(cid, ch, comptes)
    return ch


# -- avis d'Apple (App Store Server Notifications v2) ---------------------------------------------------------------
_TYPES_FIN = {"EXPIRED", "GRACE_PERIOD_EXPIRED", "REFUND", "REVOKE"}


def _deja_vu(uid, comptes):
    if not uid:
        return False
    chemin = os.path.join(comptes.DONNEES, "apple_avis_vus.json")
    with _verrou:
        try:
            with open(chemin, encoding="utf-8") as f:
                vus = json.load(f) or []
        except (OSError, ValueError):
            vus = []
        if uid in vus:
            return True
        vus = (vus + [uid])[-1000:]
        tmp = chemin + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(vus, f)
        os.replace(tmp, chemin)
    return False


def recevoir_avis(corps, comptes, racines=None, maintenant=None):
    """POST /apple/notifications -> (code HTTP, message). 200 des que l'avis est authentique (Apple arrete d'envoyer)."""
    try:
        signe = (json.loads(corps or b"{}") or {}).get("signedPayload")
        avis = verifier_jws(signe, racines)
    except (Refus, ValueError, AttributeError) as e:
        return 400, "avis refusé (" + str(e) + ")"
    data = avis.get("data") or {}
    if data.get("bundleId") and data.get("bundleId") != BUNDLE:
        return 200, "autre app"
    if _deja_vu(avis.get("notificationUUID"), comptes):
        return 200, "déjà traité"
    t, st = avis.get("notificationType") or "", avis.get("subtype") or ""
    if t == "TEST" or not data.get("signedTransactionInfo"):
        return 200, "reçu"
    try:
        tx = verifier_jws(data["signedTransactionInfo"], racines)
        ch = champs_transaction(tx, maintenant)
        ren = verifier_jws(data["signedRenewalInfo"], racines) if data.get("signedRenewalInfo") else {}
    except Refus as e:
        return 200, "ignoré (" + str(e) + ")"
    if t in _TYPES_FIN:
        ch.update(forfait="gratuit", forfait_statut="revoked" if t in ("REFUND", "REVOKE") else "expired")
    if t == "DID_FAIL_TO_RENEW" and st == "GRACE_PERIOD" and ren.get("gracePeriodExpiresDate"):
        g = int(ren["gracePeriodExpiresDate"] / 1000)
        if g > (maintenant or time.time()):
            ch.update(forfait="pro", forfait_statut="grace", forfait_fin=g)
    if "autoRenewStatus" in ren:
        ch["forfait_annule"] = ren.get("autoRenewStatus") == 0
    jt = str(tx.get("appAccountToken") or "").lower()
    cid = next((c for c in comptes.par_champ("apple_jeton", jt)), None) if jt else None
    cid = cid or next((c for c in comptes.par_champ("apple_tx_orig", ch["apple_tx_orig"])), None)
    if not cid:
        return 200, "compte inconnu"
    with _verrou:
        _relier(cid, ch, comptes)
    return 200, "ok"
