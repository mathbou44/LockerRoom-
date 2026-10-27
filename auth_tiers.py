"""
SLABCOACH - se connecter SANS eBay : Apple et Google (27 oct 2026).

Mathieu : « ne pas obliger d'avoir un compte eBay, mais fortement recommande » ; choix : Apple + Google.

  - OpenID Connect standard : on recoit un code, on l'echange contre un id_token, on verifie la signature
    (cles publiques d'Apple / de Google), l'emetteur, l'audience, l'expiration et le nonce.
  - l'etat (state) est signe (HMAC avec le secret du serveur) et vaut 10 minutes : Apple renvoie en POST
    d'un autre site, donc le cookie de session n'est pas la ; l'etat signe suffit.
  - un compte par identifiant (sub) Apple ou Google ; eBay se connecte ensuite dans Reglages (recommande).
Rien a configurer dans le code : les cles sont dans Render (voir HEBERGEMENT.md), jamais dans GitHub.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

FOURNISSEURS = {
    "google": {"auth": "https://accounts.google.com/o/oauth2/v2/auth", "jeton": "https://oauth2.googleapis.com/token",
               "jwks": "https://www.googleapis.com/oauth2/v3/certs", "iss": ("https://accounts.google.com", "accounts.google.com"),
               "scope": "openid email profile", "nom": "Google"},
    "apple": {"auth": "https://appleid.apple.com/auth/authorize", "jeton": "https://appleid.apple.com/auth/token",
              "jwks": "https://appleid.apple.com/auth/keys", "iss": ("https://appleid.apple.com",),
              "scope": "name email", "nom": "Apple"},
}
DUREE_ETAT_S = 600
_JWKS = {}


def _b64e(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _b64d(s):
    s = str(s)
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def cfg(f):
    e = os.environ.get
    if f == "google":
        return {"client_id": e("GOOGLE_CLIENT_ID") or "", "secret": e("GOOGLE_CLIENT_SECRET") or ""}
    if f == "apple":
        cle = (e("APPLE_PRIVATE_KEY") or "").replace("\\n", "\n").strip()
        return {"client_id": e("APPLE_SERVICES_ID") or "", "equipe": e("APPLE_TEAM_ID") or "", "cle_id": e("APPLE_KEY_ID") or "", "cle": cle}
    return {}


def actif(f):
    c = cfg(f)
    return bool(c) and all(c.values())


def actifs():
    return [f for f in FOURNISSEURS if actif(f)]


def _secret_serveur():
    s = os.environ.get("LOCKERROOM_SECRET") or ""
    if not s:
        raise RuntimeError("LOCKERROOM_SECRET manquant")
    return s.encode()


def _signer_etat(d):
    corps = _b64e(json.dumps(d, separators=(",", ":")).encode())
    sig = _b64e(hmac.new(_secret_serveur(), corps.encode(), hashlib.sha256).digest())
    return corps + "." + sig


def _lire_etat(etat):
    try:
        corps, sig = str(etat or "").split(".", 1)
    except ValueError:
        return None
    attendu = _b64e(hmac.new(_secret_serveur(), corps.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, attendu):
        return None
    try:
        d = json.loads(_b64d(corps))
    except ValueError:
        return None
    if time.time() - float(d.get("t") or 0) > DUREE_ETAT_S:
        return None
    return d


def adresse_retour(f, base):
    return base.rstrip("/") + f"/auth/{f}/retour"


def url_connexion(f, base):
    """Adresse de la page officielle d'Apple ou de Google."""
    if f not in FOURNISSEURS or not actif(f):
        raise RuntimeError("Connexion " + f + " pas encore configurée")
    p, c = FOURNISSEURS[f], cfg(f)
    nonce = secrets.token_urlsafe(16)
    etat = _signer_etat({"f": f, "n": nonce, "t": int(time.time())})
    q = {"client_id": c["client_id"], "redirect_uri": adresse_retour(f, base), "response_type": "code",
         "scope": p["scope"], "state": etat, "nonce": nonce}
    if f == "google":
        q.update(prompt="select_account", access_type="online")
    else:
        q["response_mode"] = "form_post"                # Apple : obligatoire quand on demande le nom ou le courriel
    return p["auth"] + "?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)


def _secret_apple():
    """Apple : le « client secret » est un jeton ES256 signe avec la cle .p8 (valide 30 jours ici)."""
    c = cfg("apple")
    cle = serialization.load_pem_private_key(c["cle"].encode(), password=None)
    maint = int(time.time())
    tete = {"alg": "ES256", "kid": c["cle_id"]}
    corps = {"iss": c["equipe"], "iat": maint, "exp": maint + 30 * 86400, "aud": "https://appleid.apple.com", "sub": c["client_id"]}
    entree = _b64e(json.dumps(tete, separators=(",", ":")).encode()) + "." + _b64e(json.dumps(corps, separators=(",", ":")).encode())
    r, s = decode_dss_signature(cle.sign(entree.encode(), ec.ECDSA(hashes.SHA256())))
    return entree + "." + _b64e(r.to_bytes(32, "big") + s.to_bytes(32, "big"))


def _post(url, data):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json",
                                          "User-Agent": "SlabCoach"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"refus (HTTP {e.code}) : {e.read().decode('utf-8', 'ignore')[:160]}")


def _cles_publiques(f, lecteur=None):
    e = _JWKS.get(f)
    if e and time.time() - e["le"] < 6 * 3600:
        return e["cles"]
    if lecteur:
        brut = lecteur(FOURNISSEURS[f]["jwks"])
    else:
        with urllib.request.urlopen(urllib.request.Request(FOURNISSEURS[f]["jwks"], headers={"User-Agent": "SlabCoach"}), timeout=10) as r:
            brut = r.read()
    cles = {k["kid"]: k for k in json.loads(brut).get("keys") or [] if k.get("kty") == "RSA"}
    _JWKS[f] = {"le": time.time(), "cles": cles}
    return cles


def verifier_id_token(f, jeton, nonce, lecteur=None, maintenant=None):
    """Signature RS256 + emetteur + audience + expiration + nonce. -> claims, sinon RuntimeError."""
    try:
        t64, c64, s64 = str(jeton).split(".")
        tete, claims = json.loads(_b64d(t64)), json.loads(_b64d(c64))
    except (ValueError, TypeError):
        raise RuntimeError("jeton illisible")
    if tete.get("alg") != "RS256":
        raise RuntimeError("algorithme refusé")
    jwk = _cles_publiques(f, lecteur).get(tete.get("kid"))
    if not jwk:
        _JWKS.pop(f, None)                          # cles tournees : on relit une fois
        jwk = _cles_publiques(f, lecteur).get(tete.get("kid"))
    if not jwk:
        raise RuntimeError("clé inconnue")
    pub = rsa.RSAPublicNumbers(int.from_bytes(_b64d(jwk["e"]), "big"), int.from_bytes(_b64d(jwk["n"]), "big")).public_key()
    try:
        pub.verify(_b64d(s64), (t64 + "." + c64).encode(), padding.PKCS1v15(), hashes.SHA256())
    except Exception:
        raise RuntimeError("signature invalide")
    m = maintenant or time.time()
    if claims.get("iss") not in FOURNISSEURS[f]["iss"]:
        raise RuntimeError("émetteur inattendu")
    aud = claims.get("aud")
    if cfg(f)["client_id"] not in (aud if isinstance(aud, list) else [aud]):
        raise RuntimeError("audience inattendue")
    if float(claims.get("exp") or 0) < m - 60:
        raise RuntimeError("jeton expiré")
    if nonce and not hmac.compare_digest(str(claims.get("nonce") or ""), str(nonce)):
        raise RuntimeError("nonce différent")
    if not claims.get("sub"):
        raise RuntimeError("identité absente")
    return claims


def terminer(f, code, etat, base, utilisateur_json=None):
    """-> {ok, sub, courriel, nom} ou {ok: False, erreur}."""
    d = _lire_etat(etat)
    if not d or d.get("f") != f:
        return {"ok": False, "erreur": "Connexion expirée : recommence"}
    if not code:
        return {"ok": False, "erreur": "Connexion annulée"}
    c = cfg(f)
    try:
        secret = _secret_apple() if f == "apple" else c["secret"]
        rep = _post(FOURNISSEURS[f]["jeton"], {"client_id": c["client_id"], "client_secret": secret, "code": code,
                                                "grant_type": "authorization_code", "redirect_uri": adresse_retour(f, base)})
        claims = verifier_id_token(f, rep.get("id_token"), d.get("n"))
    except Exception as e:
        return {"ok": False, "erreur": f"{FOURNISSEURS[f]['nom']} n'a pas confirmé ton identité ({e})"}
    nom = claims.get("name") or ""
    if f == "apple" and utilisateur_json:                 # Apple donne le nom UNE seule fois, au premier passage
        try:
            n = (json.loads(utilisateur_json) or {}).get("name") or {}
            nom = " ".join(x for x in (n.get("firstName"), n.get("lastName")) if x)
        except ValueError:
            pass
    return {"ok": True, "sub": str(claims["sub"]), "courriel": claims.get("email") if claims.get("email_verified") in (True, "true", None) else None,
            "nom": nom or (str(claims.get("email") or "").split("@")[0]) or FOURNISSEURS[f]["nom"]}
