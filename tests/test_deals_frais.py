"""18 nov 2026 (Mathieu : « ou sont les comps recentes ?! », la Misa PMG Blue /50 a +122 $ sur des ventes de juillet et
aout ; 130point : 477 $ CA le 1er oct., 283 $ CA le 15 oct.) : une valeur sans aucune vente de 45 jours ou moins va
chercher les ventes d'aujourd'hui ; toujours rien de recent -> pas un deal."""
import os, sys, tempfile
from datetime import datetime, timedelta, timezone
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import deals
m = datetime.now(timezone.utc)
j = lambda n: (m - timedelta(days=n)).strftime("%Y-%m-%d")
T = "2025-26 METAL UNIVERSE PRECIOUS METAL GEMS BLUE ROOKIES PMG /50 MICHAEL MISA"
a = {"item_id": "misa1", "titre": T, "prix_cad": 339.0, "port_cad": 0.0, "encan": True, "fin": (m + timedelta(hours=5)).isoformat(),
     "vendeur": "remi-card-trader", "photo": None}
r = {"joueur": "Michael Misa", "sport": "hockey", "q": "michael misa"}
vieilles = [{"titre": "25-26 MICHAEL MISA RC 41/50 SKYBOX METAL UNIVERSE ROOKIE PMG BLUE #126 SHARKS", "prix": 858.0, "le": j(91), "url": "u1"},
            {"titre": "25-26 MICHAEL MISA RC 12/50 SKYBOX METAL UNIVERSE ROOKIE PMG BLUE #126 SHARKS", "prix": 814.0, "le": j(116), "url": "u2"}]
recentes = [{"titre": "2025 METAL UNIVERSE #126 MICHAEL MISA ROOKIE BLUE PRECIOUS METAL GEMS PMG RC /50", "prix": 340.0, "le": j(48), "url": "u3"},
            {"titre": "2025 SKYBOX METAL UNIVERSE #126 MICHAEL MISA ROOKIE BLUE PRECIOUS GEMS RC /50", "prix": 201.0, "le": j(34), "url": "u4"},
            {"titre": "2025-26 Metal Universe Michael Misa Blue Precious Metal Gems /50 #126", "prix": 260.0, "le": j(20), "url": "u5"}]
appels = []
def verif(cib):
    appels.append(cib)
    return recentes
# 1. des ventes perimees seulement + le verificateur : on va chercher les recentes, et la carte n'est plus un « deal »
D, st = {}, {}
deals._juger(a, r, list(vieilles), [], m, D, st, verif=verif)
assert st.get("comps_vieilles") == 1 and appels, st
assert "misa1" not in D, D.get("misa1")
# 2. des ventes perimees et aucun verificateur (budget) : pas un deal non plus
D, st = {}, {}
deals._VERIF_FORCE.clear()
deals._juger(dict(a, item_id="misa2"), r, list(vieilles), [], m, D, st, verif=None)
assert "misa2" not in D and st.get("_res", ("",))[0] in ("comps_vieilles", "sans_ventes", "trop_cher"), st
print("DEALS FRAIS OK", st.get("_res"))
