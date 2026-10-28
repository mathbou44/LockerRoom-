"""28 oct 2026 - « ou sont les cartes auto patch de veterans ou de legendes ? » : vedettes dans les recherches, hits
d'abord, et une part du budget de verification gardee pour les hits."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("LOCKERROOM_DONNEES", tempfile.mkdtemp())
import deals  # noqa: E402
import vendues  # noqa: E402


class TestVedettes(unittest.TestCase):
    def test_vedettes_intercalees(self):
        r = deals.requetes()
        ved = [x for x in r if x.get("vedette")]
        self.assertTrue(ved)
        self.assertTrue(any(x["q"] == "Wayne Gretzky auto" for x in ved))
        self.assertTrue(any(x.get("vedette") for x in r[:3]))       # des le debut de la rotation, pas a la fin

    def test_memes_vedette_toutes_les_cartes_du_joueur(self):
        L = [{"titre": "2019-20 Upper Deck The Cup Wayne Gretzky Auto Patch /25"},
             {"titre": "2022 SP Legendary Signatures Wayne Gretzky auto"},
             {"titre": "2020 Upper Deck Mario Lemieux auto"}]
        _c, l, _e = deals._memes({"q": "Wayne Gretzky auto", "joueur": "Wayne Gretzky", "vedette": True}, L)
        self.assertEqual(len(l), 2)

    def test_budget_garde_pour_les_hits(self):
        vrai = vendues.rechercher
        vendues.rechercher = lambda q, fond=True, **k: {"ventes": [{"titre": q, "prix": 10, "le": "2026-10-20"}]}
        os.environ["LR_DEALS_VERIF_JOUR"] = "10"
        try:
            st = {}
            vrai_j = deals._jour_mtl
            deals._jour_mtl = lambda: ("2026-10-28", 23.9)          # fin de journee : le rythme ne limite plus
            try:
                f = deals._verificateur({}, st, deals.Bassin(charger=False))
            finally:
                deals._jour_mtl = vrai_j
            yg = [f({"texte": f"joueur{i} young guns", "mots": [f"joueur{i}"], "joueur": f"joueur{i}", "auto": False, "patch": False,
                     "serie": None, "annee": 2025, "num": None, "grade": None, "rc": True, "paralleles": set(), "exclu": False,
                     "veut_grade": False, "brute": False, "veut_serie": False, "base": False, "produits": set()}) for i in range(8)]
            hits = [f({"texte": f"legende{i} auto patch /25", "mots": [f"legende{i}"], "joueur": f"legende{i}", "auto": True, "patch": True,
                       "serie": 25, "annee": 2020, "num": None, "grade": None, "rc": False, "paralleles": set(), "exclu": False,
                       "veut_grade": False, "brute": False, "veut_serie": True, "base": False, "produits": set()}) for i in range(8)]
        finally:
            vendues.rechercher = vrai
            os.environ.pop("LR_DEALS_VERIF_JOUR", None)
        self.assertEqual(sum(1 for x in yg if x is not None), 2)      # 15 % de 10 pour les cartes ordinaires (28 oct : 0,85 aux hits)
        self.assertEqual(sum(1 for x in hits if x is not None), 8)    # le reste pour les hits

    def test_filtres_veteran_et_hit(self):
        import lockerroom
        L = [{"titre": "2026-27 Upper Deck Young Guns Anton Frondell"}, {"titre": "2019-20 The Cup Wayne Gretzky Auto Patch /25"},
             {"titre": "2020-21 SP Authentic Sidney Crosby Sign of the Times Auto"}, {"titre": "2025-26 SP Authentic Demidov Future Watch Auto /999"}]
        f = lockerroom.Api._deals_filtrer
        self.assertEqual([x["titre"][:12] for x in f(L, {"sortes": ["veteran"]})], ["2019-20 The ", "2020-21 SP A"])
        self.assertEqual(len(f(L, {"sortes": ["hit"]})), 3)
        self.assertEqual(len(f(L, {"sortes": ["veteran", "hit"]})), 2)

    def test_hit_prix_fixe_vedette_verifie(self):
        """29 oct 2026 : un hit d'une vedette a prix fixe, sans vente connue de sa carte, est verifie en fin de tour."""
        from datetime import datetime, timedelta, timezone
        maint = datetime.now(timezone.utc)
        j = lambda n: (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d")
        titre = "2019-20 Upper Deck The Cup Wayne Gretzky Auto Patch /25"
        ventes = [{"titre": titre, "prix": p, "le": j(k), "url": f"u{k}"} for k, p in ((3, 410), (9, 395), (15, 430), (20, 400))]
        vus = []
        def verif(cib):
            vus.append(cib.get("joueur"))
            return ventes
        a = {"item_id": "v1", "titre": titre, "prix_cad": 180.0, "port_cad": 0.0, "url": "https://www.ebay.com/itm/v1", "vendeur_pct": "100", "vendeur_score": 900}
        st, deals_ = {}, {}
        r = {"q": "Wayne Gretzky auto", "joueur": "Wayne Gretzky", "sport": "hockey", "vedette": True}
        deals._juger(a, r, [], [], maint, deals_, st, bassin=deals.Bassin(charger=False), verif=verif)
        self.assertNotIn("v1", deals_)                       # pas encore : verifie en fin de tour
        self.assertEqual(len(st.get("_tard") or []), 1)
        deals._verifier_tard(st, deals_, maint, deals.Bassin(charger=False), verif)
        self.assertEqual(vus, ["wayne gretzky"])
        self.assertIn("v1", deals_)                          # 180 $ pour une carte qui se vend ~400 $
        # un hit a prix fixe ordinaire, sans repere : pas de verification (on garde le budget)
        st2 = {}
        b = dict(a, item_id="v2", prix_cad=50.0)                 # 28 oct : sous 60 $, sans repere (a 60 $ et plus, verifie)
        deals._juger(b, {"q": "x", "joueur": "Wayne Gretzky", "sport": "hockey"}, [], [], maint, {}, st2, bassin=deals.Bassin(charger=False), verif=verif)
        self.assertFalse(st2.get("_tard"))

    def test_vendeurs_suivis(self):
        """29 oct 2026 : les encans des vendeurs suivis (toutes cartes de 25 $ et plus), verifies en fin de tour."""
        from datetime import datetime, timedelta, timezone
        j = lambda n: (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d")
        self.assertEqual(deals.regler_vendeurs(["@savage_cards", "savage_cards", "remi.cards", "bad name!"]), ["savage_cards", "remi.cards", "badname"])
        fin = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat().replace("+00:00", "Z")
        titre = "2015-16 Upper Deck SP Authentic Connor McDavid Sign of the Times Auto"
        appels = []
        def rech(q, **k):
            appels.append(k.get("vendeurs"))
            if k.get("vendeurs") and k.get("encheres"):
                return [{"item_id": "s1", "titre": titre, "prix_cad": 60.0, "port_cad": 0.0, "encan": True, "fin": fin, "mises": 4,
                         "url": "https://www.ebay.com/itm/s1", "vendeur_pct": "100", "vendeur_score": 5000}]
            return []
        vrai, avant, avant_h = vendues.rechercher, deals.FLUX, deals.FLUX_HITS
        vendues.rechercher = lambda q, fond=True, **k: {"ventes": [{"titre": titre, "prix": p, "le": j(k), "url": f"w{k}"} for k, p in ((2, 240), (8, 255), (14, 230))]}
        deals.FLUX, deals.FLUX_HITS = [], []
        try:
            r = deals.flux(rech, bassin=deals.Bassin(charger=False))
        finally:
            vendues.rechercher, deals.FLUX, deals.FLUX_HITS = vrai, avant, avant_h
            deals.regler_vendeurs(deals.VENDEURS_DEFAUT)
        self.assertIn(["savage_cards", "remi.cards", "badname"], appels)
        ids = {x["item_id"]: x for x in deals.lire().get("deals") or []}
        self.assertIn("s1", ids, r)                              # 60 $ pour une auto qui se vend ~240 $

    def test_ecran_melange_pas_un_mur_de_young_guns(self):
        L = [{"titre": f"2025-26 Upper Deck Young Guns Joueur{i}"} for i in range(6)] + [{"titre": "2019-20 The Cup Gretzky Auto Patch /25"},
             {"titre": "2020-21 SP Authentic Sidney Crosby"}]
        m = deals.melanger(L)
        self.assertEqual([deals.sorte(x["titre"]) for x in m[:3]], ["hits", "veterans", "young_guns"])
        self.assertEqual(len(m), len(L))

    def test_hit_avec_une_seule_vente_connue_verifie(self):
        """28 oct 2026 : un hit avec 1 vente connue (pas assez pour une valeur sure) est verifie, plus jamais ecarte."""
        from datetime import datetime, timedelta, timezone
        maint = datetime.now(timezone.utc)
        titre = "2021-22 SP Authentic Cole Caufield Future Watch Auto Patch /100"
        fin = (maint + timedelta(hours=10)).isoformat().replace("+00:00", "Z")
        a = {"item_id": "h1", "titre": titre, "prix_cad": 70.0, "port_cad": 0.0, "encan": True, "fin": fin, "mises": 2,
             "url": "https://www.ebay.com/itm/h1", "vendeur_pct": "100", "vendeur_score": 900}
        une = [{"titre": titre, "prix": 200.0, "le": datetime.now().strftime("%Y-%m-%d"), "url": "u1"}]
        st = {}
        deals._juger(a, {"q": None, "flux": "x", "sport": "hockey", "joueur": None}, une, [], maint, {}, st,
                     bassin=deals.Bassin(charger=False), verif=lambda c: [])
        self.assertEqual(len(st.get("_tard") or []), 1)


if __name__ == "__main__":
    unittest.main()
