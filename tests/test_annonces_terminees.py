"""4 nov 2026 (revue) : une annonce terminee sans vente (absente des annonces actives d'eBay depuis plus de 24 h) revient
En stock, garde son numero (une vente en retard la retrouve) et peut etre remise en vente. Aucun reseau."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom, ebay_compte

api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "t.db"))
A = lambda i, p: {"item_number": i, "titre": "2025-26 Upper Deck Young Guns Carte " + i, "prix": p, "sku": "", "debut": None}
api._maj_annonces([A("111", 50), A("222", 60), A("333", 70), A("555", 90)])
c = api._db(); c.execute("UPDATE cartes SET vu_actif_le='2026-01-01T10:00:00' WHERE item_number IN ('111','222','555')"); c.commit(); c.close()
r = api._maj_annonces([A("333", 70)])                                   # 111 et 222 ne sont plus actives
assert api._annonces_terminees(r["vu"], 1) == 0                          # 3 terminees pour 1 active : prudent, rien
r = api._maj_annonces([A("333", 70), A("444", 80), A("666", 85)])
assert api._annonces_terminees(r["vu"], 3) == 3
l = {x["item_number"]: x["statut"] for x in api.inventaire_liste({})}
assert l["111"] == "En stock" and l["222"] == "En stock" and l["555"] == "En stock" and l["333"] == "Listée", l
# une vente en retard de 111 retrouve sa carte (pas de doublon)
v = api._maj_ventes([{"transaction_id": "api:1:1", "item_number": "111", "titre": "x", "sku": "", "prix": 50, "port_charge": 0,
                      "frais_reels": None, "date": "2026-11-04"}])
assert v["nouvelles"] == 1 and v["sans_fiche"] == 0, v
# une annonce juste publiee (jamais vue) ne bouge pas ; une sauvegarde sans changer le numero garde « vu »
cid = [x for x in api.inventaire_liste({}) if x["item_number"] == "333"][0]["id"]
api.carte_sauver({"id": cid, "item_number": "333", "prix_demande": 75})
c = api._db(); vu = c.execute("SELECT vu_actif_le FROM cartes WHERE id=?", (cid,)).fetchone()[0]; c.close()
assert vu, "vu_actif_le efface par une sauvegarde"
print("ok annonces terminees")
