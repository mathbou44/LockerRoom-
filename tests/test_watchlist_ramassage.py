"""27 nov 2026, 13 h 34 (Mathieu, la Heiskanen Tableau Shutter Speed Auto /99 : la fiche disait mise max et profit « — » (une seule
vente), la watchlist « ta mise max 7 $, profit +14 $, au-dessus de ta mise max » ; « ca bug et ca fait pas de sens le prix / profit
sachant que j'ai coche le vendeur comme pick up local »). 1) La mise max par defaut suit le ramassage (la ligne doit connaitre le
vendeur : la fiche le lui donne) ; cocher un vendeur refait aussi les mises gardees (les alertes). 2) La fiche
complete est la reference : sans valeur sure, la carte de la watchlist n'a plus de mise max ni de profit ; une mise ecrite a la
main reste. 3) La fiche dit pourquoi : « une seule vente : pas assez pour une mise max ».   python tests/test_watchlist_ramassage.py"""
import os, sys, tempfile
from datetime import datetime, timedelta, timezone
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import lockerroom, watchlist, deals
api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "t.db"))
fin = (datetime.now(timezone.utc) + timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
c = watchlist._cx(api)
c.execute("INSERT INTO watchlist (item_id, titre, total, port, valeur, mise_max, encan, fin, statut, vendeur) VALUES (?,?,?,?,?,?,1,?,'ok',?)",
          ("v1|1|0", "2025-26 UD Tableau Shutter Speed Auto Miro Heiskanen #SS-MH /99", 21.0, 13.0, 50.0, 7.71, fin, "MarDorCards"))
c.execute("INSERT INTO watchlist (item_id, titre, total, port, valeur, mise_max, mise_perso, encan, fin, statut, vendeur) VALUES (?,?,?,?,?,?,1,1,?,'ok',?)",
          ("v1|2|0", "2024-25 Upper Deck Young Guns Lane Hutson #485", 30.0, 10.0, 60.0, 25.0, fin, "MarDorCards"))
c.commit(); c.close()
cfg = watchlist.reglages(api)
L = {x["item_id"]: x for x in watchlist.liste(api)["cartes"]}
assert L["v1|1|0"]["mise_max"] == watchlist.mise_auto(cfg, 50.0, 13.0) and not L["v1|1|0"]["ramassage"], "sans ramassage : le port compte"
# il coche le vendeur « pick up local » (la casse ne compte pas) : la mise max et le profit sans le port, tout de suite
api.deals_ramassage(["mardorcards"])
L = {x["item_id"]: x for x in watchlist.liste(api)["cartes"]}
x = L["v1|1|0"]
assert x["ramassage"] and x["mise_max"] == watchlist.mise_auto(cfg, 50.0, 0.0), x
assert x["profit"] == round(deals.net_revente(50.0) - deals.cout_achat(8.0), 2), x                  # paye 8 $ (la mise, sans le port)
assert L["v1|2|0"]["mise_max"] == 25.0, "une mise ecrite a la main reste"
c = watchlist._cx(api)
assert c.execute("SELECT mise_max FROM watchlist WHERE item_id='v1|1|0'").fetchone()[0] == watchlist.mise_auto(cfg, 50.0, 0.0), "gardee aussi (les alertes)"
c.close()
# la fiche complete relit les ventes : une seule vente -> pas de valeur sure -> la watchlist n'en a plus (sauf la mise a la main)
api._sync_watch("v1|1|0", {"ok": True, "article": {"vendeur": "MarDorCards"}, "ventes": [{"prix": 43.0}], "valeur": None}, False)
api._sync_watch("v1|2|0", {"ok": True, "article": {}, "ventes": [{"prix": 43.0}], "valeur": None}, False)
L = {x["item_id"]: x for x in watchlist.liste(api)["cartes"]}
assert not L["v1|1|0"].get("valeur") and not L["v1|1|0"].get("mise_max") and "profit" not in L["v1|1|0"], L["v1|1|0"]
assert L["v1|2|0"]["mise_max"] == 25.0 and not L["v1|2|0"].get("valeur")
# la version rapide, une panne ou des ventes en attente : rien ne change
c = watchlist._cx(api); c.execute("UPDATE watchlist SET valeur=50 WHERE item_id='v1|1|0'"); c.commit(); c.close()
for r, rapide in (({"ok": True, "ventes": [], "valeur": None}, True), ({"ok": True, "ventes": [], "valeur": None, "ventes_lentes": True}, False),
                  ({"ok": True, "valeur": None}, False), ({"ok": True, "ventes": [], "valeur": None, "ventes_attente": True}, False), ({"ok": False}, False)):
    api._sync_watch("v1|1|0", r, rapide)
    assert {x["item_id"]: x for x in watchlist.liste(api)["cartes"]}["v1|1|0"].get("valeur") == 50, r
# le vendeur manquant est garde depuis la fiche (le ramassage en depend)
c = watchlist._cx(api); c.execute("UPDATE watchlist SET vendeur=NULL WHERE item_id='v1|1|0'"); c.commit(); c.close()
api._sync_watch("v1|1|0", {"ok": True, "article": {"vendeur": "MarDorCards"}, "ventes": [{"prix": 43}, {"prix": 45}], "valeur": 44.0}, False)
assert {x["item_id"]: x for x in watchlist.liste(api)["cartes"]}["v1|1|0"]["ramassage"] is True
# la fiche : la raison
src = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()
assert "ventes.length < 2 ? tt('une seule vente : pas assez pour une mise max', 'only one sale: not enough for a max bid')" in src
s_ = open(os.path.join(RACINE, "lockerroom.py"), encoding="utf-8").read()
assert "r = self._annonce_detail0(item_id, titre=titre, rapide=rapide, q=q)" in s_ and "watchlist._refaire_mises(self)" in s_
print("WATCHLIST RAMASSAGE OK")
