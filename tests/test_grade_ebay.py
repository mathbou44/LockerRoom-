"""30 oct 2026 - « eBay a refusé : Grade (27502) is a required field » pour une PSA 6 : toutes les notes d'eBay."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import annonces
import ebay_csv
import ebay_ecriture
import ebay_moderne

ok = 0
for g, att in [("PSA 6", ("PSA", "6")), ("psa6", ("PSA", "6")), ("PSA 6.0", ("PSA", "6")), ("BGS 9.5", ("BGS", "9.5")),
               ("Beckett 9.5", ("BGS", "9.5")), ("PSA 10 GEM MINT", ("PSA", "10")), ("SGC 1", ("SGC", "1")),
               ("PSA Authentic", ("PSA", "Authentic")), ("Raw", None), ("", None), ("PSA 11", None)]:
    assert ebay_csv.lire_grade(g) == att, (g, ebay_csv.lire_grade(g))
    ok += 1
# toutes les notes de 1 a 10 ont un ID eBay
for n in ["10", "9.5", "9", "8.5", "8", "7.5", "7", "6.5", "6", "5.5", "5", "4.5", "4", "3.5", "3", "2.5", "2", "1.5", "1"]:
    cond, d = ebay_ecriture._etat({"grade": f"PSA {n}"})
    assert cond == 2750 and "<Name>27502</Name><Value>" in d, n
    ok += 1
cond, d = annonces._xml_etat({"grade": "PSA 6", "cert": "123 456 78"}, None)
assert "<Value>275028</Value>" in d and "<Value>275010</Value>" in d and "<AdditionalInfo>12345678</AdditionalInfo>" in d
cond, descs = ebay_moderne.etat_structure({"grade": "PSA 6", "cert": "12345678"}, None)
assert cond == "LIKE_NEW" and {"name": "27502", "values": ["275028"]} in descs and {"name": "27503", "additionalInfo": "12345678"} in descs
assert annonces._xml_etat({"grade": "raw"}, "nm")[0] == 4000
try:
    annonces._xml_etat({"grade": "PSA 11"}, None)
    raise AssertionError("PSA 11 aurait du etre refuse avant eBay")
except ValueError:
    pass
ok += 4
print(f"OK test_grade_ebay ({ok})")
