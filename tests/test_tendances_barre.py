"""27 nov 2026 (Mathieu, 2 captures au cell : « regarde la grosseur de la barre Players / Cards [...] elle change de grosseur quand
tu passes de Players a Cards, ca shift. C'est bizarre. »). Quand la page Joueurs debordait, l'app serrait AUSSI la barre des
onglets et les pastilles dessous, dans cet onglet-la seulement. Regle : l'en-tete (titre, recherche, barre, pastilles) a la meme
taille et la meme place dans les 3 onglets ; seules les listes cedent de la place.
Mesure dans un vrai navigateur le 27 nov (vrais clics Joueurs -> Cartes -> A grader -> Joueurs, 6 ecrans, FR et EN) : la barre
ne bouge plus d'un pixel ; 375 x 667 tient sans defiler dans les 3 onglets.   python tests/test_tendances_barre.py"""
import os, re
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()
app = open(os.path.join(RACINE, "ui", "app.html"), encoding="utf-8").read()
css = src

# ---- 1. le mode « serre » (decide par l'onglet affiche) ne touche plus ni la barre des onglets, ni les pastilles, ni le titre
for regle in re.findall(r"[^{}]*\.tiq-serre[^{}]*\{[^}]*\}", css):
    sel = regle.split("{")[0]
    assert ".tiq-mode" not in sel and ".tiq-seg" not in sel and ".tiq-t" not in sel and "#tiq-z" not in sel, regle
assert ".tiq-serre .tiq-lm .tiq-m{padding:8px 0}" in css          # il serre encore les rangees des listes
# ---- 2. plus de classe posee par l'app qui change l'en-tete selon l'onglet
assert "classList.add('tiq-court')" not in src and ".tiq-court " not in css and ".tiq-court{" not in css
i = src.index("function ajusterTiq(z)"); f = src[i:src.index("if (!window.__tiqFit)", i)]
assert f.count("classList.add(") == 1 and "z.classList.add('tiq-serre')" in f
# ---- 3. l'en-tete serre des tout petits ecrans : decide par l'ECRAN (les 3 onglets pareil), ecrit APRES la regle generale
gen = css.index("@media (max-width:1099px){ .tiq-mode{display:flex; align-self:stretch; margin-bottom:10px} .tiq-mode button{flex:1; padding:8px 6px}")
pet = css.index("@media (max-width:1099px) and (max-height:700px){\n  .tiq-mode{margin-bottom:6px} .tiq-mode button{padding-top:5px; padding-bottom:5px}")
assert pet > gen
bloc = css[pet:css.index("\n}", pet)]
assert ".ecran.tiq .tiq-tf .tiq-t .sous{display:none}" in bloc and ".tiq-kr2{flex-wrap:nowrap; overflow-x:auto" in bloc
assert "tiq-serre" not in bloc and "tiq-court" not in bloc
# ---- 4. une seule barre pour les 3 onglets (le meme gabarit, ou qu'on soit)
assert src.count('id="tiq-mode" role="tablist"') == 1
assert "tiq-court" not in app.replace("classList.remove('tiq-court')", "").replace('classList.remove("tiq-court")', "")
print("BARRE DES TENDANCES OK")
