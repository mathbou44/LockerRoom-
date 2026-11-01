"""1er nov 2026 - collection par sets, valeur dans le temps, export CSV."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import lockerroom, catalogue


def main():
    api = lockerroom.Api()
    p = catalogue.charger("2025-26-ud-series-1")
    yg = next(s["nom"] for s in p["sous_ensembles"] if s["nom"] == "Young Guns")
    c1 = next(c for c in p["cartes"] if c["sous_ensemble"] == yg)
    c2 = [c for c in p["cartes"] if c["sous_ensemble"] == yg][1]
    for c, v in ((c1, 120), (c2, 40)):
        api.carte_sauver({"titre": f"2025-26 Upper Deck Series 1 Young Guns {c['joueur']} #{c['numero']}", "joueur": c["joueur"], "annee": "2025-26",
                          "marque": "Upper Deck", "set_nom": "Series 1", "parallele": "Young Guns", "numero": c["numero"], "emplacement": "Collection",
                          "statut": "En stock", "valeur": v, "cout": 60})
    api.carte_sauver({"titre": "Carte inconnue", "joueur": "Personne", "emplacement": "Collection", "statut": "En stock", "valeur": 5})
    r = api.collection_sets()
    assert r["ok"] and r["hors_checklist"] == 1, r
    pr = r["produits"][0]
    assert pr["id"] == "2025-26-ud-series-1" and pr["n"] == 2
    s = next(x for x in pr["sous"] if x["nom"] == yg)
    assert s["possedees"] == 2 and s["total"] >= 50, s
    ck = api.collection_checklist(pr["id"], yg)
    assert ck["possedees"] == 2 and sum(1 for x in ck["cartes"] if x["a"]) == 2
    v = api.collection_valeur()
    assert v["valeur"] == 165 and v["hausses"][0]["gain"] == 60 and v["baisses"][0]["gain"] == -20
    csvr = api.collection_csv()
    assert c1["joueur"] in csvr["csv"] and "Young Guns" in csvr["csv"]
    print("ok")


if __name__ == "__main__":
    main()
