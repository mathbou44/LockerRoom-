"""14 nov 2026 (Mathieu : « l'accueil ordi : un graph de trend ou un tableau ») : le tableau des tendances SlabIQ de l'accueil
(top de l'Indice et plus fortes hausses sur 30 jours, avec la serie de l'Indice). Aucun reseau, aucun prix."""
import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
from datetime import date, timedelta
import indice_joueurs, quoi_de_neuf, lockerroom

I = {"Haut Stable": {"indice": 95, "actif": True, "equipe": "EDM", "pastilles": ["legende"]},
     "Monte Vite": {"indice": 80, "actif": True, "equipe": "MTL", "pastilles": ["en_feu"], "semaine": {"pts": 6, "mj": 3}},
     "Descend": {"indice": 40, "actif": True, "equipe": "CBJ", "pastilles": ["echange_baisse"]},
     "Retraite": {"indice": 99, "actif": False, "equipe": None, "pastilles": []}}
indice_joueurs._ecrire({"joueurs": {}, "indice": I, "le": 0})
for k in range(10):
    j = date.today() - timedelta(days=9 - k)
    quoi_de_neuf.hist_noter({"Haut Stable": {"indice": 95}, "Monte Vite": {"indice": 60 + 2 * k}, "Descend": {"indice": 60 - 2 * k}}, j)
api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "t.db"))
r = api.accueil_tendances()
assert r["ok"] and [x["nom"] for x in r["top"]] == ["Haut Stable", "Monte Vite", "Descend"], r["top"]   # les retraites : non
assert [x["nom"] for x in r["hausses"]] == ["Monte Vite"] and r["hausses"][0]["ecart"] == 80 - 60, r["hausses"]
m = r["top"][1]
assert len(m["serie"]) == 10 and m["serie"][0] == 60 and m["pastilles"] == ["en_feu"] and m["semaine"] == {"pts": 6, "mj": 3}
assert r["top"][2]["pastilles"] == ["echange_baisse"] and r["top"][2]["ecart"] < 0
assert "prix" not in json.dumps(r)
print("ACCUEIL TENDANCES OK")
