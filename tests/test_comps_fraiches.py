"""26 nov 2026, 21 h 18 – 21 h 21 (Mathieu, deux fiches : la Matvei Michkov Credentials Debut Ticket Access Auto /99, mise max 70 $
sur des ventes de fevrier a aout : « explique-moi ou est le profit » ; la Gabe Perreault Ice Premieres Patch /25, mise max 31 $
sur une seule vente montree deux fois ; son « oui » aux 3 regles) :
1. FRAICHEUR : pas de valeur (ni mise max ni profit) si la vente comparable la plus recente a plus de 45 jours ;
2. recherche VIEILLE (aucune vente depuis 30 jours) : nos autres ventes de la meme carte, plus recentes, s'ajoutent ;
3. une vente ne compte qu'UNE fois."""
import os, sys, tempfile
from datetime import datetime, timedelta
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import deals, base_ventes, cartes_match
jr = lambda k: (datetime.now() - timedelta(days=k)).strftime("%Y-%m-%d")
assert deals.JOURS_FRAIS == 45 and deals.RECHERCHE_VIEILLE_J == 30

# ---- 3. une vente ne compte qu'une fois (Perreault : la vente du 24 sept, vue par deux recherches a 63,98 $ et 62,90 $)
P = "Gabe Perreault 2025-26 Upper Deck Ice #IPP-GP Ice Premieres Patch #/25"
D = [{"titre": P, "prix": 63.98, "le": jr(63), "url": "https://www.ebay.com/itm/236000111222?hash=a"},
     {"titre": P, "prix": 62.90, "le": jr(63), "url": "https://www.ebay.ca/itm/236000111222"},          # le meme item, un autre lien
     {"titre": P, "prix": 62.90, "le": jr(63), "url": None},                                            # le meme titre, le meme jour, sans lien
     {"titre": P, "prix": 44.08, "le": jr(1), "url": "https://www.ebay.com/itm/236000999888"}]
assert [v["prix"] for v in deals.sans_doublons(D)] == [63.98, 44.08]
assert deals.cle_vente(D[0]) == deals.cle_vente(D[1]) == "i236000111222"
# deux VRAIES ventes le meme jour (deux prix differents) restent deux ventes
assert len(deals.sans_doublons([dict(D[2], prix=40.0), dict(D[2], prix=64.0)])) == 2
AP = {"item_id": "p", "titre": "2025-26 Upper Deck Ice Premieres Patch Gabe Perreault #IPP-GP /25"}
cibp = cartes_match.cible_titre(AP["titre"])
assert len(deals.memes_ventes(cibp, D)) == 2
# la seule vraie vente, vue deux fois : plus jamais « 2 ventes » (la mise max de 31 $ venait de la)
assert deals.valeur_annonce(AP, D[:3], []) is None

# ---- 2 et 1. Michkov : la recherche de la carte s'arrete en aout ; nos archives du joueur ont des ventes d'octobre et novembre
M = "2024-25 UD Credentials Debut Ticket Access Auto Horizontal RC Matvei Michkov /99"
AM = {"item_id": "m", "titre": M, "port_cad": 0.0}
cib = cartes_match.cible_titre(M)
def v(i, prix, j, titre="2024-25 Credentials Debut Ticket Access /99 Matvei Michkov #115 Rookie Auto RC"):
    return {"titre": titre, "prix": float(prix), "le": jr(j), "url": f"https://www.ebay.com/itm/3000000{i:05d}", "photo": None}
VIEILLES = [v(1, 102.93, 94), v(2, 127.23, 254), v(3, 127.23, 256), v(4, 115.8, 264), v(5, 135.81, 282), v(6, 214.44, 314), v(7, 130, 300), v(8, 120, 290)]
avant = deals._valeur_annonce0(AM, VIEILLES, [])
assert avant and avant[0] >= 100, avant                      # sans nos archives : l'ancien niveau (la fiche disait 127 $)
# (1) seule, cette valeur est PERIMEE : aucune vente de 45 jours ou moins -> pas de valeur pour un encan suivi, la fiche, la watchlist
assert deals.fraiche(avant) is None and deals.age_ventes(avant[3]) == 94
r_ = deals.valeur_ou_saison(AM, VIEILLES, [])
assert r_ is None or r_[1] not in deals.SOURCES_SURES, r_        # jamais « Se vend 127 $ » ; au plus une valeur dite « Estimé »
# une valeur « Estimé » (vente unique d'une carte rare, autre saison...) garde ses propres regles (decisions du 7, 14 et 16 nov)
assert deals.fraiche((250.0, "unique", 1, [{"le": jr(200), "prix": 316.0}]))[0] == 250.0
assert deals.fraiche((295.0, "vendues", 2, [{"le": jr(200), "prix": 328.0}, {"le": jr(200), "prix": 427.0}]))[0] == 295.0   # 2 ventes d'un an d'une carte rare (7 nov)
assert deals.fraiche((250.0, "vendues", 3, [{"le": jr(46), "prix": 250.0}])) is None and deals.fraiche((250.0, "vendues", 3, [{"le": jr(45), "prix": 250.0}]))[0] == 250.0
# (2) nos autres ventes du joueur, sous d'AUTRES recherches
base_ventes.noter("matvei michkov credentials ice", [
    {"titre": "2024-25 Upper Deck Credentials Hockey Matvei Michkov #115 Ticket Access Auto /99", "prix": 142.56, "le": jr(12), "url": "https://www.ebay.com/itm/400000000001"},
    {"titre": "2024 CREDENTIALS #115 MATVEI MICHKOV HORIZONTAL DEBUT TICKET ACCESS AUTO RC /99", "prix": 58.94, "le": jr(42), "url": "https://www.ebay.com/itm/400000000002"},
    {"titre": "2024 UPPER DECK CREDENTIALS MATVEI MICHKOV DEBUT TICKET ACCESS AUTO RC /99", "prix": 82.61, "le": jr(49), "url": "https://www.ebay.com/itm/400000000003"},
    {"titre": "2024-25 Credentials Debut Ticket Access Matvei Michkov RC #115 /999", "prix": 12.12, "le": jr(16), "url": "https://www.ebay.com/itm/400000000004"},   # la /999 sans auto : une autre carte
    {"titre": "2024-25 Credentials Debut Ticket Access /99 Matvei Michkov #115 Rookie Auto RC", "prix": 500.0, "le": jr(120), "url": "https://www.ebay.com/itm/400000000005"}],  # plus vieille que la derniere de la recherche : pas ajoutee
    sport="hockey")
deals._MEME.clear()
pv = deals.avec_ventes_du_joueur(AM, cib, deals.memes_ventes(cib, VIEILLES))
ajoutees = sorted(x["prix"] for x in pv if x.get("_arch"))
assert ajoutees == [58.94, 82.61, 142.56], ajoutees
va = deals.valeur_annonce(AM, VIEILLES, [])
assert va and va[0] < avant[0] and 58 <= va[0] <= 100, va[:3]          # autour de 83 $ (refait sur les vraies archives : 82,61 $)
assert deals.fraiche(va) == va and deals.valeur_ou_saison(AM, VIEILLES, [])[0] == va[0]
mm = deals.prix_max(va[0], taxe=deals.taxe_de(AM, valeur=va[0]))
assert mm < 62, mm                                                       # a 62 $ de mise, ce n'etait pas un deal
# une recherche FRAICHE (une vente de la carte dans les 30 jours) n'est pas touchee
FR = VIEILLES + [v(9, 125, 10)]
assert [x for x in deals.avec_ventes_du_joueur(AM, cib, deals.memes_ventes(cib, FR)) if x.get("_arch")] == []
# la base occupee : la regle se tait, sans erreur
deals._MEME.clear()
vrai = base_ventes._cx
base_ventes._cx = lambda *a_, **k_: (_ for _ in ()).throw(__import__("sqlite3").OperationalError("database is locked"))
try:
    assert deals.avec_ventes_du_joueur(AM, cib, deals.memes_ventes(cib, VIEILLES)) == deals.memes_ventes(cib, VIEILLES)
finally:
    base_ventes._cx = vrai

# ---- ou la fraicheur s'applique : valeur_ou_saison (encans suivis, verification tardive, watchlist, « pourquoi »), la fiche
src = open(os.path.join(RACINE, "deals.py"), encoding="utf-8").read()
corps = src[src.index("def valeur_ou_saison("):src.index("UNIQUE_SERIE_MAX = 25")]
assert "return fraiche(valeur_annonce(a, ventes, actives, cib=cib)) or plafonner_meme_titre(" in corps
loc = open(os.path.join(RACINE, "lockerroom.py"), encoding="utf-8").read()
assert "_deals.avec_ventes_du_joueur(" in loc and "_deals.sans_doublons(" in loc and '"ventes_perimees": perimees' in loc
assert "age_ > _deals.JOURS_FRAIS" in loc and 'src_ in ("vendues", "echange")' in loc
app = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()
assert "d.ventes_perimees ?" in app and "last sale ${d.ventes_perimees} days ago: no max bid" in app
print("test_comps_fraiches OK")
