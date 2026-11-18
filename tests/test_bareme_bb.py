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
assert b.sorte("2013 BBM 1st Version Shohei Ohtani #F91 Red Wing")[0] == "A+"
assert b.sorte("1955 Topps #164 Roberto Clemente RC SGC 1")[0] == "A+"
assert b.sorte("2025 Topps Allen & Ginter Wood Mini Aaron Judge 1/1")[0] == "A+"
assert b.sorte("2025 Topps Allen & Ginter No Number Mini Paul Skenes")[0] == "A-"
# 18 nov (2e passe) : Bowman 1952-1955, Heritage, integration
assert b.sorte("1954 Bowman #66 Ted Williams PSA 4") == ("A+", "icone")
assert b.sorte("1953 Bowman Color #59 Mickey Mantle")[0] == "A"
assert b.sorte("1955 Bowman #179 Hank Aaron")[0] == "A"
assert b.sorte("1952 Topps #312 Jackie Robinson PSA 5") == ("A+", "icone")
assert b.sorte("1949 Bowman #224 Satchel Paige")[0] == "A"
assert b.sorte("1948 Leaf #138 Larry Doby RC")[0] == "A"
assert b.sorte("2022 Topps Heritage Mike Trout Error Variation") == ("A-", "heritage_rare")
assert b.sorte("2022 Topps Heritage Juan Soto Image Variation") == ("B+", "heritage_variation")
assert b.sorte("1952 Topps #340 Joe Random") == ("B", "vintage_high")
assert b.sorte("1952 Topps #12 Joe Random") == ("C+", "vintage")
assert b.sorte("1955 Bowman #300 Joe Umpire") == ("B", "vintage_high")
assert b.sorte("1973 Topps #600 Joe Random")[1] == "vintage_high"
assert len(astuces.astuces_baseball("fr")) == 26
# 18 nov (5e passe) : annees 70 et inserts 90
assert b.sorte("1975 Topps #223 Robin Yount") == ("A", "icone")
assert b.sorte("1979 Topps #116 Ozzie Smith RC")[0] == "A"
assert b.sorte("1978 Topps #707 Paul Molitor Alan Trammell RC")[0] == "A-"
assert b.sorte("1998 Metal Universe Precious Metal Gems Derek Jeter /50") == ("A+", "icone")
assert b.sorte("1991 Donruss Elite Nolan Ryan /10000")[0] == "B+"
assert b.sorte("1991 Donruss Joe Smith") == ("D", "junk_wax")
# 18 nov (4e passe) : annees 60 et Japon
assert b.sorte("1968 Topps #177 Nolan Ryan Jerry Koosman PSA 5") == ("A+", "icone")
assert b.sorte("1969 Topps #260 Reggie Jackson RC")[0] == "A+"
assert b.sorte("1960 Topps #148 Carl Yastrzemski RC") == ("A-", "icone")
assert b.sorte("1993 BBM #239 Ichiro Suzuki RC") == ("A+", "icone")
assert b.sorte("1993 BBM #423 Hideki Matsui")[0] == "A-"
assert b.sorte("1968 Topps Bob Random") == ("C+", "vintage")
assert b.joueur_connu("1960 Topps Yastrzemski") == "Carl Yastrzemski"
print("BAREME BB OK")
