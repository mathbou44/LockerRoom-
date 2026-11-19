"""19 nov 2026 : la demande a Fanatics Collect est semee dans « Licences de donnees » (une fois), avec son courriel."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import ceo
c = ceo._semer({"semis": ["licences", "suivi"], "taches": [{"id": "lic_hci", "projet": "licences"}]})
fc = [t for t in c["taches"] if t["id"] == "lic_fc"]
assert len(fc) == 1 and fc[0]["projet"] == "licences" and fc[0]["modele"] == "fc", fc
assert "licences_fc" in c["semis"]
c = ceo._semer(c)
assert sum(1 for t in c["taches"] if t["id"] == "lic_fc") == 1      # une seule fois
print("OK test_ceo_fanatics")
