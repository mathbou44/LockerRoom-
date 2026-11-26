"""
LOCKERROOM - notifications sur l'iPhone (Apple Push Notification service) (26 oct 2026).

Mathieu : « prepare la version mobile, je veux mon app dans l'App Store d'ici la fin de la semaine ».
L'app iPhone demande la permission quand l'utilisateur cree une alerte de prix ; son jeton est garde dans SON compte.
Quand une alerte trouve la carte sous le prix cible, le serveur envoie la notification a ses iPhone.

Render (variables) - rien n'est envoye tant qu'elles manquent :
  APNS_KEY_ID   l'identifiant de la cle (.p8) creee dans developer.apple.com > Keys (Apple Push Notifications service)
  APNS_TEAM_ID  l'identifiant d'equipe Apple (10 caracteres)
  APNS_KEY      le contenu du fichier .p8 (-----BEGIN PRIVATE KEY----- ...), jamais dans le depot
  APNS_TOPIC    l'identifiant de l'app (com.slabcoach.app par defaut)
  APNS_SANDBOX  1 pour les versions de test installees depuis Xcode (TestFlight et App Store : laisser vide)
Le jeton d'authentification (JWT ES256) est refait toutes les 50 minutes, comme Apple le demande.
"""
import base64
import hashlib
import json
import os
import re
import threading
import time

_verrou = threading.Lock()
_JWT = {"le": 0.0, "v": None}
_PRET = {"cle": None, "ok": False}


class CleIllisible(ValueError):
    """APNS_KEY ne se lit pas. 25 nov 2026 : une cle collee sans ses lignes BEGIN / END faisait planter le serveur, et
    l'erreur ecrite au journal contenait les octets de la cle. Ce message-ci ne contient JAMAIS la cle."""
    def __init__(self):
        super().__init__("APNS_KEY illisible : colle tout le fichier .p8 dans Render")


_RE_PEM = re.compile(r"-----BEGIN ([A-Z ]*PRIVATE KEY)-----(.*?)-----END \1-----", re.S)


def cle_pem(brut):
    """La cle telle qu'elle est collee dans Render -> un PEM propre. Accepte : le fichier .p8 au complet ; le meme sur une
    seule ligne ou avec des « \\n » ecrits ; seulement le corps (sans les lignes BEGIN / END) ; le fichier encode en base64."""
    t = str(brut or "").replace("\\n", "\n").replace("\r", "").strip().strip("\"'").strip()
    sorte, m = "PRIVATE KEY", _RE_PEM.search(t)
    if m:
        sorte, corps = m.group(1), "".join(m.group(2).split())
    else:
        corps = "".join(t.split())
        try:
            d = base64.b64decode(corps, validate=True)
        except Exception:
            raise CleIllisible() from None
        m2 = _RE_PEM.search(d.decode("latin-1"))
        if m2:                                           # le fichier entier, encode en base64
            sorte, corps = m2.group(1), "".join(m2.group(2).split())
    if len(corps) < 80 or re.search(r"[^A-Za-z0-9+/=]", corps):
        raise CleIllisible() from None
    return f"-----BEGIN {sorte}-----\n" + "\n".join(corps[i:i + 64] for i in range(0, len(corps), 64)) + f"\n-----END {sorte}-----\n"


def _charger_cle():
    from cryptography.hazmat.primitives import serialization
    try:
        return serialization.load_pem_private_key(cle_pem(os.environ.get("APNS_KEY")).encode(), password=None)
    except Exception:
        raise CleIllisible() from None                  # jamais l'erreur d'origine : elle peut porter la cle


def pret():
    """Les trois variables sont la ET la cle se lit. (actif() : les variables sont la, sans plus.)"""
    if not actif():
        return False
    k = hashlib.sha256((os.environ.get("APNS_KEY") or "").encode()).hexdigest()
    if _PRET["cle"] != k:
        try:
            _charger_cle()
            ok = True
        except CleIllisible:
            ok = False
        _PRET.update(cle=k, ok=ok)
    return _PRET["ok"]


DERNIER = {}                   # la derniere reponse d'Apple : {code, texte, le}


def actif():
    return all(os.environ.get(k) for k in ("APNS_KEY_ID", "APNS_TEAM_ID", "APNS_KEY"))


def _b64(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def jeton_auth(maintenant=None):
    """JWT signe ES256 : {alg, kid} . {iss: equipe, iat}."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    t = int(maintenant or time.time())
    with _verrou:
        if _JWT["v"] and t - _JWT["le"] < 3000:
            return _JWT["v"]
        cle = _charger_cle()
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
    try:
        auth = jeton_auth()
    except Exception as e:                               # 25 nov 2026 : jamais repr(e) ici (voir CleIllisible)
        msg = str(e) if isinstance(e, CleIllisible) else "signature impossible (" + type(e).__name__ + ")"
        print("APNs : " + msg, flush=True)
        DERNIER.update(code=0, texte=msg, le=time.time())
        return "erreur"
    tetes = {"authorization": "bearer " + auth, "apns-topic": os.environ.get("APNS_TOPIC") or "com.slabcoach.app",
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
        DERNIER.update(code=0, texte=repr(e)[:200], le=time.time())
        return "erreur"
    DERNIER.update(code=r.status_code, texte=(r.text or "")[:200], le=time.time())      # 24 nov 2026 : pour l'essai (Api.push_essai)
    if r.status_code == 200:
        return "ok"
    if r.status_code == 410 or (r.status_code == 400 and "BadDeviceToken" in r.text):
        return "perime"
    print(f"APNs {r.status_code} : {r.text[:200]}", flush=True)
    return "erreur"
