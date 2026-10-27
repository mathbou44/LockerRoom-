"""API modernes d'eBay (Media, Inventory, Account) : python tests/test_ebay_moderne.py. Aucun appel reseau (eBay simule)."""
import os
import subprocess
import sys
import tempfile
import textwrap

ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = textwrap.dedent('''
    import os, sys, json, io, base64, urllib.request, urllib.error
    sys.path.insert(0, %(ici)r); os.chdir(%(ici)r)
    import ebay_compte, ebay_moderne, annonces, ebay_ecriture, comptes
    ebay_compte.jeton = lambda *a, **k: "JETON"
    ebay_compte.environnement = lambda: "sandbox"
    comptes.dossier = lambda: os.environ["LOCKERROOM_DONNEES"]
    annonces._services = lambda: (["CA_PostLettermail", "CA_PostTrackedPacket"], ["USALetterPost", "TrackedPacketsUSA"])

    APPELS = []
    class Rep:
        def __init__(s, st, corps, h=None): s.status, s._c, s.headers = st, json.dumps(corps).encode() if corps is not None else b"", h or {}
        def read(s): return s._c
        def __enter__(s): return s
        def __exit__(s, *a): return False
    SCRIPTE = {}
    def urlopen(req, timeout=0):
        u, m = req.full_url, req.get_method()
        corps = req.data
        APPELS.append((m, u, corps, dict(req.header_items())))
        for (mm, morceau), f in SCRIPTE.items():
            if mm == m and morceau in u:
                st, c, h = f(u, corps) if callable(f) else f
                if st >= 400:
                    raise urllib.error.HTTPError(u, st, "x", {}, io.BytesIO(json.dumps(c).encode()))
                return Rep(st, c, h)
        raise AssertionError("appel inattendu " + m + " " + u)
    urllib.request.urlopen = urlopen

    # 1. photo : Media API (UploadSiteHostedPictures est retire depuis le 30 sept. 2026), champ multipart « image »
    PNG = b"\\x89PNG\\r\\n\\x1a\\n" + b"0" * 64
    SCRIPTE[("POST", "/commerce/media/v1_beta/image/create_image_from_file")] = (201, {"imageUrl": "https://i.ebayimg.com/images/g/ABC/s-l1600.png"}, {})
    u = annonces.photos_ebay(["data:image/png;base64," + base64.b64encode(PNG).decode(), "https://deja.ca/x.jpg"])
    assert u == ["https://i.ebayimg.com/images/g/ABC/s-l1600.png", "https://deja.ca/x.jpg"], u
    m, url, corps, h = APPELS[-1]
    assert url.startswith("https://apim.sandbox.ebay.com/commerce/media/v1_beta/"), url
    assert b'name="image"' in corps and b"image/png" in corps and h.get("Authorization") == "Bearer JETON"
    assert not any("ws/api.dll" in a[1] for a in APPELS)
    # sans imageUrl dans la reponse : on suit l'en-tete Location
    SCRIPTE.clear()
    SCRIPTE[("POST", "create_image_from_file")] = (201, {}, {"Location": "https://apim.sandbox.ebay.com/commerce/media/v1_beta/image/IMG9"})
    SCRIPTE[("GET", "/image/IMG9")] = (200, {"imageUrl": "https://i.ebayimg.com/9.jpg"}, {})
    assert ebay_moderne.televerser_image(b"\\xff\\xd8\\xff" + b"1" * 50) == "https://i.ebayimg.com/9.jpg"
    try:
        ebay_moderne.televerser_image(b"GIF89a....."); raise SystemExit("format accepte")
    except ValueError:
        pass

    # 2. mode classique par defaut : la publication reste Trading
    assert ebay_moderne.mode() == "classique"
    vus = []
    import xml.etree.ElementTree as ET
    ebay_compte.trading = lambda appel, corps, **k: vus.append(appel) or ET.fromstring('<r xmlns="urn:ebay:apis:eBLBaseComponents"><ItemID>111</ItemID></r>')
    D = {"carte": {"id": 7, "joueur": "Macklin Celebrini", "annee": "2024-25", "marque": "Upper Deck", "set_nom": "Series 1",
                   "parallele": "Young Guns", "numero": "201", "recrue": 1, "grade": "PSA 10"},
         "titre": "2024-25 Upper Deck Young Guns #201 Macklin Celebrini RC PSA 10", "prix": 250, "format": "fixe",
         "description": "<p>Carte</p>", "etat": "nm", "expedition": "suivi", "cout_suivi": 12, "us": True, "us_cout_suivi": 22,
         "delai": 2, "poids_g": 40, "retours": "30_acheteur", "offres": True, "offre_auto_pct": 0, "offre_min_pct": 70}
    r = annonces.publier(D, ["https://i.ebayimg.com/a.jpg"], "J6W 2S8")
    assert r["item_id"] == "111" and vus == ["VerifyAddFixedPriceItem", "AddFixedPriceItem"], (r, vus)
    assert ebay_compte.SCOPE_ECRITURE in ebay_compte.scopes_demandes() and ebay_moderne.SCOPE_COMPTE not in ebay_compte.scopes_demandes()

    # 3. mode inventaire : emplacement, politiques d'affaires, article, offre, frais, publication
    os.environ["LOCKERROOM_EBAY_API"] = "inventaire"
    assert ebay_moderne.SCOPE_COMPTE in ebay_compte.scopes_demandes()
    SCRIPTE.clear(); APPELS.clear(); vus.clear()
    cree = {}
    def creer(nom):
        def f(u, c):
            d = json.loads(c); cree[nom] = d
            return 201, {{"fulfillment": "fulfillmentPolicyId", "return": "returnPolicyId", "payment": "paymentPolicyId"}[nom]: nom.upper() + "-1"}, {}
        return f
    SCRIPTE[("GET", "get_opted_in_programs")] = (200, {"programs": [{"programType": "SELLING_POLICY_MANAGEMENT"}]}, {})
    SCRIPTE[("GET", "/location/slabcoach-j6w2s8")] = (404, {"errors": [{"errorId": 25805, "message": "not found"}]}, {})
    SCRIPTE[("POST", "/location/slabcoach-j6w2s8")] = lambda u, c: (cree.__setitem__("loc", json.loads(c)) or (204, None, {}))
    SCRIPTE[("GET", "fulfillment_policy?")] = (200, {"fulfillmentPolicies": []}, {})
    SCRIPTE[("GET", "return_policy?")] = (200, {"returnPolicies": []}, {})
    SCRIPTE[("GET", "payment_policy?")] = (200, {"paymentPolicies": [{"name": "SlabCoach · paiement", "paymentPolicyId": "PAY-0"}]}, {})
    SCRIPTE[("POST", "/fulfillment_policy")] = creer("fulfillment")
    SCRIPTE[("POST", "/return_policy")] = creer("return")
    SCRIPTE[("PUT", "/inventory_item/SC-7")] = lambda u, c: (cree.__setitem__("item", json.loads(c)) or (204, None, {}))
    SCRIPTE[("GET", "/offer?sku=SC-7")] = (404, {"errors": [{"errorId": 25713}]}, {})
    SCRIPTE[("POST", "/offer/get_listing_fees")] = (200, {"feeSummaries": [{"fees": [{"amount": {"value": "0.35"}}, {"amount": {"value": "0.00"}}]}]}, {})
    SCRIPTE[("POST", "/offer/OF1/publish")] = (200, {"listingId": "222333444"}, {})
    SCRIPTE[("POST", "/sell/inventory/v1/offer")] = lambda u, c: (cree.__setitem__("offre", json.loads(c)) or (201, {"offerId": "OF1"}, {}))
    v = annonces.publier(D, ["https://i.ebayimg.com/a.jpg"], "J6W 2S8", verifier_seulement=True)
    assert v["verifie"] and v["frais"] == 0.35 and not any("/publish" in a[1] for a in APPELS), v
    r = annonces.publier(D, ["https://i.ebayimg.com/a.jpg"], "J6W 2S8")
    assert r["ok"] and r["item_id"] == "222333444" and r["api"] == "inventaire" and not vus, (r, vus)
    it, of = cree["item"], cree["offre"]
    assert it["condition"] == "LIKE_NEW" and {"name": "27501", "values": ["275010"]} in it["conditionDescriptors"], it["conditionDescriptors"]
    assert it["product"]["imageUrls"] == ["https://i.ebayimg.com/a.jpg"] and it["product"]["aspects"]["Player/Athlete"] == ["Macklin Celebrini"]
    assert of["marketplaceId"] == "EBAY_CA" and of["format"] == "FIXED_PRICE" and of["listingDuration"] == "GTC"
    assert of["pricingSummary"]["price"] == {"value": "250.00", "currency": "CAD"} and of["merchantLocationKey"] == "slabcoach-j6w2s8"
    assert of["listingPolicies"]["paymentPolicyId"] == "PAY-0" and of["listingPolicies"]["fulfillmentPolicyId"] == "FULFILLMENT-1"
    assert of["listingPolicies"]["bestOfferTerms"] == {"bestOfferEnabled": True, "autoDeclinePrice": {"value": "175.00", "currency": "CAD"}}
    f = cree["fulfillment"]
    assert f["handlingTime"] == {"value": 2, "unit": "DAY"} and f["shippingOptions"][0]["shippingServices"][0]["shippingServiceCode"] == "CA_PostTrackedPacket"
    assert f["shippingOptions"][1]["shippingServices"][0]["shippingServiceCode"] == "TrackedPacketsUSA"
    assert cree["return"]["returnsAccepted"] and cree["return"]["returnShippingCostPayer"] == "BUYER"
    assert cree["loc"]["location"]["address"] == {"postalCode": "J6W 2S8", "country": "CA"}
    assert all(a[3].get("Content-language") == "en-CA" for a in APPELS if "/sell/" in a[1])
    # les politiques sont gardees : une 2e annonce ne les recree pas
    n_pol = sum(1 for a in APPELS if a[0] == "POST" and "_policy" in a[1])
    assert n_pol == 2, n_pol                       # expedition + retours crees une fois (paiement : trouve)
    SCRIPTE[("GET", "/location/slabcoach-j6w2s8")] = (200, {"merchantLocationKey": "slabcoach-j6w2s8"}, {})
    # changer le prix : l'offre (pas Trading)
    SCRIPTE[("POST", "/bulk_update_price_quantity")] = lambda u, c: (cree.__setitem__("prix", json.loads(c)) or (200, {"responses": [{"statusCode": 200}]}, {}))
    r = ebay_ecriture.changer_prix("222333444", 199)
    assert r["api"] == "inventaire" and cree["prix"]["requests"][0]["offers"][0] == {"offerId": "OF1", "price": {"value": "199.00", "currency": "CAD"}}
    assert not vus
    # une annonce classique garde Trading pour son prix
    ebay_ecriture.changer_prix("999888777", 50)
    assert vus == ["ReviseInventoryStatus"], vus
    # encan : AUCTION 7 jours, prix de depart, pas d'offres
    SCRIPTE[("GET", "/offer?sku=SC-9")] = (404, {}, {}); SCRIPTE[("PUT", "/inventory_item/SC-9")] = lambda u, c: (cree.__setitem__("item", json.loads(c)) or (204, None, {}))
    E = dict(D, carte=dict(D["carte"], id=9, grade=""), format="encan", prix=20)
    ebay_moderne.publier(E, [], "J6W 2S8", verifier_seulement=True)
    of = cree["offre"]
    assert of["format"] == "AUCTION" and of["listingDuration"] == "DAYS_7" and of["pricingSummary"] == {"auctionStartPrice": {"value": "20.00", "currency": "CAD"}}
    assert "bestOfferTerms" not in of["listingPolicies"]
    assert cree["item"]["condition"] == "USED_VERY_GOOD" and cree["item"]["conditionDescriptors"] == [{"name": "40001", "values": ["400010"]}]

    # 4. politiques pas encore activees : on les active et on le dit simplement
    SCRIPTE[("GET", "get_opted_in_programs")] = (200, {"programs": []}, {})
    SCRIPTE[("POST", "/program/opt_in")] = (200, {}, {})
    try:
        annonces.publier(D, [], "J6W 2S8"); raise SystemExit("publie sans politiques")
    except RuntimeError as e:
        assert "politiques" in str(e), e
    assert any("/program/opt_in" in a[1] for a in APPELS)
    # 5. code postal invalide
    SCRIPTE[("GET", "get_opted_in_programs")] = (200, {"programs": [{"programType": "SELLING_POLICY_MANAGEMENT"}]}, {})
    try:
        annonces.publier(D, [], "12345"); raise SystemExit("code postal accepte")
    except ValueError:
        pass
    print("EBAY MODERNE OK")
''')

if __name__ == "__main__":
    d = tempfile.mkdtemp()
    env = dict(os.environ, LOCKERROOM_DONNEES=d, LOCKERROOM_TACHES="0")
    env.pop("LOCKERROOM_EBAY_API", None)
    r = subprocess.run([sys.executable, "-c", SCRIPT % {"ici": ICI}], env=env, capture_output=True, text=True)
    print(r.stdout or r.stderr[-3000:])
    sys.exit(0 if "EBAY MODERNE OK" in r.stdout else 1)
