"""27 nov 2026 (Mathieu, capture de la fiche de Yurov a l'ordi, 1377 x 841 : « devrait pas avoir de scroll bar » ; les tuiles
Joueur / Vendeur etaient coupees). La fiche d'une annonce a l'ordi : la photo et les actions a gauche, l'info a droite ; ce
sont les photos des ventes qui cedent la place ; plus aucune barre. Au telephone : rien ne change.
Mesure dans un vrai navigateur le 27 nov (8 tailles de 1024 x 640 a 1920 x 1080, FR et EN, cas plein et cas simple) : 0 px de
trop partout.   python tests/test_fiche_ordi.py"""
import os, re
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()
app = open(os.path.join(RACINE, "ui", "app.html"), encoding="utf-8").read()

# ---- 1. le gabarit de la fiche admin / Platine : l'info dans .fb-dr, les actions dans .fb-ac, dans le MEME ordre qu'avant
i = src.index('f.innerHTML = `<div class="fen fa fb fb-adm"'); FIN = "</span></div></div></div>`;"
g = src[i:src.index(FIN, i) + len(FIN)]
assert g.count('<div class="fb-dr">') == 1 and g.count('<div class="fb-ac">') == 1
ordre = ['<div class="fb-top">', '<div class="fb-nom">', '<div class="fb-dr">', 'faVerdict(', 'bandeTend(', 'blocMesAchats(', '<div class="fa-ventes">', '<div class="grd-z"',
         '</div></div>\n      <div class="fb-ac">', '<div class="fa-btns">', 'blocAutres(base)', 'proChips(a)', '<div class="fa-bas">']
pos = [g.index(x) for x in ordre]
assert pos == sorted(pos), list(zip(ordre, pos))
# les balises se ferment bien : .fb-dr avant .fb-ac, puis .fb-ac et la fiche a la toute fin
assert g.index('<div class="fb-ac">') > g.index('<div class="grd-z"') and '<div class="fb-ac">' not in g[:g.index('<div class="grd-z"')]

# ---- 2. au telephone : les deux groupes ne comptent pas (leurs enfants restent les enfants de la fiche)
assert "\n.fb-dr, .fb-ac{display:contents}" in src

# ---- 3. a l'ordi : la grille, les ventes qui cedent, plus de barre
i = src.index("@media (min-width:1000px){\n  .fen.fen.fen.fa.fb.fb-adm{width:min(1080px, 94vw)"); c = src[i:src.index("\n}\n", i)]
for bout in ("grid-template-rows:auto auto minmax(0,1fr) auto", "max-height:calc(100dvh - 40px) !important", "scrollbar-width:none",
             ".fb-ph{grid-column:1; grid-row:1 / span 3; align-self:stretch; height:auto !important", "contain:size",
             "> .fb-dr{grid-column:2; grid-row:3 / span 2; min-width:0; min-height:0; display:flex; flex-direction:column",
             "> .fb-ac{grid-column:1; grid-row:4;", ".fb-dr > *, .fen.fen.fen.fa.fb.fb-adm .fb-ac > *{margin-top:0; margin-bottom:0; flex-shrink:0}",
             ".fb-dr > .fa-ventes{flex:0 1 auto; min-height:104px", ".fa-car .fv-ph{flex:0 1 118px; height:auto; min-height:44px", ".fa-pq{display:none}",
             "::-webkit-scrollbar, .fen.fen.fen.fa.fb.fb-adm > .fb-dr::-webkit-scrollbar{display:none}", ".fb-ac .fb-aut{position:relative; order:-1}",
             ".fb-aut[open] .fb-aut-l{position:absolute"):
    assert bout in c, bout
# la photo ne peut jamais demander plus que la place qui reste (sinon elle passerait sous les actions)
assert "min-height:min(520px, calc(100dvh - 340px))" in c
# fenetre basse : memes blocs, plus serres
assert "@media (min-width:1000px) and (max-height:800px){" in src

# ---- 4. la fiche Pro a l'ordi : deux colonnes aussi, les memes blocs (aucun prix de plus)
i = src.index("@media (min-width:1000px){\n  html body .fen.fen.fen.fa.fa-pub.fb{"); p = src[i:src.index("\n}\n", i)]
for bout in ("grid-template-columns:minmax(0,0.8fr) minmax(0,1.2fr)", "overflow:hidden auto !important; scrollbar-width:none", "> .fb-top{display:contents}",
             ".fb-ph{grid-column:1; grid-row:1 / span 30; align-self:stretch", "> *:not(.fb-top):not(.fen-x){grid-column:2", "> .fb-nom{grid-row:1"):
    assert bout in p, bout
i = src.index('f.innerHTML = `<div class="fen fa fa-pub fb"'); gp = src[i:src.index("$$('.fen-vigs [data-ph]', f)", i)]
for interdit in ("d.valeur", "fa-ventes", "mise_max", "maxA", "gainAff"):
    assert interdit not in gp, interdit                    # licence eBay : la fiche publique ne montre aucun prix derive

# ---- 5. tout est dans l'app construite
for bout in ('class="fb-ac"', ".fb-dr,.fb-ac{display:contents}", "grid-template-rows:auto auto minmax(0,1fr) auto"):
    assert bout in app or bout.replace(",.", ", .") in app, bout
print("FICHE ORDI OK")
