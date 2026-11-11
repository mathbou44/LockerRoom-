"""11 nov 2026 (Mathieu : « Canada choisi mais une carte expediee des Etats-Unis : douanes, tarifs ») : le Radar ne garde que
les cartes expediees des pays choisis (une annonce sans pays connu reste)."""
import os, sys, tempfile
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lockerroom
a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
r = {"deals": [{"item_id": "1", "lieu": "US"}, {"item_id": "2", "lieu": "CA"}], "petits": [{"item_id": "3", "lieu": ""}],
     "pour_toi": [{"joueur": "X", "annonces": [{"item_id": "4", "lieu": "US"}]}, {"joueur": "Y", "annonces": [{"item_id": "5", "lieu": "CA"}]}]}
assert a._provenance() == ["CA", "US"] and a._filtrer_provenance(r) is r          # les deux : rien ne change
a.reglages_sauver({"provenance": ["CA"]})
f = a._filtrer_provenance(r)
assert [x["item_id"] for x in f["deals"]] == ["2"] and [x["item_id"] for x in f["petits"]] == ["3"], f
assert [g["joueur"] for g in f["pour_toi"]] == ["Y"], f["pour_toi"]
a.reglages_sauver({"provenance": []})
assert a._provenance() == ["CA", "US"]                                            # jamais aucun pays
print("PROVENANCE OK")
