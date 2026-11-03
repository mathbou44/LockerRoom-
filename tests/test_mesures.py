"""3 nov 2026 (Mathieu : « on doit etre meilleur que tout ce qui est presente ») : les mesures de l'app (mesures.py) :
centrage par paires en miroir (et decentrage de design a verifier), blanchiment mesure en mm, qualite de la photo ; et
l'examen complet avec un modele simule (aucun reseau)."""
import base64, io, os, random, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import examen, mesures, vision
vision.DOSSIER = os.environ["LOCKERROOM_DONNEES"]
from PIL import Image, ImageDraw, ImageFilter


def bordee(g, d, h, b):
    W, H = 1000, 1400
    c = Image.new("RGB", (W, H), (245, 245, 240)); dr = ImageDraw.Draw(c)
    dr.rectangle([g, h, W - d, H - b], fill=(170, 30, 40)); r = random.Random(1)
    for _ in range(400):
        x, y = r.randint(g + 5, W - d - 40), r.randint(h + 5, H - b - 40)
        dr.ellipse([x, y, x + r.randint(3, 35), y + r.randint(3, 35)], fill=(r.randint(0, 255),) * 3)
    return c.filter(ImageFilter.GaussianBlur(1))


def fenetres(dx, dy):
    """Sans bordure (photo jusqu'aux aretes), deux fenetres de patch symetriques ; la coupe est decalee de dx, dy."""
    W, H = 1400, 1000
    big = Image.new("RGB", (W + 200, H + 200)); dr = ImageDraw.Draw(big); r = random.Random(2)
    for _ in range(900):
        x, y = r.randint(0, W + 200), r.randint(0, H + 200)
        dr.ellipse([x, y, x + r.randint(5, 60), y + r.randint(5, 60)], fill=(r.randint(0, 255), r.randint(0, 255), r.randint(0, 255)))
    for x0 in (420, 860):
        dr.rectangle([x0 - 25, 320, x0 + 345, 980], fill=(180, 150, 60)); dr.rectangle([x0, 350, x0 + 320, 950], fill=(170, 30, 40))
    return big.crop((100 + dx, 100 + dy, 100 + dx + W, 100 + dy + H)).filter(ImageFilter.GaussianBlur(1))


def usee():
    """Bordure foncee sur fond noir (20 px / mm) : coin bas-gauche blanchi (~0,8 mm2), 5 mm de blanc au bord du haut."""
    W, H = 1270, 1778
    c = Image.new("RGB", (W, H), (20, 40, 120)); dr = ImageDraw.Draw(c)
    dr.rectangle([150, 150, W - 150, H - 150], fill=(200, 60, 50))
    dr.polygon([(0, H - 1), (0, H - 25), (25, H - 1)], fill=(235, 235, 230))
    dr.rectangle([400, 0, 500, 8], fill=(240, 240, 235))
    ph = Image.new("RGB", (W + 200, H + 200), (15, 15, 18)); ph.paste(c, (100, 100))
    q = [[100 * 1000 / 1470, 100 * 1000 / 1978], [1370 * 1000 / 1470, 100 * 1000 / 1978], [1370 * 1000 / 1470, 1878 * 1000 / 1978], [100 * 1000 / 1470, 1878 * 1000 / 1978]]
    return ph, q

def silhouette_test():
    """Une carte grise claire (le blanc ne se mesure pas) sur fond noir, 20 px/mm : un coin haut-droit arrondi, une encoche
    de 0,5 mm x 1,5 mm sur le bord gauche. La forme les trouve ; une carte propre n'a rien."""
    W, H = 1270, 1778
    def carte(abime):
        c = Image.new("RGB", (W + 200, H + 200), (12, 12, 14)); dr = ImageDraw.Draw(c)
        dr.rectangle([100, 100, 100 + W - 1, 100 + H - 1], fill=(205, 205, 200))
        if abime:
            dr.rectangle([100 + W - 30, 100, 100 + W - 1, 130], fill=(12, 12, 14))
            dr.pieslice([100 + W - 60, 100, 100 + W - 1, 160], 270, 360, fill=(205, 205, 200))
            dr.rectangle([100, 100 + 600, 100 + 9, 100 + 630], fill=(12, 12, 14))
        return c
    q = [[100 * 1000 / 1470, 100 * 1000 / 1978], [1370 * 1000 / 1470, 100 * 1000 / 1978], [1370 * 1000 / 1470, 1878 * 1000 / 1978], [100 * 1000 / 1470, 1878 * 1000 / 1978]]
    s = mesures.silhouette(examen.redresser(carte(True), q, 0.03, 1778), 0.03)
    assert s["coins"]["haut-droit"]["relatif"] >= 0.3, s["coins"]
    enc = s["cotes"]["gauche"]["encoches"]
    assert enc and 0.3 <= enc[0]["profondeur_mm"] <= 0.7 and 29 <= enc[0]["pos_mm"] <= 33, enc
    assert not s["cotes"]["droit"]["encoches"] and not s["cotes"]["haut"]["encoches"], s["cotes"]
    p = mesures.silhouette(examen.redresser(carte(False), q, 0.03, 1778), 0.03)
    assert all(not x["encoches"] for x in p["cotes"].values() if x.get("mesurable")), p["cotes"]
    assert all(abs(x.get("relatif") or 0) < 0.1 for x in p["coins"].values() if x.get("mesurable")), p["coins"]

def surface_test():
    """Deux eclairages : la meme carte (impression identique), une rayure qui ne brille que sous la lampe de gauche ->
    la difference la montre ; deux photos identiques -> rien."""
    def photo(rayure, gauche):
        c = bordee(40, 40, 50, 50).convert("RGB")
        if rayure:
            ImageDraw.Draw(c).line([(300, 500), (700, 760)], fill=(255, 255, 255) if gauche else (150, 30, 40), width=3)
        ph = Image.new("RGB", (c.size[0] + 300, c.size[1] + 300), (14, 14, 16)); ph.paste(c, (150, 150))
        return ph
    d = mesures.difference_eclairages(photo(True, True), photo(True, False))
    d0 = mesures.difference_eclairages(photo(False, True), photo(False, False))
    assert d and d0 and d["pct_relief"] > d0["pct_relief"] + 0.05, (d and d["pct_relief"], d0 and d0["pct_relief"])
    assert mesures.relief(photo(True, True)) is not None


def main():
    r = mesures.centrage(bordee(40, 60, 50, 50))
    assert r["gd"]["ratio"] == "60/40" and r["gd"]["fiabilite"] == "haute" and r["gd"]["bordure"] and not r["gd"]["a_verifier"], r["gd"]
    assert r["hb"]["ratio"] in ("50/50", "51/49", "52/48"), r["hb"]
    r = mesures.centrage(bordee(30, 70, 60, 40))
    assert r["gd"]["ratio"] == "70/30" and not r["gd"]["a_verifier"]          # une vraie bordure : un fort decentrage est reel
    r = mesures.centrage(fenetres(0, 0))
    assert r["gd"]["ratio"] == "50/50" and r["gd"]["paires"] >= 2, r["gd"]    # sans bordure : les fenetres en miroir
    assert r["hb"]["a_verifier"], r["hb"]                                     # titre plus haut que le bas : peut-etre le dessin
    r = mesures.centrage(fenetres(40, 0))
    assert r["gd"]["ratio"] in ("56/44", "57/43", "58/42"), r["gd"]
    ph, q = usee()
    z = examen.redresser(ph, q, 0.03, 1778)
    u = mesures.usure(z, 0.03)
    assert 0.35 <= u["coins"]["bas-gauche"]["blanc_mm2"] <= 1.3 and u["coins"]["haut-droit"]["blanc_mm2"] == 0, u["coins"]
    assert 4 <= u["bords"]["haut"]["blanc_mm"] <= 6 and u["bords"]["haut"]["points"] == 1 and u["bords"]["bas"]["blanc_mm"] == 0, u["bords"]
    qq = mesures.qualite(examen.redresser(ph, q).filter(ImageFilter.GaussianBlur(3)), 20)
    assert not qq["net"] and qq["a_reprendre"], qq
    # l'examen complet, modele simule : tout net selon l'IA -> le coin MESURE devient un point a verifier (bas de fourchette)
    b = io.BytesIO(); ph.save(b, "JPEG", quality=95)
    url = "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()
    vision._cle = lambda: "test"
    vision._verifier_etat = lambda: None
    vision._noter_etat = lambda u: None
    vu = {}
    def appeler(corps, timeout=0):
        vu["texte"] = " ".join(x.get("text", "") for x in corps["messages"][0]["content"] if x.get("type") == "text")
        f = {"evaluable": True, "coins": [{"photo": 0, "coin": c, "etat": "net", "certitude": "sure"} for c in ("haut-gauche", "haut-droit", "bas-droit", "bas-gauche")],
             "bords": [{"photo": 0, "bord": c, "etat": "net", "certitude": "sure"} for c in ("haut", "droit", "bas", "gauche")], "surface": [], "surface_jugeable": True}
        return {"content": [{"type": "tool_use", "name": "etat", "input": f}], "usage": {}}
    vision._appeler = appeler
    e = vision.etat([url], quads=[q], rasante=url, rasante2=url)
    assert "DIFFERENCE entre les deux eclairages" in vu["texte"] and "FORME de la carte" in vu["texte"], vu["texte"][-600:]
    assert "MESURE de l'app" in vu["texte"] and "bas-gauche" in vu["texte"], vu["texte"][:400]
    m = [d for d in e["defauts"] if d.get("mesure")]
    assert m and m[0]["zone"] == "coin bas-gauche" and m[0]["gravite"] == "a verifier", e["defauts"]
    assert e["note_max"] == 10 and e["note_min"] <= 9 and e["mesures"]["devant"]["coins"]["bas-gauche"]["blanc_mm2"] > 0.3, (e["note_min"], e["note_max"])
    silhouette_test()
    surface_test()
    print("ok mesures")


if __name__ == "__main__":
    main()
