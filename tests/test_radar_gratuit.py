"""13 nov 2026 (Mathieu : « limiter le Radar en gratuit ; le gratuit doit accrocher et ne pas laisser le choix d'aller Pro ») :
15 cartes visibles (les 3 meilleures + des ordinaires ; 6 avant le 21 nov) ; les meilleures verrouillees : score et photo seulement."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LR_DONNEES"] = tempfile.mkdtemp()
import lockerroom
api = lockerroom.Api()
A = lambda i, sc: {"item_id": str(1000 + i), "titre": f"Carte {i}", "total": 50 + i, "url": f"https://ebay.ca/itm/{i}", "photo": f"p{i}", "score": sc, "vendeur": "v"}
# 21 nov 2026 (Mathieu : « c'est trop peu ») : 15 cartes visibles (ses 3 meilleures + des ordinaires), les autres bonnes verrouillees
r = {"ok": True, "deals": [A(0, 95), A(1, 90)], "pour_toi": [{"joueur": "X", "annonces": [A(2, 88), A(3, 60), A(4, 55), A(0, 95), A(30, 86), A(31, 84)]}],
     "chauds": [{"joueur": "Y", "annonces": [A(5, 80), A(6, 50), A(7, 45), A(8, 40), A(9, 30)] + [A(11 + i, 20 + i) for i in range(12)]}], "petits": [A(10, 20)]}
g = api._radar_gratuit(r)
tout = g["deals"] + g["petits"] + [y for k in ("pour_toi", "chauds") for gg in g[k] for y in gg["annonces"]]
vis = [x for x in tout if not x.get("verrou")]
ver = [x for x in tout if x.get("verrou")]
ids_vis = {x["item_id"] for x in vis}
assert {"1000", "1001", "1002"} <= ids_vis and len(ids_vis) == 15, ids_vis      # les 3 meilleures + 12 ordinaires (< 75)
assert all((x.get("score") or 0) < 75 for x in vis if x["item_id"] not in ("1000", "1001", "1002"))
assert {x["score"] for x in ver} >= {86, 84, 80}                              # les autres bonnes : verrouillees
for x in ver:                                                                 # rien a contourner : ni titre, ni prix, ni lien
    assert not any(k in x for k in ("titre", "total", "url", "vendeur")) and x["item_id"].startswith("L"), x
assert g["gratuit"]["visibles"] == 15 and g["gratuit"]["trouvees"] == 25 and g["gratuit"]["seuil"] == 75 and g["gratuit"]["meilleures"] == 6, g["gratuit"]
# les recherches du Radar en Gratuit : 20 par semaine, puis la limite (dite, jamais un ecran vide sans raison)
import forfaits
assert forfaits.LIMITES["radar_semaine"] == 20 and forfaits.LIMITES["annonces_mois"] == 10
assert forfaits._cle_periode("radar_semaine").count("-S") == 1 and len(forfaits._cle_periode("annonces_mois")) == 7
import inspect
assert 'verifier("radar_semaine")' in inspect.getsource(lockerroom.Api.radar_chercher) and '"limite": True' in inspect.getsource(lockerroom.Api.radar_chercher)
print("OK radar gratuit")
