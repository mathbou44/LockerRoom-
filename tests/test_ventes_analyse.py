"""5 nov 2026 (Mathieu : « une section pour mes solds et une analyse profit ») : revenus, profit (seulement avec cout),
marge, retour, delai, par type / joueur, meilleures ventes et pertes ; et l'achat eBay de la MEME carte propose a la fiche."""
import os, sys, tempfile
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom, ebay_compte

ebay_compte.statut = lambda *a, **k: {"connecte": False}
api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "t.db"))
j = lambda n: (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%dT10:00:00")
ventes = [("Connor Bedard", "PSA 10", 100.0, 250.0, 30.0, 220.0 - 100.0, 40, 5),
          ("Ivan Demidov", "", 80.0, 60.0, 8.0, 52.0 - 80.0, 20, 2),
          ("Macklin Celebrini", "", None, 120.0, 15.0, 105.0, 10, 1),
          ("Connor Bedard", "", 20.0, 45.0, 6.0, 39.0 - 20.0, 300, 200)]
c = api._db()
for jo, g, cout, prix, frais, prof, cree, vendu in ventes:
    c.execute("INSERT INTO cartes (titre, joueur, grade, cout, prix_vendu, frais, profit, statut, cree_le, vendu_le, canal) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (jo + " card", jo, g, cout, prix, frais, prof, "Vendue", j(cree), j(vendu), "eBay"))
c.commit(); c.close()
r = api.ventes_analyse("90")
k = r["kpis"]
assert r["ok"] and k["nb"] == 3 and k["revenus"] == 430.0, k                      # la vente d'il y a 200 jours : hors periode
assert k["profit"] == 120.0 - 28.0 and k["avec_cout"] == 2 and k["sans_cout"] == 1 and k["revenus_sans_cout"] == 120.0, k
assert k["marge"] == round(100 * 92 / 310, 1) and k["roi"] == round(100 * 92 / 180, 1) and k["pertes"] == 1, k
assert k["jours_median"] == 18, k
assert [x["nom"] for x in r["par_type"]] == ["Gradée", "Raw"], r["par_type"]
assert r["meilleures"][0]["joueur"] == "Connor Bedard" and r["pertes"][0]["joueur"] == "Ivan Demidov", r
assert all(v["profit"] is None for v in r["liste"] if v["sans_cout"])
assert api.ventes_analyse("tout")["kpis"]["nb"] == 4
assert sum(m["nb"] for m in api.ventes_analyse("tout")["par_mois"]) >= 3
assert api.ventes_analyse(datetime.now().strftime("%Y-%m"))["ok"]
# la fiche : l'achat de la MEME carte est signale (meme_carte), un autre joueur non
achats = [{"item_id": "9", "titre": "2023-24 Upper Deck Young Guns Connor Bedard #201", "quantite": 1, "cout_total": 380.0, "devise": "CAD", "date": "2026-10-28"},
          {"item_id": "8", "titre": "2025-26 Upper Deck Young Guns Ivan Demidov #201", "quantite": 1, "cout_total": 160.0, "devise": "CAD", "date": "2026-10-20"}]
api.couts_depuis_achats(achats)
cid = api.carte_sauver({"titre": "2023-24 UD Young Guns Connor Bedard #201 RC", "joueur": "Connor Bedard", "statut": "En stock"})["id"]
s = api.achats_carte(cid)
m = {a["item_id"]: a["meme_carte"] for a in s["suggestions"]}
assert m.get("9") is True and m.get("8") is False, s
print("VENTES ANALYSE OK")
