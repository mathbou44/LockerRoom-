"""26 nov 2026 (Mathieu, capture du Radar apres « Save » dans les Filtres, de « Ending soon » a « Best deal » : « ca enleve la
premiere slab pour mettre la loading bar, c'est pas tres beau ; il faudrait aucune slab, avec un petit SlabCoach qui load ; quand
il a fini de loader, tout apparait »). La cause : la grille etait videe pour y mettre la barre, mais la suite de l'ANCIENNE liste
(30 cartes de plus quand on approche du bas) revenait aussitot se poser a cote. Maintenant : cette suite est arretee, et l'attente
prend toute la grille (le logo SlabCoach au centre, la barre dessous)."""
import os, re, sys
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()
ui = open(os.path.join(RACINE, "ui", "app.html"), encoding="utf-8").read()

# 1. l'attente : le logo SlabCoach (anime) puis la barre avec son pourcentage ; elle prend TOUTE la largeur de la grille
i = src.index("function attenteSC(texte, duree){")
corps = src[i:src.index("\n}", i)]
assert "LOGO_HOLO('sc-att-l', true)" in corps and "barreProg(Date.now(), duree || 8, texte, 'mince')" in corps and 'class="sc-att" role="status"' in corps
assert ".sc-att{grid-column:1 / -1;" in src, "une seule case de la grille ne suffit pas : toute la rangee"
assert "@media (prefers-reduced-motion:reduce){ .sc-att .logo-holo{animation:none} }" in src

# 2. apres « Save » : la suite de l'ancienne liste est arretee AVANT de vider la grille, puis l'attente, puis les nouveaux deals
j = src.index("S.dealsProfil = r || null; sauverDealsF(); MEMO.clear(); fermerFeuille();")
bloc = src[j:src.index("await chargerDeals(true);", j)]
arret, vide = bloc.index("S.dealsReste = []; if (S.obsDeals) S.obsDeals.disconnect();"), bloc.index("zg.innerHTML = attenteSC(tt('On applique tes filtres…', 'Applying your filters…'));")
assert arret < vide, "on arrete la suite avant de vider la grille"
assert '<div class="lecture"><span class="roue"></span>${tt(\'On applique tes filtres…\'' not in src, "plus la barre posee dans la premiere case"

# 3. la suite des deals lit bien ces deux memes variables (sinon l'arret ne servirait a rien)
k = src.index("function suiteDeals(){")
suite = src[k:src.index("\n}", k)]
assert "S.dealsReste.splice(0, PAS_DEALS)" in suite and "S.obsDeals = new IntersectionObserver" in suite and "if (S.obsDeals) S.obsDeals.disconnect();" in suite

# 4. l'app construite porte le changement
assert "attenteSC" in ui and "sc-att" in ui and "S.dealsReste=[]" in ui.replace(" ", ""), "ui/app.html n'est pas reconstruit"
print("test_attente_radar OK")
