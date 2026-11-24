"""24 nov 2026 (vitesse du Radar, lue dans les piles du serveur : 8 a 30 s, 29 s juste apres un push).
1. Les reglages : lus des dizaines de fois par Radar, chaque fois en ouvrant la base sous le verrou commun. Gardes 2 s par
   base ; une ecriture se voit tout de suite ; ce qu'on recoit est une copie (la modifier ne change pas la garde).
2. indice_joueurs.lire() et demande_legale.lire() sont appeles une fois PAR CARTE (le score) : plus un appel au disque a chaque
   fois (la date du fichier, son existence), au plus un aux 2 secondes ; une ecriture se voit tout de suite.
3. Le Radar ecrit le temps de chaque etape dans le journal (« Radar (temps) : ... ») : on sait ou partent les secondes."""
import contextlib
import io
import os
import sys
import tempfile
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
os.environ["LR_RADAR_TEMPS_S"] = "0"
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom
import ebay_compte
from lockerroom import Api

api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
api2 = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "b.db"))

# 1. les reglages
n = [0]
vrai = Api._reglages_lire0


def compte(self):
    n[0] += 1
    return vrai(self)


Api._reglages_lire0 = compte
try:
    Api._REGL.clear()
    a = api.reglages_lire()
    for _ in range(60):
        api.reglages_lire()
    assert n[0] == 1, n[0]                                        # 61 lectures, UNE ouverture de la base
    a["pays"] = "ZZ"
    assert api.reglages_lire()["pays"] != "ZZ"                    # une copie : la modifier ne touche pas la garde
    assert api.reglages_sauver({"pays": "US"})["pays"] == "US" and api.reglages_lire()["pays"] == "US"   # l'ecriture se voit tout de suite
    assert api2.reglages_sauver({"pays": "CA"})["pays"] == "CA"
    assert api.reglages_lire()["pays"] == "US" and api2.reglages_lire()["pays"] == "CA"                  # chaque base a sa garde
    n0, Api.REGL_S = n[0], 0.05
    time.sleep(0.09)
    api.reglages_lire()
    assert n[0] == n0 + 1                                         # passe le delai : relu sur le disque
finally:
    Api._reglages_lire0, Api.REGL_S = vrai, 2.0

# 2. une lecture du disque aux 2 secondes, pas une par carte
import indice_joueurs as ij
import demande_legale as dl
ij._ecrire({"joueurs": {}, "indice": {"A": {"x": 1}}, "le": 1})
dl.lire()
nb = {"mt": 0, "ex": 0}
vrai_mt, vrai_ex = os.path.getmtime, os.path.exists
os.path.getmtime = lambda p: (nb.__setitem__("mt", nb["mt"] + 1), vrai_mt(p))[1]
os.path.exists = lambda p: (nb.__setitem__("ex", nb["ex"] + 1), vrai_ex(p))[1]
try:
    for _ in range(300):
        assert ij.lire()["indice"]["A"]["x"] == 1
        dl.lire()
    assert nb["mt"] <= 2 and nb["ex"] <= 2, nb                    # avant : 300 et 300
finally:
    os.path.getmtime, os.path.exists = vrai_mt, vrai_ex
ij._ecrire({"joueurs": {}, "indice": {"A": {"x": 2}}, "le": 2})
assert ij.lire()["indice"]["A"]["x"] == 2                         # une ecriture se voit tout de suite

# 3. le temps de chaque etape du Radar, dans le journal
ebay_compte.rechercher = lambda q, **k: []
assert api.deals_profil_regler({"favoris": ["Connor Bedard"], "collectionne": [], "prix_min": None, "prix_max": None, "iq_min": None})["ok"]
tampon = io.StringIO()
with contextlib.redirect_stdout(tampon):
    r = api.mes_deals(True)
assert r["ok"], r
ligne = [l for l in tampon.getvalue().splitlines() if l.startswith("Radar (temps) : ")]
assert len(ligne) == 1 and " recherches, " in ligne[0] and "trop longues" in ligne[0] and "annonces gardees" in ligne[0], tampon.getvalue()[-400:]
assert "joueur Connor Bedard" in ligne[0], ligne[0]               # les recherches les plus lentes sont nommees
print("OK test_vitesse_radar :", ligne[0][:150])
