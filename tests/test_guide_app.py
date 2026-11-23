"""23 nov 2026 (Mathieu : « le plus simple et efficace pour aider les nouveaux utilisateurs a comprendre tout ce que l'app fait ») :
« Que veux-tu faire ? » : UNE fenetre, une ligne par besoin, un toucher mene a la bonne page. Montree une fois au nouveau compte
(apres ses 3 questions), puis toujours a un toucher (le « ? » en haut a gauche au cell, dans la barre de cote a l'ordi, et
Profil › Le tour de l'app). 40 mots au plus (docs/GUIDE_ACCROCHE.md), chaque page existe, et l'ancien tour en 8 ecrans est parti."""
import os, re, sys
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ICI)
s = open(os.path.join(ICI, "source", "src_app.html"), encoding="utf-8").read()
i = s.index("const GUIDE_APP = () => {"); j = s.index("function guideAppAuto(", i)
bloc = s[i:j]
L = re.findall(r"\['(\w+)', '(\w+)', tt\('([^']*)', '([^']*)'\), (.*?), '(#\w+)'\]", bloc)
assert len(L) == 7, len(L)
# chaque ligne mene a un ecran qui existe (la table des vues) ; « alertes » et « iq » en font partie
vues = re.search(r"const vues = \{([^}]*)\}", s).group(1)
for k, ic, fr, en, page, h in L:
    assert re.search(r"\b%s:" % h[1:], vues), (k, h)
    assert re.search(r"\b%s:\s*'<" % ic, s), ("icone inconnue", ic)
    assert 2 <= len(fr.split()) <= 6 and 2 <= len(en.split()) <= 6, ("2 a 6 mots par ligne", fr, en)
# 40 mots au plus dans la fenetre : le titre, les 7 besoins et le nom des 7 pages
mots = len("Que veux-tu faire ?".split()) + sum(len(x[2].split()) for x in L) + 7
assert mots <= 40, mots
assert "tt('Que veux-tu faire ?', 'What do you want to do?')" in bloc and "popOuvrir(" in bloc
# sa 1re ligne suit son but (collection, breaks ; sinon le Radar)
assert "{collection: 'collection', breaks: 'breaks'}[(S.reglages || {}).objectif] || 'radar'" in bloc
# une fois par compte : le reglage existe cote serveur, et le guide ne s'ouvre jamais par-dessus autre chose
import lockerroom
assert "guide_app" in lockerroom.REGLAGES_DEFAUT and lockerroom.REGLAGES_DEFAUT["guide_app"] == 0
auto = s[j:s.index("document.addEventListener('click'", j)]
assert "guide_app" in auto and "sc_guide_app" in auto and "$('#pop-fond')" in auto and "S.questionOuvert" in auto and "surAccueil()" in auto
assert "questionnaireProfil(() => { chargerConseils(true); setTimeout(guideAppAuto, 500); })" in s
# toujours a un toucher : le « ? » du haut (cell), celui de la barre de cote (ordi), Profil › Le tour de l'app
# 23 nov 2026 (Mathieu : « tout semble trop decale vers le haut ») : le « ? » garde la case de 44 px de l'ancienne place vide ; avec la
# classe « rond » (36 px dans la barre), la barre du haut perdait 8 px et tout l'ecran montait
assert 'class="rond haut-plus haut-aide"' not in s and re.search(r"html body \.haut-aide\{[^}]*width:44px; height:44px", s)
assert 'class="haut-plus haut-aide" data-guide' in s and 'class="nav-aide" data-guide' in s and "$('#g-tour').onclick = () => guideApp();" in s
assert ":not(.nav-aide)" in s, "le « ? » de l'ordi ne compte pas parmi les onglets du cell"
assert "closest('[data-guide]')" in s
# l'ancien tour en 8 ecrans n'existe plus
assert not re.search(r"(?<![A-Z_])TUTO\[|function tutoriel\(|tutoriel\(", s)
# la page construite le contient
a = open(os.path.join(ICI, "ui", "app.html"), encoding="utf-8").read()
assert "data-guide" in a and "Que veux-tu faire" in a and "What do you want to do?" in a
print("OK test_guide_app (%d lignes, %d mots)" % (len(L), mots))
