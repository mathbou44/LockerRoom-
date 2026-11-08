"""8 nov 2026 (Mathieu : « frais d'importation a considerer », sa commande US : 106,17 + 18,58 $ US, TPS/TVH 8,89 $, frais
d'importation 53,09 $) ; et une Poitras « Inscribed 6/11/23 » /999 : la date n'est pas une numerotation."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deals, ebay_compte, cartes_match
sub = 106.17 + 18.58
# 1. le Canada : 14,975 % ; hors Canada pas encore relue : prudent ; relue avec les frais d'eBay : ceux-la
assert deals.taxe_de({"lieu": "CA", "total": 50}) == deals.TAXE_ACHAT == deals.taxe_de({})
assert deals.taxe_de({"lieu": "US", "total": 50}) == deals.IMPORT_DEFAUT
assert abs((sub * (1 + deals.IMPORT_DEFAUT)) - 186.73) < 0.5                     # sa commande, au dollar pres
a = {"lieu": "US", "import_lu": True, "import_cad": 53.09, "prix_cad": 106.17, "port_cad": 18.58}
assert abs(deals.taxe_de(a) - (53.09 / sub + deals.TAXE_IMPORT)) < 0.001
assert abs(sub * (1 + deals.taxe_de(a)) - 186.73) < 0.5
assert deals.taxe_de({"lieu": "US", "import_lu": True, "import_cad": 0, "prix_cad": 50}) == deals.TAXE_ACHAT   # expedie par le vendeur
# 2. la mise max baisse d'autant ; le pourcentage suit le prix (garde avec le deal)
assert deals.prix_max(300, taxe=deals.taxe_de(a)) < deals.prix_max(300) * 0.8
x = dict(deals.achat(a), total=200.0)
assert abs(deals.taxe_de(x) - deals.taxe_de(a)) < 0.001
assert deals.achat({"lieu": "US"}) == {"lieu": "US"}                             # une recherche n'efface pas les frais lus
assert deals.cout_achat(100, 0.5) == 150.0 and deals.cout_achat(100) == round(100 * (1 + deals.TAXE_ACHAT), 2)
# 3. eBay : les frais d'importation de getItem
it = {"title": "t", "price": {"value": "100", "currency": "CAD"}, "itemLocation": {"country": "US"},
      "shippingOptions": [{"shippingCost": {"value": "20", "currency": "CAD"}, "importCharges": {"value": "45.5", "currency": "CAD"}}]}
r = ebay_compte._lire_article(it, "1")
assert r["import_cad"] == 45.5 and r["import_lu"] and r["lieu"] == "US", r
it["shippingOptions"][0].pop("importCharges")
assert ebay_compte._lire_article(it, "1")["import_cad"] == 0.0
assert ebay_compte.lire_recherche({"itemSummaries": [{"title": "t", "price": {"value": "5", "currency": "CAD"}, "itemLocation": {"country": "US"}}]})[0]["lieu"] == "US"
# 4. une date inscrite
assert cartes_match.decoder("Poitras Future Watch Auto Inscribed 6/11/23 /999")["serie"] == 999
assert cartes_match.numero_serie("Inscribed 6/11/2023 018/999") == (18, 999)
print("IMPORT OK")
