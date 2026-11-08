"""7 nov 2026 (Mathieu : « le prix de la vue generale n'est jamais le meme que dans la fiche », Snuggerud New Grooves chez
Remi : mise max 104 $ et profit +110 $ dans la watchlist, 113 $ dans la fiche) : chez un vendeur ou tu ramasses, la
watchlist compte sans le port, comme la fiche et les deals."""
import os, sys, tempfile
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom, watchlist, deals

a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "w.db"))
d = deals.lire(); d.update(deals=[], suivis=[], pres=[]); deals._ecrire(d)
fin = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
base = {"titre": "2025-26 SP Game Used New Grooves Purple Auto Patch /10 Jimmy Snuggerud", "valeur": 203, "port": 9, "total": 50,
        "encan": True, "fin": fin}
watchlist.ajouter(a, dict(base, item_id="1", vendeur="remi-card-trader"))
watchlist.ajouter(a, dict(base, item_id="2", vendeur="autre_vendeur"))
L = {x["item_id"]: x for x in watchlist.liste(a)["cartes"]}
assert L["1"]["mise_max"] == L["2"]["mise_max"] == round(deals.prix_max(203) - 9, 2), L       # pas de ramassage choisi
a.reglages_sauver({"ramassage": ["remi-card-trader"]})
L = {x["item_id"]: x for x in watchlist.liste(a)["cartes"]}
assert L["1"]["ramassage"] and L["1"]["mise_max"] == round(deals.prix_max(203), 2) == 113.08, L["1"]
assert L["1"]["profit"] == round(deals.net_revente(203) - deals.cout_achat(41), 2), L["1"]
assert not L["2"]["ramassage"] and L["2"]["mise_max"] == round(deals.prix_max(203) - 9, 2), L["2"]
assert L["2"]["profit"] == round(deals.net_revente(203) - deals.cout_achat(50), 2)
assert L["1"]["total"] == 50 and L["1"]["port"] == 9                                   # le vrai port reste en base
# le vendeur arrive aussi du chasseur (une carte ajoutee sans vendeur)
watchlist.ajouter(a, dict(base, item_id="3"))
d = deals.lire(); d["suivis"] = [dict(base, item_id="3", vendeur="Remi-Card-Trader", vu_le=datetime.now(timezone.utc).isoformat())]; deals._ecrire(d)
L = {x["item_id"]: x for x in watchlist.liste(a)["cartes"]}
assert L["3"]["ramassage"] and L["3"]["mise_max"] == 113.08, L["3"]
print("WATCH RAMASSAGE OK")
