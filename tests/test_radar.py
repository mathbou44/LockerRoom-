"""10 nov 2026 (Mathieu : « on devrait voir des cartes ; un petit questionnaire pour qu'il ait ses deals direct ») :
le Radar montre les annonces de SES joueurs dans SON budget (questionnaire), et « A decouvrir » si rien n'est regle."""
import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom
import ebay_compte
import demande_legale

api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "r.db"))
appels = []


def rech(q, **k):
    appels.append((q, k))
    if "Celebrini" in q:
        return [{"item_id": "c1", "titre": "2024-25 Upper Deck Young Guns Macklin Celebrini #201", "prix_cad": 90, "port_cad": 5, "url": "u"},
                {"item_id": "c2", "titre": "Macklin Celebrini lot of 20 base cards", "prix_cad": 20, "port_cad": 0, "url": "u"},
                {"item_id": "c3", "titre": "2024-25 Upper Deck Young Guns Macklin Celebrini #201", "prix_cad": 400, "port_cad": 0, "url": "u"},
                {"item_id": "c4", "titre": "2024-25 Upper Deck Young Guns Ivan Demidov", "prix_cad": 30, "port_cad": 0, "url": "u"}]
    return []


ebay_compte.rechercher = rech

# 1. rien de regle : « A decouvrir » (les joueurs les plus demandes, donnees publiques), budget 100 $ par defaut
demande_legale.populaires = lambda n=12, recrues=False: [{"nom": "Macklin Celebrini", "equipe": "SJS", "recrue": True, "hausse": True}]
r = api.mes_deals()
assert r["ok"] and r["profil_vide"] and not r["pour_toi"], r
assert [x["item_id"] for g in r["decouvrir"] for x in g["annonces"]] == ["c1"], r["decouvrir"]      # pas de lot, pas un autre joueur, <= 100 $
assert any(k.get("prix_max") == 100 for _q, k in appels)
print("OK radar a decouvrir")

# 2. le questionnaire : ses joueurs, ce qu'il collectionne, son budget -> une case par joueur, tout de suite
p = api.deals_profil_regler({"favoris": ["Macklin Celebrini", "Connor Bedard"], "collectionne": ["recrues", "hits"], "prix_max": 500})
assert p["ok"], p
appels.clear()
r = api.mes_deals()
assert not r["profil_vide"] and not r["decouvrir"]
pt = {g["joueur"]: [x["item_id"] for x in g["annonces"]] for g in r["pour_toi"]}
assert pt == {"Macklin Celebrini": ["c1", "c3"], "Connor Bedard": []}, pt
q0 = [q for q, _k in appels if "Celebrini" in q][0]
assert "young guns" in q0 and "auto" in q0 and q0.startswith("Macklin Celebrini ("), q0
print("OK radar mes joueurs")

# 3. l'accueil (sans prix cible) montre ces annonces « pour toi » sur les slabs
lockerroom.ebay_prix_actif = lambda api=None: False
api._MES_DEALS.clear()
a = api.acheteur_accueil()
assert [d["item_id"] for d in a["deals"]][:2] == ["c1", "c3"] and all(d.get("pourtoi") for d in a["deals"]), a["deals"]
print("OK accueil pour toi")

# 4. les pastilles du questionnaire
s = api.radar_suggestions()
assert s["ok"] and s["joueurs"][0]["nom"] == "Macklin Celebrini"
print("OK radar suggestions")

# 5. « Comparer » : la meme carte en Achat immediat, la moins chere d'abord ; jamais une moyenne ni un prix suggere
def rech2(q, **k):
    if k.get("encheres"):
        return []
    return [{"item_id": "b2", "titre": "2024-25 Upper Deck Young Guns Macklin Celebrini #201", "prix_cad": 80, "port_cad": 5, "url": "u2"},
            {"item_id": "b1", "titre": "2024-25 Upper Deck Young Guns Macklin Celebrini #201 RC", "prix_cad": 60, "port_cad": 3, "url": "u1"},
            {"item_id": "b3", "titre": "2024-25 Upper Deck Young Guns Macklin Celebrini Canvas #C1", "prix_cad": 20, "port_cad": 0, "url": "u3"},
            {"item_id": "9001", "titre": "2024-25 Upper Deck Young Guns Macklin Celebrini #201", "prix_cad": 30, "port_cad": 0, "url": "u4"}]


ebay_compte.rechercher = rech2
c = api.comparer("9001", "2024-25 Upper Deck Young Guns Macklin Celebrini #201")
assert c["ok"] and [x["item_id"] for x in c["annonces"]] == ["b1", "b2"], c        # sans Canvas, sans l'encan lui-meme, du moins cher
assert set(c) == {"ok", "annonces", "n"}
lot = api.comparer_lot([{"item_id": "9001", "titre": "2024-25 Upper Deck Young Guns Macklin Celebrini #201"}])
assert lot["items"]["9001"]["des"] == 63 and lot["items"]["9001"]["n"] == 2, lot
print("OK radar comparer")

# 6. une recherche qui plante (n'importe quelle erreur) ne fait plus tomber le Radar : sa case reste vide
def rech_panne(q, **k):
    if "Celebrini" in q:
        raise ValueError("JSON illisible")
    return rech(q, **k)


ebay_compte.rechercher = rech_panne
r = api.mes_deals()
assert r["ok"] and r["partiel"], r
assert {g["joueur"]: len(g["annonces"]) for g in r["pour_toi"]}["Macklin Celebrini"] == 0
print("OK radar robuste")

# 7. le Radar « large » : toutes les autos, toutes les numerotees... sans joueur choisi ; le titre doit le dire
vus_k = []


def rech_large(q, **k):
    vus_k.append(k)
    if k.get("encheres"):
        return []
    return [{"item_id": "a1", "titre": "2024-25 SP Authentic Future Watch Auto Ivan Demidov", "prix_cad": 60, "port_cad": 2, "url": "u"},
            {"item_id": "a2", "titre": "2024-25 Upper Deck Series 1 Ivan Demidov base", "prix_cad": 5, "port_cad": 2, "url": "u"},          # pas une auto
            {"item_id": "a3", "titre": "2024-25 Upper Deck Exclusives Ivan Demidov 12/100", "prix_cad": 30, "port_cad": 2, "url": "u"},
            {"item_id": "a4", "titre": "Lot of 10 autos hockey", "prix_cad": 40, "port_cad": 2, "url": "u"}]


ebay_compte.rechercher = rech_large
api.deals_profil_regler({"favoris": [], "collectionne": ["autos", "numerotees"], "prix_max": 200})
r = api.mes_deals()
T = {g["type"]: [x["item_id"] for x in g["annonces"]] for g in r["types"]}
assert T == {"autos": ["a1"], "numerotees": ["a3"]}, T
assert not r["decouvrir"] and not r["profil_vide"]
assert all(k.get("aspects") == "Sport:{Ice Hockey}" for k in vus_k), vus_k
print("OK radar large")

# 8. le Score SlabCoach sur chaque annonce du Radar (joueur + carte, jamais le prix)
import score_slab
s1 = score_slab.score("Upper Deck 2025-26 Premier Matvei Gridin Focus Rookies Patch Auto 85/99")
s2 = score_slab.score("2023-24 Upper Deck Series 1 Brock Nelson base #12")
assert s1["carte"]["auto"] and s1["carte"]["patch"] and s1["carte"]["tirage"] == 99 and s1["score"] > s2["score"], (s1, s2)
sx = score_slab.score("x", None)["score"]                # 12 nov 2026 : un titre sans indice n'a plus de score invente
assert sx is None or sx >= 0
r = api.mes_deals()
assert all(isinstance(x.get("score"), int) for g in r["types"] for x in g["annonces"]), r["types"]
assert api.annonce_score("2024-25 SP Authentic Future Watch Auto Ivan Demidov /999")["ok"]
print("OK score slabcoach")

# 9. 11 nov 2026 : l'ADMIN voit les ventes reelles de la meme carte sur le Radar ; les autres comptes : jamais
import vendues
vendues.memes_cache = lambda t, q=None, n=16, age_max=0: {"ventes": [{"prix": 100}] * 6, "mediane": 100.0, "nb": 6,
                                                          "points": [["2026-11-10", 110], ["2026-11-09", 104], ["2026-10-10", 90], ["2026-10-08", 92]]}
lockerroom.ebay_prix_actif = lambda api=None: True
r = api.mes_deals()
av = [x.get("admin_vendu") for g in r["types"] for x in g["annonces"]]
assert av and all(a and a["med"] == 100.0 and a["nb"] == 6 and a["achat_max"] > 0 for a in av), av
assert av[0]["tend_pct"] is not None and av[0]["tend_pct"] > 0, av
api._est_admin = lambda *a, **k: False                     # un compte Pro ou gratuit
r = api.mes_deals()
assert not any("admin_vendu" in x for g in r["types"] + r["pour_toi"] + r["creux"] for x in g["annonces"]), "fuite des ventes vers un non-admin"
print("OK radar admin vendu (et rien pour les autres)")

# 10. 11 nov 2026 (Mathieu : « capter tous les deals et encheres de petits vendeurs ») : la rangee « Petits vendeurs »
from datetime import datetime as _dt, timedelta as _td, timezone as _tz
fin_ = (_dt.now(_tz.utc) + _td(hours=3)).isoformat()
def rech_pv(q, **k):
    if not k.get("encheres"):
        return []
    return [{"item_id": "p1", "titre": "2024-25 Upper Deck Young Guns Lane Hutson", "prix_cad": 20, "port_cad": 3, "url": "u", "encan": True, "fin": fin_,
             "vendeur": "petitgars", "vendeur_score": 42, "vendeur_pct": 100},
            {"item_id": "p2", "titre": "2024-25 Upper Deck Young Guns Lane Hutson", "prix_cad": 20, "port_cad": 3, "url": "u", "encan": True, "fin": fin_,
             "vendeur": "grosvendeur", "vendeur_score": 90000, "vendeur_pct": 100},
            {"item_id": "p3", "titre": "2024-25 Upper Deck Young Guns Lane Hutson", "prix_cad": 20, "port_cad": 3, "url": "u", "encan": True, "fin": fin_,
             "vendeur": "nouveau", "vendeur_score": 3, "vendeur_pct": 100}]
ebay_compte.rechercher = rech_pv
api._est_admin = lambda *a, **k: False
r = api.mes_deals()
assert [x["item_id"] for x in r["petits"]] == ["p1"], r["petits"]          # pas le gros vendeur, pas le vendeur a risque
assert r["petits"][0]["petit_vendeur"] and r["petits"][0]["vendeur_score"] == 42
print("OK radar petits vendeurs")
