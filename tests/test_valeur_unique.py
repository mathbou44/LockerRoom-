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
assert r and r[1] == "unique" and r[0] == round(328.12 * 0.80, 2), r
v2 = v + [{"titre": "Dominik Hasek 2024-25 Premier Upper Deck Focus Auto Gold /15", "prix": 427.48, "le": le, "url": "https://www.ebay.com/itm/2"}]
r2 = deals.valeur_ou_saison({"titre": t, "item_id": "9"}, v2, [])
assert r2 and r2[1] == "vendues" and abs(r2[0] - 328.12 * 0.9) < 0.02, r2
assert deals.valeur_unique({"titre": "2024-25 Upper Deck Young Guns Macklin Celebrini"}, [{"titre": "2024-25 Upper Deck Young Guns Macklin Celebrini", "prix": 90, "le": le}]) is None
# 14 nov 2026 (la Kaprizov The Cup Scripted Swatches Auto Patch /35 chez Remi : une seule vente, il y a 15 mois) : /50 et
# moins, une vente jusqu'a 18 mois -> 60 % ; plus de 18 mois ou une carte /99 : rien
tk = "2020-21 UD THE CUP SCRIPTED SWATCHES ROOKIES AUTO PATCH /35 KIRILL KAPRIZOV"
vieux = (datetime.now() - timedelta(days=465)).strftime("%Y-%m-%d")
vk = [{"titre": "2020-21 UD The Cup Rookie Scripted Swatches Auto Patch 5/35 Kirill Kaprizov FCFZ", "prix": 438.14, "le": vieux, "url": "https://www.ebay.com/itm/3"}]
rk = deals.valeur_ou_saison({"titre": tk, "item_id": "10"}, vk, [])
assert rk and rk[1] == "unique" and rk[0] == round(438.14 * 0.65, 2), rk
trop = (datetime.now() - timedelta(days=600)).strftime("%Y-%m-%d")
assert deals.valeur_unique({"titre": tk}, [dict(vk[0], le=trop)]) is None
t99 = "2020-21 SP Authentic Future Watch Auto /99 Kirill Kaprizov"
assert deals.valeur_unique({"titre": t99}, [{"titre": t99.replace("/99", "12/99"), "prix": 200, "le": vieux}]) is None
print("UNIQUE OK", r, r2, rk)
