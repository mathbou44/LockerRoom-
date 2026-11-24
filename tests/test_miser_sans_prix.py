"""24 nov 2026 (Mathieu, vue Pro, capture : « Ca me sort ca quand je veux bid in a batch » : « No auction to bid on right now
(ended, or already over your max bid) » avec 5 encans en cours). Depuis le 16 nov, un compte sans l'outil de prix (Gratuit,
Pro) n'a plus de mise max conseillee, et la preparation des mises sautait tout encan sans mise max : « Miser » et « Miser
en lot » ne menaient nulle part. Un encan sans mise max est maintenant prepare aussi (l'utilisateur ecrit son montant), et
la mise qu'il a ecrite lui-meme revient. Aucune valeur ni mise conseillee ne sort pour autant."""
import os, sys, tempfile
from datetime import datetime, timedelta, timezone
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lockerroom, watchlist, ebay_compte
a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
iso = lambda m: (datetime.now(timezone.utc) + timedelta(minutes=m)).isoformat().replace("+00:00", "Z")
a.watch_ajouter({"item_id": "111", "titre": "Tableau Rookie Watch Schaefer /999", "valeur": 300, "port": 0, "total": 23, "encan": True, "fin": iso(250)})
a.watch_ajouter({"item_id": "222", "titre": "Young Guns Canvas Caufield PSA 10", "port": 0, "total": 25, "encan": True, "fin": iso(380)})
a.watch_ajouter({"item_id": "333", "titre": "Prix fixe", "port": 0, "total": 40, "encan": False})
a.watch_ajouter({"item_id": "444", "titre": "Encan fini", "port": 0, "total": 40, "encan": True, "fin": iso(-30)})
TAUX = {"USD": 1.40, "CAD": 1.0}
ebay_compte._taux_vers_cad = lambda d: TAUX.get(d)
art = {"111": {"devise": "CAD", "prix_devise": 23.0, "mises": 4, "fin": iso(250)}, "222": {"devise": "USD", "prix_devise": 18.0, "mises": 0, "fin": iso(380)}}
lire = lambda i: art[i]
prix = {"ok": True}
lockerroom.ebay_prix_actif = lambda *x, **k: prix["ok"]

# 1. un compte SANS l'outil de prix (Gratuit, Pro) : les deux encans en cours sont prepares, sans mise max ni valeur
prix["ok"] = False
r = watchlist.preparer(a, lire)
C = {x["item_id"]: x for x in r["cartes"]}
assert set(C) == {"111", "222"}, C.keys()                                        # ni le prix fixe, ni l'encan fini
for x in C.values():
    assert x["mise_max"] is None and x["mise_max_cad"] is None and x["valeur_cad"] is None and not x["trop_bas"] and not x["mise_perso"], x
assert C["111"]["mise_actuelle"] == 23.0 and C["111"]["mise_min"] == watchlist.mise_minimum(23.0, 4) > 23.0     # le minimum d'eBay
assert C["222"]["devise"] == "USD" and C["222"]["mise_min"] == 18.0 and C["222"]["taux"] == 1.40
assert r["texte"] == ""                                                          # rien a exporter sans mise
L = {x["item_id"]: x for x in a.watch_liste()["cartes"]}
assert all(L[i].get(k) is None for i in L for k in ("valeur", "mise_max", "profit", "mise_perso")), L   # rien de reserve ne sort
# 2. il ecrit SA mise (30 $ CA et 25 $ US) : gardee, et elle revient au retour dans l'app
assert a.watch_mise_max("111", 30, 30, "CAD", True) == {"ok": True}
a.watch_mise_max("222", round(25 * 1.40, 2), 25, "USD", True)
for _ in range(2):
    C = {x["item_id"]: x for x in watchlist.preparer(a, lire)["cartes"]}
    assert C["111"]["mise_max"] == 30.0 and C["111"]["mise_perso"] and not C["111"]["trop_bas"], C["111"]
    assert C["222"]["mise_max"] == 25.0 and C["222"]["devise"] == "USD" and C["222"]["mise_perso"], C["222"]
    assert C["111"]["valeur_cad"] is None and C["222"]["valeur_cad"] is None      # toujours aucune valeur
L = {x["item_id"]: x for x in a.watch_liste()["cartes"]}
assert L["111"]["mise_max"] == 30.0 and L["111"]["mise_perso"] and L["111"].get("valeur") is None and L["111"].get("profit") is None
assert L["333"].get("mise_max") is None                                          # une carte sans mise ecrite : toujours rien
# une mise depassee par l'encan : dite « trop basse », et l'etat « depasse » (l'alerte) marche pour lui aussi
art["111"]["prix_devise"] = 31.0
c = watchlist._cx(a); c.execute("UPDATE watchlist SET total=31 WHERE item_id='111'"); c.commit(); c.close()
assert {x["item_id"]: x for x in watchlist.preparer(a, lire)["cartes"]}["111"]["trop_bas"]
assert {x["item_id"]: x for x in a.watch_liste()["cartes"]}["111"]["etat"] == "depasse"
# la case videe : plus de mise (et pas de mise conseillee a la place)
a.watch_mise_max("111", None, None, None, True)
x = {x["item_id"]: x for x in watchlist.preparer(a, lire)["cartes"]}["111"]
assert x["mise_max"] is None and not x["mise_perso"] and not x["trop_bas"], x
# 3. eBay ne repond pas : l'encan reste prepare (sans minimum), jamais d'erreur
def panne(i):
    raise RuntimeError("eBay injoignable")
C = {x["item_id"]: x for x in watchlist.preparer(a, panne)["cartes"]}
assert set(C) == {"111", "222"} and C["111"]["mise_min"] is None and C["111"]["erreur"]
# 4. avec l'outil de prix (admin, Platine) : comme avant, la mise max conseillee ; une carte sans valeur est preparee aussi
prix["ok"] = True
art["111"]["prix_devise"] = 23.0
c = watchlist._cx(a); c.execute("UPDATE watchlist SET total=23 WHERE item_id='111'"); c.commit(); c.close()
watchlist._valeurs_manquantes = lambda *x, **k: None                             # pas de recherche de ventes (aucun reseau)
C = {x["item_id"]: x for x in watchlist.preparer(a, lire)["cartes"]}
assert C["111"]["mise_max"] == float(int(watchlist.mise_auto(watchlist.reglages(a), 300, 0) + 1e-6)) and C["111"]["valeur_cad"] == 300
assert C["222"]["mise_max"] == 25.0 and C["222"]["mise_perso"]                   # sa mise ecrite, sans valeur
assert "111 " in watchlist.preparer(a, lire)["texte"]
# 5. l'ecran : le montant propose, la case en lot et Gixen tiennent compte d'un encan sans mise max
src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "source", "src_app.html"), encoding="utf-8").read()
for bout in ("x.trop_bas || x.mise_max == null ? (x.mise_min ?? x.mise_max) : x.mise_max",
             "x.mise_max != null && v > x.mise_max",
             "x.mise_max != null ? Math.floor(x.mise_max) : x.mise_min != null ? Math.ceil(x.mise_min) : ''",
             "x.mise_max != null ? Math.floor(x.mise_max) : 0;",
             "L = L.filter(x => x.mise_max != null);",
             "Écris ton montant pour chaque encan. En pâle : le minimum d’eBay."):
    assert bout in src, bout
assert "placeholder=\"${Math.floor(x.mise_max)}\"" not in src
print("OK test_miser_sans_prix")
