"""26 nov 2026 (Mathieu : « si ce sont de fausses valeurs, oui, il faut les enlever ») : une carte RAW vendue comme une future 10
(« PSA 10 ? », « PSA 10 Contender », « Possible PSA 10 ») etait acceptee comme comparable d'une vraie PSA 10. Elle est refusee
quand on cherche une carte gradee. La regle est etroite : mesuree sur 52 544 ventes « PSA 10 / PSA 9 » de 120 jours, elle touche
8 ventes, toutes des raw ; une regle large (« ? » n'importe ou, « should be a 10 ») aurait enleve 45 vraies cartes gradees."""
import os, sys, tempfile, sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import cartes_match as c

YG = "2023-24 Upper Deck Connor Bedard Young Guns #451"
# des titres REELS de nos archives
ESPERENT = ["2025-26 Upper Deck Extended Beckett Sennecke Young Guns RC #701 PSA 10 Contender", "2018 Topps Stadium Club - Shohei Ohtani #138 (RC) Rookie. Def PSA 10 Worthy!",
            "2025-26 OPC Platinum Matthew Schaefer Rainbow Rookie 268 PSA 10 Candidate", "2025 Bowmans Best Hagen Smith Purple /75 Oncard Auto White Sox PSA 10 Ready",
            "Evan Bouchard Young Guns x4 (PSA 10 potential)", YG + " PSA 10?", YG + " PSA 10 ?", YG + " Possible PSA 10", YG + " potential gem mint", YG + " ungraded, PSA 10 quality"]
VRAIES = ["1990 7TH INNING SKETCH OHL #195 ERIC LINDROS WHERE IN 91? PSA 10", "2018 Bowman Chrome Shohei Ohtani Batting #1 PSA 10 Angels Dodgers HOF?",
          "2024-25 Upper Deck Young Guns Macklin Celebrini PSA 10 POSSIBLE BLACK LABEL Read", "1989 OPC #113 JOE SAKIC ROOKIE CARD PSA 9 MINT *SHOULD BE A 10*",
          "2022 Stadium Club Chrome #TOF-13 Julio Rodriguez Team of the Future PSA 9", YG + " PSA 10 GEM MINT", YG + " PSA 10 ready to ship",
          "2025-26 Upper Deck Allure #HN-12 Macklin Celebrini Hues Next? Blue PSA 10", YG + " PSA 10 POP 5", YG + " PSA 9 MINT"]
for t in ESPERENT:
    assert c.espere_note(t), t
for t in VRAIES:
    assert not c.espere_note(t), ("une vraie carte gradee ne doit jamais etre ecartee", t)

# le tri des comps : refusee pour une carte gradee ; rien d'autre ne change (la regle n'ajoute que des refus)
ref = lambda q, t: c.raisons_refus(c.cible(q), t)
assert ref("connor bedard young guns psa 10", YG + " PSA 10 Contender") == ["pas gradée (espère la note)"]
assert ref("connor bedard young guns psa 10", YG + " PSA 10?") == ["pas gradée (espère la note)"]
assert ref("connor bedard young guns psa 10", YG + " PSA 10 GEM MINT") == [] and ref("connor bedard young guns psa 10", YG + " PSA 10 HOF?") == []
assert "pas gradée (espère la note)" not in ref("connor bedard young guns psa 10", YG + " PSA 10 possible black label"), "une vraie PSA 10 (refusee avant comme « variante black » : inchange)"
assert ref("connor bedard young guns psa 9", YG + " PSA 9 MINT should be a 10") == [], "une vraie PSA 9"
assert ref("connor bedard young guns psa 10", YG + " PSA 9 Contender") == ["autre gradation"], "le refus d'avant reste le meme"
assert ref("connor bedard young guns", YG + " PSA 10 Contender") == ["gradée"], "cherchee raw : inchange (elle n'entre pas non plus dans les raw)"
assert ref("connor bedard young guns", YG + " RC") == []
ct = c.cible_titre(YG + " PSA 10 GEM MINT")                                    # les comparables d'une annonce PSA 10
assert "pas gradée (espère la note)" in c.raisons_refus(ct, YG + " PSA 10 Contender") and c.raisons_refus(ct, YG + " PSA 10") == []
assert "pas gradée" in c.raisons_refus(c.cible("connor bedard young guns graded"), YG + " PSA 10 Contender"), "« graded » : une raw qui espere n'est pas gradee"
print("REGLE OK")

# le verdict GARDE des ventes deja rangees est refait une fois (base_ventes, version 2) ; une base deja en version 1 ne refait que le nouveau
import base_ventes as b
assert b.TRI_VERSION == 2
ch = os.path.join(os.environ["LOCKERROOM_DONNEES"], "v.sqlite")
b._chemin = lambda sport=None: ch
b.noter("connor bedard young guns psa 10", [{"titre": YG + " PSA 10 Contender", "prix": 100.0, "le": "2026-11-20", "url": "https://e/1"},
                                            {"titre": YG + " PSA 10 GEM MINT", "prix": 900.0, "le": "2026-11-20", "url": "https://e/2"},
                                            {"titre": YG + " PSA 10 HOF?", "prix": 910.0, "le": "2026-11-20", "url": "https://e/3"}], sport="hockey")
b.noter("sidney crosby young guns", [{"titre": "Sidney Crosby Young Guns Renewed #YGR-10", "prix": 4.0, "le": "2026-11-20", "url": "https://e/4"}], sport="hockey")
cx = b._cx()
cx.execute("CREATE TABLE IF NOT EXISTS accepte (q TEXT, cle TEXT, ok INTEGER, PRIMARY KEY (q, cle))")
for q, cle in cx.execute("SELECT q, cle FROM ventes").fetchall():
    cx.execute("INSERT OR REPLACE INTO accepte VALUES (?,?,1)", (q, cle))
cx.execute("PRAGMA user_version = 1"); cx.commit(); cx.close()                  # la base a deja refait le tri du matin (lots, Renewed)
assert b.retrier_si_regle_change() == 1, "seul le verdict de la « PSA 10 Contender » est efface"
cx = b._cx()
reste = sorted(t for (t,) in cx.execute("SELECT v.titre FROM accepte a JOIN ventes v ON v.q = a.q AND v.cle = a.cle"))
assert reste == sorted([YG + " PSA 10 GEM MINT", YG + " PSA 10 HOF?", "Sidney Crosby Young Guns Renewed #YGR-10"]), reste
assert cx.execute("PRAGMA user_version").fetchone()[0] == 2
cx.close()
assert b.retrier_si_regle_change() == 0, "une seule fois par base"
print("OK test_espere_note")
