"""26 nov 2026, 21 h 50 (Mathieu, capture de la section « Ended » de la watchlist : « devrait etre marque celle qu'on gagne »).
Un encan termine dont le numero d'annonce est dans les achats eBay du compte est marque GAGNE, avec ce qui a ete paye."""
import os, sys, tempfile
from datetime import datetime, timedelta, timezone
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import lockerroom, watchlist
api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "t.db"))
hier = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
demain = (datetime.now(timezone.utc) + timedelta(hours=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
c = watchlist._cx(api)
for iid, titre, fin, total in (("v1|365001112223|0", "SP Authentic Future Watch Auto Horizontal Brady Martin #171 /599", hier, 24.0),
                               ("v1|365004445556|0", "Fleer Ultra ExCELLYng Auto Connor Bedard #EC-28 PSA 8", hier, 181.0),
                               ("v1|365007778889|0", "2024-25 Upper Deck Young Guns Macklin Celebrini #201", demain, 300.0),
                               ("365009990001", "2023-24 Upper Deck Young Guns Connor Bedard #451", hier, 900.0)):
    c.execute("INSERT INTO watchlist (item_id, titre, total, port, encan, fin, statut) VALUES (?,?,?,?,1,?,'ok')", (iid, titre, total, 13.0, fin))
c.commit(); c.close()
assert api._achats_par_item() == {}
r = watchlist.liste(api)
assert all(not x.get("gagne") for x in r["cartes"]), "aucun achat : rien n'est marque"
# les achats eBay du compte : la Brady Martin (payee en $ CA), la Bedard YG (en $ US), et la Celebrini (encan PAS fini)
d = api._db(); api._achats_table(d)
d.execute("INSERT INTO achats_ebay (item_id, n, titre, cout, devise, date) VALUES ('365001112223', 0, 'Brady Martin FW Auto', 24.61, 'CAD', '2026-11-26')")
d.execute("INSERT INTO achats_ebay (item_id, n, titre, cout, devise, date) VALUES ('365009990001', 0, 'Bedard YG', 640.0, 'USD', '2026-11-26')")
d.execute("INSERT INTO achats_ebay (item_id, n, titre, cout, devise, date) VALUES ('365007778889', 0, 'Celebrini YG', 300.0, 'CAD', '2026-11-26')")
d.commit(); d.close()
L = {x["item_id"]: x for x in watchlist.liste(api)["cartes"]}
assert L["v1|365001112223|0"]["gagne"] is True and L["v1|365001112223|0"]["paye"] == 24.61
assert L["365009990001"]["gagne"] is True and L["365009990001"]["paye"] is None, "une autre devise : gagnee, sans montant"
assert not L["v1|365004445556|0"].get("gagne"), "terminee, pas dans les achats : pas gagnee"
assert not L["v1|365007778889|0"].get("gagne") and L["v1|365007778889|0"]["etat"] != "fini", "un encan en cours n'est jamais « gagne »"
ordre = [x["item_id"] for x in watchlist.liste(api)["cartes"]]
assert ordre[0] == "v1|365007778889|0" and set(ordre[1:3]) == {"v1|365001112223|0", "365009990001"} and ordre[3] == "v1|365004445556|0", ordre
# l'ecran
src = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()
app = open(os.path.join(RACINE, "ui", "app.html"), encoding="utf-8").read()
assert "fini ? (x.gagne ? tt('Gagnée', 'Won') : tt('Terminé', 'Ended'))" in src and "tt('Gagnée · payé', 'Won · paid')" in src
assert src.index('if (x.gagne) return `<div class="w-pr2"><div class="w-final w-gagne">') < src.index("tt('on le cherche…', 'looking it up…')"), "gagnee : plus de « on le cherche »"
assert "w-gg" in app and "Won · paid" in app
print("test_watchlist_gagnee OK")
