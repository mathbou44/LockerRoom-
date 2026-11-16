"""16 nov 2026 : les taches du tableau CEO (son outil de travail) : semees une fois, ajout, modification, suppression, tri."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import lockerroom  # noqa: E402

a = lockerroom.Api()
a._est_admin = lambda: True
r = a.admin_ceo()
assert r["ok"], r
T = r["taches"]
assert any(t["id"] == "lic_hci" and t["modele"] == "hci" for t in T), T
n0 = len(T)
assert len(a.admin_ceo()["taches"]) == n0                      # semees une seule fois
# ajout (titre vide refuse), priorite hors bornes ramenee a 3
a.admin_ceo_sauver({"tache_ajout": {"titre": "   "}})
x = a.admin_ceo_sauver({"tache_ajout": {"titre": "Appeler le comptable", "prio": 9, "echeance": "2026-12-01", "hack": 1}})
t = next(t for t in x["config"]["taches"] if t["titre"] == "Appeler le comptable")
assert t["prio"] == 3 and t["echeance"] == "2026-12-01" and "hack" not in t and t["id"].startswith("t")
# modification : fait, puis suppression d'une semee
a.admin_ceo_sauver({"taches": {t["id"]: {"etat": "fait"}, "lic_hci": {"prio": 1, "etat": "attente", "note": "envoyé le 16"}}})
r = a.admin_ceo()
d = {x["id"]: x for x in r["taches"]}
assert d[t["id"]]["etat"] == "fait" and d[t["id"]]["fait_le"] and d["lic_hci"]["prio"] == 1 and d["lic_hci"]["etat"] == "attente"
assert r["taches"][0]["id"] == "lic_hci" and r["taches"][-1]["id"] == t["id"]          # urgente d'abord, faite a la fin
a.admin_ceo_sauver({"taches_suppr": ["lic_cl"]})
assert "lic_cl" not in {x["id"] for x in a.admin_ceo()["taches"]}                      # pas resemee
a._est_admin = lambda: False
assert a.admin_ceo_sauver({"tache_ajout": {"titre": "x"}})["ok"] is False
print("CEO TACHES OK")
