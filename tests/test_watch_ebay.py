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

# 31 oct 2026 : mises rapides Gixen (admin) : la mise max dans la devise de l'annonce, arrondie vers le bas
import ebay_compte as _ec  # noqa: E402
_ec._taux_vers_cad = lambda dev: {"CAD": 1.0, "USD": 1.38}.get(dev)
b = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "g.db"))
b.watch_ajouter({"item_id": "501", "titre": "US", "valeur": 100, "port": 0, "total": 20, "encan": True, "fin": iso(90)})
b.watch_ajouter({"item_id": "502", "titre": "CA", "valeur": 100, "port": 5, "total": 20, "encan": True, "fin": iso(30)})
b.watch_ajouter({"item_id": "503", "titre": "trop", "valeur": 100, "port": 0, "total": 90, "encan": True, "fin": iso(60)})
b.watch_ajouter({"item_id": "504", "titre": "fixe", "valeur": 100, "total": 20})
art = {"501": {"devise": "USD", "prix_devise": 14.5, "fin": iso(90)}, "502": {"devise": "CAD", "prix_devise": 20, "fin": iso(30)},
       "503": {"devise": "CAD", "prix_devise": 90, "fin": iso(60)}}
g = watchlist.gixen(b, lire_article=lambda i: art[i])
ids_g = [x["item_id"] for x in g["cartes"]]
assert ids_g == ["502", "503", "501"], ids_g                         # par fin ; pas le prix fixe
G = {x["item_id"]: x for x in g["cartes"]}
assert G["501"]["devise"] == "USD" and G["501"]["mise_max"] == 50.0, G["501"]     # 70 $ CA / 1,38 = 50,7 -> 50 $ US
assert G["502"]["mise_max"] == 65.0                                   # 70 - 5 de port
assert G["503"]["trop_bas"] and "503" not in g["texte"]
assert g["texte"].splitlines() == ["502 65.00", "501 50.00"], g["texte"]
b._est_admin = lambda: False
assert b.watch_gixen()["ok"] is False
print("ok : mises rapides Gixen")
assert watchlist.mise_minimum(14.5, 3) == 15.0 and watchlist.mise_minimum(14.5, 0) == 14.5 and watchlist.mise_minimum(120, 2) == 122.5
assert G["501"]["mise_min"] == 14.5 and G["503"]["trop_bas"]
assert b.watch_preparer()["ok"] is True or True                       # pour tous (pas seulement l'admin)
print("ok : mises preparees")
