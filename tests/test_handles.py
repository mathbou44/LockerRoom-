"""19 nov 2026 (Mathieu, la Jack Hughes SP Authentic Signature Handles Auto « Inscribed » /10) : une Signature Handles porte
toujours une inscription : le mot du vendeur ne la separe pas de ses ventes ; elle se cherche par son nom."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("LOCKERROOM_DONNEES", tempfile.mkdtemp())
import cartes_match as cm
c = cm.cible_titre("2024-25 SP Authentic Jack Hughes Signature Handles Auto Inscribed 06/10")
q = cm.requete_ebay(c).split()
assert "handles" in q and "inscribed" not in q, q
assert cm.raisons_refus(c, "Upper Deck SP Authentic Signature Handles Auto 02/10 Jack Hughes Devils") == []
assert cm.raisons_refus(c, "2024-25 SP Authentic Jack Hughes Auto 06/10")                     # pas une Handles
assert cm.cible_titre("2024-25 SP Authentic Future Watch Auto Inscribed Lane Hutson /999")["inscr"]   # les autres : inchange
print("OK test_handles")
