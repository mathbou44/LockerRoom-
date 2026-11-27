"""26 nov 2026, 19 h 10 – 19 h 25 (Mathieu, captures du tableau de bord admin et de « Worth grading » : « les couleurs sont fades,
on doit les mettre dans le meme style que [...] l'accueil » ; « pense toujours Apple iOS, simplifie la section admin au complet » ;
« revoir le layout [...] simple, epure, beau et colore »). L'admin et la liste « A grader » prennent la palette de l'accueil."""
import os, re
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()
app = open(os.path.join(RACINE, "ui", "app.html"), encoding="utf-8").read()
PAL = ("#30D158", "#0A84FF", "#FF9F0A", "#FF375F", "#BF5AF2", "#64D2FF")          # les couleurs systeme d'iOS, celles de l'accueil
bloc = src[src.index("L'admin prend la PALETTE DE L'ACCUEIL"):src.rindex("</style>")]
assert all(c in bloc for c in PAL), "les six couleurs de l'accueil"
# la meme recette que les tuiles de l'accueil : un halo dans le coin, un fond teinte, un contour de la couleur
assert "radial-gradient(120% 90% at 0% 0%, color-mix(in srgb, var(--tt) 34%, transparent), transparent 62%)" in bloc
assert "border-color:color-mix(in srgb, var(--tt) 48%, var(--ligne)) !important" in bloc
# simplifie : plus de MAJUSCULES espacees, plus d'etiquette repetee sur chaque tache, plus de rayures dans les en-tetes
assert "html body .ceo .ceo-k span{" in bloc and "text-transform:none !important" in bloc and "letter-spacing:0 !important" in bloc
assert "html body .ceo .ceo-al-l .ceo-pr{display:none !important}" in bloc
assert "html body .ceo .ceo-c > .ceo-c-t{background:none !important" in bloc
# « A grader » : une tuile par carte, la couleur dit la reponse
assert "const etatG = (x) => x.seuil === 0 ? 'ag-ok' : x.seuil != null ? 'ag-seu' : x.reste9 != null && x.reste10 <= 0 ? 'ag-per' : 'ag-inc';" in src
assert '<button class="tiq-m tiq-mg ${etatG(x)}" data-ag="${i}">' in src
assert ".tiq-mg.ag-ok{--tt:#30D158} .tiq-mg.ag-seu{--tt:#FF9F0A} .tiq-mg.ag-per{--tt:#FF375F} .tiq-mg.ag-inc{--tt:#0A84FF}" in src
# le bloc est le DERNIER du style : il gagne sur les anciennes regles
assert src.rindex("L'admin prend la PALETTE DE L'ACCUEIL") > src.rindex(".ceo-entw-x{")
assert "ag-ok" in app and "--i-vert:#30D158" in app, "l'app servie"
# la prudence d'un prix n'a pas change : aucune couleur ne remplace un chiffre (les classes vert / rouge des chiffres restent)
assert "html body .ceo .ceo-k.vert b{color:var(--i-vert)}" in bloc and "html body .ceo .ceo-k.rouge b{" in bloc
print("test_admin_couleurs OK")
