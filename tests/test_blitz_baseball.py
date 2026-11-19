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
print("OK test_blitz_baseball")
