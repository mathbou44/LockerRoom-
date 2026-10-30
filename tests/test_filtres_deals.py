"""31 oct 2026 (Mathieu : « assure-toi que le filtre fonctionne lorsqu'applique ») : les filtres s'appliquent aussi aux
encans des gros vendeurs (avant : rabais minimum, une mise, prix fixe ignores pour eux). Aucun reseau."""
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deals  # noqa: E402
import forfaits  # noqa: E402
import lockerroom  # noqa: E402

deals.chasser_si_besoin = lambda *a, **k: False
forfaits.est_pro = lambda: True
m = datetime.now(timezone.utc)
iso = lambda h: (m + timedelta(hours=h)).isoformat().replace("+00:00", "Z")
vu = m.isoformat(timespec="seconds")
S = lambda i, t, tot, val=None, mises=1: {"item_id": i, "titre": t, "total": tot, "valeur": val, "encan": True, "fin": iso(3), "vu_le": vu,
                                          "vendeur": "savage.cards", "suivi": True, "mises": mises, "sport": "hockey", "port": 0}
d = deals.lire()
d["deals"], d["pres"] = [], []
d["suivis"] = [S("s1", "2020-21 Upper Deck Tim Hortons NHL Signatures Brady Tkachuk Auto", 16),          # sans valeur
               S("s2", "2005-06 UD Ultimate Collection Jersey Patch Joe Sakic", 42, val=120),            # -65 %
               S("s3", "2005-06 UD Ultimate Collection Jersey Patch Luc Robitaille", 30, val=40),        # -25 %
               S("s4", "2025-26 Upper Deck Young Guns Ivan Demidov", 20, val=60, mises=0)]               # recrue, sans mise
deals._ecrire(d)
a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
a._valeur_en_cache = lambda x, calculer=True: None
ids = lambda f: {x["item_id"] for x in a.deals_liste(f).get("suivis") or []}
assert ids({}) == {"s1", "s2", "s4"}, ids({})          # 31 oct : s3 (75 % de sa valeur) n'est pas un deal : hors ecran
assert ids({"rabais_min": 50}) == {"s2", "s4"}, ids({"rabais_min": 50})        # sans valeur ou -25 % : caches
assert ids({"avec_mise": True}) == {"s1", "s2"}
assert ids({"type": "fixe"}) == set()
assert ids({"sortes": ["patch"]}) == {"s2"}
assert ids({"joueurs": ["Sakic"]}) == {"s2"}
assert ids({"prix_max": 25}) == {"s1", "s4"}
a.deals_profil_regler({"collectionne": ["veterans"]})                           # ce que je collectionne : pas de recrues
assert "s4" not in ids({}), ids({})
a.deals_profil_regler({"collectionne": [], "prix_min": 25})
assert ids({}) == {"s2"}, ids({})
# 31 oct 2026 : un encan valorise sous 70 % compte dans le nombre de deals (s2 et s4 ; pas s3 a 75 %, pas s1 sans valeur)
a.deals_profil_regler({"collectionne": [], "prix_min": None})
r = a.deals_liste({})
assert r["n_encans_valorises"] == 2 and r["n"] >= 2, (r["n"], r.get("n_encans_valorises"))
# « Relancer le chasseur » pendant une passe : le tour est demande (et le dit), pas refuse en silence
deals.chasser_si_besoin = lambda force=False: False
deals._ETAT["proches"] = True
x = deals.recharger()
assert x["attente"] and not x["lance"] and deals.tour()["demande"], x
deals._ETAT.pop("tour_demande", None); deals._ETAT["proches"] = False
# 31 oct 2026 : les 2 dernieres heures, le prix du moment ; la mise a monte -> plus un deal, hors de l'ecran
d = deals.lire()
d["deals"] = [{"item_id": "d1", "titre": "x", "total": 20, "valeur": 100, "ratio": .2, "encan": True, "fin": iso(1), "vu_le": vu},
              {"item_id": "d2", "titre": "y", "total": 20, "valeur": 100, "ratio": .2, "encan": True, "fin": iso(1), "vu_le": vu},
              {"item_id": "d3", "titre": "z", "total": 20, "valeur": 100, "ratio": .2, "encan": True, "fin": iso(30), "vu_le": vu}]
deals._ecrire(d)
lus = []
def lot(ids):
    lus.append(list(ids))
    return {"d1": {"prix_cad": 85.0, "port_cad": 0.0, "fin": iso(1), "mises": 9}, "d2": {"prix_cad": 40.0, "port_cad": 0.0, "fin": iso(1), "mises": 4}}
r = deals.fin_proche(lire_lot=lot)
dd = {x["item_id"]: x for x in deals.lire()["deals"]}
assert r["sortis"] == 1 and "d1" not in dd and dd["d2"]["total"] == 40.0 and dd["d3"]["total"] == 20, (r, dd)
assert all("d3" not in l for l in lus)                                  # finit dans 30 h : pas relu
print("ok : filtres des deals")
