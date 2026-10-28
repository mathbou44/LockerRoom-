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



import deals as _deals_t  # noqa: E402
_deals_t.VENDEURS_DEFAUT = []          # 29 oct : ces tests comptent les appels des flux, sans les vendeurs suivis

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

    def test_meme_produit_annonce(self):
        """26 oct 2026 : « pas du tout les memes cartes » (National Hockey Card Day vs Tim Hortons, Metal Universe vs Copperheads)."""
        c = cm.cible_titre("2025-26 Skybox Metal Universe - Zeev Buium #112 Rookie (RC)")
        self.assertTrue(cm.raisons_refus(c, "SkyBox 2025-26 Metal Universe Hockey Copperheads Zeev Buium"))
        self.assertTrue(cm.raisons_refus(c, "2025-26 Upper Deck Series 2 Zeev Buium Young Guns"))
        self.assertTrue(cm.raisons_refus(c, "2025-26 Parkhurst Penworks Rookies Zeev Buium Minnesota"))
        self.assertFalse(cm.raisons_refus(c, "2025-26 Skybox Metal Universe Zeev Buium RC #112 Minnesota Wild"))
        c = cm.cible_titre("Zeev Buium 2026 National Hockey Card Day Prominent Rookies #NHCD-6 Minnesota Wil")
        self.assertTrue(cm.raisons_refus(c, "2026-27 Tim Hortons Zeev Buium Next Gen Phenoms Vancouver"))
        self.assertFalse(cm.raisons_refus(c, "2026 National Hockey Card Day Zeev Buium Prominent Rookies NHCD-6"))
        c = cm.cible_titre("2025-26 Upper Deck Series 1 Young Guns #224 Quinn Hutson RC Oilers")
        self.assertFalse(cm.raisons_refus(c, "Quinn Hutson 2025 Upper Deck YG Rookie #224 Invest"))

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
        import vendues
        vrai, vrai_c = vendues.rechercher, vendues.en_cache
        ventes = lambda q: [{"titre": f"2025-26 Upper Deck {q} #201 RC", "prix": p, "le": "2026-10-20"} for p in (24, 26, 25, 27)]
        vendues.rechercher = lambda q, fond=True, **k: {"ventes": ventes(q), "erreur": None}
        vendues.en_cache = ventes
        try:
            r = deals.chasser(2, rech)
            e = deals.encans(2, rech)
        finally:
            vendues.rechercher, vendues.en_cache = vrai, vrai_c
        self.assertTrue(r["ok"] and e["ok"])
        d = deals.lire()["deals"]
        self.assertTrue(d and all(x["ratio"] <= deals.RATIO_DEAL for x in d))
        self.assertTrue(any(x["encan"] for x in d))
        dg = deals.diagnostic()                      # 26 oct 2026 : ce qui a ete verifie (preuve)
        self.assertGreaterEqual(dg.get("requetes_encans", 0), 1)
        self.assertGreaterEqual(dg.get("encans_fen", 0), 1)
        self.assertGreaterEqual(dg.get("trop_cher", 0), 1)

    def test_flux_bassin_verif(self):
        """26 oct 2026 (« trouver le maximum ») : flux larges, valeur tiree de TOUTES les ventes connues, verification ciblee."""
        import deals
        import vendues
        maint = datetime.now(timezone.utc)
        T = "2024-25 Upper Deck Young Guns Lane Hutson #493 RC"
        T2 = "2024-25 Upper Deck Young Guns Canvas Ivan Demidov #C250 RC"

        def rech(q, categorie=None, limite=50, fond=True, encheres=False, **k):
            if encheres:
                return [{"item_id": "e1", "titre": T, "prix_cad": 20.0, "port_cad": 2, "encan": True, "url": "u",
                         "fin": (maint + timedelta(hours=1)).isoformat().replace("+00:00", "Z")}]
            return [{"item_id": "f1", "titre": T, "prix_cad": 30.0, "port_cad": 2, "url": "u"},          # 32 > 70 % de 40 : non
                    {"item_id": "f2", "titre": T, "prix_cad": 12.0, "port_cad": 2, "url": "u"},          # deal (bassin)
                    {"item_id": "f3", "titre": T2, "prix_cad": 8.0, "port_cad": 2, "url": "u"},          # deal apres verification
                    {"item_id": "f4", "titre": "Lot of 5 2024-25 Upper Deck Young Guns", "prix_cad": 5.0, "url": "u"}]
        b = deals.Bassin(charger=False)
        b.ajouter([{"titre": T, "prix": p, "le": "2026-10-2" + str(i), "url": "v" + str(i)} for i, p in enumerate((38, 40, 42, 41))])
        b.ajouter([{"titre": T2, "prix": 60, "le": "2026-10-20", "url": "w0"}])               # une seule vente : a verifier
        appels = []

        def rech_v(q, fond=True, **k):
            appels.append(q)
            return {"ventes": [{"titre": T2, "prix": p, "le": "2026-10-2" + str(i), "url": "w" + str(i)} for i, p in enumerate((60, 55, 65))],
                    "erreur": None}
        vrai = vendues.rechercher
        vendues.rechercher = rech_v
        avant, avant_h = deals.FLUX, deals.FLUX_HITS
        deals.FLUX, deals.FLUX_HITS = [("young guns", "hockey")], []
        try:
            r = deals.flux(rech, bassin=b)
        finally:
            vendues.rechercher, deals.FLUX, deals.FLUX_HITS = vrai, avant, avant_h
        ids = {x["item_id"] for x in deals.lire()["deals"]}
        self.assertTrue({"f2", "f3", "e1"} <= ids, ids)
        self.assertFalse({"f1", "f4"} & ids)
        self.assertEqual(len(appels), 1)                         # une seule verification (Demidov Canvas)
        self.assertEqual(r["stats"].get("requetes_flux"), 2)          # 1 prix fixe + 1 page d'encans (derniere page)
        import deals as D
        self.assertEqual(D.ENCAN_H, 48)                               # 26 oct 2026 : encans de 48 h et moins

    def test_hits_autres_produits(self):
        """27 oct 2026 (Mathieu : « pourquoi c'est juste des Young Guns ? ») : un encan de hit d'un autre produit, sans
        aucune vente connue (Pride of a Nation Stutzle /99 a 101 $, qui finit dans 2 h), est verifie et devient un deal ;
        les flux de hits tournent (5 par tour)."""
        import deals
        import vendues
        maint = datetime.now(timezone.utc)
        T = "2025 SPx 2023-24 Update UD Black Pride of a Nation 34/99 Tim Stutzle Patch Auto"
        fin = lambda h: (maint + timedelta(hours=h)).isoformat().replace("+00:00", "Z")

        def rech(q, categorie=None, limite=50, fond=True, encheres=False, **k):
            if not encheres:
                return []
            return [{"item_id": "s1", "titre": T, "prix_cad": 78.42, "port_cad": 23.03, "encan": True, "url": "u", "fin": fin(2)},
                    {"item_id": "s2", "titre": T.replace("34/99", "12/99"), "prix_cad": 30.0, "port_cad": 2, "encan": True,
                     "url": "u", "fin": fin(30)},                                   # finit dans 30 h : pas de verification
                    {"item_id": "s3", "titre": "2023-24 Upper Deck Tim Stutzle #120", "prix_cad": 5.0, "port_cad": 2,
                     "encan": True, "url": "u", "fin": fin(1)},                     # base a 7 $ : pas un hit, rien
                    {"item_id": "s4", "titre": "MATT SAVOIE 2022-23 UD SP GAME USED ROOKIE DRAFT DAY MARKS PATCH AUTO /35",
                     "prix_cad": 49.75, "port_cad": 6.0, "encan": True, "url": "u", "fin": fin(25)},   # verifie en fin de tour
                    {"item_id": "s5", "titre": "2022-23 SP Game Used Draft Day Marks Wyatt Johnston Patch Auto /35",
                     "prix_cad": 40.0, "port_cad": 6.0, "encan": True, "url": "u", "fin": fin(40)}]    # 40 h : trop loin
        appels = []

        def rech_v(q, fond=True, **k):
            appels.append(q)
            if "savoie" in q:
                return {"ventes": [{"titre": "2022-23 SP Game Used Draft Day Marks Matt Savoie Patch Auto %d/35" % n, "prix": p,
                                    "le": "2026-07-1" + str(i), "url": "x" + str(i)}
                                   for i, (n, p) in enumerate(((3, 174.5), (27, 84.08), (13, 87.09), (8, 118.24), (11, 84.08), (4, 56.05)))],
                        "erreur": None}
            return {"ventes": [{"titre": "2025-26 SPx Update UD Black Pride of a Nation Patch Auto %d/99 Tim Stutzle" % n, "prix": p,
                                "le": "2026-10-1" + str(i), "url": "w" + str(i)}
                               for i, (n, p) in enumerate(((48, 143.82), (66, 241.72), (3, 177.50), (9, 145.03), (7, 135.31)))],
                    "erreur": None}
        vrai = vendues.rechercher
        vendues.rechercher = rech_v
        avant, avant_h = deals.FLUX, deals.FLUX_HITS
        deals.FLUX, deals.FLUX_HITS = [], [("ud black auto", "hockey")] + [("h%d" % i, "hockey") for i in range(6)]
        try:
            d0 = deals.lire().get("curseur_h")
            r = deals.flux(rech, bassin=deals.Bassin(charger=False))
            d1 = deals.lire().get("curseur_h")
        finally:
            vendues.rechercher, deals.FLUX, deals.FLUX_HITS = vrai, avant, avant_h
        ids = {x["item_id"]: x for x in deals.lire()["deals"]}
        self.assertIn("s1", ids)
        self.assertGreater(ids["s1"]["valeur"], 140)
        self.assertNotIn("s3", ids)
        self.assertEqual(len(appels), 2)                          # s1 (finit dans 2 h), puis s4 en fin de tour
        self.assertIn("s4", ids)                                  # Savoie : 55,75 $ pour ~86 $
        self.assertAlmostEqual(ids["s4"]["mise_max"], round(ids["s4"]["valeur"] * deals.RATIO_DEAL - 6.0, 2))
        self.assertNotIn("s5", ids)
        n = min(deals.HITS_PAR_TOUR, 7)
        self.assertEqual((int(d0 or 0) + deals.HITS_PAR_TOUR) % 7, d1)   # HITS_PAR_TOUR flux de hits par tour, en rotation
        self.assertEqual(r["stats"].get("requetes_flux"), 2 * n)   # n flux x (prix fixe + 1 page d'encans)

    def test_autres_joueurs(self):
        """27 oct 2026 : la meme carte vendue par d'autres joueurs (repere), sans le meme joueur ni une autre carte."""
        import vendues
        T = "COLTON PARAYKO 2025-26 UD SP GAME USED PURPLE PREMIUM PATCH AUTO /15 Q1303"
        V = [("2025-26 SP Game Used Edition Purple Premium Patch Auto 11/15 Jaccob Slavin", 72.87),
             ("2025-26 SP Game Used Purple Auto Premium Patch Troy Terry /15 #124 Anaheim Ducks", 41.0),
             ("2022 Immaculate College Premium Purple Chris Olave /15 ROOKIE PATCH AUTO RC RPA", 115.68),   # autre carte
             ("2025-26 SP Game Used Colton Parayko Gold Patch Auto /25", 30.0)]                             # le meme joueur
        vrai = vendues.rechercher
        vendues.rechercher = lambda q, fond=False, **k: {"ventes": [{"titre": t, "prix": p, "le": "2026-10-0%d" % i} for i, (t, p) in enumerate(V)]}
        try:
            r = vendues.autres_joueurs(T)
        finally:
            vendues.rechercher = vrai
        self.assertEqual(sorted(v["joueur"] for v in r["ventes"]), ["Jaccob Slavin", "Troy Terry"])
        self.assertEqual((r["min"], r["max"]), (41.0, 72.87))

    def test_valeur_de_la_meme_carte(self):
        """26 oct 2026 : un Purple Shock a 1 $ ne « vaut » pas 70 $ parce que les autos de la recherche se vendent 70 $."""
        import deals
        v = [{"titre": "2024 Donruss Optic Rated Rookie Bucky Irving #216 Purple Shock", "prix": p, "le": "2026-10-2" + str(i)}
             for i, p in enumerate([1, 1, 2, 3, 1])]
        v += [{"titre": "2024 Donruss Optic Rated Rookie Bucky Irving #216 Auto /25", "prix": 70, "le": "2026-10-20"}] * 6
        r = deals.valeur_annonce({"titre": "2024 Panini Donruss Optic - Rated Rookie Bucky Irving #216 Purple Shock", "item_id": "x"}, v, [])
        # une seule vente (3 $) et des annonces a 21 $ : pas de valeur de deal (Red Prism /199, 26 oct 2026)
        une = [{"titre": "2025-26 O-Pee-Chee Platinum Red Prism Michael Callahan Marquee Rookie /199", "prix": 3, "le": "2026-10-01"}]
        ann = [{"item_id": str(i), "titre": "2025-26 O-Pee-Chee Platinum Red Prism Michael Callahan Marquee Rookie /199", "prix_cad": 21}
               for i in range(6)]
        self.assertIsNone(deals.valeur_annonce({"titre": une[0]["titre"], "item_id": "z"}, une, ann))
        deux = une + [{**une[0], "prix": 4}]
        self.assertLessEqual(deals.valeur_annonce({"titre": une[0]["titre"], "item_id": "z"}, deux, ann)[0], 4)
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


class Astuces(unittest.TestCase):
    """26 oct 2026 - « Le savais-tu ? » : les astuces sourcees sont toujours la ; les calculees ne parlent que s'il y a
    assez de donnees (jamais de chiffre invente)."""
    def test_astuces(self):
        import astuces
        import comptes
        import lockerroom
        with tempfile.TemporaryDirectory() as t:
            ancien = comptes.DONNEES
            comptes.DONNEES = t
            try:
                api = lockerroom.Api(os.path.join(t, "a.db"))
                fr = astuces.liste(api, "debutant", True, "fr")
                en = astuces.liste(api, None, True, "en")
            finally:
                comptes.DONNEES = ancien
        ids = {x["id"] for x in fr}
        self.assertTrue({"bedard", "numerotation", "gradation", "demande", "frais"} <= ids)
        self.assertNotIn("offres", ids)                       # base vide : pas de chiffre
        self.assertNotIn("psa10", ids)
        self.assertTrue(all(x["titre"] and x["truc"] and x["source"] for x in fr))
        self.assertIn("Did you know", "Did you know") and self.assertTrue(any("Bedard" in x["titre"] for x in en))
        self.assertEqual(fr[0]["niveau"], "debutant")
        self.assertTrue(any(x.get("url", "").startswith("https://") for x in fr))


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



class ChancesHits(unittest.TestCase):
    """26 oct 2026 : les memes categories de hit pour chaque joueur / equipe, et ses ventes reelles avec la meme regle."""

    def test_categories_carte(self):
        import calcul
        s_ap = {"nom": "Auto Patch", "groupe": "auto_memo", "tirage": 25}
        self.assertEqual(calcul.categories_carte({}, s_ap), {"numerotee", "auto", "patch", "auto_patch"})
        self.assertEqual(calcul.categories_carte({"sp": "SSP"}, {"nom": "Base", "groupe": "base"}), {"ssp"})
        self.assertEqual(calcul.categories_carte({}, {"nom": "Young Guns", "groupe": "recrue"}), set())
        ch = calcul._chances({"auto": [0.1, 5.0, 5.0], "hit": [0.1, 5.0, 5.0]})
        self.assertAlmostEqual(ch["auto"]["p"], 0.095163, places=5)
        self.assertEqual(ch["auto"]["valeur"], 50.0)
        self.assertEqual(ch["ssp"]["p"], 0)

    def test_ventes_joueur(self):
        import ventes_joueur as V
        prod = {"nom": "2026-27 Upper Deck Series 1", "saison": "2026-27", "marque": "Upper Deck",
                "sous_ensembles": [{"nom": "Young Guns"}, {"nom": "Young Guns Exclusives"}]}
        self.assertFalse(V.de_ce_produit(prod, "Macklin Celebrini", "2026-27 Upper Deck MVP Celebrini Rookie"))
        self.assertFalse(V.de_ce_produit(prod, "Macklin Celebrini", "2025-26 Upper Deck Series 1 Celebrini Young Guns"))
        self.assertTrue(V.de_ce_produit(prod, "Macklin Celebrini", "2026-27 UD Young Guns Celebrini #201"))
        self.assertEqual(V.categories_titre("2026-27 Upper Deck Series 1 Celebrini Auto Patch 3/25"), {"numerotee", "auto", "patch", "auto_patch"})
        self.assertEqual(V.categories_titre("2026-27 Upper Deck Series 1 Celebrini Young Guns"), set())

        def rech(q, fond=False):
            return {"ventes": [{"titre": "2026-27 Upper Deck Series 1 Young Guns Macklin Celebrini #201", "prix": 100, "le": "2026-10-20"},
                               {"titre": "2026-27 Upper Deck Series 1 Celebrini Young Guns Exclusives 12/100", "prix": 300, "le": "2026-10-21"},
                               {"titre": "2026-27 Upper Deck Series 1 Celebrini Young Guns PSA 10", "prix": 900, "le": "2026-10-21"}]}
        r = V.ventes(prod, "Macklin Celebrini", rechercher=rech)
        self.assertEqual((r["n"], r["gradees"]), (2, 1))
        self.assertEqual(r["par_cat"]["numerotee"]["moyenne"], 300.0)
        self.assertEqual(r["autres"]["moyenne"], 100.0)


if __name__ == "__main__":
    unittest.main(verbosity=1)
