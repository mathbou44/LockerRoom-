"""20 nov 2026 (Mathieu : « en Platine, je devrais voir si ma carte est bien pricee avec les comps ; une Tua Tagovailoa a 120 $
qui en vaut 40 ») : chaque heure, les cartes pas vendues passent par leurs comps ; le resultat est garde a part de la valeur
(comps_valeur) et lu par l'inventaire (admin et Platine) ; le public ne le voit jamais."""
import os, sys, tempfile
from datetime import date, timedelta
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom, vendues

J = lambda n: (date.today() - timedelta(days=n)).isoformat()
T = "2020 Panini Prizm Tua Tagovailoa Rookie #325"
vendues.memes_annonce = lambda t, q=None, n=24, fond=False: {"ventes": [{"titre": T, "prix": p, "le": J(d)} for p, d in ((38, 3), (41, 6), (40, 9), (43, 12), (39, 15))]}
a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
cid = a.carte_sauver({"titre": T, "joueur": "Tua Tagovailoa", "annee": "2020", "marque": "Panini", "set_nom": "Prizm", "numero": "325",
                      "prix_demande": 120, "valeur": 120, "statut": "En stock", "sport": "football"})
cid = cid.get("id") if isinstance(cid, dict) else cid
assert a.comps_inventaire() == 1
L = a.inventaire_liste({}); L = L if isinstance(L, list) else L.get("cartes")
c = [x for x in L if x["id"] == cid][0]
assert c["comps_valeur"] and 35 <= c["comps_valeur"] <= 45 and c["comps_n"] == 5, c
assert a.comps_inventaire() == 0                                    # deja analysee cette semaine
# le public (Pro, Gratuit) : jamais
lockerroom.comps_permis = lambda *a_, **k: False
L = a.inventaire_liste({}); L = L if isinstance(L, list) else L.get("cartes")
assert "comps_valeur" not in [x for x in L if x["id"] == cid][0]
assert a.comps_inventaire() == 0
print("OK test_comps_inventaire")
