"""23 nov 2026 (Mathieu, fenetre admin « Activite » : « refaire cette page/fenetre, bcp bcp trop long a scroller pour rien »).
A l'ordi, tout tient sur un ecran (mesure a 1456 x 760 : 656 px de contenu, aucun defilement ; avant, le graphique seul
prenait environ 290 px et les 3 classements s'empilaient). Rien n'est enleve : le detail s'ouvre d'un toucher."""
import os
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(ICI, "source", "src_app.html"), encoding="utf-8").read()
i = s.index("async function adminActivite(){"); f = s[i:s.index("async function adminAbonnes(){")]
# les 3 chiffres a cote de la periode ; un graphique de hauteur fixe (il grandissait avec la largeur de la fenetre)
assert 'class="act-tete"' in f and 'class="act-k"' in f
assert 'preserveAspectRatio="none"' in f and ".act-g{width:100%; height:54px" in s and ".act-g{width:100%; height:auto" not in s
# les 3 classements cote a cote, 6 lignes (4 au cell), « Tout voir » pour le reste
assert ".act-cols{display:grid; grid-template-columns:repeat(3, minmax(0, 1fr))" in s and "@media (max-width:900px){ .act-cols{grid-template-columns:1fr}" in s
assert "N_TOP = estBureau() ? 6 : 4" in f and f.count("${col('") == 3 and "data-at=" in f and "S.actTout" in f
# rien n'est enleve : les jamais utilisees et les commentaires par categorie s'ouvrent d'un toucher
assert "d.jamais.length" in f and "<details class=\"act-d\">" in f
assert "data-ac=" in f and "comSel.a_faire" in f and "S.actCom" in f
for lib in ("Actifs aujourd’hui", "Comptes", "Actions", "Personnes actives par jour", "Écrans les plus visités", "Fonctions les plus utilisées", "Les moins utilisées", "Commentaires", "Anonyme"):
    assert lib in f, lib
print("OK test_activite_compacte")
