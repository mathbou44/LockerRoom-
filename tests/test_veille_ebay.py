"""9 nov 2026 (Mathieu : « fetch automatiquement tous les updates eBay financiers ou legaux, comme les tarifs, a tous les
jours en back end ») : veille de la page officielle d'eBay, frais d'importation appris, frais de vente des vraies ventes."""
import os, sys, tempfile
from datetime import datetime, timezone
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
os.environ.pop("LR_IMPORT_DEFAUT", None); os.environ.pop("LR_IMPORT_US", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import deals, lockerroom, veille_ebay
# 1. la page « Seller updates » : les entrees, et leur sorte
P1 = ('<a href="/sellercentre/resources/seller-updates/timeline">Overview</a>'
      '<a href="https://www.ebay.ca/sellercentre/news/2026-april/issue-resolution-centre-launch">Issue Resolution Centre launch</a>'
      '<a href="/sellercentre/news/2026-january/trust-and-protections#feedback-policy-update"><span>Automatic positive feedback</span></a>'
      '<a href="/help/x">Help</a>')
e = veille_ebay.entrees(P1)
assert [x["titre"] for x in e] == ["Issue Resolution Centre launch", "Automatic positive feedback"], e
assert e[1]["url"].startswith("https://www.ebay.ca/sellercentre/news/")
assert veille_ebay.sorte("Final value fee adjustments") == "frais" and veille_ebay.sorte("Laws and regulations guide") == "legal"
assert veille_ebay.sorte("Short videos in Promoted Listings") == "frais" and veille_ebay.sorte("Team Access") == "autre"
assert veille_ebay.taux_cartes("<td>Sports Trading Cards</td><td>13.75% on total amount up to $7,500</td>") == 13.75
assert veille_ebay.taux_cartes("aucun taux") is None
# 2. premier passage : apprend la page (aucune alerte) ; ensuite, une nouvelle entree de frais -> alerte a l'admin
alertes = []
P2 = P1 + '<a href="/sellercentre/news/2026-october/fees#fvf">Final value fee changes for Trading Cards</a>'
pages = {veille_ebay.SOURCES[0]["url"]: P1}
lire = lambda u: pages.get(u, "<p>Sports Trading Cards 13.6% of the total</p>")
r = veille_ebay.rafraichir(lambda t, x: alertes.append((t, x)), lire, us=False)
assert r["nouveautes"] == 0 and not alertes
pages[veille_ebay.SOURCES[0]["url"]] = P2
r = veille_ebay.rafraichir(lambda t, x: alertes.append((t, x)), lire, us=False)
assert r["nouveautes"] == 1 and len(alertes) == 1 and "Trading Cards" in alertes[0][1], alertes
n = veille_ebay.resume()["nouveautes"][0]
assert n["sorte"] == "frais" and n["taux_cartes"] == 13.6
assert veille_ebay.rafraichir(lambda t, x: alertes.append((t, x)), lire, us=False)["nouveautes"] == 0 and len(alertes) == 1
# une page qui ne repond plus : signalee, rien d'efface
pages[veille_ebay.SOURCES[0]["url"]] = "<html>captcha</html>"
veille_ebay.rafraichir(None, lire, us=False)
s = veille_ebay.resume()["sources"]["ca"]
assert s["erreur"] and s["n"] == 3, s
# 3. frais d'importation vers le Canada : appris des annonces relues (15 au moins)
vu = datetime.now(timezone.utc).isoformat()
ann = [{"item_id": str(i), "lieu": "US", "import_lu": True, "import_cad": 30.0, "prix_cad": 80.0, "port_cad": 20.0, "vu_le": vu} for i in range(20)]
d = {}
v = veille_ebay.calibrer_import(d, ann)
assert abs(v - (0.30 + deals.TAXE_IMPORT)) < 1e-6, v
assert veille_ebay.calibrer_import({}, ann[:10]) is None                         # trop peu : rien ne change
veille_ebay.appliquer(d)
assert abs(deals.IMPORT_DEFAUT - v) < 1e-9 and deals.taxe_de({"lieu": "US"}) == v
# 4. douanes vers les Etats-Unis : relues avec un acheteur americain
ca = [{"item_id": str(100 + i), "lieu": "CA", "encan": False} for i in range(8)]
d2 = {}
assert veille_ebay.calibrer_import_us(d2, ca, lambda i: {"import_lu": True, "import_cad": 12.0, "prix_cad": 90.0, "port_cad": 10.0}) == 0.12
veille_ebay.appliquer(d2)
assert abs(deals.taxe_de({"lieu": "CA"}, "US") - (deals.TAXE_US + 0.12)) < 1e-9
assert veille_ebay.calibrer_import_us({}, ca, lambda i: {"import_lu": False}) is None
# 5. les frais de vente de chaque compte suivent ses vraies ventes
a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
assert a.frais_calibrer()["n"] == 0
ventes = [{"transaction_id": f"api:{i}:1", "item_number": "", "titre": "Carte", "sku": "", "prix": 100.0, "port_charge": 0.0,
           "frais_reels": round(100 * 0.1375 + 0.40, 2), "date": datetime.now().strftime("%Y-%m-%d"), "annulee": False} for i in range(6)]
a._maj_ventes(ventes)
r = a.frais_calibrer()
assert r["change"] and r["pct"] == 13.75 and a.reglages_lire()["frais_ebay_pct"] == 13.75, r
assert not a.frais_calibrer()["change"]
a.reglages_sauver({"frais_ebay_pct": 12.0})                                     # change a la main : plus touche
assert a.reglages_lire()["frais_auto"] is False and a.frais_calibrer().get("manuel") and a.reglages_lire()["frais_ebay_pct"] == 12.0
a.reglages_sauver({"frais_ebay_pct": 12.0, "nom_boutique": "X"})                 # le formulaire renvoie le meme % : rien ne change
a.reglages_sauver({"frais_auto": True})
assert a.frais_calibrer()["change"] and a.reglages_lire()["frais_ebay_pct"] == 13.75
print("OK test_veille_ebay")
