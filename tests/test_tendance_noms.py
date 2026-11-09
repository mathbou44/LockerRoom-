"""9 nov 2026 (capture de Mathieu : « Ufc Moment » dans les tendances hockey) : ce qui n'est pas un joueur n'y entre pas."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tendance_stats as t
pts = [["2026-10-%02d" % d, 10 + d] for d in range(1, 28)]
cartes = [{"joueur": n, "points": pts, "carte": "2025-26 Upper Deck"} for n in ("Ufc Moment", "Team Canada", "Dylan Garand", "Pelle Lindbergh", "Card 2")]
j = {x.lower() for x in t.par_joueur(cartes)}
assert j == {"dylan garand", "pelle lindbergh"}, j
print("OK test_tendance_noms")
