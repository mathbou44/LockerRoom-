"""
SLABCOACH - envoyer une mise a Gixen en un tap (31 oct 2026, admin seulement).

Mathieu : « pour Gixen, y'a rien de plus rapide ? ». Gixen a une API (https://www.gixen.com/api.php : itemid + maxbid,
reponse « OK <item> ADDED ») : la mise part chez Gixen sans copier-coller, et Gixen la place dans les dernieres secondes.

  - ses identifiants Gixen dans Render seulement (GIXEN_UTILISATEUR, GIXEN_MOT_DE_PASSE) : jamais dans l'app ni dans un
    journal ; l'adresse de l'appel (qui les contient) n'est jamais ecrite nulle part ;
  - toujours un tap de l'admin, une carte a la fois (ou « tout envoyer » qu'il touche lui-meme), le montant qu'il a vu ;
  - le montant est dans la devise de l'annonce (Gixen mise dans cette devise).
"""
import os
import re
import urllib.parse
import urllib.request

URL = "https://www.gixen.com/api.php"
DECALAGES = (3, 6, 8, 10, 15)               # secondes avant la fin (Gixen)


def actif():
    return bool(os.environ.get("GIXEN_UTILISATEUR", "").strip() and os.environ.get("GIXEN_MOT_DE_PASSE", ""))


def _appel(params, lire=None):
    q = {"username": os.environ.get("GIXEN_UTILISATEUR", "").strip(), "password": os.environ.get("GIXEN_MOT_DE_PASSE", ""),
         "notags": "1", **params}
    if lire:
        return lire(q)
    req = urllib.request.Request(URL + "?" + urllib.parse.urlencode(q), headers={"User-Agent": "SlabCoach/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.read(20000).decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return f"ERROR (HTTP{e.code}): Gixen a répondu {e.code}"
    except (urllib.error.URLError, TimeoutError) as e:
        return f"ERROR (RESEAU): Gixen injoignable ({getattr(e, 'reason', e)})"


def ajouter(item_id, mise, decalage=6, lire=None):
    """{ok, item_id, mise} ou {ok: False, erreur} (le message de Gixen tel quel)."""
    if not actif():
        return {"ok": False, "erreur": "Ajoute GIXEN_UTILISATEUR et GIXEN_MOT_DE_PASSE dans Render pour envoyer à Gixen"}
    item_id = str(item_id or "").strip()
    if not re.fullmatch(r"\d{9,15}", item_id):
        return {"ok": False, "erreur": "Numéro d'annonce eBay invalide"}
    try:
        mise = round(float(mise), 2)
    except (TypeError, ValueError):
        return {"ok": False, "erreur": "Montant invalide"}
    if mise <= 0:
        return {"ok": False, "erreur": "Montant invalide"}
    d = int(decalage) if int(decalage or 0) in DECALAGES else 6
    rep = _appel({"itemid": item_id, "maxbid": f"{mise:.2f}", "bidoffset": str(d)}, lire)
    if re.search(rf"OK\s+{item_id}\s+ADDED", rep or ""):
        return {"ok": True, "item_id": item_id, "mise": mise, "decalage": d}
    m = re.search(r"ERROR\s*\(([^)]*)\)\s*:?\s*(.*)", rep or "", re.S)
    msg = re.sub(r"<[^>]+>", " ", (m.group(2) if m else rep or "")).strip()[:200] or "réponse inattendue"
    return {"ok": False, "erreur": "Gixen : " + msg, "code": m.group(1) if m else None}
