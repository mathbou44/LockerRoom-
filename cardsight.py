"""
SLABCOACH - CardSight AI, en complement de la lecture par Claude (28 oct 2026, Mathieu : « ok go »).

CardSight reconnait la carte dans SON catalogue (16 M de cartes) : le nom exact du set, du numero et de la variante,
la ou une lecture « a l'oeil » hesite. On s'en sert seulement pour CONFIRMER ou COMPLETER les champs douteux de la
fiche : la lecture Claude reste la base, et un champ deja lu clairement n'est jamais remplace.

API (cardsight.ai, SDK officiel « cardsightai » 4.3) :
  POST https://api.cardsight.ai/v1/identify/card   (multipart, champ « image », en-tete X-API-Key)
  GET  https://api.cardsight.ai/v1/pricing/{card_id}?period=90d&listing_type=auction   (ventes)
Conditions (cardsight.ai/terms) : integration dans une app commerciale permise ; pas de base de donnees a part avec
leurs donnees (on ne garde rien) ; les photos envoyees peuvent servir a entrainer leurs modeles (dit dans la politique
de confidentialite). Prix : « fixed » = prix DEMANDE, pas une vente : on ne garde que les encans termines.
Eteint tant que CARDSIGHT_CLE n'est pas dans Render ; au plus CARDSIGHT_QUOTA appels par mois (700 par defaut,
le forfait gratuit en donne 750).
"""
import json
import os
import threading
import time
import urllib.error
import urllib.request
import uuid

BASE = "https://api.cardsight.ai"
_verrou = threading.Lock()


def actif():
    return bool(os.environ.get("CARDSIGHT_CLE", "").strip()) and os.environ.get("CARDSIGHT_ACTIF", "1") != "0"


def _quota():
    try:
        return max(0, int(os.environ.get("CARDSIGHT_QUOTA") or 700))
    except ValueError:
        return 700


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "cardsight_usage.json")


def _prendre_appel():
    """Compte un appel du mois (tout le serveur) ; False si le plafond est atteint."""
    mois = time.strftime("%Y-%m")
    with _verrou:
        try:
            with open(_chemin(), encoding="utf-8") as f:
                d = json.load(f) or {}
        except (OSError, ValueError):
            d = {}
        n = int(d.get(mois) or 0)
        if n >= _quota():
            return False
        d = {mois: n + 1}
        with open(_chemin(), "w", encoding="utf-8") as f:
            json.dump(d, f)
    return True


def _appel(meth, chemin, corps=None, type_=None, timeout=25):
    h = {"X-API-Key": os.environ.get("CARDSIGHT_CLE", "").strip(), "Accept": "application/json"}
    if type_:
        h["Content-Type"] = type_
    req = urllib.request.Request(BASE + chemin, data=corps, method=meth, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            brut = r.read()
            return r.status, (json.loads(brut) if brut else {})
    except urllib.error.HTTPError as e:
        return e.code, None
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return 0, None


def identifier(image):
    """Octets d'une photo -> {ok, confiance, champs} (champs au format de la fiche SlabCoach) ou {ok: False, erreur}."""
    if not actif():
        return {"ok": False, "erreur": "inactif"}
    if not image or len(image) > 20_000_000:
        return {"ok": False, "erreur": "photo"}
    if not _prendre_appel():
        return {"ok": False, "erreur": "quota"}
    borne = "SC" + uuid.uuid4().hex
    corps = (f"--{borne}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"carte.jpg\"\r\n"
             "Content-Type: image/jpeg\r\n\r\n").encode() + image + f"\r\n--{borne}--\r\n".encode()
    st, r = _appel("POST", "/v1/identify/card", corps, "multipart/form-data; boundary=" + borne)
    if st != 200 or not isinstance(r, dict):
        return {"ok": False, "erreur": f"CardSight {st}"}
    dets = [d for d in r.get("detections") or [] if isinstance(d, dict) and (d.get("card") or {}).get("name")]
    if not dets:
        return {"ok": False, "erreur": "carte pas trouvée"}
    d = dets[0]
    c, g = d.get("card") or {}, d.get("grading") or {}
    ch = {"joueur": c.get("name"), "annee": c.get("year"), "marque": c.get("manufacturer"),
          "set_nom": c.get("setName") or c.get("releaseName"), "numero": c.get("number"), "tirage": c.get("numberedTo")}
    par = [p for p in c.get("parallelSuggestions") or [] if isinstance(p, dict) and p.get("name")]
    if par and par[0].get("confidence") == "High":
        ch["parallele"] = par[0]["name"]
        ch["tirage"] = par[0].get("numberedTo") or ch["tirage"]
    comp, note = ((g.get("company") or {}).get("name"), (g.get("grade") or {}).get("value"))
    if comp and note and g.get("confidence") == "High":
        ch["grade"] = f"{comp} {note}".strip()
        if g.get("certNumber"):
            ch["cert"] = str(g["certNumber"])
    return {"ok": True, "confiance": d.get("confidence"), "id": c.get("id"),
            "champs": {k: (str(v).strip() if k != "tirage" else v) for k, v in ch.items() if v not in (None, "")}}


def completer(champs, douteux, image):
    """La fiche lue par Claude + la reconnaissance CardSight (confiance « High » seulement) :
    remplit les champs vides et confirme les champs douteux. -> (champs, douteux restants, source ou None)."""
    if not actif() or not image:
        return champs, douteux, None
    r = identifier(image)
    if not r.get("ok") or r.get("confiance") != "High":
        return champs, douteux, None
    out, reste = dict(champs or {}), set(douteux or [])
    for k, v in r["champs"].items():
        # 29 oct 2026 (Mathieu : « encore PSA 10 » sur une carte raw) : CardSight ne donne JAMAIS une note a une carte
        # que la lecture n'a pas vue dans un slab ; il peut seulement completer le certificat d'une carte gradee
        if k == "grade" or (k == "cert" and not out.get("grade")):
            continue
        if k == "tirage":
            try:
                v = int(v)
            except (TypeError, ValueError):
                continue
        if not out.get(k) or k in reste:
            if out.get(k) and str(out[k]).lower() != str(v).lower() and k == "joueur":
                continue                      # jamais un autre joueur : on garde la lecture et le doute
            out[k] = v
            reste.discard(k)
    return out, sorted(reste), "cardsight"
