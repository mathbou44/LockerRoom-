"""15 nov 2026 (Mathieu, captures du Radar Pro) : encans sans mise a gros prix et encans finis caches ; le lien des ventes
eBay avec le nom complet, l'annee et le numero ; un joueur peu recherche ne monte pas a 88 (la popularite du joueur d'abord)."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import lockerroom, cartes_match as cm, score_slab as S
A = lockerroom.Api
x = {"encan": True, "mises": 0, "total": 80, "fin": "2099-01-01T00:00:00Z"}
assert A._encan_douteux(x) and not A._encan_douteux(dict(x, mises=2)) and not A._encan_douteux(dict(x, total=12))
assert A._encan_douteux(dict(x, mises=5, fin="2020-01-01T00:00:00Z")) and not A._encan_douteux({"encan": False, "total": 500})
api = A(os.path.join(tempfile.mkdtemp(), "t.db"))
api._provenance = lambda: ["CA", "US"]
r = api._filtrer_provenance({"deals": [x, dict(x, mises=3)], "pour_toi": [{"annonces": [x]}, {"annonces": [dict(x, mises=1)]}]})
assert len(r["deals"]) == 1 and len(r["pour_toi"]) == 1, r
print("ENCANS OK")
t = "2021 Skybox Metal Universe Rookies PMG Red /100 Scott Perunovich #171 Rookie RC"
c = cm.cible_titre(t); q = A._requete_vendues(t, c, cm.requete_ebay(c))
assert "perunovich" in q and "2021" in q and "171" in q, q
print("LIEN OK")
assert S.plafond_joueur(88, {"score": 70}, {"indice": 25}) < 55 and S.plafond_joueur(88, {"score": 70}, {"indice": 85}) == 88
assert S.plafond_joueur(88, {"score": 70}, None) == 88
print("POPULARITE OK")

# une EQUIPE dans le Radar : son surnom ou ses joueurs les plus recherches au titre (une seule recherche)
import ebay_compte, indice_joueurs
assert A.equipe_fav("Canadiens")["abrev"] == "MTL" and A.equipe_fav("Habs")["abrev"] == "MTL" and A.equipe_fav("Maple Leafs")["abrev"] == "TOR"
assert A.equipe_fav("Connor Bedard") is None
indice_joueurs.lire = lambda: {"indice": {"Lane Hutson": {"equipe": "MTL", "indice": 90, "actif": True}, "Nick Suzuki": {"equipe": "MTL", "indice": 80, "actif": True},
                                         "Auston Matthews": {"equipe": "TOR", "indice": 95, "actif": True}}}
Q = []
def rech(q, **k):
    Q.append(q)
    return [{"item_id": "1", "titre": "2024-25 Upper Deck Young Guns Lane Hutson RC", "prix_cad": 30, "port_cad": 0, "url": "u"},
            {"item_id": "2", "titre": "1990 Patrick Roy Montreal Canadiens OPC", "prix_cad": 20, "port_cad": 0, "url": "u"},
            {"item_id": "3", "titre": "Auston Matthews Young Guns", "prix_cad": 50, "port_cad": 0, "url": "u"},
            {"item_id": "4", "titre": "Lot of 50 Canadiens cards", "prix_cad": 40, "port_cad": 0, "url": "u"}] if not k.get("encheres") else []
ebay_compte.rechercher = rech
api._pays_radar = lambda: "CA"
l = api._radar_annonces("Canadiens", ["recrues"])
assert [x["item_id"] for x in l] == ["1", "2"], l
assert l[0]["joueur"] == "Lane Hutson" and l[1]["equipe"] == "Montreal Canadiens"
assert Q[0].startswith("(canadiens, hutson, suzuki)"), Q
print("EQUIPE OK")
