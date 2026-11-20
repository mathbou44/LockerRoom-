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

# 14 nov 2026 (Render : memoire depassee a l'heure du reapprentissage) : la memoire libre = la limite du service moins ce
# qu'il utilise, jamais la memoire de toute la machine
import score_appris as _sa
_m, _c = admin.memoire, _sa._cache_repris_mo
_sa._cache_repris_mo = lambda: 0.0
admin.memoire = lambda: {"limite_mo": 4096, "conteneur_mo": 2600, "processus_mo": 900}
assert _sa._mo_libres() <= 1496 and _sa._moteur() == "lgb_leger", (_sa._mo_libres(), _sa._moteur())
# 20 nov 2026 (les plantages des 13 et 14 nov) : le seuil couvre le pic mesure (1,7 Go) ; le cache de fichiers inactif,
# que le systeme reprend au besoin, compte comme libre
assert _sa.MO_LIBRES_MIN >= 1700, _sa.MO_LIBRES_MIN
admin.memoire = lambda: {"limite_mo": 4096, "conteneur_mo": 2400, "processus_mo": 900}
assert _sa._mo_libres() < _sa.MO_LIBRES_MIN, _sa._mo_libres()          # 1 696 Mo : le reapprentissage attend
_sa._cache_repris_mo = lambda: 500.0
assert _sa._mo_libres() >= _sa.MO_LIBRES_MIN, _sa._mo_libres()         # + 500 Mo de cache reprenable : il peut partir
_sa._cache_repris_mo = _c
assert isinstance(_sa._cache_repris_mo(), float)
admin.memoire = _m
print("OK memoire libre du service")

# 20 nov 2026 : la memoire liberee rendue au systeme (Linux) ; le seuil de la soupape sur la memoire vraiment prise
import importlib
admin = importlib.reload(admin)                 # la vraie mesure (plus haut, admin.memoire est simulee)
_m = admin.memoire
assert isinstance(admin.limiter_arenes(), bool) and isinstance(admin.rendre_memoire(), int)
m = admin.memoire()
assert "reel_mo" in m and "detail" in m, m
admin.memoire = lambda: {"conteneur_mo": 1900, "reel_mo": 900, "limite_mo": 2048, "processus_mo": 800, "detail": {}}
n = admin._SOUPAPE["n"]
assert admin.soupape() is None and admin._SOUPAPE["n"] == n        # 1 900 au compteur mais 900 vraiment pris : rien a vider
admin.memoire = lambda: {"conteneur_mo": 1900, "reel_mo": 1800, "limite_mo": 2048, "processus_mo": 1700, "detail": {}}
assert admin.soupape() is not None and admin._SOUPAPE["n"] == n + 1
admin.memoire = _m
print("OK memoire rendue au systeme")
