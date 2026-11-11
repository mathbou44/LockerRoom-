"""11 nov 2026 (Mathieu : « un visuel de TOUS les deals du chasseur pour l'admin ; il s'est passe quelque chose ») : chaque
carte gardee, montree ou cachee, avec la regle qui la cache. Aucun reseau."""
import os, sys, tempfile
from datetime import datetime, timedelta, timezone
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deals, lockerroom
deals.chasser_si_besoin = lambda *a, **k: False
m = datetime.now(timezone.utc)
iso = lambda h: (m + timedelta(hours=h)).isoformat().replace("+00:00", "Z")
vu, vieux = m.isoformat(timespec="seconds"), (m - timedelta(hours=8)).isoformat(timespec="seconds")
D = lambda i, v, enc=True, h=3, mises=1, tot=40, val=120, vu_=vu, **k: {"item_id": i, "titre": f"2015-16 Upper Deck Young Guns Connor McDavid #201 {i}",
    "total": tot, "valeur": val, "ratio": tot / val if val else None, "encan": enc, "fin": iso(h) if enc else None, "vu_le": vu_, "vendeur": v, "mises": mises,
    "sport": "hockey", "port": 0, "n": 3, "vendues": [], "v": deals.VERSION, **k}
d = deals.lire()
d["deals"] = [D("a1", "savage.cards", h=60, mises=0),                 # Savage : 60 h, sans mise -> visible
              D("a2", "petitvendeur", h=30, mises=0, vendeur_score=40),  # petit : 30 h sans mise -> cache (encan)
              D("a3", "petitvendeur", h=5, vu_=vieux, vendeur_score=40), # pas revu depuis 8 h
              D("a4", "dcsports87", enc=False, tot=200)]                 # prix fixe au-dessus du max
d["suivis"] = [D("s1", "remi-card-trader", val=None, suivi=True)]        # sans valeur
deals._ecrire(d)
a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
a._est_admin = lambda reel=False: True
r = a.deals_admin_tout()
c = {x["item_id"]: x["cache"] for x in r["deals"]}
assert c == {"a1": None, "a2": "encan", "a3": "vieux", "a4": "monte", "s1": "sans_valeur"}, c
g = {x["item_id"]: x["groupe"] for x in r["deals"]}
assert g["a1"] == "savage.cards" and g["s1"] == "remi-card-trader" and g["a4"] == "fin" and g["a2"] == "petits", g
assert r["compte"]["visible"] == 1 and r["deals"][0]["item_id"] == "a1"
a._est_admin = lambda reel=False: False
assert not a.deals_admin_tout()["ok"]
print("DEALS ADMIN TOUT OK")
