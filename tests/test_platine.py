"""16 nov 2026 : la version Platine (comps et prix calcules) : fermee tant que LR_PLATINE n'est pas a 1, sauf la vue
« comme un Platine » de l'admin ; un compte Pro ordinaire n'y a jamais droit."""
import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
os.environ.pop("LR_PLATINE", None)
import forfaits
import lockerroom

# vue simulee « platine » : comps et prix permis, meme avant l'ouverture
lockerroom.vue_simulee = lambda: "platine"
forfaits_etat = forfaits.etat()
assert forfaits_etat["platine"] and forfaits_etat["pro"], forfaits_etat
assert forfaits.est_platine()
assert lockerroom._platine()
# vue « pro » : jamais les comps
lockerroom.vue_simulee = lambda: "pro"
assert not forfaits.est_platine() and not lockerroom._platine()
# un vrai compte au forfait platine : rien tant que LR_PLATINE n'est pas a 1
lockerroom.vue_simulee = lambda: None
import comptes
comptes.info = lambda cid: {"forfait": "platine", "cree_le": "2026-01-01T00:00:00"}
forfaits._compte = lambda: "c1"
assert not forfaits.est_platine() and forfaits.etat()["pro"]          # payant (Pro) mais pas encore Platine
os.environ["LR_PLATINE"] = "1"
assert forfaits.est_platine()
comptes.info = lambda cid: {"forfait": "pro", "cree_le": "2026-01-01T00:00:00"}
assert not forfaits.est_platine()                                        # un Pro reste un Pro
print("PLATINE OK")
