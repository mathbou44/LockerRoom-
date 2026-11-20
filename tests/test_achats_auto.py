"""20 nov 2026 (Mathieu : « les cartes achetees sont necessairement dans ton inventaire ; tout doit etre automatise ») : un achat eBay
entre tout seul dans l'inventaire avec le prix paye ; une carte supprimee ne revient pas ; la meme carte creee ensuite a la main
remplace la copie automatique (pas de doublon) ; la 1re synchro va chercher 2 ans de ventes, une seule fois."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import lockerroom
a = lockerroom.Api(chemin_db=os.path.join(os.environ["LOCKERROOM_DONNEES"], "t.db"))
c = a._db(); a._achats_table(c)
c.execute("INSERT INTO achats_ebay (item_id, n, titre, cout, devise, date) VALUES (?,?,?,?,?,?)",
          ("111", 0, "2024-25 Upper Deck Young Guns Macklin Celebrini #201", 120.0, "CAD", "2026-11-01"))
c.execute("INSERT INTO achats_ebay (item_id, n, titre, cout, devise, date) VALUES (?,?,?,?,?,?)",
          ("222", 0, "2025-26 SP Authentic Future Watch Auto Ivan Demidov /999", 300.0, "CAD", "2026-11-02"))
c.commit(); c.close()
n = a.achats_ajouter_auto()
assert n == 2, n
L = a.inventaire_liste({"dispo": 1})
L = L if isinstance(L, list) else L.get("cartes")
cel = [x for x in L if "Celebrini" in x["titre"]]
assert len(cel) == 1 and cel[0]["cout"] == 120.0 and cel[0]["emplacement"] == "Réserve", cel
assert a.achats_ajouter_auto() == 0                       # deja ajoutes
dem = [x for x in L if "Demidov" in x["titre"]][0]
a.carte_supprimer(dem["id"])                              # supprimee par la personne : ne revient pas
assert a.achats_ajouter_auto() == 0
# la meme carte creee a la main (une photo pour la vendre) : la copie automatique part, la carte gardee recoit le prix paye
r = a.carte_sauver({"titre": "Macklin Celebrini 2024-25 Upper Deck Young Guns Rookie #201", "statut": "En stock"})
assert a.achats_fusionner_doublons() == 1
L = a.inventaire_liste({"dispo": 1}); L = L if isinstance(L, list) else L.get("cartes")
cel = [x for x in L if "Celebrini" in x["titre"]]
assert len(cel) == 1 and cel[0]["id"] == r["id"] and cel[0]["cout"] == 120.0, cel
# 20 nov 2026 (« ou sont tous mes cartes ?! ») : un collectionneur aussi : l'achat arrive dans « Achetees » (la Reserve),
# et les copies deja rangees dans la Collection par l'ancienne version y reviennent, une seule fois
c = a._db(); c.execute("INSERT INTO achats_ebay (item_id, n, titre, cout, devise, date) VALUES (?,?,?,?,?,?)",
                       ("333", 0, "2023-24 Upper Deck Young Guns Connor Bedard #451", 400.0, "CAD", "2026-11-03")); c.commit(); c.close()
a.reglages_sauver({"mode": "acheteur"})
a.achats_ajouter_auto()
L = a.inventaire_liste({"dispo": 1}); L = L if isinstance(L, list) else L.get("cartes")
bed = [x for x in L if "Bedard" in x["titre"]]
assert [x["emplacement"] for x in bed] == ["Réserve"], bed
assert any("Bedard" in x["titre"] for x in a.achetees_tableau()["cartes"])
c = a._db(); c.execute("UPDATE cartes SET emplacement='Collection' WHERE id=?", (bed[0]["id"],)); c.commit(); c.close()
a.reglages_sauver({"auto_coll_corrige": False}); a.achats_ajouter_auto()
L = a.inventaire_liste({"dispo": 1}); L = L if isinstance(L, list) else L.get("cartes")
assert [x["emplacement"] for x in L if "Bedard" in x["titre"]] == ["Réserve"]
c = a._db(); c.execute("UPDATE cartes SET emplacement='Collection' WHERE id=?", (bed[0]["id"],)); c.commit(); c.close()
a.achats_ajouter_auto()                                   # rangee ensuite par la personne : on n'y touche plus
L = a.inventaire_liste({"dispo": 1}); L = L if isinstance(L, list) else L.get("cartes")
assert [x["emplacement"] for x in L if "Bedard" in x["titre"]] == ["Collection"]
# 20 nov 2026 (« c'est pas une carte, c'est un cadre signe ») : un objet signe, une boite scellee : jamais tout seuls dans les cartes ;
# un objet deja entre tout seul (version d'avant) ressort une fois
c = a._db()
c.execute("INSERT INTO achats_ebay (item_id, n, titre, cout, devise, date) VALUES (?,?,?,?,?,?)",
          ("444", 0, "Shayne Corson Signed Autographed 8x10 Photo Framed Montreal Canadiens", 150.0, "CAD", "2026-11-04"))
c.execute("INSERT INTO achats_ebay (item_id, n, titre, cout, devise, date) VALUES (?,?,?,?,?,?)",
          ("555", 0, "2024-25 Upper Deck Series 1 Hobby Box", 160.0, "CAD", "2026-11-04"))
c.commit(); c.close()
a.achats_ajouter_auto()
L = a.inventaire_liste({}); L = L if isinstance(L, list) else L.get("cartes")
assert not [x for x in L if "Corson" in x["titre"] or "Hobby Box" in x["titre"]], [x["titre"] for x in L]
r_ = a.achat_vers_inventaire("444", 0)                     # l'ancienne version l'aurait ajoute tout seul
assert r_.get("ok")
a.reglages_sauver({"non_cartes_retires": False}); a.achats_ajouter_auto()
L = a.inventaire_liste({}); L = L if isinstance(L, list) else L.get("cartes")
assert not [x for x in L if "Corson" in x["titre"]], [x["titre"] for x in L]
# la 1re synchro : 2 ans de ventes, une seule fois
import ebay_compte
vus = []
ebay_compte.annonces_actives = lambda *x, **k: []
ebay_compte.commandes = lambda j=90: vus.append(j) or []
ebay_compte.ventes_trading = lambda *x, **k: []
ebay_compte.achats = lambda j=90: []
ebay_compte.noter_synchro = lambda b: None
a.ebay_synchroniser(90); a.ebay_synchroniser(90)
assert vus[:2] == [729, 90], vus
print("OK test_achats_auto")
