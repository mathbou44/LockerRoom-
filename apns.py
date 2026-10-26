"""
LOCKERROOM - notifications sur l'iPhone (Apple Push Notification service) (26 oct 2026).

Mathieu : « prepare la version mobile, je veux mon app dans l'App Store d'ici la fin de la semaine ».
L'app iPhone demande la permission quand l'utilisateur cree une alerte de prix ; son jeton est garde dans SON compte.
Quand une alerte trouve la carte sous le prix cible, le serveur envoie la notification a ses iPhone.

Render (variables) - rien n'est envoye tant qu'elles manquent :
  APNS_KEY_ID   l'identifiant de la cle (.p8) creee dans developer.apple.com > Keys (Apple Push Notifications service)
  APNS_TEAM_ID  l'identifiant d'equipe Apple (10 caracteres)
  APNS_KEY      le contenu du fichier .p8 (-----BEGIN PRIVATE KEY----- ...), jamais dans le depot
  APNS_TOPIC    l'identifiant de l'app (com.lockerroom.app par defaut)
  APNS_SANDBOX  1 pour les versions de test installees depuis Xcode (TestFlight et App Store : laisser vide)
Le jeton d'authentification (JWT ES256) est refait toutes les 50 minutes, comme Apple le demande.
"""
import base64
import json
import os
import threading
import time

_verrou = threading.Lock()
_JWT = {"le": 0.0, "v": None}


def actif():
    return all(os.environ.get(k) for k in ("APNS_KEY_ID", "APNS_TEAM_ID", "APNS_KEY"))


def _b64(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def jeton_auth(maintenant=None):
    """JWT signe ES256 : {alg, kid} . {iss: equipe, iat}."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    t = int(maintenant or time.time())
    with _verrou:
        if _JWT["v"] and t - _JWT["le"] < 3000:
            return _JWT["v"]
        cle_txt = os.environ["APNS_KEY"].replace("\\n", "\n").strip()
        if "BEGIN" not in cle_txt:
            cle_txt = base64.b64decode(cle_txt).decode()
        cle = serialization.load_pem_private_key(cle_txt.encode(), password=None)
        tete = _b64(json.dumps({"alg": "ES256", "kid": os.environ["APNS_KEY_ID"]}, separators=(",", ":")).encode())
        corps = _b64(json.dumps({"iss": os.environ["APNS_TEAM_ID"], "iat": t}, separators=(",", ":")).encode())
        sig = cle.sign(f"{tete}.{corps}".encode(), ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(sig)
        jwt = f"{tete}.{corps}.{_b64(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"
        _JWT.update(le=t, v=jwt)
        return jwt


def envoyer(jeton, titre, texte, donnees=None, client=None):
    """-> 'ok' | 'perime' (jeton a oublier) | 'erreur'."""
    if not actif() or not jeton:
        return "erreur"
    hote = "api.sandbox.push.apple.com" if os.environ.get("APNS_SANDBOX") == "1" else "api.push.apple.com"
    corps = {"aps": {"alert": {"title": str(titre)[:120], "body": str(texte)[:240]}, "sound": "default"}, **(donnees or {})}
    tetes = {"authorization": "bearer " + jeton_auth(), "apns-topic": os.environ.get("APNS_TOPIC") or "com.lockerroom.app",
             "apns-push-type": "alert", "apns-priority": "10"}
    try:
        import httpx
        fermer = client is None
        client = client or httpx.Client(http2=True, timeout=10)
        try:
            r = client.post(f"https://{hote}/3/device/{jeton}", headers=tetes, json=corps)
        finally:
            if fermer:
                client.close()
    except Exception as e:
        print("APNs : " + repr(e), flush=True)
        return "erreur"
    if r.status_code == 200:
        return "ok"
    if r.status_code == 410 or (r.status_code == 400 and "BadDeviceToken" in r.text):
        return "perime"
    print(f"APNs {r.status_code} : {r.text[:200]}", flush=True)
    return "erreur"
