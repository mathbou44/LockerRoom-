"""10 nov 2026 (licence eBay §9.5 ; Mathieu : « c'est le prix suggere qui va etre difficile ») : une carte SANS ventes
recoit un prix suggere a partir des VENTES des cartes proches (saisons voisines, autre numerotation), jamais des annonces."""
import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
from datetime import datetime, timedelta
import base_ventes
import vendues
import lockerroom

vendues.rechercher = lambda q, fond=True, usage=None: {"ventes": [], "erreur": None}     # aucun appel payant ici
j = lambda n: (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d")
base_ventes.noter("ron francis clear cut", [
    {"titre": "2023-24 Upper Deck Clear Cut Outburst Auto Ron Francis /25 Hurricanes", "prix": 100.0, "le": j(5), "url": "https://www.ebay.com/itm/100000000001"},
    {"titre": "2023-24 UD Clear Cut Outburst Autograph Ron Francis 12/25", "prix": 110.0, "le": j(20), "url": "https://www.ebay.com/itm/100000000002"},
    {"titre": "2023-24 Upper Deck Clear Cut Outburst Auto Ron Francis /25", "prix": 90.0, "le": j(40), "url": "https://www.ebay.com/itm/100000000003"},
    {"titre": "2023-24 Upper Deck Series 1 Ron Francis base #12", "prix": 1.0, "le": j(3), "url": "https://www.ebay.com/itm/100000000004"},
])
api = lockerroom.Api()
r = api._prix_similaires("2024-25 Upper Deck Clear Cut Outburst Auto Ron Francis /25", "Ron Francis")
assert r, r
val, src, n, vv = r
assert src == "autre_saison" and n == 3 and 70 <= val <= 85, r          # la mediane (100) moins 20 %
assert all("Outburst" in v["titre"] for v in vv)
# une carte de base sans ventes : rien (jamais une valeur inventee)
assert api._prix_similaires("2024-25 Upper Deck Series 1 Connor Bedard base #1", "Connor Bedard") is None
print("OK prix similaires")
