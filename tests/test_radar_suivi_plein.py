"""24 nov 2026 (Mathieu : « il nous faut beaucoup de cartes a proposer. Chaque personne collectionne des equipes et des joueurs
differents, donc notre Radar doit s'adapter aux demandes de chacun et leur offrir le meilleur »).

Mesure sur nos ventes des 90 derniers jours (30 $ et plus, ni base ni lot) : sur 522 joueurs qui se vendent, 343 n'ont aucune
carte B+ ou mieux. Celui qui suivait un de ces joueurs ne voyait RIEN de lui dans son Radar. Ici, le Radar complet (le serveur,
de la recherche eBay a la reponse) : la rangee d'un joueur suivi montre ses meilleures cartes ; son propre choix de note tient."""
import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom
import ebay_compte
from lockerroom import Api
assert Api.RADAR_FILTRE                                   # le filtre de qualite est EN PLACE (ce test juge la regle, pas le tri)
api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "m.db"))
J = "Luke Evangelista"
L = [{"item_id": str(i), "titre": f"2023-24 Upper Deck Premier {J} Rookie Auto Patch /{100 + i}", "prix_cad": 40 + i, "port_cad": 0, "url": "u%d" % i,
      "encan": i % 2 == 0} for i in range(30)]
L += [{"item_id": "90", "titre": f"2023-24 Upper Deck Series 1 {J} #112 base", "prix_cad": 45, "port_cad": 0, "url": "u90"},     # une base
      {"item_id": "91", "titre": f"2023-24 Upper Deck Premier {J} Rookie Auto Patch /999", "prix_cad": 12, "port_cad": 0, "url": "u91"}]   # 12 $
ebay_compte.rechercher = lambda q, **k: [dict(x) for x in L] if "evangelista" in str(q).lower() else []
# ses notes telles qu'en ligne (joueur note 53 : ses belles cartes sont des C, 64) ; le dossier de test, lui, ne connait pas le joueur
import score_slab


def _notes(l):
    for x in l or []:
        base = " base" in (x.get("titre") or "")
        x["score"], x["sorte"], x["joueur"] = (30, "D", J) if base else (64, "A", J)


score_slab.annoter_lot = _notes
assert api.deals_profil_regler({"favoris": [J], "collectionne": [], "prix_min": None, "prix_max": None, "iq_min": None})["ok"]
r = api.mes_deals(True)
assert r["ok"], r
g = next(x for x in r["pour_toi"] if x["joueur"] == J)
A = g["annonces"]
regle = [x for x in A if not x.get("elargi")]
assert 1 <= len(A) <= 60 and len(A) >= min(Api.RADAR_RANGEE_MIN, 30) or len(regle) >= Api.RADAR_RANGEE_MIN, (len(A), len(regle))
assert all((x.get("score") or 0) >= Api.RADAR_RANGEE_PLANCHER and x.get("sorte") != "D" and x["total"] >= Api.RADAR_PRIX_MIN for x in A)
assert not {"90", "91"} & {x["item_id"] for x in A}                                   # jamais la base, jamais la carte a 12 $
el = [x for x in A if x.get("elargi")]
assert [x["score"] for x in el] == sorted((x["score"] for x in el), reverse=True)     # les meilleures d'abord
n_regle = len(regle)
# s'il choisit LUI-MEME « A- et + » dans les Filtres : son choix tient, rien n'est ajoute
assert api.deals_profil_regler({"favoris": [J], "collectionne": [], "prix_min": None, "prix_max": None, "iq_min": 80})["ok"]
r2 = api.mes_deals(True)
g2 = next(x for x in r2["pour_toi"] if x["joueur"] == J)
assert not any(x.get("elargi") for x in g2["annonces"]) and all((x.get("score") or 0) >= 80 for x in g2["annonces"])
# 24 nov 2026 (Mathieu, juste apres le push : « presque pas de cartes dans le Radar Pro ») : une annonce deja en vitrine, sans son
# signal « pas une carte neuve » (entree avant la regle), ne reste plus cachee jusqu'au balayage suivant : le Radar la complete
# lui-meme avant de lire « A la une »
import time
from datetime import date, timedelta
import base_ventes
import liquidite
import vitrine
MCD = "2015-16 Upper Deck Young Guns Connor McDavid #201 PSA 10"
c = base_ventes._cx()
lignes = [("q1", "m%d" % i, MCD, 2400, (date.today() - timedelta(days=3 + 6 * i)).isoformat(), None, None, 0, (date.today() - timedelta(days=3 + 6 * i)).isoformat())
          for i in range(13)]                                             # 13 ventes de 3 a 75 jours : liquide, et pas neuve
c.executemany("INSERT INTO ventes VALUES (?,?,?,?,?,?,?,?,?)", lignes)
c.commit(); c.close()
liquidite.signaux([MCD]); time.sleep(0.5)
while liquidite._ETAT["en_cours"]:
    time.sleep(0.05)
liquidite.rafraichir(pause=0)
with vitrine._VERROU:                                                     # telle qu'elle etait gardee AVANT la regle : sans « _vieux »
    vitrine._pool()["777"] = {"item_id": "777", "titre": MCD, "total": 2300.0, "prix_cad": 2300, "port_cad": 0, "vu": time.time(), "score": 95,
                             "sorte": "A+", "joueur": "Connor McDavid", "_liq": 10, "_med": 2400.0}
assert vitrine.liste() == []                                              # la vitrine seule la cache encore (signal inconnu)
score_slab.annoter_lot = lambda l: None
assert api.deals_profil_regler({"favoris": [], "collectionne": [], "prix_min": None, "prix_max": None, "iq_min": None})["ok"]
r3 = api.mes_deals(True)
assert "777" in {x["item_id"] for x in r3["a_la_une"]}, [x["item_id"] for x in r3["a_la_une"]]
print("OK test_radar_suivi_plein (%d tuiles : %d par la regle, %d ajoutees ; notes %s a %s)" % (len(A), n_regle, len(el),
      round(min(x["score"] for x in A)), round(max(x["score"] for x in A))))
