"""31 oct 2026 - collection : photo studio montree + originale gardee ; valeur par les ventes reelles. Aucun reseau."""
import base64, io, json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import lockerroom, photos_cartes, vendues

def _jpg(c):
    from PIL import Image
    b = io.BytesIO(); Image.new("RGB", (300, 400), c).save(b, "JPEG", quality=95)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()

def main():
    d = tempfile.mkdtemp()
    api = lockerroom.Api(os.path.join(d, "t.db")) if lockerroom.Api.__init__.__code__.co_argcount > 1 else lockerroom.Api()
    photos_cartes.dossier = lambda: d
    st, orig = [_jpg((200, 10, 10)), _jpg((10, 200, 10))], [_jpg((1, 2, 250)), _jpg((90, 90, 90))]
    r = api.carte_garder({"carte": {"joueur": "Ivan Demidov", "emplacement": "Collection", "photos_orig": "x"},
                          "titre": "2025-26 Upper Deck Premier Ivan Demidov Dual Rookie Patch /25", "photos": st, "originales": orig})
    assert r["ok"], r
    c = api.carte_lire(r["id"])
    assert len(json.loads(c["photos"])) == 2 and len(json.loads(c["photos_orig"])) == 2
    assert set(json.loads(c["photos"])).isdisjoint(json.loads(c["photos_orig"]))
    # memes photos -> pas de doublon d'originales
    r2 = api.carte_garder({"carte": {"emplacement": "Collection"}, "titre": "x carte test", "photos": st[:1], "originales": st[:1]})
    assert not api.carte_lire(r2["id"]).get("photos_orig")
    # valeur : 3 ventes qui se tiennent -> valeur sure, gardee
    from datetime import datetime, timedelta
    j = lambda n: (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d")
    vendues.memes_annonce = lambda t, **k: {"ventes": [{"prix": 300, "le": j(3), "titre": t}, {"prix": 320, "le": j(10), "titre": t},
                                                       {"prix": 340, "le": j(20), "titre": t}]}
    v = api.carte_valeur(r["id"])
    assert v["ok"] and v["n"] == 3 and v["valeur"] and 290 <= v["valeur"] <= 340, v
    assert api.carte_lire(r["id"])["valeur"] == v["valeur"]
    # 1 seule vente : la mediane (= cette vente), dite « 1 vente », gardee seulement si la carte n'avait pas de valeur
    vendues.memes_annonce = lambda t, **k: {"ventes": [{"prix": 410, "le": j(5), "titre": t}]}
    v = api.carte_valeur(r["id"])
    assert v["n"] == 1 and v["valeur"] == 410 and not v["sure"]
    assert api.carte_lire(r["id"])["valeur"] != 410
    vendues.memes_annonce = lambda t, **k: {"ventes": []}
    assert api.carte_valeur(r["id"])["n"] == 0
    # supprimer : les originales partent aussi
    refs = json.loads(api.carte_lire(r["id"])["photos_orig"])
    api.carte_supprimer(r["id"])
    assert not any(os.path.exists(os.path.join(d, x.split("/")[-1])) for x in refs)
    print("ok")

if __name__ == "__main__":
    main()


def test_double_joueur():
    """31 oct 2026 : Demidov / Fowler Dual Rookie Patch-Taculars /25 : ses propres ventes ne sont plus refusees."""
    import cartes_match as cm
    c = cm.cible_titre("2025-26 Upper Deck Premier Dual Rookie Patch-Taculars Ivan Demidov Jacob Fowler /25 #DRPT-DF")
    assert c["autres_joueurs"] == ["jacob fowler"] and "fowler" in cm.requete_ebay(c)
    for v in ["2025-26 Upper Deck Premier Ivan Demidov Jacob Fowler Dual Rookie Patch-Taculars /25 Canadiens",
              "2025-26 UD Premier Demidov Fowler Dual Rookie Patch 12/25 RPA",
              "2025 Upper Deck Premier Ivan Demidov Jacob Fowler Dual Rookie Patchtaculars 17/25 Montreal"]:
        assert cm.raisons_refus(c, v) == [], (v, cm.raisons_refus(c, v))
    for v in ["2025-26 Upper Deck Premier Ivan Demidov Rookie Patch-Taculars /25",
              "2025-26 Premier Dual Rookie Patch-Taculars Lane Hutson Ivan Demidov /25",
              "2025-26 Premier Ivan Demidov Jacob Fowler Dual Rookie Patch Auto /25"]:
        assert cm.raisons_refus(c, v), v


if __name__ == "__main__":
    test_double_joueur()
    print("ok double joueur")


def test_beckett_prenom():
    """1er nov 2026 : « Beckett Sennecke » (prenom) n'est pas une gradation Beckett ; une raw ne se compare qu'a des raws."""
    import cartes_match as cm
    c = cm.cible_titre("2025-26 Upper Deck Beckett Sennecke Young Guns Anaheim Ducks")
    assert c["grade"] is None and not c["veut_grade"] and "bgs" not in cm.requete_ebay(c)
    assert cm.raisons_refus(c, "2025-26 Upper Deck Beckett Sennecke Young Guns BGS 9.5 Gem Mint #461") == ["gradée"]
    assert cm.raisons_refus(c, "2025-26 UD Beckett Sennecke Young Guns PSA 10") == ["gradée"]
    assert cm.raisons_refus(c, "2025-26 Upper Deck Young Guns Beckett Sennecke #461 RC Ducks") == []
    assert cm.decoder("Bedard YG Beckett 9.5")["grade"] == {"cie": "bgs", "note": "9.5"}


if __name__ == "__main__":
    test_beckett_prenom()
    print("ok beckett")
