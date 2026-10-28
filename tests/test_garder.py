"""Assistant de vente : « Garder dans mon inventaire » + photos de la carte (python tests/test_garder.py). Aucun appel reseau."""
import base64
import json
import os
import sys
import tempfile

os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ICI)
import lockerroom  # noqa: E402
import photos_cartes  # noqa: E402
import annonces  # noqa: E402
import ebay_ecriture  # noqa: E402
import vision  # noqa: E402

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 5000
URL = "data:image/jpeg;base64," + base64.b64encode(JPEG).decode()
a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "g.db"))

r = a.carte_garder({"carte": {"joueur": "Macklin Celebrini", "annee": "2024-25", "marque": "Upper Deck", "parallele": "Young Guns",
                              "statut": "Vendue", "id": 999}, "titre": "2024-25 Upper Deck Young Guns Macklin Celebrini #201 RC",
                    "prix": "149.99", "cout": "40", "photos": [URL, URL, "https://i.ebayimg.com/x.jpg", "javascript:alert(1)"]})
assert r["ok"] and len(r["photos"]) == 3 and r["photos"][2].startswith("https://"), r
c = a.carte_lire(r["id"])
assert c["statut"] == "En stock" and c["prix_demande"] == 149.99 and c["cout"] == 40 and c["photo"] == r["photos"][0], c
refs = json.loads(c["photos"]); assert refs == r["photos"]
f = photos_cartes.chemin(refs[0]); assert f and open(f, "rb").read() == JPEG
# references bidon refusees (pas de sortie du dossier)
assert photos_cartes.chemin("/mes-photos/../g.db") is None and photos_cartes.chemin("/mes-photos/abc.jpg") is None
# mise a jour de la meme carte : pas de doublon, photos deja gardees reutilisees
r2 = a.carte_garder({"cid": r["id"], "carte": {"joueur": "Macklin Celebrini"}, "titre": "x" * 20, "prix": 120, "photos": refs[:1]})
assert r2["id"] == r["id"] and r2["photos"] == refs[:1] and a.carte_lire(r["id"])["prix_demande"] == 120
# publication plus tard : la photo gardee part chez eBay (televersement simule)
vus = []
ebay_ecriture.televerser_photo = lambda chemin, nom: vus.append(chemin) or "https://i.ebayimg.com/ok.jpg"
assert annonces.photos_ebay([refs[0], "https://i.ebayimg.com/y.jpg"]) == ["https://i.ebayimg.com/ok.jpg", "https://i.ebayimg.com/y.jpg"]
assert vus == [f]
# trop lourd -> refuse proprement
big = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff" + b"0" * 4_600_000).decode()
assert not a.carte_garder({"carte": {"joueur": "X"}, "photos": [big]})["ok"]
# supprimer la carte supprime ses photos
a.carte_supprimer(r["id"])
assert not os.path.exists(f)
# vision : coins et qualite des photos nettoyes
p = vision._photos([{"cote": "devant", "coins": [[100, 50], [900, 48], [905, 960], ["98", 955]], "entiere": True, "nette": True},
                    {"cote": "x", "coins": [[1, 2]], "entiere": False, "probleme": "coin coupé en bas à droite"}, {}])
assert p[0]["coins"] == [[100, 50], [900, 48], [905, 960], [98, 955]] and p[0]["entiere"] and p[0]["cote"] == "devant"
assert p[1]["coins"] is None and not p[1]["entiere"] and p[1]["cote"] is None and p[1]["probleme"].startswith("coin")
assert len(p) == 2
print("GARDER OK")
