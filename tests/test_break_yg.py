"""31 oct 2026 (Mathieu : « la valeur des equipes est en fonction de la valeur des Young Guns RAW de cette equipe ;
Martone (Flyers) et Frondell (Blackhawks) valent cher ») : 2026-27 Series 1, les Young Guns raw en vente decident.
Aucun reseau."""
import os
import sys
import tempfile
from datetime import datetime
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import catalogue  # noqa: E402
import forfaits  # noqa: E402
import lockerroom  # noqa: E402
import valeur_produit  # noqa: E402

forfaits.produit_permis = lambda pid: True
prod = catalogue.charger("2026-27-ud-series-1")
assert prod, "produit absent"
nom = valeur_produit.sous_yg(prod)
joueurs = sorted({c["joueur"] for c in prod["cartes"] if c.get("sous_ensemble") == nom and "/" not in c["joueur"]})
assert {"Porter Martone", "Anton Frondell", "James Hagens"} <= set(joueurs), joueurs
prix = {j: 6.0 for j in joueurs}
prix.update({"Porter Martone": 95.0, "Anton Frondell": 90.0, "James Hagens": 100.0, "Ivan Demidov": 60.0})
yg = {j: {"m": p, "n": 12} for j, p in prix.items()}
# des annonces factices, comme eBay les renverrait (raw, gradees, paralleles, lots : seules les raw comptent)
def chercher(q):
    j = next(x for x in joueurs if x.lower() in q.lower())
    base = [{"titre": f"2026-27 Upper Deck Young Guns {j} #{k}", "prix_cad": prix[j] + k % 3, "port_cad": 0} for k in range(6)]
    bruit = [{"titre": f"2026-27 Upper Deck Young Guns {j} PSA 10", "prix_cad": prix[j] * 5, "port_cad": 0},
             {"titre": f"2026-27 Upper Deck Young Guns Exclusives {j} /100", "prix_cad": prix[j] * 8, "port_cad": 0},
             {"titre": f"lot 3x 2026-27 Young Guns {j}", "prix_cad": 1, "port_cad": 0}]
    return base + bruit
m = valeur_produit.yg_annonces(prod, chercher)
assert abs(m["Porter Martone"]["m"] - 96) < 2 and m["Porter Martone"]["n"] == 6, m["Porter Martone"]
valeur_produit._ecrire({prod["id"]: {"maj": datetime.now().isoformat(timespec="seconds"), "sous": {}, "yg_annonces": m,
                                     "annonces_recrues": {}, "annonces_etalons": {}}})
a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "b.db"))
r = a.analyse_break({"produit_id": prod["id"], "boites": 12, "cout_boite": 150, "mode": "equipes"})
assert r["ok"], r
rang = [p["cle"] for p in r["places"]]
haut = rang[:6]
for eq in ("PHI", "CHI", "BOS"):
    assert eq in haut, (eq, rang[:10])
px = {p["cle"]: p["prix"] for p in r["places"]}
assert px["PHI"] >= px["NYI"] and px["CHI"] >= px["CGY"], px
print("OK test_break_yg", rang[:8])
# vue acheteur : sans prix de breaker, Boston (Hagens), Philadelphie (Martone) et Chicago (Frondell) en haut aussi
ra = a.analyse_break({"produit_id": prod["id"], "boites": 12, "cout_boite": 150, "mode": "equipes", "acheteur": True})
ordre = [p["cle"] for p in sorted(ra["places"], key=lambda x: -x["score"])]
for eq in ("PHI", "CHI", "BOS"):
    assert eq in ordre[:5], (eq, ordre[:10])
jo = [x["nom"] for x in ra["joueurs"][:6]]
assert {"James Hagens", "Porter Martone", "Anton Frondell"} <= set(jo), jo
print("OK acheteur", ordre[:6], jo[:4])
# 31 oct 2026 : le classement « Recrues » suit la VALEUR des recrues (Hagens, Martone, Frondell en tete), pas la chance
eq_r = [p["cle"] for p in sorted(ra["places"], key=lambda x: -(x.get("ev_recrue") or 0))]
assert set(eq_r[:3]) == {"PHI", "BOS", "CHI"}, eq_r[:8]
jr = [x["nom"] for x in sorted(ra["joueurs"], key=lambda x: -(x.get("ev_recrue") or 0))]
assert set(jr[:3]) == {"James Hagens", "Porter Martone", "Anton Frondell"}, jr[:8]
print("OK recrues", eq_r[:4], jr[:4])


def test_vedette_absente_des_ventes():
    """1er nov 2026 (Mathieu : « Schaefer et Gridin sont de tres bons joueurs recherches ») : une vedette absente de
    l'echantillon des ventes d'un sous-ensemble vaut selon sa demande, pas 0,6 x la mediane."""
    import valeur_produit as vp, valeurs
    vieux = (vp.de, valeurs.connu, valeurs.demande, vp.demande_recrue)
    try:
        prod = {"id": "t", "sous_ensembles": [{"nom": "Rookie X", "groupe": "recrue"}]}
        vp.de = lambda pid: {"sous": {"Rookie X": {"mediane": 8.0, "joueurs": {"A B": {"m": 6, "n": 3}, "C D": {"m": 9, "n": 2},
                                                                              "E F": {"m": 12, "n": 2}, "G H": {"m": 7, "n": 2}}}}}
        D = {"matthew schaefer": 10.8, "a b": 0.5, "c d": 0.8, "e f": 1.5, "g h": 0.6, "joe ordinaire": 0.4}
        valeurs.connu = lambda j: j.lower() in D
        valeurs.demande = lambda j: D.get(j.lower(), 0.5)
        vp.demande_recrue = lambda prod, j: None
        assert vp.valeur(prod, "Rookie X", "Matthew Schaefer", None)[0] > 50
        assert vp.valeur(prod, "Rookie X", "Joe Ordinaire", None)[0] < 8
        assert vp.valeur(prod, "Rookie X", "A B", None)[0] == 6
    finally:
        vp.de, valeurs.connu, valeurs.demande, vp.demande_recrue = vieux


if __name__ == "__main__":
    test_vedette_absente_des_ventes()
    print("ok vedette")
