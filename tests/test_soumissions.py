"""1er nov 2026 - soumissions de gradation groupees."""
import os, sys, tempfile, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import lockerroom


def main():
    api = lockerroom.Api()
    ids = [api.carte_sauver({"titre": f"Carte {i}", "joueur": f"Joueur {i}", "annee": "2025-26", "marque": "Upper Deck", "set_nom": "Series 1",
                             "numero": str(200 + i), "emplacement": "Collection", "statut": "En stock", "valeur": 100 + i, "cout": 50})["id"]
           for i in range(3)]
    r = api.soumission_creer({"compagnie": "PSA", "service": "Value", "numero": "123", "retour_prevu": "2026-01-01", "cout_carte": 25,
                              "cartes": ids, "valeurs": {str(ids[0]): 300}})
    assert r["ok"] and r["n"] == 3, r
    assert not api.soumission_creer({"cartes": ids})["ok"]                     # deja envoyees
    l = api.soumissions_liste()["soumissions"]
    assert len(l) == 1 and l[0]["n"] == 3 and l[0]["valeur_declaree"] == 300 + 101 + 102 and l[0]["cout_total"] == 75 and l[0]["retard"]
    assert json.loads(api.carte_lire(ids[1])["envoi_json"])["soumission"] == "123"
    assert api.soumission_maj(r["id"], {"numero": "999"})["ok"]
    assert json.loads(api.carte_lire(ids[2])["envoi_json"])["soumission"] == "999"
    csv = api.soumission_csv(r["id"])
    assert csv["ok"] and "Joueur 1" in csv["csv"] and "999" in csv["nom"]
    assert api.soumission_retour(r["id"], {str(ids[0]): {"grade": "PSA 10", "cert": "11112222"}})["n"] == 3
    c = api.carte_lire(ids[0])
    assert c["grade"] == "PSA 10" and c["cout"] == 75 and c["envoi_json"] is None
    l = api.soumissions_liste()["soumissions"]
    assert l[0]["statut"] == "revenue" and l[0]["n"] == 3 and l[0]["cartes"][0]["revenue"]
    print("ok")


if __name__ == "__main__":
    main()
