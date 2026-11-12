"""12 nov 2026 (Mathieu : « bonjour, voici les nouvelles que tu as manquees depuis ta derniere visite ») : la visite (6 h),
l'historique de l'Indice, l'echange d'equipe, l'evenement, la valeur de la collection, les ventes."""
import os, sys, tempfile, json
from datetime import datetime, timedelta, date
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom, quoi_de_neuf as qn, indice_joueurs

# la visite : 1re fois rien ; 2 h plus tard rien ; 10 h plus tard une nouvelle visite depuis la derniere ouverture
t0 = datetime(2026, 11, 13, 8, 0)
d, nv, w = qn.rouler_visite({}, t0)
assert d is None and not nv and w == {"visite_le": t0.isoformat(timespec="seconds")}
d, nv, w = qn.rouler_visite({"visite_le": "2026-11-13T08:00:00"}, t0 + timedelta(hours=2))
assert not nv and d is None
d, nv, w = qn.rouler_visite({"visite_le": "2026-11-13T10:00:00", "visite_prec": "2026-11-12T19:00:00"}, t0 + timedelta(hours=14))
assert nv and d == "2026-11-13T10:00:00" and w["visite_prec"] == d
d, nv, w = qn.rouler_visite({"visite_le": "2026-11-13T23:00:00", "visite_prec": "2026-11-13T10:00:00"}, datetime(2026, 11, 13, 23, 30))
assert not nv and d == "2026-11-13T10:00:00"          # meme visite : on peut revoir le meme resume
print("VISITE OK")

# l'historique : hier aux Leafs (indice 70), aujourd'hui a Columbus ; Price au Temple ; Celebrini en feu
hier = (date.today() - timedelta(days=2))
qn.hist_noter({"Matthew Knies": {"indice": 70, "equipe": "TOR"}, "Carey Price": {"indice": 60, "equipe": None},
               "Macklin Celebrini": {"indice": 80, "equipe": "SJS"}, "Joe Calme": {"indice": 50, "equipe": "UTA"}}, hier)
I = {"Matthew Knies": {"indice": 61, "equipe": "CBJ", "pastilles": []},
     "Carey Price": {"indice": 75, "equipe": None, "pastilles": ["honneur"],
                     "evenements": [{"type": "temple", "sens": 1, "titre": "Carey Price inducted into the Hall of Fame", "date": date.today().isoformat()}]},
     "Macklin Celebrini": {"indice": 84, "equipe": "SJS", "pastilles": ["en_feu"], "semaine": {"pts": 9, "mj": 4}},
     "Joe Calme": {"indice": 51, "equipe": "UTA", "pastilles": []}}
mq = {"TOR": 95, "CBJ": 40, "SJS": 60, "UTA": 20}.get
depuis = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
l = qn.joueurs([("Matthew Knies", 3), ("Carey Price", 1), ("Macklin Celebrini", 2), ("Joe Calme", 5)], depuis, I=I, marche=mq)
assert [x["joueur"] for x in l][:3] == ["Matthew Knies", "Carey Price", "Macklin Celebrini"], l
assert "Joe Calme" not in [x["joueur"] for x in l]
k = l[0]; assert k["sorte"] == "echange" and k["de"] == "TOR" and k["vers"] == "CBJ" and k["marche"] == "moins" and k["ecart"] == -9
t, dd, ton = qn.phrase(k)
assert "TOR → CBJ" in t and "plus petit marché" in dd, (t, dd)
t, dd, ton = qn.phrase(l[1]); assert "Temple" in t and ton == "or"
t, dd, ton = qn.phrase(l[2]); assert "en feu" in t and "9 points en 4 matchs" in dd
assert "Hall of Fame" in qn.phrase(l[1], en=True)[0]
print("JOUEURS OK", [qn.phrase(x)[0] for x in l])

# la valeur : une photo par jour, 60 jours ; la valeur d'avant = le dernier jour <= la visite
h = {}
for i in range(70):
    h = qn.valeur_noter(h, 100 + i, 3, date(2026, 9, 1) + timedelta(days=i))
assert len(h) == 60 and qn.valeur_avant(h, "2026-11-01T10:00:00") == [161, 3] and qn.valeur_avant(h, "2020-01-01") is None

# l'Api de bout en bout : 1re ouverture (rien), puis 8 h plus tard avec un joueur echange et une vente
a = lockerroom.Api()
indice_joueurs._ecrire({"joueurs": {}, "indice": I, "le": 0})
assert a.quoi_de_neuf() == {"ok": True, "montrer": False}
r0 = a.reglages_lire(); assert r0["visite_le"] and list(r0["valeur_hist"].values())[0] == [0, 0]
avant = (datetime.now() - timedelta(hours=9)).isoformat(timespec="seconds")
c = a._db()
c.execute("INSERT INTO cartes (titre, joueur, valeur, statut, cree_le) VALUES (?,?,?,?,?)", ("Knies YG", "Matthew Knies", 120, "En stock", avant))
c.execute("INSERT INTO cartes (titre, joueur, prix_vendu, statut, cree_le, vendu_le) VALUES (?,?,?,?,?,?)",
          ("Price auto", "Carey Price", 80, "Vendue", avant, datetime.now().isoformat(timespec="seconds")))
c.commit(); c.close()
a.reglages_sauver({"visite_le": avant})
import demande_legale
demande_legale.marche_equipe = mq
r = a.quoi_de_neuf()
assert r["montrer"] and r["ventes"] == {"n": 1, "total": 80.0} and r["valeur"]["maintenant"] == 120 and r["valeur"]["ecart"] is None and r["valeur"]["ajoutees"] == 1, r
assert r["joueurs"][0]["joueur"] == "Matthew Knies" and r["joueurs"][0]["sorte"] == "echange", r["joueurs"]
assert a.quoi_de_neuf()["montrer"] is False                     # meme visite : pas deux fois
assert a.quoi_de_neuf(True)["joueurs"][0]["joueur"] == "Matthew Knies"     # mais on peut le revoir
print("API OK", json.dumps(r, ensure_ascii=False)[:300])
