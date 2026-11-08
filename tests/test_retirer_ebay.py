"""8 nov 2026 (Mathieu : « les cartes a retirer de mon inventaire devraient aussi se supprimer dans eBay, et je peux les
selectionner dans l'app ») : cartes_retirer termine l'annonce eBay d'abord ; si eBay refuse, la carte reste."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom, ebay_ecriture, ebay_compte, ebay_moderne

api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "r.db"))
ids = [api.carte_sauver({"titre": f"Carte {i}", "joueur": "X", "statut": "En stock"})["id"] for i in range(4)]
c = api._db()
c.execute("UPDATE cartes SET statut='Listée', item_number='111111111111' WHERE id=?", (ids[0],))
c.execute("UPDATE cartes SET statut='Listée', item_number='222222222222' WHERE id=?", (ids[1],))
c.commit(); c.close()
fin = []
def faux(item_id):
    if item_id == "222222222222":
        raise RuntimeError("eBay HTTP 500 : panne")
    fin.append(item_id)
    return {"ok": True, "item_id": item_id}
vrai = ebay_ecriture.terminer
ebay_ecriture.terminer = faux
try:
    r = api.cartes_retirer([ids[0], ids[1], ids[2]], True)
finally:
    ebay_ecriture.terminer = vrai
assert fin == ["111111111111"] and r["terminees"] == 1 and r["retirees"] == 2, r
assert len(r["erreurs"]) == 1 and r["erreurs"][0]["id"] == ids[1] and "panne" in r["erreurs"][0]["erreur"], r
assert not api.carte_lire(ids[0]) and not api.carte_lire(ids[2])
assert api.carte_lire(ids[1]) and api.carte_lire(ids[3])                       # eBay a refuse : gardee ; pas choisie : gardee
# terminer : Trading EndItem ; deja terminee = pas une erreur
appels = []
vt, vm = ebay_compte.trading, ebay_moderne.retirer
ebay_moderne.retirer = lambda i: None
try:
    ebay_compte.trading = lambda appel, corps, fond=False: appels.append((appel, corps))
    assert ebay_ecriture.terminer("333333333333")["ok"] and appels[0][0] == "EndItem" and "<EndingReason>NotAvailable" in appels[0][1]
    def deja(appel, corps, fond=False):
        raise RuntimeError("eBay : The auction has already been closed. (1047)")
    ebay_compte.trading = deja
    assert ebay_ecriture.terminer("333333333333")["deja"]
finally:
    ebay_compte.trading, ebay_moderne.retirer = vt, vm
print("RETIRER EBAY OK")
