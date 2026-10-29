"""30 oct 2026 (Mathieu : « toutes les cartes de Savage n'ont pas de comp, c'est pour ca que je les vois pas ») : la
reserve de verifications des 4 vendeurs prioritaires. Budget du chasseur a zero : les cartes de 10 $ et plus de Savage
(prix fixe et encans) sont quand meme verifiees sur leurs vraies ventes ; un autre vendeur suivi, non ; et la reserve
s'arrete a son plafond."""
import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
os.environ["LR_DEALS_VERIF_JOUR"] = "0"
from datetime import datetime, timedelta, timezone
import deals, vendues, cartes_match
maint = datetime.now(timezone.utc)
fin = lambda h: (maint + timedelta(hours=h)).isoformat().replace("+00:00", "Z")
# (titre, prix, valeur reelle, heures avant la fin ou None, vendeur)
CARTES = [
 ("2024-25 Upper Deck Young Guns Renewed Sidney Crosby #YGR-10 Pittsburgh Penguins", 22, 60, None, "savage.cards"),
 ("2025-26 Upper Deck Young Guns Outburst Otto Stenberg #711 St. Louis Blues", 12, 45, None, "savage.cards"),
 ("2023-24 Upper Deck Canvas Auston Matthews #C70 Toronto Maple Leafs", 11, 40, 30, "savage.cards"),
 ("2022-23 Upper Deck Clear Cut Connor McDavid #CC-1 Edmonton Oilers", 18, 70, None, "remi-card-trader"),
 ("2021-22 Upper Deck Ice Nathan MacKinnon #20 Colorado Avalanche", 4, 6, None, "savage.cards"),            # sous 10 $
 ("2023-24 Upper Deck Canvas Cale Makar #C120 Colorado Avalanche", 12, 45, None, "dcsports87"),          # pas prioritaire
]
VAL = {t: v for t, _p, v, _h, _v in CARTES}
appels = []
def ventes_pour(q):
    out = []
    for t, v in VAL.items():
        if (cartes_match.requete_ebay(cartes_match.cible_titre(t)) or "").strip() == q:
            out += [{"titre": t, "prix": v * f, "le": (datetime.now() - timedelta(days=d)).strftime("%Y-%m-%d"), "url": f"{t}{d}"}
                    for f, d in ((1.0, 3), (0.95, 9), (1.05, 15))]
    return out
compte = {"prio": 0}
def faux_rechercher(q, fond=True, usage=None, **k):
    appels.append((q, usage))
    if usage == "prio":
        compte["prio"] += 1
    return {"ventes": ventes_pour(q)}
vendues.rechercher = faux_rechercher
vendues.en_cache = lambda q: None
vendues.utilises_aujourdhui = lambda usage=None: compte["prio"] if usage == "prio" else 0
deals._jour_mtl = lambda: (maint.strftime("%Y-%m-%d"), 20.0)
deals.vendeurs_suivis = lambda: ["savage.cards", "remi-card-trader", "dcsports87"]
deals.groupes_chasse = lambda: [["savage.cards", "remi-card-trader", "dcsports87"]]


def rech(q, **k):
    if not k.get("vendeurs") or (k.get("offset") or 0):
        return []
    l = []
    for i, (t, p, v, h, ve) in enumerate(CARTES):
        if bool(k.get("encheres")) != (h is not None):
            continue
        a = {"item_id": f"p{i}", "titre": t, "prix_cad": float(p), "port_cad": 0.0, "url": f"https://www.ebay.com/itm/p{i}",
             "vendeur": ve, "vendeur_pct": "100", "vendeur_score": 90000}
        if h is not None:
            a.update(encan=True, fin=fin(h), mises=1)
        l.append(a)
    return l


class TestPrioSavage(unittest.TestCase):
    def setUp(self):
        self.avant = deals.FLUX, deals.FLUX_HITS
        deals.FLUX, deals.FLUX_HITS = [], []
        appels.clear(); compte["prio"] = 0
        d0 = deals.lire(); d0["deals"], d0["suivis"] = [], []; deals._ecrire(d0)

    def tearDown(self):
        deals.FLUX, deals.FLUX_HITS = self.avant
        os.environ.pop("LR_DEALS_VERIF_PRIO", None)

    def test_reserve_savage(self):
        deals.flux(rech, bassin=deals.Bassin(charger=False))
        prio_q = [q for q, u in appels if u == "prio"]
        ids = {x["item_id"]: x for x in deals.lire().get("deals") or []}
        for i in (0, 1, 3):                                  # Savage et Remi, prix fixe, 10 $ et plus : verifies -> deals
            self.assertIn(f"p{i}", ids, (CARTES[i][0], prio_q))
            self.assertTrue(ids[f"p{i}"].get("valeur"))
        self.assertIn("p4", ids)                             # 31 oct : TOUTES les cartes des 4 vendeurs (meme a 4 $)
        self.assertNotIn("p5", ids)                          # vendeur suivi non prioritaire : budget du chasseur (0)
        self.assertFalse(any("makar" in q for q in prio_q))
        self.assertTrue(any("mackinnon" in q for q in prio_q))
        cov = deals.lire()["prio_couverture"]                # 31 oct : combien de cartes des 4 vendeurs sont analysees
        self.assertEqual((cov["faites"], cov["total"]), (5, 5), cov)
        self.assertEqual(cov["par_vendeur"]["savage.cards"], [4, 4])
        # l'ordre : Savage avant Remi
        ia = [i for i, q in enumerate(prio_q) if "crosby" in q][0]
        ib = [i for i, q in enumerate(prio_q) if "mcdavid" in q][0]
        self.assertLess(ia, ib)

    def test_plafond_reserve(self):
        os.environ["LR_DEALS_VERIF_PRIO"] = "1"
        deals.flux(rech, bassin=deals.Bassin(charger=False))
        self.assertEqual(len([1 for _q, u in appels if u == "prio"]), 1)

    def test_debordement_avant_les_autres(self):
        """31 oct 2026 (« toutes analysees avant de passer au reste ») : reserve vide -> les cartes des 4 vendeurs prennent
        le budget du chasseur ; les autres cartes attendent qu'elles soient toutes passees."""
        os.environ["LR_DEALS_VERIF_PRIO"] = "1"
        os.environ["LR_DEALS_VERIF_JOUR"] = "3"
        u = {"verif": 0}
        def faux2(q, fond=True, usage=None, **k):
            appels.append((q, usage))
            if usage == "prio":
                compte["prio"] += 1
            else:
                u["verif"] += 1
            return {"ventes": ventes_pour(q)}
        vendues.rechercher = faux2
        vendues.utilises_aujourdhui = lambda usage=None: compte["prio"] if usage == "prio" else u["verif"] if usage == "verif" else 0
        try:
            deals.flux(rech, bassin=deals.Bassin(charger=False))
        finally:
            vendues.rechercher = faux_rechercher
            vendues.utilises_aujourdhui = lambda usage=None: compte["prio"] if usage == "prio" else 0
            os.environ["LR_DEALS_VERIF_JOUR"] = "0"
        us = [(q, x) for q, x in appels]
        self.assertEqual([x for _q, x in us][:1], ["prio"])
        self.assertEqual(len([1 for _q, x in us if x == "verif"]), 3)       # le budget du chasseur, aux 4 vendeurs d'abord
        self.assertFalse(any("makar" in q for q, _x in us))                 # l'autre vendeur attend
        self.assertTrue(deals.lire()["prio_couverture"]["faites"] >= 4)

    def test_valoriser_entre_deux_tours(self):
        """30 oct 2026 : entre deux tours, les encans de Savage sans valeur prennent la leur (reserve « prio »)."""
        d0 = deals.lire()
        T = "2024-25 Upper Deck Young Guns Renewed Sidney Crosby #YGR-10 Pittsburgh Penguins"
        d0["suivis"] = [{"item_id": "v1", "titre": T, "total": 15, "port": 0, "encan": True, "fin": fin(6), "vendeur": "savage.cards", "suivi": True},
                        {"item_id": "v2", "titre": T, "total": 18, "port": 0, "encan": True, "fin": fin(9), "vendeur": "savage.cards", "suivi": True},
                        {"item_id": "v3", "titre": CARTES[5][0], "total": 12, "port": 0, "encan": True, "fin": fin(5), "vendeur": "dcsports87", "suivi": True}]
        deals._ecrire(d0)
        r = deals.valoriser_suivis()
        su = {x["item_id"]: x for x in deals.lire()["suivis"]}
        self.assertEqual(r["verifies"], 1)                    # une seule recherche pour les deux Crosby
        self.assertAlmostEqual(su["v1"]["valeur"], 60, delta=4)
        self.assertTrue(su["v2"]["valeur"])
        self.assertFalse(su["v3"].get("valeur"))              # vendeur non prioritaire : pas de credit


if __name__ == "__main__":
    unittest.main()
