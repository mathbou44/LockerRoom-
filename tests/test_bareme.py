"""2 nov 2026 : le bareme de l'examen : les memes observations donnent toujours la meme note (normes PSA)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bareme as b
import vision

assert b.note_coins(["net"] * 8) == 10
assert b.note_coins(["net"] * 7 + ["point_blanc"]) == 9
assert b.note_coins(["net"] * 6 + ["point_blanc"] * 2) == 8.5
assert b.note_coins(["net"] * 6 + ["effilochage_leger"] * 2) == 8          # PSA 8 : un ou deux coins
assert b.note_coins(["net"] * 5 + ["effilochage_leger"] * 3) == 7          # PSA 7 : quelques coins
assert b.note_coins(["net"] * 7 + ["arrondi_leger"]) == 5
assert b.note_coins(["net"] * 7 + ["plie"]) == 3
assert b.note_bords(["net"] * 7 + ["point_blanc"]) == 9 and b.note_bords(["net"] * 6 + ["point_blanc"] * 2) == 8.5
# 9 nov 2026 (la Hutson : des points fins sur un seul bord -> PSA 9 selon Mathieu)
assert b.note_bords(["net"] * 7 + ["quelques_points"]) == 9 and b.note_bords(["net"] * 6 + ["quelques_points", "point_blanc"]) == 8.5
assert b.note_bords(["net"] * 5 + ["quelques_points"] * 3) == 8
assert b.note_bords(["net"] * 7 + ["encoche"]) == 6 and b.note_bords(["net"] * 4 + ["quelques_points"] * 4) == 7.5
assert b.note_surface([]) == 10 and b.note_surface([("ligne d'impression", "rasante")]) == 10
# 9 nov 2026 (guide pregradecards.com) : une rayure vue de pres : 7 ; deux dont une visible : 5 ; une micro-rayure rasante : 9
assert b.note_surface([("rayure", "de_pres")]) == 7 and b.note_surface([("rayure", "de_pres"), ("rayure", "visible")]) == 5
assert b.note_surface([("rayure", "rasante")]) == 9 and b.note_surface([("rayure", "de_pres"), ("rayure", "de_pres")]) == 7
assert b.note_surface([("micro-creux", "rasante")] * 3) == 8 and b.note_surface([("point d'encre", "de_pres")]) == 9
assert b.note_surface([("decollement", "de_pres")]) == 7 and b.note_surface([("pli", "rasante")]) == 5
assert b.note_surface([("pli", "visible")]) == 3
assert b.globale({"centrage": 10, "coins": 9, "bords": 10, "surface": 10}) == 9
assert b.globale({"centrage": 10, "coins": 9, "bords": 9, "surface": 10}) == 8.5
assert b.globale({"centrage": 9, "coins": 8, "bords": 10, "surface": None}) == 8
assert b.psa(9.5) == 9

# observations -> examen : la meme entree donne toujours le meme resultat ; « incertaine » n'abaisse que le bas
f = {"evaluable": True, "invisible": [],
     "coins": [{"photo": 0, "coin": c, "etat": "net", "certitude": "sure"} for c in b.COINS[:3]]
              + [{"photo": 0, "coin": "bas-gauche", "etat": "effilochage_leger", "certitude": "sure"}],
     "bords": [{"photo": 0, "bord": x, "etat": "net", "certitude": "sure"} for x in b.BORDS[:3]]
              + [{"photo": 0, "bord": "gauche", "etat": "encoche", "certitude": "incertaine"}],
     "surface": [{"photo": 0, "type": "rayure", "visibilite": "visible", "certitude": "sure", "x": 500, "y": 400, "sur_relique": True}]}
r1 = vision._noter_observations(f, {"devant": {"gd": "52/48"}, "note": 10})
r2 = vision._noter_observations(f, {"devant": {"gd": "52/48"}, "note": 10})
# 9 nov 2026 (Mathieu : « quand l'IA doute : ne rien montrer ») : l'encoche incertaine ne baisse plus rien et n'est pas montree
assert r1["note_max"] == r2["note_max"] == 8 and r1["note_min"] == 8, (r1["note_min"], r1["note_max"])
assert r1["notes"]["surface"] == 10                                          # la rayure est sur la patch : ignoree
assert [d["gravite"] for d in r1["defauts"]] == ["moyen"]
assert r1["bareme"] == "PSA-1"
print("ok bareme")
# 9 nov 2026 (la Dickinson : une vraie tache brune au dos) : jamais 10 ; au dos, un cran moins grave qu'au devant
assert b.note_surface([("tache", "visible", 1)]) == 8 and b.note_surface([("tache", "visible", 0)]) == 6
assert b.note_surface([("tache", "de_pres", 1)]) == 9 and b.note_surface([("tache", "rasante", 1)]) == 9
print("ok tache au dos")
