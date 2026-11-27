"""26 nov 2026, 19 h 16 – 20 h 03 (Mathieu, deux fiches du Radar : la Josh Doan Violet Pixels /65 annoncee 128 $ alors que le meme
titre s'etait vendu 26 $ le 5 nov ; la Porter Martone Auto Patch /175 annoncee 356 $ alors que le meme titre s'etait vendu 83 $
le 19 nov : « c'est inacceptable » ; « mets une regle pour ne plus que ca arrive »). Quand le MEME titre exact s'est deja vendu
dans les 60 jours (nos archives du joueur, n'importe quelle recherche), la valeur ne depasse pas cette vente."""
import os, sys, tempfile
from datetime import datetime, timedelta
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import deals, base_ventes, cartes_match
jr = lambda k: (datetime.now() - timedelta(days=k)).strftime("%Y-%m-%d")
T = "2024 UPPER DECK TEAM CANADA JUNIORS #59 PORTER MARTONE AUTO PATCH /175"
A = {"item_id": "999", "titre": T, "prix_cad": 51.0, "port_cad": 13.0, "encan": True}
def v(i, prix, j, titre=T):
    return {"titre": titre, "prix": float(prix), "le": jr(j), "url": f"https://e/{i}", "photo": None}
# les ventes de la recherche de la carte : l'ete, 204 $ a 464 $ (ce que la fiche montrait : « Sells for $356 »)
ETE = [v(1, 204, 89), v(2, 381, 118), v(3, 464, 127), v(4, 297, 154), v(5, 365, 176), v(6, 356, 160), v(7, 340, 140)]
avant = deals.valeur_annonce(A, ETE, [])
assert avant and avant[0] >= 200, avant                      # sans la vente du meme titre : l'ancien niveau

# la vente du MEME titre, le 19 nov (il y a 7 jours), rangee sous une AUTRE recherche (« porter martone »)
base_ventes.noter("porter martone", [{"titre": T, "prix": 82.88, "le": jr(7), "url": "https://e/83", "cle": "83"},
                                     {"titre": "2024 Upper Deck Team Canada Juniors 109/175 Porter Martone #20 Patch Auto", "prix": 87.2, "le": jr(20), "url": "https://e/87"},
                                     {"titre": T, "prix": 40.0, "le": jr(75), "url": "https://e/40"}], sport="hockey")     # 75 jours : trop vieille
deals._MEME.clear()
va = deals.valeur_annonce(A, ETE, [])
# (depuis 21 h 21, la recherche de l'ete est « vieille » : nos ventes du joueur plus recentes s'y ajoutent, voir test_comps_fraiches)
assert va[0] == 82.88 and va[3][0]["prix"] == 82.88 and va[3][0]["le"] == jr(7), va[:3]
# la recherche de la carte est FRAICHE (3 ventes du mois, autour de 300 $) : c'est le plafond du meme titre qui joue
FR = ETE + [v(8, 300, 5), v(9, 310, 12), v(10, 290, 20)]
sans = deals._valeur_annonce0(A, FR, [])
assert sans[0] >= 290, sans[0]
va = deals.valeur_annonce(A, FR, [])
assert va[0] == 82.88, va[0]
assert va[3][0].get("meme") is True and va[3][0]["prix"] == 82.88 and va[3][0]["le"] == jr(7), va[3][0]
assert va[1] == sans[1] and va[2] == sans[2] and len(va[3]) <= 6
# la mise max suit : bien sous les 51 $ deja mises + 13 $ de port -> plus un deal
mm = deals.prix_max(va[0], taxe=deals.taxe_de(A, valeur=va[0])) - deals.port_eff(A["port_cad"])
assert mm < 51, mm
# majuscules et espaces : le meme titre quand meme
assert deals.valeur_annonce(dict(A, titre="  " + T.lower().replace(" #59", "  #59")), FR, [])[0] == 82.88
# un titre qui ne s'est jamais vendu tel quel : pas de plafond (la valeur de la recherche fraiche reste)
B = dict(A, titre="2024 Upper Deck Team Canada Juniors Porter Martone Auto Patch /175 SP")
assert deals._ventes_meme_titre(B, cartes_match.cible_titre(B["titre"])) == []
# la vente du meme titre est PLUS HAUTE que la valeur : rien ne monte (un plafond, jamais un plancher)
base_ventes.noter("porter martone", [{"titre": T, "prix": 900.0, "le": jr(2), "url": "https://e/900"}], sport="hockey")
deals._MEME.clear()
assert deals.plafonner_meme_titre(A, (300.0, "vendues", 3, []))[0] == 300.0
assert deals.valeur_annonce(A, FR, [])[0] <= sans[0]
# l'annonce elle-meme (meme numero d'item) ne compte pas ; un titre trop court ou sans joueur : la regle se tait
assert deals.plafonner_meme_titre({"titre": "Porter Martone", "item_id": "1"}, (300.0, "vendues", 3, [])) == (300.0, "vendues", 3, [])
assert deals.plafonner_meme_titre(A, None) is None
# les valeurs de secours (autre saison, vente unique...) sont plafonnees aussi : valeur_ou_saison passe par la regle
src = open(os.path.join(RACINE, "deals.py"), encoding="utf-8").read()
corps = src[src.index("def valeur_ou_saison("):src.index("UNIQUE_SERIE_MAX = 25")]
assert "plafonner_meme_titre(a, valeur_autre_saison(" in corps
assert src.count("plafonner_meme_titre(") >= 5
# la base occupee ou absente : jamais d'erreur, la valeur d'avant
deals._MEME.clear()
vrai = base_ventes._cx
base_ventes._cx = lambda *a_, **k_: (_ for _ in ()).throw(__import__("sqlite3").OperationalError("database is locked"))
try:
    assert deals.valeur_annonce(A, FR, [])[0] == sans[0]
finally:
    base_ventes._cx = vrai
# la fiche le dit : « le même titre s'est vendu ... »
app = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()
assert "ventes[0] && ventes[0].meme" in app and "this same listing last sold" in app
print("test_meme_titre OK")
