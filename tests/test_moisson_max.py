"""11 nov 2026 (Mathieu : « maximiser jusqu'a 5 000 ventes par jour, c'est gratuit ; les plus utiles dans NOTRE banque ») :
la moisson prend presque tout le budget, les ventes utiles d'abord, et une 2e passe le soir ramasse le reste."""
import os, sys, tempfile
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
os.environ["THECARDAPI_CLE"] = "x"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import thecardapi, base_ventes
assert thecardapi.plafond_jour() == 4950
mots, n_page = [], {"n": 0}
def appel(p, delai):
    mots.append(p["q"])
    n_page["n"] += 1
    return {"data": [{"title": f"{p['q']} carte {n_page['n']}-{i}", "sale_price": 20, "sale_date": "2026-11-10", "id": f"ebay_{100000000000 + n_page['n'] * 1000 + i}"} for i in range(100)]}
thecardapi._appel = appel
thecardapi._taux = lambda: 1.38
thecardapi.moissonner(max_pages=100)
assert mots[0] == "hockey auto" and "hockey" in mots, mots[:3]
u = thecardapi.utilisees()
assert 4500 <= u <= 4950 * 0.94 + 100, u                       # presque tout le jour, ~300 gardees pour les secours
assert thecardapi._budget_ok("tap", 100)                         # un geste de l'utilisateur passe encore
print("MOISSON MAX OK", u)
