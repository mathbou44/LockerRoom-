"""7 nov 2026 (Mathieu : « utiliser l'API seulement pour les cartes sans comps de 3 mois ») : CompSniper, un an de ventes."""
import io, json, os, sys, tempfile
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import historique, vendues, base_ventes, cartes_match

jr = lambda k: (datetime.now() - timedelta(days=k)).strftime("%Y-%m-%d")
# sans cle : rien n'est appele
os.environ.pop("COMPSNIPER_CLE", None)
assert historique.rechercher("frank nazar") == ([], "inactif") and not historique.etat()["actif"]
os.environ["COMPSNIPER_CLE"] = "cs_test_xxx"
vendues._taux_usd_cad = lambda: 1.40
REP = {"results": [
    {"itemId": "1", "title": "2024-25 Upper Deck SP Authentic Future Watch Inscribed Frank Nazar Auto 005/999", "itemUrl": "https://www.ebay.com/itm/1",
     "soldPrice": {"amount": "357.14", "currency": "USD"}, "soldDate": jr(218)},
    {"itemId": "2", "title": "2024-25 Sp Authentic - Frank Nazar Future Watch Auto INSCRIBED /999 (Rookie)", "itemUrl": "https://www.ebay.com/itm/2",
     "soldPrice": {"amount": "355.45", "currency": "USD"}, "soldDate": jr(237)},
    {"recordType": "listing_aggregate", "title": "x", "soldPrice": None, "soldDate": None}]}
appels = []
class R(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False
def faux(req, timeout=30):
    appels.append(req.full_url)
    assert req.headers.get("Authorization") == "Bearer cs_test_xxx"
    return R(json.dumps(REP).encode())
historique.urllib.request.urlopen = faux
v, err = historique.rechercher("Frank Nazar future watch auto inscribed")
assert err is None and len(v) == 2 and v[0]["prix"] == round(357.14 * 1.40, 2) and v[0]["source"] == "historique", v
assert "startDate=" in appels[0] and "sort=lastSoldDescending" in appels[0] and "singleUnitOnly=true" in appels[0]
# le cache : pas un 2e appel ; les archives : gardees
historique.rechercher("frank nazar future watch auto inscribed")
assert len(appels) == 1
c = cartes_match.cible_titre("Frank Nazar 2024-25 SP Authentic Future Watch Auto Inscribed 17/999 Blackhawks")
assert len(vendues.archives(c)) == 2
# les budgets : le jour du chasseur, puis le mois
os.environ["LR_HISTORIQUE_JOUR"] = "1"
historique.rechercher("autre carte a", chasseur=True)
assert historique.rechercher("autre carte b", chasseur=True) == ([], "budget")
os.environ["LR_HISTORIQUE_MOIS"] = "3"
historique.rechercher("autre carte c")
assert historique.rechercher("autre carte d") == ([], "budget")
assert historique.etat()["mois"] == 3
print("HISTORIQUE OK")
