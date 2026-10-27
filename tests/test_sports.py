"""23 oct 2026 - SlabCoach multi-sports (sports.py)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import calcul  # noqa: E402
import sports  # noqa: E402


class Detection(unittest.TestCase):
    def test_titres(self):
        cas = {
            "2023-24 Upper Deck Young Guns Connor Bedard #451": "hockey",
            "2024 Panini Prizm Caleb Williams Rookie Silver Chicago Bears": "football",
            "2023-24 Prizm Victor Wembanyama RC Spurs": "basketball",
            "2024 Bowman Chrome 1st Auto Jackson Holliday": "baseball",
            "Topps Chrome Shohei Ohtani Dodgers": "baseball",
            "Toronto Raptors Scottie Barnes": "basketball",
            "Patrick Mahomes Chiefs": "football",
            "Vladimir Guerrero Jr Blue Jays": "baseball",
        }
        for titre, attendu in cas.items():
            self.assertEqual(sports.detecter(titre, defaut="hockey"), attendu, titre)

    def test_sport_principal_quand_rien_ne_tranche(self):
        self.assertEqual(sports.detecter("Sidney Crosby", defaut="hockey"), "hockey")
        self.assertEqual(sports.detecter("Rookie card", defaut="basketball"), "basketball")
        self.assertEqual(sports.detecter("Toronto", defaut="football"), "football")     # ville seule : 3 ligues
        self.assertEqual(sports.detecter("Crosby", defaut="football", bonus={"hockey": 3}), "hockey")

    def test_equipes_par_ligue(self):
        self.assertEqual(sports.code_equipe("Chicago Bears", "football"), "CHI")
        self.assertEqual(sports.code_equipe("Maple Leafs"), "TOR")
        self.assertEqual(sports.code_equipe("Dodgers", "baseball"), "LAD")
        self.assertEqual(sports.code_equipe("Montréal Canadiens"), "MTL")
        self.assertEqual(len(sports.equipes("football")), 32)
        self.assertEqual(len(sports.equipes("basketball")), 30)
        self.assertEqual(len(sports.equipes("baseball")), 30)
        self.assertEqual(sports.division("KC", "football"), "AFC Ouest")

    def test_aspects_ebay(self):
        self.assertEqual(sports.aspects_ebay("basketball"), {"Sport": "Basketball", "League": "NBA"})
        self.assertEqual(sports.aspects_ebay(None), {"Sport": "Ice Hockey", "League": "NHL"})

    def test_break_toutes_les_equipes_de_la_ligue(self):
        ck = [{"joueur": "Patrick Mahomes", "equipe": "Kansas City Chiefs", "categorie": "Base"}]
        r = calcul.prix_places(ck, cout_boite=100, sport="football")
        self.assertEqual(len(r["places"]), 32)
        self.assertIn("Kansas City Chiefs", [p["nom"] for p in r["places"]])
        ck_h = [{"joueur": "Nick Suzuki", "equipe": "Montreal Canadiens", "categorie": "Base"}]
        self.assertEqual(len(calcul.prix_places(ck_h, cout_boite=100)["places"]), 32)   # hockey par defaut


if __name__ == "__main__":
    unittest.main()
