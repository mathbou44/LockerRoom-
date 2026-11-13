"""13 nov 2026 : le badge Recrue = les vraies recrues LNH de la saison (regle du Calder). Cowan et Schaefer (2025-26 complete)
ne le sont plus en 2026-27."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import date
import indice_joueurs as I

d = date(2026, 11, 13)
assert I.saison_lnh(d) == 20262027 and I.saison_lnh(date(2027, 3, 1)) == 20262027 and I.saison_lnh(date(2027, 9, 20)) == 20272028
s = lambda an, gp, l="NHL": {"s": an * 10000 + an + 1, "l": l, "gp": gp}
schaefer = {"par_saison": [s(2024, 56, "OHL"), s(2025, 82), s(2026, 16)], "naissance": "2007-09-05", "saisons": 2}
cowan = {"par_saison": [s(2024, 64, "OHL"), s(2025, 71), s(2026, 15)], "naissance": "2005-07-20", "saisons": 2}
vraie = {"par_saison": [s(2025, 64, "WHL"), s(2026, 15)], "naissance": "2007-04-01", "saisons": 1}
essai = {"par_saison": [s(2025, 9), s(2026, 15)], "naissance": "2005-01-01", "saisons": 2}       # 9 matchs l'an dernier : encore recrue
deux = {"par_saison": [s(2022, 7), s(2025, 8), s(2026, 15)], "naissance": "2004-01-01", "saisons": 3}  # 6+ dans deux saisons : non
vieux = {"par_saison": [s(2026, 15)], "naissance": "1999-01-01", "saisons": 1}                 # 26 ans et plus : non (Calder)
echange = {"par_saison": [s(2025, 14), s(2025, 13), s(2026, 15)], "naissance": "2004-01-01"}  # 2 equipes = 27 matchs : non
assert not I.recrue_lnh(schaefer, d) and not I.recrue_lnh(cowan, d)
assert I.recrue_lnh(vraie, d) and I.recrue_lnh(essai, d)
assert not I.recrue_lnh(deux, d) and not I.recrue_lnh(vieux, d) and not I.recrue_lnh(echange, d)
assert I.recrue_lnh({"saisons": 1}, d) and not I.recrue_lnh({"saisons": 2}, d) and not I.recrue_lnh({}, d)
print("OK test_recrue_lnh")
