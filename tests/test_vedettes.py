"""28 oct 2026 - « ou sont les cartes auto patch de veterans ou de legendes ? » : vedettes dans les recherches, hits
d'abord, et une part du budget de verification gardee pour les hits."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("LOCKERROOM_DONNEES", tempfile.mkdtemp())
import deals  # noqa: E402
import vendues  # noqa: E402


class TestVedettes(unittest.TestCase):
    def test_vedettes_intercalees(self):
        r = deals.requetes()
        ved = [x for x in r if x.get("vedette")]
        self.assertTrue(ved)
        self.assertTrue(any(x["q"] == "Wayne Gretzky auto" for x in ved))
        self.assertTrue(any(x.get("vedette") for x in r[:3]))       # des le debut de la rotation, pas a la fin

    def test_memes_vedette_toutes_les_cartes_du_joueur(self):
        L = [{"titre": "2019-20 Upper Deck The Cup Wayne Gretzky Auto Patch /25"},
             {"titre": "2022 SP Legendary Signatures Wayne Gretzky auto"},
             {"titre": "2020 Upper Deck Mario Lemieux auto"}]
        _c, l, _e = deals._memes({"q": "Wayne Gretzky auto", "joueur": "Wayne Gretzky", "vedette": True}, L)
        self.assertEqual(len(l), 2)

    def test_budget_garde_pour_les_hits(self):
        vrai = vendues.rechercher
        vendues.rechercher = lambda q, fond=True: {"ventes": [{"titre": q, "prix": 10, "le": "2026-10-20"}]}
        os.environ["LR_DEALS_VERIF_JOUR"] = "10"
        try:
            st = {}
            f = deals._verificateur({}, st, deals.Bassin(charger=False))
            yg = [f({"texte": f"joueur{i} young guns", "mots": [f"joueur{i}"], "joueur": f"joueur{i}", "auto": False, "patch": False,
                     "serie": None, "annee": 2025, "num": None, "grade": None, "rc": True, "paralleles": set(), "exclu": False,
                     "veut_grade": False, "brute": False, "veut_serie": False, "base": False, "produits": set()}) for i in range(8)]
            hits = [f({"texte": f"legende{i} auto patch /25", "mots": [f"legende{i}"], "joueur": f"legende{i}", "auto": True, "patch": True,
                       "serie": 25, "annee": 2020, "num": None, "grade": None, "rc": False, "paralleles": set(), "exclu": False,
                       "veut_grade": False, "brute": False, "veut_serie": True, "base": False, "produits": set()}) for i in range(8)]
        finally:
            vendues.rechercher = vrai
            os.environ.pop("LR_DEALS_VERIF_JOUR", None)
        self.assertEqual(sum(1 for x in yg if x is not None), 4)      # 40 % de 10 pour les cartes ordinaires
        self.assertEqual(sum(1 for x in hits if x is not None), 6)    # le reste pour les hits


if __name__ == "__main__":
    unittest.main()
