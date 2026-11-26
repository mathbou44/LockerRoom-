"""26 nov 2026 (Mathieu, capture d'une annonce au cell : « le X en haut a droite est cache ») : la fiche d'une annonce defile quand
son contenu depasse l'ecran (sur un iPhone, dans l'app, de ~35 px depuis la bande de tendance) et le X, pose en haut du contenu,
sortait de l'ecran. Au cell il COLLE en haut de la fenetre (sticky) ; sur un ecran large (X pose en absolu) il suit le defilement."""
import os, re
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()
app = open(os.path.join(RACINE, "ui", "app.html"), encoding="utf-8").read()

# 1. au cell : le X colle, dans les deux fiches (Pro / publique, et admin / Platine)
m = re.search(r"@media \(max-width:999px\)\{\s*html body \.fen\.fen\.fen\.fen\.fa\.fb\{padding-top:0 !important\}(.*?)\n\}", src, re.S)
assert m, "le bloc du X collant a disparu"
bloc = m.group(1)
assert "> .fen-x{position:sticky !important" in bloc and "align-self:flex-end" in bloc
assert ":not(.fb-adm) > .fen-x{top:10px !important; margin:10px 0 0 0 !important}" in bloc, "fiche Pro : 10 + 34 + 8 = les 52 px d'avant"
assert ".fb-adm > .fen-x{top:18px !important; margin:18px calc((100% - 10px) * 0.444 + 16px) -46px 0 !important}" in bloc, "fiche admin : le X sur le coin de la photo"
# la marge du haut passe a 0 : « top » se compte alors du haut de la fenetre dans tous les navigateurs (Safari comme Chrome)
assert "padding-top:0 !important" in m.group(0)
# 2. le X reste le premier enfant de la fenetre (le sticky en depend)
assert '<div class="fen fa fb fb-adm" role="dialog" aria-modal="true"><button class="fen-x"' in src
assert re.search(r'<div class="fen fa fa-pub fb"[^>]*><button class="fen-x"', src), "fiche Pro : le X doit rester le premier enfant"
# 3. ecran large : le X (absolu) suit le defilement ; au cell (sticky) le script ne touche a rien
assert "getComputedStyle(x).position === 'absolute'" in src and "x.style.transform = abs && p.scrollTop > 0 ? `translateY(${p.scrollTop}px)` : ''" in src
assert "{capture: true, passive: true}" in src
# 4. l'app servie a le correctif
assert "position:sticky!important" in app.replace(" ", "") and "fen-x-suit" in app
print("OK test_fen_x_colle")
