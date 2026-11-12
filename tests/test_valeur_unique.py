"""12 nov 2026 (Mathieu : Hasek Premier Focus Auto Gold /15, Caufield Emerald Surge Auto 1/10) : une carte tres rare avec UNE
seule vente d'un an a une valeur prudente « estimee » (75 %) ; une carte ordinaire, jamais."""
import os, sys, tempfile
from datetime import datetime, timedelta
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import deals
le = (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d")
t = "2024-25 Upper Deck Premier Focus Auto Gold Dominik Hasek #PFA-DH /15"
v = [{"titre": "2024-25 UD Premier Dominik Hasek Focus Auto Gold /15 Sabres", "prix": 328.12, "le": le, "url": "https://www.ebay.com/itm/1"}]
r = deals.valeur_ou_saison({"titre": t, "item_id": "9"}, v, [])
assert r and r[1] == "unique" and r[0] == round(328.12 * 0.75, 2), r
v2 = v + [{"titre": "Dominik Hasek 2024-25 Premier Upper Deck Focus Auto Gold /15", "prix": 427.48, "le": le, "url": "https://www.ebay.com/itm/2"}]
r2 = deals.valeur_ou_saison({"titre": t, "item_id": "9"}, v2, [])
assert r2 and r2[1] == "vendues" and abs(r2[0] - 328.12 * 0.9) < 0.02, r2
assert deals.valeur_unique({"titre": "2024-25 Upper Deck Young Guns Macklin Celebrini"}, [{"titre": "2024-25 Upper Deck Young Guns Macklin Celebrini", "prix": 90, "le": le}]) is None
print("UNIQUE OK", r, r2)
