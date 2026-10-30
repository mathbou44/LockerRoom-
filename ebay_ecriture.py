"""
LOCKERROOM - ecrire sur eBay (21 oct 2026, Mathieu : « effortless »).

Toujours declenche par un tap du vendeur, jamais en automatique :
  - publier()       : met une carte en vente (AddFixedPriceItem, apres VerifyAddFixedPriceItem)
  - changer_prix()  : nouveau prix d'une annonce a prix fixe (ReviseInventoryStatus)
  - miser()         : mise maximum (proxy bid) sur une enchere (API Offer)
  - donnees_test()  : SANDBOX SEULEMENT - remplit le compte vendeur de test

Le meme code sert en sandbox et en production (ebay_compte.environnement()).
"""
import base64
import os
import re
import urllib.request
from xml.sax.saxutils import escape

import ebay_compte
import ebay_csv

DOSSIER = os.path.dirname(os.path.abspath(__file__))
NS = "urn:ebay:apis:eBLBaseComponents"
# expedition et retours en ligne (vendeurs sans « business policies ») ; ajustables dans Reglages
EXPEDITION_DEFAUT = {"service": "CA_PostLettermail", "cout": 2.50, "delai": 3, "code_postal": "H2X 1Y4",
                     # 22 oct 2026 - la plupart des acheteurs de cartes sont aux E.-U. : livraison vers les E.-U. offerte
                     "us": True, "us_cout": 6.50}

# 22 oct 2026 - code eBay du service postal vers les E.-U., lu chez eBay (GeteBayDetails) plutot que devine :
# un mauvais code ferait echouer chaque annonce. Sans reponse d'eBay : pas d'option E.-U. (l'annonce part quand meme).
_PREF_US = ("TrackedPacketsUSA", "TrackedPacketUSA", "SmallPacketsUSA", "USALetterPost", "USA")
_cache_us = {"code": None, "le": 0.0}


def service_us():
    import time
    if _cache_us["code"] is not None or time.time() - _cache_us["le"] < 600:
        return _cache_us["code"] or None
    _cache_us["le"] = time.time()
    try:
        r = ebay_compte.trading("GeteBayDetails", f'<?xml version="1.0" encoding="utf-8"?><GeteBayDetailsRequest xmlns="{NS}">'
                                "<DetailName>ShippingServiceDetails</DetailName></GeteBayDetailsRequest>")
    except Exception:
        return None
    codes = []
    for d in r.findall("e:ShippingServiceDetails", ebay_compte._NS):
        code = ebay_compte._txt(d, "e:ShippingService") or ""
        if (ebay_compte._txt(d, "e:InternationalService") or "").lower() == "true" \
                and (ebay_compte._txt(d, "e:ValidForSellingFlow") or "true").lower() == "true" and "USA" in code:
            codes.append(code)
    choix = next((c for p in _PREF_US for c in codes if p in c), None)
    _cache_us["code"] = choix or ""
    return choix


def _livraison_xml(e):
    """<ShippingDetails> : Canada (service domestique) + E.-U. si un service valide est connu."""
    us = service_us() if e.get("us") else None
    return ("<ShippingDetails><ShippingType>Flat</ShippingType><ShippingServiceOptions>"
            f"<ShippingServicePriority>1</ShippingServicePriority><ShippingService>{escape(e['service'])}</ShippingService>"
            f'<ShippingServiceCost currencyID="CAD">{float(e["cout"]):.2f}</ShippingServiceCost>'
            "</ShippingServiceOptions>"
            + (f"<InternationalShippingServiceOption><ShippingService>{escape(us)}</ShippingService>"
               f'<ShippingServiceCost currencyID="CAD">{float(e["us_cout"]):.2f}</ShippingServiceCost>'
               "<ShippingServicePriority>1</ShippingServicePriority><ShipToLocation>US</ShipToLocation>"
               "</InternationalShippingServiceOption>" if us else "")
            + "</ShippingDetails>")


def _specifiques(carte):
    import sports                                   # 23 oct 2026 - NHL, NFL, NBA, MLB
    asp = sports.aspects_ebay(carte.get("sport") or sports.detecter(carte.get("titre"), carte.get("equipe"), defaut="hockey"))
    paires = [("Sport", asp["Sport"]), ("Player/Athlete", carte.get("joueur")), ("Manufacturer", carte.get("marque")),
              ("Season", carte.get("annee")), ("Set", carte.get("set_nom")), ("Parallel/Variety", carte.get("parallele")),
              ("Team", carte.get("equipe")), ("League", asp["League"]), ("Card Number", carte.get("numero")),
              ("Autographed", "Yes" if carte.get("auto") else "No"), ("Type", "Sports Trading Card")]
    if carte.get("tirage"):
        paires.append(("Print Run", str(carte["tirage"])))
    return "".join(f"<NameValueList><Name>{escape(n)}</Name><Value>{escape(str(v))[:65]}</Value></NameValueList>"
                   for n, v in paires if v not in (None, ""))


def _etat(carte):
    """ConditionID + descripteurs obligatoires des cartes (gradee : graduateur + note + no de certificat ; brute : etat).
    30 oct 2026 : toutes les notes d'eBay (1 a 10, Authentic) ; avant, une PSA 6 partait sans note et eBay refusait."""
    g = ebay_csv.lire_grade(carte.get("grade"))
    if g:
        desc = (f"<ConditionDescriptor><Name>27501</Name><Value>{ebay_csv.id_gradeur(g[0])}</Value></ConditionDescriptor>"
                f"<ConditionDescriptor><Name>27502</Name><Value>{ebay_csv.id_note(g[1])}</Value></ConditionDescriptor>")
        cert = re.sub(r"[^A-Za-z0-9-]", "", str(carte.get("cert") or ""))[:30]
        if cert:
            desc += f"<ConditionDescriptor><Name>27503</Name><AdditionalInfo>{cert}</AdditionalInfo></ConditionDescriptor>"
        return ebay_csv.CONDITION_GRADEE, desc
    return ebay_csv.CONDITION_NON_GRADEE, "<ConditionDescriptor><Name>40001</Name><Value>400010</Value></ConditionDescriptor>"


def xml_annonce(carte, prix, photos, description="", expedition=None, sku=None):
    e = {**EXPEDITION_DEFAUT, **(expedition or {})}
    cond, desc = _etat(carte)
    titre = (carte.get("titre") or ebay_csv.titre_annonce(carte))[:80]
    photos_xml = "".join(f"<PictureURL>{escape(u)}</PictureURL>" for u in (photos or [])[:12])
    return (f"<Item><Title>{escape(titre)}</Title>"
            f"<Description><![CDATA[{(description or titre).replace(']]>', '')}]]></Description>"
            f"<PrimaryCategory><CategoryID>{ebay_csv.CATEGORY_ID}</CategoryID></PrimaryCategory>"
            f'<StartPrice currencyID="CAD">{float(prix):.2f}</StartPrice>'
            f"<ConditionID>{cond}</ConditionID><ConditionDescriptors>{desc}</ConditionDescriptors>"
            f"<Country>CA</Country><Currency>CAD</Currency><PostalCode>{escape(e['code_postal'])}</PostalCode>"
            f"<DispatchTimeMax>{int(e['delai'])}</DispatchTimeMax><ListingDuration>GTC</ListingDuration>"
            f"<ListingType>FixedPriceItem</ListingType><Quantity>1</Quantity>"
            + (f"<PictureDetails>{photos_xml}</PictureDetails>" if photos_xml else "")
            + f"<ItemSpecifics>{_specifiques(carte)}</ItemSpecifics>"
            "<ReturnPolicy><ReturnsAcceptedOption>ReturnsNotAccepted</ReturnsAcceptedOption></ReturnPolicy>"
            + _livraison_xml(e)
            + (f"<SKU>{escape(str(sku))[:50]}</SKU>" if sku else "")
            + "</Item>")


def _requete(appel, item_xml):
    return f'<?xml version="1.0" encoding="utf-8"?><{appel}Request xmlns="{NS}">{item_xml}</{appel}Request>'


def publier(carte, prix, photos, description="", expedition=None, sku=None, verifier_seulement=False):
    """{ok, item_id, frais, avertissements}. Verifie d'abord : rien n'est cree si eBay refuse."""
    item = xml_annonce(carte, prix, photos, description, expedition, sku)
    v = ebay_compte.trading("VerifyAddFixedPriceItem", _requete("VerifyAddFixedPriceItem", item))
    frais = _frais(v)
    if verifier_seulement:
        return {"ok": True, "verifie": True, "frais": frais, "frais_detail": frais_detail(v), "avertissements": ebay_compte.avertissements(v)}
    r = ebay_compte.trading("AddFixedPriceItem", _requete("AddFixedPriceItem", item))
    return {"ok": True, "item_id": ebay_compte._txt(r, "e:ItemID"), "frais": frais, "avertissements": ebay_compte.avertissements(r)}


# 30 oct 2026 (Mathieu : « depuis quand j'ai des frais d'insertion ? ») : on additionnait TOUTES les lignes de <Fees>,
# y compris « ListingFee » (le total des autres, donc compte deux fois) et sans retirer les rabais promotionnels (les
# annonces gratuites du mois). Maintenant : chaque frais moins son rabais, sans le total d'eBay.
NOMS_FRAIS = {"InsertionFee": ("Frais d'insertion", "Insertion fee"), "ScheduleFee": ("Programmation", "Scheduling"),
              "GalleryFee": ("Galerie", "Gallery"), "GalleryPlusFee": ("Gallery Plus", "Gallery Plus"),
              "SubtitleFee": ("Sous-titre", "Subtitle"), "BoldFee": ("Gras", "Bold"), "ReserveFee": ("Prix de réserve", "Reserve"),
              "BuyItNowFee": ("Achat immédiat", "Buy It Now"), "InternationalInsertionFee": ("Insertion internationale", "International insertion")}


def frais_detail(racine):
    out = []
    for f in racine.findall("e:Fees/e:Fee", ebay_compte._NS):
        nom = ebay_compte._txt(f, "e:Name") or ""
        if nom == "ListingFee":                         # le total d'eBay : deja compte dans les lignes
            continue
        try:
            m = float(ebay_compte._txt(f, "e:Fee") or 0) - float(ebay_compte._txt(f, "e:PromotionalDiscount") or 0)
        except ValueError:
            continue
        if m > 0.004:
            out.append({"nom": nom, "fr": NOMS_FRAIS.get(nom, (nom, nom))[0], "en": NOMS_FRAIS.get(nom, (nom, nom))[1], "montant": round(m, 2)})
    return out


def _frais(racine):
    return round(sum(x["montant"] for x in frais_detail(racine)), 2)


def changer_prix(item_id, prix):
    item_id = str(item_id or "").strip()
    if not re.fullmatch(r"\d{9,15}", item_id):
        raise ValueError("Numéro d'annonce eBay invalide")
    prix = float(prix)
    if prix < 0.99:
        raise ValueError("Prix trop bas (minimum 0,99 $)")
    import ebay_moderne                     # 27 oct 2026 : annonce creee par l'Inventory API -> son offre
    r = ebay_moderne.changer_prix(item_id, prix)
    if r:
        return r
    corps = (f'<?xml version="1.0" encoding="utf-8"?><ReviseInventoryStatusRequest xmlns="{NS}">'
             f"<InventoryStatus><ItemID>{item_id}</ItemID><StartPrice>{prix:.2f}</StartPrice></InventoryStatus>"
             "</ReviseInventoryStatusRequest>")
    r = ebay_compte.trading("ReviseInventoryStatus", corps)
    return {"ok": True, "item_id": item_id, "prix": round(prix, 2), "avertissements": ebay_compte.avertissements(r)}


def id_rest(item_id):
    """« 1234567890 » (numero d'annonce) -> « v1|1234567890|0 » (format des API Buy)."""
    s = str(item_id or "").strip()
    return s if s.startswith("v1|") else f"v1|{s}|0"


def miser(item_id, montant, devise="CAD"):
    """Mise MAXIMUM (eBay surenchérit pour toi jusqu'a ce montant). Un tap = une mise."""
    montant = float(montant)
    if montant <= 0:
        raise ValueError("Montant invalide")
    adresse = ebay_compte.url("offre") + "/" + urllib.request.quote(id_rest(item_id), safe="") + "/place_proxy_bid"
    r = ebay_compte.post_json(adresse, {"maxAmount": {"value": f"{montant:.2f}", "currency": devise},
                                        "userConsent": {"adultOnlyItem": False}})
    return {"ok": True, "item_id": str(item_id), "mise_max": round(montant, 2), "proxy_bid_id": r.get("proxyBidId")}


def televerser_photo(chemin, nom="lockerroom"):
    """Photo -> URL d'image hebergee par eBay. 27 oct 2026 : UploadSiteHostedPictures (Trading) a ete retire par eBay
    le 30 sept. 2026 ; on passe par la Media API (createImageFromFile), meme resultat (une URL EPS)."""
    import ebay_moderne
    return ebay_moderne.televerser_fichier(chemin, nom)


def cartes_test(n=20):
    """Cartes fictives realistes tirees du catalogue (recrues d'abord : vrais joueurs, sets, numeros)."""
    import calcul
    import catalogue
    out = []
    for p in catalogue.liste():
        try:
            prod = catalogue.charger(p["id"])
        except Exception:
            continue
        cartes = sorted(prod.get("cartes") or [], key=lambda c: not c.get("recrue"))
        for c in cartes[:4]:
            eq = str(c.get("equipe") or "").split("/")[0]
            out.append({"joueur": c.get("joueur"), "annee": prod.get("saison"), "marque": prod.get("marque") or "Upper Deck",
                        "set_nom": re.sub(r"^\d{4}-\d{2}\s+(Upper Deck\s+)?", "", prod.get("nom") or ""),
                        "parallele": c.get("sous_ensemble"), "numero": c.get("numero"), "tirage": c.get("tirage"),
                        "auto": 1 if c.get("auto") else 0, "equipe": (calcul.EQUIPES_LNH.get(eq) or (eq,))[0]})
            if len(out) >= n:
                return out
    return out


def livraison_us_tests():
    """SANDBOX SEULEMENT (22 oct 2026) : ajoute la livraison vers les E.-U. aux annonces deja en ligne
    (l'acheteur de test sandbox est aux E.-U. : sans elle, eBay bloque l'achat)."""
    if ebay_compte.environnement() != "sandbox":
        raise RuntimeError("Réservé au sandbox")
    if not service_us():
        raise RuntimeError("eBay n'a renvoyé aucun service postal vers les É.-U. pour ce compte")
    det = _livraison_xml(dict(EXPEDITION_DEFAUT))
    faites, erreurs = 0, []
    for a in ebay_compte.annonces_actives():
        iid = str(a.get("item_number") or a.get("item_id") or "")
        if not iid:
            continue
        try:
            ebay_compte.trading("ReviseFixedPriceItem", _requete("ReviseFixedPriceItem", f"<Item><ItemID>{escape(iid)}</ItemID>{det}</Item>"))
            faites += 1
        except RuntimeError as ex:
            erreurs.append(str(ex)[:200])
            if len(erreurs) >= 3 and not faites:
                break
    return {"ok": bool(faites), "creees": faites, "erreurs": erreurs[:5], "service": service_us()}


def donnees_test(n=20, prix_base=4.99, progression=None):
    """SANDBOX SEULEMENT : n annonces au vendeur de test connecte, pour remplir l'app."""
    if ebay_compte.environnement() != "sandbox":
        raise RuntimeError("Réservé au sandbox : passe en mode Sandbox dans Réglages")
    photo = televerser_photo(os.path.join(DOSSIER, "ui", "icone-512.png"), "lockerroom-test")
    faites, erreurs = [], []
    lot = cartes_test(n)
    for i, c in enumerate(lot):
        if progression:
            progression(i, len(lot))
        try:
            r = publier(c, prix_base + i, [photo], "Annonce de test SlabCoach (sandbox)", sku=f"LR-TEST-{i + 1}")
            faites.append({"item_id": r["item_id"], "titre": ebay_csv.titre_annonce(c)})
        except (RuntimeError, ValueError) as e:
            erreurs.append(str(e)[:200])
            if len(erreurs) >= 3 and not faites:
                break               # meme erreur partout : inutile d'insister
    return {"ok": bool(faites), "creees": len(faites), "annonces": faites, "erreurs": erreurs[:5]}
