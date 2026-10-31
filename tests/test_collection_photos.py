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
