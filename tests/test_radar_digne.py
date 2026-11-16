"""16 nov 2026 (Mathieu, questionnaire : « B et plus seulement, C+ pour mes joueurs, jamais une base ; la limite inferieure
a 10 $ et laisser l'utilisateur choisir ») : le filtre de qualite du Radar."""
import os, sys, tempfile
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
from lockerroom import Api
d = Api._radar_digne
assert not d({"score": 40, "total": 6})                       # un D a 6 $
assert not d({"score": 60, "total": 120})                     # un C+ : pas pour tout le monde
assert d({"score": 60, "total": 120, "pour_moi": ["joueur"]})  # ... mais oui pour SON joueur
assert not d({"score": 52, "total": 120, "pour_moi": ["joueur"]})  # un C : non, meme son joueur
assert d({"score": 70, "total": 11})                          # un B a 11 $ : oui
assert not d({"score": 95, "total": 8})                       # sous 10 $ : non, meme A+
assert d({"score": 95, "total": 8}, prix_min=5)               # ... sauf si l'utilisateur a choisi 5 $
assert not d({"score": 70, "total": 30}, prix_min=50)         # son minimum a 50 $
assert not d({"score": 80, "total": 45, "sorte": "D"})        # jamais une base
assert d({"score": 70, "total": 45, "sorte": "A"})
assert not d({"total": 45})                                   # sans note : non
print("RADAR DIGNE OK")
