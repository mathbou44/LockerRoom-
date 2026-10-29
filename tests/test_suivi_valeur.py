"""29 oct 2026 - l'alerte de valeur d'une carte de la collection : chaque semaine, ventes reelles ; alerte a +/-15 %
(python tests/test_suivi_valeur.py). Aucun appel reseau."""
import os
import sys
import tempfile
from datetime import datetime, timedelta

os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lockerroom  # noqa: E402
import suivi_valeur  # noqa: E402
import alarmes  # noqa: E402
alarmes._heure_locale = lambda m=None: 14          # le jour : les alertes de nuit attendent le matin

a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
pushs = []
a._push = lambda t, x, d=None: pushs.append((t, x)) or 1
cid = a.carte_garder({"carte": {"joueur": "Wayne Gretzky", "annee": "1979-80", "marque": "O-Pee-Chee", "numero": "18", "grade": "PSA 7",
                                "emplacement": "Collection", "valeur": 1400}, "titre": "1979-80 O-Pee-Chee Wayne Gretzky #18 PSA 7",
                      "prix": None, "photos": []})["id"]
titre_avant = a.carte_lire(cid)["titre"]
assert a.valeur_suivi(cid)["actif"] is False
e = a.valeur_suivi(cid, True)
assert e["actif"] and e["reference"] == 1400, e
assert suivi_valeur.ids(a) == [cid]
vals = {"v": 1500.0}
t0 = datetime(2026, 10, 29, 14, 0)
# +7 % : pas d'alerte, la valeur de la collection suit
assert suivi_valeur.verifier(a, maint=t0, valeur=lambda c: vals["v"]) == 0
assert a.carte_lire(cid)["valeur"] == 1500 and a.carte_lire(cid)["titre"] == titre_avant
# moins d'une semaine apres : pas reverifiee
vals["v"] = 2000.0
assert suivi_valeur.verifier(a, maint=t0 + timedelta(days=3), valeur=lambda c: vals["v"]) == 0
assert a.carte_lire(cid)["valeur"] == 1500
# une semaine apres : +43 % depuis la reference (1 400 $) -> alerte, la reference devient 2 000 $
assert suivi_valeur.verifier(a, maint=t0 + timedelta(days=8), valeur=lambda c: vals["v"]) == 1
assert "+43 %" in pushs[-1][0] and "Était 1400 $" in pushs[-1][1], pushs[-1]
assert a.valeur_suivi(cid)["reference"] == 2000
# baisse de 20 % la semaine d'apres
vals["v"] = 1600.0
assert suivi_valeur.verifier(a, maint=t0 + timedelta(days=16), valeur=lambda c: vals["v"]) == 1
assert "−20 %" in pushs[-1][0], pushs[-1]
# arretee : plus rien
a.valeur_suivi(cid, False)
assert suivi_valeur.ids(a) == [] and a.valeur_suivi(cid)["actif"] is False
assert suivi_valeur.verifier(a, maint=t0 + timedelta(days=40), valeur=lambda c: 99.0) == 0
print("SUIVI VALEUR OK")
