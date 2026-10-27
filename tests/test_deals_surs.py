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


class TestRepere(unittest.TestCase):
    def test_repere_sur_les_ventes(self):
        import cartes_match
        import sante
        self.assertTrue(cartes_match.decoder("SP Game Used Nations Face-Off Fabrics Filip Forsberg")["patch"])   # « Fabrics »
        self.assertEqual(sante.evaluer_vendues(65, 60, 5)["verdict"], "ok")
        self.assertEqual(sante.evaluer_vendues(65, 34, 5)["verdict"], "baisser")
        r = sante.evaluer_vendues(65, None, 1)                  # pas de valeur sure : aucun verdict de prix
        self.assertEqual((r["verdict"], r["mediane"], r["ecart"]), ("ok", None, None))




class TestToujoursQuelqueChose(unittest.TestCase):
    """27 oct 2026 : apres une mise a jour, les users voient toujours quelque chose."""
    def test_continuite_et_a_surveiller(self):
        maint = datetime.now(timezone.utc).isoformat(timespec="seconds")
        ventes = [{"titre": "Young Guns Demidov", "prix": p, "le": j(d)} for p, d in [(40, 3), (42, 5), (41, 8)]]
        vieux = {"item_id": "555555555", "titre": "Young Guns Demidov", "total": 20, "valeur": 45, "ratio": .44, "encan": False,
                 "vu_le": maint, "v": deals.VERSION - 1, "vendues": ventes}
        self.assertTrue(deals.valide(dict(vieux)))                    # rejuge, pas efface
        trop = dict(vieux, item_id="666666666", total=35)
        self.assertFalse(deals.valide(trop))                          # 35 > 70 % de 41 : plus un deal
        pres = dict(vieux, item_id="777777777", total=33, ratio=.8, v=deals.VERSION, palier="pres")
        deals._ecrire({"deals": [dict(vieux)], "pres": [pres], "maj": maint})
        import lockerroom
        a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "t.db"))
        r = a.deals_liste({})
        self.assertEqual([x["item_id"] for x in r["deals"]], ["555555555"])
        self.assertEqual([x["item_id"] for x in r["pres"]], ["777777777"])
        # plus aucun deal courant : la derniere bonne liste sert de secours
        deals._ecrire({"deals": [], "pres": [], "maj": maint, "secours": {"le": maint, "deals": [dict(vieux, v=deals.VERSION)]}})
        r = a.deals_liste({})
        self.assertTrue(r["secours"])
        self.assertEqual(len(r["deals"]), 1)

if __name__ == "__main__":
    unittest.main()
