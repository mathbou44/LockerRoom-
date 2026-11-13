"""13 nov 2026 (Mathieu : « juste etre sur qu'on ne les manquera pas ») : les encans trouves par le Radar Pro passent aussi
par le chasseur admin (memes regles)."""
import os, sys, tempfile
from datetime import datetime, timedelta, timezone
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import deals, credits
credits.calibre = lambda j: "bon" if "lundell" in (j or "").lower() else "gris"
m = datetime.now(timezone.utc)
iso = lambda h: (m + timedelta(hours=h)).isoformat().replace("+00:00", "Z")
radar = {"ok": True,
         "pour_toi": [{"joueur": "Anton Lundell", "annonces": [
             {"item_id": "1", "titre": "2021-22 Upper Deck The Cup Rookie Auto Patch Anton Lundell /249", "prix_cad": 1.0, "port_cad": 15.0,
              "encan": True, "fin": iso(59), "mises": 2, "vendeur": "vladddddy87"}]}],
         "petits": [{"item_id": "2", "titre": "2021 The Cup Anton Lundell Signature Materials Patch Auto /99", "prix_cad": 1.0, "port_cad": 15.0,
                     "encan": True, "fin": iso(59), "vendeur": "vladddddy87"},
                    {"item_id": "3", "titre": "x fini", "prix_cad": 5.0, "encan": True, "fin": iso(-1)},
                    {"item_id": "4", "titre": "prix fixe", "prix_cad": 5.0, "encan": False}],
         "decouvrir": [{"annonces": [{"item_id": "5", "titre": "2024-25 Upper Deck Young Guns Joe Nobody", "prix_cad": 3.0, "port_cad": 2.0,
                                      "encan": True, "fin": iso(59), "vendeur": "y"}]}]}
import lockerroom
api = lockerroom.Api.__new__(lockerroom.Api)
api.RADAR_GARDE_S = 0
lockerroom.Api._radar_garder(api, None, radar)                  # le Radar Pro se garde : ses encans vont au chasseur
c = deals.candidats()
assert set(c) == {"1", "2", "5"}, c                              # pas le fini, pas le prix fixe
juges = []
vrai = deals._juger
deals._juger = lambda a, r, *x, **k: juges.append((a["item_id"], r["flux"]))
try:
    n = deals._juger_candidats({}, {}, m, None, None)
finally:
    deals._juger = vrai
assert sorted(juges) == [("1", "radar_pro"), ("2", "radar_pro")], juges   # la Young Guns d'un joueur gris a 59 h : pas admise
print("CANDIDATS OK")
