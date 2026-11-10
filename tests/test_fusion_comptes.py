"""9 nov 2026 (2 comptes : le cell et l'ordi) : relier une connexion d'un autre compte copie ses cartes, leurs photos et
sa watchlist, sans doublon ; une seule fois ; l'ancien compte garde tout."""
import base64
import io
import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
comptes.DOSSIER_COMPTES = os.path.join(comptes.DONNEES, "comptes")
comptes.MULTI = True
import lockerroom
import photos_cartes
import watchlist
from PIL import Image
api = lockerroom.Api()
b = io.BytesIO(); Image.new("RGB", (300, 420), (120, 30, 30)).save(b, "JPEG"); photo = "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()
cell, _ = comptes.trouver_ou_creer("apple-sub-1", "Mathieu Bourassa", "apple")
ordi, _ = comptes.trouver_ou_creer("ebay-user-1", "hallofcardz", "production")
with comptes.utiliser(cell):
    g = api.carte_garder({"carte": {"joueur": "Bedard", "emplacement": "Collection"}, "titre": "2023 Young Guns Bedard", "photos": [photo]})
    ref = api.carte_lire(g["id"])["photo"]
    c = watchlist._cx(api); c.execute("INSERT INTO watchlist (item_id, titre) VALUES ('111', 'Celebrini YG')"); c.commit(); c.close()
with comptes.utiliser(ordi):
    api.carte_sauver({"titre": "Carte de l'ordi", "statut": "En stock"})
    r = api._fusionner_depuis(cell)
    assert r["ok"] and r["cartes"] == 1 and r["watchlist"] == 1, r
    l = api.inventaire_liste({})
    l = l if isinstance(l, list) else l.get("cartes", [])
    titres = {x["titre"] for x in l}
    assert {"2023 Young Guns Bedard", "Carte de l'ordi"} <= titres, titres
    assert photos_cartes.chemin(ref), "la photo a suivi"
    c = watchlist._cx(api); assert c.execute("SELECT COUNT(*) FROM watchlist WHERE item_id='111'").fetchone()[0] == 1; c.close()
    assert api._fusionner_depuis(cell).get("deja")                      # une seule fois
    assert not api._fusionner_depuis(ordi)["ok"]                        # jamais avec soi-meme
with comptes.utiliser(cell):                                            # l'ancien compte garde tout
    l = api.inventaire_liste({}); l = l if isinstance(l, list) else l.get("cartes", [])
    assert any(x["titre"] == "2023 Young Guns Bedard" for x in l)
print("OK fusion comptes")
