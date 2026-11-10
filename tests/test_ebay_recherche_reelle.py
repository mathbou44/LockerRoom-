"""10 nov 2026 (Mathieu : « rien fonctionne… ca doit jamais arriver ») : ebay_compte.rechercher de bout en bout, SANS la
remplacer (seul le reseau est simule). Avant : une variable non definie (« pays ») faisait echouer toute recherche hors
cache, et les autres tests ne le voyaient pas (ils remplacent rechercher)."""
import io
import json
import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import ebay_compte
import appels_ebay

ebay_compte.jeton_application = lambda: "jeton-test"
vus = []


class Rep(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def ouvrir(req, timeout=None):
    vus.append(req)
    return Rep(json.dumps({"itemSummaries": [{"itemId": "v1|123456789012|0", "title": "2024-25 Upper Deck Young Guns Macklin Celebrini #201",
                                              "price": {"value": "50.00", "currency": "CAD"}, "itemWebUrl": "https://www.ebay.ca/itm/123456789012",
                                              "buyingOptions": ["FIXED_PRICE"], "itemLocation": {"country": "CA"}}]}).encode())


ebay_compte.urllib.request.urlopen = ouvrir
for kw in ({}, {"encheres": True}, {"recentes": True, "prix_max": 100, "prix_min": 5, "aspects": "Sport:{Ice Hockey}"}, {"flux": True, "vendeurs": ["x"]},
           {"pays": "US"}):
    r = ebay_compte.rechercher("celebrini young guns", categorie="261328", fond=False, frais=True, **kw)
    assert r and r[0]["titre"].startswith("2024-25"), (kw, r)
assert vus[-1].get_header("X-ebay-c-marketplace-id") == "EBAY_US" and vus[0].get_header("X-ebay-c-marketplace-id") == "EBAY_CA"
print("OK recherche eBay reelle")
