"""13 nov 2026 (Mathieu : « une carte en encan, scannee, pas un deal : a la 2e passe, ne repasse pas dessus ; juste les
nouvelles ») : une annonce deja jugee ne coute pas un 2e credit (encan trop cher : jamais ; prix fixe : si son prix baisse ;
sans ventes : pas avant 4 jours)."""
import os, sys, tempfile
from datetime import datetime, timedelta, timezone
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import deals
m = datetime.now(timezone.utc)
fin = (m + timedelta(days=5)).isoformat()
enc = {"item_id": "1", "titre": "x", "prix_cad": 40.0, "port_cad": 0.0, "encan": True, "fin": fin}
fixe = {"item_id": "2", "titre": "y", "prix_cad": 100.0, "port_cad": 0.0}
sv = {"item_id": "3", "titre": "z", "prix_cad": 30.0, "port_cad": 0.0, "encan": True, "fin": fin}
assert not deals.deja_jugee(enc)
deals.noter_jugee(enc, "trop_cher", 0.9)
deals.noter_jugee(fixe, "trop_cher", 0.95)
deals.noter_jugee(sv, "sans_ventes", None)
deals._JUG["d"] = None                                       # relu du disque (un redemarrage)
assert deals.jugees()["1"]["valeur"] == round(40 / 0.9, 2)
assert deals.deja_jugee(dict(enc, prix_cad=55.0))            # la mise a monte : toujours pas un deal, pas de credit
assert deals.deja_jugee(fixe) and not deals.deja_jugee(dict(fixe, prix_cad=70.0))   # prix fixe baisse : on revoit
assert deals.deja_jugee(sv) and not deals.deja_jugee(sv, maint=m + timedelta(days=5))
assert not deals.deja_jugee({"item_id": "4", "prix_cad": 10.0})                     # une nouvelle : verifiee
# un deal n'est jamais saute (il reste a suivre)
deals.noter_jugee({"item_id": "5", "prix_cad": 20.0, "encan": True, "fin": fin}, "deal", 0.4)
assert not deals.deja_jugee({"item_id": "5", "prix_cad": 25.0, "encan": True})
# un encan fini est oublie
deals.noter_jugee({"item_id": "6", "prix_cad": 20.0, "encan": True, "fin": (m - timedelta(hours=1)).isoformat()}, "trop_cher", 0.9)
deals.noter_jugee({"item_id": "7", "prix_cad": 20.0}, "trop_cher", 0.9)
assert "6" not in deals.jugees()
print("JUGEES OK")
