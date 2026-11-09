"""9 nov 2026 : le filtre « pas ce pays » des deals."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lockerroom
L = [{"titre": "A", "lieu": "US", "total": 10}, {"titre": "B", "lieu": "CA", "total": 10}, {"titre": "C", "lieu": "gb", "total": 10}, {"titre": "D", "total": 10}]
r = lockerroom.Api._deals_filtrer(L, {"pays_exclus": ["US", "GB", "<x>"]})
assert [x["titre"] for x in r] == ["B", "D"], r
assert len(lockerroom.Api._deals_filtrer(L, {})) == 4
print("OK pays exclus")
