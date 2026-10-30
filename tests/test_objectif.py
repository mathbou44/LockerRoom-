"""31 oct 2026 (Mathieu : « un inventaire a vendre rapidement et un inventaire de collection ») : le score de desirabilite,
l'objectif des deals (revente / collection) et les deux tableaux de l'inventaire. Aucun reseau."""
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deals  # noqa: E402
import desirabilite  # noqa: E402
import forfaits  # noqa: E402
import lockerroom  # noqa: E402

d1 = desirabilite.score("2022-23 SPx Wayne Gretzky Auto 1/1", valeur=3000)
d2 = desirabilite.score("2024-25 Upper Deck Series 1 Anders Lee #50", valeur=1)
d3 = desirabilite.score("2005-06 SP Authentic Sidney Crosby Future Watch Auto /999", valeur=2500)
assert d1["score"] >= 80 and "1/1" in d1["raisons"] and d2["score"] < 20, (d1, d2)
assert "SP" not in d3["raisons"], d3                                  # « SP Authentic » n'est pas un short print

deals.chasser_si_besoin = lambda *a, **k: False
deals.valide = lambda x: True
forfaits.est_pro = lambda: True
vu = datetime.now(timezone.utc).isoformat(timespec="seconds")
D = lambda i, t, tot, val, n: {"item_id": i, "titre": t, "total": tot, "valeur": val, "ratio": tot / val, "encan": False, "vu_le": vu,
                               "source": "marche", "sport": "hockey", "url": "u", "v": deals.VERSION, "n": n}
deals._ecrire({"deals": [D("rare", "2022-23 SPx Wayne Gretzky Auto 1/1", 900, 3000, 2),
                         D("base", "2024-25 Upper Deck Series 1 Anders Lee #50", 2, 10, 12),
                         D("flip", "2023-24 Upper Deck Young Guns Connor Bedard #201", 60, 150, 20)]})
a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "o.db"))
a._valeur_en_cache = lambda x, calculer=True: None
ids = lambda f: [x["item_id"] for x in a.deals_liste(f)["deals"]]
assert ids({"objectif": "collection"})[0] == "rare" and "base" not in ids({"objectif": "collection"})
rv = ids({"objectif": "revente"})
assert "rare" not in rv and rv[0] == "flip", rv                       # 2 ventes seulement : pas une revente rapide
assert all("desir" in x for x in a.deals_liste({})["deals"])

vieux = (datetime.now() - timedelta(days=90)).isoformat(timespec="seconds")
c = a._db()
c.execute("INSERT INTO cartes (titre, joueur, valeur, prix_demande, emplacement, statut, cree_le) VALUES (?,?,?,?,?,?,?)",
          ("Wayne Gretzky Auto 1/1", "Wayne Gretzky", 3000, None, "Collection", "En stock", vieux))
c.execute("INSERT INTO cartes (titre, joueur, valeur, prix_demande, emplacement, statut, cree_le) VALUES (?,?,?,?,?,?,?)",
          ("Anders Lee base", "Anders Lee", 1, 3, "Réserve", "En stock", vieux))
for k in range(4):
    c.execute("INSERT INTO cartes (titre, statut, cree_le, vendu_le) VALUES (?,?,?,?)",
              ("x", "Vendue", (datetime.now() - timedelta(days=20 + k)).isoformat(), (datetime.now() - timedelta(days=10)).isoformat()))
c.commit()
c.close()
t = a.inventaire_tableaux()
assert t["vente"]["n"] == 1 and t["vente"]["dorment"] == 1 and t["vente"]["delai_median"] in (11, 12), t["vente"]
assert t["collection"]["n"] == 1 and t["collection"]["top"][0]["score"] >= 80, t["collection"]
rare = desirabilite.score("2023-24 Upper Deck Young Guns Connor Bedard #201", valeur=150, ventes=1, jours=400)
courant = desirabilite.score("2023-24 Upper Deck Young Guns Connor Bedard #201", valeur=150, ventes=40)
assert rare["score"] > courant["score"] and any("presque jamais" in r for r in rare["raisons"]), (rare, courant)
print("OK test_objectif")
