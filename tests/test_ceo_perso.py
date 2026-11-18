"""Abonnements perso (18 nov 2026) : ajout, pas de doublon, modif, retrait, total."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import ceo

def P():
    return ceo.lire().get("services_perso") or []

ceo.sauver({"perso_ajout": {"nom": "Netlify", "montant": 19, "devise": "USD", "periode": "mois"}})
assert len(P()) == 1 and P()[0]["montant"] == 19 and P()[0]["devise"] == "USD", P()
ceo.sauver({"perso_ajout": {"nom": "netlify ", "montant": 25}})
assert len(P()) == 1 and P()[0]["montant"] == 25, P()
# nom d'un service deja connu -> met a jour le connu, pas de tuile en double
ceo.sauver({"perso_ajout": {"nom": "CompSniper", "montant": 30, "periode": "mois"}})
assert len(P()) == 1, P()
assert ceo.lire()["services"]["compsniper"]["montant"] == 30
pid = P()[0]["id"]
ceo.sauver({"perso": {pid: {"periode": "an", "montant": 120}}})
assert P()[0]["periode"] == "an" and P()[0]["montant"] == 120
ceo.sauver({"perso_suppr": [pid]})
assert P() == []
ceo.sauver({"perso_ajout": {"nom": ""}})
assert P() == []
print("OK test_ceo_perso")
