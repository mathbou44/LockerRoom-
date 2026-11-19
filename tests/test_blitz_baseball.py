"""19 nov 2026 (Mathieu : « ca marque encore 0 ») : plus de credits (402) = « quota » : le blitz s'arrete au lieu de reessayer
sans fin ; « Baseball maintenant » met le hockey en pause et fait passer le baseball."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import urllib.error, urllib.request, io
import vendues, cote_marche, lockerroom

def refus(*a, **k):
    raise urllib.error.HTTPError("u", 402, "Payment Required", {}, io.BytesIO(b""))
vendues._cle = lambda: "x"
vieux = urllib.request.urlopen
urllib.request.urlopen = refus
d, err = vendues._appel("crosby", "ebay.com", attendre=False, usage="blitz")
urllib.request.urlopen = vieux
assert d is None and "quota" in err, err
api = lockerroom.Api()
api._est_admin = lambda *a, **k: True
cote_marche._BLITZ["en_cours"] = True
r = api.soldcomps_blitz("baseball")
assert r["ok"] and cote_marche._BLITZ["stop"] and cote_marche._BB_PRIO[0], r
cote_marche._BLITZ["en_cours"] = False
api.soldcomps_blitz("arreter_baseball")
assert cote_marche._BLITZ_BB["stop"]
# « Baseball maintenant » : le baseball part des que le hockey s'arrete (avant : au prochain tour de la boucle, une fois par heure)
import time
parti = []
cote_marche.blitz_bb = lambda *a, **k: parti.append(1) or {"ok": True}
cote_marche._BLITZ.update(en_cours=True, stop=False)
cote_marche._BLITZ_BB.update(en_cours=False, stop=False)
cote_marche.baseball_maintenant()
assert cote_marche._BLITZ["stop"] and not parti
cote_marche._BLITZ["en_cours"] = False                 # le hockey s'est arrete
for _ in range(50):
    if parti:
        break
    time.sleep(0.1)
time.sleep(0.3)
assert parti, "le baseball n'est pas parti"
# une attente de panne s'interrompt au bouton Arreter
t0 = time.time(); cote_marche._BLITZ["stop"] = True; cote_marche._dormir(30, cote_marche._BLITZ)
assert time.time() - t0 < 2
print("OK test_blitz_baseball")
