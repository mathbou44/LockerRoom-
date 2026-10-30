"""31 oct 2026 - une Bedard « 08-09 UD Retro » PSA 10 valait 908 $ (les ventes de SA Young Guns de base) : le produit
nomme par la carte (Retro...) doit etre dans chaque comparable ; les deals gardes sont rejuges une fois."""
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cartes_match  # noqa: E402
import deals  # noqa: E402

RETRO = "2023-24 UD Extended Series 08-09 UD Retro Rookie Young Guns Connor Bedard PSA 10"
BASE = "2023-24 Upper Deck Series 2 Young Guns Connor Bedard #451 PSA 10"
RETRO_V = "2023 Upper Deck Extended Connor Bedard 08-09 UD Retro Young Guns #T47 PSA 10"
assert cartes_match.raisons_refus(cartes_match.cible_titre(RETRO), BASE)            # la base n'est pas un comparable
assert not cartes_match.raisons_refus(cartes_match.cible_titre(RETRO), RETRO_V)     # la meme Retro, oui
assert cartes_match.raisons_refus(cartes_match.cible_titre(BASE), RETRO_V)          # et l'inverse

f = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat().replace("+00:00", "Z")
vb = [{"titre": BASE, "prix": p, "le": "2026-10-2%d" % i} for i, p in enumerate([900, 910, 905, 915])]
vr = [{"titre": RETRO_V, "prix": p, "le": "2026-10-2%d" % i} for i, p in enumerate([282, 318])]
deals._ecrire({"deals": [{"item_id": "1", "titre": RETRO, "total": 369, "valeur": 908, "vendues": vb + vr},
                         {"item_id": "2", "titre": BASE, "total": 400, "valeur": 908, "vendues": vb}],
               "suivis": [{"item_id": "3", "titre": RETRO, "total": 200, "valeur": 908, "vendues": vb, "encan": True, "fin": f}]})
r = deals.revalider_produits()
d = deals.lire()
assert [x["item_id"] for x in d["deals"]] == ["2"], d["deals"]
assert not d["suivis"][0].get("valeur")
assert deals.revalider_produits() == {"fait": False}          # une seule fois
print("OK test_meme_produit")
