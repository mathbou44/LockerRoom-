"""28 oct 2026 : le modele configure est refuse par Anthropic (404) -> on prend le meilleur modele que la cle peut utiliser."""
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("LOCKERROOM_DONNEES", tempfile.mkdtemp())
import vision  # noqa: E402


class Rep(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestModele(unittest.TestCase):
    def setUp(self):
        vision._MODELE_OK["m"] = None

    def test_modele_refuse_on_bascule(self):
        vus = []

        def ouvrir(req, timeout=None):
            if "/v1/models" in req.full_url:
                return Rep(json.dumps({"data": [{"id": "claude-sonnet-9"}, {"id": "claude-opus-9"}, {"id": "claude-haiku-9"}]}).encode())
            m = json.loads(req.data)["model"]
            vus.append(m)
            if m != "claude-opus-9":
                raise urllib.error.HTTPError(req.full_url, 404, "x", {}, io.BytesIO(b'{"error":{"type":"not_found_error","message":"model: x"}}'))
            return Rep(b'{"content": []}')
        with mock.patch.object(vision.urllib.request, "urlopen", side_effect=ouvrir), mock.patch.object(vision, "_cle", return_value="k"):
            r = vision._appeler({"model": vision.MODELE, "messages": []})
            self.assertEqual(r, {"content": []})
            vision._appeler({"model": vision.MODELE, "messages": []})        # la suite : directement le bon modele
        self.assertEqual(vus, [vision.MODELE, "claude-opus-9", "claude-opus-9"])

    def test_credit_epuise_message_clair(self):
        def ouvrir(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 400, "x", {}, io.BytesIO(b'{"error":{"message":"Your credit balance is too low"}}'))
        with mock.patch.object(vision.urllib.request, "urlopen", side_effect=ouvrir), mock.patch.object(vision, "_cle", return_value="k"):
            with self.assertRaises(vision.Erreur) as e:
                vision._appeler({"model": "m", "messages": []})
        self.assertIn("crédit", str(e.exception))
        self.assertEqual(vision.derniere_erreur()["code"], 400)


if __name__ == "__main__":
    unittest.main()
