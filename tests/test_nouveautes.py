"""24 oct 2026 - la meme carte (cartes_match), l'annonce complete (annonces), Gratuit/Pro (forfaits), deals, analyse de break.
python tests/test_nouveautes.py"""
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

os.environ.setdefault("LOCKERROOM_DONNEES", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cartes_match as cm  # noqa: E402


class MemeCarte(unittest.TestCase):
    TITRES = {
        "2023-24 Upper Deck Will Smith Young Guns Rookie RC #230 San Jose Sharks": None,
        "2023-24 UD Will Smith YG #230 RC Sharks": None,
        "2023-24 Upper Deck Young Guns Will Smith #230 Exclusives /100": "numérotée /100",
        "2023-24 Upper Deck Young Guns Will Smith PSA 10 Gem Mint": "gradée",
        "2023-24 Upper Deck Young Guns Canvas Will Smith C230": "variante canvas",
        "Lot of 3 Will Smith Young Guns": "lot / pas une carte seule",
        "2023-24 Upper Deck Young Guns Connor Bedard #451": "autre carte",
        "2023-24 Upper Deck Will Smith Young Guns Jersey Patch": "patch / relique",
        "Will Smith 2023 SP Authentic Future Watch Auto /999": "autre carte",
    }

    def test_will_smith_young_guns(self):
        c = cm.cible("will smith young guns")
        for t, attendu in self.TITRES.items():
            r = cm.raisons_refus(c, t)
            if attendu is None:
                self.assertEqual(r, [], t)
            else:
                self.assertTrue(r and r[0].startswith(attendu), (t, r))

    def test_variantes_demandees(self):
        self.assertEqual(cm.raisons_refus(cm.cible("bedard young guns psa 10"), "2023-24 UD Young Guns Connor Bedard #451 PSA 10"), [])
        self.assertTrue(cm.raisons_refus(cm.cible("bedard young guns psa 10"), "2023-24 UD Young Guns Connor Bedard #451 PSA 9"))
        self.assertEqual(cm.raisons_refus(cm.cible("2023 prizm silver wembanyama"), "2023 Panini Prizm Victor Wembanyama Silver Prizm #136 RC"), [])
        self.assertTrue(cm.raisons_refus(cm.cible("2023 prizm silver wembanyama"), "2023 Panini Prizm Victor Wembanyama #136 RC"))
        self.assertEqual(cm.decoder("2024/25 Upper Deck Bedard #201")["serie"], None)
        self.assertEqual(cm.decoder("Celebrini Exclusives 12/100")["serie"], 100)
        self.assertEqual(cm.decoder("Red Wings Young Guns")["paralleles"], set())

    def test_mediane_robuste(self):
        med, garde = cm.mediane_robuste([10, 40, 42, 44, 45, 400])
        self.assertEqual(med, 43.0)
        self.assertNotIn(400, garde)

    def test_apprentissage(self):
        q = "celebrini young guns"
        cm.apprendre(q, "111", "2024-25 Young Guns Macklin Celebrini Bad Copy", False)
        c, g, e = cm.filtrer(q, [{"item_id": "111", "titre": "2024-25 Young Guns Macklin Celebrini"},
                                 {"item_id": "112", "titre": "2024-25 Young Guns Macklin Celebrini #451"}])
        self.assertEqual([x["item_id"] for x in g], ["112"])
        cm.apprendre(q, "111", "x", True)
        c, g, e = cm.filtrer(q, [{"item_id": "111", "titre": "2024-25 Young Guns Macklin Celebrini PSA 10"}])
        self.assertEqual(len(g), 1)                   # confirmee par l'utilisateur : gardee

    def test_carte_ou_pas(self):
        self.assertTrue(cm.est_carte("2023-24 Upper Deck Young Guns Will Smith #230"))
        self.assertFalse(cm.est_carte("LEGO 75192 Millennium Falcon"))


class Annonce(unittest.TestCase):
    def test_xml_complet(self):
        import annonces
        import ebay_compte
        avant = ebay_compte.trading
        ebay_compte.trading = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("hors ligne"))
        try:
            c = {"joueur": "Will Smith", "annee": "2023-24", "marque": "Upper Deck", "set_nom": "Series 1", "parallele": "Young Guns",
                 "numero": "230", "recrue": 1, "equipe": "San Jose Sharks", "sport": "hockey"}
            t = annonces.titre_optimise(c)
            self.assertLessEqual(len(t), 80)
            self.assertIn("Will Smith", t)
            d = {**annonces.MODELE_DEFAUT, "carte": c, "titre": t, "prix": 40, "description": annonces.description(c, t, True),
                 "expedition": "suivi", "retours": "30_acheteur", "offres": True, "promotion": 5}
            x = annonces.xml_item(d, ["https://i.ebayimg.com/x.jpg"])
            ET.fromstring(x)
            for morceau in ("BestOfferEnabled", "Days_30", "<ShippingPackageDetails>", "Rookie", "FixedPriceItem", "400010"):
                self.assertIn(morceau, x)
            self.assertIn("Chinese", annonces.xml_item({**d, "format": "encan"}, []))
        finally:
            ebay_compte.trading = avant


class Forfaits(unittest.TestCase):
    def test_local_toujours_pro(self):
        import forfaits
        self.assertTrue(forfaits.est_pro())
        forfaits.verifier("valeur_jour")            # ne leve jamais en local


class Deals(unittest.TestCase):
    def test_chasse(self):
        import deals
        maint = datetime.now(timezone.utc)

        def rech(q, categorie=None, limite=50, fond=True, encheres=False, **k):
            return [{"item_id": f"{i}{int(encheres)}", "titre": f"2025-26 Upper Deck {q} #201 RC", "prix_cad": 9.0 if i == 0 else 25.0 + i,
                     "port_cad": 1, "url": "u", "photo": None, "encan": encheres,
                     "fin": (maint + timedelta(hours=2)).isoformat().replace("+00:00", "Z") if encheres else None} for i in range(6)]
        r = deals.chasser(2, rech)
        self.assertTrue(r["ok"])
        d = deals.lire()["deals"]
        self.assertTrue(d and all(x["ratio"] <= deals.RATIO_DEAL for x in d))
        self.assertTrue(any(x["encan"] for x in d))


class AnalyseBreak(unittest.TestCase):
    def test_chances_et_prix(self):
        import catalogue
        import lockerroom
        pid = catalogue.liste()[0]["id"]
        a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "b.db"))
        r = a.analyse_break({"produit_id": pid, "boites": 12, "cout_boite": 150, "prix_demandes": {}})
        self.assertTrue(r["ok"])
        self.assertTrue(all(0 <= p["p_recrue"] <= 1 for p in r["places"]))
        self.assertGreater(r["total"], 0)
        self.assertTrue(r["joueurs"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
