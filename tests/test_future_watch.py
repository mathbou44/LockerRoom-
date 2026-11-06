"""6 nov 2026 (Mathieu : une Dobes « Future Watch Auto /999 » a 1 h de la fin, valeur approx -25 % alors que ses ventes
etaient la) : Future Watch est dans SP Authentic ; le code #FW-JD n'est pas un mot de la carte."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cartes_match as m
c = m.cible_titre("Jakub Dobes Future Watch Auto /999")
for v in ("2024-25 SP Authentic Future Watch Auto /999 Jakub Dobes #FW-JD RC",
          "2024-25 Upper Deck SP Authentic Jakub Dobes Future Watch Autograph RC 518/999 Canadiens"):
    assert m.raisons_refus(c, v) == [], (v, m.raisons_refus(c, v))
assert m.raisons_refus(c, "2024-25 SP Authentic Jakub Dobes Future Watch /999 RC")              # sans auto
assert m.raisons_refus(c, "2024-25 SP Authentic Limited Jakub Dobes Future Watch Auto /100")    # autre tirage
assert m.raisons_refus(c, "2024-25 SP Authentic Jakub Dobes Sign of the Times Auto /999")       # autre insert
c = m.cible_titre("2024-25 SP Authentic Jakub Dobes Future Watch Auto /999")
assert m.raisons_refus(c, "Jakub Dobes Future Watch Auto /999 RC") == []
assert m.raisons_refus(c, "2024-25 SP Authentic Jakub Dobes Auto /999")                         # Future Watch absent
assert m.raisons_refus(m.cible_titre("2007-08 The Cup Exquisite Endorsements Sidney Crosby Auto"), "Sidney Crosby Exquisite Endorsements Auto") == []
print("FUTURE WATCH OK")
