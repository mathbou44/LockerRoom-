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
assert all(p[1] == 1 and p[3] == (auj - timedelta(days=banque_psa.JOURS)).isoformat() and p[4] == auj.isoformat() for p in plan), plan

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
assert all(a[2] == (auj - timedelta(days=banque_psa.JOURS)).isoformat() and a[3] == auj.isoformat() for a in APP)
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
c.execute("INSERT INTO plan (q, phase, joueur, ordre, debut, fin) VALUES ('a b psa 10', 1, 'A B', 0, ?, ?), ('c d psa 10', 1, 'C D', 1, ?, ?)", (jr(banque_psa.JOURS), jr(0), jr(banque_psa.JOURS), jr(0)))
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
import threading
for th in threading.enumerate():                 # la collecte tourne dans son fil : on attend qu'il finisse
    if th.name == "donnees-psa":
        th.join(60)
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

# ---- 4 bis. JAMAIS DEUX COLLECTES (26 nov, 13 h 28, journal : « Donnees PSA : reprise (en_cours) » 45 s apres le lancement : la
#           boucle de l'heure a relance une collecte qui venait de partir ; deux collectes paieraient chaque page deux fois)
import contextlib
c = banque_psa._cx(); c.execute("UPDATE plan SET fini=0, pages=0 WHERE q='c d psa 10'"); c.commit(); c.close()
APP.clear()
banque_psa._page = page4
# (a) le battement : « en_cours » et un battement frais = elle tourne (meme si le drapeau en memoire dit non) : rien ne la double
banque_psa._run_maj(statut="en_cours", battement=time.time() - 20, erreur=None)
assert banque_psa.ETAT["en_cours"] is False and banque_psa.vivante()
assert banque_psa.continuer_si_besoin() is None, "la boucle de l'heure ne relance pas une collecte qui tourne"
assert banque_psa.lancer().get("deja") is True and banque_psa.collecter(pause=0).get("deja") is True and not APP, "le bouton non plus"
assert banque_psa.bilan()["en_cours"] is True
# (b) un battement de plus de 3 minutes : elle est morte (redemarrage) : la reprise part
banque_psa._run_maj(battement=time.time() - banque_psa.VIVANTE_S - 5)
assert not banque_psa.vivante()
# (c) le jeton : une collecte qui tourne s'arrete des qu'une autre a pris le relais, sans toucher au statut ni payer une page de plus
lent = threading.Event()
def page_lente(q, p, debut, fin):
    APP.append((q, p)); lent.wait(5)
    return {"results": [v(f"l{p}{i}", "c d card", j=3) for i in range(50)]}
banque_psa._page = page_lente
jl = io.StringIO()
with contextlib.redirect_stdout(jl):
    assert banque_psa.continuer_si_besoin()["ok"]
    for _ in range(100):
        if APP: break
        time.sleep(0.02)
    assert APP == [("c d psa 10", 1)] and banque_psa.ETAT["en_cours"]
    jeton1 = banque_psa._run()["jeton"]
    assert jeton1 and len(jeton1) == 32
    banque_psa._run_maj(jeton="une-autre-collecte")            # une autre collecte (un autre processus) prend le relais
    cr0 = banque_psa._run()["credits"]
    lent.set()
    for _ in range(200):
        if not banque_psa.ETAT["en_cours"]: break
        time.sleep(0.02)
assert not banque_psa.ETAT["en_cours"] and APP == [("c d psa 10", 1)], APP          # elle n'a pas demande la page 2
r_ = banque_psa._run()
assert r_["statut"] == "en_cours" and r_["jeton"] == "une-autre-collecte" and r_["credits"] == cr0 + 1, r_     # le statut reste a l'autre
assert "une autre collecte a pris le relais" in jl.getvalue(), jl.getvalue()
banque_psa._run_maj(statut="interrompue", jeton=None)
print("JAMAIS DEUX OK")

# ---- 4 ter. UNE BASE OCCUPEE NE TUE PLUS LA COLLECTE (26 nov, 14 h 58, journal : « Exception in thread donnees-psa [...]
#            sqlite3.OperationalError: database is locked », 22 s apres la reprise ; le statut restait « en_cours »)
import sqlite3 as _sq
c = banque_psa._cx(); c.execute("UPDATE plan SET fini=0, pages=0, ventes=0 WHERE q='c d psa 10'"); c.execute("DELETE FROM ventes"); c.commit(); c.close()
banque_psa._run_maj(statut="interrompue", credits=0, erreur=None)
vrai_cx, pannes = banque_psa._cx, {"n": 0}
def cx_occupe():                                 # la base est occupee 1 fois sur 3 : chaque lecture / ecriture reessaie
    pannes["n"] += 1
    if pannes["n"] % 3 == 0:
        raise _sq.OperationalError("database is locked")
    return vrai_cx()
vrai_compter, pc = historique._compter, {"n": 0}
def compter_occupe(chasseur, sport=None):        # historique.sqlite aussi (il n'attend que 5 s)
    pc["n"] += 1
    if pc["n"] % 2 == 1:
        raise _sq.OperationalError("database is locked")
    return vrai_compter(chasseur, sport)
def page3(q, p, debut, fin):
    return {"results": [v(f"t{p}{i}", "c d card", j=3) for i in range(50 if p < 3 else 7)]}
banque_psa._cx, historique._compter, banque_psa._page = cx_occupe, compter_occupe, page3
u1 = historique.utilises()["mois"]
try:
    banque_psa.collecter(pause=0)
finally:
    banque_psa._cx, historique._compter = vrai_cx, vrai_compter
b = banque_psa.bilan()
assert b["statut"] == "terminee" and b["credits"] == 3 and b["ventes"] == 107 and historique.utilises()["mois"] - u1 == 3, b     # rien de perdu, rien de paye deux fois
assert pannes["n"] > 30 and pc["n"] == 6, (pannes, pc)
# une erreur imprevue : le fil ne meurt plus sans le dire : statut « erreur » (jamais « en_cours » pour toujours), reprise plus tard
c = banque_psa._cx(); c.execute("UPDATE plan SET fini=0, pages=0 WHERE q='c d psa 10'"); c.commit(); c.close()
banque_psa._run_maj(statut="interrompue", erreur=None)
vrai_noter = banque_psa._noter
def noter_casse(q, joueur, ventes):
    raise ValueError("imprevu")
banque_psa._noter = noter_casse
jl = io.StringIO()
try:
    with contextlib.redirect_stdout(jl):
        b = banque_psa.collecter(pause=0)
finally:
    banque_psa._noter = vrai_noter
assert b["statut"] == "erreur" and "Arrêt imprévu" in b["erreur"] and not banque_psa.ETAT["en_cours"] and "arret imprevu" in jl.getvalue(), (b, jl.getvalue())
assert banque_psa.continuer_si_besoin() is None, "une erreur : pas avant 15 minutes"
banque_psa._run_maj(battement=time.time() - 16 * 60)
banque_psa._page = page4
r = banque_psa.continuer_si_besoin()
assert r and r["ok"]
for th in threading.enumerate():
    if th.name == "donnees-psa":
        th.join(60)
assert banque_psa.bilan()["statut"] == "terminee"
print("BASE OCCUPEE OK")

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
