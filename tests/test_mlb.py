"""13 nov 2026 : le baseball (statsapi.mlb.com) : liste, fiche, recrue, joueur d'un titre, moisson a part."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = tempfile.mkdtemp()
from datetime import date
import mlb, base_ventes, thecardapi

L = mlb.lire_liste([{"id": 694192, "fullName": "Konnor Griffin", "birthDate": "2006-04-24", "primaryPosition": {"abbreviation": "SS"},
                     "currentTeam": {"id": 452}}, {"id": 660271, "fullName": "Shohei Ohtani", "mlbDebutDate": "2018-03-29"},
                    {"id": 665489, "fullName": "Vladimir Guerrero Jr."}, {"fullName": "sans id"}], "AA")
assert set(L) == {"konnor griffin", "shohei ohtani", "vladimir guerrero"}, L
mlb._ecrire("mlb_joueurs.json", {"le": 9e12, "joueurs": L, "equipes": {"141": {"abbr": "TOR", "nom": "Toronto Blue Jays", "niveau": "MLB"}}})
assert mlb.joueur_du_titre("2025 Bowman Chrome 1st Bowman Auto KONNOR GRIFFIN /99")["id"] == 694192
assert mlb.joueur_du_titre("Vladimir Guerrero Jr. 2019 Topps Chrome RC PSA 10")["id"] == 665489
assert mlb.joueur_du_titre("Connor McDavid Young Guns") is None

def sp(an, grp, st, team="Toronto Blue Jays"):
    d = {"season": str(an), "stat": st, "sport": {"id": 1}}
    if team:
        d["team"] = {"name": team}
    return d
p = {"id": 1, "fullName": "Jeune Lanceur", "active": True, "currentTeam": {"id": 141}, "primaryPosition": {"abbreviation": "P"},
     "birthDate": "2002-05-01", "mlbDebutDate": "2025-09-01", "primaryNumber": "48",
     "drafts": [{"year": "2023", "pickRound": "1", "pickNumber": 20}],
     "awards": [{"name": "AL Rookie of the Year", "season": "2026"}, {"name": "AL All-Star"}, {"name": "Rookie of the Year MiLB"}],
     "stats": [{"type": {"displayName": "yearByYear"}, "group": {"displayName": "pitching"},
                "splits": [sp(2025, "pitching", {"gamesPlayed": 6, "inningsPitched": "30.1", "strikeOuts": 35, "earnedRuns": 10}),
                           sp(2026, "pitching", {"gamesPlayed": 30, "inningsPitched": "170.2", "strikeOuts": 200, "earnedRuns": 50}),
                           sp(2026, "pitching", {"gamesPlayed": 1, "inningsPitched": "5.0"}, team=None) if False else
                           {"season": "2026", "stat": {}, "sport": {"id": 11}, "team": {"name": "Buffalo Bisons"}}]}]}
f = mlb.lire_fiche(p, mlb.equipes())
assert f["equipe"] == "TOR" and f["lanceur"] and f["chandail"] == "48" and f["repech"] == 20 and f["an_repech"] == 2023
assert f["trophees_c"] == {"recrue": 1, "etoile": 1}, f["trophees_c"]
assert [e["s"] for e in f["par_saison"]] == [2025, 2026] and abs(f["par_saison"][0]["ip"] - 30.3) < 0.05
assert f["par_saison"][1]["era"] == round(9 * 50 / (170 + 2 / 3), 2)
d26 = date(2026, 11, 13)
assert mlb.saison(d26) == 2026 and mlb.saison(date(2027, 2, 1)) == 2026 and mlb.saison(date(2027, 3, 20)) == 2027
assert mlb.recrue(f, d26)                                   # 30 manches avant 2026 (< 50) et il a lance en 2026
assert not mlb.recrue(f, date(2027, 4, 10))                 # 2027 : 200 manches avant -> plus recrue
# un echange : la ligne sans equipe = le total ; les equipes notees
p2 = {"id": 2, "fullName": "Frappeur", "active": True, "stats": [{"type": {"displayName": "yearByYear"}, "group": {"displayName": "hitting"},
      "splits": [sp(2026, "hitting", {"gamesPlayed": 60, "atBats": 200, "homeRuns": 10}, "A"), sp(2026, "hitting", {"gamesPlayed": 50, "atBats": 180, "homeRuns": 8}, "B"),
                 sp(2026, "hitting", {"gamesPlayed": 110, "atBats": 380, "homeRuns": 18, "ops": ".800"}, None)]}]}
f2 = mlb.lire_fiche(p2)
e = f2["par_saison"][0]
assert e["ab"] == 380 and e["hr"] == 18 and e["gp"] == 110 and e["equipes"] == ["A", "B"], e
assert not mlb.recrue({"par_saison": [{"s": 2025, "ab": 150, "gp": 40}, {"s": 2026, "ab": 300, "gp": 90}]}, d26)
assert mlb.recrue({"par_saison": [{"s": 2025, "ab": 120, "gp": 30}, {"s": 2026, "ab": 300, "gp": 90}]}, d26)
assert mlb.prospect({"par_saison": [], "niveau": "AA"}) and not mlb.prospect(f)
# la base du baseball est a part : rien ne se mele au hockey
base_ventes.noter("moisson baseball", [{"titre": "2025 Topps Chrome Paul Skenes", "prix": 50, "le": "2026-11-12", "url": "u1"}], sport="baseball")
base_ventes.noter("young guns", [{"titre": "Demidov Young Guns", "prix": 90, "le": "2026-11-12", "url": "u2"}])
assert base_ventes.nombre("baseball") == 1 and base_ventes.nombre() == 1 and base_ventes.nombre("hockey") == 1
# le budget de la moisson : le baseball a sa part, le hockey ne la mange pas
os.environ["THECARDAPI_CLE"] = "x"
thecardapi._compter(900, "moisson_baseball")
assert not thecardapi._budget_ok("moisson_baseball", 100)         # 20 % x 93 % x 4950 = 920
thecardapi._compter(3700, "moisson")
assert not thecardapi._budget_ok("moisson", 100) and thecardapi._budget_ok("tap", 100)
# CompSniper : les autres sports ensemble, 15 % du mois au plus
import historique
os.environ.update(COMPSNIPER_CLE="x", LR_HISTORIQUE_MOIS="100")
for _ in range(15):
    historique._compter(False, "baseball")
historique._compter(False, "hockey")
assert historique.utilises_sports() == 15 and historique.utilises()["mois"] == 16
assert historique.rechercher("paul skenes topps chrome", sport="baseball") == ([], "budget")
# l'ecran baseball : le resume d'un joueur (jamais un prix)
import lockerroom
r = lockerroom._bb_resume(f, "jeune lanceur", 12)
assert r["lanceur"] and r["ligne"]["s"] == 2026 and r["ligne"]["so"] == 200 and r["ventes"] == 12 and "prix" not in r
assert lockerroom._bb_resume(None, "inconnu total", 3)["fiche"] is False
print("OK test_mlb")
