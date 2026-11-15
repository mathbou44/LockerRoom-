"""15 nov 2026 (« prends toute la data qu'il faut ; fais tout ») : la banque Young Guns pour entrainer SlabIQ sur le timing."""
import gzip, json, os, sys, tempfile
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import banque_yg, historique, vendues
jr = lambda k: (datetime.now() - timedelta(days=k)).strftime("%Y-%m-%d")
os.environ["COMPSNIPER_CLE"] = "cs_test"; os.environ["LR_HISTORIQUE_MOIS"] = "1100"
vendues._taux_usd_cad = lambda: 1.40
banque_yg.PAUSE_S = 0
# une fausse CompSniper : 2 pages pleines puis une page courte, pour chaque recherche
APP = []
def page(q, p, par):
    APP.append((q, p, par))
    if par > 50:
        import urllib.error
        raise urllib.error.HTTPError("u", 400, "limit", {}, None)          # le forfait refuse 200 par page
    n = par if p < 3 else 7
    return {"results": [{"itemId": f"{abs(hash(q)) % 999}{p}{i}", "title": f"{q} #{i} rc", "soldPrice": {"amount": "10", "currency": "USD"},
                         "soldDate": jr(p * 30 + i)} for i in range(n)]}
banque_yg._page = page
r = banque_yg.collecter(plafond=100, joueurs=["Connor Bedard", "Ivan Demidov"])
assert r["ventes"] == 4 * (50 + 50 + 7), r
assert r["recherches_finies"] == 4 and r["joueurs"] == 2, r
assert APP[0][2] == 200 and all(par == 50 for _, _, par in APP[1:]), APP[:3]
assert historique.utilises()["mois"] == 12, historique.utilises()          # 4 recherches x 3 pages (les refus : gratuits)
# reprise : rien n'est refait
APP.clear(); banque_yg.collecter(plafond=100, joueurs=["Connor Bedard", "Ivan Demidov"]); assert not APP
# le plafond de credits de la collecte, et la reserve de l'app
APP.clear(); banque_yg.ETAT["credits"] = 0
r = banque_yg.collecter(plafond=2, joueurs=["Macklin Celebrini"])
assert len([a for a in APP if a[2] == 50]) == 2 and r["texte"] == "Plafond de crédits atteint", (APP, r)
os.environ["LR_HISTORIQUE_MOIS"] = str(historique.utilises()["mois"] + banque_yg.RESERVE_APP)       # plus rien pour la banque
APP.clear(); r = banque_yg.collecter(plafond=100, joueurs=["Lane Hutson"]); assert not APP and "Plafond" in r["texte"]
print("COLLECTE OK")
# l'offre du jour : une fois par jour par joueur
LUS = []
banque_yg._offre_une = lambda nom: (LUS.append(nom), (123, 45.0))[1]
assert banque_yg.offre_du_jour() == 3 and banque_yg.offre_du_jour() == 0 and len(LUS) == 3
print("OFFRE OK")
# les nouvelles : titre + lien, une fois
nj = {"Connor Bedard": {"titres": [{"titre": "Bedard scores twice", "lien": "https://www.nhl.com/a", "date": jr(1)}],
                        "evs": [{"type": "exploit", "sens": 1, "titre": "Bedard scores twice", "lien": "https://www.nhl.com/a", "date": jr(1)}]}}
banque_yg.archiver_nouvelles(nj); banque_yg.archiver_nouvelles(nj)
assert banque_yg.bilan()["nouvelles"] == 1
print("NOUVELLES OK")
b, nom = banque_yg.exporter()
d = json.loads(gzip.decompress(b))
assert len(d["ventes"]) == banque_yg.bilan()["ventes"] and d["offre"][0]["annonces"] == 123 and d["nouvelles"][0]["type"] == "exploit"
assert nom.startswith("banque_yg_") and nom.endswith(".json.gz")
print("EXPORT OK")
# admin seulement
import lockerroom
api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "t.db"))
api._est_admin = lambda reel=False: False
assert api.admin_banque_yg()["ok"] is False and api.admin_banque_yg_lancer(10)["ok"] is False
api._est_admin = lambda reel=False: True
assert api.admin_banque_yg()["ventes"] == banque_yg.bilan()["ventes"]
print("ADMIN OK")
