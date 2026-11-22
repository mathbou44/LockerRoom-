"""22 nov 2026 (Mathieu : « fais le mega test CompSniper ») : 3 ans de ventes de la meme carte, collectes sur le serveur."""
import os, sys, tempfile, time
from datetime import date, datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import mega_test, historique, vendues, base_ventes
jr = lambda k: (datetime.now() - timedelta(days=k)).strftime("%Y-%m-%d")
auj = date.today()
vendues._taux_usd_cad = lambda: 1.40
mega_test.PAUSE_S = 0

# sans cle : rien
os.environ.pop("COMPSNIPER_CLE", None)
assert mega_test.lancer()["ok"] is False and mega_test.continuer_si_besoin() is None
os.environ["COMPSNIPER_CLE"] = "cs_test"; os.environ["LR_HISTORIQUE_MOIS"] = "100000"; os.environ["LR_MEGA_RESERVE"] = "100"

# nos archives : une carte tres vendue, une peu vendue, une trop bon marche, une recherche large, une carte connue depuis peu
def ventes(q, n, prix, d0=1, pas=3):
    base_ventes.noter(q, [{"titre": f"{q} #{i}", "prix": prix, "le": jr(d0 + pas * i), "url": f"https://e/{q}/{i}"} for i in range(n)], sport="hockey")
ventes("connor bedard young guns", 40, 300.0)            # 40 ventes connues : on ne repaie pas sa periode connue
ventes("macklin celebrini young guns psa 10", 5, 500.0)
ventes("ivan demidov young guns", 2, 200.0)                # 2 ventes en un an : pas assez pour un test
ventes("tanner molendyk base", 20, 5.0)                    # sous le prix minimum du Radar
ventes("young guns psa 10", 50, 120.0)                     # recherche large : jamais
assert mega_test.construire_plan() == 2
c = mega_test._cx(); plan = c.execute("SELECT q, ordre FROM plan ORDER BY ordre").fetchall(); c.close()
assert [q for q, _ in plan] == ["connor bedard young guns", "macklin celebrini young guns psa 10"], plan

# la fenetre : 3 ans ; une carte deja bien connue s'arrete a sa plus vieille vente connue (+2 jours)
d, f = mega_test.fenetre(None, 0)
assert d == (auj - timedelta(days=1095)).isoformat() and f == auj.isoformat()
d, f = mega_test.fenetre(jr(118), 40)
assert f == (date.fromisoformat(jr(118)) + timedelta(days=2)).isoformat()
assert mega_test.fenetre(jr(118), 5)[1] == auj.isoformat()                 # trop peu connue : toute la fenetre

# une fausse CompSniper : Bedard a 2 pages pleines puis une courte ; Celebrini : une page courte
APP = []
def page(q, p, debut, fin):
    APP.append((q, p, debut, fin))
    n = 50 if ("bedard" in q and p < 3) else 7
    return {"results": [{"itemId": f"{q[:3]}{p}-{i}", "title": f"{q} card {p}-{i}", "soldPrice": {"amount": "100", "currency": "USD"},
                         "soldDate": jr(150 + p * 60 + i)} for i in range(n)]}
mega_test._page = page
u0 = historique.utilises()["mois"]
b = mega_test.collecter(pause=0)
assert b["statut"] == "terminee" and b["cartes_finies"] == 2 and b["credits"] == 4, b
assert historique.utilises()["mois"] - u0 == 4                     # 1 page = 1 credit, compte avec les autres
assert b["ventes"] == 50 + 50 + 7 + 7 and b["raisons"] == {"toutes les ventes": 2}, b
assert APP[0][3] == (date.fromisoformat(jr(118)) + timedelta(days=2)).isoformat()      # Bedard : sa periode connue n'est pas repayee
assert APP[-1][3] == auj.isoformat()                                                     # Celebrini : toute la fenetre
c = base_ventes._cx(); n_b = c.execute("SELECT COUNT(*) FROM ventes WHERE q='connor bedard young guns'").fetchone()[0]; c.close()
assert n_b == 40 + 107, n_b                                                              # dans nos archives (prix en $ CA)
c = base_ventes._cx(); p_ = c.execute("SELECT prix FROM ventes WHERE titre LIKE 'connor bedard young guns card%' LIMIT 1").fetchone()[0]; c.close()
assert p_ == 140.0
# terminee : rien n'est refait, rien ne repart seul
APP.clear(); assert mega_test.continuer_si_besoin() is None and not APP
print("COLLECTE OK")

# garde-fous : une page repetee (l'API ignore la page) termine la recherche ; 3 ans atteints aussi
mega_test._run_maj(statut="aucune", credits=0)
c = mega_test._cx(); c.execute("DELETE FROM plan"); c.execute("INSERT INTO plan (q, ordre, n_an, prix) VALUES ('rep a', 0, 9, 50), ('vieux b', 1, 9, 50)"); c.commit(); c.close()
def page2(q, p, debut, fin):
    APP.append((q, p))
    if q == "rep a":
        return {"results": [{"itemId": f"x{i}", "title": f"rep {i}", "soldPrice": {"amount": "50"}, "soldDate": jr(10 + i)} for i in range(50)]}
    return {"results": [{"itemId": f"v{p}{i}", "title": f"vieux {i}", "soldPrice": {"amount": "50"}, "soldDate": jr(1100 + i)} for i in range(50)]}
mega_test._page = page2
APP.clear(); b = mega_test.collecter(pause=0)
assert APP == [("rep a", 1), ("rep a", 2), ("vieux b", 1)] and b["raisons"] == {"page repetee": 1, "3 ans atteints": 1}, (APP, b)
print("GARDE-FOUS OK")

# les credits : le plafond de la collecte ; le budget du mois moins la reserve de l'app (a sec : attend le mois suivant)
mega_test._run_maj(statut="aucune", credits=0)
c = mega_test._cx(); c.execute("DELETE FROM plan"); c.execute("INSERT INTO plan (q, ordre, n_an, prix) VALUES ('long c', 0, 9, 50)"); c.commit(); c.close()
def page3(q, p, debut, fin):
    APP.append((q, p))
    return {"results": [{"itemId": f"l{p}-{i}", "title": f"long {i}", "soldPrice": {"amount": "50"}, "soldDate": jr(5 + p)} for i in range(50)]}
mega_test._page = page3
APP.clear(); b = mega_test.collecter(plafond=3, pause=0)
assert len(APP) == 3 and b["statut"] == "plafond", (APP, b)
assert mega_test.continuer_si_besoin() is None                     # plafond atteint : l'admin decide
mega_test._run_maj(statut="interrompue", plafond=1000)
os.environ["LR_HISTORIQUE_MOIS"] = str(historique.utilises()["mois"] + 100 + 2)          # 2 credits de libres apres la reserve
APP.clear(); b = mega_test.collecter(pause=0)
assert len(APP) == 2 and b["statut"] == "attente_mois", (APP, b)
assert APP[0] == ("long c", 4)                                      # reprend a la page suivante
APP.clear(); assert mega_test.continuer_si_besoin() is None and not APP      # a sec : rien
os.environ["LR_HISTORIQUE_MOIS"] = "100000"                         # le mois suivant : elle repart toute seule
assert mega_test.continuer_si_besoin()["ok"]
for _ in range(200):
    time.sleep(0.05)
    if not mega_test.ETAT["en_cours"]:
        break
assert APP and APP[0] == ("long c", 6), APP
os.environ["LR_MEGA_AUTO"] = "0"; mega_test._run_maj(statut="interrompue")
assert mega_test.continuer_si_besoin() is None
os.environ.pop("LR_MEGA_AUTO")
print("CREDITS OK")

# la sonde (le tout premier tour) : 5 credits sur les ventes d'il y a 2 a 3 ans ; rien de vieux -> on ne met pas le forfait
def frais():
    c = mega_test._cx(); c.execute("DELETE FROM plan"); c.execute("DELETE FROM collecte"); c.commit(); c.close()
    mega_test.construire_plan()
def attendre():
    for _ in range(200):
        time.sleep(0.05)
        if not mega_test.ETAT["en_cours"]:
            break
    time.sleep(0.1)
frais()
SON = []
def sonde_vide(q, p, debut, fin):
    SON.append((q, debut, fin)); return {"results": []}
mega_test._page = sonde_vide
assert mega_test.continuer_si_besoin()["ok"]; attendre()
b = mega_test.bilan()
assert b["statut"] == "essai_rate" and "Essai raté" in b["texte"] and len(SON) == b["cartes"] == 4, (b, SON)     # Bedard, Celebrini et les 2 cartes des garde-fous
assert SON[0][1] == (auj - timedelta(days=1095)).isoformat() and SON[0][2] == (auj - timedelta(days=730)).isoformat()
assert mega_test.continuer_si_besoin() is None                     # essai rate : l'admin decide
frais(); SON.clear()
def sonde_ok(q, p, debut, fin):
    SON.append((q, p))
    if fin == (auj - timedelta(days=730)).isoformat():
        return {"results": [{"itemId": f"s{q[:3]}", "title": f"{q} vieille", "soldPrice": {"amount": "80"}, "soldDate": jr(900)}]}
    return {"results": []}
mega_test._page = sonde_ok
assert mega_test.continuer_si_besoin()["ok"]; attendre()
b = mega_test.bilan()
assert b["statut"] == "terminee" and b["credits"] == 4 + 4 and b["plafond"] == mega_test.PLAFOND_DEFAUT, b    # sonde 2 + collecte 2
c = base_ventes._cx(); assert c.execute("SELECT COUNT(*) FROM ventes WHERE titre LIKE '% vieille'").fetchone()[0] == 4; c.close()
print("SONDE OK")

# admin seulement
import lockerroom
api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "t.db"))
api._est_admin = lambda reel=False: False
assert api.admin_mega_test()["ok"] is False and api.admin_mega_test_lancer(10)["ok"] is False
api._est_admin = lambda reel=False: True
assert api.admin_mega_test()["cartes"] == 4
print("ADMIN OK")
