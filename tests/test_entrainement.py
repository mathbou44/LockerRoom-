"""3 nov 2026 (Mathieu : « va tout chercher pour entrainer notre IA ») : la banque d'entrainement (OUI explicite, retour du
gradage, avis, retrait, export) et les gros plans des coins dans l'examen (modele simule, aucun reseau)."""
import base64, io, json, os, sys, tempfile, zipfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom, vision, entrainement, etat_verite
vision.DOSSIER = os.environ["LOCKERROOM_DONNEES"]
from PIL import Image, ImageDraw, ImageFilter


def photo(couleur=(170, 30, 40), flou=0):
    ph = Image.new("RGB", (1200, 1600), (40, 40, 45))
    dr = ImageDraw.Draw(ph)
    dr.rectangle([200, 250, 1000, 1370], fill=(240, 240, 235))
    dr.rectangle([260, 320, 940, 1300], fill=couleur)
    for i in range(0, 600, 37):
        dr.line([300 + i, 400, 320 + i, 1200], fill=(250, 250, 250), width=3)
    if flou:
        ph = ph.filter(ImageFilter.GaussianBlur(flou))
    b = io.BytesIO(); ph.save(b, "JPEG", quality=92)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


def main():
    vision._cle = lambda: "test"
    vision._verifier_etat = lambda: None
    vision._noter_etat = lambda u: None
    vu = {}

    def appeler(corps, timeout=0):
        if corps["tools"][0]["name"] == "verdicts":       # 9 nov 2026 : la contre-verification (rien a dire ici)
            return {"content": [], "usage": {}}
        c = corps["messages"][0]["content"]
        vu["n_images"] = sum(1 for x in c if x.get("type") == "image")
        vu["texte"] = " ".join(x.get("text", "") for x in c if x.get("type") == "text")
        f = {"evaluable": True, "coins": [{"photo": 0, "coin": k, "etat": "point_blanc" if k == "haut-gauche" else "net", "certitude": "sure"}
                                          for k in ("haut-gauche", "haut-droit", "bas-droit", "bas-gauche")],
             "bords": [{"photo": 0, "bord": k, "etat": "net", "certitude": "sure"} for k in ("haut", "droit", "bas", "gauche")],
             "surface": [], "surface_jugeable": True}
        return {"content": [{"type": "tool_use", "name": "etat", "input": f}], "usage": {}}
    vision._appeler = appeler
    api = lockerroom.Api()
    api.reglages_sauver({"ia_photos_ok": True})
    assert api.reglages_lire()["ia_entrainement_ok"] is False            # non par defaut
    cid = api.carte_sauver({"titre": "2025-26 Upper Deck Young Guns Ivan Demidov", "joueur": "Ivan Demidov", "annee": "2025-26",
                            "emplacement": "Collection", "statut": "En stock", "cout": 100})["id"]
    gp = [{"face": "devant", "coin": "haut-gauche", "photo": photo((30, 60, 160))}, {"face": "devant", "coin": "bas-droit", "photo": photo((30, 160, 60), flou=6)},
          {"face": "devant", "coin": "pas-un-coin", "photo": photo()}]
    r = api.carte_etat(cid, True, "fr", {"photos": [photo()], "quads": [None], "gros_plans": gp})
    assert r["ok"], r
    assert "GROS PLAN du coin haut-gauche du DEVANT" in vu["texte"] and "GROS PLANS fournis pour : devant haut-gauche, devant bas-droit" in vu["texte"], vu["texte"][:300]
    assert vu["n_images"] >= 7, vu["n_images"]
    assert [(g["face"], g["coin"]) for g in r["gros_plans"]] == [("devant", "haut-gauche"), ("devant", "bas-droit")], r["gros_plans"]
    assert r["gros_plans"][0]["net"] is True and r["gros_plans"][1]["net"] is False, r["gros_plans"]
    assert any("gros plan flou" in t for t in r.get("a_reprendre") or []), r.get("a_reprendre")
    # sans le OUI : rien dans la banque
    api.carte_etat_avis(cid, 0, True) if r.get("defauts") else None
    api.carte_envoi(cid, {"type": "gradation", "compagnie": "TAG", "cout": 30})
    api.carte_envoi(cid, {"retour": {"grade": "TAG 9"}})
    assert entrainement.stats()["exemples"] == 0
    # avec le OUI : le retour garde photos, examen, vraie note et sous-notes ; rien sur la personne
    api.reglages_sauver({"ia_entrainement_ok": True})
    api.carte_envoi(cid, {"type": "gradation", "compagnie": "TAG", "cout": 30})
    x = api.carte_envoi(cid, {"retour": {"grade": "TAG 8.5", "cert": "T123", "lien": "https://my.taggrading.com/card/T123",
                                         "sous_notes": {"centrage": 9.5, "coins": "8,5", "bords": 9, "surface": 12}}})
    assert x["ok"]
    s = entrainement.stats()
    assert s["exemples"] == 1 and s["avec_note"] == 1 and s["avec_sous_notes"] == 1 and s["avec_gros_plans"] == 1, s
    ex = entrainement.exemples()[0]
    assert ex["verite"]["note"] == 8.5 and ex["verite"]["sous_notes"] == {"centrage": 9.5, "coins": 8.5, "bords": 9.0}, ex["verite"]
    assert ex["carte"]["joueur"] == "Ivan Demidov" and "cout" not in json.dumps(ex["carte"]) and ex["photos"]["devant"] and len(ex["photos"]["gros_plans"]) == 2
    assert etat_verite._lire("etat_verite.json", [])[-1]["sous"] == {"centrage": 9.5, "coins": 8.5, "bords": 9.0}
    # avis : le meme examen, regroupe (la verite gardee)
    api.carte_etat_avis(cid, 0, False) if r.get("defauts") else entrainement.ajouter(api.carte_lire(cid), api.carte_lire(cid)["etat_json"], raison="avis")
    assert entrainement.stats()["exemples"] == 1 and entrainement.exemples()[0].get("verite"), entrainement.exemples()
    # l'export (admin) : dataset + photos, sans l'identifiant du compte
    ch, nom = entrainement.exporter()
    with zipfile.ZipFile(ch) as z:
        noms = z.namelist()
        ds = [json.loads(l) for l in z.read("dataset.jsonl").decode().splitlines()]
    os.remove(ch)
    assert "LISEZMOI.txt" in noms and sum(1 for n in noms if n.startswith("photos/")) == 3 and nom.endswith(".zip"), noms
    assert ds and "compte" not in ds[0]
    # le OUI retire : tout est efface (lignes et photos)
    api.reglages_sauver({"ia_entrainement_ok": False})
    assert entrainement.stats()["exemples"] == 0 and not os.listdir(os.path.join(entrainement.dossier(), "photos"))
    # sous-notes : 8 cartes ou la surface etait surestimee -> une consigne
    for _ in range(8):
        etat_verite.noter({"note_min": 9, "note_max": 10, "notes": {"surface": 10, "coins": 9}}, "TAG 8", "TAG", {"surface": 8, "coins": 9})
    rg = etat_verite.regles()
    assert any("surface" in t and "trop haute" in t for t in rg) and not any("coins etait" in t for t in rg), rg
    print("ok entrainement")


if __name__ == "__main__":
    main()


def test_reference():
    """Une carte gradee de reference (admin) : photos, note, defaut connu ; le contour d'un slab n'est pas pris pour la carte."""
    r = entrainement.ajouter_reference({"photos": [photo()], "compagnie": "PSA", "grade": "PSA 6", "carte": {"titre": "2024-25 UD Young Guns Will Smith #701"},
                                        "defauts": [{"zone": "surface", "type": "marque d'ecriture", "texte": "un 8 creuse pres de la tete"}]})
    assert r["ok"], r
    ex = [x for x in entrainement.exemples() if x["raison"] == "reference"][0]
    assert ex["verite"]["note"] == 6 and ex["verite"]["defauts_connus"][0]["type"] == "marque d'ecriture" and ex["slab"]
    assert entrainement.stats()["references"] == 1
    assert not entrainement.ajouter_reference({"photos": [photo()], "grade": ""})["ok"]
    import bareme
    assert bareme.SURFACE["marque d'ecriture"] == (6, 6, 5)
    # le contour : une fenetre plus large, couchee (le slab), ne remplace pas une carte debout bien trouvee
    import examen, mesures
    ph = Image.new("RGB", (1500, 2000), (90, 90, 95)); dr = ImageDraw.Draw(ph)
    dr.rectangle([150, 420, 1350, 1700], fill=(20, 20, 20))                 # la fenetre du slab
    dr.rectangle([360, 520, 1160, 1640], fill=(30, 140, 60))                # la carte (800 x 1120)
    q = [[360 / 1.5, 520 / 2], [1160 / 1.5, 520 / 2], [1160 / 1.5, 1640 / 2], [360 / 1.5, 1640 / 2]]
    assert mesures.meilleur_contour(ph, q) == q
    print("ok reference")


if __name__ == "__main__":
    test_reference()
