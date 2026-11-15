"""15 nov 2026 (« c'est meme plus cette photo-la ; sur eBay ce sont d'autres photos ») : les photos des cartes en vente sont
relues chez eBay (GetItem) ; la vignette de GetMyeBaySelling ne les ecrase plus ensuite."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("LOCKERROOM_DATA", tempfile.mkdtemp())
import lockerroom, ebay_compte

api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "p.db"))
k = api.carte_sauver({"titre": "2015-16 SP Authentic Jari Kurri Global Chirography Auto", "statut": "Listée", "item_number": "123456789012",
                      "photo": "/mes-photos/vieux-dos.jpg", "prix_demande": 45})
v = api.carte_sauver({"titre": "Vendue", "statut": "Vendue", "item_number": "999999999999", "photo": "/mes-photos/v.jpg"})
APP = []
def _ph(i):
    APP.append(i)
    return ["https://i.ebayimg.com/images/g/AAA/s-l1600.jpg", "https://i.ebayimg.com/images/g/BBB/s-l1600.jpg"]
ebay_compte.photos_item = _ph
assert api._photos_annonces() == 1
assert APP == ["123456789012"], APP                    # seulement les cartes en vente
c = api.carte_lire(k["id"])
assert c["photo"] == "https://i.ebayimg.com/images/g/AAA/s-l1600.jpg", c["photo"]
assert c["photos"].count("i.ebayimg.com") == 2, c["photos"]
# relue au plus une fois aux 20 h
assert api._photos_annonces() == 0 and APP == ["123456789012"]
# la synchro des annonces (vignette ancienne) n'ecrase plus la photo relue
api._maj_annonces([{"item_number": "123456789012", "titre": "x", "prix": 45, "sku": "", "photo": "https://i.ebayimg.com/vieille/s-l140.jpg"}])
assert api.carte_lire(k["id"])["photo"] == "https://i.ebayimg.com/images/g/AAA/s-l1600.jpg"
# eBay ne repond pas : on arrete le tour, rien ne casse
def _err(i): raise RuntimeError("eBay ferme")
ebay_compte.photos_item = _err
k2 = api.carte_sauver({"titre": "Autre", "statut": "Listée", "item_number": "123456789013"})
assert api._photos_annonces() == 0
print("PHOTOS ANNONCES OK")
