"""23 oct 2026 - « une photo, un bouton » (vision.py) : sans reseau (Anthropic simule)."""
import base64
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vision  # noqa: E402

PHOTO = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff" + os.urandom(5000)).decode()
REPONSE = {"usage": {"input_tokens": 3000, "output_tokens": 400}, "content": [{"type": "tool_use", "name": "carte", "input": {
    "est_une_carte": True, "sport": "hockey", "joueur": "Connor Bedard", "annee": "2023-24", "marque": "Upper Deck",
    "set_nom": "Series 1", "parallele": "Young Guns", "numero": "451", "tirage": None, "auto": False, "recrue": True,
    "equipe": "Chicago Blackhawks", "titre_ebay": "2023-24 Upper Deck Series 1 Young Guns CONNOR BEDARD #451 RC",
    "confiance": {"joueur": 0.99, "annee": 0.97, "numero": 0.6, "parallele": 0.95}, "a_verifier": ["le numéro : flou"]}}]}


class Vision(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.p = [mock.patch.object(vision, "DOSSIER", self.d), mock.patch.object(vision, "_cle", lambda: "test"),
                  mock.patch("comptes.DONNEES", self.d), mock.patch("comptes.MULTI", False)]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()

    def test_fiche_et_champs_douteux(self):
        with mock.patch.object(vision, "_appeler", return_value=REPONSE) as appel:
            r = vision.identifier([PHOTO, PHOTO])
        corps = appel.call_args[0][0]
        self.assertEqual(corps["model"], vision.MODELE)
        self.assertEqual(sum(1 for b in corps["messages"][0]["content"] if b["type"] == "image"), 2)
        self.assertEqual(r["champs"]["joueur"], "Connor Bedard")
        self.assertEqual(r["champs"]["titre"][:7], "2023-24")
        self.assertEqual(r["a_verifier"], ["numero"])          # confiance 0.6 < 0.85
        self.assertNotIn("tirage", r["champs"])                # null : pas invente
        self.assertGreater(r["cout_usd"], 0)

    def test_meme_photo_jamais_repayee(self):
        with mock.patch.object(vision, "_appeler", return_value=REPONSE) as appel:
            vision.identifier([PHOTO])
            r = vision.identifier([PHOTO])
        self.assertEqual(appel.call_count, 1)
        self.assertTrue(r["cache"])

    def test_pas_une_carte(self):
        rep = {"usage": {}, "content": [{"type": "tool_use", "input": {"est_une_carte": False, "sport": "autre", "joueur": "",
                                                                          "confiance": {}, "a_verifier": []}}]}
        with mock.patch.object(vision, "_appeler", return_value=rep):
            with self.assertRaises(vision.Erreur):
                vision.identifier([PHOTO])

    def test_quota_gratuit(self):
        with mock.patch.object(vision, "_limite_compte", return_value=1), \
                mock.patch.object(vision, "_appeler", return_value=REPONSE):
            vision.identifier([PHOTO])
            autre = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff" + os.urandom(5000)).decode()
            with self.assertRaises(vision.Erreur):
                vision.identifier([autre])

    def test_sans_cle(self):
        with mock.patch.object(vision, "_cle", lambda: ""):
            self.assertFalse(vision.statut()["disponible"])
            with self.assertRaises(vision.Erreur):
                vision.identifier([PHOTO])


if __name__ == "__main__":
    unittest.main()
