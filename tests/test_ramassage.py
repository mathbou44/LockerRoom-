"""30 oct 2026 - Savage, Remi, CF31, Slab Sharks d'abord ; ramassage sur place = pas de port (python tests/test_ramassage.py)."""
import os
import sys
import tempfile

os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deals  # noqa: E402
import lockerroom  # noqa: E402

# l'ordre des recherches : chaque prioritaire seul, dans l'ordre, puis les autres en groupes
g = deals.groupes_vendeurs(["wests01", "slabsharksinc", "probstein123", "cf31_sports_cards", "Remi-Card-Trader", "savage.cards"])
assert g[:4] == [["savage.cards"], ["Remi-Card-Trader"], ["cf31_sports_cards"], ["slabsharksinc"]], g
assert g[4] == ["wests01", "probstein123"], g
assert [deals.rang_vendeur(v) for v in ("savage.cards", "remi-card-trader", "cf31_sports_cards", "slabsharksinc", "probstein123", "x")] == [0, 1, 2, 3, 4, 5]

a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
assert a.deals_vendeurs_liste()["vendeurs"][:4] == ["savage.cards", "remi-card-trader", "cf31_sports_cards", "slabsharksinc"]
r = a.deals_ramassage(["Savage.cards", "remi-card-trader", "cf31_sports_cards", "<b>"])
assert r["ramassage"] == ["b", "cf31_sports_cards", "remi-card-trader", "savage.cards"], r
chez = a._chez_ramassage()
x = {"item_id": "1", "vendeur": "savage.cards", "total": 70.0, "port": 10.0, "valeur": 100.0, "ratio": 0.7, "mise_max": 60.0}
y = a._ramasser(x, chez)
assert y["total"] == 60.0 and y["port"] == 0.0 and y["ratio"] == 0.6 and y["mise_max"] == 70.0 and y["ramassage"], y
assert x["total"] == 70.0                                                    # l'original (partage) ne change pas
z = a._ramasser(dict(x, vendeur="slabsharksinc"), chez)
assert z["total"] == 70.0 and not z.get("ramassage")
print("RAMASSAGE OK")
