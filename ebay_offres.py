"""
SLABCOACH - offres aux acheteurs interesses (28 oct 2026, Mathieu : « go pour celle de eBay »).

API officielle d'eBay « Negotiation » (scope sell.inventory, deja demande a la connexion) :
  GET  /sell/negotiation/v1/find_eligible_items             -> les annonces qu'un acheteur surveille (Watch list) ou a
                                                               laissees dans son panier
  POST /sell/negotiation/v1/send_offer_to_interested_buyers -> une offre (rabais en %, 5 % minimum) a ces acheteurs,
                                                               une annonce par appel ; eBay previent chaque acheteur
Regles d'eBay qu'on respecte : pas de contre-offre (allowCounterOffer=false), duree standard du site (offerDuration
vide, sinon l'appel echoue), message sans HTML (2 000 caracteres max), annonces de la Trading API seulement.
Rien n'est envoye sans le tap du vendeur. Le site : EBAY_CA d'abord ; si eBay repond « site non pris en charge »
(150002), on essaie EBAY_US et on retient celui qui marche.
"""
import json
import os
import time

import ebay_moderne as em

BASE = "/sell/negotiation/v1"
GARDE_S = 3600
ERREURS = {
    "150002": "eBay n’offre pas encore les offres aux acheteurs intéressés sur ce site",
    "150008": "Rabais trop petit pour eBay : essaie un plus grand %",
    "150011": "Cette annonce est terminée",
    "150012": "Annonce introuvable dans ton compte eBay",
    "150015": "Le prix après rabais est sous le minimum d’eBay",
    "150017": "Cette annonce n’accepte pas les offres",
    "150018": "Une offre est déjà en cours sur cette annonce",
    "150019": "Tu as déjà envoyé une offre pour cette annonce",
    "150020": "Plus d’acheteur intéressé pour cette annonce",
    "150022": "Limite d’offres d’eBay atteinte pour cette annonce",
    "150023": "Limite d’offres d’eBay atteinte pour aujourd’hui",
    "150010": "Message refusé par eBay (mot interdit ou trop long)",
}


def _chemin():
    import comptes
    return os.path.join(comptes.dossier() or comptes.DONNEES, "offres_acheteurs.json")


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


def _marches(d):
    m = d.get("marche")
    return [m] if m else [em.MARCHE, "EBAY_US"]


def _message_erreur(e):
    for i in getattr(e, "ids", ()) or ():
        if str(i) in ERREURS:
            return ERREURS[str(i)]
    return str(e)


def eligibles(force=False):
    """Les numeros d'annonce qui ont des acheteurs interesses (garde 1 h) -> {ok, ids, marche, le} ou {ok: False, erreur}."""
    d = _lire()
    g = d.get("eligibles") or {}
    if not force and g.get("le") and time.time() - g["le"] < GARDE_S:
        return {"ok": True, **g, "garde": True}
    derniere = None
    for m in _marches(d):
        try:
            ids, offset = [], 0
            while offset < 1000:
                st, _h, r = em.rest("GET", f"{BASE}/find_eligible_items?limit=200&offset={offset}", marche=m)
                l = [x.get("listingId") for x in (r or {}).get("eligibleItems") or [] if x.get("listingId")]
                ids += l
                if st == 204 or not l or not (r or {}).get("next"):
                    break
                offset += 200
            g = {"ids": ids, "marche": m, "le": time.time()}
            d["eligibles"], d["marche"] = g, m
            _ecrire(d)
            return {"ok": True, **g}
        except em.ErreurEbay as e:
            derniere = e
            if "150002" in [str(i) for i in e.ids]:
                continue
            break
    return {"ok": False, "erreur": _message_erreur(derniere) if derniere else "eBay ne répond pas"}


def envoyer(listing_id, pct, message=None):
    """Une offre (rabais pct %) aux acheteurs interesses d'une annonce. -> {ok, n} ou {ok: False, erreur}."""
    try:
        pct = round(float(pct), 1)
    except (TypeError, ValueError):
        return {"ok": False, "erreur": "Rabais invalide"}
    if pct < 5 or pct > 50:
        return {"ok": False, "erreur": "Le rabais doit être entre 5 % et 50 %"}
    corps = {"allowCounterOffer": False,
             "offeredItems": [{"listingId": str(listing_id), "discountPercentage": f"{pct:g}", "quantity": 1}]}
    msg = " ".join(str(message or "").replace("<", " ").replace(">", " ").split())[:500]
    if msg:
        corps["message"] = msg
    d = _lire()
    try:
        _st, _h, r = em.rest("POST", f"{BASE}/send_offer_to_interested_buyers", corps, marche=_marches(d)[0])
    except em.ErreurEbay as e:
        return {"ok": False, "erreur": _message_erreur(e)}
    n = len((r or {}).get("offers") or [])
    j = d.setdefault("journal", [])
    j.append({"le": time.time(), "item": str(listing_id), "pct": pct, "n": n})
    d["journal"] = j[-300:]
    g = d.get("eligibles") or {}
    if g.get("ids"):                                     # l'annonce n'est plus eligible (offre en cours)
        g["ids"] = [i for i in g["ids"] if i != str(listing_id)]
    _ecrire(d)
    return {"ok": True, "n": n}


def recentes(jours=3):
    """Annonces qui ont recu une offre de nous ces derniers jours (on ne les repropose pas)."""
    lim = time.time() - jours * 86400
    return {x["item"] for x in (_lire().get("journal") or []) if x.get("le", 0) >= lim}
