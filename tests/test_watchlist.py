"""29 oct 2026 - la watchlist : une etoile sur un deal, une alerte 15 min avant la fin (« place ta mise ») et une si la mise
depasse la mise max ; une seule fois chacune, meme la nuit (python tests/test_watchlist.py). Aucun appel reseau."""
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import alarmes  # noqa: E402
import lockerroom  # noqa: E402
import watchlist  # noqa: E402

a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
pushs = []
a._push = lambda t, x, d=None: pushs.append((t, x)) or 1
maint = datetime.now(timezone.utc)
iso = lambda m: (maint + timedelta(minutes=m)).isoformat().replace("+00:00", "Z")

# ajouter : la mise max vient de la valeur (70 %, port compris) ; retirer ; ids
r = a.watch_ajouter({"item_id": "111", "titre": "1979-80 OPC Wayne Gretzky #18 PSA 7", "valeur": 1400, "port": 20, "total": 520,
                     "encan": True, "fin": iso(60), "url": "https://www.ebay.com/itm/111"})
assert r["ok"] and r["ids"] == ["111"], r
a.watch_ajouter({"item_id": "222", "titre": "2019-20 The Cup Gretzky Auto Patch /25", "valeur": 1000, "port": 0, "total": 300,
                 "encan": True, "fin": iso(300), "mise_max": 700})
a.watch_ajouter({"item_id": "333", "titre": "Lemieux OPC RC BGS 8.5", "valeur": 900, "total": 400, "encan": True, "fin": iso(-30)})
a.watch_ajouter({"item_id": "444", "titre": "x", "valeur": 100, "total": 50})
assert sorted(a.watch_retirer("444")["ids"]) == ["111", "222", "333"]
L = {x["item_id"]: x for x in a.watch_liste()["cartes"]}
assert L["111"]["mise_max"] == 960.0 and L["111"]["etat"] == "ok" and 55 <= L["111"]["reste_min"] <= 60
assert L["333"]["etat"] == "fini"
assert [x["item_id"] for x in a.watch_liste()["cartes"]][-1] == "333"          # les finies a la fin

# 5 min plus tard (encans qui finissent dans 75 min seulement) : 111 a 12 min de la fin, mise encore rentable -> « place ta mise »
prix = {"111": 700.0, "222": 800.0}
lus = []
def lire(i):
    lus.append(i)
    return {"prix_cad": prix[i], "port_cad": 20.0 if i == "111" else 0.0, "fin": iso(12) if i == "111" else iso(300)}
heure_nuit = datetime(2026, 10, 29, 23, 30)                       # la nuit : part quand meme (demande par l'utilisateur)
n = watchlist.verifier(a, proches=True, lire_article=lire, maint=maint)
assert lus == ["111"], lus                                          # 222 finit dans 5 h : pas relue
assert n == 1 and "place ta mise" in pushs[-1][0], pushs
assert watchlist.verifier(a, proches=True, lire_article=lire, maint=maint) == 0          # une seule fois

# la mise monte au-dessus de la mise max -> « plus rentable » (une fois)
prix["111"] = 1100.0
assert watchlist.verifier(a, proches=True, lire_article=lire, maint=maint) == 1
assert "dépasse ta mise max" in pushs[-1][1], pushs[-1]
assert {x["item_id"]: x for x in a.watch_liste()["cartes"]}["111"]["etat"] == "depasse"
assert watchlist.verifier(a, proches=True, lire_article=lire, maint=maint) == 0

# la boucle de l'heure relit 222 (ancienne) : 800 $ > mise max 700 -> alerte ; la nuit et au-dela du quota de 3 : part quand meme
for k in range(3):
    alarmes._notifier(a, alarmes._lire(), f"autre{k}", "x", "y", "#")
n0 = len(pushs)
from unittest import mock  # noqa: E402
with mock.patch.object(alarmes, "_heure_locale", lambda m=None: 23):
    a_maj = watchlist.verifier(a, proches=False, lire_article=lire, maint=maint + timedelta(minutes=90))
assert a_maj >= 1 and len(pushs) > n0, (a_maj, pushs[n0:])

# 29 oct 2026 : les reglages de l'utilisateur (defaut 15 min / 70 %), et une mise max a la main pour une carte
assert a.watch_liste()["reglages"] == {"fin_min": 15, "ratio_pct": 70, "alerte_fin": True, "alerte_seuil": True, "ebay_auto": False, "garder_h": 12}
a.watch_ajouter({"item_id": "555", "titre": "Crosby YG", "valeur": 1000, "port": 0, "total": 300, "encan": True, "fin": iso(25)})
a.watch_ajouter({"item_id": "666", "titre": "Ovechkin YG", "valeur": 1000, "port": 0, "total": 300, "encan": True, "fin": iso(25)})
a.watch_mise_max("666", 450)
r = a.watch_regler({"ratio_pct": 60, "fin_min": 30, "alerte_seuil": False})
assert r["ratio_pct"] == 60 and r["fin_min"] == 30 and r["alerte_seuil"] is False
L = {x["item_id"]: x for x in a.watch_liste()["cartes"]}
assert L["555"]["mise_max"] == 600.0 and L["666"]["mise_max"] == 450.0, (L["555"]["mise_max"], L["666"]["mise_max"])
assert a.watch_regler({"fin_min": 7})["fin_min"] == 30                         # seulement les choix offerts
n0 = len(pushs)
watchlist.verifier(a, proches=True, lire_article=lambda i: {"prix_cad": 300.0, "port_cad": 0.0, "fin": iso(25)}, maint=maint)
assert any("place ta mise" in t for t, _x in pushs[n0:]), pushs[n0:]           # 25 min : alerte, car reglee a 30 min
a.watch_regler({"alerte_fin": False})
a.watch_ajouter({"item_id": "777", "titre": "McDavid YG", "valeur": 1000, "total": 300, "encan": True, "fin": iso(20)})
n0 = len(pushs)
watchlist.verifier(a, proches=True, lire_article=lambda i: {"prix_cad": 300.0, "port_cad": 0.0, "fin": iso(20)}, maint=maint)
assert not any("777" in str(x) or "McDavid" in str(x) for x in pushs[n0:]), pushs[n0:]
assert {x["item_id"]: x for x in a.watch_mise_max("666", None)["cartes"]}["666"]["mise_max"] == 600.0
print("WATCHLIST OK")
