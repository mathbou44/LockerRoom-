"""20 nov 2026 (docs/GUIDE_ACCROCHE.md) : « Pour bien partir » coche ce qui est VRAIMENT fait (le compte, eBay relie...) ;
le set le plus proche n'est montre que pres du but (50 % et plus, ou 10 cartes ou moins). Aucun reseau."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import lockerroom, ebay_compte, catalogue
ebay_compte.statut = lambda *a, **k: {"connecte": True}
a = lockerroom.Api(os.path.join(os.environ["LOCKERROOM_DONNEES"], "t.db"))
r = a.accueil_progres()
assert r["faites"] == 2 and r["total"] == 5 and [e["k"] for e in r["etapes"] if e["fait"]] == ["compte", "ebay"], r
a.reglages_sauver({"budget_mois": 200, "deals_profil": {"favoris": ["Connor Bedard"]}})
assert a.accueil_progres()["faites"] == 4
# un petit set presque complet : montre ; un gros set loin du but : pas montre
pid = "2025-26-upper-deck-star-rookies-box-set"
prod = catalogue.charger(pid)
assert prod, "produit de test"
se = next(s["nom"] for s in prod["sous_ensembles"] if 5 <= len({c["numero"] for c in prod["cartes"] if c["sous_ensemble"] == s["nom"]}) <= 60)
cartes = [c for c in prod["cartes"] if c["sous_ensemble"] == se]
tot = len({c["numero"] for c in cartes})
assert a.accueil_progres()["set"] is None
for c in cartes[:max(3, tot - 2)]:
    a.carte_sauver({"titre": f"{prod['nom']} {se} {c['joueur']} #{c['numero']}", "joueur": c["joueur"], "annee": prod["saison"],
                    "marque": "Upper Deck", "set_nom": "Star Rookies Box Set", "parallele": se if se != "Base Set" else None,
                    "numero": c["numero"], "emplacement": "Collection", "statut": "En stock"})
lockerroom.Api._PROGRES.clear()
r = a.accueil_progres()
assert r["faites"] == 5, r
s = r["set"]
if s:                                             # le rapprochement carte -> checklist depend du titre ; s'il se fait : pres du but
    assert s["manque"] <= 10 or s["pct"] >= 50, s
a.depart_cacher()
assert a.accueil_progres()["cache"]
print("OK test_progres", s and (s["sous"], s["possedees"], s["total"]))
