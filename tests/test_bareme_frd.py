"""18 nov 2026 : l'insert 1st Round Draft (Extended #7xx) n'est pas une Young Guns ; Bedard FRD = B+."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("LOCKERROOM_DONNEES", tempfile.mkdtemp())
import bareme_iq as b
s = b.sorte("2023-24 Upper Deck Extended 1st Round Draft Connor Bedard #740 RC Blackhawks")
assert s == ("B", "frd"), s
assert b.sorte("2023-24 Upper Deck Extended Young Guns Connor Bedard #701")[1] == "yg"
assert b.sorte("2023-24 Upper Deck Extended Connor Bedard #701 RC")[1] == "yg"     # le numero dit encore YG sans le mot
assert b.lettre(b.note_finale(b.NOTE["B"], 95)) == "B+"
print("OK test_bareme_frd")
