"""8 nov 2026 (Mathieu : « on aurait du capter ca ») : l'admin demande pourquoi une annonce n'est pas sortie."""
import os, sys, tempfile
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom, vendues, ebay_compte, deals

api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "q.db"))
assert not api.deals_pourquoi("336877908150")["ok"] or api._est_admin()       # reserve a l'admin
api._est_admin = lambda: True
T = "2026-27 UD Young Guns Porter Martone"
j = lambda k: (datetime.now() - timedelta(days=k)).strftime("%Y-%m-%d")
vendues.memes = lambda t, **k: {"ventes": [{"titre": "2026-27 Upper Deck Series 1 Young Guns Porter Martone #209 RC", "prix": p, "le": j(k), "url": f"u{k}"} for p, k in ((95, 1), (100, 2), (110, 3), (90, 4))]}
deals.bassin_partage = lambda *a, **k: type("B", (), {"candidats": lambda self, c: []})()
def lire(i, **k):
    raise RuntimeError("eBay HTTP 404 : terminée")
ebay_compte.article = lire
r = api.deals_pourquoi("https://www.ebay.ca/itm/336877908150")
assert not r["ok"] and "titre" in r["erreur"]
r = api.deals_pourquoi("https://www.ebay.ca/itm/336877908150", T, 28)
assert r["ok"] and 90 <= r["valeur"] <= 110 and "deal" in r["verdict"].lower(), r
fin = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat().replace("+00:00", "Z")
ebay_compte.article = lambda i, **k: {"item_id": i, "titre": T, "prix_cad": 28.0, "port_cad": 5.0, "encan": True, "mises": 2, "fin": fin,
                                      "vendeur": "shelbycollectibles", "vendeur_score": 6536, "lieu": "CA"}
r = api.deals_pourquoi("336877908150")
quoi = [e["quoi"] for e in r["etapes"]]
assert "Fenêtre des encans" in quoi and "Prix" in quoi and r["etapes"][quoi.index("Prix")]["ok"], r
print("POURQUOI OK")
