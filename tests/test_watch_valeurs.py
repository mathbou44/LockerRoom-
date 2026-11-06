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
vrai_fond = watchlist._chercher_en_fond
watchlist._chercher_en_fond = lambda api, items: fond.extend(x["item_id"] for x in items)
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
# la vraie recherche de fond : les ventes de la carte -> sa valeur et sa mise max
watchlist._chercher_en_fond = vrai_fond
import vendues, time
le = datetime.now().strftime("%Y-%m-%d")
vendues.memes_annonce = lambda t, n=24, fond=False: {"ventes": [{"titre": t, "prix": p, "le": le} for p in (48, 50, 52, 50)]}
watchlist._chercher_en_fond(a, [{"item_id": "3", "titre": "The Cup Roope Hintz /99"}])
for _ in range(50):
    if not watchlist._FOND["en_cours"]:
        break
    time.sleep(0.1)
L = {x["item_id"]: x for x in watchlist.liste(a)["cartes"]}
assert L["3"]["valeur"] and abs(L["3"]["mise_max"] - L["3"]["valeur"] * 0.7) < 0.02, L["3"]
# aucune vente sure : « Pas de comps », pas recherchee de nouveau avant 24 h
a._valeur_en_cache = lambda x, calculer=True: None
watchlist.ajouter(a, {"item_id": "6", "titre": "Premier Focus Auto Patch Shea Theodore /15", "total": 37, "encan": True, "fin": fin})
vendues.memes_annonce = lambda t, n=24, fond=False: {"ventes": [{"titre": t, "prix": 40, "le": le}]}
watchlist._chercher_en_fond(a, [{"item_id": "6", "titre": "Premier Focus Auto Patch Shea Theodore /15"}])
for _ in range(50):
    if not watchlist._FOND["en_cours"]:
        break
    time.sleep(0.1)
appels = []
watchlist._chercher_en_fond = lambda api, items: appels.extend(x["item_id"] for x in items)
L = {x["item_id"]: x for x in watchlist.liste(a)["cartes"]}
assert L["6"]["sans_comps"] and L["6"].get("mise_max") is None and "6" not in appels, (L["6"], appels)
watchlist._chercher_en_fond = vrai_fond
# la fiche de l'annonce donne une valeur : la watchlist la garde (jamais par-dessus une valeur deja la)
watchlist.ajouter(a, {"item_id": "5", "titre": "y carte", "total": 10, "encan": True, "fin": fin})
assert watchlist.valeur_trouvee(a, "5", 80) and not watchlist.valeur_trouvee(a, "5", 999)
print("WATCH VALEURS OK")
