"""14 nov 2026 (Mathieu : « Matthew Knies, un bon joueur des Leafs, echange en debut de saison a Columbus : la valeur de ses
cartes a drastiquement diminue ; SlabIQ aurait du le capter ») : le changement d'equipe recent, son sens (quitter ou rejoindre
Toronto/Montreal), l'indice, le score de la carte et la valeur (ventes d'avant ramenees)."""
import json
import time
import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
comptes.DOSSIER_COMPTES = os.path.join(comptes.DONNEES, "comptes")
from datetime import date, timedelta
import indice_joueurs as ij

AUJ = date(2026, 11, 14)

# 1. les noms d'equipes et le sens
assert ij.abrev_equipe("Toronto Maple Leafs") == "TOR" and ij.abrev_equipe("Montréal Canadiens") == "MTL"
assert ij.abrev_equipe("St. Louis Blues") == "STL" and ij.abrev_equipe("cbj") == "CBJ" and ij.abrev_equipe("Inconnus FC") is None
assert ij.sens_echange("TOR", "CBJ") == "baisse" and ij.sens_echange("CBJ", "TOR") == "hausse"
assert ij.sens_echange("ANA", "STL") == "neutre" and ij.sens_echange("TOR", "MTL") == "neutre"

# 2. la detection : par ses saisons LNH (changement d'ete, pendant la saison), et par l'equipe vue la veille
knies = {"actif": True, "equipe": "CBJ", "equipes": [[20232024, "Toronto Maple Leafs", 80], [20252026, "Toronto Maple Leafs", 78],
                                                      [20262027, "Columbus Blue Jackets", 15]]}
x = ij.detecter_echange(knies, None, AUJ)
assert x == {"de": "TOR", "vers": "CBJ", "le": "2026-10-01", "source": "saisons"}, x
# pas encore joue avec Columbus : la meme chose
x = ij.detecter_echange({**knies, "equipes": knies["equipes"][:2]}, None, AUJ)
assert x and x["de"] == "TOR" and x["le"] == "2026-10-01", x
# un changement d'ete vu en aout : la date du jour (pas octobre, dans le futur)
assert ij.detecter_echange({**knies, "equipes": knies["equipes"][:2]}, None, date(2026, 8, 10))["le"] == "2026-08-10"
# echange pendant CETTE saison (date inconnue) : aujourd'hui, par prudence
x = ij.detecter_echange({"equipe": "CBJ", "equipes": [[20252026, "Toronto Maple Leafs", 80], [20262027, "Toronto Maple Leafs", 9],
                                                      [20262027, "Columbus Blue Jackets", 6]]}, None, AUJ)
assert x and x["le"] == AUJ.isoformat(), x
# echange pendant la saison DERNIERE : trop vieux
assert ij.detecter_echange({"equipe": "CBJ", "equipes": [[20252026, "Toronto Maple Leafs", 40], [20252026, "Columbus Blue Jackets", 30],
                                                         [20262027, "Columbus Blue Jackets", 15]]}, None, AUJ) is None
# toujours la meme equipe : rien ; une vieille equipe (il y a 3 ans) : rien
assert ij.detecter_echange({"equipe": "TOR", "equipes": [[20252026, "Toronto Maple Leafs", 80], [20262027, "Toronto Maple Leafs", 15]]}, None, AUJ) is None
assert ij.detecter_echange({"equipe": "CBJ", "equipes": [[20222023, "Toronto Maple Leafs", 80], [20252026, "Columbus Blue Jackets", 80]]}, None, AUJ) is None
# l'equipe vue la derniere fois : un changement du jour, date exacte
x = ij.detecter_echange({"equipe": "TOR", "equipes": []}, {"eq": "CBJ", "le": "2026-11-13"}, AUJ)
assert x == {"de": "CBJ", "vers": "TOR", "le": AUJ.isoformat(), "source": "vu"}, x
print("OK detection")

# 3. le suivi : garde les changements, oublie les vieux (150 jours)
d = {"joueurs": {}}
base = {"Matthew Knies": {"nhl": knies}, "Kirill Marchenko": {"nhl": {"actif": True, "equipe": "TOR", "equipes": [
            [20252026, "Columbus Blue Jackets", 80], [20262027, "Toronto Maple Leafs", 15]]}},
        "Reste Ici": {"nhl": {"actif": True, "equipe": "BOS", "equipes": [[20252026, "Boston Bruins", 80], [20262027, "Boston Bruins", 15]]}}}
E = ij.suivre_echanges(d, base, AUJ)
assert set(E) == {"Matthew Knies", "Kirill Marchenko"} and d["equipes_vues"]["Reste Ici"]["eq"] == "BOS", E
assert ij.suivre_echanges(d, base, AUJ + timedelta(days=200)) == {}, "un changement de plus de 150 jours est oublie"
print("OK suivi")

# 4. l'indice : quitter Toronto = -8 et « echange_baisse » ; rejoindre Toronto = +8 ; le reste : « echange » seulement
base = {"Matthew Knies": {"nhl": {**knies, "saisons": 3, "l5": 2}, "wiki": {"v60": 3000, "v20": 1000}},
        "Kirill Marchenko": {"nhl": {**base["Kirill Marchenko"]["nhl"], "saisons": 4, "l5": 2}, "wiki": {"v60": 3000, "v20": 1000}},
        "Mason McTavish": {"nhl": {"actif": True, "equipe": "STL", "saisons": 4, "l5": 2, "equipes": [[20252026, "Anaheim Ducks", 80],
                                   [20262027, "St. Louis Blues", 15]]}, "wiki": {"v60": 3000, "v20": 1000}}}
for i in range(20):
    base[f"Joueur {chr(65 + i)}"] = {"nhl": {"actif": True, "equipe": "BOS", "saisons": 4, "l5": i % 4}, "wiki": {"v60": 500 + i * 10, "v20": 160}}
sans = ij.calculer({"joueurs": {}}, {n: {**e, "nhl": {**e["nhl"], "equipes": []}} for n, e in base.items()}, lambda n: 1)
d = {"joueurs": {}}
I = ij.calculer(d, base, lambda n: 1)
k, m, t = I["Matthew Knies"], I["Kirill Marchenko"], I["Mason McTavish"]
assert "echange_baisse" in k["pastilles"] and k["echange"]["de_nom"] == "Toronto" and k["echange"]["vers_nom"] == "Columbus", k
assert "echange_hausse" in m["pastilles"] and "echange" in t["pastilles"], (m["pastilles"], t["pastilles"])
assert k["indice"] < sans["Matthew Knies"]["indice"] and m["indice"] > sans["Kirill Marchenko"]["indice"]
assert t["indice"] == sans["Mason McTavish"]["indice"]
assert set(d["echanges"]) == {"Matthew Knies", "Kirill Marchenko", "Mason McTavish"}
# une nouvelle « traded » n'est plus une bonne nouvelle d'office
assert ij.classer_evenement("Maple Leafs trade Matthew Knies to Columbus")[0] is None
print("OK indice", k["indice"], sans["Matthew Knies"]["indice"])

# 5. l'Indice est ecrit : le titre d'une annonce retrouve l'echange de son joueur
ij._ecrire({"joueurs": {}, "indice": I, "le": 0, "echanges": d["echanges"]})
x = ij.echange_titre("2023-24 SP Authentic Matthew Knies Future Watch Auto RC 14/99")
assert x and x["sens"] == "baisse" and x["joueur"] == "Matthew Knies", x
assert ij.echange_titre("2023-24 SP Authentic Easton Cowan Future Watch Auto") is None

# 6. la valeur : 2 ventes depuis l'echange -> seulement elles ; sinon les ventes d'avant a 70 % (Toronto -> Columbus)
import deals
T = "2023-24 SP Authentic Matthew Knies Future Watch Auto RC /99"
j = lambda n: (date.today() - timedelta(days=n)).isoformat()
le = d["echanges"]["Matthew Knies"]["le"]
assert le == "2026-10-01" or le <= date.today().isoformat()
d["echanges"]["Matthew Knies"]["le"] = j(30)                  # l'echange : il y a 30 jours (le test ne depend pas de la date)
ij._ecrire({"joueurs": {}, "indice": I, "le": 0, "echanges": d["echanges"]})
avant = [{"titre": T + " 1/99", "prix": 260.0, "le": j(50), "url": "a"}, {"titre": T + " 2/99", "prix": 250.0, "le": j(45), "url": "b"},
         {"titre": T + " 3/99", "prix": 255.0, "le": j(40), "url": "c"}]
apres = [{"titre": T + " 4/99", "prix": 130.0, "le": j(10), "url": "d"}, {"titre": T + " 5/99", "prix": 125.0, "le": j(5), "url": "e"}]
v, pv = deals.valeur_sure(avant + apres, T)
assert v is not None and v <= 130 and all(not x.get("_ech") for x in pv), (v, pv)
v, pv = deals.valeur_sure(avant + apres[:1], T)                       # 1 seule vente depuis : celles d'avant a 70 %
assert v is not None and v <= 0.7 * 260 + 1 and any(x.get("_ech") == 0.7 for x in pv), (v, pv)
v0, _ = deals._valeur_sure0(avant + apres[:1], T)
assert v < v0
# la valeur d'une annonce le dit (« echange ») et montre les VRAIS prix vendus
r = deals.valeur_annonce({"titre": T, "item_id": "x"}, avant + apres[:1], [])
if r:
    assert r[1] == "echange" and {x["prix"] for x in r[3]} <= {260.0, 250.0, 255.0, 130.0}, r
# un autre joueur : rien ne change
T2 = "2023-24 SP Authentic Joueur A Future Watch Auto RC /99"
assert deals.valeur_sure([dict(x, titre=x["titre"].replace("Matthew Knies", "Joueur A")) for x in avant], T2) == \
    deals._valeur_sure0([dict(x, titre=x["titre"].replace("Matthew Knies", "Joueur A")) for x in avant], T2)
print("OK valeur", v, v0)

# 7. le score de la carte : -12 en quittant Toronto, +8 en y arrivant
import score_slab
assert score_slab.ajuster_echange(80, {"pastilles": ["echange_baisse"]}) == 68
assert score_slab.ajuster_echange(80, {"pastilles": ["echange_hausse"]}) == 88
assert score_slab.ajuster_echange(80, {"pastilles": ["echange"]}) == 80 and score_slab.ajuster_echange(None, {"pastilles": []}) is None
print("OK score")

# 8. le badge SlabIQ du Radar (admin) : Knies « en baisse », la raison et les clubs
import lockerroom
q = lockerroom.Api._iq_un("Matthew Knies", I)
assert q["sens"] == "baisse" and q["pq"] == "echange_baisse" and q["ech"] == {"de": "Toronto", "vers": "Columbus"}, q
q = lockerroom.Api._iq_un("Kirill Marchenko", I)
assert q["sens"] == "hausse" and q["pq"] == "echange_hausse", q
print("ECHANGE OK")

# 9. 14 nov 2026 (« pourquoi Knies est encore a 87 ? ») : sa fiche LNH etait vieille (ou absente) ; les alignements des 32
# clubs (cette saison et la derniere) disent le vrai club et le changement, meme sans fiche
d = {"rosters": {"le": 9e12, "cour": {"matthew knies": "CBJ", "kirill marchenko": "TOR", "auston matthews": "TOR"},
                 "prec": {"matthew knies": ["TOR"], "kirill marchenko": ["CBJ"], "auston matthews": ["TOR"]}},
     "indice": {"Matthew Knies": {"indice": 40}, "Auston Matthews": {"indice": 90}}}
E = ij.suivre_echanges(d, {"Kirill Marchenko": {"nhl": {"actif": True, "equipe": "CBJ"}}}, AUJ)     # fiche vieille : CBJ
assert E["Matthew Knies"] == {"de": "TOR", "vers": "CBJ", "le": "2026-10-01", "source": "alignements"}, E
assert E["Kirill Marchenko"]["vers"] == "TOR" and "Auston Matthews" not in E, E
# echange PENDANT la saison derniere (dans les deux clubs l'an passe) : pas recent
d = {"rosters": {"le": 9e12, "cour": {"joe a": "CBJ"}, "prec": {"joe a": ["TOR", "CBJ"]}}, "indice": {"Joe A": {"indice": 50}}}
assert ij.suivre_echanges(d, {}, AUJ) == {}
v_ = {"le": time.time(), "cour": {"x": "TOR"}}; assert ij.rosters_lnh(v_) is v_          # pas relu avant 20 h
print("ALIGNEMENTS OK")
