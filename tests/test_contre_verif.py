"""9 nov 2026 (Mathieu, la Hutson : « ca aucun rapport ») : chaque defaut de coin / bord est contre-verifie sur son gros plan ;
rejete -> il disparait ; flou -> il ne compte pas (et l'app demande un gros plan) ; un doute ne baisse plus la note ;
une carte collee au bord de la photo -> « laisse un peu de fond »."""
import base64
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("LR_DONNEES", tempfile.mkdtemp())
from PIL import Image, ImageDraw
import vision

W, H = 1500, 2000
def carte(bas_colle=False):
    im = Image.new("RGB", (W, H), (12, 12, 14))
    d = ImageDraw.Draw(im)
    w = 1300; h = int(w * 88.9 / 63.5)
    y0 = H - h - 4 if bas_colle else 80
    d.rectangle([100, y0, 100 + w, y0 + h], fill=(205, 35, 45))
    d.rectangle([180, y0 + 90, 100 + w - 80, y0 + h - 90], fill=(230, 230, 230))
    b = io.BytesIO(); im.save(b, "JPEG", quality=95)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()

vision._cle = lambda: "test"
_cache = os.path.join(tempfile.mkdtemp(), "c.json")
vision._chemin_cache = lambda: _cache
vision._verifier_etat = lambda: None
vision._noter_etat = lambda u: None
vu = {"n": 0}
def appeler(corps, timeout=0):
    if corps["tools"][0]["name"] == "verdicts":
        vu["verif"] = " ".join(x.get("text", "") for x in corps["messages"][0]["content"] if x.get("type") == "text")
        vu["n_img"] = sum(1 for x in corps["messages"][0]["content"] if x.get("type") == "image")
        return {"content": [{"type": "tool_use", "name": "verdicts", "input": {"verdicts": [
            {"n": 1, "verdict": "rejete", "pourquoi": "pointe nette ; le blanc est le long du bord du haut"},
            {"n": 2, "verdict": "flou"},
            {"n": 3, "verdict": "confirme", "etat": "quelques_points", "pourquoi": "points blancs sur l'arete rouge"},
            {"n": 4, "verdict": "rejete"}]}}], "usage": {}}
    vu["n"] += 1
    f = {"evaluable": True, "surface_jugeable": True, "surface": [
            {"photo": 1, "type": "rayure", "visibilite": "de_pres", "certitude": "incertaine", "x": 500, "y": 500}],
         "coins": [{"photo": p, "coin": c, "etat": "net", "certitude": "sure"} for p in (0, 1) for c in ("haut-droit", "bas-gauche")]
                  + [{"photo": 0, "coin": c, "etat": "net", "certitude": "sure"} for c in ("haut-gauche", "bas-droit")]
                  + [{"photo": 1, "coin": "haut-gauche", "etat": "point_blanc", "certitude": "sure", "pourquoi": "specks near tip"},
                     {"photo": 1, "coin": "bas-droit", "etat": "point_blanc", "certitude": "probable", "pourquoi": "tip softened"}],
         "bords": [{"photo": p, "bord": b, "etat": "net", "certitude": "sure"} for p in (0, 1) for b in ("bas", "gauche")]
                  + [{"photo": 0, "bord": b, "etat": "net", "certitude": "sure"} for b in ("haut", "droit")]
                  + [{"photo": 1, "bord": "haut", "etat": "point_blanc", "certitude": "sure", "position": 300},
                     {"photo": 1, "bord": "droit", "etat": "point_blanc", "certitude": "probable", "position": 300}]}
    return {"content": [{"type": "tool_use", "name": "etat", "input": f}], "usage": {}}
vision._appeler = appeler

e = vision.etat([carte(), carte(bas_colle=True)], langue="fr")
assert "#1 : le coin haut-gauche du dos" in vu["verif"] and "#4 : le bord droit du dos" in vu["verif"], vu["verif"]
assert vu["n_img"] == 5, vu["n_img"]                      # les 4 coins du dos pour comparer + 4 gros plans
zones = [(d["photo"], d["zone"]) for d in e["defauts"]]
assert zones == [(1, "bord haut")], e["defauts"]            # le coin rejete, le flou et le bord invente ont disparu
assert e["defauts"][0]["note"] == 8 and "arete rouge" in e["defauts"][0]["pourquoi"], e["defauts"][0]
# des points fins sur UN seul bord, tout le reste net : PSA 9 (la note de Mathieu pour la Hutson)
assert e["notes"]["coins"] == 10 and e["notes"]["bords"] == 9, e["notes"]
assert e["notes"]["surface"] == 10 and e["note_min"] == e["note_max"] == 9, (e["notes"], e["note_min"], e["note_max"])   # le doute ne baisse rien
assert e["contre_verif"]["rejetes"] == ["dos coin haut-gauche", "dos bord droit"] and e["contre_verif"]["flous"] == ["dos coin bas-droit"], e["contre_verif"]
rp = " | ".join(e.get("a_reprendre") or [])
assert "dos coin bas-droit" in rp and "dos : la carte touche le bord de la photo" in rp and "devant : la carte touche" not in rp, rp
# en anglais : les libelles des defauts aussi
e2 = vision.etat([carte(), carte(bas_colle=True)], langue="en")
assert "a few white specks : 8/10" in e2["defauts"][0]["pourquoi"] and "the card touches the edge" in " ".join(e2["a_reprendre"]), e2
# la verification echoue (pas d'outil « verdicts ») : les defauts de l'IA restent, rien de mesure n'est ajoute
vision._appeler = lambda corps, timeout=0: appeler(corps) if corps["tools"][0]["name"] == "etat" else {"content": [], "usage": {}}
e3 = vision.etat([carte(), carte()], langue="fr", calibration={"n": 1})
assert {(d["photo"], d["zone"]) for d in e3["defauts"]} == {(1, "coin haut-gauche"), (1, "coin bas-droit"), (1, "bord haut"), (1, "bord droit")}, e3["defauts"]
assert not e3["contre_verif"]["fait"]
print("OK test_contre_verif")
