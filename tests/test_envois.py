"""1er nov 2026 - suivi des cartes envoyees en gradation ou en consignation (encan) ; quota de l'analyse d'etat."""
import os, sys, tempfile, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import lockerroom, comptes, vision, forfaits


def main():
    api = lockerroom.Api()
    cid = api.carte_sauver({"titre": "2025-26 Upper Deck Young Guns Ivan Demidov", "joueur": "Ivan Demidov", "emplacement": "Collection",
                            "statut": "En stock", "cout": 100})["id"]
    r = api.carte_envoi(cid, {"type": "gradation", "compagnie": "PSA", "service": "Value", "envoye_le": "2026-09-01",
                              "retour_prevu": "2026-10-15", "cout": 25, "soumission": "12345678"})
    assert r["ok"] and json.loads(r["carte"]["envoi_json"])["compagnie"] == "PSA"
    e = api.envois_en_cours()
    assert len(e["gradation"]) == 1 and e["gradation"][0]["retard"] is True
    assert any(a["cle"] == "gradation" for a in api._actions_envois())
    r = api.carte_envoi(cid, {"retour": {"grade": "PSA 10", "cert": "87654321"}})
    c = r["carte"]
    assert c["envoi_json"] is None and c["grade"] == "PSA 10" and c["cout"] == 125 and c["emplacement"] == "Collection"
    # consignation (encan)
    assert not api.carte_envoi(cid, {"type": "encan", "chez": ""})["ok"]
    r = api.carte_envoi(cid, {"type": "encan", "chez": "Boutique X", "commission": 12, "reserve": 300, "lien": "javascript:alert(1)"})
    e = json.loads(r["carte"]["envoi_json"])
    assert e["commission"] == 12 and "lien" not in e and e["alerte_jours"] == 45
    assert api.envois_en_cours()["encan"][0]["retard"] is False
    assert not api.carte_envoi(cid, {"type": "autre"})["ok"]
    # quota de l'analyse d'etat : 3 gratuit, 30 Pro
    comptes.MULTI, comptes.courant = True, lambda: "c1"
    forfaits.est_pro = lambda: False
    assert vision._limite_etat() == 3
    forfaits.est_pro = lambda: True
    assert vision._limite_etat() == 30
    print("ok")


if __name__ == "__main__":
    main()
