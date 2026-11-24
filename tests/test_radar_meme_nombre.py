"""24 nov 2026 (Mathieu : « pourquoi 99+ dans la page Radar et 11 dans la page d'accueil ? ») : UN seul nombre.
Le nombre de l'accueil est le « Tout » du Radar : chaque annonce de chaque rangee, une fois, les deux rangees du haut
(« A la une », « Tres recherchees ») comprises. Il est compte a chaque Radar envoye et relu par l'accueil sous la MEME cle.
"""
import os
import re
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(ICI)
sys.path.insert(0, RACINE)
os.environ.setdefault("LOCKERROOM_DONNEES", tempfile.mkdtemp(prefix="lr_nb_"))

import lockerroom  # noqa: E402
from lockerroom import Api  # noqa: E402


def an(i, **k):
    return dict({"item_id": str(i), "titre": "carte %s" % i, "total": 50, "score": 80}, **k)


RADAR = {"ok": True,
         "a_la_une": [an(1), an(2)],
         "recherchees": [an(3), an(4), an(5), an(2)],            # la 2 est deja « a la une » : comptee une fois
         "deals": [an(6)],
         "petits": [an(7), an(1)],
         "pour_toi": [{"joueur": "Shane Wright", "annonces": [an(8), an(9), an(3)]}],
         "types": [{"type": "auto", "annonces": [an(10)]}],
         "chasses": [{"pid": "p", "sous": "s", "annonces": [an(11)]}],
         "chauds": [{"joueur": "A", "annonces": [an(12)]}],
         "creux": [{"joueur": "B", "annonces": [an(13)]}],
         "decouvrir": [{"joueur": "C", "annonces": [an(14)]}],
         "vendeurs": [{"vendeur": "v", "annonces": [an(15), an(6)]}],
         "cibles": [{"annonces": [an(99)]}]}                     # l'app ne les affiche pas dans son fil : pas comptees


class MemeNombre(unittest.TestCase):

    def test_le_tout_compte_chaque_rangee_une_fois(self):
        self.assertEqual(Api._radar_tout(RADAR), 15)
        self.assertEqual(Api._radar_tout({"ok": True}), 0)
        self.assertEqual(Api._radar_tout(None), 0)
        # les deux rangees du haut comptent (l'oubli du 19 et du 24 nov)
        self.assertEqual(Api._radar_tout({"a_la_une": [an(1)], "recherchees": [an(2), an(3)]}), 3)

    def test_les_memes_rangees_que_l_app(self):
        """Le fil de l'app (vueMesDeals : ajouter(...)) et le compte du serveur lisent les memes rangees."""
        with open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8") as f:
            src = f.read()
        i = src.index("const ajouter = (cle, nom, l)")
        bloc = src[i:src.index("S.mdTous = tous;", i)]
        app = set(re.findall(r"\br\.([a-z_]+)", bloc)) - {"profil"}
        self.assertEqual(app, set(Api._TOUT_PLATES) | set(Api._TOUT_GROUPES))

    def test_l_accueil_relit_le_nombre_du_radar(self):
        a = Api()
        avant = (a._mes_deals0, lockerroom.ebay_prix_actif, lockerroom.forfaits.est_pro)
        a._mes_deals0 = lambda frais=False: {k: (list(v) if isinstance(v, list) else v) for k, v in RADAR.items()}
        lockerroom.ebay_prix_actif = lambda *x, **k: False
        lockerroom.forfaits.est_pro = lambda *x, **k: True
        Api._MES_DEALS.clear()
        Api._MES_DEALS_N.clear()
        try:
            r = a.mes_deals()
            self.assertEqual(r["tout_n"], 15)
            self.assertTrue(r["tout_le"] > 0)
            d = a.acheteur_accueil()
            self.assertEqual(d["nb_deals"], 15, "l'accueil doit donner le meme nombre que le Radar")
            # l'accueil recalcule parfois le Radar pour son carrousel : son heure n'est jamais plus vieille que celle du Radar envoye
            self.assertGreaterEqual(d["nb_deals_le"], r["tout_le"])
            # un Radar plus recent (une carte de plus) : l'accueil suit tout de suite, sans attendre ses 10 minutes
            a._mes_deals0 = lambda frais=False: dict(RADAR, recherchees=RADAR["recherchees"] + [an(50)])
            r2 = a.mes_deals()
            self.assertEqual(r2["tout_n"], 16)
            d2 = a.acheteur_accueil()
            self.assertEqual(d2["nb_deals"], 16)
            self.assertGreaterEqual(d2["nb_deals_le"], d["nb_deals_le"])
        finally:
            a._mes_deals0, lockerroom.ebay_prix_actif, lockerroom.forfaits.est_pro = avant

    def test_l_app_n_a_qu_une_source(self):
        with open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8") as f:
            src = f.read()
        self.assertIn("function radarNb(n, le)", src)
        self.assertIn("radarNb(nb_, r.tout_le)", src)
        self.assertNotIn("'99+'", src, "le vrai nombre s'ecrit en entier, le meme partout")
        # la pastille de l'onglet ne s'ecrit plus qu'a travers nbTxt
        for m in re.finditer(r"pD\.textContent = ([^;]+);", src):
            self.assertIn("nbTxt(", m.group(1), m.group(0))


if __name__ == "__main__":
    unittest.main()
