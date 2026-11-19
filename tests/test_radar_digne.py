"""Le filtre de qualite du Radar.
16 nov 2026 : jamais une base ; l'utilisateur peut choisir sa limite.
19 nov 2026 (Mathieu : « le Pro doit etre ultra precis ; pas de cartes a 20 $ ») : A- et plus (B+ pour ses joueurs suivis),
30 $ et plus ; a prix fixe (Pro, sans comps) : A et plus (A- pour ses joueurs suivis) ; un « en feu » n'aide pas un prix fixe."""
import os, sys, tempfile
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
from lockerroom import Api
d = Api._radar_digne
assert not d({"score": 40, "total": 60})                      # un D
assert not d({"score": 70, "total": 120})                     # un B : plus dans le Radar par defaut
assert d({"score": 78, "total": 120, "pour_moi": ["joueur"]})  # ... un B+ de SON joueur : oui
assert not d({"score": 70, "total": 120, "pour_moi": ["joueur"]})  # un B : non, meme son joueur
assert d({"score": 84, "total": 31})                          # un A- a 31 $ : oui
assert not d({"score": 95, "total": 25})                      # sous 30 $ : non, meme A+
assert d({"score": 95, "total": 25}, prix_min=5)              # ... sauf si l'utilisateur a choisi 5 $
assert not d({"score": 84, "total": 40}, prix_min=50)         # son minimum a 50 $
assert not d({"score": 90, "total": 45, "sorte": "D"})        # jamais une base
assert d({"score": 84, "total": 45, "sorte": "A"})
assert not d({"total": 45})                                   # sans note : non
# prix fixe sans comps (Pro, gratuit)
assert not d({"score": 84, "total": 45}, fixe_strict=True)                      # un A- a prix fixe : non (Pro)
assert d({"score": 84, "total": 45, "encan": True}, fixe_strict=True)           # le meme A- en encan : oui
assert d({"score": 88, "total": 45}, fixe_strict=True)                          # un A a prix fixe : oui
assert d({"score": 83, "total": 45, "pour_moi": ["joueur"]}, fixe_strict=True)  # un A- de SON joueur : oui
assert d({"score": 70, "total": 45, "alerte_id": 3}, iq_min=0, fixe_strict=True)  # son prix cible : oui (son choix)
assert not d({"score": 88, "total": 45, "pastilles_j": ["en_feu"], "score_carte": 88}, fixe_strict=True)   # A grace au feu seulement : non
assert not d({"score": 92, "total": 45, "sorte": "D"}, fixe_strict=True)        # une base a prix fixe : jamais
assert d({"score": 84, "total": 45})                                            # admin / Platine : A- a prix fixe : oui
assert d({"score": 30, "total": 35}, iq_min=0, fixe_strict=True)                # il a choisi « toutes les notes » : son choix
assert not d({"score": 84, "total": 45}, iq_min=82, fixe_strict=True)          # « A- et + » choisi : la regle du prix fixe tient
print("RADAR DIGNE OK")
