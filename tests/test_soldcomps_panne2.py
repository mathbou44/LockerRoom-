"""9 nov 2026 (courriel de SoldComps : eBay refuse leurs recherches ; « ralentissez les essais » ; les echecs ne sont pas
factures) : un echec rend son credit a notre budget du jour et l'attente des taches de fond grandit (2, 5, 15, 30 min)."""
import os
import sys
import tempfile
import time
import urllib.error
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import vendues
vendues._cle = lambda: "x"


def panne(req, timeout=0):
    raise urllib.error.HTTPError(req.full_url, 503, "Service Unavailable", {}, None)


vendues.urllib.request.urlopen = panne
avant = vendues.utilises_aujourdhui()
d, err = vendues._appel("bedard young guns", "ebay.com", attendre=False)
assert d is None and "HTTP 503" in err, err
assert vendues.utilises_aujourdhui() == avant, "un echec ne compte pas dans le budget"
attentes = []
for _ in range(5):
    vendues._noter_erreur("q", err)
    attentes.append(round(vendues._PANNE[0] - time.time()))
assert attentes[0] in (119, 120) and attentes[1] in (299, 300) and attentes[2] in (899, 900) and attentes[4] in (1799, 1800), attentes
print("OK soldcomps panne")
# le secours : CompSniper quand SoldComps est en panne et que rien n'est en cache (geste de l'utilisateur seulement)
import historique
from datetime import datetime
historique.actif = lambda: True
historique.rechercher = lambda q, **k: ([{"titre": "2023 Bedard Young Guns", "prix": 300.0, "le": datetime.now().strftime("%Y-%m-%d"), "source": "historique"}], None)
vendues._PANNE[0] = 0; vendues._PANNE_N[0] = 0; vendues._ERREURS.clear()
r = vendues.rechercher("bedard young guns 451 exclusives", fond=False)
assert r.get("secours") == "compsniper" and r["ventes"] and not r.get("erreur"), r
r2 = vendues.rechercher("bedard young guns 451 clear cut", fond=True)
assert not r2.get("secours"), r2
print("OK secours compsniper")
