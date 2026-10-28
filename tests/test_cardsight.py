"""CardSight AI (simule, aucun appel reseau) : python tests/test_cardsight.py"""
import io
import json
import os
import sys
import tempfile
import urllib.request

os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
os.environ.pop("CARDSIGHT_CLE", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cardsight  # noqa: E402

VU = []
REP = {"detections": [{"confidence": "High", "card": {"id": "c1", "name": "Macklin Celebrini", "year": "2024", "manufacturer": "Upper Deck",
       "setName": "Series 1", "number": "201", "parallelSuggestions": [{"name": "Young Guns", "confidence": "High"}]},
       "grading": {"confidence": "High", "company": {"name": "PSA"}, "grade": {"value": "10"}, "certNumber": "12345678"}}]}


class R:
    status = 200
    def __init__(self, d): self.d = d
    def read(self): return json.dumps(self.d).encode()
    def __enter__(self): return self
    def __exit__(self, *a): return False


def urlopen(req, timeout=0):
    VU.append((req.full_url, dict(req.header_items()), req.data[:200]))
    return R(REP)


urllib.request.urlopen = urlopen
img = b"\xff\xd8\xff" + b"0" * 3000
# eteint sans cle : rien ne part
assert cardsight.completer({"joueur": "X"}, ["parallele"], img) == ({"joueur": "X"}, ["parallele"], None) and not VU
os.environ["CARDSIGHT_CLE"] = "CLE-TEST"; os.environ["CARDSIGHT_QUOTA"] = "2"
r = cardsight.identifier(img)
assert r["ok"] and r["champs"]["parallele"] == "Young Guns" and r["champs"]["grade"] == "PSA 10" and r["champs"]["cert"] == "12345678", r
url, h, corps = VU[-1]
assert url == "https://api.cardsight.ai/v1/identify/card" and h.get("X-api-key") == "CLE-TEST" and b'name="image"' in corps, (url, h)
# complete : les champs douteux ou vides seulement, jamais un autre joueur
ch, reste, src = cardsight.completer({"joueur": "Macklin Celebrini", "annee": "2024-25", "parallele": "Young Gun?"}, ["parallele", "numero"], img)
assert src == "cardsight" and ch["parallele"] == "Young Guns" and ch["numero"] == "201" and ch["annee"] == "2024-25" and reste == [], (ch, reste)
# plafond du mois
assert cardsight.identifier(img)["erreur"] == "quota"
# confiance moyenne : on ne touche a rien
os.environ["CARDSIGHT_QUOTA"] = "50"; REP["detections"][0]["confidence"] = "Medium"
assert cardsight.completer({"joueur": "A"}, ["numero"], img)[2] is None
REP["detections"][0]["confidence"] = "High"; REP["detections"][0]["card"]["name"] = "Ivan Demidov"
ch, reste, _ = cardsight.completer({"joueur": "Macklin Celebrini"}, ["joueur"], img)
assert ch["joueur"] == "Macklin Celebrini" and "joueur" in reste
print("CARDSIGHT OK")
