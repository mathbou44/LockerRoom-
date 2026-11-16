"""16 nov 2026 (Mathieu : « les joueurs evergreen : Temple, retraites, ou exceptionnels qui jouent encore, comme Crosby,
Ovechkin, Kane (longtemps a Chicago), Datsyuk (longtemps a Detroit) ») : ils sortent evergreen ; un joueur ordinaire, non."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import evergreen as e
saisons = lambda eq, n, gp=78: [[2005 + i, eq, gp] for i in range(n)]
crosby = {"top100": True, "pos": "C", "trophees_c": {"Stanley Cup": 3, "Art Ross Trophy": 2, "Conn Smythe Trophy": 2, "Hart Memorial Trophy": 2},
          "carriere": {"gamesPlayed": 1438, "points": 1700}, "equipes": saisons("Pittsburgh Penguins", 20)}
kane = {"top100": True, "pos": "R", "trophees_c": {"Stanley Cup": 3, "Conn Smythe Trophy": 1, "Hart Memorial Trophy": 1, "Art Ross Trophy": 1},
        "carriere": {"gamesPlayed": 1300, "points": 1340}, "equipes": saisons("Chicago Blackhawks", 16) + saisons("Detroit Red Wings", 3, 50)}
datsyuk = {"hhof": True, "pos": "C", "trophees_c": {"Stanley Cup": 2, "Frank J. Selke Trophy": 3, "Lady Byng Memorial Trophy": 4},
           "carriere": {"gamesPlayed": 953, "points": 918}, "equipes": saisons("Detroit Red Wings", 14)}
mcdavid = {"pos": "C", "trophees_c": {"Hart Memorial Trophy": 3, "Art Ross Trophy": 5, "Ted Lindsay Award": 4, "Conn Smythe Trophy": 1},
           "carriere": {"gamesPlayed": 750, "points": 1100}, "equipes": saisons("Edmonton Oilers", 11)}
quatrieme = {"pos": "C", "carriere": {"gamesPlayed": 420, "points": 90}, "equipes": saisons("Arizona Coyotes", 3, 60) + saisons("Seattle Kraken", 3, 50)}
pop = {"notoriete": 85, "demande": 80, "communaute": 60}
for nom, h in (("Crosby", crosby), ("Kane", kane), ("Datsyuk", datsyuk), ("McDavid", mcdavid)):
    sc, r = e.score_de(h, pop)
    assert sc >= e.SEUIL, (nom, sc, r)
sc_k, r_k = e.score_de(kane, pop)
assert "fidele" in r_k and "gros_marche" in r_k, r_k                 # longtemps a Chicago, un gros marche
assert "fidele" in e.score_de(datsyuk)[1]
assert e.score_de(quatrieme, {"notoriete": 20, "demande": 15})[0] < 30
print("EVERGREEN OK", {n: e.score_de(h, pop)[0] for n, h in (("Crosby", crosby), ("Kane", kane), ("Datsyuk", datsyuk), ("McDavid", mcdavid))})
import score_slab as ss
assert ss.raison_de([], None, {"evergreen": True}, True) == "long_terme"
assert ss.raison_de(["en_feu"], None, {"evergreen": True}, True) == "chaud"
assert ss.raison_de([], {"ecart_pct": -20}, None, False) == "marche_bas"
assert ss.raison_de([], None, {"evergreen": True}, False) is None           # une carte de base d'un evergreen : pas « long terme »
assert ss.premium({"auto": True}) and ss.premium({"tirage": 25}) and not ss.premium({"tirage": 499}) and not ss.premium({})
print("RAISONS OK")
