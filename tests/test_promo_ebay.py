"""31 oct 2026 (Mathieu : « la promotion de 2 % pour eBay n'a pas fonctionne pour Mercer ») : la campagne SlabCoach est
retrouvee meme si elle commence ou est en pause, une annonce deja promue n'est plus une erreur muette, et le message
d'eBay remonte tel quel. python tests/test_promo_ebay.py (eBay simule, aucun appel reseau)."""
import os
import sys
import tempfile
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import annonces  # noqa: E402

def simuler(campagnes, ads=None, refus_ad=None):
    appels = []
    ads = ads if ads is not None else {}
    def mkt(meth, chemin, corps=None):
        appels.append((meth, chemin, corps))
        if meth == "GET" and chemin.startswith("/ad_campaign?"):
            return {"campaigns": campagnes}, {}
        if meth == "POST" and chemin == "/ad_campaign":
            campagnes.append({"campaignId": "NEW", "campaignName": corps["campaignName"], "campaignStatus": "SCHEDULED",
                              "fundingStrategy": {"fundingModel": "COST_PER_SALE"}})
            return {}, {"Location": "https://api.ebay.com/sell/marketing/v1/ad_campaign/NEW"}
        if meth == "POST" and chemin.endswith("/ad"):
            if refus_ad:
                raise annonces.ErreurPromo(400, refus_ad, [35048])
            ads[corps["listingId"]] = (chemin.split("/")[2], corps["bidPercentage"])
            return {}, {}
        if chemin.startswith("/ad_campaign/find_campaign_by_ad_reference"):
            lid = chemin.split("=")[-1]
            if lid not in ads:
                raise annonces.ErreurPromo(404, "pas trouvee")
            cid = ads[lid][0]
            c = next(x for x in campagnes if x["campaignId"] == cid)
            return {"campaigns": [c]}, {}
        if meth == "GET" and "/ad?listing_ids=" in chemin:
            lid = chemin.split("=")[-1]
            return {"ads": [{"adId": "A1", "bidPercentage": ads[lid][1], "adStatus": "ACTIVE"}]}, {}
        if chemin.endswith("/resume") or chemin.endswith("/update_bid"):
            if chemin.endswith("/update_bid"):
                lid = next(k for k, v in ads.items())
                ads[lid] = (ads[lid][0], corps["bidPercentage"])
            return {}, {}
        raise AssertionError(chemin)
    annonces._mkt = mkt
    return appels, ads

CPS = {"fundingModel": "COST_PER_SALE"}
# 1) la campagne commence encore (SCHEDULED) : retrouvee, pas recreee
appels, ads = simuler([{"campaignId": "C1", "campaignName": "SlabCoach", "campaignStatus": "SCHEDULED", "fundingStrategy": CPS}])
r = annonces.promouvoir("123456789012", 2)
assert r["ok"] and r["campagne"] == "C1" and ads["123456789012"] == ("C1", "2.0"), (r, appels)
assert not any(c == "/ad_campaign" and m == "POST" for m, c, _ in appels)

# 2) en pause : relancee
appels, ads = simuler([{"campaignId": "C2", "campaignName": "SlabCoach", "campaignStatus": "PAUSED", "fundingStrategy": CPS}])
annonces.promouvoir("123456789012", 2)
assert ("POST", "/ad_campaign/C2/resume", None) in appels

# 3) l'ancienne est terminee : une nouvelle, avec un autre nom (eBay refuse deux fois le meme nom)
appels, ads = simuler([{"campaignId": "C3", "campaignName": "SlabCoach", "campaignStatus": "ENDED", "fundingStrategy": CPS}])
r = annonces.promouvoir("123456789012", 2)
cree = [c for m, ch, c in appels if m == "POST" and ch == "/ad_campaign"][0]
assert r["campagne"] == "NEW" and cree["campaignName"].startswith("SlabCoach ") and cree["campaignName"] != "SlabCoach", cree

# 4) deja dans une campagne a lui : on le dit, sans erreur
camps = [{"campaignId": "C1", "campaignName": "SlabCoach", "campaignStatus": "RUNNING", "fundingStrategy": CPS},
         {"campaignId": "MA", "campaignName": "Ma campagne", "campaignStatus": "RUNNING", "fundingStrategy": CPS}]
appels, ads = simuler(camps, ads={"123456789012": ("MA", "4.0")}, refus_ad="The listing is already in another campaign")
r = annonces.promouvoir("123456789012", 2)
assert r["ok"] and r["deja"] and "Ma campagne" in r["avertissement"] and "4 %" in r["avertissement"], r

# 5) refus d'eBay sans campagne : le message d'eBay remonte
appels, ads = simuler(camps[:1], refus_ad="eBay (400) : The seller is not eligible for Promoted Listings")
try:
    annonces.promouvoir("123456789012", 2)
    raise AssertionError("aurait du echouer")
except RuntimeError as e:
    assert "not eligible" in str(e), e

# 6) l'etat
appels, ads = simuler(camps[:1], ads={"123456789012": ("C1", "2.0")})
s = annonces.promo_statut("123456789012")
assert s["promue"] and s["pct"] == 2.0, s
appels, ads = simuler(camps[:1])
assert annonces.promo_statut("123456789012")["promue"] is False
# 7) la fiche de la carte : etat, promouvoir ; programmee -> attend la mise en ligne
import ebay_compte, lockerroom  # noqa: E402
ebay_compte.statut = lambda: {"connecte": True}
a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
cid = a.carte_sauver({"joueur": "Mercer", "titre": "Dawson Mercer YG", "prix_demande": 20}).get("id")
c = a._db(); c.execute("UPDATE cartes SET item_number='123456789012', debut=NULL WHERE id=?", (cid,)); c.commit(); c.close()
appels, ads = simuler(camps[:1])
assert a.annonce_promotion(cid)["promue"] is False
r = a.annonce_promotion(cid, 2)
assert r["ok"] and r["promue"] and r["pct"] == 2.0, r
c = a._db(); c.execute("UPDATE cartes SET debut='2099-01-01T12:00:00.000Z' WHERE id=?", (cid,)); c.commit(); c.close()
r = a.annonce_promotion(cid, 3)
assert r["attente"]["pct"] == 3 and r["attente"]["debut"].startswith("2099"), r
print("ok : promotion eBay")
