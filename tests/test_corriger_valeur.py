"""13 nov 2026 (la Gretzky Team Logo Jumbos : « ≈ 81 $ » estime sur la tuile, 4 vraies ventes a 67 $ dans la fiche) :
la fiche corrige le deal garde : la source devient « vendues », le profit suit ; mise depassee -> retire pour tous."""
import os, sys, tempfile
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import deals
deals._ecrire({"deals": [
    {"item_id": "g1", "titre": "2025 UD Black Diamond Wayne Gretzky Team Logo Jumbos", "encan": True, "total": 43.0, "port": 13.0,
     "valeur": 250.0, "valeur_source": "approx", "mise_max": 81.0, "gain": 32.0, "v": deals.VERSION},
    {"item_id": "g2", "titre": "Une autre", "encan": True, "total": 20.0, "port": 5.0, "valeur": 100.0, "valeur_source": "approx",
     "mise_max": 40.0, "gain": 20.0, "v": deals.VERSION}], "suivis": []})
r = deals.corriger("g1", 67.0, 5.0, 43.0, source="vendues")
assert r == {"trouve": True, "retire": True}, r
assert not any(x["item_id"] == "g1" for x in deals.lire()["deals"]), "la Gretzky devait sortir des deals"
r2 = deals.corriger("g2", 120.0, 60.0, 20.0, source="vendues")
x = next(x for x in deals.lire()["deals"] if x["item_id"] == "g2")
assert not r2["retire"] and x["valeur_source"] == "vendues" and x["gain"] == 60.0 and x["valeur"] == 120.0, x
assert deals.corriger("absent", 50.0, 10.0, 20.0) == {"trouve": False, "retire": False}
print("CORRIGER VALEUR OK", x["mise_max"])
