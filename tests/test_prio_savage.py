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
        self.assertNotIn("p4", ids)                          # 4 $ : pas de credit
        self.assertNotIn("p5", ids)                          # vendeur suivi non prioritaire : budget du chasseur (0)
        self.assertFalse(any("makar" in q for q in prio_q))
        self.assertFalse(any("mackinnon" in q for q in prio_q))
        # l'ordre : Savage avant Remi
        ia = [i for i, q in enumerate(prio_q) if "crosby" in q][0]
        ib = [i for i, q in enumerate(prio_q) if "mcdavid" in q][0]
        self.assertLess(ia, ib)

    def test_plafond_reserve(self):
        os.environ["LR_DEALS_VERIF_PRIO"] = "1"
        deals.flux(rech, bassin=deals.Bassin(charger=False))
        self.assertEqual(len([1 for _q, u in appels if u == "prio"]), 1)


if __name__ == "__main__":
    unittest.main()
