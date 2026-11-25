"""24 nov 2026 (Mathieu, deux captures du Profil qui glisse de 16 points : « je ne devrais pas pouvoir bouger l'ecran ») : quand
le Profil depasse l'ecran de peu, il se serre juste assez pour tenir (rangees de 58 a 50 points, jamais sous les 44 d'iOS) ;
s'il depasse de trop meme serre (petit ecran), rien ne change et la page defile. Mesure avec les marges de l'iPhone
(vue/profil.py) : 0 point de trop a 430 x 932, 393 x 852, 390 x 844 et 375 x 812 ; 375 x 667 defile comme avant."""
import os, re, sys
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()
# 1. le serrage est proportionnel (--pk de 0 a 1) et ne touche que le Profil
for regle in ("html body .ecran.reglages #g-pils > .acc-pil{min-height:calc(58px - 8px * var(--pk, 0))",
              "html body .ecran.reglages #g-pils{gap:calc(8px - 3px * var(--pk, 0))",
              "html body .ecran.reglages:has(#g-pils){row-gap:calc(14px - 5px * var(--pk, 0))",
              "@media (max-width:899px){ body:has(.ecran.reglages #g-pils){padding-bottom:calc(96px + var(--bas) - 12px * var(--pk, 0))} }"):
    assert regle in src, regle
assert 58 - 8 >= 44                                                              # une rangee serree reste au-dessus du minimum d'iOS
for m in re.finditer(r"var\(--pk", src):                                         # --pk ne sert que dans des regles du Profil
    debut = src.rfind("\n", 0, m.start())
    assert ".ecran.reglages" in src[debut:m.start()], src[debut:m.start() + 40]
# 2. tenirProfil : rien si tout tient ; rien si ca ne tient pas meme serre ; sinon le plus petit serrage qui tient
i = src.index("function tenirProfil(){")
f = src[i:src.index("\nfunction pastillerReglages(){", i)]
# 24 nov 2026 (soir) : s'il depasse meme serre, un petit telephone plie ses dernieres lignes derriere « Plus »
# (tests/test_profil_petit_ecran.py) ; a l'ordi, il reste comme avant et defile
assert "if (dep(0) <= 0) return;" in f and "if (dep(1) <= 0) { serrer(); return; }" in f and "if (innerWidth >= 900 || L.length < 2) { dep(0); return; }" in f
assert "if (dep(m) > 0) a = m; else b = m;" in f and "dep(b);" in f
assert "R.style.removeProperty('--pk')" in f                                     # hors du Profil : plus de serrage
assert "addEventListener('resize'" in f                                          # l'ecran tourne ou change de taille
j = src.index("function pastillerReglages(){")
assert "setTimeout(tenirProfil, 0)" in src[j:j + 400] and "setTimeout(tenirProfil, 2500)" in src[j:j + 400]
print("OK test_profil_tient")
