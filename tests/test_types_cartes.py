"""12 nov 2026 (Mathieu : « une Dazzler PSA 10 versus une Young Guns PSA 10, ca n'a rien a voir ») : les types de cartes appris
dans nos ventes (la carte contre la carte typique du MEME joueur) ; le classement par joueur ; le score de la carte."""
import os, sys, tempfile, random
from datetime import datetime, timedelta
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import types_cartes as T

assert T.type_de("2021-22 Upper Deck Young Guns Anton Lundell #464 PSA 10") == "young_guns|10"
assert T.type_de("2021 UD YG Anton Lundell RC BGS 9.5") == "young_guns|10"
assert T.type_de("2021-22 SP Authentic Future Watch Auto Anton Lundell /999") == "fw_auto|r"
assert T.type_de("2021-22 SPA FW Autograph Lundell PSA 9") == "fw_auto|9"
assert T.type_de("2021-22 Upper Deck Dazzlers Anton Lundell PSA 10") == "dazzlers|10"
assert T.type_de("2021-22 Young Guns Canvas Lundell C220") == "yg_canvas|r"
assert T.type_de("2021-22 The Cup Rookie Auto Patch RPA Lundell /249") == "cup_rpa|r"
assert T.type_de("2021-22 Premier Rookie Auto Patch Lundell /299") == "premier_auto|r"
assert T.type_de("Lundell Stature Auto /99") == "stature|r"
assert T.nom_type("young_guns|10") == "Young Guns gradée 10" and T.nom_type("dazzlers|r") == "Dazzlers"
print("FAMILLES OK")

# des ventes inventees : pour chaque joueur, une YG gradee 10 vaut 6x sa carte typique, une Dazzler gradee 10 2x, une base 0.5x
random.seed(3)
now = datetime(2026, 11, 14)
V = []
F = {"Young Guns PSA 10": 6.0, "Future Watch Auto": 4.0, "Dazzlers PSA 10": 2.0, "Upper Deck Series 1": 0.4, "Young Guns": 2.5, "MVP Auto": 0.7}
for i in range(30):
    j = f"Joueur Numero{i}"
    base = random.uniform(5, 80)
    for t, f in F.items():
        for _ in range(random.randint(3, 6)):
            le = (now - timedelta(days=random.randint(1, 360))).strftime("%Y-%m-%d")
            V.append((j, f"2022-23 {t} {j}", base * f * random.uniform(0.8, 1.25), le))
d = T.apprendre(V, now)
L = sorted(d["types"].items(), key=lambda kv: -kv[1]["score"])
noms = [t["nom"] for k, t in L]
assert noms.index("Young Guns gradée 10") < noms.index("Future Watch Auto") < noms.index("Dazzlers gradée 10") < noms.index("Upper Deck (base)"), noms
assert d["types"]["young_guns|10"]["prime"] > 2 * d["types"]["dazzlers|10"]["prime"]
assert d["fiabilite"] is None or d["fiabilite"] > 0.5, d["fiabilite"]
assert d["joueurs"]["Joueur Numero3"][0][0] == "young_guns|10"
T.ecrire(d)
dj = T.du_joueur("joueur numero3")
assert dj["source"] == "joueur" and dj["types"][0]["nom"] == "Young Guns gradée 10" and "prime" not in dj["types"][0]
assert "prime" in T.du_joueur("Joueur Numero3", admin=True)["types"][0]
assert T.du_joueur("Personne Inconnu")["source"] == "general"
assert all("prime" not in x for x in T.classement(10))
i = T.info("2023-24 Upper Deck Young Guns Somebody PSA 10")
assert i["rang"] == 1 and i["score"] >= 75, i
m = d["mesure"]
assert m and m["apres"] > m["avant"], m                 # le test avant / apres : les types classent mieux les cartes d'un joueur
print("CLASSEMENT OK", noms[:5], "fiabilite", d["fiabilite"], "mesure", m)

import score_slab
a = score_slab.carte("2023-24 Upper Deck Young Guns Somebody PSA 10")
b = score_slab.carte("2023-24 Upper Deck Dazzlers Somebody PSA 10")
assert a["type"]["nom"] == "Young Guns gradée 10" and a["score"] > b["score"], (a, b)
print("SCORE CARTE OK", a["score"], b["score"])
