"""24 nov 2026 (Mathieu, captures de son iPhone) :
1. Bilan : « revois le design de cette page, elle semble vieille ; elle doit tenir sur une page comme toutes les autres ».
   Un chiffre en grand (le profit net), trois reperes, « ou va ton argent » en lignes serrees, une action pleine, deux liens.
   Mesure avec Chrome : 0 point de depassement a 430 x 932, 393 x 852 et 375 x 667 (avant : la page defilait de plus d'un ecran).
2. Grille de centrage : « je peux bouger toute la page et le Save est trop bas ; tout doit tenir dans un ecran ; le texte
   explicatif derriere un point d'interrogation ». Mesure : aucun defilement, ni haut-bas ni gauche-droite, « Enregistrer »
   visible (carte debout et couchee, aux trois tailles)."""
import os
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()
# -- le Bilan
assert '<section class="ecran bil bil2">' in s and 'class="b2-heros"' in s and 'class="b2-3"' in s
assert "tt('Profit net', 'Net profit')" in s and "rep3(argentKpi(b.revenus), tt('Ventes', 'Sales'))" in s
assert 'class="btn b2-go" href="#ventes/' in s and 'class="b2-liens ph-liens"' in s
assert s.count('id="b-dep"') == 2 and s.count('id="b-csv"') == 2            # etat vide et etat plein : les deux boutons existent toujours
assert "$('#b-dep').onclick = feuilleDepense;" in s and "const sc = $('#b-sc');" in s
assert "tt('Frais eBay', 'eBay fees')" in s and "tt('Autres', 'Other')" in s  # une ligne chacun, jamais deux
assert '<p class="bil-ph">' not in s and 'class="bil-ks"' not in s            # l'ancienne phrase et les 4 tuiles ne reviennent pas
for palier in ("(max-width:699px) and (max-height:880px)", "(max-width:699px) and (max-height:700px)"):
    assert palier in s, palier
# le profit reste le chiffre du serveur : l'ecran ne recalcule rien
i = s.index('<div class="b2-heros">'); assert "argent(Math.abs(b.profit), 0)" in s[i:i + 400]
# -- la grille de centrage
assert "o.classList.toggle('cg-aide-on', !!aide);" in s and '<div class="sous cg-expl">' in s
assert ".vd.cg:not(.cg-aide-on) .cg-expl{display:none}" in s and ".vd.cg{overflow-x:hidden;" in s
assert "--cgh:calc(100dvh - env(safe-area-inset-top) - env(safe-area-inset-bottom) - 352px)" in s
assert ".vd.cg:not(.cg-aide-on) .env-b{margin-top:auto}" in s
u = open(os.path.join(RACINE, "ui", "app.html"), encoding="utf-8").read()
assert "b2-heros" in u and "cg-aide-on" in u
print("OK test_bilan_grille_un_ecran")
