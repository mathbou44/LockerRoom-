"""26 nov 2026, 19 h 22 (Mathieu, captures a l'ordi des menus « Ships from », « Listings », « SlabIQ grade » : texte blanc sur
fond blanc ; « tous les drop down doivent etre revus »). Tous les menus de l'app ouvrent une liste sombre au texte clair."""
import os, re
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()
app = open(os.path.join(RACINE, "ui", "app.html"), encoding="utf-8").read()
assert "select{color-scheme:dark}" in src and "select option, select optgroup{background:#1B1B22; color:#F4F2EE" in src
assert re.search(r"select\{color-scheme:dark\}", app) and re.search(r"select option,\s*select optgroup\{background:#1B1B22;\s*color:#F4F2EE", app), "l'app servie a la regle"
# la regle est GLOBALE (pas un menu a la fois) et aucune regle ne remet une liste claire
assert not re.search(r"select[^{}]*option\{[^}]*background:\s*(#fff|#FFF|white)", src)
assert src.count("<select") >= 15, "les menus de l'app"
print("test_menus_lisibles OK")
