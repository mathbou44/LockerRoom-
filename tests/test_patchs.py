"""13 nov 2026 (Mathieu, la Gauthier Signature Swatches /49) : 1) « The Cup Signatures Swatches » (erreur du vendeur) est
l'insert d'ICE ; 2) une patch 2 couleurs vaut ~60 % d'une 4 couleurs : les ventes sont ramenees aux couleurs de la carte."""
import os, sys, tempfile
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import cartes_match, patchs
# 1. le titre fautif
c = cartes_match.cible_titre("2025-26 Upper Deck The Cup Signatures Swatches Cutter Gauthier #SS-CG /49")
assert not cartes_match.raisons_refus(c, "2025/26 Upper Deck Ice Hockey Signature Swatches Cutter Gauthier Auto Patch 23/49")
assert cartes_match.raisons_refus(c, "2025-26 Upper Deck The Cup Rookie Auto Patch Cutter Gauthier /99")
assert "sigpatches" in cartes_match._norm("2025-26 The Cup Signature Patches Bedard")          # The Cup Signature Patches reste The Cup
assert "the cup" in cartes_match._norm("2025-26 The Cup Signature Patches Bedard")
# 2. le bareme
assert patchs.du_titre("Bedard RPA 3 color patch /99") == 3 and patchs.du_titre("two-color patch") == 2
assert patchs.du_titre("Gauthier Signature Swatches logo patch") == 5 and patchs.du_titre("Gauthier auto /49") is None
assert abs(patchs.facteur(2, 4) - 0.6) < 1e-9 and patchs.facteur(None, 4) == 1.0 and patchs.facteur(4, 1) > 2.5
assert not patchs.est_patch("2015 Young Guns McDavid") and patchs.est_patch("Signature Swatches auto")
# la carte : 2 couleurs (photo) ; les ventes : 4, 4, 1 couleurs et une inconnue
lu = {"http://x/carte.jpg": 2, "http://x/a.jpg": 4, "http://x/b.jpg": 4, "http://x/c.jpg": 1, "http://x/d.jpg": None}
patchs.compter = lambda urls: {u: lu.get(u) for u in urls}
ventes = [{"titre": "Gauthier Signature Swatches", "prix": 285, "photo": "http://x/a.jpg"},
          {"titre": "Gauthier Signature Swatches", "prix": 250, "photo": "http://x/b.jpg"},
          {"titre": "Gauthier Signature Swatches", "prix": 41, "photo": "http://x/c.jpg"},
          {"titre": "Gauthier Signature Swatches", "prix": 150, "photo": "http://x/d.jpg"}]
r, n, vv = patchs.ajuster("Gauthier Signature Swatches /49", "http://x/carte.jpg", ventes)
assert n == 2 and r < 0.9, (r, n)
assert [v["couleurs"] for v in vv] == [4, 4, 1, None]
assert abs(vv[0]["prix_patch"] - 171) < 0.5 and abs(vv[2]["prix_patch"] - 41 * 0.6 / 0.35) < 0.5
# pas une patch, ou rien de connu : la valeur ne bouge pas
assert patchs.ajuster("McDavid Young Guns", "http://x/carte.jpg", ventes)[0] == 1.0
patchs.compter = lambda urls: {}
assert patchs.ajuster("Gauthier Signature Swatches /49", "http://x/carte.jpg", ventes)[0] == 1.0
print("PATCHS OK", r)
