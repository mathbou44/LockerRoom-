"""16 nov 2026 : un deal du Radar = une carte recherchee (SlabIQ >= 35), valeur tiree des ventes de la meme carte, pas
contredite par ses ventes connues."""
import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import lockerroom
import vendues

vendues.memes_cache = lambda t, **k: ({"nb": 5, "mediane": 2.0} if "Eichel" in t else {"nb": 0})
L = [{"item_id": "1", "titre": "Wendel Clark 87-88 OPC", "score": 11, "valeur": 30},
     {"item_id": "2", "titre": "Gretzky SP Authentic", "score": 60, "valeur": 40, "valeur_source": "approx"},
     {"item_id": "3", "titre": "Jack Eichel Outburst Silver", "score": 50, "valeur": 97, "valeur_source": "vendues"},
     {"item_id": "4", "titre": "Ivan Demidov Young Guns", "score": 69, "valeur": 45, "valeur_source": "vendues"},
     {"item_id": "5", "titre": "Celebrini Young Guns", "score": None, "valeur": 120}]
assert [x["item_id"] for x in lockerroom.Api._deals_qualite(L)] == ["4", "5"]
print("DEALS QUALITE OK")
