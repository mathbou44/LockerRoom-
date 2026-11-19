"""19 nov 2026 : la chance de series (series.py) et les sets tres collectionnes (sets_cultes.py)."""
import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import series, sets_cultes

# 1) le modele : une equipe loin au-dessus de la ligne ~ 100 %, loin en dessous ~ 0 %, sur la ligne ~ 50 %
assert series.probabilite(0.20, 22, 1.0, 0.73) > 0.95
assert series.probabilite(-0.20, 22, -1.0, 0.73) < 0.05
assert 0.3 < series.probabilite(0.0, 22, 0.0, 0.73) < 0.7
# 2) le classement -> {equipe: p}
st = []
for i in range(16):
    for conf in ("E", "W"):
        st.append({"conferenceAbbrev": conf, "teamAbbrev": {"default": f"{conf}{i:02d}"}, "teamName": {"default": f"{conf}{i}"},
                   "pointPctg": 0.80 - i * 0.03, "gamesPlayed": 22, "goalDifferential": 20 - 3 * i})
eq = series.calculer(st)
assert eq["E00"]["p"] > 0.95 and eq["E15"]["p"] < 0.05 and len(eq) == 32
# 3) la pastille d'un joueur + le conseil
series._ecrire({"le": 0, "phase": "saison", "equipes": {"CHI": {"p": 0.02}, "EDM": {"p": 0.997}, "MTL": {"p": 0.52}},
                "joueurs": {"connor bedard": "CHI", "connor mcdavid": "EDM", "ivan demidov": "MTL"}})
b = series.pour_joueur("Connor Bedard"); assert b["ton"] == "rouge" and b["conseil"] == "mars" and b["effet"] <= -14, b
m = series.pour_joueur("Connor McDavid"); assert m["ton"] == "vert" and m["conseil"] == "mai" and m["p"] == 100, m
assert series.pour_joueur("Ivan Demidov")["conseil"] == "suivre"
assert series.pour_joueur("Wayne Gretzky") is None
series._ecrire({"le": 0, "phase": "hors", "equipes": {"CHI": {"p": 0.5}}, "joueurs": {"connor bedard": "CHI"}})
assert series.pour_joueur("Connor Bedard") is None                                     # hors saison : rien
assert series.conseil(1.0, "series", "vivante") == ("vert", "maintenant")
# 4) les sets cultes
I = sets_cultes.info
assert I("1979-80 O-Pee-Chee Wayne Gretzky #18 PSA 6", "Wayne Gretzky") == {"set": "1979-80 O-Pee-Chee", "cle": True}
assert I("1979-80 O-Pee-Chee Wayne Gretzky #18 Reprint", "Wayne Gretzky") is None
assert I("2015-16 Upper Deck Young Guns Connor McDavid #201", "Connor McDavid")["cle"] is True
assert I("2015-16 Upper Deck Young Guns Ryan Hartman #227", "Ryan Hartman") == {"set": "2015-16 Young Guns", "cle": False}
assert I("2017-18 Upper Deck Young Guns Nico Hischier #201", "Nico Hischier") is None   # pas une annee « culte »
assert I("2023-24 Upper Deck Extended 1st Round Draft Connor Bedard #740", "Connor Bedard") is None
assert I("2015-16 Upper Deck The Cup Connor McDavid Rookie Patch Auto /99 RPA", "Connor McDavid")["cle"] is True
assert I("2022-23 Upper Deck Series 1 Connor McDavid #1", "Connor McDavid") is None
print("OK test_series_cultes")
# 5) les pastilles arrivent dans la liste du Radar (deals_liste ET mes_deals passent par _pastilles_radar)
import lockerroom
series._ecrire({"le": 0, "phase": "saison", "equipes": {"SJS": {"p": 0.15}}, "joueurs": {"michael misa": "SJS"}})
api = lockerroom.Api()
r = api._pastilles_radar({"deals": [{"titre": "2020-21 Upper Deck The Cup Tim Stutzle Rookie Patch Auto /249", "joueur_n": "Tim Stutzle"},
                                    {"titre": "2025-26 Metal Universe PMG Blue /50 Michael Misa", "joueur_n": "Michael Misa"}], "suivis": []})
assert r["deals"][0]["culte"]["set"] == "2020-21 The Cup", r["deals"][0]
assert r["deals"][1]["culte"] is None
if lockerroom.comps_permis(api):
    assert r["deals"][1]["series"]["eq"] == "SJS", r["deals"][1]
import inspect
assert "_pastilles_radar(" in inspect.getsource(lockerroom.Api.deals_liste)
print("OK pastilles radar")
