"""Tests SlabCoach : python tests/test_calcul.py (depuis le dossier de l'app)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import calcul  # noqa: E402
import ebay_csv  # noqa: E402
import lockerroom  # noqa: E402

ICI = os.path.dirname(os.path.abspath(__file__))


class Calcul(unittest.TestCase):
    def test_code_equipe(self):
        self.assertEqual(calcul.code_equipe("Montréal Canadiens"), "MTL")
        self.assertEqual(calcul.code_equipe("Canadiens"), "MTL")
        self.assertEqual(calcul.code_equipe("tor"), "TOR")
        self.assertEqual(calcul.code_equipe("Utah Hockey Club"), "UTA")
        self.assertEqual(calcul.division("EDM"), "Pacifique")

    def test_prix_couvrent_cout_marge_frais(self):
        ck = [{"joueur": "A", "equipe": "MTL", "categorie": "Young Guns", "recrue": 1},
              {"joueur": "B", "equipe": "TOR", "categorie": "Base"}]
        r = calcul.prix_places(ck, boites=2, cout_boite=100, marge=0.25, frais_pct=0.10, frais_fixe=0.30)
        self.assertEqual(len(r["places"]), 32)                 # les 32 equipes
        self.assertGreaterEqual(r["total"], r["cible"] - 0.01)  # arrondi vers le haut
        self.assertGreaterEqual(r["profit_estime"], 0.25 * 200 - 0.5)
        self.assertEqual(r["places"][0]["cle"], "MTL")          # la recrue vaut plus

    def test_carte_deux_equipes_partagee(self):
        ck = [{"joueur": "A / B", "equipe": "MTL/TOR", "categorie": "Base"}]
        r = calcul.prix_places(ck, mode="equipes", cout_boite=50, plancher=0)
        p = {x["cle"]: x for x in r["places"]}
        self.assertEqual(p["MTL"]["part"], p["TOR"]["part"])

    def test_tirage_reproductible(self):
        t = calcul.tirage([1, 2, 3], list(calcul.EQUIPES_LNH), "graine-test")
        t2 = calcul.tirage([1, 2, 3], list(calcul.EQUIPES_LNH), "graine-test")
        self.assertEqual(t["resultat"], t2["resultat"])
        import hashlib
        self.assertEqual(t["empreinte"], hashlib.sha256(b"graine-test").hexdigest())

    def test_profit_vente_ebay(self):
        r = calcul.profit_vente(100, cout=50, port_paye=2, port_charge=5, frais_pct=0.1325, frais_fixe=0.40)
        self.assertAlmostEqual(r["frais"], 14.31, places=2)
        self.assertAlmostEqual(r["profit"], 100 + 5 - 14.31 - 2 - 50, places=2)

    def test_offre_rachat(self):
        r = calcul.offre_rachat([5, 100, 10 ** 7], bonus_credit=0.10)
        self.assertEqual([x["pct"] for x in r["lignes"]], [0.30, 0.60, 0.70])
        self.assertAlmostEqual(r["credit"], r["comptant"] * 1.10, places=1)

    def test_dates_ebay(self):
        self.assertEqual(ebay_csv.date_iso("Oct-15-26 21:00:01 PDT"), "2026-10-15")
        self.assertEqual(ebay_csv.date_iso("Oct 5, 2026"), "2026-10-05")


class Catalogue(unittest.TestCase):
    def test_produits_et_taux(self):
        import catalogue
        l = catalogue.liste()
        self.assertGreaterEqual(len(l), 1)
        for p in l:
            prod = catalogue.charger(p["id"])
            self.assertTrue(prod["cartes"])
            self.assertTrue(all(v >= 0 for v in prod["_taux"].values()))

    def test_groupe_reparti(self):
        import catalogue
        prod = {"sous_ensembles": [{"nom": "A", "nb_cartes": 10, "tirage": 100}, {"nom": "B", "nb_cartes": 10, "tirage": 10},
                                   {"nom": "C", "par_boite": 0.5}],
                "groupes_boite": [{"libelle": "A, B ou C", "par_boite": 1.6, "sous_ensembles": ["A", "B", "C"]}],
                "_par_se": {"A": [{}] * 10, "B": [{}] * 10}}
        t = catalogue.taux_par_boite(prod)
        self.assertAlmostEqual(t["A"] + t["B"], 1.1)
        self.assertAlmostEqual(t["A"] / t["B"], 10.0)

    def test_prix_catalogue(self):
        import catalogue
        l = catalogue.liste()
        prod = catalogue.charger(l[0]["id"])
        r = calcul.prix_catalogue(prod, boites=12, cout_boite=150)
        self.assertEqual(len(r["places"]), 32)
        self.assertGreater(r["ev_total"], 0)
        self.assertGreaterEqual(r["total"], r["cible"] - 0.01)
        self.assertAlmostEqual(sum(p["part"] for p in r["places"]), 100, delta=1)

    def test_api_catalogue(self):
        a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "c.db"))
        l = a.catalogue_liste()["produits"]
        r = a.calculer_catalogue({"produit_id": l[0]["id"], "boites": 6, "cout_boite": 120})
        self.assertTrue(r["ok"])
        b = a.break_creer({"nom": "C", "catalogue_id": l[0]["id"], "mode": "equipes", "cout": r["cout"],
                           "places": [{"cle": p["cle"], "libelle": p["nom"], "prix": p["prix"]} for p in r["places"]]})
        pub = a.break_public(b["jeton"])
        self.assertEqual(pub["produit"]["nom"], l[0]["nom"])
        self.assertTrue(pub["resume_equipes"])
        self.assertTrue(a.catalogue_checklist(l[0]["id"]))


class CompteEbay(unittest.TestCase):
    def setUp(self):
        import ebay_compte
        self.e = ebay_compte
        d = tempfile.mkdtemp()
        self.anciens = (ebay_compte.CHEMIN_CLES, ebay_compte.CHEMIN_JETONS, ebay_compte.CHEMIN_ENV)
        ebay_compte.CHEMIN_CLES, ebay_compte.CHEMIN_JETONS = os.path.join(d, "c.json"), os.path.join(d, "j.json")
        ebay_compte.CHEMIN_ENV = os.path.join(d, "env.json")   # n'utilise jamais le vrai choix sandbox/production

    def tearDown(self):
        self.e.CHEMIN_CLES, self.e.CHEMIN_JETONS, self.e.CHEMIN_ENV = self.anciens

    def test_cles_masquees(self):
        s = self.e.sauver_cles("MonApp-PRD-123456789", "PRD-secret-abcdef123456", "Mon-RuName-xyz98765")
        self.assertTrue(s["cles_ok"])
        self.assertNotIn("secret", json_dump(s))
        self.assertTrue(s["cles"]["cert_id"].endswith("3456"))
        self.e.sauver_cles("", "•••• 3456", "")              # champs vides ou masques : rien ne change
        self.assertTrue(self.e.statut()["cles_ok"])

    def test_url_et_code(self):
        self.e.sauver_cles("app", "cert", "ru")
        u = self.e.url_connexion()["url"]
        self.assertIn("auth.ebay.com/oauth2/authorize", u)
        self.assertIn("sell.fulfillment.readonly", u)
        code, etat = self.e.code_depuis("http://localhost:8430/api/ebay_retour?state=abc&code=v%5E1.1%23i%5E1&expires_in=299")
        self.assertEqual((code, etat), ("v^1.1#i^1", "abc"))

    def test_terminer_et_refus_etat(self):
        self.e.sauver_cles("app", "cert", "ru")
        self.e.url_connexion()
        self.assertFalse(self.e.terminer_connexion("x?code=abc&state=mauvais")["ok"])
        appels = []
        vrai = self.e._post_jeton
        self.e._post_jeton = lambda data: (appels.append(data) or ({"access_token": "A", "expires_in": 7200, "refresh_token": "R",
                                                                   "refresh_token_expires_in": 47304000}, None))
        try:
            etat = json_lire(self.e.CHEMIN_JETONS)["etat_attendu"]
            r = self.e.terminer_connexion(f"x?code=abc&state={etat}")
        finally:
            self.e._post_jeton = vrai
        self.assertTrue(r["ok"] and r["connecte"])
        self.assertEqual(appels[0]["grant_type"], "authorization_code")
        self.assertEqual(self.e.jeton(), "A")
        self.assertFalse(self.e.deconnecter()["connecte"])

    def test_lectures(self):
        xml = (b'<?xml version="1.0"?><GetMyeBaySellingResponse xmlns="urn:ebay:apis:eBLBaseComponents"><Ack>Success</Ack>'
               b'<ActiveList><ItemArray><Item><ItemID>1234</ItemID><Title>2025-26 YG Demidov</Title><SKU>LR-1</SKU>'
               b'<SellingStatus><CurrentPrice currencyID="CAD">49.99</CurrentPrice></SellingStatus></Item></ItemArray>'
               b'<PaginationResult><TotalNumberOfPages>1</TotalNumberOfPages></PaginationResult></ActiveList></GetMyeBaySellingResponse>')
        a, pages = self.e.lire_annonces_xml(xml)
        self.assertEqual((a[0]["item_number"], a[0]["prix"], pages), ("1234", 49.99, 1))
        v = self.e.lire_commandes({"orders": [{"orderId": "O1", "creationDate": "2026-10-15T12:00:00Z", "buyer": {"username": "bob"},
                                               "totalMarketplaceFee": {"value": "6.70"},
                                               "lineItems": [{"lineItemId": "L1", "legacyItemId": "1234", "title": "YG", "lineItemCost": {"value": "40"},
                                                              "deliveryCost": {"shippingCost": {"value": "5"}}},
                                                             {"lineItemId": "L2", "legacyItemId": "99", "title": "B", "lineItemCost": {"value": "10"}}]}]})
        self.assertEqual(len(v), 2)
        self.assertAlmostEqual(v[0]["frais_reels"] + v[1]["frais_reels"], 6.70, places=2)
        self.assertEqual(v[0]["transaction_id"], "api:O1:L1")

    def test_synchro_api(self):
        a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "s.db"))
        cid = a.carte_sauver({"joueur": "Demidov", "cout": 20, "item_number": "1234"})["id"]
        vrais = (self.e.annonces_actives, self.e.commandes)
        self.e.annonces_actives = lambda: [{"item_number": "1234", "titre": "YG Demidov", "sku": "", "prix": 49.99},
                                           {"item_number": "555", "titre": "Autre", "sku": "", "prix": 9.99}]
        self.e.commandes = lambda jours=90: [{"transaction_id": "api:O1:L1", "item_number": "1234", "titre": "YG", "prix": 40.0,
                                              "port_charge": 5.0, "frais_reels": 6.0, "date": "2026-10-15"}]
        try:
            r = a.ebay_synchroniser()
            r2 = a.ebay_synchroniser()
        finally:
            self.e.annonces_actives, self.e.commandes = vrais
        self.assertEqual((r["annonces"], r["ventes"], r2["ventes"]), (2, 1, 0))
        c = next(x for x in a.inventaire_liste({"statut": "Vendue"}) if x["id"] == cid)
        self.assertAlmostEqual(c["profit"], 40 + 5 - 6 - 20)


def json_dump(x):
    import json
    return json.dumps(x)


def json_lire(chemin):
    import json
    with open(chemin) as f:
        return json.load(f)


class Sante(unittest.TestCase):
    def test_requete(self):
        import sante
        self.assertEqual(sante.requete("LEGO Star Wars 75192 Millennium Falcon UCS NEW Sealed 🔥 Free Shipping"),
                         "LEGO Star Wars 75192 Millennium Falcon UCS")
        self.assertIn("/99", sante.requete("2025-26 Upper Deck Clear Cut Demidov 12/99 Auto"))

    def test_verdicts(self):
        import sante
        marche = [{"prix_cad": p} for p in (40, 42, 45, 39, 41, 44)]
        self.assertEqual(sante.evaluer(60, marche)["verdict"], "baisser")
        self.assertEqual(sante.evaluer(60, marche)["suggestion"], 39.99)
        self.assertEqual(sante.evaluer(25, marche)["verdict"], "monter")
        self.assertEqual(sante.evaluer(42, marche, age=90, watchers=0)["verdict"], "traine")
        self.assertEqual(sante.evaluer(42, marche, age=10)["verdict"], "ok")
        self.assertEqual(sante.evaluer(60, marche[:3])["verdict"], "ok")      # trop peu d'annonces pour juger

    def test_parcours_api(self):
        import ebay_compte
        a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "s.db"))
        a._maj_annonces([{"item_number": "1", "titre": "LEGO 75192 Millennium Falcon", "sku": "", "prix": 1200, "debut": "2026-06-01T00:00:00Z", "watchers": 0},
                         {"item_number": "2", "titre": "Vintage Pyrex Bowl Set", "sku": "", "prix": 20, "debut": "2026-10-10T00:00:00Z", "watchers": 3}])
        c = a.carte_sauver({"titre": "Nintendo 64 Console", "prix_demande": 0})["id"]
        a.carte_vendre(c, {"canal": "eBay", "prix": 150})
        vrai = ebay_compte.rechercher

        def faux(q, categorie=None, prix_max=None, recentes=False, limite=50):
            if "Falcon" in q:
                return [{"item_id": str(9 + i), "titre": "x", "prix_cad": p} for i, p in enumerate((900, 950, 980, 1000, 1010))]
            if "Pyrex" in q:
                return [{"item_id": str(20 + i), "titre": "x", "prix_cad": p} for i, p in enumerate((35, 38, 40, 42, 45))]
            if "Nintendo" in q:
                return [{"item_id": "77", "titre": "N64 console", "prix_cad": 80, "url": "u", "photo": ""}]
            return []
        ebay_compte.rechercher = faux
        try:
            r = a.sante_rafraichir(10)
        finally:
            ebay_compte.rechercher = vrai
        self.assertTrue(r["ok"])
        cpt = a.sante_resume()["compte"]
        self.assertEqual((cpt["baisser"], cpt["monter"], cpt["racheter"]), (1, 1, 1))
        b = a.sante_liste("baisser")[0]
        self.assertEqual(b["suggestion"], 959.99)
        a.sante_fait(b["item_number"])
        self.assertEqual(a.sante_resume()["compte"]["baisser"], 0)


class Parcours(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.mkdtemp()
        self.api = lockerroom.Api(os.path.join(self.dossier, "t.db"))

    def test_break_complet(self):
        a = self.api
        pid = a.produit_sauver({"nom": "Test", "cout_boite": 150, "par_boite": {"recrue": 6}})["id"]
        with open(os.path.join(ICI, "exemple_checklist.csv"), encoding="utf-8") as f:
            self.assertGreater(a.checklist_importer(pid, f.read())["nb"], 50)
        r = a.calculer_prix({"produit_id": pid, "boites": 6})
        self.assertTrue(r["ok"])
        b = a.break_creer({"nom": "B", "produit_id": pid, "mode": "equipes", "cout": r["cout"], "frais_pct": 10,
                           "places": [{"cle": p["cle"], "libelle": p["nom"], "prix": p["prix"]} for p in r["places"]]})
        d = a.break_detail(b["id"])
        mtl = next(p for p in d["places"] if p["cle"] == "MTL")
        a.place_maj(mtl["id"], {"acheteur": "Marc"})
        f = a.frappe_ajouter(b["id"], {"joueur": "Ivan Demidov", "equipe": "Montreal Canadiens"})
        self.assertEqual(f["place"]["acheteur"], "Marc")
        env = a.break_envois(b["id"])["acheteurs"]
        self.assertEqual(env[0]["acheteur"], "Marc")
        pub = a.break_public(b["jeton"])
        self.assertNotIn("Marc", str(pub))                    # acheteur masque sur la page publique

    def test_tirage_aleatoire(self):
        a = self.api
        b = a.break_creer({"nom": "R", "mode": "aleatoire", "nb_places": 5, "prix_place": 20})
        for p in a.break_detail(b["id"])["places"]:
            a.place_maj(p["id"], {"acheteur": "x" + str(p["id"])})
        a.break_engager(b["id"])
        self.assertNotIn("graine", str(a.break_public(b["jeton"])["tirage"]).replace("engage", ""))
        self.assertTrue(a.break_tirage(b["id"])["ok"])
        lots = [e for p in a.break_detail(b["id"])["places"] for e in p["lot"].split(",")]
        self.assertEqual(sorted(lots), sorted(calcul.EQUIPES_LNH))   # 32 equipes, aucune en double
        self.assertFalse(a.break_tirage(b["id"])["ok"])               # pas de 2e tirage

    def test_boutique(self):
        a = self.api
        cid = a.carte_sauver({"joueur": "Test", "cout": 10, "prix_demande": 30})["id"]
        k = a.consignataire_sauver({"nom": "K", "pct_boutique": 20})["id"]
        c2 = a.carte_sauver({"joueur": "Consigne", "consignataire_id": k, "prix_demande": 100})["id"]
        v = a.comptoir_vente({"lignes": [{"carte_id": cid, "description": "Test", "prix": 30}, {"carte_id": c2, "description": "C", "prix": 100}]})
        self.assertAlmostEqual(v["taxes"], round(130 * 0.14975, 2))
        self.assertAlmostEqual(a.consignataires_liste()[0]["du"], 80.0)
        b = a.bilan()
        self.assertAlmostEqual(b["canaux"]["Magasin"]["profit"], 20 + 20)
        ventes = ("Item Number,Item Title,Sold For,Shipping And Handling,Sale Date,Transaction ID\n"
                  "1,X,10,0,Oct-15-26,T1\n")
        self.assertEqual(a.importer_ventes_ebay(ventes)["nouvelles"], 1)
        self.assertEqual(a.importer_ventes_ebay(ventes)["deja"], 1)




class EbaySandbox(unittest.TestCase):
    """21 oct 2026 - sandbox / production, ecriture eBay, avis de suppression de compte."""

    def setUp(self):
        import ebay_compte
        self.ec = ebay_compte
        self.dir = tempfile.mkdtemp()
        self._old = (ebay_compte.DOSSIER, ebay_compte.CHEMIN_ENV)
        ebay_compte.DOSSIER = self.dir
        ebay_compte.CHEMIN_ENV = os.path.join(self.dir, "ebay_env.json")

    def tearDown(self):
        self.ec.DOSSIER, self.ec.CHEMIN_ENV = self._old

    def test_environnements_separes(self):
        ec = self.ec
        self.assertEqual(ec.environnement(), "production")
        self.assertTrue(ec.url("jeton").startswith("https://api.ebay.com/"))
        ec.changer_environnement("sandbox")
        self.assertEqual(ec.environnement(), "sandbox")
        self.assertTrue(ec.url("jeton").startswith("https://api.sandbox.ebay.com/"))
        self.assertTrue(ec.url("auth").startswith("https://auth.sandbox.ebay.com/"))
        self.assertTrue(ec.chemin_cles().endswith("ebay_cles_sandbox.json"))
        self.assertNotIn(ec.SCOPE_MISES, ec.scopes_demandes())     # jamais sans permission (sinon eBay refuse tout)
        ec.changer_environnement("production")
        self.assertNotIn(ec.SCOPE_MISES, ec.scopes_demandes())     # production : seulement apres approbation
        self.assertIn(ec.SCOPE_ECRITURE, ec.scopes_demandes())
        with self.assertRaises(ValueError):
            ec.changer_environnement("autre")

    def test_annonce_xml_valide(self):
        import xml.etree.ElementTree as ET
        import ebay_ecriture as E
        c = {"joueur": "Ivan Demidov", "annee": "2024-25", "marque": "Upper Deck", "set_nom": "Series 2",
             "parallele": "Young Guns", "numero": "451", "equipe": "Montreal Canadiens", "grade": "PSA 10"}
        x = E._requete("AddFixedPriceItem", E.xml_annonce(c, 125, ["https://i.ebayimg.com/a.jpg"], sku="LR-7"))
        r = ET.fromstring(x)
        ns = {"e": E.NS}
        self.assertEqual(r.find("e:Item/e:ConditionID", ns).text, "2750")          # gradee
        self.assertEqual(r.find("e:Item/e:StartPrice", ns).text, "125.00")
        self.assertEqual(r.find("e:Item/e:SKU", ns).text, "LR-7")
        self.assertIn("IVAN DEMIDOV", r.find("e:Item/e:Title", ns).text)
        self.assertEqual(E.id_rest("257796099259"), "v1|257796099259|0")
        with self.assertRaises(ValueError):
            E.changer_prix("abc", 10)
        with self.assertRaises(ValueError):
            E.changer_prix("257796099259", 0.10)

    def test_donnees_test_refusees_en_production(self):
        import ebay_ecriture as E
        with self.assertRaises(RuntimeError):
            E.donnees_test(1)
        self.assertGreaterEqual(len(E.cartes_test(20)), 10)

    def test_defi_suppression_compte(self):
        import hashlib
        import ebay_avis
        old = ebay_avis.CHEMIN
        ebay_avis.CHEMIN = os.path.join(self.dir, "ebay_avis.json")
        try:
            c = ebay_avis.reglage("https://exemple.com/ebay/suppression-compte")
            self.assertTrue(32 <= len(c["jeton"]) <= 80)
            attendu = hashlib.sha256(("abc123" + c["jeton"] + c["adresse"]).encode()).hexdigest()
            self.assertEqual(ebay_avis.reponse_defi("abc123")["challengeResponse"], attendu)
            self.assertTrue(ebay_avis.statut()["pret"])
        finally:
            ebay_avis.CHEMIN = old

    def test_base_separee_en_sandbox(self):
        self.assertTrue(lockerroom.chemin_db_env().endswith("lockerroom.db"))
        self.ec.changer_environnement("sandbox")
        self.assertTrue(lockerroom.chemin_db_env().endswith("lockerroom_sandbox.db"))


class AppelsEbay(unittest.TestCase):
    """21 oct 2026 - compteur d'appels (limites par application) et cache partage."""

    def setUp(self):
        import appels_ebay
        self.a = appels_ebay
        d = tempfile.mkdtemp()
        self._old = (appels_ebay.CHEMIN_COMPTEUR, appels_ebay.CHEMIN_CACHE)
        appels_ebay.CHEMIN_COMPTEUR, appels_ebay.CHEMIN_CACHE = os.path.join(d, "a.json"), os.path.join(d, "c.sqlite")

    def tearDown(self):
        self.a.CHEMIN_COMPTEUR, self.a.CHEMIN_CACHE = self._old

    def test_reserve_pour_les_gestes(self):
        a = self.a
        a.compter("browse", 3999)
        self.assertTrue(a.budget_ok("browse", fond=True))
        a.compter("browse")                       # 4 000 = 80 % : les taches de fond s'arretent
        self.assertFalse(a.budget_ok("browse", fond=True))
        self.assertTrue(a.budget_ok("browse", fond=False))   # un tap du vendeur passe encore
        with self.assertRaises(RuntimeError):
            a.exiger("browse", fond=True)
        self.assertEqual(a.resume()["appels"]["browse"]["utilises"], 4000)

    def test_cache(self):
        a = self.a
        cle = a.cle_recherche("production", q="young guns demidov")
        self.assertIsNone(a.cache_lire(cle))
        a.cache_ecrire(cle, [{"item_id": "1"}])
        self.assertEqual(a.cache_lire(cle), [{"item_id": "1"}])
        self.assertNotEqual(cle, a.cle_recherche("sandbox", q="young guns demidov"))
        self.assertEqual(a.resume()["cache_pct"], 50)


class Accueil(unittest.TestCase):
    """22 oct 2026 - accueil : profit vs mois passe a pareille date, gestes classes par $, onglets deduits."""
    def test_accueil(self):
        from datetime import datetime, timedelta
        a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
        c = a._db()
        maint = datetime.now()
        passe = (maint.replace(day=1) - timedelta(days=1)).replace(day=1)
        c.execute("INSERT INTO cartes (titre, statut, prix_vendu, cout, profit, vendu_le, canal) VALUES ('2025-26 UD A', 'Vendue', 50, 20, 23, ?, 'eBay')",
                  (maint.isoformat(),))
        c.execute("INSERT INTO cartes (titre, statut, prix_vendu, cout, profit, vendu_le, canal) VALUES ('B', 'Vendue', 30, 10, 15, ?, 'eBay')",
                  (passe.isoformat(),))
        c.execute("INSERT INTO cartes (titre, statut, prix_demande, cout, item_number, vu_actif_le, debut) VALUES ('C', 'Listée', 40, 10, '77', ?, ?)",
                  (maint.isoformat(), (maint - timedelta(days=120)).isoformat()))
        c.execute("INSERT INTO cartes (titre, statut, prix_demande, item_number, vu_actif_le) VALUES ('D', 'Listée', 25, '78', ?)", (maint.isoformat(),))
        c.execute("INSERT INTO sante (item_number, maj, verdict, suggestion, mediane, n, ecart, requete, fait) VALUES ('77', ?, 'baisser', 32, 33, 5, .2, 'q', 0)",
                  (maint.isoformat(),))
        c.commit(); c.close()
        d = a.accueil()
        self.assertEqual(d["hero"]["profit"], 23)
        self.assertEqual(d["hero"]["pareille_date"], 15)       # le 1er du mois passe est avant aujourd'hui
        self.assertEqual(d["hero"]["ecart"], 8)
        cles = [g["cle"] for g in d["actions"]]
        self.assertEqual(cles[0], "baisser")
        self.assertIn("couts", cles)                            # D n'a pas de cout
        self.assertEqual(d["stock"]["ages"]["vieux"]["n"], 1)
        self.assertEqual(d["activites"], {"breaks": False, "magasin": False})
        a.reglages_sauver({"activites": {"breaks": True, "magasin": False}})
        self.assertTrue(a.activites()["breaks"])
        self.assertEqual(len(a.inventaire_liste({"sans_cout": 1})), 1)


class VoletAcheteur(unittest.TestCase):
    """22 oct 2026 - volet Acheteur : valeur d'une carte (mediane, bon prix a 70 %) et deals."""
    def test_valeur_et_deals(self):
        import ebay_compte
        a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "v.db"))
        avant = ebay_compte.rechercher
        ebay_compte.rechercher = lambda q, **k: [{"item_id": str(i), "titre": q, "prix_cad": p, "port_cad": 0, "url": "u", "photo": None}
                                                  for i, p in enumerate([50, 100, 120, 80, 200])]
        try:
            r = a.valeur_carte("Bedard Young Guns")
        finally:
            ebay_compte.rechercher = avant
        self.assertTrue(r["ok"])
        self.assertEqual(r["mediane"], 100)
        self.assertEqual(r["bon_prix"], 70)
        self.assertEqual([x["total"] for x in r["annonces"]][:2], [50, 80])
        self.assertTrue(r["annonces"][0]["deal"] and not r["annonces"][1]["deal"])
        self.assertFalse(a.valeur_carte("ab")["ok"])
        c = a._db()
        c.execute("INSERT INTO opportunites (item_id, titre, total, url, ref_prix, ratio, vu_le) VALUES ('9','x',40,'u',100,0.4,?)",
                  (lockerroom._maintenant(),))
        c.commit(); c.close()
        import deals                     # 26 oct 2026 : les deals = le chasseur (ventes reelles) ; les rachats n'y sont plus
        un = {"item_id": "9", "titre": "x", "total": 40, "url": "u", "valeur": 100, "ratio": 0.4, "encan": False, "fin": None,
              "sport": "hockey", "q": None, "v": deals.VERSION, "vu_le": lockerroom._maintenant()}
        lire_avant, deals.lire = deals.lire, lambda: {"deals": [un]}
        deals.chasser_si_besoin, chasser_avant = (lambda: False), deals.chasser_si_besoin
        try:
            d = a.acheteur_accueil()
        finally:
            deals.lire, deals.chasser_si_besoin = lire_avant, chasser_avant
        self.assertEqual(d["nb_deals"], 1)
        self.assertEqual(d["deals"][0]["rabais"], 60)
        self.assertGreater(d["deals"][0]["gain"], 40)
        self.assertEqual(a.reglages_sauver({"mode": "acheteur"})["mode"], "acheteur")


class VentesDeuxSources(unittest.TestCase):
    """22 oct 2026 - ventes lues par Trading (GetSellerTransactions) ET par l'API des commandes : jamais en double,
    et les frais reels de la 2e remplacent l'estimation de la 1re."""
    def test_trading_puis_commandes(self):
        import ebay_compte
        xml = (b'<?xml version="1.0"?><GetSellerTransactionsResponse xmlns="urn:ebay:apis:eBLBaseComponents"><Ack>Success</Ack>'
               b'<TransactionArray><Transaction><Item><ItemID>110591315806</ItemID><Title>Cole OHara YG</Title></Item>'
               b'<TransactionID>5001</TransactionID><TransactionPrice currencyID="CAD">5.99</TransactionPrice>'
               b'<ShippingServiceSelected><ShippingServiceCost currencyID="CAD">2.50</ShippingServiceCost></ShippingServiceSelected>'
               b'<CreatedDate>2026-10-22T23:50:00.000Z</CreatedDate><PaidTime>2026-10-23T00:10:00.000Z</PaidTime>'
               b'<Buyer><UserID>testuser_lr_acheteur</UserID></Buyer></Transaction></TransactionArray>'
               b'<PaginationResult><TotalNumberOfPages>1</TotalNumberOfPages></PaginationResult></GetSellerTransactionsResponse>')
        v, pages = ebay_compte.lire_transactions_xml(xml)
        self.assertEqual((len(v), pages, v[0]["prix"], v[0]["port_charge"], v[0]["statut_paiement"]), (1, 1, 5.99, 2.5, "PAID"))
        a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "d.db"))
        c = a._db()
        c.execute("INSERT INTO cartes (titre, item_number, statut, cout) VALUES ('Cole OHara YG','110591315806','Listée',2)")
        c.commit(); c.close()
        r1 = a._maj_ventes(v)
        f = {**v[0], "transaction_id": "api:00-03999-66209:1", "frais_reels": 1.20, "source": None}
        r2 = a._maj_ventes([f])
        self.assertEqual((r1["nouvelles"], r2["nouvelles"], r2["deja"]), (1, 0, 1))
        c = a._db()
        lignes = c.execute("SELECT statut, frais, profit FROM cartes WHERE item_number='110591315806'").fetchall()
        c.close()
        self.assertEqual(len(lignes), 1)
        self.assertEqual(tuple(lignes[0]), ("Vendue", 1.2, round(5.99 + 2.5 - 1.2 - 2, 2)))


if __name__ == "__main__":
    r = unittest.main(exit=False, verbosity=1).result
    print("TOUS LES TESTS PASSENT" if r.wasSuccessful() else "ECHEC")
    sys.exit(0 if r.wasSuccessful() else 1)
