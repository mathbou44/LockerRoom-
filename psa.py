"""
SLABCOACH - verification d'un certificat PSA (27 oct 2026, Mathieu : « ajoute l'info de l'API de PSA publique si c'est autorise »).

PSA Public API (api.psacard.com/publicapi, jeton Bearer obtenu avec un compte PSA) :
  GET /cert/GetByCertNumber/{cert}  ->  PSACert : annee, marque, joueur, numero, variante, note, population.
Regles qu'on s'impose, en attendant de relire l'entente d'utilisation de l'API de PSA (« PSA API End User Agreement »,
visible une fois connecte sur psacard.com) :
  - eteint tant que PSA_JETON n'est pas dans Render (et PSA_ACTIF=0 le coupe en tout temps) ;
  - une verification = un certificat, a la demande du vendeur (jamais en lot, jamais en tache de fond) ;
  - au plus PSA_QUOTA appels par jour pour tout le serveur (90 par defaut), resultat garde 30 jours ;
  - on montre les donnees dans l'app avec le lien officiel du certificat ; pas de logo PSA, rien n'est copie dans l'annonce.
"""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request

BASE = "https://api.psacard.com/publicapi"
GARDE_S = 30 * 86400
_verrou = threading.Lock()


def actif():
    return bool(os.environ.get("PSA_JETON", "").strip()) and os.environ.get("PSA_ACTIF", "1") != "0"


def _quota():
    try:
        return max(1, int(os.environ.get("PSA_QUOTA") or 90))
    except ValueError:
        return 90


def _chemin():
    d = os.environ.get("LOCKERROOM_DONNEES") or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(d, "psa_cache.json")


def _lire():
    try:
        with open(_chemin(), encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def _ecrire(d):
    p = _chemin()
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(d, f)
    os.replace(p + ".tmp", p)


def _get(chemin):
    req = urllib.request.Request(BASE + chemin, headers={"Authorization": "bearer " + os.environ.get("PSA_JETON", "").strip(),
                                                         "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            brut = r.read()
            return r.status, (json.loads(brut) if brut else None)
    except urllib.error.HTTPError as e:
        return e.code, None
    except (urllib.error.URLError, TimeoutError, ValueError):
        return 0, None


def _titre(s):
    """« MACKLIN CELEBRINI » -> « Macklin Celebrini » ; garde les sigles courts (RC, SP, UD)."""
    mots = []
    for m in str(s or "").split():
        mots.append(m if len(m) <= 2 and m.isupper() else m[:1].upper() + m[1:].lower())
    return " ".join(mots)


def note(carte_grade):
    """« GEM MT 10 » -> « 10 » ; « NM-MT 8.5 » -> « 8.5 » ; « AUTHENTIC » -> None."""
    m = re.search(r"(\d{1,2}(?:\.5)?)\s*$", str(carte_grade or "").strip())
    return m.group(1) if m else None


def _analyser(cert, c):
    n = note(c.get("CardGrade"))
    return {"ok": True, "cert": cert, "source": "PSA", "lien": f"https://www.psacard.com/cert/{cert}",
            "annee": str(c.get("Year") or "").strip() or None, "marque": _titre(c.get("Brand")) or None,
            "joueur": _titre(c.get("Subject")) or None, "numero": str(c.get("CardNumber") or "").strip() or None,
            "variante": _titre(c.get("Variety")) or None, "categorie": _titre(c.get("Category")) or None,
            "grade": ("PSA " + n) if n else None, "grade_texte": c.get("GradeDescription") or c.get("CardGrade"),
            "auto_grade": c.get("AutographGrade") or None,
            "pop": c.get("TotalPopulation"), "pop_plus_haute": c.get("PopulationHigher"),
            "double": bool(c.get("IsDualCert")), "statut": c.get("ItemStatus")}


def verifier(cert):
    """Un certificat PSA -> ce que PSA en dit (ou {ok: False, erreur})."""
    cert = re.sub(r"\D", "", str(cert or ""))
    if not 6 <= len(cert) <= 10:
        return {"ok": False, "erreur": "Numéro de certificat PSA : 6 à 10 chiffres (sur l'étiquette)"}
    if not actif():
        return {"ok": False, "erreur": "La vérification PSA n'est pas encore activée", "inactif": True}
    with _verrou:
        d = _lire()
        g = (d.get("certs") or {}).get(cert)
        if g and time.time() - g.get("le", 0) < GARDE_S:
            return {**g["r"], "garde": True}
        jour = time.strftime("%Y-%m-%d")
        if d.get("jour") != jour:
            d["jour"], d["n"] = jour, 0
        if d.get("n", 0) >= _quota():
            return {"ok": False, "erreur": "Vérifications PSA du jour épuisées : réessaie demain"}
        d["n"] = d.get("n", 0) + 1
        _ecrire(d)
    st, r = _get(f"/cert/GetByCertNumber/{cert}")
    if st in (401, 403, 500) and not r:
        return {"ok": False, "erreur": "PSA ne répond pas pour l'instant (jeton à vérifier)"}
    if st == 0:
        return {"ok": False, "erreur": "PSA ne répond pas : réessaie dans un instant"}
    c = (r or {}).get("PSACert") if isinstance(r, dict) else None
    if st == 204 or not c or not c.get("CertNumber"):
        msg = str((r or {}).get("ServerMessage") or "") if isinstance(r, dict) else ""
        return {"ok": False, "erreur": "Certificat introuvable chez PSA" + (f" ({msg})" if msg and "No data" not in msg else "")}
    res = _analyser(cert, c)
    with _verrou:
        d = _lire()
        certs = d.setdefault("certs", {})
        certs[cert] = {"le": time.time(), "r": res}
        if len(certs) > 5000:                     # garde les plus recents
            for k in sorted(certs, key=lambda k: certs[k].get("le", 0))[:len(certs) - 5000]:
                certs.pop(k, None)
        _ecrire(d)
    return res
