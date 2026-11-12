"""13 nov 2026 (la Caufield OPC Platinum Rookie Auto Emerald Surge 1/10 PSA 8 « doit se retrouver dans nos deals ») : une
carte rare gradee sans vente de SA note : les ventes des autres notes et parallels sont ramenees a sa note et sa rarete."""
import os, sys, tempfile
from datetime import date, timedelta
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import deals
d = lambda k: (date.today() - timedelta(days=k)).isoformat()
V = [{"titre": "2021-22 O-Pee-Chee Platinum Cole Caufield Rookie Auto Violet Pixels /149 PSA 10", "prix": 180, "le": d(20), "url": "u1"},
     {"titre": "2021-22 OPC Platinum Cole Caufield Rookie Auto Rainbow Black /25 PSA 9", "prix": 400, "le": d(40), "url": "u2"},
     {"titre": "2021-22 O-Pee-Chee Platinum Cole Caufield Rookie Auto Sunset /50", "prix": 300, "le": d(30), "url": "u3"},
     {"titre": "2021-22 O-Pee-Chee Platinum Cole Caufield Rookie Auto PSA 8", "prix": 90, "le": d(10), "url": "u4"}]
r = deals.valeur_approx({"titre": "2021-22 O-Pee-Chee Platinum Cole Caufield Rookie Auto Emerald Surge 1/10 PSA 8"}, V)
assert r and r[1] == "approx" and 150 < r[0] < 400, r
assert any("PSA 10" in (v.get("note") or "") for v in r[3])
# une PSA 10 vaut plus qu'une PSA 8 de la meme carte (memes ventes)
r10 = deals.valeur_approx({"titre": "2021-22 O-Pee-Chee Platinum Cole Caufield Rookie Auto Emerald Surge 1/10 PSA 10"}, V)
assert r10 and r10[0] > r[0], (r10, r)
# la recherche large prend toutes les notes
import cartes_match
c = deals.cible_large(cartes_match.cible_titre("2021-22 O-Pee-Chee Platinum Cole Caufield Rookie Auto Emerald Surge 1/10 PSA 8"))
assert not c.get("grade") and not c.get("veut_grade")
print("APPROX NOTES OK", r[0], r10[0])
