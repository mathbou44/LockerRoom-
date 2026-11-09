"""9 nov 2026 (criteres de TAG fournis par Mathieu, taggrading.com) : la note TAG estimee avec les memes observations."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bareme as b, vision
N = lambda f: [(f, "net")] * 4
assert b.tag(N(0) + N(1), N(0) + N(1), [], ["52/48"], ["67/33"])["note"] == 10                     # Hutson : 52/48, dos 67/33
assert b.tag(N(0) + N(1), N(0) + N(1), [], ["58/42"], [])["note"] == 9                             # 58/42 : 9 (10 = 55/45)
assert b.tag(N(0) + N(1), N(0) + N(1), [], ["62/38"], [])["note"] is None                          # 62/38 : 8 ou moins
assert b.tag(N(0) + N(1), N(0) + N(1), [], [], ["72/28"])["note"] == 9                             # dos 72/28 : 9 (10 = 70/30)
assert b.tag(N(0) + [(1, "effilochage_leger")] * 2 + N(1)[2:], N(0), [], [], [])["note"] == 10     # 2 legeres touches au dos : 10
assert b.tag([(0, "effilochage_leger")] + N(0)[1:], N(0), [], [], [])["note"] == 9                 # une touche au devant : 9
assert b.tag([(0, "effilochage_leger")] * 3 + N(0)[3:], N(0), [], [], [])["note"] is None          # 3 au devant : 8 ou moins
assert b.tag(N(0), [(0, "usure_legere"), (0, "usure_legere")], [], [], [])["note"] == 9            # 2 bords legers : 9
assert b.tag(N(0), N(0), [(0, "rayure", "rasante")], [], [])["note"] == 10                         # une rayure fine : 10
assert b.tag(N(0), N(0), [(0, "pli", "rasante")], [], [])["note"] is None
f = {"coins": [{"photo": 0, "coin": c, "etat": "net", "certitude": "sure"} for c in b.COINS]
     + [{"photo": 0, "coin": "haut-gauche", "etat": "effilochage_leger", "certitude": "incertaine"}],
     "bords": [{"photo": 0, "bord": x, "etat": "net", "certitude": "sure"} for x in b.BORDS], "surface": []}
r = vision._noter_observations(f, {"devant": {"gd": "52/48"}})
assert r["tag"]["note"] == 10 and r["tag"]["bas"] == 9, r["tag"]                                   # incertaine : seulement le bas
print("OK test_tag")
# Pristine (990-1000) : 51/49 devant, 54,5/45,5 dos, tout net ; seulement si le centrage des deux faces est mesure
P = b.tag(N(0) + N(1), N(0) + N(1), [], ["51/49"], ["54/46"])
assert P["pristine"] and P["note"] == 10 and P["score"] == "990–1000", P
assert not b.tag(N(0) + N(1), N(0) + N(1), [], ["52/48"], ["54/46"]).get("pristine")
assert not b.tag(N(0) + N(1), N(0) + N(1), [], ["51/49"], []).get("pristine")                   # dos pas mesure
assert not b.tag(N(0) + N(1), N(0) + N(1), [(0, "ligne d'impression", "rasante")], ["51/49"], ["54/46"]).get("pristine")
print("OK Pristine")
# 9 nov 2026 (psacard.com, captures de Mathieu) : PSA 10 = 55/45 devant et 75/25 dos ; PSA 9 = 60/40 et 90/10
import examen
assert examen.note_centrage({"gd": "55/45"}) == 10 and examen.note_centrage({"gd": "58/42"}) == 9
assert examen.note_centrage({"gd": "60/40"}) == 9 and examen.note_centrage({"gd": "62/38"}) == 8
assert examen.note_centrage({"gd": "52/48"}, {"hb": "76/24"}) == 9 and examen.note_centrage({"gd": "52/48"}, {"hb": "75/25"}) == 10
print("OK centrage PSA")
