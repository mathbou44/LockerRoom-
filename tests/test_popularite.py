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

def test_liquider_sous_20_ajuster_au_dessus():
    # 24 nov 2026 (Mathieu, devant « To clear 186 » : « sous 20 $ le clear fait du sens (consignation), mais pour les cartes
    # plus cheres, simplement revoir le prix aiderait ») : sans interet et moins de 20 $ = a liquider ; 20 $ et plus = a
    # ajuster ; une annonce populaire n'est jamais ni l'une ni l'autre (avant : 95 jours et 3 suivis = les deux a la fois)
    def p(i, prix, **k):
        return dict(c(i, **k), prix_demande=prix)
    l = [p(1, 8, w=0, v=2, j=65), p(2, 19.99, w=0, v=1, j=120), p(3, 20, w=0, v=2, j=65), p(4, 150, w=1, v=12, j=95),
         p(5, 300, w=3, v=40, j=200), p(6, 12, w=2, v=5, j=100), p(7, 60, w=0, v=3, j=30), p(8, 5, w=0, v=1, j=10),
         p(9, 45, w=0, v=90, j=61), p(10, None, w=0, v=1, j=70)]
    r = lockerroom.popularite(l, M)
    assert r["liquider_ids"] == [2, 10, 1] and r["liquider"] == 3, r["liquider_ids"]       # moins de 20 $ (ou sans prix), la plus vieille d'abord
    assert r["ajuster_ids"] == [4, 3] and r["ajuster"] == 2, r["ajuster_ids"]             # 20 $ et plus : le prix a revoir
    assert set(r["populaires_ids"]) == {5, 6, 9}                                           # suivies, ou tres vues
    assert not set(r["populaires_ids"]) & (set(r["liquider_ids"]) | set(r["ajuster_ids"]))  # jamais populaire ET froide
    assert not set(r["liquider_ids"]) & set(r["ajuster_ids"]) and r["liquider_prix"] == 20.0
    assert 7 not in r["ajuster_ids"] and 8 not in r["liquider_ids"]                        # 30 et 10 jours : trop tot
    vide = lockerroom.popularite([c(1, st="En stock")], M)
    assert vide["ajuster"] is None and vide["ajuster_ids"] == []


def test_ecran_juge_un_prix_seulement_avec_l_outil():
    # 24 nov 2026 (Mathieu : « pour les "to adjust" en Pro, t'utilises les ventes actuelles ? ») : oui, par la valeur gardee sur
    # la carte ; le jugement d'un prix est maintenant coupe a la source pour un compte sans l'outil de prix
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "source", "src_app.html"), encoding="utf-8").read()
    assert "const prixOutil = () => comps() && !!(S.forfait && (S.forfait.admin || S.forfait.comps));" in src
    i = src.index("function repere(c){")
    assert src[i:i + 80].split("\n")[1].strip() == "if (!prixOutil()) return null;"
    j = src.index("function majTuileAjuster(){")
    f = src[j:src.index("\n}", j)]
    assert "const L = !prixOutil() ? [] :" in f and "...(S.invAjuster || [])" in f     # sans l'outil : seulement les froides de 20 $ et plus
    assert "prix au-dessus du marché" not in f and "tt('prix à revoir', 'price to review')" in f
    assert "if (S.valEnCours || !prixOutil()) return;" in src                             # aucune recherche de valeur sans l'outil
    assert "S.invAjuster = enLigne ? (v.ajuster_ids || []) : [];" in src


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
