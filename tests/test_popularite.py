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
    # 23 nov 2026 (Mathieu : « 30 jours c'est peu ; si pas de watchers, peu ou pas de views, ou 90 jours affiche ») :
    # 60 jours sans interet, ou 90 jours en ligne quoi qu'il arrive
    l = [c(1, w=3, v=50), c(2, w=0, v=200), c(3, w=0, v=20), c(4, w=0, v=2, j=65), c(5, w=0, v=3, j=45),
         c(6, w=1, v=1, j=70), c(7, w=0, v=None, j=60), c(8, w=1, v=15, j=95), c(9, w=0, v=2, j=59)]
    r = lockerroom.popularite(l, M)
    assert r["populaires_ids"] == [1, 2]                 # suivis d'abord, puis beaucoup de vues
    assert 4 in r["liquider_ids"] and 7 in r["liquider_ids"]
    assert 5 not in r["liquider_ids"] and 9 not in r["liquider_ids"]     # 45 et 59 jours : trop tot (avant le 23 nov : 30 jours)
    assert 6 not in r["liquider_ids"]                    # 1 suivi a 70 jours : quelqu'un s'y interesse
    assert 8 in r["liquider_ids"]                        # 95 jours en ligne : a liquider, meme suivie et vue
    assert r["liquider_ids"][0] == 8 and r["liquider"] == len(r["liquider_ids"]) == 3       # la plus vieille d'abord ; le chiffre = la liste
    assert 2 not in r["liquider_ids"]
    assert r["top"]["id"] == 1

def test_sans_vues_suivis_seulement():
    r = lockerroom.popularite([c(1, w=2), c(2, w=0, j=65), c(3, w=0, j=5), c(4, w=0, j=50)], M)
    assert r["populaires_ids"] == [1] and r["liquider_ids"] == [2]

def test_programmee_ignoree():
    x = c(1, w=5); x["debut"] = (M + timedelta(days=2)).isoformat()
    assert lockerroom.popularite([x], M)["populaires"] is None


if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f()
    print("ok")
