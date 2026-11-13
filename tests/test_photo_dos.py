"""9 nov 2026 : changer la photo du devant OU du dos (camera ou phototheque)."""
import base64
import io
import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LR_DONNEES"] = tempfile.mkdtemp()
from PIL import Image
import lockerroom

def ph(c):
    b = io.BytesIO(); Image.new("RGB", (600, 800), c).save(b, "JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()
api = lockerroom.Api()
cid = api.carte_sauver({"titre": "Test", "emplacement": "Collection", "statut": "En stock"})["id"]
r = api.carte_photo_changer(cid, ph((200, 0, 0)))
assert r["ok"] and len(r["photos"]) == 1
r2 = api.carte_photo_changer(cid, ph((0, 200, 0)), 1)            # ajoute le dos
assert r2["ok"] and len(r2["photos"]) == 2 and r2["photos"][0] == r["photos"][0], r2
r3 = api.carte_photo_changer(cid, ph((0, 0, 200)), 1)            # remplace le dos
assert len(r3["photos"]) == 2 and r3["photos"][0] == r["photos"][0] and r3["photos"][1] != r2["photos"][1], r3
r4 = api.carte_photo_changer(cid, ph((9, 9, 9)))                 # remplace le devant
assert r4["photos"][1] == r3["photos"][1] and r4["photos"][0] != r3["photos"][0]
r5 = api.carte_photos_inverser(cid)                                # 13 nov : inverser devant et dos
assert r5["ok"] and r5["photos"] == [r4["photos"][1], r4["photos"][0]] and api.carte_lire(cid)["photo"] == r4["photos"][1], r5
assert not api.carte_photos_inverser(api.carte_sauver({"titre": "Une seule", "statut": "En stock"})["id"])["ok"]
print("OK photo devant / dos")
