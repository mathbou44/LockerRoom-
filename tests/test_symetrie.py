"""9 nov 2026 (la Letang Cosmic : « le centering est offset, il faut que tu le trouves ») : sans bordure unie, l'AXE de
symetrie du dessin et son cadre imprime donnent le centrage gauche / droite ; un dessin asymetrique est refuse."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image, ImageDraw, ImageFilter
import random
import mesures

def carte(decal, sym=True):
    W, H = 635, 889
    im = Image.new("RGB", (W, H), (40, 60, 160))
    d = ImageDraw.Draw(im)
    random.seed(3)
    for _ in range(900):                                   # un fond holo bruite (pas de bordure unie)
        x, y = random.randrange(W), random.randrange(H)
        d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(random.randrange(90, 255), random.randrange(90, 255), 255))
    m = 45                                                  # le cadre imprime : 45 px de chaque cote, decale de « decal »
    d.rectangle([m - decal, 60, W - m - decal, H - 60], outline=(15, 15, 25), width=5)
    if sym:
        cx = W // 2 - decal                                 # un dessin symetrique autour de son propre axe
        d.polygon([(cx - 150, 600), (cx, 200), (cx + 150, 600)], outline=(240, 240, 240), width=6)
        d.rectangle([cx - 200, 720, cx + 200, 780], fill=(10, 10, 10))
    else:
        d.ellipse([60, 120, 380, 520], fill=(220, 30, 30)); d.rectangle([300, 600, 600, 700], fill=(250, 250, 250))
        d.rectangle([0, 0, 2, H], fill=(40, 60, 160))
    return im.filter(ImageFilter.GaussianBlur(0.6))

r0 = mesures.symetrie_gd(carte(0))
assert r0 and r0["ratio"] in ("50/50", "51/49"), r0
r = mesures.symetrie_gd(carte(10))                          # 35 px / 55 px : 61/39
assert r and r["ratio"] in ("60/40", "61/39", "62/38") and r["l"] < 1 - r["r"], r
assert mesures.centrage(carte(10))["gd"]["ratio"] in ("60/40", "61/39", "62/38")
print("OK test_symetrie")
