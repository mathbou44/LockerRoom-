"""27 oct 2026 - « pas de faux deals ni de faux prix » : valeur sure, numeros speciaux, etat, vendeur, revue eBay."""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("LOCKERROOM_DONNEES", tempfile.mkdtemp())
import deals  # noqa: E402


def j(n):
    return (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d")


class TestDealsSurs(unittest.TestCase):
    def test_numeros_speciaux_ecartes(self):
        pv = [{"titre": "Auto /99", "prix": 40, "le": j(3)}, {"titre": "Auto 12/99", "prix": 42, "le": j(5)},
              {"titre": "Auto 45/99", "prix": 38, "le": j(9)}, {"titre": "Auto 99/99", "prix": 300, "le": j(2)},
              {"titre": "Auto 1/99", "prix": 250, "le": j(1)}]
        v, garde = deals.valeur_sure(pv, "Auto 33/99")
        self.assertEqual(v, 40.0)
        self.assertEqual(len(garde), 3)

    def test_deux_ventes(self):
        self.assertIsNone(deals.valeur_sure([{"titre": "x", "prix": 10, "le": j(3)}, {"titre": "x", "prix": 30, "le": j(4)}])[0])
        self.assertIsNone(deals.valeur_sure([{"titre": "x", "prix": 20, "le": j(80)}, {"titre": "x", "prix": 21, "le": j(4)}])[0])
        self.assertEqual(deals.valeur_sure([{"titre": "x", "prix": 20, "le": j(10)}, {"titre": "x", "prix": 24, "le": j(4)}])[0], 20.0)

    def test_tendance_et_dispersion(self):
        pv = [{"titre": "x", "prix": p, "le": j(d)} for p, d in [(50, 40), (52, 35), (48, 30), (30, 3), (31, 2), (29, 1)]]
        self.assertEqual(deals.valeur_sure(pv)[0], 30.0)          # la carte baisse : les 3 dernieres ventes comptent
        large = [{"titre": "x", "prix": p, "le": j(5)} for p in (10, 25, 60, 90, 28)]
        self.assertIsNone(deals.valeur_sure(large)[0])

    def test_etat_et_vendeur(self):
        import cartes_match
        self.assertTrue(cartes_match.abimee("Young Guns Demidov RC crease"))
        self.assertFalse(cartes_match.abimee("Young Guns Demidov RC #201"))
        self.assertTrue(deals.vendeur_risque({"vendeur_pct": "92.1", "vendeur_score": 500}))
        self.assertTrue(deals.vendeur_risque({"vendeur_pct": "100", "vendeur_score": 2}))
        self.assertFalse(deals.vendeur_risque({"vendeur_pct": "99.8", "vendeur_score": 1200}))
        self.assertEqual(deals._total({"prix_cad": 20, "port_cad": None}), 35.0)    # port inconnu : 15 $ comptes

    def test_reverifier(self):
        vieux = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(timespec="seconds")
        base = {"total": 20, "valeur": 40, "ratio": .5, "encan": False, "vu_le": vieux, "v": deals.VERSION, "titre": "t", "q": None}
        deals._ecrire({"deals": [dict(base, item_id="111111111"), dict(base, item_id="222222222"), dict(base, item_id="333333333")]})
        reponses = {"111111111": {"prix_cad": 22, "port_cad": 2, "titre": "t"},            # toujours un deal
                    "222222222": {"prix_cad": 39, "port_cad": 2, "titre": "t"}}            # le prix a monte
        def lire_article(i):
            if i not in reponses:
                raise RuntimeError("eBay HTTP 404 : fini")
            return reponses[i]
        r = deals.reverifier(lire_article)
        ids = [x["item_id"] for x in deals.lire()["deals"]]
        self.assertEqual(ids, ["111111111"])
        self.assertEqual(deals.lire()["deals"][0]["total"], 24.0)
        self.assertEqual(r["stats"]["reverifies"], 3)


if __name__ == "__main__":
    unittest.main()
