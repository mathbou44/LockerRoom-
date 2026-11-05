"""5 nov 2026 (Landeskog BGS 9.5, centrage 10, lu 81/19) : dans un slab, l'examen mesure la CARTE, pas l'etui."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import examen
from PIL import Image, ImageDraw

W, H = 1500, 2000
im = Image.new("RGB", (W, H), (25, 25, 25)); d = ImageDraw.Draw(im)
d.rectangle([40, 90, 1460, 1960], fill=(150, 150, 155))                 # le slab (plastique)
d.rectangle([120, 180, 1380, 470], fill=(200, 170, 90))                 # l'etiquette
d.rectangle([250, 500, 1250, 1900], fill=(60, 60, 60))                  # l'etui interieur (cadre noir BGS)
cx0, cy0, cx1 = 300, 545, 1190                                          # la carte : 890 px de large
cy1 = cy0 + int((cx1 - cx0) / examen.CARTE_RAPPORT)
d.rectangle([cx0, cy0, cx1, cy1], fill=(230, 235, 238))
d.rectangle([cx0 + 200, cy0 + 150, cx1 - 120, cy0 + 700], fill=(160, 60, 70))   # le joueur
q = examen.carte_dans_slab(im, [[27, 45], [973, 45], [973, 980], [27, 980]])
assert q, q
vrai = [[cx0 / W * 1000, cy0 / H * 1000], [cx1 / W * 1000, cy0 / H * 1000], [cx1 / W * 1000, cy1 / H * 1000], [cx0 / W * 1000, cy1 / H * 1000]]
assert all(abs(a[0] - b[0]) <= 8 and abs(a[1] - b[1]) <= 8 for a, b in zip(q, vrai)), (q, vrai)
# une photo sans slab : le rectangle n'est pas une carte -> rien (l'examen garde son contour)
vide = Image.new("RGB", (W, H), (25, 25, 25))
assert examen.carte_dans_slab(vide, None) is None
print("CARTE DANS SLAB OK")
