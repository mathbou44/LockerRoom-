"""16 nov 2026 (Mathieu : « les Kaboom, Uptown, Downtown... certaines sortes sont ultra recherchees ») : les case hits ont leur
famille (avant ils tombaient dans « Upper Deck (base) ») et une sorte au sommet du classement est « ultra »."""
import os, sys, tempfile
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import types_cartes as tc
for t, k in (("2023-24 Upper Deck Kaboom Connor Bedard KB-1", "kaboom"), ("2024-25 Upper Deck Downtown Macklin Celebrini", "downtown"),
             ("2024-25 UD Extended Uptown Lane Hutson", "uptown"), ("2025-26 Upper Deck Manga Ivan Demidov", "manga"),
             ("2023-24 Upper Deck Color Blast Connor McDavid", "color_blast"), ("2023-24 Upper Deck Young Guns Canvas Bedard", "yg_canvas"),
             ("2023-24 Upper Deck Canvas Connor McDavid C-1", "canvas"), ("2023-24 Upper Deck Young Guns Connor Bedard #201", "young_guns")):
    assert tc.famille(t)[0] == k, (t, tc.famille(t))
assert tc.niveau({"score": 92, "joueurs": 10}) == "ultra"
assert tc.niveau({"score": 92, "joueurs": 2}) == "forte"          # trop peu de joueurs pour dire « ultra »
assert tc.niveau({"score": 60, "joueurs": 30}) is None
print("TYPES ULTRA OK")
