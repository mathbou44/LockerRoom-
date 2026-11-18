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
# 18 nov 2026 (Mathieu : « pas les petites cartes a 25 $ payees 2 $ qui ne sont pas en enchere, dans la Pro ») :
# sans les comps, un prix fixe doit etre A- et plus (B+ pour ses joueurs) ; les encans gardent B ; ses prix cibles restent
assert not d({"score": 70, "total": 25}, fixe_strict=True)                      # un B a prix fixe : non (Pro)
assert d({"score": 70, "total": 25, "encan": True}, fixe_strict=True)           # le meme B en encan : oui
assert d({"score": 82, "total": 25}, fixe_strict=True)                          # un A- a prix fixe : oui
assert d({"score": 76, "total": 25, "pour_moi": ["joueur"]}, fixe_strict=True)  # un B+ de SON joueur : oui
assert d({"score": 70, "total": 25, "alerte_id": 3}, fixe_strict=True)          # son prix cible : oui
assert d({"score": 70, "total": 25})                                            # admin / Platine : inchange
assert d({"score": 30, "total": 25}, iq_min=0, fixe_strict=True)                # il a choisi « toutes les notes » : son choix
assert not d({"score": 70, "total": 25}, iq_min=65, fixe_strict=True)          # « B et + » (le defaut des Filtres) : la regle tient
print("RADAR DIGNE OK")
