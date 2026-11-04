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


_IX = {"cle": None, "ix": {}}


def _index(frais=False):
    """4 nov 2026 (tournee vitesse) : relu seulement quand le fichier change (date + taille), pas 3 fois par requete.
    Les lecteurs recoivent l'objet partage (ne pas le modifier) ; ceux qui ecrivent demandent frais=True (copie du disque)."""
    try:
        st = os.stat(CHEMIN_INDEX)
        cle = (st.st_mtime_ns, st.st_ctime_ns, st.st_size, st.st_ino)
    except OSError:
        return {}
    if not frais and _IX["cle"] == cle:
        return _IX["ix"]
    try:
        with open(CHEMIN_INDEX, encoding="utf-8") as f:
            ix = json.load(f) or {}
    except (OSError, ValueError):
        return {}
    if not frais:
        _IX.update(cle=cle, ix=ix)
    return ix


def _ecrire_index(ix):
    os.makedirs(DOSSIER_COMPTES, exist_ok=True)
    tmp = CHEMIN_INDEX + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(ix, f)
    os.replace(tmp, CHEMIN_INDEX)
    _IX["cle"] = None


def id_pour(ebay_user_id, env):
    """Identifiant stable et opaque : rien de lisible ne sort du compte eBay."""
    return hashlib.sha256(f"{env}:{ebay_user_id}".encode()).hexdigest()[:24]


def trouver_ou_creer(ebay_user_id, username, env):
    cid = id_pour(ebay_user_id, env)
    with _verrou:
        ix = _index(True)
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
        ix = _index(True)
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
    return dict(_index().get(compte_id) or {})


def par_username(username):
    u = str(username or "").lower()
    return [cid for cid, e in _index().items() if str(e.get("username") or "").lower() == u]


def supprimer(compte_id):
    """Compte eBay supprime (avis d'eBay) ou demande du client : tout son dossier disparait."""
    import shutil
    d = os.path.join(DOSSIER_COMPTES, compte_id)
    with _verrou:
        ix = _index(True)
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
    if not f and MULTI and os.environ.get("LOCKERROOM_HEBERGE") == "1":
        # 3 nov 2026 (revue de securite) : en ligne, jamais un jeton en clair sur le disque (la cle manque : on refuse)
        raise RuntimeError("LOCKERROOM_CLE manquante : impossible de garder ce jeton de façon sûre")
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


# -- 2 nov 2026 (Mathieu : « un utilisateur doit voir la meme chose sur son ordi que sur son cell ») ------------------------
# Un compte = une personne, peu importe comment elle se connecte (eBay, Apple, Google) :
#   1. chaque compte garde ses « identites » (fournisseur:sub) ; une identite reliee ouvre toujours CE compte ;
#   2. une nouvelle connexion avec un courriel VERIFIE deja connu ouvre le compte de ce courriel (pas un 2e compte vide) ;
#   3. un code d'appareil a 6 chiffres (10 min, un seul usage) ouvre le meme compte sur un autre appareil ;
#   4. un ancien compte relie a un autre garde ses donnees (rien n'est efface) et renvoie vers le compte choisi.
CHEMIN_CODES = os.path.join(DOSSIER_COMPTES, "codes_appareil.json")
_RELAIS = re.compile(r"@privaterelay\.appleid\.com$", re.I)


def revoquer_session(compte_id, sid):
    """3 nov 2026 (revue de securite) : « Se deconnecter » ferme CETTE session pour de bon (les 200 dernieres gardees)."""
    with _verrou:
        ix = _index(True)
        if compte_id not in ix or not sid:
            return False
        l = [x for x in ix[compte_id].get("sessions_revoquees") or [] if x != sid] + [str(sid)[:40]]
        ix[compte_id]["sessions_revoquees"] = l[-200:]
        _ecrire_index(ix)
    return True


def session_revoquee(compte_id, sid):
    return str(sid) in ((_index().get(compte_id) or {}).get("sessions_revoquees") or [])


def resoudre(compte_id):
    """Le compte ou une session doit aller (suit les renvois d'un ancien compte relie)."""
    ix = _index()
    cid, vus = compte_id, set()
    while cid in ix and ix[cid].get("renvoi") and cid not in vus and len(vus) < 4:
        vus.add(cid)
        nxt = ix[cid]["renvoi"]
        if nxt not in ix:
            break
        cid = nxt
    return cid


def par_identite(cle):
    return next((cid for cid, e in _index().items() if cle in (e.get("identites") or []) and not e.get("renvoi")), None)


def lier_identite(compte_id, cle, env=None):
    """Relie une identite (fournisseur:sub) a ce compte. L'ancien compte de cette identite (s'il existe) renvoie ici ; ses
    donnees restent sur le disque."""
    ancien = id_pour(cle, env) if env else None
    with _verrou:
        ix = _index(True)
        if compte_id not in ix:
            return False
        ids = ix[compte_id].setdefault("identites", [])
        if cle not in ids:
            ids.append(cle)
        for cid, e in ix.items():                      # une identite n'appartient qu'a un compte
            if cid != compte_id and cle in (e.get("identites") or []):
                e["identites"] = [x for x in e["identites"] if x != cle]
        if ancien and ancien != compte_id and ancien in ix and not ix[ancien].get("renvoi"):
            ix[ancien]["renvoi"] = compte_id
            ix[ancien]["relie_le"] = datetime.now().isoformat(timespec="seconds")
        _ecrire_index(ix)
    return True


def courriel_utilisable(courriel):
    c = str(courriel or "").strip().lower()
    return c if c and "@" in c and not _RELAIS.search(c) else None


def trouver_connexion(cle, nom, env, courriel=None):
    """Connexion Apple / Google : le compte de cette personne. -> (compte_id, nouveau)."""
    cid = par_identite(cle)
    if cid:
        return cid, False
    defaut = id_pour(cle, env)
    ix = _index()
    if defaut in ix:
        return resoudre(defaut), False
    c = courriel_utilisable(courriel)
    if c:
        memes = [k for k, e in ix.items() if courriel_utilisable(e.get("courriel")) == c and not e.get("renvoi")]
        if memes:
            cible = sorted(memes, key=lambda k: str(ix[k].get("cree_le") or ""))[0]       # le plus ancien
            lier_identite(cible, cle)
            return cible, False
    cid, nouveau = trouver_ou_creer(cle, nom, env)
    lier_identite(cid, cle)
    return cid, nouveau


def code_creer(compte_id, ttl=600):
    """Un code a 6 chiffres qui ouvre CE compte sur un autre appareil (10 min, un seul usage)."""
    import time
    with _verrou:
        d = {}
        try:
            with open(CHEMIN_CODES, encoding="utf-8") as f:
                d = json.load(f) or {}
        except (OSError, ValueError):
            pass
        m = time.time()
        d = {k: v for k, v in d.items() if v[1] > m and v[0] != compte_id}
        while True:
            code = f"{secrets.randbelow(10 ** 8):08d}"          # 3 nov 2026 (revue de securite) : 8 chiffres (100 millions)
            if code not in d:
                break
        d[code] = [compte_id, m + ttl]
        os.makedirs(DOSSIER_COMPTES, exist_ok=True)
        _ecrire_json(CHEMIN_CODES, d)
    return code


def code_utiliser(code):
    import time
    code = re.sub(r"\D", "", str(code or ""))
    if len(code) not in (6, 8):                       # 6 : un code demande avant la mise a jour (10 min au plus)
        return None
    with _verrou:
        try:
            with open(CHEMIN_CODES, encoding="utf-8") as f:
                d = json.load(f) or {}
        except (OSError, ValueError):
            return None
        v = d.pop(code, None)
        _ecrire_json(CHEMIN_CODES, {k: x for k, x in d.items() if x[1] > time.time()})
    if not v or v[1] < time.time() or v[0] not in _index():
        return None
    return resoudre(v[0])
