"""24 nov 2026 (Mathieu, iPhone SE : « si c'est trop serre, cache certaines options dans le menu ; ca doit rester clean ») : sur
un petit telephone (375 x 667), le Profil, Vendre et les Notifications tiennent dans l'ecran. Le Profil plie ses dernieres
lignes derriere une ligne « Plus » (une feuille les montre) : rien ne disparait. Mesure avec Chrome le 24 nov : 0 point de
depassement pour l'Accueil, Vendre, le Profil et les Notifications (avant : 208 au Profil, 80 a Vendre, 42 aux Notifications)."""
import os, re
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()
i = s.index("function tenirProfil(){"); f = s[i:s.index("if (!window.__tenirProfil)", i)]
# 1. l'ordre du pliage : les moins utilisees d'abord ; « Mon compte », « Mes preferences » et « Notifications » ne se plient jamais
assert "const PLIER_PROFIL = ['gg-maj', 'gg-donnees', 'gg-aide', 'gg-boutique'];" in s
for jamais in ("gg-compte", "gg-prefs", "gg-notifs"):
    assert jamais not in s[s.index("const PLIER_PROFIL"):s.index("function tenirProfil(){")]
# 2. toujours idempotent : on deplie tout avant de mesurer (appele 3 fois apres le rendu, et au changement de taille)
assert "$$('.pk-plie', pils).forEach(x => x.classList.remove('pk-plie'));" in f and "if (p0) p0.remove();" in f
# 3. on plie seulement si, serre au maximum, ca depasse encore ; jamais a l'ordi ; jamais pour une seule ligne
assert "if (dep(1) <= 0) { serrer(); return; }" in f and "if (innerWidth >= 900 || L.length < 2) { dep(0); return; }" in f
assert "if (plies.length >= 2 && d.scrollHeight - innerHeight <= 0) break;" in f
# 4. rien ne disparait : la feuille « Plus » montre chaque ligne pliee, et un toucher ouvre la vraie ligne
assert "c.onclick = () => l.click();" in f and "pilAcc('gg-plus', 'trois'" in f and "trois: '<circle" in s
assert "tt('Plus', 'More')" in f and ".pk-plie{display:none !important}" in s
# 5. le point des nouveautes suit la ligne pliee
assert "pn.textContent = neuf.textContent;" in f
# 6. Vendre et les Notifications : plus petits sur un telephone court seulement
assert "@media (max-width:699px) and (max-height:700px){ .ecran.vendre .guide-ph svg{width:84px; height:112px} .notifs .nt-vide:has(.nt-vi){padding-top:44px; padding-bottom:44px} }" in s
u = open(os.path.join(RACINE, "ui", "app.html"), encoding="utf-8").read()
assert "PLIER_PROFIL" in u and "pk-plie" in u and "gg-plus" in u
print("OK test_profil_petit_ecran")
