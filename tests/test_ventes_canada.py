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
        def appel(q, site, attendre=True, usage=None):
            appels.append(site)
            if site == "ebay.com":
                return {"items": [it(111111111111, 100, "USD", site), it(222222222222, 80, "USD", site)]}, None
            return {"items": [it(222222222222, 110, "CAD", site), it(333333333333, 150, "CAD", site)]}, None
        with mock.patch.object(vendues, "_appel", side_effect=appel), mock.patch.object(vendues, "actif", return_value=True), \
             mock.patch.object(vendues, "_taux_usd_cad", return_value=1.4), mock.patch.object(vendues, "utilises_aujourdhui", return_value=0):
            r = vendues.rechercher("demidov young guns canada test", fond=False)
        self.assertEqual(sorted(appels), ["ebay.ca", "ebay.com"])
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
        def appel(q, site, attendre=True, usage=None):
            return ({"items": [it(444444444444, 50, "USD", site)]}, None) if site == "ebay.com" else (None, "SoldComps HTTP 500")
        with mock.patch.object(vendues, "_appel", side_effect=appel), mock.patch.object(vendues, "actif", return_value=True), \
             mock.patch.object(vendues, "_taux_usd_cad", return_value=1.4), mock.patch.object(vendues, "utilises_aujourdhui", return_value=0):
            r = vendues.rechercher("autre recherche canada test", fond=False)
        self.assertEqual(len(r["ventes"]), 1)
        self.assertIsNone(r["erreur"])

    def test_budget_garde_pour_les_verifications(self):
        """28 oct 2026 : les autres taches de fond ont au plus 35 % ; les verifications de deals gardent le reste (70 %)."""
        u = {None: 40, "verif": 4}
        with mock.patch.object(vendues, "utilises_aujourdhui", side_effect=lambda usage=None: u[usage]), \
             mock.patch.object(vendues, "plafond_jour", return_value=100):
            self.assertFalse(vendues._budget_ok(True, None))          # autres : 36 >= 35
            self.assertTrue(vendues._budget_ok(True, "verif"))        # verifs : 40 < 70
            self.assertTrue(vendues._budget_ok(False, None))          # un tap : jusqu'a 100
            u[None] = 70
            self.assertFalse(vendues._budget_ok(True, "verif"))

    def test_taches_de_fond_un_seul_site(self):
        appels = []
        def appel(q, site, attendre=True, usage=None):
            appels.append(site)
            return {"items": [it(555555555555, 50, "USD", site)]}, None
        with mock.patch.object(vendues, "_appel", side_effect=appel), mock.patch.object(vendues, "actif", return_value=True), \
             mock.patch.object(vendues, "_taux_usd_cad", return_value=1.4), mock.patch.object(vendues, "_budget_ok", return_value=True):
            vendues.rechercher("valeur produit fond test")
            vendues.rechercher("verif deal test", usage="verif")
        self.assertEqual(appels, ["ebay.com", "ebay.com", "ebay.ca"])


    def test_verif_un_seul_credit_si_assez_de_ventes(self):
        """29 oct 2026 : une verification de deal n'interroge eBay.ca que si eBay.com n'a pas deja 3 ventes."""
        appels = []
        def appel(q, site, attendre=True, usage=None):
            appels.append(site)
            n = 3 if "beaucoup" in q else 1
            return {"items": [{"title": f"{q} {site} {k}", "soldPrice": "50", "soldDate": "2026-10-20", "url": f"https://www.ebay.com/itm/{site[-2:]}{k}12345678"} for k in range(n)]}, None
        with mock.patch.object(vendues, "_appel", appel), mock.patch.object(vendues, "actif", lambda: True), \
                mock.patch.object(vendues, "_cache_lire", lambda q: None), mock.patch.object(vendues, "_budget_ok", lambda f, u: True):
            vendues.rechercher("beaucoup gretzky opc", fond=True, usage="verif")
            self.assertEqual(appels, ["ebay.com"])
            appels.clear()
            vendues.rechercher("rare gretzky auto", fond=True, usage="verif")
            self.assertEqual(appels, ["ebay.com", "ebay.ca"])

if __name__ == "__main__":
    unittest.main()
