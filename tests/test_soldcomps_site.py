"""11 nov 2026 (SoldComps : « eBay.com est revenu, les autres sites recuperent encore ») : eBay.ca en panne est saute 30 min ;
les ventes d'eBay.com passent quand meme, sans attendre eBay.ca a chaque recherche."""
import os, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import vendues
vendues._cle = lambda: "x"
vendues.actif = lambda: True
vendues._budget_ok = lambda *a, **k: True
vendues._taux_usd_cad = lambda: 1.38
appels = []
def appel(q, site, **k):
    appels.append(site)
    if site == "ebay.ca":
        return None, "SoldComps injoignable (TimeoutError)"
    return {"items": [{"title": q, "soldPrice": 50, "soldDate": "2026-11-10", "url": "https://www.ebay.com/itm/123456789012", "currency": "USD"}]}, None
vendues._appel = appel
r = vendues.rechercher("bedard young guns", fond=True, usage="verif")
assert appels == ["ebay.com", "ebay.ca"] and not r.get("erreur"), (appels, r)
assert vendues._SITE_PANNE["ebay.ca"] > time.time() + 1700
assert vendues._PANNE[0] < time.time(), "eBay.ca seul en panne ne met pas toute la chasse en pause"
appels.clear()
vendues.rechercher("mcdavid young guns", fond=True, usage="verif")
assert appels == ["ebay.com"], appels                   # eBay.ca saute pendant 30 min
print("OK soldcomps site")
