"""24 nov 2026 (Mathieu) : la feuille Filtres des deals.
1) « Quand je clique sur Best deal, ça revient à Ending soon » : avec « Encans », « Appliquer » remplacait en silence
   « Meilleur deal » par « Finit bientôt ». L'ordre choisi reste ; « Encans » propose « Finit bientôt » au moment du choix.
2) « Revoir le layout pour que ça fitte sur une page ; la methode Apple » : des rangees facon Reglages d'iOS, des menus natifs.
"""
import os
import re
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lire(*p):
    with open(os.path.join(RACINE, *p), encoding="utf-8") as f:
        return f.read()


class FiltresIOS(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.src = lire("source", "src_app.html")
        i = cls.src.index("async function feuilleFiltresDeals(){")
        cls.fn = cls.src[i:cls.src.index("\nasync function feuilleReglagesDeals(){", i)]

    def test_appliquer_garde_l_ordre_choisi(self):
        i = self.fn.index("const appliquer = async (raz) => {")
        corps = self.fn[i:]
        self.assertIn("F.tri = raz ? 'rabais' : tri; F.type = raz ? '' : ty;", corps)
        self.assertNotRegex(corps, r"F\.type === 'encan' && F\.tri === 'rabais'\) F\.tri = 'fin'",
                            "« Appliquer » ne doit plus remplacer « Meilleur deal » par « Finit bientôt »")

    def test_encans_propose_finit_bientot_au_moment_du_choix(self):
        self.assertRegex(self.fn, r"lier\('fd-ty', v => \{ ty = v; if \(ty === 'encan' && tri === 'rabais'\) \{ tri = 'fin'; poser\('fd-tri', 'fin'\); \} \}\);")
        self.assertIn("lier('fd-tri', v => { tri = v; });", self.fn)          # un choix d'ordre fait a la main n'est jamais change

    def test_cinq_menus_natifs(self):
        for id_ in ("fd-tri", "fd-ty", "fd-iq", "fd-bud", "fd-prov"):
            self.assertIn("menu('%s'," % id_, self.fn, id_)
            self.assertIn("lier('%s'," % id_, self.fn, id_)
        self.assertIn("<select id=\"${id}\" aria-label=", self.src)          # le menu partage (ioMenu)
        self.assertIn("const menu = ioMenu;", self.fn)
        self.assertIn("e.target.matches('input[type=checkbox], select')", self.fn, "« Appliquer » doit apparaitre quand un menu change")

    def test_plus_de_rangees_de_pastilles(self):
        for vieux in ('class="fx-s"', 'class="fx-pl"', "data-bud=", "data-tri=", "data-ty=", "data-pv="):
            self.assertNotIn(vieux, self.fn, vieux)
        self.assertNotRegex(self.src, r"(?m)^\.fx-(s|t|pl|p)\{")

    def test_rangees_ios(self):
        m = re.search(r"\.io-r\{[^}]*min-height:(\d+)px", self.src)
        self.assertTrue(m and int(m.group(1)) >= 44, "une rangee iOS fait 44 px")
        self.assertRegex(self.src, r"\.io-m select\{[^}]*opacity:0[^}]*font-size:16px")       # 16 px : l'iPhone ne zoome pas
        self.assertRegex(self.src, r"\.io-sw i\{[^}]*width:51px; height:31px")                  # l'interrupteur d'iOS
        self.assertIn('id="fd-raz"', self.fn)
        self.assertIn('id="fd-seul"', self.fn)


if __name__ == "__main__":
    unittest.main()
