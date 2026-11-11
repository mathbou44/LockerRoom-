"""13 nov 2026 (Mathieu : « Price intronise au Temple, standing ovation au Centre Bell : ses cartes se vendent plus ; capter
TOUS les evenements ; les bons joueurs en baisse = occasions pour les acheteurs ; SlabIQ connait l'inventaire et dit de
verifier son annonce ; dans les notifs a activer »)."""
import os, sys, tempfile
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
comptes.MULTI = False
import indice_joueurs as I, alarmes, marche, lockerroom

# 1. les evenements classes (type, sens)
for t, ty in [("Carey Price inducted into Hockey Hall of Fame", "temple"), ("Standing ovation for Carey Price as plaque unveiled at Centre Bell", "honneur"),
              ("Canadiens to retire Price jersey", "honneur"), ("Bedard records first career hat trick", "exploit"),
              ("Suzuki out with upper-body injury", "blessure"), ("Prospect sent down to AHL", "negatif")]:
    assert I.classer_evenement(t)[0] == ty, (t, I.classer_evenement(t))
assert I.classer_evenement("Canadiens beat Leafs 4-2")[0] is None
# 2. par joueur : la bonne nouvelle d'hier compte fort, celle d'il y a 10 jours presque plus
auj = date.today().isoformat()
items = [{"titre": "Standing ovation for Carey Price as plaque unveiled at Centre Bell", "date": auj, "lien": "https://x"},
         {"titre": "Nick Suzuki out with upper-body injury", "date": auj},
         {"titre": "Carey Price inducted into Hall of Fame", "date": (date.today() - timedelta(days=12)).isoformat()}]
a = I._actu_par_joueur(["Carey Price", "Nick Suzuki"], items)
assert a["Carey Price"]["pos"] > 25 and a["Carey Price"]["neg"] == 0, a
assert a["Nick Suzuki"]["neg"] >= 14 and a["Nick Suzuki"]["evs"][0]["sens"] == -1, a
# 3. les pastilles : « honneur » et la hausse ; un bon joueur blesse = « occasion »
base = {"Carey Price": {"nhl": {"actif": False, "hhof": True, "trophees_n": 6}, "wiki": {"v60": 9000, "v20": 4000, "v3": 2500}},
        "Nick Suzuki": {"nhl": {"actif": True, "equipe": "MTL"}, "wiki": {"v60": 6000, "v20": 2000, "v3": 300}},
        "Joe Bloggs": {"nhl": {"actif": True, "equipe": "MTL"}, "wiki": {"v60": 300, "v20": 100, "v3": 15}}}
I.actu = lambda jours=7: items
out = I.calculer(d={"joueurs": {}}, base=base, demande=lambda n: {"Nick Suzuki": 90, "Carey Price": 80}.get(n, 5))
assert "honneur" in out["Carey Price"]["pastilles"] and out["Carey Price"]["ev_pos"] > 25, out["Carey Price"]
assert "mauvaise" in out["Nick Suzuki"]["pastilles"] and "occasion" in out["Nick Suzuki"]["pastilles"], out["Nick Suzuki"]
assert "occasion" not in (out.get("Joe Bloggs") or {}).get("pastilles", [])
# 4. les notifications SlabIQ : a activer (off par defaut), sur les joueurs de TES cartes ; la cloche les reconnait
api = lockerroom.Api(os.path.join(os.environ["LOCKERROOM_DONNEES"], "t.db"))
assert alarmes.reglages(api)["iq_nouvelle"] is False and alarmes.reglages(api)["iq_occasion"] is False
api.carte_sauver({"titre": "2005-06 Carey Price Young Guns", "joueur": "Carey Price", "statut": "En stock"})
I.lire = lambda: {"indice": out}
envoyes = []
alarmes._notifier = lambda api_, etat, cle, titre, texte, lien, **k: envoyes.append((cle, titre, texte, lien)) or True
assert not alarmes.verifier(api).get("iq_nouvelle")
alarmes.regler(api, {"iq_nouvelle": True, "iq_occasion": True})
f = alarmes.verifier(api)
assert f.get("iq_nouvelle") == 1 and f.get("iq_occasion") == 1, (f, envoyes)
n = [e for e in envoyes if e[0].startswith("iqn:")][0]
assert n[1] == "Bonne nouvelle pour Carey Price" and "vérifie le prix" in n[2] and n[3] == "#iqcartes/Carey Price", n
o = [e for e in envoyes if e[0].startswith("iqo:")][0]
assert "Nick Suzuki" in o[1], o
assert marche.decrire({"item_id": n[0], "titre": n[1], "texte": n[2]})["sorte"] == "iq_bonne"
assert marche.decrire({"item_id": o[0], "titre": o[1], "texte": o[2]})["sorte"] == "iq_occasion"
print("OK SlabIQ evenements")
