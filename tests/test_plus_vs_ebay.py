"""10 nov 2026 (Mathieu : « l'utilisateur doit avoir un bon plus sur notre app vs eBay » ; « fais tout ») :
le vrai total en $ CA, la chasse des cartes qui manquent, l'alerte « en feu » du Radar, le dernier rappel d'encan,
« pourquoi il bouge ». Aucun appel reseau."""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom
import ebay_compte
import deals

api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "p.db"))

# 1. le vrai total : prix + port + taxes (Canada) ; une carte des Etats-Unis : importation estimee
x = api._frais_reels({"total": 100.0, "lieu": "CA"})
assert x["total_reel"] == round(100 * (1 + deals.TAXE_ACHAT), 2) and not x["etranger"], x
y = api._frais_reels({"total": 100.0, "lieu": "US"})
assert y["etranger"] and y["total_reel"] > x["total_reel"], y
z = api._frais_reels({"total": 100.0, "lieu": "US"}, "US")
assert not z["etranger"] and z["total_reel"] == round(100 * (1 + deals.TAXE_US), 2), z
print("OK vrai total")

# 2. « il te manque » : une carte de la collection relie le set ; le Radar chasse les autres, une recherche par set
api.carte_garder({"carte": {"joueur": "Anton Frondell", "annee": "2026-27", "marque": "Upper Deck", "set_nom": "Series 1", "parallele": "Young Guns",
                            "numero": "201", "emplacement": "Collection"}, "titre": "2026-27 Upper Deck Series 1 Young Guns Anton Frondell #201", "prix": 10, "photos": []})
r = api.chasse_ajouter("2026-27-ud-series-1", "Young Guns")
assert r["ok"] and r["chasses"][0]["sous"] == "Young Guns", r
assert not api.chasse_ajouter("2026-27-ud-series-1", "Rien de tel")["ok"]
qs = []


def rech(q, **k):
    qs.append(q)
    if k.get("encheres"):
        return []
    return [{"item_id": "11", "titre": "2026-27 Upper Deck Series 1 Young Guns Cole O'Hara #202 RC", "prix_cad": 9, "port_cad": 2, "url": "u", "lieu": "CA"},
            {"item_id": "12", "titre": "2026-27 Upper Deck Young Guns Anton Frondell #201", "prix_cad": 40, "port_cad": 2, "url": "u"},      # je l'ai deja
            {"item_id": "13", "titre": "2026-27 Upper Deck Young Guns Jared Wright #203 lot of 5", "prix_cad": 10, "port_cad": 0, "url": "u"},
            {"item_id": "14", "titre": "2026-27 Upper Deck Young Guns Topias Vilen #999", "prix_cad": 8, "port_cad": 0, "url": "u"}]                # mauvais numero


ebay_compte.rechercher = rech
r = api.mes_deals()
ch = r["chasses"][0]
assert [a["item_id"] for a in ch["annonces"]] == ["11"] and ch["annonces"][0]["numero"] == "202", ch
assert ch["manque"] == ch["total"] - 1 and ch["annonces"][0]["total_reel"] > 11, ch
assert sum(1 for q in qs if "Series 1" in q) == 2, qs                               # une recherche (prix fixe + encans) pour tout le set
assert api.chasse_retirer("2026-27-ud-series-1", "Young Guns")["chasses"] == []
print("OK chasse")

# 3. l'alerte « en feu » se coche depuis le Radar (une alerte promotionnelle : jamais cochee d'office)
assert r["alerte_feu"] is False
assert api.radar_alerte_feu(True)["alerte_feu"] is True and api.mes_deals()["alerte_feu"] is True
print("OK alerte feu")

# 4. le dernier rappel d'un encan suivi : 6 min avant la fin, avec SA limite
import watchlist
import alarmes
pushs = []
api._push = lambda t, x_, d=None: pushs.append((t, x_)) or 1
maint = datetime.now(timezone.utc).replace(microsecond=0)
fin = (maint + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
api.watch_ajouter({"item_id": "777", "titre": "2026-27 Upper Deck Young Guns Cole O'Hara #202", "url": "u", "total": 12, "encan": True, "fin": fin})
api.watch_mise_max("777", 30)
watchlist.verifier(api, proches=True, lire_article=lambda i: {"prix_cad": 12.0, "port_cad": 0.0, "fin": fin}, maint=maint)
titres = [t for t, _ in pushs]
assert any(t.startswith("Dernière chance") for t in titres), pushs
assert any("ta limite 30 $" in x_ for t, x_ in pushs if t.startswith("Dernière chance")), pushs
print("OK dernier rappel")

# 5. « pourquoi il bouge » : des faits (semaine, saison contre avant, legende), jamais un prix
import indice_joueurs
d = {"joueurs": {}}
j0, j7 = (datetime.now() - timedelta(days=7)).date().isoformat(), datetime.now().date().isoformat()
st = lambda an, mj, b, a: {"saison": an, "partie": "Season", "ligue": "NHL", "stats": {"Total Games Played": mj, "Total Goals": b, "Total Assists": a, "Total Points": b + a}}
indice_joueurs.noter_jour(d, "Cole Caufield", {"saisons": [st(2026, 82, 40, 30), st(2027, 10, 5, 4)]}, j0)
indice_joueurs.noter_jour(d, "Cole Caufield", {"saisons": [st(2026, 82, 40, 30), st(2027, 14, 10, 6)]}, j7)
import demande_legale
demande_legale.lire = lambda: {"joueurs": {"Cole Caufield": {"nhl": {"actif": True, "equipe": "MTL", "saisons": 5, "repech": 15, "an_repech": 2019},
                                                              "wiki": {"v60": 9000, "v20": 6000}}}}
d["indice"] = indice_joueurs.calculer(d, demande_legale.lire()["joueurs"], lambda n: 2)
indice_joueurs._ecrire(d)
t = api.tendance_joueur("Cole Caufield")
q = t["pourquoi"]
assert q["semaine"]["pts"] == 7 and q["semaine"]["b"] == 5, q
assert q["saison"]["ppm"] == round(16 / 14, 2) and q["saison"]["ecart_pct"] > 0, q
assert q["buzz"]["pct"] > 0 and "prix" not in json.dumps(q), q
print("OK pourquoi")

# 6. « Verifier le prix » : en vente (du moins cher), encans en cours, le lien des ventes terminees sur eBay, son historique
fin_e = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat().replace("+00:00", "Z")
passe_e = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat().replace("+00:00", "Z")
T = "2026-27 Upper Deck Young Guns Cole O'Hara #202"


def rech3(q, **k):
    if k.get("encheres"):
        return [{"item_id": "31", "titre": T, "prix_cad": 9, "port_cad": 2, "url": "u", "encan": True, "fin": fin_e, "mises": 2},
                {"item_id": "32", "titre": T, "prix_cad": 5, "port_cad": 2, "url": "u", "encan": True, "fin": passe_e, "mises": 9}]       # fini
    return [{"item_id": "21", "titre": T + " RC", "prix_cad": 25, "port_cad": 2, "url": "u", "lieu": "US"},
            {"item_id": "22", "titre": T, "prix_cad": 15, "port_cad": 2, "url": "u", "lieu": "CA"}]


ebay_compte.rechercher = rech3
v = api.verifier_prix("999", T)
assert [x["item_id"] for x in v["en_vente"]] == ["22", "21"] and v["en_vente"][1]["etranger"], v["en_vente"]
assert [x["item_id"] for x in v["encans"]] == ["31"] and v["encans"][0]["mises"] == 2, v["encans"]
assert v["lien_vendues"].startswith("https://www.ebay.ca/sch/i.html?") and "LH_Sold=1" in v["lien_vendues"] and "LH_Complete=1" in v["lien_vendues"]
assert not any(k in json.dumps(v) for k in ("mediane", "moyenne", "valeur", "suggere")), v
print("OK verifier le prix")
