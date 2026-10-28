"""Offres aux acheteurs interesses (API Negotiation d'eBay, simulee) : python tests/test_offres.py"""
import json
import os
import sys
import tempfile

os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ebay_moderne as em  # noqa: E402
import ebay_offres  # noqa: E402
import ebay_compte  # noqa: E402
import forfaits  # noqa: E402
import lockerroom  # noqa: E402

APPELS = []
CA_OK = [False]


def rest(meth, chemin, corps=None, base=None, marche=True):
    APPELS.append((meth, chemin, corps, marche))
    if not CA_OK[0] and marche == "EBAY_CA":
        raise em.ErreurEbay("marketplace not supported", 400, ["150002"])
    if "find_eligible_items" in chemin:
        return 200, {}, {"eligibleItems": [{"listingId": "111"}, {"listingId": "222"}, {"listingId": "333"}, {"listingId": "999"}], "total": 4}
    lid = corps["offeredItems"][0]["listingId"]
    if lid == "333":
        raise em.ErreurEbay("best offer exists", 409, ["150018"])
    return 200, {}, {"offers": [{"offerId": "o1"}, {"offerId": "o2"}]}


em.rest = rest
ebay_compte.statut = lambda: {"connecte": True, "ecriture": True, "cles_ok": True}
a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "o.db"))
ACT = [{"item_number": "111", "titre": "Bedard YG", "prix_demande": 400.0, "cout": None, "photo": None, "watchers": 5, "id": 1},
       {"item_number": "222", "titre": "Fantilli YG", "prix_demande": 50.0, "cout": 47.0, "photo": None, "watchers": 1, "id": 2},
       {"item_number": "333", "titre": "Celebrini YG", "prix_demande": 160.0, "cout": 158.0, "photo": None, "watchers": 2, "id": 3}]
a._annonces_actives = lambda c: [dict(x) for x in ACT]
c = a._db(); c.execute("INSERT INTO sante (item_number, verdict, suggestion, mediane) VALUES ('111','baisser',340,345)"); c.commit(); c.close()

r = a.offres_liste()
assert r["ok"] and r["marche"] == "EBAY_US" and r["n_ebay"] == 4, r          # CA refuse -> US retenu
it = {x["item_number"]: x for x in r["items"]}
assert set(it) == {"111", "222", "333"}                                         # 999 : pas une annonce active connue
assert it["111"]["pct"] == 15 and it["222"]["pct"] == 6.0 and it["333"]["sous_cout"] and it["333"]["pct"] is None, it
assert r["items"][-1]["item_number"] == "333"                                   # sous le cout : a la fin
# garde 1 h : pas de 2e appel
n = len(APPELS); a.offres_liste(); assert len(APPELS) == n
# envoi : corps conforme aux regles d'eBay
assert not a.offres_envoyer("111", 3)["ok"]
r = a.offres_envoyer("111", 15, "Merci de suivre <b>ma</b> carte !")
assert r["ok"] and r["n"] == 2, r
meth, chemin, corps, m = APPELS[-1]
assert chemin.endswith("/send_offer_to_interested_buyers") and m == "EBAY_US" and corps["allowCounterOffer"] is False
assert corps["offeredItems"] == [{"listingId": "111", "discountPercentage": "15", "quantity": 1}] and "offerDuration" not in corps
assert "<" not in corps["message"]
# deja une offre -> message clair ; l'annonce envoyee ne revient pas dans la liste
r = a.offres_envoyer("333", 10); assert not r["ok"] and "déjà" in r["erreur"], r
assert "111" not in {x["item_number"] for x in a.offres_liste()["items"]} and a.offres_compte()["n"] == 3
# Gratuit : 3 par jour
forfaits.est_pro = lambda: False
forfaits._compte = lambda: "x"
for _ in range(3):
    forfaits.compter("offres_jour")
r = a.offres_envoyer("222", 6); assert not r["ok"] and r.get("pro_requis"), r
print("OFFRES OK")
