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

    def test_valeur_de_la_meme_carte(self):
        """26 oct 2026 : un Purple Shock a 1 $ ne « vaut » pas 70 $ parce que les autos de la recherche se vendent 70 $."""
        import deals
        v = [{"titre": "2024 Donruss Optic Rated Rookie Bucky Irving #216 Purple Shock", "prix": p, "le": "2026-10-2" + str(i)}
             for i, p in enumerate([1, 1, 2, 3, 1])]
        v += [{"titre": "2024 Donruss Optic Rated Rookie Bucky Irving #216 Auto /25", "prix": 70, "le": "2026-10-20"}] * 6
        r = deals.valeur_annonce({"titre": "2024 Panini Donruss Optic - Rated Rookie Bucky Irving #216 Purple Shock", "item_id": "x"}, v, [])
        self.assertLessEqual(r[0], 3)
        self.assertEqual(r[1], "vendues")
        self.assertIsNone(deals.valeur_annonce({"titre": "2024 Donruss Optic Rated Rookie Bucky Irving #216 Holo", "item_id": "y"}, v, []))
        self.assertFalse(deals.valide({"item_id": "z", "titre": "t"}))       # deal d'avant la correction : retire


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
        self.assertTrue(r["hits"]["joueurs"])
        self.assertGreater(r["total"] * (1 - r["decote"] / 100), 0)


class NouveauxProduits(unittest.TestCase):
    def test_reperer_et_demander(self):
        import nouveaux_produits as n
        self.assertEqual(n.nom_produit("Upper Deck 2025-26 Series 2 Hockey Hobby Box Factory Sealed", "hockey")[0], "2025-26 Upper Deck Series 2")
        self.assertEqual(n.nom_produit("2025 Panini Prizm Football Hobby Box FOTL", "football")[0], "2025 Panini Prizm Football")
        titres = {"hockey": ["PRESALE 2026-27 SP Authentic Hockey Hobby Box"] * 3 + ["2026-27 Upper Deck Series 1 Hobby Box"] * 3}

        def rech(q, **k):
            return [{"titre": t, "prix_cad": 300} for t in titres.get(q.split()[1], [])]
        n.detecter(rech, datetime(2026, 10, 24))
        noms = [x["nom"] for x in n.liste()]
        self.assertIn("2026-27 SP Authentic", noms)
        self.assertNotIn("2026-27 Upper Deck Series 1", noms)          # deja au catalogue
        n.demander("2026-27 Upper Deck Trilogy", "hockey", "a")
        n.demander("2026-27 Upper Deck Trilogy", "hockey", "b")
        self.assertEqual(n.liste()[0]["demandes"], 2)


class DemandesAdmin(unittest.TestCase):
    def test_demande_agent_reponse(self):
        import demandes
        r = demandes.envoyer("probleme", "La recherche Will Smith Young Guns montre des PSA", "c1", "bob", "fr", "valeur", agent=False)
        self.assertTrue(r["ok"])
        faux = lambda corps: {"content": [{"type": "tool_use", "input": {"categorie": "bug", "priorite": 2, "resume": "Recherche : gradées mélangées",
                                                                          "reponse_proposee": "Merci Bob !", "a_faire": "Filtrer les gradées"}}]}
        ia = demandes.trier(r["id"], appeler=faux)
        self.assertEqual(ia["categorie"], "bug")
        self.assertIn("Filtrer les gradées", demandes.brief())
        demandes.repondre(r["id"], "C'est réglé, merci !")
        self.assertEqual(demandes.mes_reponses("c1")[0]["reponse"], "C'est réglé, merci !")
        demandes.marquer_lu("c1", r["id"])
        self.assertEqual(demandes.mes_reponses("c1"), [])

    def test_sante_et_catalogue(self):
        import admin
        admin.noter_erreur("test", ValueError("x"))
        s = admin.sante()
        self.assertTrue(s["erreurs"] and "ebay" in s)
        self.assertTrue(admin.catalogue_etat()["produits"])


class ChecklistGTS(unittest.TestCase):
    """25 oct 2026 - l'Excel de GTS Distribution (gogts.net) : colonnes, recrues, numerotation, cotes hobby."""
    def test_format_gts(self):
        import io
        import openpyxl
        import checklist_import as ci
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Checklist"
        ws.append(["Set Name", "Card", "Description", "Team City", "Team Name", "Rookie", "Auto", "Tech", "Serial #'d", "SPs", "Stated Odds", "Point"])
        for i in range(1, 6):
            ws.append(["Base Set", str(i), f"Joueur {i}", "New York", "Rangers", None, None, None, None, None, None, 20])
        for i in range(201, 206):
            ws.append(["Base Set - Young Guns ", str(i), f"Recrue {i}", "Boston", "Bruins", "Rookie", None, None, None, None, "1:2 h, 1:2 e, 1:1 hanger", 20])
        for i in range(201, 206):
            ws.append(["Deluxe Parallel - Young Guns", str(i), f"Recrue {i}", "Boston", "Bruins", "Rookie", None, None, 250, None, "Random Inserts in Hobby and e-Pack", 20])
        ws.append(["Snow Spray Auto Variations", "10", "Joueur 1", "New York", "Rangers", None, "Auto", None, None, "SSP", "1:5570 h", 20])
        b = io.BytesIO()
        wb.save(b)
        lu = ci.lire(b.getvalue(), "2026-27-Upper-Deck-Series-1-Hockey-Checklist.xlsx", "hockey")
        se = {s["nom"]: s for s in lu["sous_ensembles"]}
        self.assertEqual(lu["cartes"][0]["equipe"], "NYR")
        self.assertTrue(all(c["recrue"] for c in lu["cartes"] if c["sous_ensemble"].endswith("Young Guns")))
        self.assertEqual(se["Deluxe Parallel - Young Guns"]["tirage"], 250)
        self.assertEqual(se["Deluxe Parallel - Young Guns"]["parallele_de"], "Base Set - Young Guns")
        self.assertEqual(se["Deluxe Parallel - Young Guns"]["groupe"], "recrue")
        self.assertEqual(se["Base Set - Young Guns"]["cote_hobby"], 2.0)
        self.assertEqual(se["Snow Spray Auto Variations"]["groupe"], "auto")
        prod = {"formats": [{"format": "Boîte hobby", "paquets": 12}], "sous_ensembles": lu["sous_ensembles"]}
        ci.par_boite_depuis_cotes(prod)
        self.assertEqual(se["Base Set - Young Guns"]["par_boite"], 6.0)          # 6 Young Guns par boite
        self.assertEqual(ci.cle_sous("Deluxe Parallel - Young Guns"), ci.cle_sous("Young Guns Deluxe"))
        self.assertEqual(ci.cle_sous("Population Count 500 Parallel"), ci.cle_sous("Population Count /500"))
        self.assertEqual(ci.cle_sous("Bootlegs"), ci.cle_sous("Bootleg"))
        self.assertEqual(ci.cle_sous("Base Set"), ci.cle_sous("Base"))


class GTS(unittest.TestCase):
    """25 oct 2026 - la liste des checklists de gogts.net et le telechargement (reseau simule)."""
    def test_liste_et_lien(self):
        import gts
        pages = {
            gts.CATEGORIES["hockey"]: '<a href="https://gogts.net/2026-27-upper-deck-series-1-nhl-hockey-cards-checklist/">S1</a>'
                                      '<a href="https://gogts.net/2025-26-upper-deck-sp-authentic-nhl-hockey-checklist/">SPA</a>'
                                      '<a href="https://gogts.net/trading-card-checklists/hockey-card-checklists/">cat</a>',
            gts.CATEGORIES["hockey"] + "page/2/": '<a href="https://gogts.net/2019-20-upper-deck-series-two-nhl-hockey-cards-checklist/">x</a>',
            "https://gogts.net/2026-27-upper-deck-series-1-nhl-hockey-cards-checklist/":
                '<a href="https://gogts.net/wp-content/uploads/2026/04/X.pdf">PDF</a><a href="https://gogts.net/wp-content/uploads/2026/04/2026-27-Upper-Deck-Series-1-Hockey-Checklist.xlsx">EXCEL</a>',
        }
        def faux(url, max_octets=0, timeout=0):
            if url.endswith(".xlsx"):
                return b"PK"
            if url not in pages:
                e = OSError("404"); e.code = 404; raise e
            return pages[url].encode()
        vrai, gts._get = gts._get, faux
        ancien = gts._chemin
        with tempfile.TemporaryDirectory() as t:
            gts._chemin = lambda: os.path.join(t, "g.json")
            try:
                r = gts.lister("hockey", force=True, maint=datetime(2026, 10, 25))
                noms = [x["nom"] for x in r["produits"]]
                self.assertEqual(noms, ["2026-27 Upper Deck Series 1", "2025-26 Upper Deck SP Authentic"])
                brut, nom = gts.telecharger(r["produits"][0]["url"])
                self.assertEqual(nom, "2026-27-Upper-Deck-Series-1-Hockey-Checklist.xlsx")
                self.assertFalse(gts._sur("https://exemple.com/gogts.net/x.xlsx"))
            finally:
                gts._get, gts._chemin = vrai, ancien


class Marche(unittest.TestCase):
    def test_alerte_meme_carte(self):
        import lockerroom
        import marche
        a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "m.db"))
        a.alerte_ajouter("will smith young guns", 30)

        def rech(q, **k):
            return [{"item_id": "1", "titre": "2023-24 Upper Deck Will Smith Young Guns #230", "prix_cad": 20, "port_cad": 2},
                    {"item_id": "2", "titre": "2023-24 Upper Deck Will Smith Young Guns #230 PSA 10", "prix_cad": 20, "port_cad": 2},
                    {"item_id": "3", "titre": "2023-24 Upper Deck Will Smith Young Guns #230", "prix_cad": 40, "port_cad": 2}]
        self.assertEqual(marche.verifier_alertes(a, rech)["nouvelles"], 1)       # gradee et trop chere : non
        self.assertEqual(marche.verifier_alertes(a, rech)["nouvelles"], 0)       # deja vue
        self.assertEqual(a.alertes_liste()["non_lues"], 1)

    def test_tendance_et_ouvrir(self):
        import vendues
        import marche
        from datetime import datetime as dt, timedelta as td
        v = [{"prix": 10, "le": (dt.now() - td(days=50 + i)).strftime("%Y-%m-%d")} for i in range(4)] + \
            [{"prix": 15, "le": (dt.now() - td(days=5 + i)).strftime("%Y-%m-%d")} for i in range(4)]
        self.assertEqual(vendues.tendance(v)["pct"], 50)
        self.assertEqual(marche.verdict_ouvrir(120, 100)["verdict"], "ouvrir")
        self.assertEqual(marche.verdict_ouvrir(60, 100)["verdict"], "garder")


if __name__ == "__main__":
    unittest.main(verbosity=1)
