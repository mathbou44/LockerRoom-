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
# 20 nov 2026 (Mathieu : « calculee avec les last comps, ponderation plus elevee aux ventes plus recentes, puis la mediane ») :
# la mediane ponderee par la recence (demi-vie donnee) ; les prix aberrants ecartes d abord
import deals
v = lambda p, d: {"prix": p, "le": J(d)}
assert deals.mediane_recente([v(100, 1), v(100, 2), v(40, 80), v(40, 85), v(40, 88)], demi_vie=30) == 100     # la mediane simple : 40
assert deals.mediane_recente([v(40, 1), v(40, 2), v(100, 80), v(100, 85), v(100, 88)], demi_vie=30) == 40
assert deals.mediane_recente([v(50, 1), v(52, 3), v(1000, 2), v(48, 5)], demi_vie=30) in (48, 50, 52)          # 1 000 $ ecarte
assert deals.mediane_recente([], demi_vie=30) is None
assert deals.demi_vie_comps() > 0
# l'inventaire : une carte vendue 100 $ ces jours-ci, 40 $ il y a 2-3 mois -> la reference suit les ventes recentes
lockerroom.comps_permis = lambda *a_, **k: True
T2 = "2021-22 Upper Deck Series 2 Young Guns Mason McTavish PSA 10 #451"
vendues.memes_annonce = lambda t, q=None, n=24, fond=False: {"ventes": [{"titre": T2, "prix": p, "le": J(d)} for p, d in ((70, 2), (72, 5), (68, 9), (40, 70), (41, 75), (39, 80), (40, 85))]}
c2 = a.carte_sauver({"titre": T2, "joueur": "Mason McTavish", "prix_demande": 70, "statut": "Listée", "grade": "PSA 10"})
c2 = c2.get("id") if isinstance(c2, dict) else c2
a.carte_valeur(c2)
x = [y for y in (lambda L: L if isinstance(L, list) else L.get("cartes"))(a.inventaire_liste({})) if y["id"] == c2][0]
assert 66 <= x["comps_valeur"] <= 74, x["comps_valeur"]                         # la mediane simple (sans poids) : 41
print("OK test_comps_inventaire")
