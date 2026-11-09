"""9 nov 2026 (Mathieu : « prioriser les deals canadiens pour un Canadien et americains pour un Americain a cause des tarifs
douaniers ») : taxes et douanes du pays de l'acheteur ; les deals de son pays d'abord. Aucun reseau."""
import os, sys, tempfile
from datetime import datetime, timezone
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deals, forfaits, lockerroom
# 1. les taxes selon le pays
assert deals.taxe_de({"lieu": "US"}, "US") == deals.TAXE_US
assert deals.taxe_de({}, "US") == deals.TAXE_US
assert abs(deals.taxe_de({"lieu": "CA"}, "US") - (deals.TAXE_US + deals.IMPORT_US)) < 1e-9
assert deals.taxe_de({"lieu": "CA"}) == deals.TAXE_ACHAT and deals.taxe_de({"lieu": "US"}) == deals.IMPORT_DEFAUT
assert deals.taxe_de({"lieu": "CA"}, "CA") == deals.TAXE_ACHAT
# 2. la liste : les deals du pays d'abord, les autres marques « etranger »
deals.chasser_si_besoin = lambda *a, **k: False
lockerroom.ebay_prix_actif = lambda: True
forfaits.est_pro = lambda: True
vu = datetime.now(timezone.utc).isoformat(timespec="seconds")
D = lambda i, lieu, tot, val: {"item_id": i, "titre": f"2015-16 Upper Deck Young Guns Connor McDavid {i}", "total": tot, "valeur": val,
                               "encan": False, "vu_le": vu, "vendeur": "petit" + i, "sport": "hockey", "port": 0, "lieu": lieu,
                               "url": "https://www.ebay.ca/itm/" + i, "rabais": round(100 * (1 - tot / val)), "ratio": tot / val, "v": deals.VERSION, "q": "mcdavid young guns"}
d = deals.lire()
d["suivis"], d["pres"] = [], []
d["deals"] = [D("u1", "US", 40, 200), D("c1", "CA", 80, 200), D("u2", "US", 50, 200), D("c2", "CA", 90, 200)]
deals._ecrire(d)
a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
a._valeur_en_cache = lambda x, calculer=True: None
def liste():
    r = a.deals_liste({})
    return [x for k in ("deals", "suivis") for x in (r.get(k) or [])]
l = liste()
ids = [x["item_id"] for x in l]
assert set(ids) >= {"c1", "c2"}, ids
if "u1" in ids:
    assert max(ids.index("c1"), ids.index("c2")) < ids.index("u1"), ids   # Canadien : le Canada d'abord
    assert next(x for x in l if x["item_id"] == "u1")["etranger"]
assert not next(x for x in l if x["item_id"] == "c1")["etranger"]
a.reglages_sauver({"pays": "US"})
l = liste(); ids = [x["item_id"] for x in l]
assert "u1" in ids and "u2" in ids, ids
assert max(ids.index("u1"), ids.index("u2")) < min(ids.index(i) for i in ("c1", "c2") if i in ids), ids   # Americain : les US d'abord
assert next(x for x in l if x["item_id"] == "u1")["taxe_achat"] == deals.TAXE_US
a.reglages_sauver({"pays": "XX"})                                                 # pays inconnu : Canada
assert not next(x for x in liste() if x["item_id"] == "c1")["etranger"]
print("OK test_pays")
