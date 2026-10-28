"""29 oct 2026 - annonces programmees en serie : politiques d'eBay du vendeur, colis 250 g 23 x 16 x 3, promotion 2 %,
offres, description, une annonce toutes les 24 h (python tests/test_programmer.py). Aucun appel reseau."""
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone

os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import annonces  # noqa: E402
import ebay_compte  # noqa: E402
import lockerroom  # noqa: E402

# 1. le XML : politiques, colis, heure de mise en ligne
mod = {**annonces.MODELE_DEFAUT, "politique_exp": "111", "politique_ret": "222", "politique_pai": "333", "poids_g": 250,
       "longueur_cm": 23, "largeur_cm": 16, "hauteur_cm": 3, "promotion": 2, "offres": True}
x = annonces.xml_item({**mod, "carte": {"joueur": "Wayne Gretzky"}, "titre": "1979-80 OPC Wayne Gretzky #18 PSA 7", "prix": 1500,
                       "debut_utc": "2026-11-02T00:00:00.000Z"}, ["https://i.ebayimg.com/1.jpg"])
assert "<ShippingProfileID>111</ShippingProfileID>" in x and "<ReturnProfileID>222</ReturnProfileID>" in x and "<PaymentProfileID>333" in x
assert "<ShippingDetails>" not in x and "<ReturnPolicy>" not in x                # les politiques d'eBay remplacent les reglages
assert '<WeightMinor unit="gm">250</WeightMinor>' in x and '<PackageLength unit="cm">23</PackageLength>' in x and '<PackageDepth unit="cm">3' in x
assert "<ScheduleTime>2026-11-02T00:00:00.000Z</ScheduleTime>" in x and "<BestOfferEnabled>true" in x
x2 = annonces.xml_item({**annonces.MODELE_DEFAUT, "carte": {}, "titre": "Une carte de test ici", "prix": 10}, [])
assert "<ShippingDetails>" in x2 and "<SellerProfiles>" not in x2 and "<ScheduleTime>" not in x2

# limites : 10 min a 21 jours
m = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
assert annonces.debut_programme("2026-10-30T19:00:00-04:00", m) == "2026-10-30T23:00:00.000Z"
for mauvais in ("2026-10-29T12:03:00+00:00", "2026-11-25T12:00:00+00:00"):
    try:
        annonces.debut_programme(mauvais, m)
        raise AssertionError(mauvais)
    except ValueError:
        pass

# 2. la serie : 3 cartes, une toutes les 24 h, la promotion attend la mise en ligne
a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
ebay_compte.statut = lambda: {"connecte": True, "ecriture": True}
annonces.photos_ebay = lambda l: [str(p) for p in l]
pub = []
def ecrire(fn, *args, **kw):
    if fn == "annonces.publier":
        pub.append(args[0])
        return {"ok": True, "item_id": str(100000000 + len(pub)), "frais": 0}
    if fn == "annonces.promouvoir":
        return {"ok": True, "promotion": args[1]}
    return {"ok": True}
a._ecrire_ebay = ecrire
ids = []
for k, (j, p) in enumerate((("Wayne Gretzky", 1500), ("Mario Lemieux", 900), ("Patrick Roy", 400))):
    ids.append(a.carte_garder({"carte": {"joueur": j, "annee": "1985-86", "marque": "O-Pee-Chee"}, "titre": f"1985-86 O-Pee-Chee {j} Rookie PSA 8",
                               "prix": p, "photos": ["https://i.ebayimg.com/x%d.jpg" % k]})["id"])
cand = a.serie_candidates()["cartes"]
assert len([c for c in cand if not c["manque"]]) == 3, cand
debut = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0)
r = a.serie_programmer(ids, debut.isoformat(), 24, {"politique_exp": "111", "promotion": 2, "poids_g": 250, "longueur_cm": 23,
                                                   "largeur_cm": 16, "hauteur_cm": 3, "offres": True})
assert r["ok"], r
for _ in range(50):
    if not a.serie_etat()["en_cours"]:
        break
    time.sleep(0.1)
e = a.serie_etat()
assert e["faites"] == 3 and not e["erreurs"], e
assert [d["debut_utc"][:13] for d in pub] == [(debut + timedelta(hours=24 * i)).strftime("%Y-%m-%dT%H") for i in range(3)], [d["debut_utc"] for d in pub]
assert all(d["politique_exp"] == "111" and d["poids_g"] == 250 and d["promotion"] == 2 and d["description"] for d in pub)
assert pub[0]["prix"] == 1500 and "Gretzky" in pub[0]["titre"]
inv = {c["id"]: c for c in a.inventaire_liste({})}
assert all(inv[i]["statut"] == "Listée" and inv[i]["debut"].startswith(pub[k]["debut_utc"][:16]) for k, i in enumerate(ids))
assert a.reglages_lire()["modele_annonce"]["promotion"] == 2                         # le modele est garde pour la prochaine fois
# trop loin : 30 cartes a 1 par jour depassent les 21 jours d'eBay
r2 = a.serie_programmer(list(range(1, 31)), debut.isoformat(), 24)
assert not r2["ok"] and "cartes au plus" in r2["erreur"], r2
# la promotion attend la mise en ligne : rien avant, puis appliquee
assert a.promos_attente_appliquer() == 0
c = a._db(); c.execute("UPDATE promos_attente SET debut='2000-01-01T00:00:00.000Z'"); c.commit(); c.close()
assert a.promos_attente_appliquer() == 3
# modifier une annonce programmee
rv = []
a._ecrire_ebay = lambda fn, *args, **kw: (rv.append((fn, args)) or {"ok": True})
r3 = a.annonce_reviser(ids[0], {"titre": "1985-86 O-Pee-Chee Wayne Gretzky PSA 8 MINT", "prix": 1450,
                                "debut": (debut + timedelta(hours=5)).isoformat()})
assert r3["ok"] and rv[0][0] == "annonces.reviser" and rv[0][1][2] == 1450, rv
assert a.carte_lire(ids[0])["prix_demande"] == 1450
print("PROGRAMMER OK")
