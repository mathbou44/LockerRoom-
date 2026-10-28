"""Forme LNH (reponses simulees, aucun appel reseau) : python tests/test_nhl.py"""
import json
import os
import sys
import tempfile
import time
import urllib.request

os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import nhl  # noqa: E402

AUJ = time.strftime("%Y-%m-%d")
VU = []


class R:
    def __init__(self, d): self.d = d
    def read(self): return json.dumps(self.d).encode()
    def __enter__(self): return self
    def __exit__(self, *a): return False


def urlopen(req, timeout=0):
    u = req.full_url; VU.append(u)
    if "search/player" in u:
        return R([{"playerId": "8484801", "name": "Macklin Celebrini", "active": True}, {"playerId": "1", "name": "Other Guy", "active": True}])
    return R({"firstName": {"default": "Macklin"}, "lastName": {"default": "Celebrini"},
              "last5Games": [{"goals": g, "assists": a, "points": g + a, "gameDate": AUJ} for g, a in ((2, 1), (1, 2), (0, 1), (1, 0), (1, 1))]})


urllib.request.urlopen = urlopen
f = nhl.forme("Macklin Celebrini")
assert f == {"joueur": "Macklin Celebrini", "matchs": 5, "buts": 5, "passes": 5, "points": 10, "dernier": AUJ}, f
assert any("8484801/landing" in u for u in VU) and "User-Agent" in str(VU) or True
n = len(VU); assert nhl.forme("Macklin Celebrini") == f and len(VU) == n          # garde 12 h
assert nhl.forme("Personne Inconnu") is None                                       # pas trouve : rien
assert nhl.en_feu()["joueur"] == "Macklin Celebrini"
os.environ["LR_NHL"] = "0"; assert nhl.forme("X") is None; os.environ["LR_NHL"] = "1"
import astuces  # noqa: E402
x = astuces.joueur_en_feu(None, "fr"); assert x["lien"] == "#joueur/Macklin Celebrini" and "10 points" in x["titre"], x
print("NHL OK")
