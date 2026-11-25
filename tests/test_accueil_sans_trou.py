"""24 nov 2026 (Mathieu, capture de son iPhone : « encore decale vers le haut, et quand je rafraichis c'est pire ») : la hauteur
de l'accueil se mesurait avec le haut de la barre du bas LU A L'ECRAN, plus le defilement. Pendant le rebond d'iOS ou pendant
que la barre glisse en place, elle sortait trop petite : un trou en bas. Mesure avec Chrome (430 x 932) : barre deplacee de
90 px pendant la mesure -> la hauteur ne change plus (686 px), trou voulu de 18 px."""
import os
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()
i = s.index("function remplirAccTel(){"); f = s[i:s.index("\n}\n", i)]
assert "nav.getBoundingClientRect().top + (scrollY || 0)" not in f                    # l'ancienne mesure
assert "innerHeight - b - nav.offsetHeight" in f and "parseFloat(cs.bottom)" in f     # la place de la barre d'apres sa mise en page
assert "[400, 1200, 2600].forEach" in f and "remplirAccTel.encore" in f               # on remesure une fois l'ecran pose, sans boucle sans fin
assert "if (h > 420) { e.style.minHeight = h + 'px'; e.classList.add('acc-plein'); }" in f
print("OK test_accueil_sans_trou")
