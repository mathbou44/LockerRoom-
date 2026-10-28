"""Verification PSA (API publique, simulee) : python tests/test_psa.py. Aucun appel reseau."""
import io
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request

ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ICI)
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
os.environ.pop("PSA_JETON", None)
import psa  # noqa: E402

APPELS = []


class Rep:
    def __init__(self, st, d):
        self.status, self._b = st, json.dumps(d).encode() if d is not None else b""

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


REPONSES = {}


def urlopen(req, timeout=0):
    APPELS.append((req.full_url, dict(req.header_items())))
    st, d = REPONSES[req.full_url.rsplit("/", 1)[-1]]
    if st >= 400:
        raise urllib.error.HTTPError(req.full_url, st, "x", {}, io.BytesIO(b""))
    return Rep(st, d)


urllib.request.urlopen = urlopen

# eteint sans jeton : aucun appel
r = psa.verifier("12345678")
assert not r["ok"] and r.get("inactif") and not APPELS, r
assert not psa.verifier("12")["ok"]

os.environ["PSA_JETON"] = "JETON-TEST"
assert not psa.actif()                    # jeton seul : coupe (licence commerciale requise)
os.environ["PSA_LICENCE"] = "1"
os.environ["PSA_QUOTA"] = "2"
REPONSES["12345678"] = (200, {"PSACert": {"CertNumber": "12345678", "Year": "2024", "Brand": "UPPER DECK", "Category": "HOCKEY CARDS",
                                          "CardNumber": "201", "Subject": "MACKLIN CELEBRINI", "Variety": "YOUNG GUNS",
                                          "CardGrade": "GEM MT 10", "GradeDescription": "GEM MINT 10", "TotalPopulation": 812,
                                          "PopulationHigher": 0, "IsDualCert": False}})
r = psa.verifier("1234-5678")
assert r["ok"] and r["grade"] == "PSA 10" and r["joueur"] == "Macklin Celebrini" and r["marque"] == "Upper Deck", r
assert r["numero"] == "201" and r["variante"] == "Young Guns" and r["pop"] == 812 and r["pop_plus_haute"] == 0
assert r["lien"] == "https://www.psacard.com/cert/12345678"
url, h = APPELS[-1]
assert url == "https://api.psacard.com/publicapi/cert/GetByCertNumber/12345678" and h.get("Authorization") == "bearer JETON-TEST"
# garde 30 jours : pas de 2e appel
n = len(APPELS)
assert psa.verifier("12345678")["garde"] and len(APPELS) == n
# introuvable, puis quota du jour atteint
REPONSES["99999999"] = (200, {"IsValidRequest": True, "ServerMessage": "No data found"})
r = psa.verifier("99999999")
assert not r["ok"] and "introuvable" in r["erreur"], r
REPONSES["55555555"] = (200, {"PSACert": {"CertNumber": "55555555", "CardGrade": "MINT 9"}})
r = psa.verifier("55555555")
assert not r["ok"] and "épuisées" in r["erreur"], r
# jeton refuse
os.environ["PSA_QUOTA"] = "50"
REPONSES["44444444"] = (500, None)
assert "jeton" in psa.verifier("44444444")["erreur"]
# PSA_ACTIF=0 coupe tout
os.environ["PSA_ACTIF"] = "0"
assert psa.verifier("55555555").get("inactif")
assert psa.note("NM-MT 8.5") == "8.5" and psa.note("AUTHENTIC") is None
# -- population et tendances
os.environ["PSA_ACTIF"] = "1"; os.environ["PSA_QUOTA"] = "100"
REPONSES["777"] = (200, {"PSACert": {"CertNumber": "777", "SpecID": 4242, "Year": "2024", "Brand": "UPPER DECK",
                                     "Subject": "IVAN DEMIDOV", "Variety": "YOUNG GUNS", "CardNumber": "451", "CardGrade": "GEM MT 10"}})
REPONSES["77777777"] = REPONSES["777"]
assert psa.verifier("77777777")["spec_id"] == 4242
d = psa._lire(); assert d["specs"]["4242"]["joueur"] == "Ivan Demidov"
assert psa.rafraichir_si_besoin() == 0                      # PSA_TENDANCES pas activee
os.environ["PSA_TENDANCES"] = "1"
REPONSES["4242"] = (200, {"SpecID": 4242, "Description": "2024 UD YG Demidov", "PSAPop": {"Total": 1000, "Grade10": 400, "Grade9": 450}})
assert psa.rafraichir_si_besoin() == 1 and psa.rafraichir_si_besoin() == 0   # une fois par jour
# une photo d'il y a 30 jours pour la croissance
d = psa._lire(); h = d["pops"]["4242"]["hist"]
import datetime
h.insert(0, [(datetime.date.today() - datetime.timedelta(days=30)).isoformat(), 800, 300, 380]); psa._ecrire(d)
st = psa.stats("4242")
assert st["pop10"] == 400 and st["gem_pct"] == 40 and st["nouvelles_30j"] == 200 and st["croissance_pct"] == 25.0, st
items = [{"joueur": "Ivan Demidov", "produit": "2024-25 Upper Deck Series 2", "carte": "Young Guns", "pct": 30},
         {"joueur": "Ivan Demidov", "produit": "2024-25 Upper Deck Series 2", "carte": "Canvas", "pct": 5},
         {"joueur": "Ivan Demidov", "produit": "2025-26 Upper Deck Series 1", "carte": "Young Guns", "pct": -8}]
psa.enrichir(items)
assert items[0]["psa"]["signal"] == "demande" and "psa" not in items[1] and "psa" not in items[2], items
print("PSA OK")
