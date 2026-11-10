"""10 nov 2026 : expedier (CompleteSale) et repondre aux offres (GetBestOffers / RespondToBestOffer) depuis l'app."""
import os
import sys
import tempfile
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import ebay_compte
import vendeur_outils as vo

ebay_compte._get_json = lambda u: {"orders": [
    {"orderId": "12-34567-89012", "orderPaymentStatus": "PAID", "creationDate": "2026-11-09T20:00:00Z", "buyer": {"username": "acheteur1"},
     "pricingSummary": {"total": {"value": "52.50"}}, "lineItems": [{"title": "Bedard YG", "legacyItemId": "123456789012", "lineItemId": "1", "lineItemCost": {"value": "45"}}],
     "fulfillmentStartInstructions": [{"shippingStep": {"shipTo": {"contactAddress": {"city": "Laval", "stateOrProvince": "QC", "countryCode": "CA", "addressLine1": "secret"}}}}]},
    {"orderId": "99-1", "orderPaymentStatus": "PENDING", "lineItems": []}]}
l = vo.a_expedier()
assert len(l) == 1 and l[0]["ville"] == "Laval, QC, CA" and l[0]["total"] == 52.5 and "secret" not in str(l), l

envoyes = []
NS = "urn:ebay:apis:eBLBaseComponents"
def trading(appel, corps, fond=False):
    envoyes.append((appel, corps))
    ET.fromstring(corps)                                   # du XML valide
    if appel == "GetBestOffers":
        return ET.fromstring(f'<GetBestOffersResponse xmlns="{NS}"><Ack>Success</Ack><ItemBestOffersArray><ItemBestOffers>'
                             f'<Item><ItemID>123456789012</ItemID><Title>Bedard YG</Title><BuyItNowPrice currencyID="CAD">60.00</BuyItNowPrice></Item>'
                             f'<BestOfferArray><BestOffer><BestOfferID>5551234</BestOfferID><Price currencyID="CAD">45.00</Price>'
                             f'<Buyer><UserID>acheteur2</UserID></Buyer><BuyerMessage>ok?</BuyerMessage></BestOffer></BestOfferArray>'
                             f'</ItemBestOffers></ItemBestOffersArray></GetBestOffersResponse>')
    return ET.fromstring(f'<R xmlns="{NS}"><Ack>Success</Ack></R>')
ebay_compte.trading = trading
assert vo.marquer_expedie("12-34567-89012", "postes_canada", "LM 123 456 789 CA")["suivi"] == "LM123456789CA"
assert "<Shipped>true</Shipped>" in envoyes[-1][1] and "CanadaPost" in envoyes[-1][1]
vo.marquer_expedie("12-34567-89012")                      # Lettermail : sans suivi
assert "ShipmentTrackingNumber" not in envoyes[-1][1]
o = vo.offres_recues()
assert o == [{"offre": "5551234", "item": "123456789012", "titre": "Bedard YG", "prix": 60.0, "offert": 45.0, "devise": "CAD",
              "acheteur": "acheteur2", "message": "ok?", "expire": "", "qte": ""}], o
vo.repondre_offre("123456789012", "5551234", "contre", 52, devise="CAD")
assert "<Action>Counter</Action>" in envoyes[-1][1] and "52.00" in envoyes[-1][1]
for mauvais in (("x", "1", "accepter"), ("123456789012", "5551234", "voler")):
    try:
        vo.repondre_offre(*mauvais)
        raise AssertionError("refus attendu")
    except ValueError:
        pass
print("OK vendeur outils")
