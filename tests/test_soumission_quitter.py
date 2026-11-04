"""4 nov 2026 (Mathieu : « ca dit At grading mais j'ai rien rentre ») : quitter l'assistant avant la fin ne fait pas une
soumission envoyee ; une soumission « envoyee » sans numero ni suivi (le bug d'avant) redevient « a soumettre »."""
import os, sys, tempfile, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import lockerroom

api = lockerroom.Api()
cid = api.carte_sauver({"titre": "2025-26 Premier Demidov / Fowler Dual Rookie Patch-Taculars /25", "emplacement": "Collection",
                        "statut": "En stock", "valeur": 887})["id"]
r = api.soumission_creer({"cartes": [cid], "compagnie": "PSA", "preparation": True, "mode": "classique"})
assert r["ok"], r
etape = lambda: json.loads(api.carte_lire(cid)["envoi_json"]).get("etape")
assert etape() == "preparation"
assert not api.soumission_maj(r["id"], {"envoyer": True})["ok"]                 # rien d'entre : pas envoyee
assert etape() == "preparation"
# l'ancien bug : envoyee sans rien -> reparee a la prochaine lecture de l'inventaire
c = api._db(); c.execute("UPDATE soumissions SET statut='envoyee', envoyee_le='2026-11-03' WHERE id=?", (r["id"],))
c.execute("UPDATE cartes SET envoi_json=? WHERE id=?", (json.dumps({"type": "gradation", "soumission_id": r["id"], "compagnie": "PSA"}), cid))
c.commit(); c.close()
assert etape() is None
api.inventaire_liste({})
assert etape() == "preparation", api.carte_lire(cid)["envoi_json"]
# avec un numero : envoyee pour vrai
assert api.soumission_maj(r["id"], {"numero": "12345678", "envoyer": True})["ok"]
assert etape() is None and api.soumissions_liste()["soumissions"][0]["statut"] == "envoyee"
api.inventaire_liste({})
assert api.soumissions_liste()["soumissions"][0]["statut"] == "envoyee"
# le formulaire simple (sans mode) : envoyee sans numero, expres -> reste envoyee
cid2 = api.carte_sauver({"titre": "Autre carte", "emplacement": "Collection", "statut": "En stock", "valeur": 50})["id"]
r2 = api.soumission_creer({"cartes": [cid2], "compagnie": "PSA"})
api.inventaire_liste({})
assert [x for x in api.soumissions_liste()["soumissions"] if x["id"] == r2["id"]][0]["statut"] == "envoyee"
print("ok soumission quitter")
