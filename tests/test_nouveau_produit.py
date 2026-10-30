"""31 oct 2026 (Mathieu : « les nouveaux produits aussi : evalues selon les joueurs presents, la chance d'une numerotee,
d'un patch, d'une auto ou d'une SSP, et leur valeur sur le marche »). Un produit sans Young Guns. Aucun reseau."""
import os
import sys
import tempfile
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import valeur_produit  # noqa: E402

prod = {"id": "test-nouveau", "nom": "2026 Panini Test Hockey", "saison": "2026-27", "marque": "Panini",
        "sous_ensembles": [{"nom": "Base", "groupe": "base", "par_boite": 100},
                           {"nom": "Rated Rookies", "groupe": "recrue", "par_boite": 6},
                           {"nom": "Rated Rookies Gold", "groupe": "recrue", "parallele_de": "Rated Rookies", "tirage": 10},
                           {"nom": "Rookie Autographs", "groupe": "auto", "tirage": 99, "par_boite": 1},
                           {"nom": "Jersey Patches", "groupe": "memo", "par_boite": 1}],
        "cartes": [{"joueur": "Prospect Vedette", "sous_ensemble": "Rated Rookies"}, {"joueur": "Prospect Ordinaire", "sous_ensemble": "Rated Rookies"},
                   {"joueur": "Prospect Vedette", "sous_ensemble": "Rookie Autographs"}, {"joueur": "Joueur Patch Inconnu", "sous_ensemble": "Jersey Patches"},
                   {"joueur": "Joueur Base Inconnu", "sous_ensemble": "Base"}]}
assert valeur_produit.sous_yg(prod) == "Rated Rookies"
m = valeur_produit.joueurs_a_mesurer(prod)
assert m[0] == "Prospect Vedette" and "Joueur Patch Inconnu" in m and "Joueur Base Inconnu" not in m, m
prix = {"Prospect Vedette": 80.0, "Prospect Ordinaire": 4.0}
def chercher(q):
    j = next(x for x in prix if x.lower() in q.lower())
    return [{"titre": f"2026 Panini Rated Rookies {j} RC #{k}", "prix_cad": prix[j] + k, "port_cad": 0} for k in range(5)] + \
           [{"titre": f"2026 Panini Rated Rookies {j} PSA 10", "prix_cad": prix[j] * 6, "port_cad": 0}]
yg = valeur_produit.yg_annonces(prod, chercher)
assert set(yg) == {"Prospect Vedette", "Prospect Ordinaire"} and abs(yg["Prospect Vedette"]["m"] - 82) < 1.5, yg
print("OK test_nouveau_produit", m, yg)
