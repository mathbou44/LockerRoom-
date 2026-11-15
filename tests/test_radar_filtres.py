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
