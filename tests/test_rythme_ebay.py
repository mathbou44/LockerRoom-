"""28 oct 2026 (Mathieu : « on doit recharger les deals, il en manque une chier ») : le chasseur vidait le budget eBay
vers 20 h, puis plus rien jusqu'a la remise a zero ; les deals (6 h au plus) disparaissaient la nuit. Le budget de fond
est maintenant etale sur 24 h, et l'admin peut lancer un tour tout de suite."""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("LOCKERROOM_DONNEES", tempfile.mkdtemp())
import appels_ebay  # noqa: E402
import deals  # noqa: E402


class TestRythme(unittest.TestCase):
    def setUp(self):
        appels_ebay._LIBRE["jusqu"] = 0
        os.environ.pop("LR_EBAY_RYTHME", None)

    def _avec(self, utilises, heures):
        with mock.patch.object(appels_ebay, "utilises", return_value=utilises), \
             mock.patch.object(appels_ebay, "limite", return_value=5000), \
             mock.patch.object(appels_ebay, "_heures_ecoulees", return_value=heures):
            return appels_ebay.budget_ok("browse", True), appels_ebay.budget_ok("browse", False)

    def test_rythme_etale_sur_la_journee(self):
        # 4000 appels de fond par jour : a 10 h apres la remise a zero, (10 + 2) / 24 -> 2000
        self.assertEqual(self._avec(1999, 10), (True, True))
        self.assertEqual(self._avec(2000, 10), (False, True))          # le geste de l'utilisateur passe toujours
        self.assertEqual(self._avec(3990, 23.5), (True, True))
        self.assertEqual(self._avec(4000, 23.5), (False, True))        # plafond de fond : 80 %

    def test_tour_force_passe_le_rythme_pas_le_plafond(self):
        appels_ebay.liberer(60)
        self.assertEqual(self._avec(2500, 5), (True, True))
        self.assertEqual(self._avec(4000, 5), (False, True))

    def test_recharger_lance_un_tour_meme_frais(self):
        lances = []
        with mock.patch.object(deals.threading, "Thread") as T:
            T.return_value.start.side_effect = lambda: lances.append(1)
            deals._ETAT.update(en_cours=False, essai_le=__import__("time").time(), rapide=True,
                               valo_le=__import__("time").time(), proches_le=__import__("time").time())       # 30 oct : pas la passe des valeurs entre deux tours
            self.assertFalse(deals.chasser_si_besoin())                # essai il y a 0 s : pas de tour
            r = deals.recharger()
        self.assertTrue(r["lance"])
        self.assertEqual(lances, [1])
        self.assertGreater(appels_ebay._LIBRE["jusqu"], 0)
        deals._ETAT["en_cours"] = False
        e = deals.etat()
        self.assertIn("ebay_rythme", e)


if __name__ == "__main__":
    unittest.main()
