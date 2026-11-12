"""12 nov 2026 (Mathieu : « un joueur en pente descendante n'est pas un deal ; il faut des joueurs stables ou qui montent, ou
des bons joueurs en slump ») : le Score SlabIQ et le sens de chaque deal (admin) ; les deals a risque passent apres."""
import os, sys, tempfile, json
from datetime import date, timedelta
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom, indice_joueurs, quoi_de_neuf, slabiq_test
I = {"Joe Descente": {"indice": 40, "pastilles": []}, "Bon Creux": {"indice": 75, "pastilles": ["en_creux", "occasion"]},
     "Feu Vif": {"indice": 88, "pastilles": ["en_feu"]}, "Prev Bas": {"indice": 60, "pastilles": []}, "Calme Plat": {"indice": 55, "pastilles": []}}
indice_joueurs._ecrire({"joueurs": {}, "indice": I, "le": 0})
quoi_de_neuf.hist_noter({"Joe Descente": {"indice": 52}, "Calme Plat": {"indice": 54}}, date.today() - timedelta(days=30))
with open(os.path.join(comptes.DONNEES, "slabiq_journal.json"), "w") as f:
    json.dump({"alertes": [], "previsions": {"le": "2026-11-09", "joueurs": {"Prev Bas": ["baisse", 0.71, 0.04], "Calme Plat": ["baisse", 0.52, 0.6]}}}, f)
A = lockerroom.Api
r = {n: A._iq_un(n, I) for n in I}
assert r["Joe Descente"]["sens"] == "baisse" and r["Joe Descente"]["risque"] and r["Joe Descente"]["pq"] == "indice_baisse" and r["Joe Descente"]["ecart_28j"] == -12
assert r["Bon Creux"]["sens"] == "creux" and not r["Bon Creux"]["risque"]
assert r["Feu Vif"]["sens"] == "hausse" and r["Feu Vif"]["pq"] == "feu"
assert r["Prev Bas"]["sens"] == "baisse" and r["Prev Bas"]["pq"] == "prev_baisse"
assert r["Calme Plat"]["sens"] == "stable", r["Calme Plat"]          # une prevision peu sure ne compte pas
assert slabiq_test.prevision("prev bas")["confiance"] == 0.71
items = [{"joueur_n": "JOE DESCENTE"}, {"joueur": "Feu Vif"}, {"joueur_n": "Inconnu Total"}]
lockerroom.Api()._iq_deals(items)
assert items[0]["iq"]["s"] == 40 and items[1]["iq"]["sens"] == "hausse" and "iq" not in items[2]
print("IQ DEALS OK", {n: (v["s"], v["sens"]) for n, v in r.items()})
