"""21 nov 2026 (Mathieu : « les priorites et choses a faire : toujours dans la to-do de l'admin ») : la liste du lancement est semee."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import ceo
c = ceo._semer({"semis": ["licences", "suivi", "licences_fc"], "taches": []})
L = {t["id"]: t for t in c["taches"]}
assert L["l1_apple"]["projet"] == "lancement" and L["l1_apple"]["echeance"] == "2026-11-22" and L["l1_apple"]["prio"] == 1
assert L["d_ygr"]["echeance"] is None and all(L[x[0]]["projet"] == "lancement" for x in ceo.SEMIS["lancement_1dec"] + ceo.SEMIS["securite_21nov"])
c["taches"][0]["etat"] = "fait"
n = len(c["taches"]); c = ceo._semer(c)
assert len(c["taches"]) == n and c["taches"][0]["etat"] == "fait"      # une seule fois : ce qui est fait reste fait
assert ceo.taches(c)[0]["prio"] == 1
print("OK test_ceo_lancement")
