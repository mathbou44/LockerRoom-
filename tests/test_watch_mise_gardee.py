"""12 nov 2026 (Mathieu : « si je modifie le prix propose, c'est celui-la qui doit rester ; je veux pas mettre les prix parfaits,
quitter l'app, revenir et tous mes prix sont disparus ») : la mise ecrite dans « Miser en lot » / Gixen est gardee, dans la
devise de l'annonce, et revient exactement."""
import os, sys, tempfile
from datetime import datetime, timedelta, timezone
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lockerroom, watchlist, ebay_compte
a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
iso = lambda m: (datetime.now(timezone.utc) + timedelta(minutes=m)).isoformat().replace("+00:00", "Z")
a.watch_ajouter({"item_id": "111", "titre": "Hasek Auto /15", "valeur": 300, "port": 0, "total": 90, "encan": True, "fin": iso(300)})
a.watch_ajouter({"item_id": "222", "titre": "Caufield Emerald 1/10", "valeur": 1000, "port": 0, "total": 186, "encan": True, "fin": iso(400)})
TAUX = {"USD": 1.37, "CAD": 1.0}
ebay_compte._taux_vers_cad = lambda d: TAUX.get(d)
art = {"111": {"devise": "USD", "prix_devise": 60.0, "mises": 3, "fin": iso(300)}, "222": {"devise": "CAD", "prix_devise": 186.0, "mises": 5, "fin": iso(400)}}
lire = lambda i: art[i]
avant = {x["item_id"]: x for x in watchlist.preparer(a, lire)["cartes"]}
assert not avant["111"]["mise_perso"]
# Miser en lot : 39 $ US et 410 $ CA ecrits a la main (sauves sans relire toute la liste)
r = a.watch_mise_max("111", round(39 * 1.37, 2), 39, "USD", True)
assert r == {"ok": True}
a.watch_mise_max("222", 410, 410, "CAD", True)
# on quitte l'app et on revient : les memes montants, exactement (39 $ US, pas 38 apres conversion aller-retour)
for _ in range(2):
    apres = {x["item_id"]: x for x in watchlist.preparer(a, lire)["cartes"]}
    assert apres["111"]["mise_max"] == 39.0 and apres["111"]["devise"] == "USD" and apres["111"]["mise_perso"], apres["111"]
    assert apres["222"]["mise_max"] == 410.0 and apres["222"]["mise_perso"]
# la liste (alertes) garde l'equivalent en $ CA ; la valeur qui change ne touche pas une mise ecrite a la main
L = {x["item_id"]: x for x in a.watch_liste()["cartes"]}
assert abs(L["111"]["mise_max"] - 53.43) < 0.01 and L["111"]["mise_perso"]
# une case videe : retour a la mise conseillee
a.watch_mise_max("111", None, None, None, True)
x = {x["item_id"]: x for x in watchlist.preparer(a, lire)["cartes"]}["111"]
assert not x["mise_perso"] and x["mise_max"] == float(int(watchlist.mise_auto(watchlist.reglages(a), 300, 0) / 1.37 + 1e-6)), x
print("MISE GARDEE OK")
