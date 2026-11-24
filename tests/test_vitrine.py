"""19 nov 2026 : la vitrine du Radar Pro : ce que le chasseur balaie, seulement les cartes A- et mieux, 30 $ et plus.
20 nov 2026 : et liquides (5 ventes de la meme carte en 60 jours), pas plus de 10 % au-dessus de ce qu'elles se vendent ;
la mediane et le compte ne sortent jamais.
23 nov 2026 (Mathieu : « B : 78 % ») : 8 ventes en 60 jours, et jamais au-dessus de ce que la carte se vend."""
import os, sys, tempfile, time
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import vitrine
import base_ventes
import liquidite
from datetime import date
MCD = "2015-16 Upper Deck Young Guns Connor McDavid #201 PSA 10"
RPA = "2005-06 The Cup Sidney Crosby Rookie Patch Auto RPA /99"
c = base_ventes._cx()
lignes = []
for i in range(9):
    le = (date.today() - timedelta(days=3 + 6 * i)).isoformat()
    lignes.append(("q1", "m%d" % i, MCD, 2400 + 10 * i, le, None, None, 0, le))
    lignes.append(("q2", "r%d" % i, RPA, 9500, le, None, None, 0, le))
    lignes.append(("q3", "s%d" % i, MCD.replace("PSA 10", "SGC 10"), 900, le, None, None, 0, le))   # une autre compagnie
# 23 nov 2026 au soir : la McDavid et la Crosby se vendaient deja il y a 70 jours ; la SGC 10, elle, est une carte NEUVE chez nous
le70 = (date.today() - timedelta(days=70)).isoformat()
lignes.append(("q1", "m70", MCD, 2400, le70, None, None, 0, le70))
lignes.append(("q2", "r70", RPA, 9500, le70, None, None, 0, le70))
c.executemany("INSERT INTO ventes VALUES (?,?,?,?,?,?,?,?,?)", lignes)
c.commit(); c.close()
assert liquidite.signaux([MCD]) is None                  # l'index n'est pas encore bati : on attend (pas rejete)
time.sleep(0.5)
while liquidite._ETAT["en_cours"]:
    time.sleep(0.05)
liquidite.rafraichir(pause=0)
s_ = liquidite.signaux([MCD, RPA, MCD.replace("PSA 10", "SGC 10")])
assert s_[MCD][0] == 9 and 2400 <= s_[MCD][1] <= 2480, s_
assert s_[MCD.replace("PSA 10", "SGC 10")][1] == 900, s_
assert liquidite.passe(5, 2400, 2400, 1) and not liquidite.passe(5, 2400, 2410, 1) and not liquidite.passe(4, 2400, 1000, 1)   # 5 vraies ventes ; jamais au-dessus
# 23 nov 2026 au soir : pas une carte neuve (au moins une vente entre 60 et 90 jours avant) ; signal inconnu = refusee
assert not liquidite.passe(8, 2400, 2400, 0) and not liquidite.passe(8, 2400, 2400) and liquidite.VIEUX_MIN == 1
# 24 nov 2026 (Mathieu, une Rantanen Canvas PSA 10 partie a 63 $ : « j'espere qu'on l'avait captee » ; « on doit etre parfait avant
# Apple ») : 1) la meme vente trouvee par deux recherches (meme numero d'annonce, prix converti a 2 cents pres) compte UNE fois ;
# 2) la meme carte ecrite autrement (« 2015 » ou « 2015-16 », « #C98 » ou « C98 », « UD », « Series 1 », un tiret) a UNE cle ;
# 3) deux cartes differentes gardent deux cles
RAN = ["2015 UPPER DECK #C98 MIKKO RANTANEN UD CANVAS YOUNG GUNS RC ROOKIE PSA 10", "Upper Deck 2015-16 UD Canvas Young Guns Mikko Rantanen RC #C98 PSA 10",
       "2015-16 Upper Deck - Ud Canvas Young Guns Mikko Rantanen #C98 (RC) PSA 10", "2015-16 UD Series 1 UD Canvas Young Guns Mikko Rantanen #C98 RC PSA 10"]
assert len({liquidite.cle(t) for t in RAN}) == 1, {liquidite.cle(t) for t in RAN}
assert liquidite.cle(RAN[0]) != liquidite.cle(RAN[0].replace("PSA 10", "PSA 9")) != liquidite.cle(RAN[0].replace("PSA 10", ""))      # la note compte
assert liquidite.cle("2025 Upper Deck Extended Series 1st Round Rookies Outburst Ivan Demidov") != liquidite.cle("2025-26 Upper Deck Young Guns Outburst Ivan Demidov #205")
assert liquidite.cle("2025-26 SP Hockey Rookie Authentics Patch RC - Michael Misa #122") != liquidite.cle("2025-26 SP Game Used - #AR-MM Michael Misa Authentic Rookies Patch")
assert liquidite.cle("1985-86 O-Pee-Chee Mario Lemieux #9") != liquidite.cle("1985-86 Topps Mario Lemieux #9")                          # deux produits
assert liquidite.id_vente("https://www.ebay.com/itm/286123456789?nordt=true") == liquidite.id_vente("https://www.ebay.ca/itm/mikko-rantanen/286123456789") == "286123456789"
c = base_ventes._cx()
jr = lambda n: (date.today() - timedelta(days=n)).isoformat()
c.executemany("INSERT INTO ventes VALUES (?,?,?,?,?,?,?,?,?)", [
    ("rantanen canvas", "u1", RAN[0], 92.97, jr(30), None, "https://www.ebay.com/itm/286123456789", 0, jr(1)),
    ("rantanen young guns psa 10", "u1", RAN[0], 92.99, jr(30), None, "https://www.ebay.ca/itm/x/286123456789", 0, jr(1)),       # la MEME vente
    ("rantanen psa", "u1", RAN[0], 93.40, jr(29), None, "https://www.ebay.com/itm/286123456789?x=1", 0, jr(1)),                    # encore elle, un jour plus tard
    ("rantanen canvas", "u2", RAN[1], 114.38, jr(8), None, "https://www.ebay.com/itm/286999000111", 0, jr(1)),                    # une autre vente, ecrite autrement
    ("rantanen canvas", "u3", RAN[3], 70.0, jr(70), None, "https://www.ebay.com/itm/286999000222", 0, jr(1))])                    # il y a 70 jours
c.commit(); c.close()
liquidite.rafraichir(pause=0)
sr = liquidite.signaux([RAN[2]])[RAN[2]]                   # demandee sous une 3e facon d'ecrire
assert sr[0] == 2 and sr[2] == 1 and 92 <= sr[1] <= 115, sr      # 2 vraies ventes en 60 jours (pas 4), 1 il y a 2 mois
assert len(s_[MCD]) == 3 and s_[MCD][2] == 1 and s_[MCD.replace("PSA 10", "SGC 10")][2] == 0, s_   # une vente a 70 jours ; la SGC : aucune
assert liquidite.LIQ_MIN == 5 and liquidite.RABAIS_MAX == 0.0
fin = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
fini = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
A = [{"item_id": "1", "titre": "2015-16 Upper Deck Young Guns Connor McDavid #201 PSA 10", "prix_cad": 2300, "port_cad": 0, "encan": True, "fin": fin},
     {"item_id": "2", "titre": "2023-24 Upper Deck Series 1 Connor McDavid #1 base", "prix_cad": 40, "port_cad": 5},
     {"item_id": "3", "titre": "2023-24 SP Authentic Future Watch Auto Connor Bedard /999", "prix_cad": 12, "port_cad": 2},
     {"item_id": "4", "titre": "2005-06 The Cup Sidney Crosby Rookie Patch Auto RPA /99", "prix_cad": 9000, "port_cad": 0},
     {"item_id": "5", "titre": "2015-16 Upper Deck Young Guns Connor McDavid #201 PSA 10", "prix_cad": 2300, "encan": True, "fin": fini},
     {"item_id": "6", "titre": "2015-16 Upper Deck Young Guns Connor McDavid #201 PSA 10", "prix_cad": 3500, "port_cad": 0},   # trop cher
     {"item_id": "7", "titre": "2016-17 Upper Deck Young Guns Auston Matthews #201 PSA 10", "prix_cad": 900, "port_cad": 0},   # pas de ventes
     {"item_id": "8", "titre": MCD.replace("PSA 10", "SGC 10"), "prix_cad": 900, "port_cad": 0}]   # 9 ventes, bon prix, mais NEUVE (aucune vente il y a 2 mois)
n = vitrine.ajouter(A)
L = vitrine.liste()
ids = [x["item_id"] for x in L]
assert "2" not in ids and "3" not in ids, ids            # une base ; une carte a 14 $
assert "5" not in ids, ids                               # un encan fini
assert "6" not in ids and "7" not in ids, ids            # 45 % au-dessus de ce qu'elle se vend ; aucune vente archivee
assert "1" in ids and "4" in ids, ids
assert "8" not in ids, ids                               # 23 nov 2026 au soir : une carte neuve perd sa valeur : pas en vitrine
assert all(x["score"] >= 82 and x["a_la_une"] and "_med" not in x and "_liq" not in x and "_vieux" not in x for x in L)
# 24 nov 2026 (Mathieu, en vue Pro : « only 34 are showing » ; il choisit « deux rangees ») : les annonces dont la carte est A- ou
# mieux mais qui ne passent pas la regle prouvee ne sont plus oubliees : elles sortent dans « Tres recherchees », jamais dans
# « A la une » ; une base et une carte a 14 $ n'y entrent pas plus qu'avant ; aucun signal n'est montre
RR = vitrine.recherchees()
ids_r = [x["item_id"] for x in RR]
assert "6" in ids_r and "8" in ids_r, ids_r               # trop chere ; carte neuve : pas « A la une », mais recherchees
assert not {"1", "4"} & set(ids_r) and not {"2", "3", "5"} & set(ids_r), ids_r     # les prouvees n'y sont pas ; ni base, ni 14 $, ni encan fini
assert all(x["score"] >= 82 and not x.get("a_la_une") and "_med" not in x and "_liq" not in x and "_vieux" not in x for x in RR)
assert [x["score"] for x in RR] == sorted((x["score"] for x in RR), reverse=True)
e_ = vitrine.etat()
assert e_["cartes"] == 2 and e_["recherchees"] == len(RR) >= 2, e_
# deja vue : le prix se met a jour, sans la renoter
vitrine.ajouter([{"item_id": "1", "titre": A[0]["titre"], "prix_cad": 2400, "port_cad": 0, "encan": True, "fin": fin, "mises": 9}])
x1 = next(x for x in vitrine.liste() if x["item_id"] == "1")
assert x1["total"] == 2400 and x1["mises"] == 9
# l'encan monte au-dessus de la limite : il sort de la liste (et revient s'il redescend, ce qui n'arrive pas)
vitrine.ajouter([{"item_id": "1", "titre": A[0]["titre"], "prix_cad": 2900, "port_cad": 0, "encan": True, "fin": fin, "mises": 12}])
assert "1" not in [x["item_id"] for x in vitrine.liste()]
assert "1" in [x["item_id"] for x in vitrine.recherchees()]      # 24 nov 2026 : ... et passe dans « Tres recherchees » (toujours une A+)
vitrine.ajouter([{"item_id": "1", "titre": A[0]["titre"], "prix_cad": 2500, "port_cad": 0, "encan": True, "fin": fin, "mises": 10}])
assert "1" not in [x["item_id"] for x in vitrine.liste()]      # 23 nov 2026 : 2500 depasse ce qu'elle se vend (avant : permis jusqu'a +10 %)
vitrine.ajouter([{"item_id": "1", "titre": A[0]["titre"], "prix_cad": 2400, "port_cad": 0, "encan": True, "fin": fin, "mises": 9}])
# son budget
assert [x["item_id"] for x in vitrine.liste(prix_max=3000)] == ["1"] or "4" not in [x["item_id"] for x in vitrine.liste(prix_max=3000)]
vitrine._ecrire_si_besoin(forcer=True)
vitrine._ETAT["pool"] = None
assert {x["item_id"] for x in vitrine.liste()} == {"1", "4"}
# 23 nov 2026 au soir : une annonce entree en vitrine AVANT la regle n'a pas son signal : cachee, puis completee au balayage suivant
# (sans attendre qu'elle expire : une annonce a prix fixe revue a chaque balayage n'expire jamais)
with vitrine._VERROU:
    for x in vitrine._pool().values():
        if x is not None:
            x.pop("_vieux", None)
assert vitrine.liste() == []
vitrine.ajouter([])
assert {x["item_id"] for x in vitrine.liste()} == {"1", "4"}
# 24 nov 2026 : des signaux venus de l'ancien index (ventes comptees en double) sont relus dans le nouveau, sans rien cacher d'ici la
with vitrine._VERROU:
    x1_ = vitrine._pool()["1"]
    x1_["_liq"], x1_["_sv"] = 99, 1
vitrine.ajouter([])
with vitrine._VERROU:
    assert vitrine._pool()["1"]["_liq"] == 9 and vitrine._pool()["1"]["_sv"] == liquidite.VERSION, vitrine._pool()["1"]
# l'interrupteur de Render (LR_RADAR_ANCIENNETE=0) : la regle d'avant
os.environ["LR_RADAR_ANCIENNETE"] = "0"
assert liquidite.passe(8, 2400, 2400, 0) and liquidite.passe(8, 2400, 2400)
del os.environ["LR_RADAR_ANCIENNETE"]
# 24 nov 2026 : a la mise en ligne des deux rangees, la vitrine d'avant (vitrine_liq.json) est reprise : ses annonces restent
# « A la une » sans attendre un balayage ; ses refus (None) ne sont pas repris : ils seront rejuges
import json as _json
import comptes as _comptes
d2 = tempfile.mkdtemp()
with vitrine._VERROU:
    avant = {k: x for k, x in vitrine._pool().items()}
_json.dump({**{k: x for k, x in avant.items() if k in ("1", "4")}, "99": None}, open(os.path.join(d2, "vitrine_liq.json"), "w"))
d1, _comptes.DONNEES = _comptes.DONNEES, d2
vitrine._ETAT["pool"] = None
assert set(vitrine._pool()) == {"1", "4"}
_comptes.DONNEES = d1
vitrine._ETAT["pool"] = None
# le test publie sur le site mesure la MEME regle (le test suit l'app) : memes durees, meme fonction
ts = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outils", "tests_site.py"), encoding="utf-8").read()
assert "i60 - i90" in ts and 'liquidite.passe(liq, med_, a["p"], vieux)' in ts and "liquidite.MED_JOURS" in ts and "liquidite.LIQ_JOURS" in ts
print("OK test_vitrine", vitrine.etat())
