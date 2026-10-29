"""29 oct 2026 (Mathieu : « deux jours avant les encheres chez Savage, Remi, CF31, Slab Sharks, DC Sports… si je ne vois
pas ces cartes-la, on a un probleme ») : un tour des vendeurs suivis avec des legendes (RC vintage gradees), des autos et
patchs de veterans, des jeunes de 2e a 4e annee, a petite mise, qui finissent dans 2 a 3 jours."""
import unittest

import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
os.environ["LR_DEALS_VERIF_JOUR"] = "400"
from datetime import datetime, timedelta, timezone
import deals, vendues, cartes_match
maint = datetime.now(timezone.utc)
fin = lambda h: (maint + timedelta(hours=h)).isoformat().replace("+00:00", "Z")
# (titre, mise/prix actuel, valeur reelle (ventes), heures avant la fin ou None = prix fixe)
CARTES = [
 ("1979-80 O-Pee-Chee Wayne Gretzky #18 Rookie PSA 7", 410, 1450, 54),
 ("Mario Lemieux 1985-86 OPC Rookie RC #9 BGS 8.5", 160, 900, 56),
 ("Patrick Roy 1986-87 OPC #53 Rookie PSA 8", 45, 380, 60),
 ("Bobby Orr 1966-67 Topps #35 Rookie SGC 3", 520, 2600, 70),
 ("2019-20 Upper Deck The Cup Wayne Gretzky Auto Patch /25", 300, 1100, 50),
 ("2021-22 SP Game Used Auston Matthews Tag Patch 1/1", 210, 900, 52),
 ("2023-24 SPx Kirill Kaprizov Radiance Auto /49", 22, 140, 48),
 ("2023-24 Upper Deck Ultimate Collection Cale Makar Ultimate Jersey Auto /35", 90, 420, 58),
 ("2016-17 Upper Deck Artifacts Auston Matthews Auto Patch RC /99 BGS 9.5", 140, 700, 62),
 ("2023-24 Upper Deck Young Guns Connor Bedard #451 PSA 10", 95, 260, 55),
 ("2024-25 Upper Deck Young Guns Macklin Celebrini #201 PSA 10", 60, 210, 57),
 ("2023-24 SP Authentic Connor Bedard Future Watch Auto /999", 230, 900, 66),
 ("2020-21 Upper Deck Trilogy Nathan MacKinnon Signature Pucks", 35, 180, 64),
 ("Guy Lafleur 1971-72 OPC #148 RC PSA 6", 120, 600, 59),
 ("2019-20 Upper Deck Black Diamond Elias Pettersson Quad Jersey /25", 15, 75, 45),
 ("2012-13 Upper Deck Sidney Crosby Base #1", 2, 4, 50),           # carte ordinaire : rien
 ("2025-26 Upper Deck Young Guns Ivan Demidov #451", 30, 140, 30),
 ("2023-24 Upper Deck The Cup Connor McDavid Gold Rainbow /36 PSA 9", 600, 1500, 130),  # au-dela de 5 jours
 ("2022-23 Upper Deck Ice Jake Sanderson Ice Premieres Auto /99", 40, 70, 40),          # pas assez sous la valeur
 ("2021-22 Upper Deck Premier Leon Draisaitl Auto Patch /49", 280, 650, None),         # prix fixe
]
VAL = {t: v for t, _m, v, _h in CARTES}
def ventes_pour(q):
    out = []
    for t, v in VAL.items():
        if (cartes_match.requete_ebay(cartes_match.cible_titre(t)) or "").strip() == q:
            out += [{"titre": t, "prix": v * f, "le": (datetime.now() - timedelta(days=d)).strftime("%Y-%m-%d"), "url": f"{t}{d}"}
                    for f, d in ((1.0, 4), (0.95, 11), (1.05, 19))]
    return out
appels = []
vendues.rechercher = lambda q, fond=True, **k: (appels.append(q) or {"ventes": ventes_pour(q)})
vendues.en_cache = lambda q: None
deals._jour_mtl = lambda: (maint.strftime("%Y-%m-%d"), 20.0)
def rech(q, **k):
    if not k.get("vendeurs"):
        return []
    l = []
    for i, (t, m, v, h) in enumerate(CARTES):
        if bool(k.get("encheres")) != (h is not None):
            continue
        a = {"item_id": f"s{i}", "titre": t, "prix_cad": float(m), "port_cad": 5.0, "url": f"https://www.ebay.com/itm/s{i}",
             "vendeur_pct": "100", "vendeur_score": 50000}
        if h is not None:
            a.update(encan=True, fin=fin(h), mises=3)
        l.append(a)
    return l if (k.get("offset") or 0) == 0 else []


class TestVendeursSuivis(unittest.TestCase):
    def test_tour_vendeurs_suivis(self):
        avant = deals.FLUX, deals.FLUX_HITS
        deals.FLUX, deals.FLUX_HITS = [], []
        try:
            deals.flux(rech, bassin=deals.Bassin(charger=False))
        finally:
            deals.FLUX, deals.FLUX_HITS = avant
        ids = {x["item_id"]: x for x in deals.lire().get("deals") or []}
        for i, (t, m, v, h) in enumerate(CARTES):
            with self.subTest(t=t):
                if "Base #1" in t or (h or 0) > deals.ENCAN_SUIVI_H:
                    self.assertNotIn(f"s{i}", ids)          # carte ordinaire, ou finit dans plus de 5 jours
                else:
                    self.assertIn(f"s{i}", ids)
        import lockerroom
        vet = lockerroom.Api._deals_filtrer(list(ids.values()), {"sortes": ["veteran"]})
        self.assertGreaterEqual(len(vet), 15)
        self.assertNotIn("young guns ivan demidov", " ".join(x["titre"].lower() for x in vet))


    def test_encans_veterans_visibles_sans_credit(self):
        """29 oct 2026 (« je ne vois toujours pas les cartes non rookie ») : budget SoldComps a zero, les encans de
        veterans et de legendes des vendeurs suivis sont quand meme montres (« valeur à vérifier »), jamais comme des deals."""
        avant = deals.FLUX, deals.FLUX_HITS, os.environ.get("LR_DEALS_VERIF_JOUR")
        deals.FLUX, deals.FLUX_HITS = [], []
        os.environ["LR_DEALS_VERIF_JOUR"] = "0"
        d0 = deals.lire()
        d0["deals"], d0["suivis"] = [], []
        deals._ecrire(d0)
        try:
            deals.flux(rech, bassin=deals.Bassin(charger=False))
        finally:
            deals.FLUX, deals.FLUX_HITS = avant[0], avant[1]
            os.environ["LR_DEALS_VERIF_JOUR"] = avant[2] or "400"
        d = deals.lire()
        su = {x["titre"]: x for x in d.get("suivis") or []}
        self.assertIn("1979-80 O-Pee-Chee Wayne Gretzky #18 Rookie PSA 7", su)
        self.assertIn("2019-20 Upper Deck The Cup Wayne Gretzky Auto Patch /25", su)
        self.assertIn("2023-24 Upper Deck Young Guns Connor Bedard #451 PSA 10", su)        # joueur de 4e annee
        self.assertNotIn("2025-26 Upper Deck Young Guns Ivan Demidov #451", su)            # recrue de l'annee
        self.assertNotIn("2012-13 Upper Deck Sidney Crosby Base #1", su)                   # carte de base a 2 $
        self.assertFalse(any(t.startswith("2023-24 Upper Deck The Cup Connor McDavid") for t in su))   # finit dans plus de 5 jours
        self.assertIsNone(su["1979-80 O-Pee-Chee Wayne Gretzky #18 Rookie PSA 7"]["valeur"])
        import lockerroom
        a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
        lockerroom.ebay_prix_actif = lambda: True
        r = a.deals_liste({"sortes": ["veteran"]})
        self.assertGreaterEqual(len(r["suivis"]), 5, r.get("suivis"))


    def test_pas_de_soccer_ni_tennis(self):
        """29 oct 2026 (« pour les legendes on dirait tout sauf du hockey ») : Haaland, Paire... ne sortent pas."""
        import cartes_match
        for t in ("2026 Panini Prizm World Cup Erling Haaland Red #/50 Norway", "2023 Topps Chrome Benoit Paire Auto Autograph"):
            self.assertIsNone(deals.sport_carte(t, cartes_match.cible_titre(t)))
        for t in ("2023-24 SPx Kirill Kaprizov Radiance Auto /49", "Bobby Orr 1966-67 Topps #35 Rookie SGC 3", "1979-80 O-Pee-Chee Wayne Gretzky #18 PSA 7"):
            self.assertEqual(deals.sport_carte(t, cartes_match.cible_titre(t)), "hockey")


if __name__ == "__main__":
    unittest.main()
