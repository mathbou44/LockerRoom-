"""9 nov 2026 (« pourquoi on ne voit toujours pas si la carte est dans le bon range de prix ? ») : sans ventes sures, le
repere = la mediane des memes cartes en vente moins 10 %, 3 annonces et plus, garde sur la carte."""
import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom
import ebay_compte
import vendues
T = "2024-25 Upper Deck Young Guns Luke Evangelista #451"
annonces = [{"item_id": str(100 + i), "titre": T, "prix_cad": p, "port_cad": 2} for i, p in enumerate((18, 20, 22, 25))]
ebay_compte.rechercher = lambda q, **k: list(annonces)
vendues.memes_annonce = lambda t, **k: {"ventes": []}
api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "t.db"))
cid = api.carte_sauver({"titre": T, "joueur": "Luke Evangelista", "annee": "2024-25", "marque": "Upper Deck", "set_nom": "Young Guns",
                        "numero": "451", "prix_demande": 20, "statut": "En stock"})["id"]
r = api.carte_valeur(cid)
assert r["ok"] and not r.get("approx"), r          # 10 nov 2026 (licence eBay §9.5) : coupe par defaut
os.environ["LR_PRIX_ANNONCES"] = "1"
r = api.carte_valeur(cid)
assert r["ok"] and r.get("approx") and r.get("n_annonces") == 4, r
assert 17 <= r["approx"] <= 21, r
l = api.inventaire_liste({"dispo": 1})
l = l if isinstance(l, list) else l.get("cartes", [])
c = [x for x in l if x["id"] == cid][0]
assert c["valeur_annonces"] == r["approx"] and c["valeur_annonces_n"] == 4, c
annonces[:] = annonces[:2]                       # 2 annonces : pas de repere
cid2 = api.carte_sauver({"titre": T + " Exclusives", "joueur": "Luke Evangelista", "prix_demande": 40, "statut": "En stock"})["id"]
assert not api.carte_valeur(cid2).get("approx")
print("OK repere annonces")
