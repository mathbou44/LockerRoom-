"""Mode Auto des prix eBay (python tests/test_prix_auto.py). Aucun appel reseau : eBay est simule."""
import os
import sys
import tempfile

os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lockerroom  # noqa: E402
import forfaits  # noqa: E402
import ebay_compte  # noqa: E402

a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "p.db"))
PRO = [False]
forfaits.est_pro = lambda: PRO[0]
ebay_compte.statut = lambda: {"connecte": True, "ecriture": True, "cles_ok": True}
LISTES = {
    "baisser": [{"item_number": "1", "titre": "Bedard YG", "prix": 100.0, "suggestion": 70.0, "cout": None},     # -30 % -> borne -15 %
                {"item_number": "2", "titre": "Fantilli YG", "prix": 50.0, "suggestion": 30.0, "cout": 48.0},     # plancher cout + 0 %
                {"item_number": "3", "titre": "Petite", "prix": 10.0, "suggestion": 9.9, "cout": None}],          # trop petit
    "monter": [{"item_number": "4", "titre": "Celebrini YG", "prix": 40.0, "suggestion": 44.0, "cout": 10.0},
               {"item_number": "5", "titre": "Sans conseil", "prix": 40.0, "suggestion": None}]}
a.sante_liste = lambda v: [dict(x) for x in LISTES.get(v, [])]
CHANGES = []
a.ebay_changer_prix = lambda item, p: CHANGES.append((item, p)) or {"ok": True, "prix": p}
a._push = lambda *x, **k: 1

# inactif par defaut ; Pro requis pour l'activer
assert a.prix_auto_appliquer()["raison"] == "inactif" and not CHANGES
r = a.prix_auto_regler({"actif": True}); assert not r["ok"] and r["pro_requis"]
PRO[0] = True
r = a.prix_auto_regler({"actif": True, "max_pct": 99, "max_jour": 0, "plancher": "0.10"})
assert r["ok"] and r["actif"] and r["max_pct"] == 30 and r["max_jour"] == 1 and r["plancher"] == 0.99, r
r = a.prix_auto_regler({"max_pct": 15, "max_jour": 10, "marge_min_pct": 0})
# application
r = a.prix_auto_appliquer()
assert r["faits"] == 3, (r, CHANGES)
assert ("1", 85.0) in CHANGES and ("2", 48.0) in CHANGES and ("4", 44.0) in CHANGES and not any(i in ("3", "5") for i, _ in CHANGES), CHANGES
# une fois par jour
assert a.prix_auto_appliquer()["faits"] == 0 and len(CHANGES) == 3
j = a.prix_auto_lire()["journal"]; assert len(j) == 3 and j[0]["ok"] and j[0]["apres"] in (85.0, 48.0, 44.0)
# marge minimum : cout 48 + 20 % = 57,60 > prix actuel 50 -> on ne baisse pas sous le cout + marge (on monte meme pas : plancher)
a.prix_auto_regler({"marge_min_pct": 20, "monter": False})
CHANGES.clear(); r = a.prix_auto_appliquer(force=True)
assert ("2", 57.6) in CHANGES and not any(i == "4" for i, _ in CHANGES), CHANGES
# Pro perdu -> plus rien
PRO[0] = False; CHANGES.clear()
assert a.prix_auto_appliquer(force=True)["raison"] == "inactif" and not CHANGES
print("PRIX AUTO OK")
