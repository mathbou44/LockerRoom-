"""13 nov 2026 (Mathieu : « les cartes doivent continuer de loader meme quand le cell se ferme ou l'app se ferme ») : le lot
lu au serveur : envoi, lecture en arriere-plan, carte gardee, reprise, a reprendre, retrait."""
import base64, io, json, os, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
comptes.MULTI = False
import lockerroom, vision
from PIL import Image

def jpeg(c):
    b = io.BytesIO(); Image.new("RGB", (400, 560), c).save(b, "JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()

api = lockerroom.Api(os.path.join(os.environ["LOCKERROOM_DONNEES"], "t.db"))
api.reglages_sauver({"ia_photos_ok": True})
appels = []
def faux_identifier(photos):
    appels.append(len(photos))
    import base64 as _b, io as _io
    from PIL import Image as _I
    _px = _I.open(_io.BytesIO(_b.b64decode(str(photos[0]).split(",", 1)[-1]))).convert("RGB").getpixel((2, 2))
    if _px[1] > 100 and _px[0] < 100:                  # la paire verte (n 2) : deux cartes differentes (2 lectures en parallele)
        return {"ok": True, "champs": {"joueur": "B", "sport": "hockey"}, "a_verifier": [], "photos": [{"cote": "devant"}, {"cote": "devant"}], "meme_carte": False}
    return {"ok": True, "champs": {"joueur": "A", "sport": "hockey", "set_nom": "Series 1"}, "a_verifier": ["parallele"],
            "photos": [{"cote": "dos", "coins": [[1, 1], [9, 1], [9, 9], [1, 9]]}, {"cote": "devant", "coins": [[2, 2], [8, 2], [8, 8], [2, 8]]}], "meme_carte": True}
vision.identifier = faux_identifier
lockerroom.Api.annonce_preparer = lambda self, ch, langue=None: {"ok": True, "titre": "2019 Series 1 A", "prix": {"marche": 42}}

# 1. envois : les photos sont gardees, la lecture se fait seule
r1 = api.lot_soumettre({"lot": "lot1234", "n": 1, "cle": "cleaaaa11", "photos": [jpeg("red"), jpeg("blue")], "but": "vente"})
r2 = api.lot_soumettre({"lot": "lot1234", "n": 2, "cle": "cleaaaa22", "photos": [jpeg("green"), jpeg("white")], "but": "vente"})
assert r1["ok"] and r2["ok"], (r1, r2)
assert api.lot_soumettre({"lot": "lot1234", "n": 1, "cle": "cleaaaa11", "photos": [jpeg("red")]})["deja"]     # un envoi refait
for _ in range(60):
    e = api.lot_etat()
    if not e["restant"]:
        break
    time.sleep(0.5)
t = {x["n"]: x for x in e["travaux"]}
assert t[1]["etat"] == "verifier" and t[1]["carte_id"] and t[1]["douteux"] == ["parallele"], t[1]
assert t[2]["etat"] == "revoir" and "même carte" in t[2]["raison"], t[2]
c = api.carte_lire(t[1]["carte_id"])
assert c["titre"] == "2019 Series 1 A" and c["prix_demande"] == 42 and "parallèle" in (c.get("note") or ""), c
assert json.loads(c["coins_json"])[0] == [[2, 2], [8, 2], [8, 8], [2, 8]], c["coins_json"]       # dos puis devant : remis dans l'ordre
assert json.loads(c["photos"])[0] == t[1]["vig"]
# 2. reprendre avec de nouvelles photos ; retirer
vision.identifier = lambda photos: {"ok": True, "champs": {"joueur": "C"}, "a_verifier": [], "photos": [{"cote": "devant"}], "meme_carte": True}
assert api.lot_relancer(t[2]["id"], [jpeg("black")])["ok"]
for _ in range(60):
    e = api.lot_etat()
    if not e["restant"]:
        break
    time.sleep(0.5)
assert {x["n"]: x for x in e["travaux"]}[2]["etat"] == "ok"
r3 = api.lot_soumettre({"lot": "lot1234", "n": 3, "cle": "cleaaaa33", "photos": [jpeg("yellow")]})
vision.identifier = lambda photos: (_ for _ in ()).throw(vision.Erreur("Tes 25 photos du mois sont utilisées."))
for _ in range(60):
    e = api.lot_etat()
    if not e["restant"]:
        break
    time.sleep(0.5)
x3 = {x["n"]: x for x in e["travaux"]}[3]
assert x3["etat"] == "revoir" and "25 photos" in x3["raison"], x3
assert api.lot_retirer([x3["id"]])["retires"] == 1
assert 3 not in {x["n"] for x in api.lot_etat()["travaux"]}
# 3. sans consentement : rien
api.reglages_sauver({"ia_photos_ok": False})
assert api.lot_soumettre({"lot": "lot1234", "n": 4, "cle": "cleaaaa44", "photos": [jpeg("red")]})["consentement_requis"]
# 4. 11 nov 2026 (le dos d'une autre carte) : chaque paire est revue une fois (gardee), et le dos se retire
api.reglages_sauver({"ia_photos_ok": True})
cid = t[1]["carte_id"]
vus = []
vision.verifier_paires = lambda paires: (vus.append(len(paires)), [{"meme": False, "devant": "A", "dos": "Necas"} for _ in paires])[1]
r = api.paires_verifier({"ids": [cid]})
assert r["ok"] and r["res"][str(cid)]["meme"] is False and vus == [1], (r, vus)
assert api.paires_verifier({"ids": [cid]})["res"][str(cid)]["dos"] == "Necas" and vus == [1]      # garde : pas payee 2 fois
avant = json.loads(api.carte_lire(cid)["photos"])
r = api.carte_photo_retirer(cid, 1)
assert r["ok"] and r["photos"] == avant[:1], r
assert not api.carte_photo_retirer(cid, 0)["ok"]                    # jamais sans photo
assert api.paires_verifier({"ids": [cid]})["res"] == {}            # une seule photo : rien a verifier
print("OK lot au serveur")
