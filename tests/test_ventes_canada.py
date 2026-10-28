"""28 oct 2026 (Mathieu : « Canada, y'en a énormément et c'est notre clientèle #1 ») : ventes d'eBay.com ET d'eBay.ca."""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("LOCKERROOM_DONNEES", tempfile.mkdtemp())
import vendues  # noqa: E402


def it(i, prix, dev, site):
    return {"title": f"2025-26 Young Guns Demidov #{i}", "soldPrice": str(prix), "soldCurrency": dev, "endedAt": "2026-10-27T10:00:00Z",
            "url": f"https://www.{site}/itm/{i}"}


class TestCanada(unittest.TestCase):
    def test_deux_sites_fusionnes_sans_doublon(self):
        appels = []
        def appel(q, site):
            appels.append(site)
            if site == "ebay.com":
                return {"items": [it(111111111111, 100, "USD", site), it(222222222222, 80, "USD", site)]}, None
            return {"items": [it(222222222222, 110, "CAD", site), it(333333333333, 150, "CAD", site)]}, None
        with mock.patch.object(vendues, "_appel", side_effect=appel), mock.patch.object(vendues, "actif", return_value=True), \
             mock.patch.object(vendues, "_taux_usd_cad", return_value=1.4), mock.patch.object(vendues, "utilises_aujourdhui", return_value=0):
            r = vendues.rechercher("demidov young guns canada test")
        self.assertEqual(appels, ["ebay.com", "ebay.ca"])
        ids = sorted(vendues._id_vente(v) for v in r["ventes"])
        self.assertEqual(ids, ["111111111111", "222222222222", "333333333333"])
        ca = [v for v in r["ventes"] if v["site"] == "ebay.ca"]
        self.assertEqual([v["prix"] for v in ca], [150.0])                 # en $ CA, sans conversion

    def test_site_principal_seul_si_demande(self):
        with mock.patch.dict(os.environ, {"LR_SOLDCOMPS_SITES": "ebay.com"}):
            self.assertEqual(vendues.sites(), ["ebay.com"])
        with mock.patch.dict(os.environ, {"LR_SOLDCOMPS_SITES": "n'importe quoi"}):
            self.assertEqual(vendues.sites(), ["ebay.com"])
        os.environ.pop("LR_SOLDCOMPS_SITES", None)
        self.assertEqual(vendues.sites(), ["ebay.com", "ebay.ca"])

    def test_erreur_du_site_canadien_garde_les_ventes_us(self):
        def appel(q, site):
            return ({"items": [it(444444444444, 50, "USD", site)]}, None) if site == "ebay.com" else (None, "SoldComps HTTP 500")
        with mock.patch.object(vendues, "_appel", side_effect=appel), mock.patch.object(vendues, "actif", return_value=True), \
             mock.patch.object(vendues, "_taux_usd_cad", return_value=1.4), mock.patch.object(vendues, "utilises_aujourdhui", return_value=0):
            r = vendues.rechercher("autre recherche canada test")
        self.assertEqual(len(r["ventes"]), 1)
        self.assertIsNone(r["erreur"])


if __name__ == "__main__":
    unittest.main()
