"""5 nov 2026 (« pourquoi il n'y a aucune mise max ? il faut que ca refresh ») : une carte de la watchlist ajoutee sans
valeur prend celle du chasseur (ou des ventes connues) et sa mise max suit ; sinon elle se calcule en fond."""
import os, sys, tempfile
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom, watchlist, deals

a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "w.db"))
fin = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
for i, t in (("1", "2023-24 Ice Sub-Zero Tyson Foerster RC Auto"), ("2", "Black Diamond Jack Quinn Auto Patch"), ("3", "The Cup Roope Hintz /99")):
    watchlist.ajouter(a, {"item_id": i, "titre": t, "total": 10, "encan": True, "fin": fin})
d = deals.lire(); d["suivis"] = [{"item_id": "1", "valeur": 100.0, "vu_le": "2000-01-01"}]; deals._ecrire(d)
a._valeur_en_cache = lambda x, calculer=True: (60.0, 4) if x["item_id"] == "2" else None
fond = []
a._valeurs_en_fond = lambda items: fond.extend(x["item_id"] for x in items)
L = {x["item_id"]: x for x in watchlist.liste(a)["cartes"]}
assert L["1"]["valeur"] == 100.0 and L["1"]["mise_max"] == 70.0, L["1"]
assert L["2"]["valeur"] == 60.0 and L["2"]["mise_max"] == 42.0, L["2"]
assert L["3"].get("valeur") is None and fond == ["3"], (L["3"], fond)
# garde : la prochaine lecture les a deja (sans chasseur ni cache)
d = deals.lire(); d["suivis"] = []; deals._ecrire(d)
a._valeur_en_cache = lambda x, calculer=True: None
L = {x["item_id"]: x for x in watchlist.liste(a)["cartes"]}
assert L["1"]["mise_max"] == 70.0 and L["2"]["mise_max"] == 42.0
# une mise ecrite a la main n'est jamais remplacee
watchlist.ajouter(a, {"item_id": "4", "titre": "x carte", "total": 10, "encan": True, "fin": fin, "mise_max": 25})
watchlist.mise_max(a, "4", 25)
a._valeur_en_cache = lambda x, calculer=True: (200.0, 5)
L = {x["item_id"]: x for x in watchlist.liste(a)["cartes"]}
assert L["4"]["valeur"] == 200.0 and L["4"]["mise_max"] == 25, L["4"]
print("WATCH VALEURS OK")
