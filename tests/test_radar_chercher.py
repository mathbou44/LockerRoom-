"""19 nov 2026 (Mathieu : « quand je cherche Gridin je ne trouve rien, mais sur eBay il y en a ») : la recherche du Radar
cherche aussi sur eBay ; seules les cartes du bareme sortent, notees ; la meme recherche ne coute rien la 2e fois (tous les
comptes) ; les A et A+ entrent dans la vitrine."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom, score_slab, forfaits, vitrine

T = {"1": ("2025 Upper Deck Premier Matvei Gridin Rookie Patch Auto RC /249", 76.0, 92, "A"),
     "2": ("2025-26 Upper Deck Young Guns Matvei Gridin #466 RC", 32.0, 80, "A"),
     "3": ("2025-26 Upper Deck Series 2 Matvei Gridin base #12", 4.0, 40, "D"),
     "4": ("2025 Upper Deck Premier Matvei Gridin Focus Rookies Auto Patch /99", 165.0, 95, "A")}
appels = []


def fausses(self, nom, coll, pmin=None, pmax=None, limite=40):
    appels.append(nom)
    return [{"item_id": k, "titre": t, "total": p, "encan": k != "2", "fin": "2099-01-01T00:00:00Z", "joueur": "Matvei Gridin"}
            for k, (t, p, _, _) in T.items()]


def notes(l):
    for x in l:
        _, _, s, so = T[x["item_id"]]
        x["score"], x["sorte"], x["joueur"] = s, so, "Matvei Gridin"


lockerroom.Api._radar_annonces = fausses
score_slab.annoter_lot = notes
forfaits.est_pro = lambda *a, **k: True
ajoutes = []
vitrine.ajouter = lambda l: ajoutes.extend(x["item_id"] for x in l if (x.get("score") or 0) >= 86)
api = lockerroom.Api()
api._est_admin = lambda *a, **k: False
api.deals_profil_lire = lambda: {"ok": True, "prix_min": None, "iq_min": None}
lockerroom.comps_permis = lambda *a, **k: False            # vue Pro

r = api.radar_chercher("gridin")
ids = sorted(x["item_id"] for x in r["annonces"])
assert r["ok"] and ids == ["1", "2", "4"], r               # une recherche choisie : tout le bareme (B et plus) ; la base a 4 $ non
assert all(x.get("recherche") and x.get("score") for x in r["annonces"])
assert sorted(ajoutes) == ["1", "4"], ajoutes              # gardees pour tout le monde (« A la une »)
r2 = api.radar_chercher("  Gridin ")                       # un autre compte, la meme recherche : aucun appel
assert appels == ["gridin"] and len(r2["annonces"]) == 3, appels
assert api.radar_chercher("gr")["annonces"] == [] and appels == ["gridin"]     # trop court : rien
forfaits.est_pro = lambda *a, **k: False
assert api.radar_chercher("gridin").get("pro")             # gratuit : non
print("OK test_radar_chercher")
