"""
SLABCOACH - expedier et repondre aux offres, depuis l'app (10 nov 2026).

Mathieu : « plus facile que sur eBay ». Deux gestes de vendeur, avec SES donnees et nos cles eBay (permis) :
  1. A EXPEDIER : les commandes payees pas encore expediees (API Fulfillment, lecture) ; un tap « Expedie » avec ou sans
     numero de suivi (Trading CompleteSale : Shipped + transporteur + suivi). L'acheteur est avise par eBay.
  2. OFFRES RECUES : les Best Offers en attente sur ses annonces (Trading GetBestOffers) ; Accepter, Contre-offre, Refuser
     (Trading RespondToBestOffer). Jamais automatique : chaque reponse est un tap du vendeur.
"""
import html
import re
import urllib.parse
from datetime import datetime, timezone

TRANSPORTEURS = {"postes_canada": "CanadaPost", "purolator": "Purolator", "ups": "UPS", "fedex": "FedEx", "usps": "USPS",
                 "dhl": "DHL", "chit_chats": "Other", "stallion": "Other", "autre": "Other"}


def _x(v):
    return html.escape(str(v or ""), quote=False)


# -- 1. a expedier --------------------------------------------------------------------------------------------
def a_expedier():
    """Les commandes payees a expedier : [{commande, acheteur, articles, total, payee_le, expedier_avant, ville}]."""
    import ebay_compte
    q = urllib.parse.urlencode({"filter": "orderfulfillmentstatus:{NOT_STARTED|IN_PROGRESS}", "limit": 50})
    p = ebay_compte._get_json(ebay_compte.url("commandes") + "?" + q)
    out = []
    for o in (p or {}).get("orders") or []:
        if o.get("orderPaymentStatus") not in ("PAID", "PARTIALLY_REFUNDED"):
            continue
        if (o.get("cancelStatus") or {}).get("cancelState") == "CANCELED":
            continue
        dest = (((o.get("fulfillmentStartInstructions") or [{}])[0].get("shippingStep") or {}).get("shipTo") or {})
        adr = dest.get("contactAddress") or {}
        art = [{"titre": l.get("title"), "item": str(l.get("legacyItemId") or ""), "ligne": l.get("lineItemId"), "qte": l.get("quantity") or 1,
                "prix": float((l.get("lineItemCost") or {}).get("value") or 0)} for l in o.get("lineItems") or []]
        out.append({"commande": o.get("orderId"), "acheteur": (o.get("buyer") or {}).get("username"),
                    "articles": art, "total": float(((o.get("pricingSummary") or {}).get("total") or {}).get("value") or 0),
                    "payee_le": str(o.get("creationDate") or "")[:10],
                    "expedier_avant": str((((o.get("fulfillmentStartInstructions") or [{}])[0].get("maxEstimatedDeliveryDate")) or ""))[:10] or None,
                    # la ville et la province seulement a l'ecran (l'adresse complete reste chez eBay)
                    "ville": ", ".join(x for x in (adr.get("city"), adr.get("stateOrProvince"), adr.get("countryCode")) if x)})
    out.sort(key=lambda x: x["payee_le"])
    return out


def marquer_expedie(commande, transporteur=None, suivi=None):
    """Trading CompleteSale : la commande est expediee (avec le suivi s'il y en a un)."""
    import ebay_compte
    if not commande or not re.fullmatch(r"[0-9A-Za-z!_-]{5,60}", str(commande)):
        raise ValueError("Commande inconnue")
    suivi = re.sub(r"[^0-9A-Za-z]", "", str(suivi or ""))[:40]
    tr = TRANSPORTEURS.get(str(transporteur or "").lower(), "Other") if suivi else None
    det = (f"<Shipment><ShipmentTrackingDetails><ShippingCarrierUsed>{_x(tr)}</ShippingCarrierUsed>"
           f"<ShipmentTrackingNumber>{_x(suivi)}</ShipmentTrackingNumber></ShipmentTrackingDetails>"
           f"<ShippedTime>{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')}</ShippedTime></Shipment>") if suivi else ""
    corps = ('<?xml version="1.0" encoding="utf-8"?><CompleteSaleRequest xmlns="urn:ebay:apis:eBLBaseComponents">'
             f"<OrderID>{_x(commande)}</OrderID><Shipped>true</Shipped>{det}</CompleteSaleRequest>")
    ebay_compte.trading("CompleteSale", corps)
    return {"ok": True, "commande": commande, "suivi": suivi or None}


# -- 2. offres recues ---------------------------------------------------------------------------------------------
def offres_recues():
    """Les Best Offers en attente : [{offre, item, titre, prix, offert, acheteur, message, expire}]."""
    import ebay_compte
    corps = ('<?xml version="1.0" encoding="utf-8"?><GetBestOffersRequest xmlns="urn:ebay:apis:eBLBaseComponents">'
             "<BestOfferStatus>Active</BestOfferStatus><DetailLevel>ReturnAll</DetailLevel></GetBestOffersRequest>")
    r = ebay_compte.trading("GetBestOffers", corps)
    ns = ebay_compte._NS
    t = ebay_compte._txt
    out = []
    for it in r.findall(".//e:ItemBestOffers", ns):
        item = it.find("e:Item", ns)
        iid = t(item, "e:ItemID") if item is not None else None
        titre = t(item, "e:Title") if item is not None else None
        prix = t(item, "e:BuyItNowPrice") or (t(item, "e:SellingStatus/e:CurrentPrice") if item is not None else None)
        for bo in it.findall(".//e:BestOffer", ns):
            out.append({"offre": t(bo, "e:BestOfferID"), "item": iid, "titre": titre, "prix": _f(prix), "offert": _f(t(bo, "e:Price")),
                        "devise": (bo.find("e:Price", ns).get("currencyID") if bo.find("e:Price", ns) is not None else None),
                        "acheteur": t(bo, "e:Buyer/e:UserID"), "message": t(bo, "e:BuyerMessage"), "expire": t(bo, "e:ExpirationTime"),
                        "qte": t(bo, "e:Quantity")})
    return out


def _f(v):
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def repondre_offre(item, offre, action, contre=None, message=None, devise="CAD"):
    """Accept | Decline | Counter (avec le prix de la contre-offre). Un tap du vendeur, jamais automatique."""
    import ebay_compte
    act = {"accepter": "Accept", "refuser": "Decline", "contre": "Counter"}.get(str(action))
    if not act or not re.fullmatch(r"\d{9,15}", str(item or "")) or not re.fullmatch(r"\d{3,20}", str(offre or "")):
        raise ValueError("Offre inconnue")
    extra = ""
    if act == "Counter":
        p = _f(contre)
        if not p or p <= 0:
            raise ValueError("Prix de la contre-offre ?")
        dv = devise if devise in ("CAD", "USD", "GBP", "EUR", "AUD") else "CAD"
        extra = f'<CounterOfferPrice currencyID="{dv}">{p:.2f}</CounterOfferPrice><CounterOfferQuantity>1</CounterOfferQuantity>'
    if message:
        extra += f"<SellerResponse>{_x(str(message)[:250])}</SellerResponse>"
    corps = ('<?xml version="1.0" encoding="utf-8"?><RespondToBestOfferRequest xmlns="urn:ebay:apis:eBLBaseComponents">'
             f"<ItemID>{_x(item)}</ItemID><BestOfferID>{_x(offre)}</BestOfferID><Action>{act}</Action>{extra}"
             "</RespondToBestOfferRequest>")
    ebay_compte.trading("RespondToBestOffer", corps)
    return {"ok": True, "action": act}
