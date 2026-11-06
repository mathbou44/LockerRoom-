"""6 nov 2026 (Mathieu : « mettre a jour les max bid dans ma watchlist au plus vite et dans les deals », une Hughes Young
Guns a 74 $ sur la tuile, 43 $ dans sa fiche) : les mises max gardees avant la regle des 30 % sont refaites."""
import os, sys, tempfile
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom, watchlist, deals

maint = datetime.now(timezone.utc)
fin = (maint + timedelta(hours=3)).isoformat()
jr = lambda k: (maint - timedelta(days=k)).isoformat()
ventes = [{"titre": "2019-20 Upper Deck Young Guns Jack Hughes #201", "prix": p, "le": jr(k)} for p, k in ((87, 1), (84, 2), (73, 8), (73, 8), (84, 12), (90, 20))]

# 1. a_jour : vieille mise max (regle des 70 %) et valeur au-dessus des 3 dernieres ventes -> refaites
x = {"item_id": "9", "titre": "2019-20 Upper Deck Young Guns Jack Hughes #201", "encan": True, "valeur": 120.0, "port": 12.0, "total": 50.0, "mise_max": 74.0, "vendues": ventes}
y = deals.a_jour(x)
assert y["valeur"] == 84.0, y["valeur"]                                    # mediane de 87, 84, 73
assert y["mise_max"] == round(deals.prix_max(84.0) - 12.0, 2) == 33.33, y["mise_max"]
assert x["mise_max"] == 74.0                                               # une copie : la liste gardee n'est pas touchee
z = deals.a_jour({"item_id": "8", "encan": True, "valeur": 80.0, "port": None, "total": 20.0, "mise_max": 60.0, "vendues": ventes[:2]})
assert z["valeur"] == 80.0 and z["mise_max"] == round(deals.prix_max(80.0) - deals.PORT_INCONNU, 2), z
assert deals.a_jour({"item_id": "7", "encan": True, "total": 5}) == {"item_id": "7", "encan": True, "total": 5}

# 2. revalider_produits : la mise max des deals gardes refaite une fois ; un prix fixe plus assez rentable sort
d = deals.lire()
d.update(revalide_v=9, deals=[dict(x, vu_le=maint.isoformat()),
                              {"item_id": "5", "encan": False, "valeur": 100.0, "total": 70.0, "port": 0, "vu_le": maint.isoformat()}],
         suivis=[{"item_id": "6", "encan": True, "valeur": 100.0, "port": 0, "total": 10, "mise_max": 70.0, "vu_le": maint.isoformat()}])
deals._ecrire(d)
deals.revalider_produits()
d = deals.lire()
par = {g["item_id"]: g for g in d["deals"] + d["suivis"]}
assert par["9"]["mise_max"] == 33.33 and par["9"].get("corrige_le"), par["9"]
assert "5" not in par                                                      # 70 $ pour 100 $ : moins de 30 % de profit
assert par["6"]["mise_max"] == round(deals.prix_max(100.0), 2), par["6"]

# 3. la watchlist : une vieille mise max par defaut suit la regle a la lecture ; celle ecrite a la main reste
a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "w.db"))
d = deals.lire(); d.update(deals=[], suivis=[], pres=[]); deals._ecrire(d)
watchlist.ajouter(a, {"item_id": "1", "titre": "Young Guns Jack Hughes", "valeur": 84, "port": 12, "total": 38, "encan": True,
                      "fin": fin, "mise_max": 74})                         # la tuile envoyait sa vieille mise max
watchlist.ajouter(a, {"item_id": "2", "titre": "Young Guns Zeev Buium", "valeur": 100, "port": 0, "total": 33, "encan": True, "fin": fin})
watchlist.mise_max(a, "2", 80)                                             # ecrite a la main
c = watchlist._cx(a); c.execute("UPDATE watchlist SET mise_max=88 WHERE item_id='1'"); c.commit(); c.close()   # une vieille
L = {x["item_id"]: x for x in watchlist.liste(a)["cartes"]}
assert L["1"]["mise_max"] == watchlist.mise_auto(watchlist.reglages(a), 84, 12) == 33.33, L["1"]
assert L["2"]["mise_max"] == 80 and L["2"]["mise_perso"], L["2"]
c = watchlist._cx(a); assert c.execute("SELECT mise_max FROM watchlist WHERE item_id='1'").fetchone()[0] == 33.33; c.close()
g = {z["item_id"]: z for z in watchlist.preparer(a, lire_article=lambda i: {})["cartes"]}
assert g["1"]["mise_max"] == 33.0, g["1"]                                  # Gixen : au dollar, vers le bas
print("MISES A JOUR OK")
