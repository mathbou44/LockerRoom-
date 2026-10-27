"""
SLABCOACH - les API modernes d'eBay (27 oct 2026, Mathieu : « prepare le tout »).

eBay a lance ses « Modernized APIs » (REST + GraphQL) et retire peu a peu les API Traditional (SOAP/XML).
  1. PHOTOS (deja en service) : UploadSiteHostedPictures (Trading) a ete retire le 30 sept. 2026.
     -> Media API createImageFromFile (scope sell.inventory, que les comptes ont deja).
  2. ANNONCES (pret, derriere l'interrupteur LOCKERROOM_EBAY_API=inventaire ; « classique » par defaut) :
     AddFixedPriceItem / AddItem -> Inventory API : inventory_item + offer + publish,
     avec les politiques d'affaires (Account API : expedition, paiement, retours) et un emplacement d'inventaire.
     ReviseInventoryStatus -> bulk_update_price_quantity ; fin d'annonce -> withdraw.
     Demande en plus le scope sell.account (les vendeurs reconnectent eBay une fois, comme pour la nouvelle cle).
  3. LECTURES (GetMyeBaySelling, GetOrders acheteur, GetItem) : pas encore retirees, sans equivalent REST complet
     annonce ; on garde Trading et on suit les annonces d'eBay (requete GraphQL sellerListings a venir).
Toujours declenche par un geste du vendeur. Rien n'est publie sans « Publier ».
"""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid

import ebay_compte

MARCHE = "EBAY_CA"
LANGUE = "en-CA"
SCOPE_COMPTE = "https://api.ebay.com/oauth/api_scope/sell.account"
MEDIA = {"production": "https://apim.ebay.com", "sandbox": "https://apim.sandbox.ebay.com"}


def mode():
    """« inventaire » : annonces par l'Inventory API ; sinon « classique » (Trading, comme avant)."""
    return "inventaire" if os.environ.get("LOCKERROOM_EBAY_API", "").strip().lower() == "inventaire" else "classique"


class ErreurEbay(RuntimeError):
    def __init__(self, msg, code=0, ids=()):
        super().__init__(msg)
        self.code, self.ids = code, tuple(ids)


def _api():
    return ebay_compte._env()["api"]


def _envoyer(req, timeout=40):
    import appels_ebay
    appels_ebay.compter("autre")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            brut = r.read()
            return r.status, dict(r.headers), (json.loads(brut) if brut else {})
    except urllib.error.HTTPError as e:
        texte = e.read().decode("utf-8", "ignore")
        try:
            erreurs = json.loads(texte).get("errors") or []
        except ValueError:
            erreurs = []
        msg = " · ".join(x.get("longMessage") or x.get("message") or "" for x in erreurs) or texte[:200]
        ids = [x.get("errorId") for x in erreurs if x.get("errorId")]
        if e.code in (401, 403):
            raise ErreurEbay("eBay refuse cet accès : reconnecte eBay dans Réglages pour donner la permission (" + (msg or str(e.code)) + ")", e.code, ids)
        if e.code == 404:
            raise ErreurEbay(msg or "introuvable chez eBay", 404, ids)
        raise ErreurEbay(f"eBay {e.code} : {msg}", e.code, ids)


def rest(meth, chemin, corps=None, base=None, marche=True):
    """Appel REST eBay avec le jeton du vendeur. chemin : « /sell/inventory/v1/... »."""
    h = {"Authorization": "Bearer " + ebay_compte.jeton(), "Accept": "application/json", "Content-Language": LANGUE}
    if marche:
        h["X-EBAY-C-MARKETPLACE-ID"] = MARCHE
    data = None
    if corps is not None:
        data = json.dumps(corps).encode()
        h["Content-Type"] = "application/json"
    return _envoyer(urllib.request.Request((base or _api()) + chemin, data=data, method=meth, headers=h))


# ---------------------------------------------------------------------------------------------------------------
# 1. Photos : Media API (remplace UploadSiteHostedPictures, retire le 30 sept. 2026)
# ---------------------------------------------------------------------------------------------------------------
def _type_image(b):
    if b[:3] == b"\xff\xd8\xff":
        return "image/jpeg", "jpg"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png", "png"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "image/webp", "webp"
    if b[4:12] in (b"ftypheic", b"ftypheix", b"ftypmif1"):
        return "image/heic", "heic"
    raise ValueError("Photo : format pas reconnu (JPG, PNG, WEBP ou HEIC)")


def televerser_image(contenu, nom="slabcoach"):
    """Octets d'une photo -> URL d'image hebergee par eBay (EPS), utilisable dans Trading (PictureURL) et Inventory (imageUrls)."""
    if not contenu:
        raise ValueError("Photo vide")
    if len(contenu) > 12_000_000:
        raise ValueError("Photo trop lourde : reprends-la")
    mime, ext = _type_image(contenu)
    nom = re.sub(r"[^\w.-]", "-", str(nom or "slabcoach"))[:40]
    borne = "SC" + uuid.uuid4().hex
    corps = (f"--{borne}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{nom}.{ext}\"\r\n"
             f"Content-Type: {mime}\r\n\r\n").encode() + contenu + f"\r\n--{borne}--\r\n".encode()
    base = MEDIA[ebay_compte.environnement()] + "/commerce/media/v1_beta"
    req = urllib.request.Request(base + "/image/create_image_from_file", data=corps, method="POST", headers={
        "Authorization": "Bearer " + ebay_compte.jeton(), "Accept": "application/json",
        "Content-Type": f"multipart/form-data; boundary={borne}"})
    try:
        _st, h, d = _envoyer(req, timeout=90)
    except ErreurEbay as e:
        raise RuntimeError("Photo refusée par eBay : " + str(e)) from None
    u = (d or {}).get("imageUrl")
    if not u:                                          # au besoin, l'adresse d'image renvoyee dans Location
        loc = h.get("Location") or h.get("location") or ""
        m = re.search(r"/image/([^/?#]+)", loc)
        if m:
            _st, _h, g = _envoyer(urllib.request.Request(base + "/image/" + urllib.parse.quote(m.group(1)), method="GET", headers={
                "Authorization": "Bearer " + ebay_compte.jeton(), "Accept": "application/json"}))
            u = (g or {}).get("imageUrl")
    if not u:
        raise RuntimeError("Photo : eBay n'a pas renvoyé d'adresse d'image")
    return u


def televerser_fichier(chemin, nom="slabcoach"):
    with open(chemin, "rb") as f:
        return televerser_image(f.read(), nom)


# ---------------------------------------------------------------------------------------------------------------
# 2. Annonces : Inventory API + politiques d'affaires (Account API) + emplacement
# ---------------------------------------------------------------------------------------------------------------
def _fichier_compte(nom):
    import comptes
    d = comptes.dossier() or ebay_compte.DOSSIER
    return os.path.join(d, f"{nom}_{ebay_compte.environnement()}.json")


def _lire(nom):
    try:
        with open(_fichier_compte(nom), encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def _ecrire(nom, d):
    p = _fichier_compte(nom)
    t = p + ".tmp"
    with open(t, "w", encoding="utf-8") as f:
        json.dump(d, f)
    os.replace(t, p)


def cle_emplacement(code_postal):
    return "slabcoach-" + re.sub(r"[^a-z0-9]", "", str(code_postal or "").lower())[:30]


def emplacement(code_postal):
    """L'emplacement d'inventaire (obligatoire pour une offre) : cree une fois, a partir du code postal."""
    cp = str(code_postal or "").strip().upper()
    if not re.fullmatch(r"[A-Z]\d[A-Z] ?\d[A-Z]\d", cp):
        raise ValueError("Code postal canadien requis (ex. H2X 1Y4) pour l'emplacement eBay")
    cle = cle_emplacement(cp)
    try:
        rest("GET", "/sell/inventory/v1/location/" + cle, marche=False)
        return cle
    except ErreurEbay as e:
        if e.code != 404:
            raise
    rest("POST", "/sell/inventory/v1/location/" + cle, {
        "location": {"address": {"postalCode": cp, "country": "CA"}}, "locationTypes": ["WAREHOUSE"],
        "name": "SlabCoach", "merchantLocationStatus": "ENABLED"}, marche=False)
    return cle


def _politiques_actives():
    _st, _h, d = rest("GET", "/sell/account/v1/program/get_opted_in_programs", marche=False)
    if any(p.get("programType") == "SELLING_POLICY_MANAGEMENT" for p in (d or {}).get("programs") or []):
        return True
    rest("POST", "/sell/account/v1/program/opt_in", {"programType": "SELLING_POLICY_MANAGEMENT"}, marche=False)
    raise RuntimeError("eBay active les politiques d'affaires de ton compte (souvent quelques minutes, jusqu'à 24 h). "
                       "Réessaie de publier un peu plus tard.")


def _nom_politique(genre, d):
    m = d.get("expedition") or "lettre"
    if genre == "expedition":
        return f"SlabCoach · {m} · {int(d.get('delai') or 2)} j" + (" · E.-U." if d.get("us") else "")
    if genre == "retours":
        return "SlabCoach · " + {"30_acheteur": "retours 30 j (acheteur)", "30_gratuit": "retours 30 j (gratuits)"}.get(d.get("retours"), "vente finale")
    return "SlabCoach · paiement"


def _corps_expedition(d, nom):
    import annonces
    m = d.get("expedition") or "lettre"
    gratuit = m == "gratuit"
    cout = 0.0 if gratuit else float(d.get("cout_suivi" if m == "suivi" else "cout_lettre") or 0)
    opts = [{"optionType": "DOMESTIC", "costType": "FLAT_RATE", "shippingServices": [{
        "sortOrder": 1, "shippingServiceCode": annonces.service("suivi" if gratuit else m, "ca"),
        "shippingCost": {"value": f"{cout:.2f}", "currency": "CAD"}, "freeShipping": gratuit}]}]
    if d.get("us"):
        s_us = annonces.service("suivi" if m in ("suivi", "gratuit") else "lettre", "us")
        if s_us:
            cu = float(d.get("us_cout_suivi" if m in ("suivi", "gratuit") else "us_cout_lettre") or 0)
            opts.append({"optionType": "INTERNATIONAL", "costType": "FLAT_RATE", "shippingServices": [{
                "sortOrder": 1, "shippingServiceCode": s_us, "shippingCost": {"value": f"{cu:.2f}", "currency": "CAD"},
                "shipToLocations": {"regionIncluded": [{"regionName": "US"}]}}]})
    return {"name": nom, "marketplaceId": MARCHE, "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
            "handlingTime": {"value": int(d.get("delai") or 2), "unit": "DAY"}, "shippingOptions": opts}


def _corps_retours(d, nom):
    r = d.get("retours")
    if r in ("30_acheteur", "30_gratuit"):
        return {"name": nom, "marketplaceId": MARCHE, "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
                "returnsAccepted": True, "returnPeriod": {"value": 30, "unit": "DAY"}, "refundMethod": "MONEY_BACK",
                "returnShippingCostPayer": "BUYER" if r == "30_acheteur" else "SELLER"}
    return {"name": nom, "marketplaceId": MARCHE, "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}], "returnsAccepted": False}


def _corps_paiement(nom):
    return {"name": nom, "marketplaceId": MARCHE, "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}], "immediatePay": True}


_RESSOURCES = {"expedition": ("fulfillment_policy", "fulfillmentPolicies", "fulfillmentPolicyId"),
               "retours": ("return_policy", "returnPolicies", "returnPolicyId"),
               "paiement": ("payment_policy", "paymentPolicies", "paymentPolicyId")}


def politique(genre, d):
    """Id de la politique SlabCoach qui correspond aux choix de l'annonce : trouvee, sinon creee (une seule fois)."""
    nom = _nom_politique(genre, d)
    cache = _lire("ebay_politiques")
    if cache.get(nom):
        return cache[nom]
    res, liste, champ = _RESSOURCES[genre]
    _st, _h, r = rest("GET", f"/sell/account/v1/{res}?marketplace_id={MARCHE}", marche=False)
    pid = next((p.get(champ) for p in (r or {}).get(liste) or [] if p.get("name") == nom), None)
    if not pid:
        corps = {"expedition": _corps_expedition, "retours": _corps_retours}.get(genre)
        corps = corps(d, nom) if corps else _corps_paiement(nom)
        _st, _h, c = rest("POST", f"/sell/account/v1/{res}", corps, marche=False)
        pid = (c or {}).get(champ)
    if not pid:
        raise RuntimeError("eBay n'a pas créé la politique « " + nom + " »")
    cache[nom] = pid
    _ecrire("ebay_politiques", cache)
    return pid


def etat_structure(c, etat):
    """Etat + descripteurs (memes codes que l'annonce classique) au format Inventory API."""
    import annonces
    import ebay_csv
    cond_id, desc_xml = annonces._xml_etat(c, etat)
    descs = [{"name": n, "values": [v]} for n, v in re.findall(r"<Name>(\d+)</Name><Value>(\d+)</Value>", desc_xml)]
    # Inventory API : etats en mots ; 2750 (gradee) = LIKE_NEW, 4000 (non gradee) = USED_VERY_GOOD (categorie cartes)
    cond = "LIKE_NEW" if str(cond_id) == str(ebay_csv.CONDITION_GRADEE) else "USED_VERY_GOOD"
    return cond, descs


def sku_de(d):
    s = str(d.get("sku") or "").strip()
    if not s:
        c = d.get("carte") or {}
        s = "SC-" + str(c.get("id") or uuid.uuid4().hex[:10])
    return re.sub(r"[^A-Za-z0-9_.-]", "-", s)[:50]


def corps_article(d, photos):
    import annonces
    c = d.get("carte") or {}
    cond, descs = etat_structure(c, d.get("etat"))
    aspects = {n: (v if isinstance(v, list) else [v]) for n, v in annonces.specifiques(c)}
    g = max(10, int(float(d.get("poids_g") or 30)))
    lettre = (d.get("expedition") or "lettre") == "lettre"
    return {"availability": {"shipToLocationAvailability": {"quantity": 1}},
            "condition": cond, "conditionDescriptors": descs,
            "product": {"title": str(d["titre"])[:80], "description": str(d.get("description") or d["titre"]),
                        "aspects": aspects, "imageUrls": list(photos or [])[:24]},
            "packageWeightAndSize": {"weight": {"value": g, "unit": "GRAM"},
                                     "dimensions": {"length": 16 if lettre else 20, "width": 11 if lettre else 15,
                                                    "height": 1 if lettre else 2, "unit": "CENTIMETER"},
                                     "packageType": "LETTER" if lettre else "PADDED_BAGS"}}


def corps_offre(d, sku, cle_empl, politiques):
    import ebay_csv
    prix = float(d["prix"])
    encan = d.get("format") == "encan"
    pol = {"fulfillmentPolicyId": politiques["expedition"], "paymentPolicyId": politiques["paiement"],
           "returnPolicyId": politiques["retours"]}
    if not encan and d.get("offres"):
        pa = d.get("offre_auto_pct")
        auto = round(prix * float(90 if pa is None else pa) / 100, 2)
        mini = round(prix * float(d.get("offre_min_pct") or 70) / 100, 2)
        t = {"bestOfferEnabled": True}
        if 0 < auto < prix:
            t["autoAcceptPrice"] = {"value": f"{auto:.2f}", "currency": "CAD"}
        if 0 < mini < (auto or prix):
            t["autoDeclinePrice"] = {"value": f"{mini:.2f}", "currency": "CAD"}
        pol["bestOfferTerms"] = t
    o = {"sku": sku, "marketplaceId": MARCHE, "format": "AUCTION" if encan else "FIXED_PRICE", "availableQuantity": 1,
         "categoryId": str(ebay_csv.CATEGORY_ID), "listingDescription": str(d.get("description") or d["titre"]),
         "listingDuration": "DAYS_7" if encan else "GTC", "listingPolicies": pol, "merchantLocationKey": cle_empl}
    if encan:
        o["pricingSummary"] = {"auctionStartPrice": {"value": f"{prix:.2f}", "currency": "CAD"}}
    else:
        o["pricingSummary"] = {"price": {"value": f"{prix:.2f}", "currency": "CAD"}}
    return o


def _offre_existante(sku):
    try:
        _st, _h, r = rest("GET", "/sell/inventory/v1/offer?sku=" + urllib.parse.quote(sku) + "&marketplace_id=" + MARCHE)
    except ErreurEbay as e:
        if e.code == 404:
            return None
        raise
    l = [o for o in (r or {}).get("offers") or [] if o.get("marketplaceId") == MARCHE]
    return l[0] if l else None


def publier(d, photos, code_postal, verifier_seulement=False):
    """Meme reponse que la publication classique : {ok, item_id, frais, avertissements} (ou {ok, verifie, frais})."""
    _politiques_actives()
    cle = emplacement(code_postal)
    pols = {g: politique(g, d) for g in ("expedition", "paiement", "retours")}
    sku = sku_de(d)
    rest("PUT", "/sell/inventory/v1/inventory_item/" + urllib.parse.quote(sku), corps_article(d, photos))
    corps = corps_offre(d, sku, cle, pols)
    ex = _offre_existante(sku)
    if ex and ex.get("status") == "PUBLISHED" and ex.get("listing", {}).get("listingStatus") == "ACTIVE":
        raise RuntimeError("Cette carte est déjà en vente sur eBay")
    if ex:
        rest("PUT", "/sell/inventory/v1/offer/" + ex["offerId"], corps)
        oid = ex["offerId"]
    else:
        _st, _h, r = rest("POST", "/sell/inventory/v1/offer", corps)
        oid = r.get("offerId")
    _st, _h, f = rest("POST", "/sell/inventory/v1/offer/get_listing_fees", {"offers": [{"offerId": oid}]})
    frais = 0.0
    for s in (f or {}).get("feeSummaries") or []:
        for x in s.get("fees") or []:
            try:
                frais += float((x.get("amount") or {}).get("value") or 0)
            except (TypeError, ValueError):
                pass
    avert = [w.get("message") for s in (f or {}).get("feeSummaries") or [] for w in s.get("warnings") or [] if w.get("message")]
    if verifier_seulement:
        return {"ok": True, "verifie": True, "frais": round(frais, 2), "avertissements": avert}
    _st, _h, p = rest("POST", f"/sell/inventory/v1/offer/{oid}/publish")
    iid = (p or {}).get("listingId")
    if not iid:
        raise RuntimeError("eBay n'a pas publié l'annonce")
    carte = _lire("ebay_offres")
    carte[str(iid)] = {"sku": sku, "offer_id": oid}
    _ecrire("ebay_offres", carte)
    avert += [w.get("message") for w in (p or {}).get("warnings") or [] if w.get("message")]
    return {"ok": True, "item_id": str(iid), "frais": round(frais, 2), "avertissements": avert, "api": "inventaire"}


def offre_de(item_id):
    """L'offre Inventory API d'une annonce creee par SlabCoach en mode inventaire (sinon None : annonce classique)."""
    return _lire("ebay_offres").get(str(item_id))


def changer_prix(item_id, prix):
    o = offre_de(item_id)
    if not o:
        return None
    prix = float(prix)
    _st, _h, r = rest("POST", "/sell/inventory/v1/bulk_update_price_quantity", {"requests": [{
        "sku": o["sku"], "offers": [{"offerId": o["offer_id"], "price": {"value": f"{prix:.2f}", "currency": "CAD"}}]}]})
    for x in (r or {}).get("responses") or []:
        if int(x.get("statusCode") or 200) >= 400:
            raise RuntimeError("Prix refusé par eBay : " + " · ".join(e.get("message", "") for e in x.get("errors") or []))
    return {"ok": True, "item_id": str(item_id), "prix": round(prix, 2), "avertissements": [], "api": "inventaire"}


def retirer(item_id):
    """Termine une annonce creee en mode inventaire (withdraw : l'article reste dans l'inventaire eBay)."""
    o = offre_de(item_id)
    if not o:
        return None
    rest("POST", f"/sell/inventory/v1/offer/{o['offer_id']}/withdraw")
    return {"ok": True, "item_id": str(item_id), "api": "inventaire"}


def scopes_en_plus():
    return [SCOPE_COMPTE] if mode() == "inventaire" else []
