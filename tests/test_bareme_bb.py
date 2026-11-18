"""18 nov 2026 : le bareme SlabIQ du baseball (bareme_bb) : python tests/test_bareme_bb.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bareme_bb as b
import astuces

L = lambda t: b.score(t)["lettre"]
S = lambda t: b.sorte(t)
assert S("1952 Topps #311 Mickey Mantle PSA 3")[1] == "vintage_temple"           # pas sa recrue (1951 Bowman)
assert L("1952 Topps #311 Mickey Mantle PSA 3") == "A+"
assert S("1954 Topps Hank Aaron #128 RC SGC 4") == ("A+", "rc_vintage_temple")
assert L("1909-11 T206 Ty Cobb Red Portrait PSA 2") == "A+"
assert S("2023 Bowman Chrome 1st Bowman Auto Paul Skenes CPA-PS") == ("A+", "1st_bowman_chrome_auto")
assert S("2023 Bowman Chrome Prospects 1st Bowman Jackson Holliday")[0] == "A"
assert S("1991 Donruss Joe Smith") == ("D", "junk_wax")
assert S("1990 Topps Frank Thomas No Name on Front NNOF")[1] == "erreur_celebre"
assert S("2024 Topps Now Shohei Ohtani 50/50") == ("C", "topps_now")             # imprimee sur commande ; 50/50 n'est pas un tirage
assert S("2018 Bowman Chrome Ohtani Superfractor 1/1")[0] == "A+"
assert S("2023 Panini Prizm Shohei Ohtani") == ("C", "panini_sans_licence")
assert S("2025 Topps Series 1 Aaron Judge Golden Mirror SSP") == ("A-", "ssp")
assert S("2024 Topps Chrome Elly De La Cruz Gold Refractor /50") == ("A-", "numerotee")
assert S("2024 Topps Series 2 Paul Skenes RC") == ("B+", "flagship_rc")
assert L("1975 Topps Joe Random #400") in ("D", "C")
assert b.joueur_connu("2018 Bowman Chrome Ohtani") == "Shohei Ohtani"
assert len(astuces.astuces_baseball("fr")) >= 9 and all(a["url"].startswith("https://") for a in astuces.astuces_baseball("en"))
assert b.sorte("1980 Topps #482 Rickey Henderson RC PSA 6") == ("A+", "icone")
assert b.score("2011 Topps Update #US175 Mike Trout RC")["lettre"] == "A+"
assert b.sorte("1984 Fleer Update Roger Clemens #U-27 RC")[0] == "A"
assert b.sorte("1989 Upper Deck Ken Griffey Jr #1 RC")[0] == "A-"           # une icone, mais imprimee a ~2 millions
assert b.sorte("1973 O-Pee-Chee #615 Mike Schmidt RC")[0] == "A+"
assert b.sorte("1975 O-Pee-Chee #400 Joe Random")[1] == "vintage_opc"
assert b.sorte("1993 Finest Refractor #13 John Olerud")[0] == "A"
assert len(astuces.astuces_baseball("fr")) == 15
print("BAREME BB OK")
