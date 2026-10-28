"""29 oct 2026 - « Mes alertes » : les alertes cochees, une seule fois chacune, 3 par jour au plus sur l'iPhone, rien la nuit
(python tests/test_alarmes.py). Aucun appel reseau."""
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone

os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import alarmes  # noqa: E402
import deals  # noqa: E402
import lockerroom  # noqa: E402
import ebay_offres  # noqa: E402

D = os.environ["LOCKERROOM_DONNEES"]
a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
pushs = []
a._push = lambda t, x, d=None: pushs.append((t, d)) or 1
ebay_offres.eligibles = lambda force=False: {"ok": True, "ids": ["111", "222"]}
ebay_offres.recentes = lambda jours=3: set()

# reglages : par defaut tout est coche SAUF les alertes promotionnelles (28 oct 2026, Apple 4.5.4) ; on les coche pour la suite
r = a.alarmes_lire()["alarmes"]
assert r["gros_deal"] is False and r["en_feu"] is False and r["seuil_deal"] == 40
assert all(r[k] for k in alarmes.TYPES if k not in ("gros_deal", "en_feu"))
a.alarmes_regler({"gros_deal": True, "en_feu": True})
r = a.alarmes_regler({"vendu": False, "seuil_deal": 55, "nimporte": True})["alarmes"]
assert r["vendu"] is False and r["seuil_deal"] == 55 and "nimporte" not in r

a.carte_garder({"carte": {"joueur": "Ivan Demidov", "emplacement": "Collection", "valeur": 120}, "titre": "Demidov YG", "prix": None, "photos": []})
vid = a.carte_garder({"carte": {"joueur": "Lane Hutson"}, "titre": "Hutson YG", "prix": 40, "photos": []})["id"]
a.carte_vendre(vid, {"canal": "eBay", "prix": 55, "date": datetime.now().strftime("%Y-%m-%d")})
auj = time.strftime("%Y-%m-%d")
with open(os.path.join(D, "nhl_forme.json"), "w") as f:
    json.dump({"joueurs": {"ivan demidov": {"le": time.time(), "id": "1", "f": {"joueur": "Ivan Demidov", "matchs": 5, "buts": 4, "passes": 5, "points": 9, "dernier": auj}}}}, f)
fin = (datetime.now(timezone.utc) + timedelta(minutes=40)).isoformat().replace("+00:00", "Z")
loin = (datetime.now(timezone.utc) + timedelta(hours=20)).isoformat().replace("+00:00", "Z")
deals._ecrire({"deals": [
    {"item_id": "d1", "titre": "2025-26 Upper Deck Young Guns Ivan Demidov", "total": 30, "valeur": 100, "ratio": 0.3, "encan": False, "v": deals.VERSION},
    {"item_id": "d2", "titre": "2025-26 Upper Deck Young Guns Ivan Demidov", "total": 60, "valeur": 100, "ratio": 0.6, "encan": True, "fin": fin, "v": deals.VERSION},
    {"item_id": "d3", "titre": "2024-25 Upper Deck Young Guns Macklin Celebrini", "total": 20, "valeur": 100, "ratio": 0.2, "encan": True, "fin": loin, "v": deals.VERSION}]})
midi = datetime.now().replace(hour=12)
f1 = alarmes.verifier(a, maint=midi)
assert f1.get("gros_deal") == 1, f1               # d1 (-70 %, Demidov) ; d3 n'est pas a moi ; d2 n'atteint pas -55 %
assert f1.get("encan_fin") == 1, f1               # d2 finit dans 40 min, un joueur de mes cartes
assert f1.get("en_feu") == 1 and f1.get("acheteurs") == 1, f1
assert "vendu" not in f1, f1                       # decochee
assert len(pushs) == 3, pushs                      # 4 alertes, 3 sur l'iPhone au plus par jour
n = a.alertes_liste()["notifications"]
assert len(n) == 4 and any(x["url"] == "#offres" for x in n), n
# une seule fois chacune
assert alarmes.verifier(a, maint=midi) == {}
# la nuit : dans la cloche, pas sur l'iPhone
alarmes.regler(a, {"vendu": True})
pushs.clear()
etat = alarmes._lire(); etat["push"] = {}; alarmes._ecrire(etat)
f3 = alarmes.verifier(a, maint=datetime.now().replace(hour=23))
assert f3.get("vendu") == 1 and pushs == [], (f3, pushs)
# prix cible decochee : les alertes de prix ne tournent plus
alarmes.regler(a, {"prix_cible": False})
assert a.alertes_verifier().get("coupee")
print("ALARMES OK")
