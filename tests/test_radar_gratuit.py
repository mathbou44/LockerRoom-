"""13 nov 2026 (Mathieu : « limiter le Radar en gratuit ; le gratuit doit accrocher et ne pas laisser le choix d'aller Pro ») :
6 cartes visibles (la meilleure + des ordinaires) ; les meilleures verrouillees : score et photo seulement."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LR_DONNEES"] = tempfile.mkdtemp()
import lockerroom
api = lockerroom.Api()
A = lambda i, sc: {"item_id": str(1000 + i), "titre": f"Carte {i}", "total": 50 + i, "url": f"https://ebay.ca/itm/{i}", "photo": f"p{i}", "score": sc, "vendeur": "v"}
r = {"ok": True, "deals": [A(0, 95), A(1, 90)], "pour_toi": [{"joueur": "X", "annonces": [A(2, 88), A(3, 60), A(4, 55), A(0, 95)]}],
     "chauds": [{"joueur": "Y", "annonces": [A(5, 80), A(6, 50), A(7, 45), A(8, 40), A(9, 30)]}], "petits": [A(10, 20)]}
g = api._radar_gratuit(r)
vis = [x for x in g["deals"] + g["petits"] + [y for k in ("pour_toi", "chauds") for gg in g[k] for y in gg["annonces"]] if not x.get("verrou")]
ver = [x for x in g["deals"] + g["petits"] + [y for k in ("pour_toi", "chauds") for gg in g[k] for y in gg["annonces"]] if x.get("verrou")]
ids_vis = {x["item_id"] for x in vis}
assert "1000" in ids_vis and len(ids_vis) == 6, ids_vis                       # la meilleure + 5 ordinaires (< 75)
assert all((x.get("score") or 0) < 75 for x in vis if x["item_id"] != "1000")
assert {x["score"] for x in ver} >= {90, 88, 80}                              # les meilleures : verrouillees
for x in ver:                                                                 # rien a contourner : ni titre, ni prix, ni lien
    assert not any(k in x for k in ("titre", "total", "url", "vendeur")) and x["item_id"].startswith("L"), x
assert g["gratuit"] == {"trouvees": 11, "visibles": 6, "verrouillees": 5, "meilleures": 4, "seuil": 75}, g["gratuit"]
print("OK radar gratuit")
