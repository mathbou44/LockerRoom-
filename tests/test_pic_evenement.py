"""14 nov 2026 (Mathieu : « integre les evenements dans SlabIQ si ca aide ») : etude sur nos ventes -> un petit pic de
visites ne compte plus, un gros pic oui, un gros pic le jour d'un exploit encore plus."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import indice_joueurs as ij
ij.actu = lambda jours=7: []


def indice(v3, feu=False):
    base = {"Pic Joueur": {"nhl": {"actif": True, "equipe": "BOS", "saisons": 4, "l5": 2}, "wiki": {"v60": 6000, "v20": 2000, "v3": v3}}}
    for i in range(20):
        base[f"Joueur {chr(65 + i)}"] = {"nhl": {"actif": True, "equipe": "BOS", "saisons": 4, "l5": i % 4}, "wiki": {"v60": 500 + i * 10, "v20": 160, "v3": 30}}
    I = ij.calculer({"joueurs": {}}, base, lambda n: 1)
    return I["Pic Joueur"]


calme, petit, gros, enorme = indice(250), indice(571), indice(933), indice(2100)     # pic (3 jours) ~0,8, 2, 3,5, 10
assert petit["indice"] - calme["indice"] < 2, (calme, petit)               # x2 : plus de bonus (avant : +4)
assert 3 <= gros["indice"] - calme["indice"] <= 6 and "buzz" in gros["pastilles"], (calme, gros)
assert enorme["indice"] - calme["indice"] >= 7, (calme, enorme)
print("PIC OK", calme["indice"], petit["indice"], gros["indice"], enorme["indice"])
