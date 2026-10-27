"""
LOCKERROOM - plusieurs clients sur UN serveur (21 oct 2026, option A).

Principe : le client ne configure RIEN. Il touche « Se connecter avec eBay » ;
eBay nous dit qui il est (Commerce Identity : userId + username) ; on cree son
compte au premier passage et on importe tout de suite ses annonces et ventes.

  - un dossier par compte : DONNEES/comptes/<id>/  (sa base lockerroom.db,
    ses jetons eBay chiffres). Isolation forte : une requete ne peut lire que
    le dossier du compte de sa session.
  - compte courant : ContextVar (une requete web ou une tache de fond a la fois).
  - mode local (PC de Mathieu, sans LOCKERROOM_MULTI) : aucun compte, les fichiers
    restent a cote du code, comme avant.
"""
import base64
import contextlib
import contextvars
import hashlib
import json
import os
import re
import secrets
import threading
from datetime import datetime

DONNEES = os.environ.get("LOCKERROOM_DONNEES") or os.path.dirname(os.path.abspath(__file__))
MULTI = os.environ.get("LOCKERROOM_MULTI") == "1"
DOSSIER_COMPTES = os.path.join(DONNEES, "comptes")
CHEMIN_INDEX = os.path.join(DOSSIER_COMPTES, "index.json")
_courant = contextvars.ContextVar("compte_lockerroom", default=None)
_verrou = threading.Lock()


def courant():
    return _courant.get()


@contextlib.contextmanager
def utiliser(compte_id):
    """with comptes.utiliser(id): ... -> base, jetons et reglages de ce compte."""
    jeton = _courant.set(compte_id)
    try:
        yield compte_id
    finally:
        _courant.reset(jeton)


def activer(compte_id):
    """Pour une requete web (remis a zero a la requete suivante)."""
    _courant.set(compte_id)


def dossier(compte_id=None):
    cid = compte_id or courant()
    if not cid:
        return None
    if not re.fullmatch(r"[a-z0-9]{8,40}", str(cid)):
        raise ValueError("Compte invalide")
    d = os.path.join(DOSSIER_COMPTES, cid)
    if not os.path.isdir(d):
        if cid not in _index():             # 27 oct 2026 : compte supprime pendant une synchro -> on ne le recree pas
            raise ValueError("Compte inconnu")
        os.makedirs(d, exist_ok=True)
    return d


def _index():
    try:
        with open(CHEMIN_INDEX, encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def _ecrire_index(ix):
    os.makedirs(DOSSIER_COMPTES, exist_ok=True)
    tmp = CHEMIN_INDEX + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(ix, f)
    os.replace(tmp, CHEMIN_INDEX)


def id_pour(ebay_user_id, env):
    """Identifiant stable et opaque : rien de lisible ne sort du compte eBay."""
    return hashlib.sha256(f"{env}:{ebay_user_id}".encode()).hexdigest()[:24]


def trouver_ou_creer(ebay_user_id, username, env):
    cid = id_pour(ebay_user_id, env)
    with _verrou:
        ix = _index()
        nouveau = cid not in ix
        # 27 oct 2026 (revue) : un compte supprime puis recree garde sa date de creation (pas un 2e essai gratuit)
        e = ix.setdefault(cid, {"cree_le": _anciens().get(cid) or datetime.now().isoformat(timespec="seconds"), "env": env})
        e.update(username=username, vu_le=datetime.now().isoformat(timespec="seconds"))
        _ecrire_index(ix)
    dossier(cid)
    return cid, nouveau


def maj(compte_id, **champs):
    """Champs du compte ecrits par le SERVEUR seulement (ex. forfait venu de Stripe)."""
    with _verrou:
        ix = _index()
        if compte_id not in ix:
            return False
        ix[compte_id].update({k: v for k, v in champs.items()})
        _ecrire_index(ix)
    return True


def par_champ(champ, valeur):
    return [cid for cid, e in _index().items() if valeur and e.get(champ) == valeur]


def lister():
    return list(_index().keys())


def info(compte_id):
    return _index().get(compte_id) or {}


def par_username(username):
    u = str(username or "").lower()
    return [cid for cid, e in _index().items() if str(e.get("username") or "").lower() == u]


def supprimer(compte_id):
    """Compte eBay supprime (avis d'eBay) ou demande du client : tout son dossier disparait."""
    import shutil
    d = os.path.join(DOSSIER_COMPTES, compte_id)
    with _verrou:
        ix = _index()
        e = ix.pop(compte_id, None) or {}
        _ecrire_index(ix)
        if e.get("cree_le"):                # seulement l'identifiant opaque et la date : rien d'autre ne reste
            a = _anciens()
            a[compte_id] = min(e["cree_le"], a.get(compte_id) or e["cree_le"])
            _ecrire_json(os.path.join(DONNEES, "comptes_supprimes.json"), a)
    shutil.rmtree(d, ignore_errors=True)


def _anciens():
    try:
        with open(os.path.join(DONNEES, "comptes_supprimes.json"), encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def _ecrire_json(chemin, d):
    tmp = chemin + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f)
    os.replace(tmp, chemin)


# -- chiffrement des jetons (cle : LOCKERROOM_CLE, jamais sur le disque) ----------------------
def _fernet():
    cle = os.environ.get("LOCKERROOM_CLE")
    if not cle:
        return None
    from cryptography.fernet import Fernet
    k = base64.urlsafe_b64encode(hashlib.sha256(cle.encode()).digest())
    return Fernet(k)


def chiffrer(texte):
    f = _fernet()
    return ("LRC1:" + f.encrypt(texte.encode()).decode()) if f else texte


def dechiffrer(texte):
    if texte.startswith("LRC1:"):
        f = _fernet()
        if not f:
            raise RuntimeError("Jetons chiffrés : LOCKERROOM_CLE manquante")
        return f.decrypt(texte[5:].encode()).decode()
    return texte


def nouvel_etat():
    return secrets.token_urlsafe(16)
