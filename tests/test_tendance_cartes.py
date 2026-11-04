"""3 nov 2026 (Mathieu : « +5 % depuis la semaine passee, +10 % depuis le mois passe ») : la variation du prix de chaque
carte, sans credit SoldComps : les ventes deja lues (3 de chaque cote au moins), sinon l'historique de sa valeur."""
import os, sys, tempfile
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom, tendance_cartes, base_ventes, cartes_match

M = datetime(2026, 11, 3)
J = lambda n: (M - timedelta(days=n)).strftime("%Y-%m-%d")
T = "2025-26 Upper Deck Young Guns Ivan Demidov #451"
# 30 j : 4 ventes recentes ~110, 4 ventes il y a 30-60 j ~100 -> +10 % ; 7 j : 3 ventes cette semaine ~115 vs ~100 avant
v = [{"titre": T, "prix": p, "le": J(d), "url": f"https://www.ebay.com/itm/1000000{i:03d}"} for i, (p, d) in enumerate(
    [(115, 1), (114, 3), (116, 5), (105, 12), (103, 20), (101, 35), (99, 40), (100, 45), (102, 50)])]
q = cartes_match.requete_ebay(cartes_match.cible_titre(T))
base_ventes.noter(q, v)
t, n = tendance_cartes.par_ventes(tendance_cartes.ventes_connues(T), M)
assert t["t30"] is not None and 10 <= t["t30"] <= 16 and t["t7"] is not None and t["t7"] > 10 and t["t90"] is None, (t, n)
# trop peu de ventes : rien (pas de hasard)
assert all(x is None for x in tendance_cartes.par_ventes(v[:4], M)[0].values())
# l'historique de la valeur : 200 $ il y a 40 jours, 230 $ aujourd'hui -> +15 % sur 30 jours
h = tendance_cartes.par_historique([(J(40), 200.0), (J(2), 230.0)], 230.0, M)
assert h["t30"] == 15.0 and h["t7"] == 15.0 and h["t90"] is None, h
# dans l'inventaire
api = lockerroom.Api()
cid = api.carte_sauver({"titre": T, "joueur": "Ivan Demidov", "emplacement": "Collection", "statut": "En stock", "valeur": 112})["id"]
autre = api.carte_sauver({"titre": "2024-25 Upper Deck Some Player Base #12", "joueur": "Some Player", "statut": "En stock", "valeur": 5})["id"]
tendance_cartes.maj(api, M)
assert tendance_cartes.maj(api, M) is None                      # une fois par jour
l = {x["id"]: x for x in api.inventaire_liste({})}
assert l[cid]["tendance"]["t30"] and l[cid]["tendance"]["source"] == "ventes" and "tendance" not in l[autre], l[cid].get("tendance")
c = api._db(); assert c.execute("SELECT COUNT(*) FROM carte_valeur_hist").fetchone()[0] == 2; c.close()
print("ok tendance des cartes")
