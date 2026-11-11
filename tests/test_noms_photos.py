"""11 nov 2026 (Mathieu : le dos d'une Martin Necas colle a une Jari Kurri) : deux noms lus sans mot commun = deux cartes."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vision
assert vision.noms_differents("Jari Kurri", "MARTIN NECAS")
assert not vision.noms_differents("Jari Kurri", "JARI KURRI / RW")
assert not vision.noms_differents("Patrik Laine", "Laine")
assert not vision.noms_differents("", "Martin Necas") and not vision.noms_differents("Kurri", None)
assert not vision.noms_differents("Alexis Lafrenière", "LAFRENIERE")
assert vision._photos([{"cote": "dos", "coins": None, "entiere": True, "joueur": "Martin Necas"}])[0]["joueur"] == "Martin Necas"
assert "joueur" in vision.OUTIL["input_schema"]["properties"]["photos"]["items"]["properties"]
print("NOMS PHOTOS OK")
