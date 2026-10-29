"""29 oct 2026 - « Corriger mes prix » : plusieurs prix d'un geste (python tests/test_prix_lot.py). Aucun appel reseau."""
import os
import sys
import tempfile
import threading

os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes  # noqa: E402
import lockerroom  # noqa: E402

a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
vus, fils = [], set()
def faux_prix(iid, p):
    vus.append((iid, p, comptes._courant.get())); fils.add(threading.get_ident())
    return {"ok": True, "prix": p} if iid != "222" else {"ok": False, "erreur": "Annonce terminée"}
a.ebay_changer_prix = faux_prix
a.annonce_reviser = lambda cid, d: vus.append(("prog", cid, d["prix"])) or {"ok": True}
jeton = comptes._courant.set("compte_test")
r = a.ebay_prix_lot([{"item_number": "111", "prix": "12.499"}, {"item_number": "222", "prix": 9}, {"item_number": "333", "prix": 5, "id": 7, "programmee": True},
                     {"item_number": "", "prix": 3}, "x", {"item_number": "444", "prix": None}])
assert r["ok"] and r["faits"] == 2, r
assert [x["item_number"] for x in r["resultats"]] == ["111", "222", "333"]
assert r["resultats"][1]["erreur"] == "Annonce terminée" and r["resultats"][0]["prix"] == 12.5
assert all(v[2] == "compte_test" for v in vus if v[0] != "prog"), vus          # le compte suit dans chaque fil
assert ("prog", 7, 5.0) in vus
assert a.ebay_prix_lot([])["ok"] is False
comptes._courant.reset(jeton)
print("PRIX LOT OK")
