"""19 nov 2026 (Mathieu, la Jack Hughes The Cup Rookie Gear Auto Patch /24 PSA 9 : « pourquoi on la trouve pas ? ») : la
meme carte vendue en BGS 9 passe avant les cartes semblables, ramenee a PSA 9 (BGS = 84 % d'une PSA)."""
import os, sys, tempfile
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import deals, cartes_match

j = lambda n: (date.today() - timedelta(days=n)).isoformat()
a = {"item_id": "1", "titre": "2019-20 Upper Deck The Cup Rookie Gear Auto Patch Jack Hughes RC /24 PSA 9", "total": 356}
cib = cartes_match.cible_titre(a["titre"])
ventes = [{"titre": "2019 UPPER DECK THE CUP #ARG-JH JACK HUGHES ROOKIE GEAR PATCH AUTO RC /24 BGS 9", "prix": 615.0, "le": j(14)},
          # des cartes semblables du meme joueur (autres inserts) : ne passent plus avant LA carte
          {"titre": "2019-20 The Cup Jack Hughes Scripted Swatches Auto Patch /35", "prix": 444.0, "le": j(50)},
          {"titre": "2019-20 The Cup Jack Hughes Limited Logos Auto /50", "prix": 1755.0, "le": j(90)}]
va = deals.valeur_autre_note(a, ventes, cib)
assert va and va[1] == "autre_note" and va[2] == 1, va
assert abs(va[0] - round(615 / 0.84 * 0.80, 2)) < 1, va          # 615 $ en BGS 9 -> PSA 9 (/0,84), une vente : 80 %
assert va[3][0]["note"] == "BGS 9"
v2 = deals.valeur_ou_saison(a, ventes, [], cib=cib)
assert v2 and v2[1] == "autre_note", v2
# la meme note : pas « autre note » (c'est une vraie vente de la carte)
assert deals.valeur_autre_note(a, [dict(ventes[0], titre=ventes[0]["titre"].replace("BGS 9", "PSA 9"))], cib) is None
# un PSA 10 ramene a une 9 (60 %)
v3 = deals.valeur_autre_note(a, [dict(ventes[0], titre=ventes[0]["titre"].replace("BGS 9", "PSA 10"), prix=1000.0)], cib)
assert v3 and abs(v3[0] - 1000 * 0.6 * 0.8) < 1, v3
print("OK test_autre_note")
