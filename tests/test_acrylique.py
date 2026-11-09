"""9 nov 2026 (une Future Watch en acrylique prise par Mathieu) : le vrai bord d'une carte transparente est le filet clair,
pas l'image imprimee au milieu ; une carte ordinaire ne change pas ; pas de faux « bords uses » sur l'acrylique."""
import io, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image, ImageDraw
import mesures, examen
W, H = 1500, 2000
def photo(acrylique):
    im = Image.new("RGB", (W, H), (22, 22, 24))
    d = ImageDraw.Draw(im)
    x0, y0 = 90, 70
    w = 1300; h = int(w * 88.9 / 63.5)
    if acrylique:
        d.rectangle([x0, y0, x0 + w, y0 + h], outline=(200, 205, 210), width=4)          # le filet de l'acrylique
        d.rectangle([x0 + 110, y0 + 160, x0 + w - 110, y0 + h], fill=(40, 120, 150))      # l'image imprimee (plus petite)
    else:
        d.rectangle([x0, y0, x0 + w, y0 + h], fill=(40, 120, 150))
    b = io.BytesIO(); im.save(b, "JPEG", quality=92); return b.getvalue()
ac = examen.ouvrir(photo(True))
q0 = mesures.trouver_carte(ac)
qt = mesures.bord_transparent(ac, q0)
assert qt and qt[0][0] < q0[0][0] - 30 and qt[0][1] < q0[0][1] - 30, (q0, qt)
ord_ = examen.ouvrir(photo(False))
assert mesures.bord_transparent(ord_, mesures.trouver_carte(ord_)) is None
r = examen.preparer([photo(True)])
assert r["mesures"]["devant"]["transparent"] and r["mesures"]["devant"]["usure"]["transparent"], r["mesures"]
assert "TRANSPARENTE" in r["images"][1][0]
print("OK test_acrylique")
# 9 nov 2026 (la Hutson Red Prism : du blanc sur la bordure rouge du dos, « pas de la poussiere ») : de petits points de
# blanchiment sur la ligne de coupe d'une bordure coloree unie sont mesures ; une bordure sans points ne l'est pas
import examen as _ex
def rouge(points):
    im = Image.new("RGB", (W, H), (12, 12, 14))
    d = ImageDraw.Draw(im)
    x0, y0, w = 90, 70, 1300
    h = int(w * 88.9 / 63.5)
    d.rectangle([x0, y0, x0 + w, y0 + h], fill=(205, 35, 45))
    for i in range(points):
        cx = x0 + 200 + i * 90
        d.ellipse([cx - 3, y0 - 1, cx + 3, y0 + 3], fill=(235, 225, 225))
    b = io.BytesIO(); im.save(b, "PNG"); return b.getvalue()
m = _ex.preparer([rouge(6)])["mesures"]["devant"]["usure"]["bords"]["haut"]
assert (m.get("points_fins") or 0) >= 3, m
m0 = _ex.preparer([rouge(0)])["mesures"]["devant"]["usure"]["bords"]["haut"]
assert not m0.get("points_fins"), m0
print("OK points de blanchiment sur bordure coloree")
