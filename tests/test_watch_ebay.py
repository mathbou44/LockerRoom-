"""31 oct 2026 - envoyer la watchlist de l'app dans la watchlist eBay (AddToWatchList / RemoveFromWatchList).
python tests/test_watch_ebay.py. Aucun appel reseau : eBay est simule."""
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ebay_compte  # noqa: E402
import lockerroom  # noqa: E402
import watchlist  # noqa: E402

a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
maint = datetime.now(timezone.utc)
iso = lambda m: (maint + timedelta(minutes=m)).isoformat().replace("+00:00", "Z")

# pas connecte a eBay : message clair, rien d'envoye
ebay_compte.statut = lambda: {"connecte": False}
a.watch_ajouter({"item_id": "111", "titre": "A", "valeur": 100, "total": 20, "encan": True, "fin": iso(60)})
r = a.watch_vers_ebay()
assert not r["ok"] and "Connecte" in r["erreur"], r

ebay_compte.statut = lambda: {"connecte": True}
for i in range(2, 14):
    a.watch_ajouter({"item_id": str(i * 111), "titre": "B", "valeur": 100, "total": 20, "encan": True, "fin": iso(60)})
a.watch_ajouter({"item_id": "999", "titre": "finie", "valeur": 100, "total": 20, "encan": True, "fin": iso(-5)})

appels = []
def faux(appel, ids):
    appels.append((appel, list(ids)))
    if "444" in ids:
        raise RuntimeError("eBay a refusé : Item 444 is already in your watch list.")
    if "555" in ids:
        raise RuntimeError("eBay a refusé : The item has ended.")
    if "666" in ids:
        raise RuntimeError("eBay a refusé : Erreur bizarre")
    return {"n": "13", "max": "400"}

r = watchlist.vers_ebay(a, appel=faux)
assert r["ok"] and r["ajoutees"] == 9 and r["deja"] == 1 and r["finies"] == 2 and len(r["erreurs"]) == 1, r
assert r["erreurs"][0] == {"item_id": "666", "erreur": "Erreur bizarre"}, r
assert r["total_ebay"] == "13" and r["max_ebay"] == "400"
assert all(len(ids) <= watchlist.PAR_APPEL for _, ids in appels)
assert not any("999" in ids for _, ids in appels)                   # la finie n'est pas envoyee
L = {x["item_id"]: x for x in a.watch_liste()["cartes"]}
assert L["111"]["ebay_le"] and L["444"]["ebay_le"] and not L["666"]["ebay_le"] and not L["999"]["ebay_le"]

# l'option « a chaque etoile » : ajout et retrait suivent sur eBay
envoyes = []
watchlist._appel_ebay = lambda appel, ids: envoyes.append((appel, list(ids))) or {"n": "1", "max": "400"}
r = a.watch_ajouter({"item_id": "7777", "titre": "C", "valeur": 100, "total": 20})
assert "ebay" not in r and not envoyes                                  # option fermee : rien sur eBay
a.watch_regler({"ebay_auto": True})
assert a.watch_liste()["reglages"]["ebay_auto"] is True
r = a.watch_ajouter({"item_id": "8888", "titre": "D", "valeur": 100, "total": 20})
assert r["ebay"] is True and envoyes[-1] == ("AddToWatchList", ["8888"]), (r, envoyes)
r = a.watch_retirer("8888")
assert r["ebay"] is True and envoyes[-1] == ("RemoveFromWatchList", ["8888"])
r = a.watch_retirer("7777")                                              # jamais envoyee : on ne touche pas a eBay
assert "ebay" not in r and envoyes[-1][1] == ["8888"]
print("ok : watchlist -> eBay")
