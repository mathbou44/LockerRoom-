"""Le pouls du hobby (python tests/test_pouls.py) : ventes simulees, aucun appel reseau."""
import os
import sys
import tempfile
from datetime import datetime, timedelta

os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pouls  # noqa: E402

J0 = datetime(2026, 10, 1, 12)
ETAT = {"rythme": {}, "prix": {}, "appels": 0}


def faux(q, fond=True):
    """240 ventes au plus, la plus recente a J0 ; rythme = ventes par jour."""
    ETAT["appels"] += 1
    r, p, fin = ETAT["rythme"].get(q, 20), ETAT["prix"].get(q, 50), ETAT["fin"]
    l = []
    for i in range(240):
        m = fin - timedelta(days=i / r)
        if m < fin - timedelta(days=40):
            break
        l.append({"titre": f"{q} #{i}", "prix": p + (i % 7), "le": m.strftime("%Y-%m-%d"), "ts": m.isoformat(timespec="seconds"),
                  "url": f"https://ebay/{q}/{fin.date()}/{i}"})
    return {"ventes": l, "erreur": None}


# vitesse juste meme quand 240 ventes couvrent quelques heures
ETAT["fin"] = J0
ETAT["rythme"]["michael jordan"] = 800
v = pouls._vitesse(faux("michael jordan")["ventes"])
assert 700 < v < 900, v
# 1re mesure : tout le monde « en mesure »
n = pouls.rafraichir(n=len(pouls.SEGMENTS), rechercher=faux, maintenant=J0)
assert n == len(pouls.SEGMENTS)
r = pouls.resume(maintenant=J0)
assert all(x["chaleur"] is None for x in r["segments"]) and pouls.indice(maintenant=J0) is None
# pas refait avant 3 jours
a = ETAT["appels"]; assert pouls.rafraichir(n=10, rechercher=faux, maintenant=J0 + timedelta(days=1)) == 0 and ETAT["appels"] == a
# 8 jours plus tard : les annees 90 accelerent (x1,6) et montent (+20 %), le vintage ralentit
J1 = J0 + timedelta(days=8); ETAT["fin"] = J1
for q in ("1997 insert", "1998 refractor", "1996 insert"):
    ETAT["rythme"][q] = 32; ETAT["prix"][q] = 60
for q in ("1969 topps", "1972 topps", "1979 o-pee-chee"):
    ETAT["rythme"][q] = 10
pouls.rafraichir(n=len(pouls.SEGMENTS), rechercher=faux, maintenant=J1)
r = pouls.resume(maintenant=J1)["segments"]
assert r[0]["cle"] == "annees90" and r[0]["chaleur"] >= 2, r[0]
vin = next(x for x in r if x["cle"] == "vintage"); assert vin["chaleur"] == -1, vin
jor = next(x for x in r if x["cle"] == "jordan"); assert jor["chaleur"] == 0, jor
i = pouls.indice(maintenant=J1); assert i["cle"] == "annees90" and len(i["exemples"]) == 8 and "années 90" in i["nom"]
assert pouls.indice("en", maintenant=J1)["nom"] == "90s inserts"
# une mesure trop vieille (plus de 10 jours) : on ne dit plus rien
assert pouls.indice(maintenant=J1 + timedelta(days=12)) is None
# SoldComps en erreur : on s'arrete sans rien casser
ETAT["fin"] = J1 + timedelta(days=4)
assert pouls.rafraichir(n=3, rechercher=lambda q, fond=True: {"ventes": [], "erreur": "plafond du jour"}, maintenant=J1 + timedelta(days=4)) == 0
# l'astuce
import astuces  # noqa: E402
pouls_indice = pouls.indice
pouls.indice = lambda langue="fr", maintenant=None: pouls_indice(langue, J1)
x = astuces.pouls_hobby(None, "fr"); assert x["lien"] == "#pouls/annees90" and x["titre"].startswith("Psst") and "années 90" in x["texte"]
print("POULS OK")
