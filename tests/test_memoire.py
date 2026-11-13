"""13 nov 2026 (Render : « memoire depassee ») : la memoire suivie, et videe pres de la limite ; 40 Radars gardes au plus."""
import os, sys, tempfile, time
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import admin, lockerroom, score_slab
m = admin.memoire()
assert m["processus_mo"] and m["processus_mo"] > 10, m
# loin de la limite : rien
admin.memoire = lambda: {"conteneur_mo": 500, "limite_mo": 2048, "processus_mo": 400}
lockerroom.Api._RADAR["x"] = (time.time(), {"ok": True})
assert admin.soupape() is None and "x" in lockerroom.Api._RADAR
# pres de la limite : les memoires de confort videes
admin.memoire = lambda: {"conteneur_mo": 1800, "limite_mo": 2048, "processus_mo": 1500}
score_slab._LOT["d"]["t"] = 1
v = admin.soupape()
assert v and not lockerroom.Api._RADAR and not score_slab._LOT["d"] and admin._SOUPAPE["n"] == 1
# 40 Radars au plus, les plus vieux sortent
a = lockerroom.Api.__new__(lockerroom.Api)
a.RADAR_GARDE_S = 300
a._radar_chemin = lambda c: (tempfile.mkdtemp(), os.path.join(tempfile.mkdtemp(), "r.json"))
for i in range(60):
    lockerroom.Api._radar_garder(a, f"k{i}", {"ok": True})
assert len(lockerroom.Api._RADAR) <= 40 and "k59" in lockerroom.Api._RADAR and "k0" not in lockerroom.Api._RADAR
print("MEMOIRE OK")
