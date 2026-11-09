"""5 nov 2026 (Mathieu : « quand je gagne des cartes, elles devraient se retrouver dans une zone achats de l'inventaire ;
quand je mets en ligne une carte achetee, elle est liee directement ») : la liste des achats eBay, un achat -> une carte
(cout = prix paye), et a la vente les achats qui ressemblent a la carte. Aucun reseau."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom, ebay_compte

ebay_compte.statut = lambda *a, **k: {"connecte": False}
api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "t.db"))
api._TAUX.update(c={"usd": 0.72, "lu": 9e12}, lu=9e12)
achats = [{"item_id": "111", "titre": "2025-26 Upper Deck Young Guns Ivan Demidov #201 RC", "quantite": 1, "cout_total": 160.0, "devise": "CAD", "date": "2026-10-20"},
          {"item_id": "222", "titre": "2023-24 Upper Deck Young Guns Connor Bedard #201", "quantite": 1, "cout_total": 380.0, "devise": "CAD", "date": "2026-10-28"}]
api.couts_depuis_achats(achats)
l = api.achats_liste()
assert l["ok"] and l["a_ajouter"] == 2 and len(l["achats"]) == 2, l
# a la vente : la Bedard est proposee pour une Bedard, pas la Demidov
s = api.achats_suggerer("2023-24 UD Young Guns Connor Bedard #201 Rookie")
assert [a["item_id"] for a in s["achats"]] == ["222"] and s["achats"][0]["meme_carte"], s
# garder en collection avec l'achat choisi : relie, cout = prix paye
g = api.carte_garder({"carte": {"emplacement": "Collection"}, "titre": "2023-24 UD Young Guns Connor Bedard #201", "photos": [],
                      "achat": {"item_id": "222", "n": 0}})
assert g["ok"] and g["achat_lie"] and g["achat_lie"]["cout"] == 380.0, g
assert api.carte_lire(g["id"])["cout"] == 380.0
assert api.achats_suggerer("Connor Bedard Young Guns")["achats"] == []          # deja relie : plus propose
# un achat -> une carte de l'inventaire
r = api.achat_vers_inventaire("111", 0)
c = api.carte_lire(r["id"])
assert r["ok"] and c["cout"] == 160.0 and c["statut"] == "En stock" and "Demidov" in c["titre"] and c["source"] == "achat eBay", c
assert api.achat_vers_inventaire("111", 0).get("deja")                           # deux taps : une seule carte
l = api.achats_liste()
assert l["a_ajouter"] == 0 and all(a["carte_id"] for a in l["achats"]), l
# la carte effacee : l'achat redevient libre
api.carte_supprimer(r["id"])
assert api.achats_liste()["a_ajouter"] == 1
print("ok achats inventaire")

# 5 nov 2026 : achetee il y a plus de 3 mois, toujours en stock -> « A mettre sur eBay » (pas une carte de collection)
api.couts_depuis_achats([{"item_id": "444", "titre": "2022-23 Upper Deck Young Guns Matt Boldy #219", "quantite": 1, "cout_total": 40.0,
                          "devise": "CAD", "date": "2026-06-01"}])
v = api.achat_vers_inventaire("444", 0)
k = api.carte_sauver({"titre": "2023-24 Upper Deck Young Guns Logan Cooley #222", "statut": "En stock", "emplacement": "Collection"})
c = api._db(); c.execute("UPDATE cartes SET cree_le='2026-01-01T10:00:00' WHERE id=?", (k["id"],)); c.commit(); c.close()
l = {x["id"]: x for x in api.inventaire_liste({"dispo": 1})}
assert l[v["id"]]["a_afficher"] and l[v["id"]]["achete_le"] == "2026-06-01", l[v["id"]]
assert not l[k["id"]]["a_afficher"]                                            # collection : on la garde
assert not l[g["id"]]["a_afficher"]                                            # achetee le 28 oct : trop recente
assert [x["id"] for x in api.inventaire_liste({"dispo": 1, "a_afficher": 1})] == [v["id"]]
print("ok a mettre sur eBay")
# 9 nov 2026 (Mathieu : « quand j'affiche une carte, l'app cherche si on l'a deja achetee : le prix paye, et notre achat
# n'est jamais un comp, tout sauf notre deal »)
memes, ids, exact = api._mes_achats_titre("2025-26 UD Young Guns Ivan Demidov #201 Rookie", "111")
assert [a["item_id"] for a in memes] == ["111"] and memes[0]["cout"] == 160.0 and memes[0]["cette_annonce"] and exact and "222" in ids, memes
assert api._mes_achats_titre("2025-26 UD Young Guns Ivan Demidov #201")[0][0]["cette_annonce"] is False
assert api._mes_achats_titre("2025-26 UD Young Guns Matvei Michkov #451")[0] == []          # un autre joueur : rien
vs = [{"item_id": "111", "prix": 160, "le": "2026-10-20"},                                     # mon achat (son numero)
      {"item_id": "999", "prix": 161, "le": "2026-10-21"},                                     # au prix paye, le lendemain : le mien
      {"item_id": "888", "prix": 210, "le": "2026-10-21"}, {"item_id": "777", "prix": 190, "le": "2026-09-01"}]
out, n = api._sans_mes_achats(vs, memes, ids)
assert [v["item_id"] for v in out] == ["888", "777"] and n == 2, out
print("ok mes achats hors des comps")
