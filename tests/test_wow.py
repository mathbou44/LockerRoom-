"""23 nov 2026 (Mathieu : « les trades des gros joueurs doivent stand out des news ; de meme pour tout ce qui est WOW » ; « Larkin
devrait etre vu des l'ouverture du Radar, sans fucker tout l'ordre ») : la nouvelle WOW est marquee et passe devant ; le Radar a
son bandeau (wow_actuel)."""
import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
comptes.DOSSIER_COMPTES = os.path.join(comptes.DONNEES, "comptes")
from datetime import date, datetime, timedelta, timezone
import demande_legale
import indice_joueurs as ij
import nouvelles as nv

demande_legale.lire = lambda: {"joueurs": {"Dylan Larkin": {"nhl": {"equipe": "DET", "actif": True, "carriere": {"points": 649}}},
                                            "Kirby Dach": {"nhl": {"equipe": "MTL", "actif": True, "carriere": {"points": 410}}},
                                            "Sidney Crosby": {"nhl": {"equipe": "PIT", "actif": True, "carriere": {"points": 1700}}},
                                            "Joe Quatrieme": {"nhl": {"equipe": "DET", "actif": True, "carriere": {"points": 40}}}}}
ECH = {}
ij.lire = lambda: {"indice": {}, "echanges": ECH}
nv._GROS["le"] = 0.0
ech, gros = nv._gros_joueurs()
assert "dylan larkin" in ech and "kirby dach" in ech and "joe quatrieme" not in ech and "dylan larkin" in gros and "kirby dach" not in gros
G = (ech, gros)

# 1. une manchette WOW : un gros joueur + un echange FERME, un honneur, un trophee, un exploit
w = nv.wow_de("Montreal Canadiens Acquire Dylan Larkin In Massive Package Deal With Detroit Red Wings", G)
assert w == {"type": "echange", "joueur": "Dylan Larkin", "sens": "hausse", "de": "Detroit", "vers": "Montréal"}, w
assert nv.wow_de("Larkin traded to Canadiens by Red Wings for package involving Dach, Hage", G)["joueur"] == "Dylan Larkin"      # nom de famille seul
assert nv.wow_de("Red Wings acquire Kirby Dach in Larkin trade", G) is None or nv.wow_de("Red Wings acquire Kirby Dach in Larkin trade", G)["joueur"] in ("Kirby Dach", "Dylan Larkin")
assert nv.wow_de("Could Dylan Larkin be traded to Montreal?", G) is None and nv.wow_de("Dylan Larkin trade rumors heat up", G) is None   # rumeur
assert nv.wow_de("Red Wings trade Joe Quatrieme to Canadiens", G) is None                                                    # pas un gros joueur
assert nv.wow_de("Dylan Larkin scores in win over Bruins", G) is None                                                         # une nouvelle ordinaire
assert nv.wow_de("Sidney Crosby wins Hart Trophy", G) == {"type": "trophee", "joueur": "Sidney Crosby"}
assert nv.wow_de("Sidney Crosby records hat trick, reaches 1,700 points", G)["type"] == "exploit"
assert nv.wow_de("Kirby Dach records hat trick", G) is None                                # un exploit : seulement pour les plus gros
print("OK wow_de")

# 2. une seule par joueur et par type (dans la langue du client si possible), epinglee 48 h
maint = datetime.now(timezone.utc)          # 25 nov 2026 : le test etait fige au 23 nov ; nv.pour lit l'heure reelle : apres 48 h, plus rien d'epingle (echec)
def N(titre, h, langue="en", lien=None):
    d = maint - timedelta(hours=h)
    return {"titre": titre, "date": d.date().isoformat(), "heure": d.isoformat(), "lien": lien or "https://x.test/" + str(abs(hash(titre))), "langue": langue,
            "source": "Test", "sport": "hockey", "type": "ligue", "libelle": "LNH", "impact": 0}
L = [N("Bruins beat Sabres 4-2", 1), N("Canadiens Acquire Dylan Larkin In Massive Package Deal", 10), N("Red Wings trade Dylan Larkin to Canadiens", 11),
     N("Le Canadien acquiert Dylan Larkin des Red Wings", 12, "fr"), N("Sidney Crosby wins Hart Trophy", 60), N("Leafs lose again", 2)]
E_ = nv.marquer_wow(L, "fr", G, maint)
assert [x["titre"] for x in E_] == ["Le Canadien acquiert Dylan Larkin des Red Wings"], [x["titre"] for x in E_]          # la francaise, une seule
assert sum(1 for x in L if x.get("wow")) == 2 and L[4]["wow"]["type"] == "trophee" and L[4] not in E_                      # Crosby : WOW, mais 60 h : pas epingle
for x in L: x.pop("wow", None)
assert [x["titre"] for x in nv.marquer_wow(L, "en", G, maint)] == ["Canadiens Acquire Dylan Larkin In Massive Package Deal"]
print("OK une seule, epinglee")

# 3. dans le fil du client : le WOW passe devant, le reste garde son ordre
for x in L: x.pop("wow", None)
nv.lire_cache = lambda: {"sports": {"hockey": L}, "maj": "x", "etat": {}}
nv._GROS.update(le=9e18, v=G)
r = nv.pour(["hockey"], [], n=4, langue="en")["items"]
assert r[0]["titre"].startswith("Canadiens Acquire Dylan Larkin") and r[0]["wow"]["sens"] == "hausse" and len(r) == 4, [x["titre"] for x in r]
assert sum(1 for x in r if "Larkin" in x["titre"] and x.get("wow")) == 1
print("OK fil")

# 4. le bandeau du Radar : l'echange d'un gros joueur vers (ou depuis) un gros marche, celui qui arrive d'abord ; rien d'autre ne bouge
import lockerroom
auj = date.today().isoformat()
ECH.update({"Kirby Dach": {"de": "MTL", "vers": "DET", "le": auj, "source": "vu"},
            "Dylan Larkin": {"de": "DET", "vers": "MTL", "le": auj, "source": "nouvelles"},
            "Joe Quatrieme": {"de": "DET", "vers": "TOR", "le": auj, "source": "vu"},                      # pas un gros joueur
            "Sidney Crosby": {"de": "PIT", "vers": "COL", "le": auj, "source": "vu"}})                      # ni Toronto ni Montreal : neutre
api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
lockerroom.Api._WOW.update(le=0.0, v=None)
w = api.wow_actuel()["wow"]
assert [x["joueur"] for x in w if x["type"] == "echange"] == ["Dylan Larkin", "Kirby Dach"], w
assert w[0] == {"id": "ech:dylan larkin:MTL", "type": "echange", "joueur": "Dylan Larkin", "sens": "hausse", "de": "Detroit", "vers": "Montréal", "le": auj}, w[0]
assert not any(k in str(w) for k in ("prix", "$")), w
ECH["Dylan Larkin"]["le"] = (date.today() - timedelta(days=6)).isoformat(); lockerroom.Api._WOW.update(le=0.0, v=None)
assert "Dylan Larkin" not in [x["joueur"] for x in api.wow_actuel()["wow"] if x["type"] == "echange"]       # apres 4 jours : plus de bandeau
print("WOW OK")
