"""26 nov 2026, 18 h 50 (Mathieu : « besoin de plus de data parce qu'on doit etre vraiment tres complet [...] au moins entre 500 et
1 000 » ; son choix : « 12 mois + 500 joueurs »). La collecte du 26 nov (200 joueurs, 120 jours) est ETENDUE quand l'admin la
relance : chaque recherche recoit seulement la tranche d'avant (rien n'est paye deux fois), les joueurs de plus entrent, la phase 2
est replanifiee ; les recherches qui ramenent surtout d'autres joueurs (« cam york » : du baseball) sont laissees et, a l'avenir,
arretees apres deux pages. Elle ne part jamais seule."""
import os, sys, tempfile, time
from datetime import datetime, timedelta, timezone
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import banque_psa, historique, vendues, a_grader
jr = lambda k: (datetime.now(timezone.utc) - timedelta(days=k)).strftime("%Y-%m-%d")
vendues._taux_usd_cad = lambda: 1.40
banque_psa.PAUSE_S = 0
os.environ["COMPSNIPER_CLE"] = "cs_test"; os.environ["LR_HISTORIQUE_MOIS"] = "100000"; os.environ["LR_MEGA_RESERVE"] = "100"
assert banque_psa.JOURS == 365 and banque_psa.JOUEURS_N == 500 and banque_psa.VERSION_PLAN == 2

# ---- 0. le titre nomme-t-il le joueur ? le prenom puis le nom, cote a cote (un mot d'ecart au plus)
nm = a_grader._nomme
assert nm("2019-20 Upper Deck Young Guns Cam York #481 PSA 10", "Cam York")
assert not nm("Topps 2026 Series 1 Cam Schlittler Rookie #111 New York Yankees PSA 10", "Cam York"), "un « cam » et un « york » ne font pas Cam York"
assert not nm("2025 Panini Select Cam Skattebo New York Giants PSA 10", "Cam York")
assert nm("2005 UD #443 ALEXANDER OVECHKIN ROOKIE RC PSA 10", "Alex Ovechkin") and nm("2020-21 UD Alexis Lafreniere YG PSA 10", "Alexis Lafrenière")
assert nm("2024 UD Macklin K Celebrini #451 PSA 10", "Macklin Celebrini") and not nm("1987 Topps Ozzie Smith PSA 10", "Will Smith")

# ---- 1. la collecte du 26 nov, telle qu'elle a fini : 120 jours, pas de version
YG10 = "2023-24 Upper Deck Connor Bedard Young Guns #451 RC PSA 10"
D0, D12 = jr(120), jr(365)
banque_psa._run_maj()
c = banque_psa._cx()
plan = [("connor bedard psa 10", 1, "Connor Bedard", 0, "toutes les ventes"), ("connor bedard psa 9", 1, "Connor Bedard", 1, "fenetre atteinte"),
        ("cam york psa 10", 1, "Cam York", 2, "pages max"), ("x y psa 10", 1, "X Y", 3, "refusee (HTTP 400)"),
        ("connor bedard o-pee-chee glossy", 2, "Connor Bedard", 0, "toutes les ventes"), ("connor bedard young guns canvas", 2, "Connor Bedard", 1, "pages max"),
        ("connor bedard young guns", 2, "Connor Bedard", 2, "deja dans nos archives")]
for q, ph, j, o, raison in plan:
    c.execute("INSERT INTO plan (q, phase, joueur, ordre, debut, fin, pages, ventes, fini, raison) VALUES (?,?,?,?,?,?,3,10,1,?)", (q, ph, j, o, D0, jr(0), raison))
for i in range(10):
    c.execute("INSERT INTO ventes VALUES (?,?,?,?,?,?)", (f"b{i}", "connor bedard psa 10", "Connor Bedard", YG10, 1000.0, jr(5 + i)))
for i in range(120):
    c.execute("INSERT INTO ventes VALUES (?,?,?,?,?,?)", (f"s{i}", "cam york psa 10", "Cam York", "Topps 2026 Series 1 Cam Schlittler Rookie #111 New York Yankees PSA 10", 50.0, jr(5)))
# « jack hughes psa 10 » (26 nov) : 42 ventes, la plus vieille d'il y a 8 jours : sa tranche d'avant part de la, sans trou
c.execute("INSERT INTO plan (q, phase, joueur, ordre, debut, fin, pages, ventes, fini, raison, recu_min) VALUES ('jack hughes psa 10',1,'Jack Hughes',4,?,?,1,42,1,'toutes les ventes',?)", (D0, jr(0), jr(8)))
c.execute("UPDATE plan SET recu_min=? WHERE q='connor bedard psa 10'", (jr(121),))
c.execute("UPDATE collecte SET statut='terminee', plafond=10000, credits=1901, raw_planifie=1, battement=? WHERE id=1", (time.time() - 3600,))
c.commit(); c.close()
assert banque_psa._run().get("version") is None
banque_psa.joueurs_cibles = lambda n=None: ["Connor Bedard", "Cam York", "Lane Hutson"]

assert banque_psa.bilan()["a_etendre"] is True and banque_psa.bilan()["jours"] == 365 and banque_psa.bilan()["joueurs_vises"] == 500
# elle ne part JAMAIS seule : une collecte finie reste finie tant que l'admin ne la relance pas
assert banque_psa.continuer_si_besoin() is None

def v(i, titre, prix="100", j=200):
    return {"itemId": i, "title": titre, "soldPrice": {"amount": prix, "currency": "USD"}, "soldDate": jr(j)}
PL10 = "2023-24 O-Pee-Chee Platinum Connor Bedard Rainbow #201 PSA 10"
APP = []
def page(q, p, debut, fin):
    APP.append((q, p, debut, fin))
    if q == "connor bedard psa 10":                       # la tranche d'avant : 6 Platinum Rainbow PSA 10 d'il y a 200 jours
        return {"results": [v(f"pl{i}", PL10, "400", 200 + i) for i in range(6)]}
    if q == "lane hutson psa 10":                         # une recherche qui ne ramene QUE d'autres joueurs : arretee apres 2 pages
        return {"results": [v(f"h{p}_{i}", "2025 Panini Prizm Lane Johnson Philadelphia Eagles PSA 10", "20", 30 + p) for i in range(50)]}
    return {"results": []}
banque_psa._page = page
u0 = historique.utilises()["mois"]
b = banque_psa.collecter(plafond=10000, pause=0)
assert b["statut"] == "terminee", b
appels = [a[0] for a in APP]
assert "cam york psa 10" not in appels and "cam york psa 9" in appels, "« cam york psa 10 » ramenait d'autres joueurs : pas etendue ; sa PSA 9 est une recherche neuve"
assert "x y psa 10" not in appels and "connor bedard young guns canvas" not in appels and "connor bedard young guns" not in appels, appels
# la tranche d'avant, et seulement elle : de 12 mois a l'ancien debut
for q in ("connor bedard psa 10", "connor bedard psa 9", "connor bedard o-pee-chee glossy"):
    a = [x for x in APP if x[0] == q]
    assert a and all(x[2] == D12 and x[3] == D0 for x in a), (q, a)
a = [x for x in APP if x[0] == "jack hughes psa 10"]
assert a and all(x[2] == D12 and x[3] == jr(8) for x in a), a
assert banque_psa.bilan()["a_etendre"] is False, "une fois etendue, la fiche ne l'annonce plus"
# les joueurs de plus : 12 mois entiers
for q in ("lane hutson psa 10", "lane hutson psa 9", "cam york psa 9"):
    a = [x for x in APP if x[0] == q]
    assert a and all(x[2] == D12 and x[3] == jr(0) for x in a), (q, a)
# deux pages de suite sans le joueur : la recherche s'arrete (30 pages payees le 26 nov pour « cam york »)
assert [x[1] for x in APP if x[0] == "lane hutson psa 10"] == [1, 2], [x[:2] for x in APP if x[0].startswith("lane")]
c = banque_psa._cx()
assert c.execute("SELECT raison FROM plan WHERE q='lane hutson psa 10'").fetchone()[0] == "autres joueurs"
assert c.execute("SELECT raison FROM plan WHERE q='cam york psa 10'").fetchone()[0] == "autres joueurs"
# la phase 2 est replanifiee : la Platinum Rainbow (6 PSA 10 sur 12 mois) a maintenant sa recherche raw, sur 12 mois
p2 = c.execute("SELECT q, debut, fin, fini FROM plan WHERE phase=2 AND q LIKE '%rainbow%'").fetchall()
assert len(p2) == 1 and p2[0][1] == D12 and p2[0][2] == jr(0) and p2[0][3] == 1, p2
assert c.execute("SELECT COUNT(*) FROM ventes WHERE cle LIKE 'pl%'").fetchone()[0] == 6
c.close()
r = banque_psa._run()
assert r["version"] == 2 and r["raw_planifie"] == 1
n_app = len(APP)
assert r["credits"] == 1901 + n_app and historique.utilises()["mois"] - u0 == n_app, (r["credits"], n_app)
# relancee : plus rien a faire, rien n'est repaye
APP.clear()
b = banque_psa.collecter(plafond=10000, pause=0)
assert b["statut"] == "terminee" and APP == [] and banque_psa._run()["credits"] == 1901 + n_app

# ---- 2. une collecte NEUVE part tout de suite avec le plan a jour (12 mois), sans extension
os.environ["LOCKERROOM_DONNEES"] = comptes.DONNEES = tempfile.mkdtemp()
banque_psa._MIGRE["fait"] = False
APP.clear()
b = banque_psa.collecter(plafond=50, pause=0)
assert b["statut"] == "terminee" and banque_psa._run()["version"] == 2
assert APP and all(a[2] == D12 and a[3] == jr(0) for a in APP), APP[:3]
src = open(os.path.join(RACINE, "banque_psa.py"), encoding="utf-8").read()
assert 'if st not in ("en_cours", "interrompue", "attente_mois", "erreur"):' in src, "une collecte terminee ne repart jamais seule"
print("test_banque_psa_etendre OK")
