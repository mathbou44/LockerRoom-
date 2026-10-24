"""
LOCKERROOM - « Vendre » : une annonce eBay complete a partir des photos (24 oct 2026).

Mathieu : « il manque la section pour creer des annonces cote seller. oubli pas que tout doit se faire
a partir des photos. on veut toutes les sections de eBay necessaires pour une bonne annonce : titre, prix,
description, attributes, shipping specs, cout methode etc., si retour accepte, promotion (choisi son %),
offers accepted etc. doit etre tres tres tres friendly user »

  preparer(champs)  : titre optimise (80 car.), prix suggere (memes cartes, cartes_match), description
                      (bilingue pour un vendeur francophone), caracteristiques eBay, etat.
  xml_item(d)       : l'annonce complete (prix fixe ou encan 7 jours, offres, retours, expedition, colis).
  publier(d)        : photos televersees chez eBay, verification (frais) puis creation, promotion %.
Toujours declenche par le tap du vendeur. Rien n'est publie sans « Publier ».
"""
import base64
import os
import re
import tempfile
from datetime import datetime, timezone
from xml.sax.saxutils import escape

import ebay_compte
import ebay_csv
import ebay_ecriture

NS = ebay_ecriture.NS
MODELE_DEFAUT = {
    "format": "fixe",                       # fixe (Bon prix, jusqu'a la vente) | encan (7 jours)
    "expedition": "lettre",                 # lettre | suivi | gratuit
    "cout_lettre": 2.50, "cout_suivi": 12.00, "us": True, "us_cout_lettre": 6.50, "us_cout_suivi": 22.00,
    "delai": 2, "poids_g": 30,
    "retours": "non",                       # non | 30_acheteur | 30_gratuit
    "offres": True, "offre_auto_pct": 90, "offre_min_pct": 70,
    "promotion": 0,                         # % Promoted Listings (0 = pas de promotion)
    "etat": "nm",                           # carte brute : nm | ex | vg | p
}
# carte brute : descripteur eBay 40001 (Card Condition)
ETATS_BRUTS = {"nm": ("400010", "Near Mint or Better", "Quasi neuve ou mieux"), "ex": ("400011", "Excellent", "Excellente"),
               "vg": ("400012", "Very Good", "Très bonne"), "p": ("400013", "Poor", "Usée")}
_PREF_CA = {"lettre": ("CA_PostLettermail",),
            "suivi": ("CA_PostTrackedPacket", "CA_PostTrackedPackets", "CA_PostExpeditedParcel", "CA_PostRegularParcel"),
            "gratuit": ("CA_PostTrackedPacket", "CA_PostExpeditedParcel", "CA_PostLettermail")}
_PREF_US = {"lettre": ("USALetterPost", "SmallPacketsUSA", "TrackedPacketsUSA", "USA"),
            "suivi": ("TrackedPacketsUSA", "TrackedPacketUSA", "SmallPacketsUSA", "USA")}
_cache_services = {"ca": None, "us": None}


def _services():
    """Codes de services postaux valides chez eBay (GeteBayDetails, lu une fois). Sans reponse : codes connus."""
    if _cache_services["ca"] is not None:
        return _cache_services["ca"], _cache_services["us"]
    ca, us = [], []
    try:
        r = ebay_compte.trading("GeteBayDetails", f'<?xml version="1.0" encoding="utf-8"?><GeteBayDetailsRequest xmlns="{NS}">'
                                "<DetailName>ShippingServiceDetails</DetailName></GeteBayDetailsRequest>")
        for d in r.findall("e:ShippingServiceDetails", ebay_compte._NS):
            code = ebay_compte._txt(d, "e:ShippingService") or ""
            if (ebay_compte._txt(d, "e:ValidForSellingFlow") or "true").lower() != "true":
                continue
            (us if (ebay_compte._txt(d, "e:InternationalService") or "").lower() == "true" else ca).append(code)
    except Exception:
        pass
    _cache_services["ca"], _cache_services["us"] = ca, us
    return ca, us


def service(mode, pays="ca"):
    ca, us = _services()
    codes = ca if pays == "ca" else us
    prefs = (_PREF_CA if pays == "ca" else _PREF_US).get(mode) or ()
    for p in prefs:
        for c in codes:
            if c == p or (pays == "us" and p in c):
                return c
    if pays == "ca":
        return prefs[0] if not codes else (next((c for c in codes if "Lettermail" in c), None) or codes[0])
    return None


# -- preparer -------------------------------------------------------------------------------------
def titre_optimise(c):
    """Ce que les acheteurs tapent, dans l'ordre : annee, marque, set, insert/variante, JOUEUR, /tirage,
    Auto, Patch, gradation, #numero, RC, equipe. Coupe les morceaux les moins utiles pour tenir en 80."""
    grade = c.get("grade") if c.get("grade") and str(c.get("grade")).lower() not in ("raw", "brute") else None
    parties = [(c.get("annee"), 9), (c.get("marque"), 5), (c.get("set_nom"), 7), (c.get("parallele"), 8),
               (str(c.get("joueur") or "").strip(), 10), (f"/{c['tirage']}" if c.get("tirage") else None, 9),
               ("Auto" if c.get("auto") else None, 9), ("Patch" if c.get("relique") else None, 8), (grade, 10),
               (f"#{c['numero']}" if c.get("numero") else None, 6), ("RC" if c.get("recrue") else None, 7),
               (c.get("equipe"), 3)]
    parties = [(str(p).strip(), w) for p, w in parties if p and str(p).strip()]
    vus, uniques = set(), []
    for p, w in parties:                       # « Young Guns » deja dans le set : pas deux fois
        k = p.lower()
        if any(k in v for v in vus):
            continue
        vus.add(k)
        uniques.append((p, w))
    while len(" ".join(p for p, _ in uniques)) > 80 and len(uniques) > 2:
        uniques.remove(min(uniques, key=lambda x: x[1]))
    return re.sub(r"\s+", " ", " ".join(p for p, _ in uniques)).strip()[:80]


def specifiques(c):
    """Caracteristiques eBay (Item Specifics) : plus il y en a, mieux l'annonce sort dans les filtres."""
    import sports
    asp = sports.aspects_ebay(c.get("sport") or sports.detecter(c.get("titre"), c.get("equipe"), defaut="hockey"))
    g = re.match(r"([A-Za-z]+)\s*([\d.]+)", str(c.get("grade") or ""))
    traits = [x for x, ok in (("Rookie", c.get("recrue")), ("Serial Numbered", c.get("tirage")), ("Parallel/Variety", c.get("parallele")),
                              ("Short Print", re.search(r"\bssp?\b|short print", str(c.get("parallele") or ""), re.I)),
                              ("Autograph", c.get("auto")), ("Patch", c.get("relique"))) if ok]
    annee = re.match(r"(19|20)\d{2}", str(c.get("annee") or ""))
    paires = [("Sport", asp["Sport"]), ("League", asp["League"]), ("Player/Athlete", c.get("joueur")), ("Team", c.get("equipe")),
              ("Season", c.get("annee")), ("Year Manufactured", annee.group(0) if annee else None), ("Manufacturer", c.get("marque")),
              ("Set", c.get("set_nom")), ("Card Name", c.get("joueur")), ("Card Number", c.get("numero")),
              ("Parallel/Variety", c.get("parallele")), ("Features", traits or None),
              ("Print Run", str(c["tirage"]) if c.get("tirage") else None),
              ("Autographed", "Yes" if c.get("auto") else "No"),
              ("Autograph Authentication", "Manufacturer" if c.get("auto") else None),
              ("Graded", "Yes" if g else "No"), ("Professional Grader", _nom_grader(g.group(1)) if g else None),
              ("Grade", g.group(2) if g else None), ("Certification Number", c.get("cert")),
              ("Memorabilia", "Patch" if c.get("relique") else None),
              ("Type", "Sports Trading Card"), ("Original/Licensed Reprint", "Original"), ("Card Size", "Standard"),
              ("Language", "English"),
              ("Vintage", "Yes" if annee and int(annee.group(0)) < 1980 else "No")]
    return [(n, [str(x)[:65] for x in v] if isinstance(v, list) else str(v)[:65]) for n, v in paires if v not in (None, "", [])]


def _nom_grader(cie):
    return {"PSA": "Professional Sports Authenticator (PSA)", "BGS": "Beckett Grading Services (BGS)",
            "SGC": "Sportscard Guaranty Corporation (SGC)", "CGC": "Certified Guaranty Company (CGC)",
            "TAG": "Technical Authentication & Grading (TAG)"}.get(str(cie).upper(), str(cie).upper())


def description(c, titre, francophone=True, etat="nm", boutique=None, retours="non", expedition="lettre"):
    """HTML simple et propre (mobile) : ce que c'est, l'etat, l'envoi. Bilingue pour un vendeur francophone."""
    e = ETATS_BRUTS.get(etat, ETATS_BRUTS["nm"])
    grade = str(c.get("grade") or "").strip()
    etat_en = f"Graded {grade}" if grade and grade.lower() != "raw" else f"Raw — {e[1]} (see photos)"
    etat_fr = f"Gradée {grade}" if grade and grade.lower() != "raw" else f"Brute — {e[2]} (voir les photos)"
    envoi_en = {"lettre": "Ships in a penny sleeve + top loader, in a rigid envelope.",
                "suivi": "Ships tracked, in a penny sleeve + top loader, bubble mailer.",
                "gratuit": "Free tracked shipping, penny sleeve + top loader, bubble mailer."}.get(expedition, "")
    envoi_fr = {"lettre": "Envoi en pochette + top loader, dans une enveloppe rigide.",
                "suivi": "Envoi suivi, en pochette + top loader, enveloppe à bulles.",
                "gratuit": "Livraison suivie gratuite, pochette + top loader, enveloppe à bulles."}.get(expedition, "")
    ret_en = "Returns accepted within 30 days." if retours != "non" else "All sales final — please ask any question before buying."
    ret_fr = "Retours acceptés sous 30 jours." if retours != "non" else "Vente finale — pose tes questions avant d'acheter."
    det = " · ".join(x for x in [c.get("annee"), c.get("marque"), c.get("set_nom"), c.get("parallele"),
                                 f"#{c['numero']}" if c.get("numero") else None, f"/{c['tirage']}" if c.get("tirage") else None,
                                 "Auto" if c.get("auto") else None, "Rookie" if c.get("recrue") else None] if x)
    s = boutique or "LockerRoom"
    en = (f"<h2>{escape(titre)}</h2><p><b>Card:</b> {escape(det)}</p><p><b>Condition:</b> {escape(etat_en)}. "
          "The card in the photos is the exact card you will receive.</p>"
          f"<p>{escape(envoi_en)} Combined shipping available.</p><p>{escape(ret_en)}</p><p>Thank you! — {escape(s)}</p>")
    if not francophone:
        return en
    fr = (f"<hr><p><b>Carte :</b> {escape(det)}</p><p><b>État :</b> {escape(etat_fr)}. La carte des photos est celle que tu recevras.</p>"
          f"<p>{escape(envoi_fr)} Envoi combiné possible.</p><p>{escape(ret_fr)}</p><p>Merci ! — {escape(s)}</p>")
    return en + fr


# -- l'annonce eBay -------------------------------------------------------------------------------
def _xml_livraison(d):
    m = d.get("expedition") or "lettre"
    gratuit = m == "gratuit"
    s_ca = service("suivi" if m == "gratuit" else m, "ca")
    cout = 0.0 if gratuit else float(d.get("cout_suivi" if m == "suivi" else "cout_lettre") or 0)
    x = ("<ShippingDetails><ShippingType>Flat</ShippingType><ShippingServiceOptions>"
         f"<ShippingServicePriority>1</ShippingServicePriority><ShippingService>{escape(s_ca)}</ShippingService>"
         f'<ShippingServiceCost currencyID="CAD">{cout:.2f}</ShippingServiceCost>'
         + ("<FreeShipping>true</FreeShipping>" if gratuit else "") + "</ShippingServiceOptions>")
    if d.get("us"):
        s_us = service("suivi" if m in ("suivi", "gratuit") else "lettre", "us")
        if s_us:
            cu = float(d.get("us_cout_suivi" if m in ("suivi", "gratuit") else "us_cout_lettre") or 0)
            x += (f"<InternationalShippingServiceOption><ShippingService>{escape(s_us)}</ShippingService>"
                  f'<ShippingServiceCost currencyID="CAD">{cu:.2f}</ShippingServiceCost>'
                  "<ShippingServicePriority>1</ShippingServicePriority><ShipToLocation>US</ShipToLocation>"
                  "</InternationalShippingServiceOption>")
    return x + "</ShippingDetails>"


def _xml_colis(d):
    g = max(10, int(float(d.get("poids_g") or 30)))
    lettre = (d.get("expedition") or "lettre") == "lettre"
    return ("<ShippingPackageDetails><MeasurementUnit>Metric</MeasurementUnit>"
            f"<ShippingPackage>{'Letter' if lettre else 'PackageThickEnvelope'}</ShippingPackage>"
            f'<WeightMajor unit="kg">{g // 1000}</WeightMajor><WeightMinor unit="gm">{g % 1000}</WeightMinor>'
            f'<PackageLength unit="cm">{"16" if lettre else "20"}</PackageLength><PackageWidth unit="cm">{"11" if lettre else "15"}</PackageWidth>'
            f'<PackageDepth unit="cm">{"1" if lettre else "2"}</PackageDepth></ShippingPackageDetails>')


def _xml_retours(mode):
    if mode in ("30_acheteur", "30_gratuit"):
        qui = "Buyer" if mode == "30_acheteur" else "Seller"
        return ("<ReturnPolicy><ReturnsAcceptedOption>ReturnsAccepted</ReturnsAcceptedOption><RefundOption>MoneyBack</RefundOption>"
                f"<ReturnsWithinOption>Days_30</ReturnsWithinOption><ShippingCostPaidByOption>{qui}</ShippingCostPaidByOption>"
                "<InternationalReturnsAcceptedOption>ReturnsNotAccepted</InternationalReturnsAcceptedOption></ReturnPolicy>")
    return "<ReturnPolicy><ReturnsAcceptedOption>ReturnsNotAccepted</ReturnsAcceptedOption></ReturnPolicy>"


def _xml_etat(c, etat):
    g = str(c.get("grade") or "").strip()
    if re.match(r"([A-Za-z]+)\s*([\d.]+)", g) and g.lower() != "raw":
        cond, desc = ebay_ecriture._etat(c)
        return cond, desc
    code = ETATS_BRUTS.get(etat, ETATS_BRUTS["nm"])[0]
    return ebay_csv.CONDITION_NON_GRADEE, f"<ConditionDescriptor><Name>40001</Name><Value>{code}</Value></ConditionDescriptor>"


def xml_item(d, photos, code_postal="H2X 1Y4"):
    """d : {carte..., titre, prix, format, description, etat, expedition..., retours, offres...}."""
    c = d.get("carte") or {}
    prix = float(d["prix"])
    encan = d.get("format") == "encan"
    cond, desc = _xml_etat(c, d.get("etat"))
    specs = "".join(f"<NameValueList><Name>{escape(n)}</Name>" + "".join(f"<Value>{escape(x)}</Value>" for x in (v if isinstance(v, list) else [v]))
                    + "</NameValueList>" for n, v in specifiques(c))
    photos_xml = "".join(f"<PictureURL>{escape(u)}</PictureURL>" for u in (photos or [])[:12])
    offres = ""
    if not encan and d.get("offres"):
        auto = round(prix * float(d.get("offre_auto_pct") or 90) / 100, 2)
        mini = round(prix * float(d.get("offre_min_pct") or 70) / 100, 2)
        offres = ("<BestOfferDetails><BestOfferEnabled>true</BestOfferEnabled></BestOfferDetails><ListingDetails>"
                  + (f'<BestOfferAutoAcceptPrice currencyID="CAD">{auto:.2f}</BestOfferAutoAcceptPrice>' if 0 < auto < prix else "")
                  + (f'<MinimumBestOfferPrice currencyID="CAD">{mini:.2f}</MinimumBestOfferPrice>' if 0 < mini < auto else "")
                  + "</ListingDetails>")
    return (f"<Item><Title>{escape(str(d['titre'])[:80])}</Title>"
            f"<Description><![CDATA[{str(d.get('description') or d['titre']).replace(']]>', '')}]]></Description>"
            f"<PrimaryCategory><CategoryID>{ebay_csv.CATEGORY_ID}</CategoryID></PrimaryCategory>"
            f'<StartPrice currencyID="CAD">{prix:.2f}</StartPrice>'
            f"<ConditionID>{cond}</ConditionID><ConditionDescriptors>{desc}</ConditionDescriptors>"
            f"<Country>CA</Country><Currency>CAD</Currency><PostalCode>{escape(code_postal)}</PostalCode>"
            f"<DispatchTimeMax>{int(d.get('delai') or 2)}</DispatchTimeMax>"
            f"<ListingDuration>{'Days_7' if encan else 'GTC'}</ListingDuration>"
            f"<ListingType>{'Chinese' if encan else 'FixedPriceItem'}</ListingType><Quantity>1</Quantity>"
            + (f"<PictureDetails>{photos_xml}</PictureDetails>" if photos_xml else "")
            + f"<ItemSpecifics>{specs}</ItemSpecifics>" + _xml_retours(d.get("retours")) + _xml_livraison(d) + _xml_colis(d)
            + offres + (f"<SKU>{escape(str(d['sku']))[:50]}</SKU>" if d.get("sku") else "") + "</Item>")


def photos_ebay(photos):
    """Data URL (photo prise dans l'app) -> image hebergee par eBay ; une URL https reste telle quelle."""
    out = []
    for i, p in enumerate(photos or []):
        p = str(p or "")
        if p.startswith("https://"):
            out.append(p)
            continue
        m = re.match(r"data:image/(png|jpe?g|webp);base64,(.+)", p, re.S)
        if not m:
            continue
        brut = base64.b64decode(m.group(2))
        if len(brut) > 7_000_000:
            raise ValueError("Photo trop lourde : reprends-la")
        f = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        try:
            f.write(brut)
            f.close()
            out.append(ebay_ecriture.televerser_photo(f.name, f"lockerroom-{i + 1}"))
        finally:
            try:
                os.unlink(f.name)
            except OSError:
                pass
    return out


def publier(d, photos_hebergees, code_postal, verifier_seulement=False):
    encan = d.get("format") == "encan"
    appel = "AddItem" if encan else "AddFixedPriceItem"
    item = xml_item(d, photos_hebergees, code_postal)
    req = lambda a: f'<?xml version="1.0" encoding="utf-8"?><{a}Request xmlns="{NS}">{item}</{a}Request>'
    v = ebay_compte.trading("Verify" + appel, req("Verify" + appel))
    frais = ebay_ecriture._frais(v)
    if verifier_seulement:
        return {"ok": True, "verifie": True, "frais": frais, "avertissements": ebay_compte.avertissements(v)}
    r = ebay_compte.trading(appel, req(appel))
    return {"ok": True, "item_id": ebay_compte._txt(r, "e:ItemID"), "frais": frais, "avertissements": ebay_compte.avertissements(r)}


# -- promotion (Promoted Listings Standard : % paye seulement si l'article se vend via la pub) -----
SCOPE_MARKETING = "https://api.ebay.com/oauth/api_scope/sell.marketing"


def _base_marketing():
    return ebay_compte.url("recherche").split("/buy/")[0] + "/sell/marketing/v1"


def promouvoir(item_id, pct):
    """Ajoute l'annonce a la campagne « LockerRoom » (creee au besoin) au taux choisi."""
    import json
    import urllib.request
    pct = round(float(pct), 1)
    if pct <= 0:
        return {"ok": True, "promotion": 0}
    if pct < 2 or pct > 100:
        raise ValueError("Promotion : entre 2 et 100 %")
    base = _base_marketing()

    def appel(meth, chemin, corps=None):
        req = urllib.request.Request(base + chemin, data=json.dumps(corps).encode() if corps is not None else None, method=meth, headers={
            "Authorization": "Bearer " + ebay_compte.jeton(), "Content-Type": "application/json", "Accept": "application/json",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_CA"})
        import appels_ebay
        appels_ebay.compter("autre")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                brut = r.read()
                return (json.loads(brut) if brut else {}), r.headers
        except urllib.error.HTTPError as e:
            texte = e.read().decode("utf-8", "ignore")
            if e.code in (401, 403):
                raise RuntimeError("Promotion : reconnecte eBay (Réglages) pour autoriser la publicité")
            raise RuntimeError(f"Promotion refusée par eBay ({e.code}) : {texte[:160]}")

    camps, _h = appel("GET", "/ad_campaign?campaign_status=RUNNING&limit=100")
    camp = next((x for x in camps.get("campaigns") or [] if x.get("campaignName") == "LockerRoom"
                 and (x.get("fundingStrategy") or {}).get("fundingModel") == "COST_PER_SALE"), None)
    if camp:
        cid = camp["campaignId"]
    else:
        debut = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _r, h = appel("POST", "/ad_campaign", {"campaignName": "LockerRoom", "marketplaceId": "EBAY_CA", "startDate": debut,
                                                "fundingStrategy": {"fundingModel": "COST_PER_SALE", "bidPercentage": str(pct)}})
        cid = str(h.get("Location") or "").rstrip("/").split("/")[-1]
        if not cid:
            raise RuntimeError("Promotion : campagne non créée")
    appel("POST", f"/ad_campaign/{cid}/ad", {"listingId": str(item_id), "bidPercentage": str(pct)})
    return {"ok": True, "promotion": pct, "campagne": cid}
