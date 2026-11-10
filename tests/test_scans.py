"""9 nov 2026 : une page de numeriseur avec plusieurs cartes -> une image par carte ; le scan des dos s'apparie."""
import os
import random
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image, ImageDraw
import scans


def page(fond, positions, couleurs, penche=0):
    W, H = 2550, 3300                                   # lettre a 300 ppp
    im = Image.new("RGB", (W, H), fond)
    for (x, y), col in zip(positions, couleurs):
        c = Image.new("RGB", (750, 1050), col)
        d = ImageDraw.Draw(c)
        d.rectangle([40, 40, 710, 1010], outline=(250, 250, 250), width=18)     # bordure blanche imprimee
        d.text((100, 900), "PLAYER NAME", fill=(255, 255, 255))
        if penche:
            c = c.convert("RGBA").rotate(penche, expand=True, fillcolor=(0, 0, 0, 0))
            im.paste(c, (x, y), c)
        else:
            im.paste(c, (x, y))
    return im


random.seed(3)
pos = [(110 + i * 820, 80 + j * 1065) for j in range(3) for i in range(3)]   # 3 x 3, serre comme un vrai scan
cols = [(random.randint(20, 200), random.randint(20, 200), random.randint(20, 200)) for _ in pos]
for fond in ((252, 252, 250), (12, 12, 14)):
    r = scans.decouper(page(fond, pos, cols))
    assert len(r) == 9, (fond, len(r))
    assert r[0]["centre"][0] < r[1]["centre"][0] < r[2]["centre"][0] and r[0]["centre"][1] < r[3]["centre"][1], [c["centre"] for c in r]
    for c in r:
        w, h = c["image"].size
        assert 750 <= w <= 900 and 1050 <= h <= 1250, c["image"].size
# 4 cartes un peu penchees, sur couvercle blanc
r = scans.decouper(page((250, 250, 250), pos[:4], cols[:4], penche=4))
assert len(r) == 4, len(r)
# les dos : retournes sur place (memes positions), ou la page entiere retournee (miroir)
dv = scans.decouper(page((250, 250, 250), pos[:5], cols[:5]))
ds = scans.decouper(page((250, 250, 250), pos[:5], [(90, 90, 90)] * 5))
assert scans.apparier(dv, ds) == [0, 1, 2, 3, 4], scans.apparier(dv, ds)
W = 2550
miroir = [(W - x - 750, y) for x, y in pos[:5]]
dm = scans.decouper(page((250, 250, 250), miroir, [(90, 90, 90)] * 5))
p_ = scans.apparier(dv, dm)
assert None not in p_ and len(set(p_)) == 5, p_
for i, j in enumerate(p_):                               # chaque dos est au miroir de son devant
    assert abs((1 - dv[i]["centre"][0]) - dm[j]["centre"][0]) < 0.05
print("OK scans")
