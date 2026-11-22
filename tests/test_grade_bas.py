"""22 nov 2026 (Mathieu : « tout ce qui est gradé 8 et moins, traiter comme une raw pour le bid price et les comps, mais pas
mettre des 9 ou des 10 » ; une Evan Bouchard Young Guns ACA 8.5)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cartes_match as c, deals
cb = c.cible_titre("2018-19 Upper Deck #221 Evan Bouchard YG Rookie Card ACA 8.5 NMM+ Young Guns")
assert cb["grade"] is None and cb["grade_bas"]["cie"] == "aca" and not cb["veut_grade"]
assert c.requete_ebay(cb) == "evan bouchard young guns"                       # cherchee comme une brute
ok = lambda t: not c.raisons_refus(cb, t)
assert ok("2018-19 Upper Deck Evan Bouchard Young Guns #221 RC")             # les brutes : oui
assert ok("2018-19 Upper Deck Evan Bouchard Young Guns #221 PSA 8")          # une autre note sous 9 : oui
for t in ("PSA 10", "PSA 9", "BGS 9.5", "ACA 10"):                          # les 9 et les 10 : jamais
    assert not ok("2018-19 Upper Deck Evan Bouchard Young Guns #221 " + t), t
assert deals._facteur_note(None, {"cie": "psa", "note": "10"}) is None       # jamais ramenee a une brute
assert deals._facteur_note(None, {"cie": "psa", "note": "8"}) == 1.0
assert c.cible_titre("2018-19 Upper Deck Evan Bouchard Young Guns PSA 9")["grade"]["note"] == "9"   # 9 et plus : inchange
print("GRADE BAS OK")
