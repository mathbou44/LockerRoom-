"""14 nov 2026 (Mathieu : « un onglet pour les cartes achetees : le score SlabIQ en pastille avec les photos de l'annonce, le
prix paye et propose pour le profit ; savoir quand les mettre : 3 mois minimum apres l'achat, et surtout si le score SlabIQ est
haut ») : achetees_tableau. Aucun reseau."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
from datetime import datetime, timedelta
import lockerroom, ebay_compte, score_slab, vendues

ebay_compte.statut = lambda *a, **k: {"connecte": False}
api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "t.db"))
api._TAUX.update(c={"usd": 0.72, "lu": 9e12}, lu=9e12)
j = lambda n: (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d")
api.couts_depuis_achats([
    {"item_id": "1", "titre": "2025-26 Upper Deck Young Guns Ivan Demidov #201 RC", "quantite": 1, "cout_total": 160.0, "devise": "CAD", "date": j(120)},
    {"item_id": "2", "titre": "2023-24 Upper Deck Young Guns Connor Bedard #201", "quantite": 1, "cout_total": 380.0, "devise": "CAD", "date": j(100)},
    {"item_id": "3", "titre": "2022-23 Upper Deck Young Guns Matt Boldy #219", "quantite": 1, "cout_total": 40.0, "devise": "CAD", "date": j(20)},
    {"item_id": "4", "titre": "2024-25 Upper Deck Young Guns Joe Ordinaire #240", "quantite": 1, "cout_total": 12.0, "devise": "CAD", "date": j(95)}])
c = api._db(); api._achats_table(c); c.execute("UPDATE achats_ebay SET photo='https://i.ebayimg.com/x1.jpg' WHERE item_id='1'"); c.commit(); c.close()
# la Bedard est dans l'inventaire (en stock) ; la Boldy aussi mais deja SUR eBay ; une carte de collection ; une sans cout
b = api.achat_vers_inventaire("2", 0)
bo = api.achat_vers_inventaire("3", 0)
c = api._db(); c.execute("UPDATE cartes SET statut='Listée', item_number='555' WHERE id=?", (bo["id"],)); c.commit(); c.close()
api.carte_sauver({"titre": "2023-24 Upper Deck Young Guns Logan Cooley #222", "statut": "En stock", "emplacement": "Collection", "cout": 50})
api.carte_sauver({"titre": "Une carte trouvee", "statut": "En stock"})
m = api.carte_sauver({"titre": "2024-25 Upper Deck Young Guns Macklin Celebrini #201", "statut": "En stock", "cout": 300, "prix_demande": 450})

# les scores : forts pour Demidov et Celebrini, moyen ailleurs (on ne depend pas du modele)
def lot(items):
    for x in items:
        t = x.get("titre") or ""
        x["score"] = 88 if "Demidov" in t else 84 if "Celebrini" in t else 60
        x["pastilles_j"] = ["en_feu"] if "Bedard" in t else []
    return items
score_slab.annoter_lot = lot
vendues.memes_cache = lambda t, **k: {"mediane": 300.0, "nb": 6} if "Demidov" in t else {"mediane": None, "nb": 0}

r = api.achetees_tableau()
assert r["ok"], r
L = {x["titre"][:40]: x for x in r["cartes"]}
titres = [x["titre"] for x in r["cartes"]]
assert not any("Boldy" in t for t in titres), "deja sur eBay : pas dans les achetees"
assert not any("Cooley" in t for t in titres) and not any("trouvee" in t for t in titres), "collection / sans cout : non"
dem = next(x for x in r["cartes"] if "Demidov" in x["titre"])
bed = next(x for x in r["cartes"] if "Bedard" in x["titre"])
cel = next(x for x in r["cartes"] if "Celebrini" in x["titre"])
joe = next(x for x in r["cartes"] if "Ordinaire" in x["titre"])
# Demidov : achat eBay pas encore ajoute, photo de l'annonce, 120 jours, score 88 -> maintenant ; prix des ventes, profit
assert dem["a_ajouter"] and dem["photo"] == "https://i.ebayimg.com/x1.jpg" and dem["jours"] == 120 and dem["quand"] == "maintenant", dem
assert dem["propose"] == 300.0 and dem["source_prix"] == "ventes" and dem["profit"] == round(lockerroom._net_rev(300.0) - 160.0, 2), dem
# Bedard : dans l'inventaire (carte_id), en feu -> maintenant ; pas de prix connu
assert bed["carte_id"] == b["id"] and bed["quand"] == "maintenant" and bed["propose"] is None and "en_feu" in bed["pastilles"], bed
# Celebrini : entree aujourd'hui -> attendre 90 jours, son prix a lui ; forte demande notee
assert cel["quand"] == "attendre_3mois" and cel["jours_restants"] == 90 and cel["fort"] and cel["propose"] == 450 and cel["source_prix"] == "ton prix", cel
# Joe : 95 jours, score 60 -> prete
assert joe["quand"] == "prete", joe
# l'ordre : maintenant (meilleur score d'abord), prete, puis l'attente
assert [x["quand"] for x in r["cartes"]] == ["maintenant", "maintenant", "prete", "attendre_3mois"], [x["quand"] for x in r["cartes"]]
assert r["cartes"][0] is not None and r["cartes"][0]["titre"].find("Demidov") >= 0
s = r["resume"]
assert s["n"] == 4 and s["maintenant"] == 2 and s["pretes"] == 3 and s["a_ajouter"] == 2 and s["paye"] == 160 + 380 + 12 + 300, s
print("ok achetees")

# un bon joueur EN CREUX, pret : attendre
score_slab.annoter_lot = lambda items: [x.update(score=55, pastilles_j=["en_creux"]) or x for x in items]
r = api.achetees_tableau()
assert next(x for x in r["cartes"] if "Ordinaire" in x["titre"])["quand"] == "attendre_creux"

# hors admin (comps fermes) : pas de prix tire des ventes
lockerroom.comps_permis = lambda *a, **k: False
score_slab.annoter_lot = lot
r = api.achetees_tableau()
dem = next(x for x in r["cartes"] if "Demidov" in x["titre"])
assert dem["propose"] is None and dem["profit"] is None, dem
assert next(x for x in r["cartes"] if "Celebrini" in x["titre"])["propose"] == 450
print("ACHETEES OK")
