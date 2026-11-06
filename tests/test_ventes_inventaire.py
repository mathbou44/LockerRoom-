"""6 nov 2026 (Mathieu : « pour eviter de prendre mes achats en consideration et etre pres du marche actuel, prendre
seulement les ventes des 3 derniers mois pour l'ajustement du prix des cartes dans l'inventaire »)."""
import os, sys, tempfile
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom, vendues, suivi_valeur

api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "i.db"))
T = "2019-20 Upper Deck Young Guns Jack Hughes #201"
cid = api.carte_sauver({"titre": T, "joueur": "Jack Hughes", "statut": "En stock", "cout": 55})["id"]
j = lambda k: (datetime.now() - timedelta(days=k)).strftime("%Y-%m-%d")
url = lambda i: f"https://www.ebay.com/itm/{i}"
c = api._db()
c.execute(api._SQL_ACHATS)
c.execute("INSERT INTO achats_ebay (item_id, n, titre, cout, devise, date, carte_id) VALUES ('111111111111', 1, ?, 40, 'CAD', ?, NULL)", (T, j(5)))
c.execute("INSERT INTO achats_ebay (item_id, n, titre, cout, devise, date, carte_id) VALUES ('999', 1, ?, 55, 'CAD', ?, ?)", (T, j(20), cid))
c.commit(); c.close()
ventes = [{"titre": T, "prix": 85, "le": j(1), "url": url(222222222222)},
          {"titre": T, "prix": 84, "le": j(4), "url": url(333333333333)},
          {"titre": T, "prix": 40, "le": j(5), "url": url(111111111111)},      # mon achat (son numero)
          {"titre": T, "prix": 55.5, "le": j(21), "url": url(444444444444)},   # ma carte : prix paye, 1 jour de l'achat
          {"titre": T, "prix": 82, "le": j(30), "url": url(555555555555)},
          {"titre": T, "prix": 200, "le": j(120), "url": url(666666666666)}]   # plus de 3 mois
carte = api.carte_lire(cid)
garde = api._ventes_inventaire(ventes, carte)
assert [v["prix"] for v in garde] == [85, 84, 82], garde
assert [v["prix"] for v in api._ventes_inventaire(ventes)] == [85, 84, 55.5, 82], "sans la carte : seulement les numeros"

vendues.memes_annonce = lambda t, n=None, fond=True, **k: {"ventes": [dict(v) for v in ventes]}
r = api.carte_valeur(cid)
assert r["ok"] and r["n"] == 3 and r["valeur"] == 84, r
assert suivi_valeur.valeur_actuelle(carte, api=api) == 84
assert suivi_valeur.valeur_actuelle(carte) == 82                            # sans api : 90 jours seulement (40 et 55,5 restent)
print("VENTES INVENTAIRE OK")
