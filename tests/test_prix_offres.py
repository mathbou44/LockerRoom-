"""21 nov 2026 (Mathieu : « baisser la limite d'acceptation automatique en meme temps que le prix ») : eBay refuse un prix plus bas
que le seuil de refus automatique ; les seuils d'offres suivent alors le prix, dans la meme proportion."""
import os, sys, tempfile
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import ebay_ecriture as E, ebay_compte, ebay_moderne
assert E.seuils_offres(10, 20, 18, 14) == (9.0, 7.0)                 # 90 % et 70 % restent 90 % et 70 %
assert E.seuils_offres(10, 20, 0, 14) == (0.0, 7.0)                  # pas d'acceptation auto : seulement le refus
assert E.seuils_offres(1.00, 20, 19.99, 19.98) == (0.99, 0.98)       # toujours mini < auto < prix
assert E.seuils_offres(10, 0, 12, 11) == (9.99, 9.98)                # ancien prix inconnu : juste sous le prix
NS = "urn:ebay:apis:eBLBaseComponents"
APPELS = []
def faux(appel, corps, fond=False):
    APPELS.append((appel, corps))
    if appel == "ReviseInventoryStatus":
        raise RuntimeError("eBay a refusé : Auto decline amount cannot be greater than or equal to the Buy It Now price.")
    if appel == "GetItem":
        return ET.fromstring(f'<GetItemResponse xmlns="{NS}"><Ack>Success</Ack><Item><StartPrice>20.0</StartPrice><ListingDetails>'
                             '<BestOfferAutoAcceptPrice>18.0</BestOfferAutoAcceptPrice><MinimumBestOfferPrice>14.0</MinimumBestOfferPrice>'
                             '</ListingDetails></Item></GetItemResponse>')
    return ET.fromstring(f'<R xmlns="{NS}"><Ack>Success</Ack></R>')
ebay_compte.trading = faux
ebay_moderne.changer_prix = lambda i, p: None
r = E.changer_prix("257796099259", 10)
assert r["ok"] and r["prix"] == 10 and r["offres"] == {"auto": 9.0, "mini": 7.0}, r
assert [a[0] for a in APPELS] == ["ReviseInventoryStatus", "GetItem", "ReviseFixedPriceItem"]
x = APPELS[-1][1]
assert "<StartPrice>10.00</StartPrice>" in x and ">9.00</BestOfferAutoAcceptPrice>" in x and ">7.00</MinimumBestOfferPrice>" in x
# une autre erreur d'eBay reste une erreur
def faux2(appel, corps, fond=False):
    raise RuntimeError("eBay a refusé : Listing has ended.")
ebay_compte.trading = faux2
try:
    E.changer_prix("257796099259", 10); assert False
except RuntimeError as e:
    assert "ended" in str(e)
print("OK test_prix_offres")
