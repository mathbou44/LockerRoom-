"""9 nov 2026 (la Willander : « aucun des deux cercles n'est vrai ») : le point d'un defaut de coin ou de bord est cale sur la
vraie arete, que le contour soit un peu dehors ou un peu dedans ; une analyse enregistree est recalee une fois."""
import io
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image, ImageDraw, ImageFilter
import random
import examen
import vision

W, H = 1500, 2000
im = Image.new("RGB", (W, H), (14, 14, 16))
d = ImageDraw.Draw(im)
random.seed(1)
for _ in range(4000):                                   # un tapis avec des fibres claires
    x, y = random.randrange(W), random.randrange(H)
    d.line([x, y, x + random.randint(-6, 6), y + random.randint(-6, 6)], fill=(70, 70, 75), width=1)
x0, y0, x1, y1 = 120, 90, 1380, int(90 + 1260 * 88.9 / 63.5)
d.rectangle([x0, y0, x1, y1], fill=(170, 172, 176))
im = im.filter(ImageFilter.GaussianBlur(0.8))
vrai = [[x0 / W * 1000, y0 / H * 1000], [x1 / W * 1000, y0 / H * 1000], [x1 / W * 1000, y1 / H * 1000], [x0 / W * 1000, y1 / H * 1000]]
for dec in (-12, 12):                                   # contour 1,2 % trop dehors, puis trop dedans
    q = [[p[0] + (dec if i in (0, 3) else -dec), p[1] + (dec if i < 2 else -dec)] for i, p in enumerate(vrai)]
    for zone, (u, v), att in (("coin bas-droit", (0.98, 0.98), (x1, y1)), ("coin haut-gauche", (0.02, 0.02), (x0, y0)),
                              ("bord bas", (0.5, 0.99), (None, y1)), ("bord gauche", (0.01, 0.4), (x0, None))):
        px, py = vision._bil(q, u, v)
        r = examen.caler_point(im, q, zone, px, py)
        assert r, (dec, zone)
        gx, gy = r[0] / 1000 * W, r[1] / 1000 * H
        if att[0] is not None:
            assert abs(gx - att[0]) < 14, (dec, zone, gx, att)
        if att[1] is not None:
            assert abs(gy - att[1]) < 14, (dec, zone, gy, att)
res = {"defauts": [{"zone": "coin bas-droit", "photo": 0, "x": vrai[2][0] - 20, "y": vrai[2][1] - 15}, {"zone": "surface", "photo": 0, "x": 500, "y": 500}]}
vision.caler_defauts(res, [im], [vrai])
assert res["defauts"][0]["cale"] is True and not res["defauts"][1].get("cale"), res
print("OK calage")
