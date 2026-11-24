"""23 nov 2026 (Mathieu, sa Misa SP Rookie Authentics OR a 55 $ : « Too high +424 % · market $10 · 3 sales », alors que la meme
carte s'est vendue 61 $ : « va falloir que tu fasses attention » ; puis : « le prix est toujours plus cher que la last sold des
3 derniers mois / moyenne ponderee, la plus chere, d'environ 15 % »).
- le repere = le plus haut de la derniere vente (3 mois) et de la mediane ponderee ; le bon prix = + 15 % ;
- plus du double du repere avec moins de 8 ventes = les ventes d'une autre version : « verifier », aucun prix suggere, donc
  jamais de baisse automatique (le mode Auto ne lit que « baisser » et « monter ») ni de bouton « Mettre au marche »."""
import os, sys
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ICI)
import sante
E = sante.evaluer_vendues
# 1. son cas : 55 $ contre un « marche » de 10 $ sur 3 ventes : on doute du repere, pas du prix
r = E(55, 10.0, 3, derniere=10.49, ponderee=10.0)
assert r["verdict"] == "verifier" and r["suggestion"] is None, r
assert E(55, 10.0, 3)["verdict"] == "verifier"                                  # meme sans le detail des ventes
# ... avec beaucoup de ventes, le meme ecart est un vrai « trop cher », ramene au repere + 15 %
r = E(55, 10.0, 12, derniere=10.0, ponderee=10.0)
assert r["verdict"] == "baisser" and r["suggestion"] == sante.prix_rond(10.0 * 1.15, plafond=55), r
# 2. la regle : le plus haut de la derniere vente et de la mediane ponderee
r = E(70, 50.0, 6, derniere=61.0, ponderee=52.0)                                # derniere vente 61 $ : 70 $ = + 15 % : bon
assert r["verdict"] == "ok" and r["mediane"] == 61.0 and abs(r["ecart"] - (70 / 61 - 1)) < 0.001, r
r = E(70, 50.0, 6, derniere=44.0, ponderee=52.0)                                # mediane ponderee 52 $ : 70 $ = + 35 % : trop
assert r["verdict"] == "baisser" and r["mediane"] == 52.0 and r["suggestion"] == sante.prix_rond(52.0 * 1.15, plafond=70) == 60.0, r
assert E(64, 50.0, 6, derniere=44.0, ponderee=52.0)["verdict"] == "ok"            # + 23 % : dans la marge, on ne dit rien
# trop bas : on propose le repere + 15 %, pas le repere moins 5 %
r = E(30, 50.0, 6, derniere=44.0, ponderee=52.0)
assert r["verdict"] == "monter" and r["suggestion"] == 60.0, r
# 3. ce qui ne change pas : sans valeur sure, aucun verdict de prix ; une annonce qui traine
r = E(65, None, 1, derniere=40.0, ponderee=40.0)
assert (r["verdict"], r["mediane"], r["ecart"], r["suggestion"]) == ("ok", None, None, None), r
assert E(42, 40.0, 5, age=90, watchers=0)["verdict"] == "traine"
assert E(65, 60, 5)["verdict"] == "ok" and E(65, 34, 5)["verdict"] == "baisser"   # sans le detail : la valeur sure sert de repere
# 4. le mode Auto et les rabais ne lisent jamais « verifier »
src = open(os.path.join(ICI, "lockerroom.py"), encoding="utf-8").read()
assert 'cands = (self.sante_liste("baisser") if cfg["baisser"] else []) + (self.sante_liste("monter") if cfg["monter"] else [])' in src
assert "derniere=_der, ponderee=_pon)" in src
# 4b. un repere douteux DEJA garde (passe d'avant le 23 nov) ne sort ni dans « Trop cheres » ni dans le mode Auto
import tempfile
from datetime import datetime
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
os.environ["LR_EBAY_PRIX"] = os.environ.get("LR_EBAY_PRIX", "1")
import lockerroom
api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
c = api._db(); maint = datetime.now().isoformat()
c.execute("INSERT INTO cartes (titre, statut, prix_demande, item_number, vu_actif_le) VALUES ('Misa Rookie Authentics Gold', 'Listée', 55, '901', ?)", (maint,))
c.execute("INSERT INTO cartes (titre, statut, prix_demande, item_number, vu_actif_le) VALUES ('Une carte vraiment trop chere', 'Listée', 55, '902', ?)", (maint,))
c.execute("INSERT INTO cartes (titre, statut, prix_demande, item_number, vu_actif_le) VALUES ('Trop chere, beaucoup de ventes', 'Listée', 55, '903', ?)", (maint,))
for item, sug, med, n in (("901", 10, 10.0, 3), ("902", 40, 40.0, 3), ("903", 10, 10.0, 15)):
    c.execute("INSERT INTO sante (item_number, maj, verdict, suggestion, mediane, n, ecart, requete, fait) VALUES (?, ?, 'baisser', ?, ?, ?, .5, 'q', 0)", (item, maint, sug, med, n))
c.commit(); c.close()
if lockerroom.ebay_prix_actif():
    vus = {x["item_number"] for x in api.sante_liste("baisser")}
    assert vus == {"902", "903"}, vus          # la Misa (5,5 fois le repere, 3 ventes) n'y est pas ; les deux autres oui

# 5. l'ecran : « A verifier » sans bouton ; « Mettre au marche » = le repere + la marge de nego (15 % par defaut)
app = open(os.path.join(ICI, "source", "src_app.html"), encoding="utf-8").read()
assert "(ecart > 1 && nRef < 8)" in app and "m.verdict === 'verifier'" in app and "douteux: true" in app
assert "r_.cl !== 'vert' && r_.ref && !r_.douteux" in app and app.count("rond5(r_.ref * 1.1)") == 0 and "+am.dataset.ref * (1 + nego() / 100)" in app
print("OK test_prix_repere")
