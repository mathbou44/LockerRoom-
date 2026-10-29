"""30 oct 2026 - mon profil de deals : ce que je collectionne, mes favoris, mon budget, mes vendeurs (python tests/test_profil_deals.py)."""
import os
import sys
import tempfile

os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deals  # noqa: E402
import forfaits  # noqa: E402
import lockerroom  # noqa: E402

a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
D = [{"item_id": "1", "titre": "2025-26 Upper Deck Young Guns Ivan Demidov #451", "total": 40},
     {"item_id": "2", "titre": "1979-80 O-Pee-Chee Wayne Gretzky #18 PSA 7", "total": 900},
     {"item_id": "3", "titre": "2023-24 The Cup Sidney Crosby Auto Patch /25", "total": 300},
     {"item_id": "4", "titre": "2021-22 Upper Deck Nick Suzuki Montreal Canadiens Exclusives /100", "total": 25},
     {"item_id": "5", "titre": "2025-26 SP Authentic Future Watch Auto Demidov /999", "total": 120}]
ids = lambda l: [x["item_id"] for x in l]
assert a._appliquer_profil(D, a._profil_deals()) == D                       # rien de regle : tout
r = a.deals_profil_regler({"collectionne": ["veterans", "legendes"]})
assert ids(a._appliquer_profil(D, a._profil_deals())) == ["2", "3", "4"]   # pas de recrues de l'annee
a.deals_profil_regler({"collectionne": ["hits"]})
assert ids(a._appliquer_profil(D, a._profil_deals())) == ["3", "5"]        # les hits, toutes epoques
a.deals_profil_regler({"collectionne": ["veterans", "hits"]})
assert ids(a._appliquer_profil(D, a._profil_deals())) == ["3"]
a.deals_profil_regler({"collectionne": ["gradees", "legendes"]})
assert ids(a._appliquer_profil(D, a._profil_deals())) == ["2"]
# favoris (joueurs ou equipes) : devant, avec une etoile ; budget par carte
r = a.deals_profil_regler({"collectionne": [], "favoris": "Canadiens, crosby", "prix_min": 20, "prix_max": 500})
assert r["favoris"] == ["Canadiens", "crosby"] and r["prix_max"] == 500.0
l = a._appliquer_profil(D, a._profil_deals())
assert ids(l) == ["3", "4", "1", "5"] and l[0]["favori"] and not l[2].get("favori"), ids(l)
assert a.deals_profil_regler({"prix_min": 600, "prix_max": 100})["prix_min"] == 100.0      # inverses : remis dans l'ordre
# mes vendeurs : Pro, 3 au plus, chasses apres les vendeurs suivis
forfaits.est_pro = lambda: False
r = a.deals_profil_regler({"vendeurs": ["mon.vendeur"]})
assert not r["ok"] and r["pro_requis"] and r["vendeurs"] == []
forfaits.est_pro = lambda: True
r = a.deals_profil_regler({"vendeurs": "@Mon.Vendeur, savage.cards, b, c, d"})
assert r["ok"] and r["vendeurs"] == ["mon.vendeur", "savage.cards", "b"], r
assert deals.vendeurs_perso() == ["mon.vendeur", "b"]                      # savage.cards est deja suivi
assert deals.groupes_chasse()[-1] == ["mon.vendeur", "b"] and deals.groupes_chasse()[0] == ["savage.cards"]
assert a.deals_profil_regler({"vendeurs": []})["vendeurs"] == [] and deals.vendeurs_perso() == []
print("PROFIL DEALS OK")
