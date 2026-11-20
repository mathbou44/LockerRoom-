"""20 nov 2026 (Mathieu : « voir le prix final de l'encan dans la watchlist ; c'est tres important pour nos donnees ») : un
encan fini trouve son prix final (nos ventes, sinon une recherche 90 min apres la fin, 3 essais au plus), le garde, et reste
dans la watchlist tant qu'il n'est pas trouve (7 jours au plus). Aucun appel reseau."""
import os, sys, json, tempfile
from datetime import datetime, timedelta, timezone
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom, watchlist

a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
maint = datetime.now(timezone.utc)
iso = lambda m: (maint + timedelta(minutes=m)).isoformat().replace("+00:00", "Z")
a.watch_ajouter({"item_id": "123456789012", "titre": "2023-24 Upper Deck Young Guns Connor Bedard #201", "valeur": 300, "total": 150,
                 "encan": True, "fin": iso(-180), "mise_max": 200})
a.watch_ajouter({"item_id": "223456789012", "titre": "2015-16 Upper Deck Young Guns Connor McDavid #201", "valeur": 900, "total": 400,
                 "encan": True, "fin": iso(-30), "mise_max": 600})                       # fini il y a 30 min : pas encore cherche
appels = []
def cherche(q):
    appels.append(q)
    return [{"titre": "x", "prix": 999.0, "url": "https://www.ebay.com/itm/999999999999"},
            {"titre": "Bedard YG", "prix": 231.5, "url": "https://www.ebay.com/itm/2023-Bedard/123456789012?x=1"}]
assert watchlist.finales(a, rechercher=cherche) == 1 and len(appels) == 1, appels
L = {x["item_id"]: x for x in a.watch_liste()["cartes"]}
assert L["123456789012"]["final"] == 231.5 and L["223456789012"].get("final") is None, L
# pour nos donnees
l = [json.loads(x) for x in open(os.path.join(comptes.DONNEES, "finales_mises.jsonl"))]
assert l[-1]["final"] == 231.5 and l[-1]["mise_max"] is not None, l
# rien de trouve : 3 essais au plus, aux 6 h
assert watchlist.finales(a, maint=maint + timedelta(hours=2), rechercher=lambda q: []) == 0
assert watchlist.finales(a, maint=maint + timedelta(hours=3), rechercher=lambda q: 1 / 0) == 0      # trop tot (6 h)
# la purge : l'encan sans prix final reste (12 h passees), celui qui l'a sort
watchlist.purger(a, maint=maint + timedelta(hours=14))
ids = {x["item_id"] for x in a.watch_liste()["cartes"]}
assert ids == {"223456789012"}, ids
watchlist.purger(a, maint=maint + timedelta(days=8))
assert not a.watch_liste()["cartes"]
print("OK test_watch_final")
