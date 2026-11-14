"""14 nov 2026 (Mathieu : « 157 $ de profit ? 170 - 59 et les frais, ca fait pas 157 ») : le profit d'une carte vendue suit
son cout quand l'achat eBay se relie apres la vente (ou qu'on corrige le cout), et les ventes deja faites sont refaites."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom, ebay_compte
ebay_compte.statut = lambda *a, **k: {"connecte": False}
api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "t.db"))
api._TAUX.update(c={"usd": 0.72, "lu": 9e12}, lu=9e12)
# la Rinne vendue 170 $ + 8 $ de port charge, 21 $ de frais eBay, sans cout : le profit garde = le net (157 $)
v = api.carte_sauver({"titre": "2017-18 SP Game Used Pekka Rinne Stanley Cup Final Materials", "statut": "Vendue"})
c = api._db(); c.execute("UPDATE cartes SET prix_vendu=170, port_charge=8, frais=21, profit=157, canal='eBay' WHERE id=?", (v["id"],)); c.commit(); c.close()
# 1. une vieille vente fausse : refaite a la lecture de l'inventaire (pas de cout : 157 reste juste)
c = api._db(); c.execute("UPDATE cartes SET cout=59 WHERE id=?", (v["id"],)); c.commit(); c.close()     # le cout pose sans le profit (avant)
lockerroom.Api._PROFITS_REPARES.clear()
api.inventaire_liste({})
assert api.carte_lire(v["id"])["profit"] == 98.0, api.carte_lire(v["id"])            # 170 + 8 - 21 - 59
# 2. l'achat eBay relie apres la vente : le profit suit tout de suite
api.couts_depuis_achats([{"item_id": "777", "titre": "Pekka Rinne SP Game Used", "quantite": 1, "cout_total": 64.0, "devise": "CAD", "date": "2026-08-01"}])
api.achat_relier(v["id"], "777", 0)
assert api.carte_lire(v["id"])["cout"] == 64.0 and api.carte_lire(v["id"])["profit"] == 93.0, api.carte_lire(v["id"])
# 3. le cout corrige a la main : le profit suit aussi
api.carte_sauver({"id": v["id"], "cout": 50})
assert api.carte_lire(v["id"])["profit"] == 107.0
print("PROFIT COUT OK")
