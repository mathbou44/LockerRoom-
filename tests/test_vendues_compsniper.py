"""12 nov 2026 (Mathieu : « je peux remplacer SoldComps par CompSniper ») : CompSniper comme source principale des ventes."""
import io, json, os, sys, tempfile
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import historique, vendues

jr = lambda k: (datetime.now() - timedelta(days=k)).strftime("%Y-%m-%d")
for k in ("SOLDCOMPS_CLE", "COMPSNIPER_CLE", "LR_VENTES_SOURCE", "LR_HISTORIQUE_MOIS", "LR_HISTORIQUE_JOUR"):
    os.environ.pop(k, None)
vendues._cle = lambda: os.environ.get("SOLDCOMPS_CLE", "")
vendues._taux_usd_cad = lambda: 1.40
vendues._coupe = lambda: False
historique.rechercher.__globals__  # meme module
import lockerroom
lockerroom.comps_permis = lambda: True

# le choix de la source
os.environ["SOLDCOMPS_CLE"] = "sc"
assert vendues.source() == "soldcomps"
os.environ["COMPSNIPER_CLE"] = "cs"
assert vendues.source() == "soldcomps"                  # les deux cles : SoldComps tant qu'on ne choisit pas
os.environ["LR_VENTES_SOURCE"] = "compsniper"
assert vendues.source() == "compsniper"
os.environ.pop("LR_VENTES_SOURCE")
os.environ.pop("SOLDCOMPS_CLE")
assert vendues.source() == "compsniper" and vendues.actif()   # la cle SoldComps retiree : bascule toute seule

REP = {"results": [
    {"itemId": "1", "title": "2023-24 Upper Deck Ice Emerald Surge Cole Caufield 1/10 PSA 8", "itemUrl": "https://www.ebay.com/itm/1",
     "soldPrice": {"amount": "700", "currency": "USD"}, "soldDate": jr(150)},
    {"itemId": "2", "title": "2023-24 Upper Deck Ice Emerald Surge Cole Caufield /10", "itemUrl": "https://www.ebay.com/itm/2",
     "soldPrice": {"amount": "650", "currency": "USD"}, "soldDate": jr(20)}]}
appels = []
class R(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False
def faux(req, timeout=30):
    appels.append(req.full_url)
    return R(json.dumps(REP).encode())
historique.urllib.request.urlopen = faux

# budget du mois : 300 -> environ 300 / jours restants par jour
os.environ["LR_HISTORIQUE_MOIS"] = "300"
pl = vendues.plafond_jour()
assert 1 <= pl <= 300, pl
r = vendues.rechercher("caufield emerald surge", fond=True, usage="verif")
assert not r["erreur"] and len(r["ventes"]) == 2 and r["ventes"][0]["prix"] == 980.0 and r["ventes"][0]["ts"], r
assert len(appels) == 1 and vendues.utilises_aujourdhui() == 1 and vendues.utilises_aujourdhui("verif") == 1
# le cache : pas un 2e appel, pas un 2e credit
r2 = vendues.rechercher("caufield emerald surge", fond=True, usage="verif")
assert r2.get("cache") and len(appels) == 1 and vendues.utilises_aujourdhui() == 1
# l'historique d'un an (deals) sur la meme recherche : deja en cache chez CompSniper, aucun credit
v, e = historique.rechercher("caufield emerald surge", chasseur=True)
assert e is None and len(v) == 2 and len(appels) == 1
# une panne : le credit est rendu
def panne(req, timeout=30):
    raise OSError("x")
historique.urllib.request.urlopen = panne
r3 = vendues.rechercher("hasek premier focus gold", fond=False)
assert r3["erreur"] and vendues.utilises_aujourdhui() == 1, (r3, vendues.utilises_aujourdhui())
# SoldComps encore la (jusqu'au 18 nov) : CompSniper en panne -> None (SoldComps prend le relais)
historique._ERREUR.update(le=0, texte=None)
os.environ["SOLDCOMPS_CLE"] = "sc"; os.environ["LR_VENTES_SOURCE"] = "compsniper"
assert vendues._par_compsniper("encore une autre", False, None, None) is None
os.environ.pop("SOLDCOMPS_CLE"); os.environ.pop("LR_VENTES_SOURCE")
historique._ERREUR.update(le=0, texte=None)
historique.urllib.request.urlopen = faux
# le mois epuise -> plus rien (jamais au-dela du forfait)
os.environ["LR_HISTORIQUE_MOIS"] = "1"
assert vendues.plafond_jour() == 0 or historique.utilises()["mois"] >= 1
r4 = vendues.rechercher("une autre carte", fond=False)
assert r4["erreur"] and len(appels) == 1, r4
assert vendues.statut()["source"] == "compsniper"
print("VENDUES COMPSNIPER OK")
# la comparaison avec SoldComps (jusqu'au 18 nov) : couverture, ecart de mediane, fraicheur
os.environ["SOLDCOMPS_CLE"] = "sc"
cs = [{"titre": "a", "prix": 100.0, "le": jr(5), "url": "https://www.ebay.com/itm/123456789012"},
      {"titre": "b", "prix": 110.0, "le": jr(200), "url": "https://www.ebay.com/itm/223456789012"}]
sc_rep = {"items": [{"title": "a", "soldPrice": "70", "soldCurrency": "USD", "endedAt": jr(5) + "T10:00:00", "url": "https://www.ebay.com/itm/123456789012"},
                    {"title": "c", "soldPrice": "80", "soldCurrency": "USD", "endedAt": jr(1) + "T10:00:00", "url": "https://www.ebay.com/itm/323456789012"}]}
l = vendues.comparer("cole caufield ice emerald", cs, appel=lambda q: sc_rep)
assert l["sc"] == 2 and l["communs"] == 1 and l["cs90"] == 1 and l["der_sc"] > l["der_cs"], l
r = vendues.comparaison_resume()
assert r["n"] == 1 and r["couverture"] == 0.5 and r["plus_frais"]["sc"] == 1, r
os.environ.pop("SOLDCOMPS_CLE")
print("COMPARAISON OK")
