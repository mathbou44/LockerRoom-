"""1er nov 2026 - l'analyseur d'etat : zooms, centrage mesure, coherence, calibration et avis."""
import io, os, random, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import examen, vision, etat_verite
from PIL import Image, ImageDraw


def carte_test(g, d, h, b):
    W, H = 500, 700
    c = Image.new("RGB", (W, H), (245, 245, 240)); dr = ImageDraw.Draw(c)
    dr.rectangle([g, h, W - d, H - b], fill=(170, 30, 40))
    r = random.Random(1)
    for _ in range(300):
        x, y = r.randint(g + 5, W - d - 30), r.randint(h + 5, H - b - 30)
        dr.ellipse([x, y, x + r.randint(3, 25), y + r.randint(3, 25)], fill=(r.randint(0, 255),) * 3)
    ph = Image.new("RGB", (1200, 1500), (50, 50, 55)); ph.paste(c.resize((520, 728)), (300, 300))
    q = [(250, 200), (683.3, 200), (683.3, 685.3), (250, 685.3)]
    bb = io.BytesIO(); ph.save(bb, "JPEG", quality=92)
    return bb.getvalue(), q


def main():
    b, q = carte_test(40, 60, 50, 50)
    r = examen.preparer([b], [q])
    assert r["zooms"] and len(r["images"]) == 4          # photo, coins, bords haut-bas, bords gauche-droite
    c = r["centrage"]["devant"]
    assert c["gd"] in ("59/41", "60/40", "61/39") and c["hb"] in ("50/50", "51/49", "52/48"), c
    assert r["note_centrage"] in (9, 10)          # normes PSA : 10 jusqu'a 60/40, 9 jusqu'a 65/35
    b2, q2 = carte_test(50, 50, 52, 48)
    assert examen.preparer([b2], [q2])["note_centrage"] == 10
    # coherence : un coin blanchi plafonne les coins ; la globale ne depasse pas la pire + 0,5 ; pas de 9,5 PSA ; jamais 10 avec un defaut
    f = {"notes": {"centrage": 10, "coins": 10, "bords": 10, "surface": 10}, "note_min": 9, "note_max": 10,
         "defauts": [{"photo": 0, "zone": "coin bas-gauche", "type": "blanchiment", "gravite": "moyen", "x": 10, "y": 900}],
         "explications": {"coins": "coins nets"}, "invisible": []}
    e = vision._nettoyer_etat(f, {"devant": {"gd": "60/40", "hb": "52/48"}, "note": 9})
    assert e["notes"]["coins"] == 8 and e["notes"]["centrage"] == 9 and e["note_max"] <= 9 and e["note_min"] >= 7.5, e
    assert e["centrage_mesure"] and e["centrage_gd"] == "60/40" and "(point 1)" in e["explications"]["coins"]
    e2 = vision._nettoyer_etat({"notes": {"centrage": 10, "coins": 10, "bords": 10, "surface": 10}, "note_min": 9.5, "note_max": 10, "defauts": []})
    assert e2["note_max"] == 10 and e2["note_min"] == 9, e2
    # calibration : 15 cartes revenues un point sous l'estimation -> fourchettes decalees
    for _ in range(15):
        etat_verite.noter({"note_min": 9, "note_max": 10, "notes": {}}, "PSA 8.5", "PSA")
    cal = etat_verite.calibration()
    assert cal["n"] == 15 and cal["ecart"] == -1.0
    e3 = vision._nettoyer_etat({"notes": {"centrage": 10, "coins": 10, "bords": 10, "surface": 10}, "note_min": 9, "note_max": 10, "defauts": []}, None, cal)
    assert e3["note_max"] == 9 and e3["calibre"], e3
    assert etat_verite.precision()["n"] == 15
    # avis : 10 rejets d'un « a verifier » -> une consigne plus exigeante
    d = {"zone": "coin haut-droit", "type": "blanchiment", "gravite": "a verifier"}
    for _ in range(10):
        etat_verite.avis(d, None, False)
    assert etat_verite.regles() and "blanchiment" in etat_verite.regles()[0]
    etat_verite.avis(d, False, True)
    print("ok")


if __name__ == "__main__":
    main()


def test_grille():
    """La grille de centrage : la carte redressee gardee, ses bordures ; l'ajustement a la main change la note de centrage."""
    import base64, json, lockerroom
    b, q = carte_test(40, 60, 50, 50)
    api = lockerroom.Api()
    r = api.carte_garder({"carte": {"joueur": "G", "emplacement": "Collection"}, "titre": "G", "photos": ["data:image/jpeg;base64," + base64.b64encode(b).decode()]})
    vue = api._centrage_vue([r["photos"][0]], [q])
    assert vue["devant"]["img"] and vue["devant"]["gd"] in ("59/41", "60/40", "61/39") and 0.06 < vue["devant"]["l"] < 0.1
    e = {"notes": {"centrage": 9, "coins": 9, "bords": 9, "surface": 9}, "note_min": 8.5, "note_max": 9, "defauts": [], "centrage_vue": vue}
    c = api._db(); c.execute("UPDATE cartes SET etat_json=? WHERE id=?", (json.dumps(e), r["id"])); c.commit(); c.close()
    x = api.carte_centrage(r["id"], "devant", {"l": 0.09, "r": 0.09, "t": 0.07, "b": 0.07})
    assert x["ok"] and x["centrage_gd"] == "50/50" and x["notes"]["centrage"] == 10 and x["centrage_vue"]["devant"]["manuel"]
    y = api.carte_centrage(r["id"], "devant", None)
    assert y["centrage_gd"] == vue["devant"]["gd"] and not y["centrage_vue"]["devant"].get("manuel")
    assert not api.carte_centrage(r["id"], "devant", {"l": 0.9, "r": 0.1, "t": 0.1, "b": 0.1})["ok"]
    print("ok grille")


if __name__ == "__main__":
    test_grille()
