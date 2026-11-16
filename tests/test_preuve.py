"""16 nov 2026 : la preuve en direct : un jour fige une seule fois, enchaine, toute modification apres coup detectee ; la
page publique montre les empreintes le jour meme et les fichiers seulement apres 30 jours."""
import gzip
import json
import os
import sys
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
os.environ["LR_OTS"] = "0"
os.environ["LR_CALME_DEMARRAGE_S"] = "99999"
os.environ["LR_RECHAUFFER_S"] = "99999"
import preuve  # noqa: E402

vieux = date.today() - timedelta(days=40)
e1 = preuve.figer(vieux, {"jour": vieux.isoformat(), "marche": [{"t": "m", "j": "A", "g": "raw", "prix": 10, "etat": "creux"}], "radar": []})
assert e1 and e1["n_marche"] == 1
assert preuve.figer(vieux, {"marche": [], "radar": []}) is None                     # jamais deux fois le meme jour
hier = date.today() - timedelta(days=1)
preuve.figer(hier, {"jour": hier.isoformat(), "marche": [], "radar": [{"t": "r", "id": "1", "titre": "x"}]})
assert preuve.verifier()["ok"]
pub = preuve.public()
assert pub["chaine"][0]["fichier"] is True and pub["chaine"][1]["fichier"] is False   # le vieux jour est public, pas hier

import server  # noqa: E402
c = server.app.test_client()
r = c.get("/preuve")
assert r.status_code == 200 and b"SHA-256" in r.data and e1["sha256"][:16].encode() in r.data
assert c.get(f"/preuve/{vieux.isoformat()}.json").status_code == 200
assert c.get(f"/preuve/{hier.isoformat()}.json").status_code == 404                 # pas avant 30 jours
assert c.get("/preuve/../server.py.json").status_code == 404
assert c.get("/preuve/chaine.json").get_json()[0]["sha256"] == e1["sha256"]

# un vieux jour modifie apres coup : detecte
p = os.path.join(preuve.dossier(), vieux.isoformat() + ".json.gz")
doc = json.loads(gzip.decompress(open(p, "rb").read()))
doc["marche"][0]["prix"] = 9
open(p, "wb").write(gzip.compress(preuve.canonique(doc), mtime=0))
v = preuve.verifier()
assert not v["ok"] and any("modifi" in x for x in v["erreurs"]), v
print("PREUVE OK")
