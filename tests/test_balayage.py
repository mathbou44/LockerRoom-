"""7 nov 2026 (Mathieu : « 24 h pour les autres places que Remi, CF31 et Savage ; au moins une enchere » ; « capter toutes les
ventes fixes et encheres des petits vendeurs eBay, les deals sont surtout la »)."""
import os, sys, tempfile
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import deals

m = datetime.now(timezone.utc)
fin = lambda h: (m + timedelta(hours=h)).isoformat().replace("+00:00", "Z")
# 1. la fenetre des encans
assert deals.encan_admis({"encan": True, "fin": fin(80), "vendeur": "cf31_sports_cards", "mises": 0})
assert not deals.encan_admis({"encan": True, "fin": fin(130), "vendeur": "savage.cards", "mises": 3})
assert not deals.encan_admis({"encan": True, "fin": fin(30), "vendeur": "petitvendeur", "mises": 4})       # plus de 24 h
assert not deals.encan_admis({"encan": True, "fin": fin(5), "vendeur": "petitvendeur", "mises": 0})        # aucune mise
assert not deals.encan_admis({"encan": True, "fin": fin(5), "vendeur": "slabsharksinc", "mises": None})
assert deals.encan_admis({"encan": True, "fin": fin(5), "vendeur": "petitvendeur", "mises": 1})
assert not deals.encan_admis({"encan": True, "fin": fin(-1), "vendeur": "remi-card-trader", "mises": 2})
assert deals.encan_admis({"encan": False})
# 2. le balayage : toute la categorie hockey, les petits et moyens vendeurs, prix fixe puis encans
appels = []
T = "2024-25 Upper Deck Young Guns Ivan Demidov #451 RC"
def rech(q, categorie=None, limite=50, fond=True, encheres=False, recentes=False, flux=False, offset=0, aspects=None, **k):
    appels.append((q, categorie, encheres, offset, aspects))
    if encheres:
        return [{"item_id": "e1", "titre": T, "prix_cad": 20.0, "port_cad": 2, "encan": True, "mises": 2, "fin": fin(3),
                 "vendeur": "petit", "vendeur_score": 120, "url": "u"},
                {"item_id": "e2", "titre": T, "prix_cad": 20.0, "port_cad": 2, "encan": True, "mises": 2, "fin": fin(3),
                 "vendeur": "probstein123", "vendeur_score": 900000, "url": "u"}]
    return [{"item_id": "f1", "titre": T, "prix_cad": 30.0, "port_cad": 2, "encan": False, "vendeur": "petit", "vendeur_score": 50,
             "url": "u", "cree": m.isoformat()}]
vus = []
vrai_juger = deals._juger
deals._juger = lambda a, r, *x, **k: vus.append((a["item_id"], r["flux"]))
try:
    st = {}
    n = deals.balayer(rech, None, {}, {}, st, m, None)
finally:
    deals._juger = vrai_juger
assert n == 2 and sorted(i for i, _ in vus) == ["e1", "f1"], vus                 # le tres gros vendeur est saute
assert all(f == "petits vendeurs" for _, f in vus)
assert all(q == "" and c == "261328" and a == deals.BALAYAGE_ASPECT for q, c, _e, _o, a in appels), appels
assert [e for _q, _c, e, _o, _a in appels] == [False, True]                      # moins de 150 annonces : une page chacun
print("BALAYAGE OK")
