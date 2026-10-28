"""28 oct 2026 - « ajouter sa collection sans la mettre sur eBay » : une carte de collection n'est jamais « a lister », et
l'accueil donne UN indice : le joueur de tes cartes en feu (python tests/test_collection.py). Aucun appel reseau."""
import json
import os
import sys
import tempfile
import time

os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
os.environ["LR_NHL"] = "1"
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ICI)
import lockerroom  # noqa: E402
import nhl  # noqa: E402

a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "c.db"))
c1 = a.carte_garder({"carte": {"joueur": "Ivan Demidov", "emplacement": "Collection", "valeur": 120}, "titre": "Demidov YG", "prix": None, "photos": []})
c2 = a.carte_garder({"carte": {"joueur": "Ivan Demidov", "emplacement": "Collection", "valeur": 80}, "titre": "Demidov Canvas", "prix": None, "photos": []})
c3 = a.carte_garder({"carte": {"joueur": "Lane Hutson"}, "titre": "Hutson YG", "prix": 40, "photos": []})
assert all(x["ok"] for x in (c1, c2, c3))
assert [x["id"] for x in a.inventaire_liste({"a_lister": 1})] == [c3["id"]]          # la collection n'est pas « a mettre en ligne »
assert len(a.inventaire_liste({"emplacement": "Collection"})) == 2
d = a.accueil()
lister = [x for x in d["actions"] if x["cle"] == "lister"]
assert lister and lister[0]["n"] == 1, lister
assert d["chaud"] is None and d["collection_n"] == 2
# un joueur de mes cartes en feu
auj = time.strftime("%Y-%m-%d")
with open(os.path.join(os.environ["LOCKERROOM_DONNEES"], "nhl_forme.json"), "w") as f:
    json.dump({"joueurs": {"ivan demidov": {"le": time.time(), "id": "1", "f": {"joueur": "Ivan Demidov", "matchs": 5, "buts": 4, "passes": 5, "points": 9, "dernier": auj}},
                           "connor mcdavid": {"le": time.time(), "id": "2", "f": {"joueur": "Connor McDavid", "matchs": 5, "buts": 6, "passes": 8, "points": 14, "dernier": auj}}}}, f)
d = a.accueil()
assert d["chaud"] == {"joueur": "Ivan Demidov", "points": 9, "matchs": 5, "n": 2}, d["chaud"]     # McDavid est plus chaud, mais pas dans mes cartes
assert [x["joueur"] for x in nhl.chauds()] == ["Connor McDavid", "Ivan Demidov"]
print("COLLECTION OK")
