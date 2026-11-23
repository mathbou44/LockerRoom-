"""22 nov 2026 (tests a l'aveugle : Demidov, Hughes, Michkov) : mesures.eclats trouve un eclat blanc sur une arete foncee et
du carton arrache a un coin, mais ignore une bande blanche IMPRIMEE qui rentre loin dans la carte ; trouver_carte_serree
trouve une carte qui remplit presque toute la photo ; examen.clarifier agrandit un zoom."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image, ImageDraw
import mesures, examen
W, H = 1270, 1778                                   # carte 63,5 x 88,9 mm a 20 px/mm
m = 0.03
Wm, Hm = int(round(W * (1 + 2 * m))), int(round(H * (1 + 2 * m)))
mx, my = (Wm - W) // 2, (Hm - H) // 2
im = Image.new("RGB", (Wm, Hm), (8, 8, 8))
d = ImageDraw.Draw(im)
d.rectangle([mx, my, mx + W - 1, my + H - 1], fill=(45, 40, 42))     # carte foncee
d.rectangle([mx + 600, my, mx + 606, my + 4], fill=(240, 240, 240))   # eclat blanc sur l'arete du haut (0,3 x 0,25 mm)
d.polygon([(mx + W - 1, my), (mx + W - 25, my), (mx + W - 1, my + 22)], fill=(235, 235, 232))   # carton arrache, coin haut-droit
d.rectangle([mx, my + 900, mx + 300, my + 960], fill=(235, 235, 235))  # bande imprimee qui rentre de 15 mm : pas un eclat
e = mesures.eclats(im, m)
assert e["bords"]["haut"]["points"] >= 1, e["bords"]["haut"]
assert e["coins"]["haut-droit"]["blanc_mm2"] >= 0.3, e["coins"]
assert e["coins"]["haut-gauche"]["blanc_mm2"] < 0.05, e["coins"]
assert e["bords"]["gauche"]["points"] == 0, e["bords"]["gauche"]
# une carte qui remplit presque toute la photo
ph = Image.new("RGB", (1512, 2016), (10, 10, 10))
ImageDraw.Draw(ph).rectangle([60, 30, 1450, 1975], fill=(200, 60, 60))
q = mesures.trouver_carte_serree(ph)
assert q and abs(q[0][0] - 40) <= 3 and abs(q[2][1] - 980) <= 3, q
z = examen.clarifier(ph.crop((0, 0, 100, 80)), 400)
assert z.size == (400, 320), z.size
print("OK test_eclats")
