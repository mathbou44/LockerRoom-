"""9 nov 2026 : l'activite anonyme (tableau de l'admin) et l'ordre des deals propre a chaque compte."""
import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LR_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LR_DONNEES"]
import activite
from datetime import datetime

activite.FLUSH_S = 0
for c in ("compte-a", "compte-b", "compte-a"):
    activite.noter_api("deals_liste", c)
activite.noter_api("carte_etat", "compte-b")
activite.noter_api("statut", "compte-b")                      # technique : ignore
activite.noter_api("admin_resume", "compte-b")                # admin : ignore
activite.noter_page("deals", "compte-a"); activite.noter_page("Deals/123", "compte-a"); activite.noter_page("<script>", "x")
activite.ecrire()
d = activite.lire()["jours"][datetime.now().strftime("%Y-%m-%d")]
assert d["api"] == {"deals_liste": 3, "carte_etat": 1}, d["api"]
assert d["pages"] == {"deals": 2}, d["pages"]
assert d["actifs"] == 2 and len(d["vus"]) == 2 and "compte-a" not in str(d), d   # empreintes, jamais le compte
assert activite.empreinte("compte-a", "2026-11-09") != activite.empreinte("compte-a", "2026-11-10")   # pas reliable d'un jour a l'autre
r = activite.resume(7, ["deals_liste", "carte_etat", "vente_creer", "admin_x", "statut"])
assert r["actifs_auj"] == 2 and r["fonctions_top"][0] == ("deals_liste", 3) and r["jamais"] == ["vente_creer"], r
assert r["pages"] == [("deals", 2)] and len(r["serie"]) == 7, r
print("OK activite")

import lockerroom
api = lockerroom.Api.__new__(lockerroom.Api)
api._joueurs_a_moi = lambda: [lockerroom.Api._norm_fav("Lane Hutson")]
L = [{"item_id": str(i), "titre": f"Carte {i}" + (" Lane Hutson" if i == 9 else ""), "recrue": False, "etranger": False} for i in range(12)]
L[0]["favori"] = True
with comptes.utiliser("u1"):
    a = api._varier_deals([dict(x) for x in L])
with comptes.utiliser("u2"):
    b = api._varier_deals([dict(x) for x in L])
assert a[0]["item_id"] == "0" and b[0]["item_id"] == "0"                   # les favoris restent devant
assert sorted(x["item_id"] for x in a) == sorted(x["item_id"] for x in L)   # rien de perdu
assert {x["item_id"] for x in a[1:7]} == {str(i) for i in range(1, 7)}       # chaque paquet garde ses deals
assert [x["item_id"] for x in a] != [x["item_id"] for x in b] or comptes.MULTI is False, (a, b)
j = [x["item_id"] for x in a].index("9")
assert j == 7 and a[j].get("a_moi"), [x["item_id"] for x in a]               # mon joueur en tete de son paquet
print("OK deals varies")
