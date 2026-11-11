"""13 nov 2026 (Mathieu : « pourquoi aussi haut le score ? », « on devrait TOUJOURS avoir toute l'info ») : « LOW POP /5 »
n'est pas un tirage ; le nom du joueur est nettoye des mots de set ; la carriere d'un joueur retraite est lue (hors ligne)."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import cartes_match, nhl
t = "1985/86 OPC #33 Terry Ruskowski PSA 8 Mint Pittsburgh Penguins LOW POP /5"
assert cartes_match.decoder(t)["serie"] is None and cartes_match.numero_serie(t) is None
assert cartes_match.decoder("Pop 1 of 3 PSA 10 McDavid")["serie"] is None
assert cartes_match.decoder("2023 Bedard Gold /10 PSA 9")["serie"] == 10
assert cartes_match.numero_serie("McDavid 12/99 auto") == (12, 99)
assert nhl.nom_propre("Alexei Semenov BAP") == "Alexei Semenov"
assert nhl.nom_propre("Connor McDavid") == "Connor McDavid"
rep = {"search": [{"name": "Alexei Smirnov", "playerId": "1"}], "search2": [{"name": "Alexei Semenov", "playerId": "8467909"}],
       "landing": {"firstName": {"default": "Alexei"}, "lastName": {"default": "Semenov"}, "isActive": False, "position": "D",
                   "careerTotals": {"regularSeason": {"gamesPlayed": 211, "goals": 7, "assists": 26, "points": 33}},
                   "seasonTotals": [{"leagueAbbrev": "NHL", "gameTypeId": 2, "season": 20022003, "teamName": {"default": "Edmonton Oilers"}},
                                    {"leagueAbbrev": "NHL", "gameTypeId": 2, "season": 20082009, "teamName": {"default": "San Jose Sharks"}}],
                   "draftDetails": {"year": 1999, "overallPick": 36, "teamAbbrev": "EDM"}},
       "wiki": {"type": "standard", "description": "Russian ice hockey player", "extract": "Alexei Semenov is a Russian former defenceman. He played in the NHL.",
                "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/x"}}}}
def faux(url):
    if "search" in url:
        return rep["search"] if "Alexei+Semenov" in url else rep["search2"]
    if "landing" in url:
        return rep["landing"]
    if "wikipedia" in url:
        return rep["wiki"]
nhl._get = faux
c = nhl.carriere("Alexei Semenov BAP")
assert c["nom"] == "Alexei Semenov" and c["points"] == 33 and c["mj"] == 211 and c["saisons"] == ["2002", "2009"], c
assert c["repechage"]["rang"] == 36 and c["bio"]["texte"].startswith("Alexei Semenov") and c["actif"] is False, c
nhl._get = lambda url: (_ for _ in ()).throw(AssertionError("le cache aurait du servir"))
assert nhl.carriere("Alexei Semenov")["points"] == 33
print("OK infos joueur")
