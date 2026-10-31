"""31 oct 2026 - populaires et a liquider (suivis + vues des annonces)."""
import os, sys
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lockerroom

M = datetime(2026, 10, 31, 12)
def c(i, w=0, v=None, j=40, st="Listée"):
    return {"id": i, "statut": st, "item_number": str(1000 + i), "watchers": w, "vues": v,
            "debut": (M - timedelta(days=j)).isoformat(), "joueur": f"J{i}"}

def test_rien_en_ligne():
    r = lockerroom.popularite([c(1, st="En stock")], M)
    assert r["populaires"] is None and r["liquider"] is None

def test_populaires_et_liquider():
    l = [c(1, w=3, v=50), c(2, w=0, v=200), c(3, w=0, v=20), c(4, w=0, v=2, j=45), c(5, w=0, v=3, j=10),
         c(6, w=1, v=1, j=90), c(7, w=0, v=None, j=60)]
    r = lockerroom.popularite(l, M)
    assert r["populaires_ids"] == [1, 2]                 # suivis d'abord, puis beaucoup de vues
    assert 4 in r["liquider_ids"] and 7 in r["liquider_ids"]
    assert 5 not in r["liquider_ids"]                    # trop recente
    assert 6 not in r["liquider_ids"]                    # 1 suivi : quelqu'un s'y interesse
    assert 2 not in r["liquider_ids"]
    assert r["top"]["id"] == 1

def test_sans_vues_suivis_seulement():
    r = lockerroom.popularite([c(1, w=2), c(2, w=0, j=50), c(3, w=0, j=5)], M)
    assert r["populaires_ids"] == [1] and r["liquider_ids"] == [2]

def test_programmee_ignoree():
    x = c(1, w=5); x["debut"] = (M + timedelta(days=2)).isoformat()
    assert lockerroom.popularite([x], M)["populaires"] is None


if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f()
    print("ok")
