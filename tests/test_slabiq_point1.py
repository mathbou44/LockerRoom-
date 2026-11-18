"""18 nov 2026 (le point 1 « juste ») : les questions de SlabIQ ont une confiance, un impact et des preuves ; la plus utile
d'abord ; les reponses sont gardees (taux d'erreur) et apprennent a la confiance ; au plus 10 questions par semaine."""
import os, sys, tempfile
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import validation_iq as v
import slabiq_expert as e

J = lambda nom, l, mk, cr, st, n: {"nom": nom, "lettre": l, "marche": mk, "crans": cr, "stable": st, "n": n, "source": "ventes",
                                   "ex": [{"titre": nom + " Young Guns", "prix": 12.0, "le": "2026-11-01"}]}
m = {"joueurs": [J("Gros Ecart", "D", "B+", 4, True, 30), J("Petit Doute", "C", "B", 1, True, 400),
                 J("Mince", "C", "B", 2, False, 9)] + [J(f"Joueur {i}", "C", "B", 1, True, 50 + i) for i in range(15)],
     "sortes": [{"raison": "patch", "lettre": "B", "marche": "D", "crans": -3, "stable": True, "n": 900, "prime": 0.6, "ex": []}]}
auto, _, Q = v.decider(m)
q = next(x for x in Q if x["nom"] == "Petit Doute")
assert 0 < q["confiance"] <= 99 and q["impact"] == 400 and q["preuves"]["ex"] and q["preuves"]["n"] == 400
assert next(x for x in Q if x["nom"] == "Mince")["confiance"] < next(x for x in Q if x["nom"] == "Joueur 14")["confiance"]  # peu de ventes, instable
assert Q[0]["nom"] == "patch"                                        # l'urgente d'abord
pr = [x["priorite"] for x in Q[1:]]
assert pr == sorted(pr, reverse=True)                                # puis la plus utile (impact x confiance)
# les reponses : gardees, taux d'erreur, et la confiance apprend
d = e.lire(); d["questions_marche"] = Q; e.ecrire(d)
c0 = v.confiance(100, True, "joueur", e.lire())
e.coter("Petit Doute", "B")                                          # l'expert donne raison au marche : SlabIQ avait tort
e.coter("Joueur 3", "B")
s = e.suivi()
assert s["reponses"] == 2 and s["erreur"] == 1.0 and s["marche_juste"] == 1.0
assert v.confiance(100, True, "joueur", e.lire()) > c0              # l'expert suit le marche : plus confiant la prochaine fois
e.coter("Joueur 4", "C"); e.coter("Joueur 5", "C"); e.coter("Joueur 6", "C"); e.coter("Joueur 7", "C")
assert e.suivi()["erreur"] < 1.0
# au plus 10 questions par semaine
from lockerroom import Api
a = Api.__new__(Api)
a._est_admin = lambda reel=False: True
r = a.slabiq_questions(40)
assert r["ok"] and r["n"] <= 10 and r["suivi"]["semaine"] <= 10, r["n"]
n0 = r["n"]
e.coter(r["questions"][0]["nom"], "B") if r["questions"][0].get("type") != "sorte" else e.coter_sorte(r["questions"][0]["nom"], "B")
assert a.slabiq_questions(40)["n"] == n0 - 1                         # une question repondue n'est pas remplacee cette semaine
print("SLABIQ POINT 1 OK")
