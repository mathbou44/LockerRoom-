"""23 nov 2026 (Mathieu, la nouvelle « Échange majeur » a l'ordi : « c'est tout pogné »). A l'ordi, les nouvelles de l'accueil
ont une hauteur fixe (le bas des tuiles) et 7 rangees de hauteur egale : une rangee de 3 lignes debordait sur ses voisines
(mesure a 1456 x 690 : rangee de 75 px pour 79 px de texte). Une rangee garde la hauteur de son texte, et on n'en montre que
ce qui tient en entier."""
import os, re
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(ICI, "source", "src_app.html"), encoding="utf-8").read()
# la rangee ne retrecit plus sous son contenu
assert "> .acc-news2 > .nl-l > .nl{flex:1 0 auto; min-height:0}" in s and "> .acc-news2 > .nl-l > .nl{flex:1 1 0" not in s
# on cache les dernieres rangees tant que la liste deborde, 3 au moins ; refait quand la fenetre change de taille
i = s.index("function nlAjuster(){"); f = s[i:i + 420]
assert "while (k > 3 && l.scrollHeight > l.clientHeight + 1) R[--k].style.display = 'none'" in f and "R.forEach(r => { r.style.display = ''; })" in f
j = s.index("function rendreNewsListe(){"); g = s[j:j + 5200]
assert "nlAjuster(); requestAnimationFrame(nlAjuster);" in g and "addEventListener('resize'" in g
# la nouvelle WOW garde ses 3 lignes (l'etiquette, le titre, « ses cartes montent souvent »)
assert "${nlWow(n)}</span></button>" in g
print("OK test_nouvelles_rangees")
