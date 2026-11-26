"""26 nov 2026 (Mathieu : « on y va pour le mega test pour donnees PSA, juste me dire quand le partir ») : les ventes PSA 10 et
PSA 9 de chaque joueur (120 jours), puis la version raw de chaque carte vue en PSA 10. Une base A PART : rien dans nos archives
(une recherche « joueur + note » melange des cartes : elle fausserait les tendances et les tests publies)."""
import os, sys, tempfile, time, io, urllib.error
from datetime import datetime, timedelta, timezone
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import banque_psa, historique, vendues, base_ventes, indice_joueurs
jr = lambda k: (datetime.now(timezone.utc) - timedelta(days=k)).strftime("%Y-%m-%d")
auj = datetime.now(timezone.utc).date()
vendues._taux_usd_cad = lambda: 1.40
banque_psa.PAUSE_S = 0

# ---- 0. sans cle : rien ; jamais lancee : rien ne part seul
os.environ.pop("COMPSNIPER_CLE", None)
assert banque_psa.lancer()["ok"] is False and banque_psa.continuer_si_besoin() is None
os.environ["COMPSNIPER_CLE"] = "cs_test"; os.environ["LR_HISTORIQUE_MOIS"] = "100000"; os.environ["LR_MEGA_RESERVE"] = "100"
assert banque_psa.bilan()["statut"] == "aucune"
assert banque_psa.continuer_si_besoin() is None, "la collecte ne part JAMAIS seule : c'est l'admin qui la lance"

# ---- 1. la carte exacte, lue dans le TITRE (les memes regles que les comps)
cdt = banque_psa.carte_du_titre
assert cdt("2023-24 Upper Deck Connor Bedard Young Guns #451 RC PSA 10 GEM MINT", "Connor Bedard") == "connor bedard young guns"
assert cdt("2023-24 Upper Deck Canvas Young Guns Connor Bedard #C382 PSA 10", "Connor Bedard") == "connor bedard young guns canvas"
assert cdt("2023-24 O-Pee-Chee Platinum Connor Bedard Rookie Rainbow #201 PSA 10", "Connor Bedard") == "connor bedard o-pee-chee platinum rainbow"
assert cdt("2020-21 Upper Deck Young Guns Alexis Lafreniere #201 PSA 10 GEM MT", "Alexis Lafrenière") == "alexis lafreniere young guns"
assert cdt("2020-21 Upper Deck Young Guns Alexis Lafreniere #201 PSA 10 + free shipping", "Alexis Lafrenière") is None, "comme les tendances : un « + » ecarte la vente"
assert cdt("2023-24 Upper Deck Connor Bedard Young Guns #451 PSA 9", "Connor Bedard") is None, "une PSA 9 n'est pas une PSA 10"
assert cdt("2023-24 Upper Deck Connor Bedard Young Guns #451 PSA 9", "Connor Bedard", note="9") == "connor bedard young guns"
assert cdt("2023-24 Upper Deck Connor Bedard Young Guns #451 BGS 10", "Connor Bedard") is None, "BGS n'est pas PSA"
assert cdt("2023-24 Upper Deck Connor Bedard Young Guns #451 RC", "Connor Bedard") is None, "raw"
assert cdt("Connor Bedard PSA 10 rookie card Blackhawks", "Connor Bedard") is None, "on ne sait pas quelle carte"
assert cdt("2023-24 Upper Deck Young Guns Connor Bedard #451 PSA 10 LOT of 2", "Connor Bedard") is None, "un lot"
assert cdt("2023-24 Upper Deck Young Guns Connor Bedard #451 PSA 10 + Dazzlers", "Connor Bedard") is None, "un lot ecrit avec +"
assert cdt("2023-24 Upper Deck Young Guns Renewed Connor Bedard #YGR-1 PSA 10", "Connor Bedard") != "connor bedard young guns", "la suite d'un set n'est pas le set"
assert cdt("2024-25 Upper Deck Macklin Celebrini Young Guns #211 PSA 10", "Connor Bedard") is None, "la carte d'un autre joueur"
assert banque_psa._mots_joueur("Tim Stützle") == "tim stutzle" and banque_psa._mots_joueur("Connor Bedard") == "connor bedard"
print("TITRES OK")

# ---- 2. le plan (phase 1) : « <joueur> psa 10 » puis « <joueur> psa 9 », 120 jours
indice_joueurs.top = lambda n=12, filtre=None, actifs=None: ([{"nom": "Connor Bedard"}, {"nom": "Tim Stützle"}] if actifs else [{"nom": "Connor Bedard"}, {"nom": "Cher"}])
assert banque_psa.joueurs_cibles(10) == ["Connor Bedard", "Tim Stützle"], "actifs d'abord, sans doublon, un nom complet"
assert banque_psa.construire_plan() == 4 and banque_psa.construire_plan() == 0
c = banque_psa._cx(); plan = c.execute("SELECT q, phase, joueur, debut, fin FROM plan ORDER BY ordre").fetchall(); c.close()
assert [p[0] for p in plan] == ["connor bedard psa 10", "connor bedard psa 9", "tim stutzle psa 10", "tim stutzle psa 9"], plan
assert all(p[1] == 1 and p[3] == (auj - timedelta(days=120)).isoformat() and p[4] == auj.isoformat() for p in plan), plan

# ---- 3. une fausse CompSniper
def v(i, titre, prix="100", j=5):
    return {"itemId": i, "title": titre, "soldPrice": {"amount": prix, "currency": "USD"}, "soldDate": jr(j)}
YG10 = "2023-24 Upper Deck Connor Bedard Young Guns #451 RC PSA 10"
GL10 = "2023-24 Upper Deck O-Pee-Chee Glossy Connor Bedard #R-47 RC PSA 10"
PL10 = "2023-24 O-Pee-Chee Platinum Connor Bedard Rainbow #201 PSA 10"
APP = []
def page(q, p, debut, fin):
    APP.append((q, p, debut, fin))
    if q == "connor bedard psa 10":
        if p == 1:        # une page pleine : 30 Young Guns, 12 Glossy, 3 Platinum Rainbow (trop peu), un lot, une PSA 9, 3 sans nom de carte
            r = ([v(f"yg{i}", YG10, "1000", 3 + i) for i in range(30)] + [v(f"gl{i}", GL10, "200", 3 + i) for i in range(12)]
                 + [v(f"pl{i}", PL10, "400") for i in range(3)] + [v("lot", YG10 + " LOT of 2"), v("p9", YG10.replace("PSA 10", "PSA 9"))]
                 + [v(f"x{i}", "Connor Bedard PSA 10 rookie") for i in range(3)])
            assert len(r) == 50
            return {"results": r}
        return {"results": [v(f"z{i}", YG10, "1000", 40 + i) for i in range(6)]}
    if q == "connor bedard psa 9":
        return {"results": [v(f"n{i}", YG10.replace("PSA 10", "PSA 9"), "300", 4 + i) for i in range(8)] + [v("yg0", YG10)]}     # yg0 : deja vue
    if q == "connor bedard o-pee-chee glossy":
        return {"results": [v(f"r{i}", "2023-24 Upper Deck O-Pee-Chee Glossy Connor Bedard #R-47 RC", "25", 2 + i) for i in range(20)] + [v("gl0", GL10)]}
    return {"results": []}
banque_psa._page = page
# la version raw de la Young Guns est deja dans nos archives, fraiche (la banque Young Guns) : pas repayee
base_ventes.noter("connor bedard young guns", [{"titre": f"2023-24 Upper Deck Connor Bedard Young Guns #451 {i}", "prix": 300.0, "le": jr(1 + i), "url": f"https://e/{i}"} for i in range(25)], sport="hockey")
c = base_ventes._cx(); n_arch = c.execute("SELECT COUNT(*) FROM ventes").fetchone()[0]; c.close()

# le plafond : 2 credits, la collecte s'arrete et le dit ; elle ne reprend pas seule au plafond
u0 = historique.utilises()["mois"]
b = banque_psa.collecter(plafond=2, pause=0)
assert b["statut"] == "plafond" and b["credits"] == 2 and historique.utilises()["mois"] - u0 == 2, b
assert [a[:2] for a in APP] == [("connor bedard psa 10", 1), ("connor bedard psa 10", 2)], APP
assert banque_psa.continuer_si_besoin() is None
# l'admin monte le plafond et relance : elle reprend OU ELLE ETAIT (la recherche finie n'est pas refaite)
APP.clear()
b = banque_psa.collecter(plafond=100, pause=0)
assert b["statut"] == "terminee" and b["phase"] == 2, b
assert [a[:2] for a in APP] == [("connor bedard psa 9", 1), ("tim stutzle psa 10", 1), ("tim stutzle psa 9", 1), ("connor bedard o-pee-chee glossy", 1)], APP
assert all(a[2] == (auj - timedelta(days=120)).isoformat() and a[3] == auj.isoformat() for a in APP)
assert b["credits"] == 6 and historique.utilises()["mois"] - u0 == 6, b                   # 1 page = 1 credit, compte avec les autres
# phase 2 : la Glossy (12 PSA 10) est cherchee ; la Young Guns (36) est deja dans nos archives ; la Platinum (3) : trop peu
c = banque_psa._cx(); p2 = c.execute("SELECT q, joueur, n10, fini, raison, pages FROM plan WHERE phase=2 ORDER BY ordre").fetchall(); c.close()
assert p2 == [("connor bedard young guns", "Connor Bedard", 36, 1, "deja dans nos archives", 0),
              ("connor bedard o-pee-chee glossy", "Connor Bedard", 12, 1, "toutes les ventes", 1)], p2
# une vente n'entre qu'une fois (yg0 et gl0 reviennent dans d'autres recherches) ; les prix en $ CA
assert b["ventes"] == 50 + 6 + 8 + 20, b
c = banque_psa._cx()
assert c.execute("SELECT prix, joueur, q FROM ventes WHERE cle='yg0'").fetchone() == (1400.0, "Connor Bedard", "connor bedard psa 10")
assert c.execute("SELECT COUNT(*) FROM ventes WHERE q='connor bedard o-pee-chee glossy'").fetchone()[0] == 20
c.close()
# RIEN dans nos archives : ni une vente, ni une recherche de plus
c = base_ventes._cx()
assert c.execute("SELECT COUNT(*) FROM ventes").fetchone()[0] == n_arch and not c.execute("SELECT 1 FROM ventes WHERE q LIKE '%psa 10' OR q LIKE '%glossy'").fetchone()
c.close()
# terminee : rien n'est refait, rien ne repart
APP.clear(); assert banque_psa.continuer_si_besoin() is None and banque_psa.collecter(pause=0)["statut"] == "terminee" and not APP
print("COLLECTE OK")

# ---- 4. garde-fous : la page de trop (HTTP 400) ferme CETTE recherche ; une cle refusee (401) arrete tout et le dit ;
#         une collecte coupee reprend seule
def http(code):
    return urllib.error.HTTPError("https://x", code, "x", {}, io.BytesIO(b""))
banque_psa._run_maj(statut="interrompue", credits=0, raw_planifie=1)
c = banque_psa._cx(); c.execute("DELETE FROM plan")
c.execute("INSERT INTO plan (q, phase, joueur, ordre, debut, fin) VALUES ('a b psa 10', 1, 'A B', 0, ?, ?), ('c d psa 10', 1, 'C D', 1, ?, ?)", (jr(120), jr(0), jr(120), jr(0)))
c.commit(); c.close()
def page4(q, p, debut, fin):
    APP.append((q, p))
    if q == "a b psa 10":
        raise http(400)
    return {"results": [v(f"cd{p}{i}", "c d card", j=3) for i in range(50)]} if p <= 40 else {"results": []}
banque_psa._page = page4
APP.clear()
r = banque_psa.continuer_si_besoin()
assert r and r["ok"], r
for _ in range(200):
    if not banque_psa.ETAT["en_cours"] and banque_psa.bilan()["statut"] != "en_cours":
        break
    time.sleep(0.05)
b = banque_psa.bilan()
assert b["statut"] == "terminee" and b["raisons"] == {"refusee (HTTP 400)": 1, "pages max": 1}, b
assert APP[0] == ("a b psa 10", 1) and len(APP) == 1 + banque_psa.PAGES_MAX and b["credits"] == banque_psa.PAGES_MAX, (len(APP), b["credits"])   # la page refusee ne coute rien
banque_psa._run_maj(statut="interrompue")
c = banque_psa._cx(); c.execute("UPDATE plan SET fini=0, pages=0 WHERE q='c d psa 10'"); c.commit(); c.close()
def page401(q, p, debut, fin):
    raise http(401)
banque_psa._page = page401
b = banque_psa.collecter(pause=0)
assert b["statut"] == "erreur" and b["erreur"] == "CompSniper HTTP 401", b
print("GARDE-FOUS OK")

# ---- 5. admin seulement ; le serveur et l'ecran
import lockerroom
api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "t.db"))
api._est_admin = lambda reel=False: False
assert api.admin_banque_psa()["ok"] is False and api.admin_banque_psa_lancer(10)["ok"] is False
api._est_admin = lambda reel=False: True
assert api.admin_banque_psa()["recherches"] == 2
srv = open(os.path.join(RACINE, "server.py"), encoding="utf-8").read()
assert srv.count("banque_psa.continuer_si_besoin()") == 2, "la reprise : la boucle de l'heure et le demarrage"
src = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()
app = open(os.path.join(RACINE, "ui", "app.html"), encoding="utf-8").read()
assert "() => feuilleBanquePSA()]" in src and "async function feuilleBanquePSA(){" in src and "API.admin_banque_psa_lancer(" in src
assert "admin_banque_psa_lancer" in app and "feuilleBanquePSA" in app, "l'app servie a la tuile"
# la base est a part : le module n'ecrit jamais dans nos archives
mod = open(os.path.join(RACINE, "banque_psa.py"), encoding="utf-8").read()
assert "base_ventes.noter" not in mod.split('"""', 2)[2], "une recherche « joueur + note » ne doit jamais entrer dans nos archives"
print("ADMIN OK")
