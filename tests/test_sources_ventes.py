"""10 nov 2026 (Mathieu : « le plus de sources possible, une de base et les autres pour raffiner et sauver ») :
SoldComps = la base ; TheCardAPI raffine (ventes en plus, doublons retires), sauve (SoldComps en panne) et archive."""
import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
os.environ["SOLDCOMPS_CLE"] = "sc-test"
os.environ["THECARDAPI_CLE"] = "tca-test"
os.environ["LR_THECARDAPI_JOUR"] = "1000"
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import vendues
import thecardapi
import historique

vendues._taux_usd_cad = lambda: 1.4
historique.actif = lambda: False
appels = []


def tca(params, delai):
    appels.append(params)
    return {"data": [
        {"id": "ebay_111111111111", "title": "2023-24 Upper Deck Young Guns Connor Bedard #201", "platform": "eBay",
         "listing_type": "Auction", "sale_price": 100, "sale_date": "2026-11-09", "listing_url": "https://www.ebay.com/itm/111111111111"},
        {"id": "ebay_222222222222", "title": "2023-24 Upper Deck Young Guns Connor Bedard #201", "platform": "eBay",
         "listing_type": "BestOffer", "sale_price": "90.00", "sale_date": "2026-11-08", "listing_url": ""},
        {"id": "x", "title": "autre", "platform": "COMC", "sale_price": 5, "sale_date": "2026-11-08"},
    ], "total": 3}


thecardapi._appel = tca

# 1. TheCardAPI seul : prix en $ CA, Best Offer = offre, l'adresse refaite depuis l'id, les autres plateformes ecartees
v, err = thecardapi.rechercher("bedard young guns", limite=50, usage="raffiner")
assert not err and len(v) == 2, (v, err)
assert v[0]["prix"] == 140.0 and v[1]["offre"] and v[1]["url"].endswith("/itm/222222222222"), v
assert thecardapi.utilisees() == 3 and thecardapi.utilisees("raffiner") == 3

# 2. SoldComps repond : la vente 111 deja la n'est pas doublee, la 222 s'ajoute (raffiner)
sc_item = {"title": "2023-24 Upper Deck Young Guns Connor Bedard #201", "soldPrice": "95", "soldCurrency": "USD",
           "endedAt": "2026-11-09T20:00:00", "url": "https://www.ebay.com/itm/111111111111"}
vendues._appel = lambda q, site, **k: ({"items": [sc_item] if site == "ebay.com" else []}, None)
r = vendues.memes("Connor Bedard Young Guns 2023-24")
urls = [x.get("url") for x in r["ventes"]]
assert len([u for u in urls if u and u.endswith("111111111111")]) == 1, urls
assert any(u and u.endswith("222222222222") for u in urls), urls

# 3. SoldComps en panne, rien en cache : TheCardAPI sauve (un geste de l'utilisateur)
vendues._appel = lambda q, site, **k: (None, "SoldComps injoignable (TimeoutError)")
r = vendues.rechercher("connor bedard young guns 2023 exclusives", fond=False)
assert r.get("secours") == "thecardapi" and r["ventes"], r
# une tache de fond ordinaire ne brule pas TheCardAPI ; une verification de deal, oui (sur sa part)
vendues._PANNE[0] = 0
assert vendues._secours("q fond", True, None) is None
assert vendues._secours("q verif", True, "verif")["secours"] == "thecardapi"

# 4. le plafond du jour de TheCardAPI est respecte
thecardapi._CACHE.clear()
os.environ["LR_THECARDAPI_JOUR"] = "10"
v, err = thecardapi.rechercher("autre chose", limite=50, usage="tap")
assert err == "plafond du jour" and not v
os.environ["LR_THECARDAPI_JOUR"] = "1000"

# 5. la moisson va dans nos archives
import base_ventes
thecardapi._CACHE.clear()
n = thecardapi.moissonner(max_pages=3)
assert n >= 2, n
assert vendues.statut()["thecardapi"]["actif"]
print("OK sources de ventes")

# 11 nov 2026 : TheCardAPI (forfait gratuit : pagination par curseur) : la moisson suit le curseur jusqu'a la fin
import thecardapi
os.environ["THECARDAPI_CLE"] = "test"
appels_t = []
def faux(p, delai):
    appels_t.append(dict(p))
    k = int(p.get("cursor") or 0)
    rows = [{"title": f"2024-25 Upper Deck Young Guns Joueur {k * 100 + i} #201", "sale_price": 10 + i, "sale_date": "2026-11-10",
             "url": f"https://www.ebay.com/itm/{k * 100 + i}", "currency": "USD"} for i in range(100 if k < 2 else 40)]
    return {"data": rows, "next_cursor": str(k + 1) if k < 2 else None}
thecardapi._appel = faux
thecardapi._taux = lambda: 1.4
thecardapi._CACHE.clear()
n_t = thecardapi.moissonner(max_pages=10)
assert [a.get("cursor") for a in appels_t] == [None, "1", "2"], appels_t
assert thecardapi.statut()["reponse_champs"] == ["data", "next_cursor"]
os.environ.pop("THECARDAPI_CLE")
print("OK TheCardAPI curseur", n_t)
