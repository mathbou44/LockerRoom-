"""10 nov 2026 (Mathieu : « legaux a 100 % », choix 1) : juger le prix d'une annonce eBay (deals, prix suggere, alertes de
deals) = l'admin seulement, tant qu'eBay n'a pas donne son accord ecrit (licence §8.5 c, §9.5)."""
import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
comptes.DOSSIER_COMPTES = os.path.join(comptes.DONNEES, "comptes")
import lockerroom
api = lockerroom.Api()
assert lockerroom.ebay_prix_actif()                       # le PC de Mathieu (un seul utilisateur) : tout
comptes.MULTI = True
cid, _ = comptes.trouver_ou_creer("apple-sub-9", "Quelqu'un", "apple")
with comptes.utiliser(cid):
    assert not lockerroom.ebay_prix_actif(), "un utilisateur ne voit pas les deals"
    r = api.deals_liste({})
    assert r["coupe"] and not r["deals"], r
    os.environ["LR_PRIX_EBAY_PUBLIC"] = "1"               # apres l'accord ecrit d'eBay
    assert lockerroom.ebay_prix_actif()
    os.environ.pop("LR_PRIX_EBAY_PUBLIC")
api._est_admin = lambda reel=False: True
with comptes.utiliser(cid):
    assert lockerroom.ebay_prix_actif(), "l'admin garde les deals et les comps"
print("OK deals admin")
# 10 nov 2026 : les comps (ventes recoltees sur eBay) = admin seulement
import vendues
api._est_admin = lambda reel=False: False
with comptes.utiliser(cid):
    assert not lockerroom.comps_permis()
    assert vendues.rechercher("connor bedard young guns", fond=False).get("coupe")
    assert vendues.memes("Connor Bedard Young Guns")["coupe"]
    assert api.tendances()["coupe"] and api.pouls()["coupe"] and api.collection_valeur()["coupe"]
    assert api.forfait()["comps"] is False
assert lockerroom.comps_permis()                          # tache de fond sans compte (chasseur de l'admin)
api._est_admin = lambda reel=False: True
with comptes.utiliser(cid):
    assert lockerroom.comps_permis()
print("OK comps admin")
# 10 nov 2026 : l'admin regarde l'app comme un utilisateur Pro ou Gratuit
import forfaits
vrai = lockerroom.vue_simulee
api._est_admin = lambda reel=False: True
lockerroom.vue_simulee = lambda: "gratuit"
with comptes.utiliser(cid):
    assert not lockerroom.comps_permis() and not lockerroom.ebay_prix_actif()
    assert forfaits.etat()["pro"] is False
lockerroom.vue_simulee = lambda: "pro"
with comptes.utiliser(cid):
    assert forfaits.etat()["pro"] is True and not lockerroom.comps_permis()
lockerroom.vue_simulee = vrai
with comptes.utiliser(cid):
    assert lockerroom.comps_permis()
print("OK vue simulee")
