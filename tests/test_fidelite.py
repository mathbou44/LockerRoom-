"""13 nov 2026 (Mathieu : « longue carriere dans la meme equipe, gros bassin de partisans ») : la fidelite a une franchise
(franchises demenagees ensemble), et l'explication dans « Pourquoi ce score »."""
import os, sys, tempfile
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import score_modele as sm
yz = [[19831984 + 10001 * i, "Detroit Red Wings", 80] for i in range(22)]
assert sm.fidelite(yz)[:3] == ("DET", 1.0, 22)
sakic = [[19881989, "Quebec Nordiques", 70], [19891990, "Quebec Nordiques", 80], [19951996, "Colorado Avalanche", 82]]
assert sm.fidelite(sakic)[0] == "COL" and sm.fidelite(sakic)[1] == 1.0          # Nordiques = Avalanche
assert sm.fidelite([[20202021, "Toronto Maple Leafs", 40]]) is None                # trop peu de matchs
v = sm.numeriques3({"eqs": yz})
assert v[0] == 1.0 and v[1] == 22 and v[2] == 2 and v[4] == 3.0
assert sm.numeriques4({"chandail": 87, "serie": 99, "num": 87}) == [1.0, 0.0]
assert sm.numeriques4({"chandail": 77, "serie": 77, "num": 24}) == [0.0, 1.0]
import score_appris
assert not score_appris.FID and not score_appris.CHANDAIL                          # au banc : pas mieux -> coupes par defaut
import lockerroom, demande_legale as dl
dl.lire = lambda: {"joueurs": {"Steve Yzerman": {"nhl": {"equipes": yz}}}}
a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
r = a.annonce_score("1984-85 O-Pee-Chee Steve Yzerman #67 RC PSA 8", "Steve Yzerman")
f = (r.get("pourquoi") or {}).get("fidelite")
assert f and f["equipe"] == "Detroit Red Wings" and f["saisons"] == 22 and f["toute"] and f["gros_marche"], r.get("pourquoi")
print("FIDELITE OK")
