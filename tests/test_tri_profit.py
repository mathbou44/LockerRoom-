"""31 oct 2026 (Mathieu : « en plus gros profit, des gros profits dans le bas ») : en tri profit, un seul classement
(recrues et veterans melanges) ; la section veterans d'abord reste pour le tri par defaut. Aucun reseau."""
import os
import sys
import tempfile
from datetime import datetime, timezone
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deals  # noqa: E402
import forfaits  # noqa: E402
import lockerroom  # noqa: E402

deals.chasser_si_besoin = lambda *a, **k: False
deals.valide = lambda x: True
forfaits.est_pro = lambda: True
vu = datetime.now(timezone.utc).isoformat(timespec="seconds")
D = lambda i, t, tot, val: {"item_id": i, "titre": t, "total": tot, "valeur": val, "ratio": tot / val, "encan": False, "vu_le": vu,
                            "source": "marche", "sport": "hockey", "url": "u", "v": deals.VERSION}
deals._ecrire({"deals": [D("r", "2025-26 Upper Deck Young Guns Matthew Schaefer #451", 80, 300),      # recrue : gros profit
                         D("v", "2005-06 UD Ultimate Collection Jersey Patch Joe Sakic", 20, 60)]})   # veteran : petit
a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "t.db"))
a._valeur_en_cache = lambda x, calculer=True: None
ids = lambda f: [x["item_id"] for x in a.deals_liste(f)["deals"]]
assert ids({"tri": "gain"}) == ["r", "v"], ids({"tri": "gain"})
assert ids({"tri": "rabais"}) == ["v", "r"], ids({"tri": "rabais"})
print("OK test_tri_profit")
