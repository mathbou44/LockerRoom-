"""19 nov 2026 (audit du site, Mathieu : « go pour les breaks ») : pour le public (Pro, Gratuit), le prix juste d'une place de
break ne vient d'aucune donnee eBay (ni ventes, ni annonces) : la valeur d'un sous-ensemble = le modele (groupe, tirage) et la
cote du joueur = les donnees publiques du sport (demande_legale : LNH, Wikipedia)."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import valeurs, valeur_produit, demande_legale

def interdit(*a, **k):
    raise AssertionError("donnees eBay utilisees pour le public")
valeur_produit.valeur = interdit
valeur_produit.demande_recrue = interdit
valeurs._comps = lambda: False
appels = []
vieux = demande_legale.demande
demande_legale.demande = lambda n: appels.append(n) or 2.0
prod = {"id": "test-prod"}
se = {"Young Guns": {"groupe": "recrue"}, "Young Guns Exclusives": {"groupe": "recrue", "parallele_de": "Young Guns", "tirage": 100}}
valeurs._charger()["sous_ensembles"] = {"test-prod": {"Young Guns": {"valeur": 999.0}}}     # une mesure eBay : jamais pour le public
v, mesuree = valeurs.valeur_carte(prod, "Young Guns", "Connor Bedard", se, {})
assert v > 0 and not mesuree and v != 999.0 * 2.0, (v, mesuree)
v2, _ = valeurs.valeur_carte(prod, "Young Guns Exclusives", "Connor Bedard", se, {})
assert v2 > v, (v, v2)                              # une /100 vaut plus que la base (le modele du tirage)
assert "Connor Bedard" in appels                    # la cote du joueur : les donnees publiques
print("OK test_breaks_public")
