"""23 nov 2026 (Mathieu, le Radar au cell : « ca fait beaucoup trop d'infos dans l'entete ») : la grosse bande SlabIQ devient
une petite pastille a cote de Mes cibles et Watchlist (elle ne pousse plus rien vers le bas) ; « Voir » entre dans Mon radar
(dehors, c'etait un doublon) ; « Trier » est une petite fleche et la recherche une petite loupe, a droite de Mon radar : la
loupe s'elargit en champ, son x la referme ; la nouvelle WOW reste a sa place. A l'ordi, rien ne change."""
import os, re, sys
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(ICI, "source", "src_app.html"), encoding="utf-8").read()
i = s.index("async function vueMesDeals("); j = s.index("\nfunction ", s.index("rangerRecherche();", i))
vue = s[i:j]
# 1. plus de grosse bande : SlabIQ est une pastille dans la rangee des onglets (Mes cibles, Watchlist), jamais sur la Watchlist
assert 'class="md-iq"' not in s and 'id="md-iq"' not in s, "la grosse bande SlabIQ est revenue"
k = s.index('<div class="d-onglets"'); rangee = s[k:s.index("\n", s.index('id="d-iqp"', k))]
assert rangee.index("#deals/watch") < rangee.index('id="d-iqp"') and "${w ? '' : `<button class=\"d-pil d-iqp\" id=\"d-iqp\"" in rangee
assert "const dip = $('#d-iqp'); if (dip) dip.onclick = () => { vibrer(); expliquerSlabIQ(); };" in s
# 2. la barre : Mon radar, puis la loupe et la fleche de tri (la meme feuille que « Trier » a l'ordi)
b0 = vue.index('<div class="md-barre">'); barre = vue[b0:vue.index("</div>`", b0) if "</div>`" in vue[b0:b0 + 3000] else b0 + 3000]
assert barre.index('id="md-cfg"') < barre.index('id="md-loupe"') < barre.index('id="md-t2"'), "Mon radar, loupe, tri : dans cet ordre"
assert "const mt2 = $('#md-t2', z); if (mt2) mt2.onclick = trier;" in vue and "const mt = $('#md-t', z); if (mt) mt.onclick = trier;" in vue
# 3. la recherche : fermee au cell (avant la barre, qu'elle remplace), ouverte par la loupe, refermee et videe par son x
assert vue.index('class="tiq-rech md-rech"') < b0 and 'id="md-q-x"' in vue[:b0]
assert "class=\"md${String(S.mdQ || '').trim() ? ' rech' : ''}\"" in vue, "une recherche en cours reste visible"
assert "if (lp) lp.onclick = () => { vibrer(); ouvrir(true, true); };" in vue
assert "q.value = ''; S.mdQ = ''; S.mdMax = 40; peindre(); } ouvrir(false); };" in vue
assert "html body .md > .md-rech{display:none" in s and "html body .md.rech > .md-rech{display:flex" in s and "html body .md.rech > .md-barre{display:none}" in s
# la nouvelle WOW reste sous la barre, et « Voir ses cartes » ouvre le champ (sinon le filtre serait invisible)
w0 = s.index("async function wowRadar("); wowf = s[w0:s.index("\n}", w0)]
assert "barre.after(b)" in wowf and "md._rech(true, false)" in wowf
# 4. « Voir » vit dans Mon radar : la 1re rangee de la fenetre ouvre la meme feuille qu'avant
assert "voir: nb_ ? () => ouvrirVoir() : null" in vue and "const ouvrirVoir = () => { choix(tt('Voir', 'Show')," in vue
c0 = s.index("async function configurerRadar(") if "async function configurerRadar(" in s else s.index("function configurerRadar(")
cfg = s[c0:s.index("\nfunction ", c0 + 50) if "\nfunction " in s[c0 + 50:] else len(s)]
r0 = cfg.index('<div class="liste rq-recap">')
assert cfg.index("ligne('v', tt('Afficher', 'Show')", r0) < cfg.index("ligne(0, tt('Joueurs et équipes'", r0)
assert "if (b.dataset.aller === 'v') { const v = o.voir; fin(false).then(() => { if (v) setTimeout(v, 80); }); return; }" in cfg
# 5. a l'ordi (la meme condition que rangerRecherche) : les 3 menus restent, pas de pastille, de loupe ni de x
m0 = s.index("html:not(.tel-large) body .d-iqp, html:not(.tel-large) body .md-ic, html:not(.tel-large) body .md-rech-x{display:none !important}")
assert "@media (min-width:1100px) and (min-height:640px){" in s[m0 - 60:m0]
assert "html:not(.tel-large) body .md-barre > .md-dd{display:flex !important}" in s[m0:m0 + 700]
assert "matchMedia('(min-width:1100px) and (min-height:640px)')" in s[s.index("function rangerRecherche("):s.index("function rangerRecherche(") + 300]
# l'app construite suit la source
a = open(os.path.join(ICI, "ui", "app.html"), encoding="utf-8").read()
assert 'id="d-iqp"' in a and 'id="md-loupe"' in a and 'id="md-q-x"' in a and 'id="md-iq"' not in a, "reconstruire ui/app.html"
print("OK test_radar_entete (pastille SlabIQ pres des onglets ; Mon radar + loupe + tri ; Voir dans Mon radar ; l'ordi inchange)")
