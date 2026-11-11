"""11 nov 2026 (Mathieu : « un tres bon jeune joueur en periode difficile (Nazar, Doan) : un bon moment pour acheter » ;
« dans l'admin, le cout d'acquisition avec les ventes ; il y a juste moi ») : les joueurs EN CREUX (stats publiques,
jamais un prix) et la ligne de ventes reelles du Radar, que SEUL l'admin verifie recoit."""
import os
import sys
import tempfile
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
comptes.DOSSIER_COMPTES = os.path.join(comptes.DONNEES, "comptes")
import indice_joueurs as ij

J = date(2026, 11, 11)


def fiche(pts_avant, gp_avant, pts, gp, l5, naiss="2004-01-14", pick=13, pos="C", toi=("18:19", "17:25")):
    return {"actif": True, "equipe": "CHI", "pos": pos, "naissance": naiss, "repech": pick, "saisons": 4, "l5": l5,
            "saison": {"gamesPlayed": gp, "points": pts},
            "par_saison": [{"s": 20242025, "l": "NHL", "gp": 53, "p": 26, "toi": "15:52"},
                           {"s": 20252026, "l": "NHL", "gp": gp_avant, "p": pts_avant, "toi": toi[0]},
                           {"s": 20262027, "l": "NHL", "gp": gp, "p": pts, "toi": toi[1]}]}


# 1. Nazar (0,44 contre 0,62) : en creux ; ses 5 derniers matchs reviennent a son rythme : il en sort
c = ij.creux(fiche(41, 66, 7, 16, 2), J)
assert c and c["etat"] == "creux" and c["ecart_pct"] == -30 and c["age"] == 22 and c["toi_ratio"] == 0.95, c
assert ij.creux(fiche(41, 66, 7, 16, 4), J)["etat"] == "rebond"
# pas un creux : il produit comme avant ; trop peu de matchs ; un veteran ; un gardien ; un joueur sans talent demontre
assert ij.creux(fiche(41, 66, 11, 16, 2), J) is None
assert ij.creux(fiche(41, 66, 1, 5, 0), J) is None
assert ij.creux(dict(fiche(41, 66, 7, 16, 2), naissance="1990-01-01", saisons=12), J) is None
assert ij.creux(fiche(41, 66, 7, 16, 2, pos="G"), J) is None
assert ij.creux(fiche(25, 66, 3, 16, 0, pick=150), J) is None
print("OK creux")

# 2. l'Indice : la pastille, et « pourquoi » le dit
base = {"Frank Nazar": {"nhl": dict(fiche(41, 66, 7, 16, 2), naissance="2004-01-14"), "wiki": {"v60": 3000, "v20": 1000}}}
for i in range(10):
    base[f"Joueur {i}"] = {"nhl": {"actif": True, "equipe": "BOS", "saisons": 5, "l5": i % 4}, "wiki": {"v60": 500 + i, "v20": 160}}
I = ij.calculer({"joueurs": {}}, base, lambda n: 1)
assert "en_creux" in I["Frank Nazar"]["pastilles"] and I["Frank Nazar"]["creux"]["avant_ppm"] == 0.62, I["Frank Nazar"]
ij._ecrire({"joueurs": {}, "indice": I, "le": 0})
assert ij.top(5, "en_creux")[0]["nom"] == "Frank Nazar"
print("OK creux indice")

# 3. le Radar : la rangee « En creux » ; la ligne de ventes reelles SEULEMENT pour l'admin verifie
import lockerroom
import ebay_compte
import vendues
import demande_legale
demande_legale.populaires = lambda n=12, recrues=False: []


def rech(q, **k):
    if "Nazar" in q:
        return [{"item_id": "n1", "titre": "2024-25 Upper Deck Young Guns Frank Nazar #232", "prix_cad": 40, "port_cad": 5, "url": "u"}]
    return []


ebay_compte.rechercher = rech
vendues.memes_cache = lambda t, q=None, n=16, age_max=0: {"ventes": [{"prix": 60}] * 5, "mediane": 60.0, "nb": 5,
                                                          "points": [["2026-11-08", 64], ["2026-11-05", 62], ["2026-10-20", 55], ["2026-10-10", 54]]}
comptes.MULTI = True
api = lockerroom.Api()
cid, _ = comptes.trouver_ou_creer("apple-sub-77", "Quelqu'un", "apple")
with comptes.utiliser(cid):
    api.deals_profil_regler({"favoris": ["Connor Bedard"], "collectionne": ["recrues"], "prix_max": 200})
    r = api.mes_deals()
    assert r["ok"] and [g["joueur"] for g in r["creux"]] == ["Frank Nazar"] and r["creux"][0]["creux"]["etat"] == "creux", r.get("creux")
    tout = [x for g in r["creux"] + r["pour_toi"] + r["decouvrir"] + r["chauds"] for x in g["annonces"]] + r["deals"]
    assert tout and not any("admin_vendu" in x for x in tout), "un utilisateur ne recoit jamais les ventes reelles"
    assert "admin_vendu" not in str(r)
api._est_admin = lambda reel=False: True
api._MES_DEALS.clear() if hasattr(api, "_MES_DEALS") else None
with comptes.utiliser(cid):
    r = api.mes_deals()
    x = r["creux"][0]["annonces"][0]
    av = x.get("admin_vendu")
    assert av and av["med"] == 60.0 and av["nb"] == 5 and av["achat_max"] > 0 and av["ecart_pct"] == -25, x
# la vue simulee (l'admin regarde l'app comme un Pro) : plus rien
vrai = lockerroom.vue_simulee
lockerroom.vue_simulee = lambda: "pro"
api._est_admin = lockerroom.Api._est_admin.__get__(api)
with comptes.utiliser(cid):
    r = api.mes_deals()
    assert "admin_vendu" not in str(r)
lockerroom.vue_simulee = vrai
print("OK admin ventes reelles")
