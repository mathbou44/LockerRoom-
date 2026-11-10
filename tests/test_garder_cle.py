"""9 nov 2026 (le lot « Server unreachable » quand on quitte l'app 2 s) : l'app refait l'envoi ; avec la meme cle, la carte
n'est jamais creee en double."""
import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom
api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "t.db"))
d = {"carte": {"joueur": "Test"}, "titre": "2024 Test Card", "prix": 10, "photos": [], "cle": "abc12345xyz"}
r1 = api.carte_garder(dict(d))
r2 = api.carte_garder(dict(d))
assert r1["ok"] and r2["ok"] and r1["id"] == r2["id"] and r2.get("deja"), (r1, r2)
r3 = api.carte_garder({**d, "cle": "autre98765"})
assert r3["id"] != r1["id"]
r4 = api.carte_garder({**d, "cle": "x"})               # cle invalide : ignoree (pas d'erreur)
assert r4["ok"] and r4["id"] not in (r1["id"], r3["id"])
print("OK garder cle")
# 9 nov 2026 : « À finir » : preparee pour la vente (pas la collection), pas encore sur eBay ; retirable
l = api.inventaire_liste({"dispo": 1, "a_finir": 1})
l = l if isinstance(l, list) else l.get("cartes", [])
assert {r1["id"], r3["id"], r4["id"]} <= {c["id"] for c in l}, [c["id"] for c in l]
rc = api.carte_garder({"carte": {"joueur": "Coll", "emplacement": "Collection"}, "titre": "Collection card", "photos": []})
l = api.inventaire_liste({"dispo": 1, "a_finir": 1})
l = l if isinstance(l, list) else l.get("cartes", [])
assert rc["id"] not in {c["id"] for c in l}
api.cartes_a_finir_retirer([r1["id"]])
l = api.inventaire_liste({"dispo": 1, "a_finir": 1})
l = l if isinstance(l, list) else l.get("cartes", [])
assert r1["id"] not in {c["id"] for c in l}
print("OK a finir")
