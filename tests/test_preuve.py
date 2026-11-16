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

# 16 nov 2026 : les autres cartes du Radar (autos, patchs...) : la valeur plus tard vient de notre archive de ventes
import base_ventes  # noqa: E402
d = date.today() - timedelta(days=110)
T = "2023-24 Upper Deck SP Authentic Future Watch Auto Connor Bedard #151 /999"
preuve.figer(d, {"jour": d.isoformat(), "marche": [], "radar": [
    {"t": "r", "id": "A1", "titre": T, "j": "Connor Bedard", "g": None, "prix": 100.0, "rabais": 25, "etat": "creux"},
    {"t": "r", "id": "A2", "titre": T, "j": "Connor Bedard", "g": None, "prix": 160.0, "rabais": 5, "etat": "flambee"}]})
c = base_ventes._cx()
for h in (30, 60, 90):
    for k in range(3):
        le = (d + timedelta(days=h + k - 1)).isoformat()
        c.execute("INSERT OR IGNORE INTO ventes (q, cle, titre, prix, le) VALUES (?,?,?,?,?)", ("bedard future watch auto", f"{h}-{k}", T, 130.0, le))
c.commit(); c.close()
r = preuve.resultats()
ph = r["par_horizon"]
assert ph["30"]["autres"]["n"] == 2 and ph["30"]["autres_avec"]["mediane_pct"] == 30.0 and ph["30"]["autres_attendre"]["mediane_pct"] < 0, ph["30"]
assert ph["90"]["autres_avec"]["vaut_plus_pct"] == 100
# l'echantillon a re-mesurer : choisi par une empreinte (pas a la main), et un plafond de recherches par jour
assert len(preuve._suivis()) >= 1
appels = []
import vendues  # noqa: E402
vendues.rechercher = lambda q, fond=True, usage=None: appels.append(q) or {"ventes": []}
n1 = preuve.rechercher_suivis(maxi=2)
n2 = preuve.rechercher_suivis(maxi=2)
assert n1 <= 2 and n2 == 0, (n1, n2)                     # le plafond est par jour
print("PREUVE AUTRES OK")
