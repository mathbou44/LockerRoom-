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
# ... et elle respire : le meme espace dessous (les 1res tuiles) que dessus (la barre) ; avant : 2 px, collee aux tuiles
assert "html body .md-wow{margin:0 0 14px}" in s and re.search(r"\n\.md-barre\{[^}]*margin-bottom:14px", s)
# « et centre My Radar » : le titre au milieu du bouton au cell (marge de gauche = l'engrenage de 30 px + l'espace), a gauche a l'ordi
assert "html body .md-barre .md-glow .md-g-t{flex:1; align-items:center; margin-left:40px}" in s
assert "html:not(.tel-large) body .md-barre .md-glow .md-g-t{flex:0 1 auto; align-items:normal; margin-left:0}" in s
assert re.search(r"\.md-barre \.md-glow \.md-g-eng\{flex:none; width:30px", s), "l'engrenage a change de largeur : revoir la marge du titre"
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
# 6. le Radar ADMIN au cell (Mathieu : « enlever une rangee dans l'entete, reorganiser un peu, et espace egal ») : 2 rangees
#    (onglets + pastille SlabIQ + roue admin ; puis prochain tour, encans, annonces verifiees), 16 px partout
k0 = s.index("html body .d-ligne:has(#d-tour){display:flex; flex-wrap:wrap; align-items:center; gap:8px; margin:0}")
adm = s[k0:s.index("@media (max-width:409px)", k0) + 120]
assert "@media (max-width:699px){" in s[k0 - 40:k0], "seulement au telephone (l'ordi garde sa rangee)"
assert '::after{content:""; order:2; flex:0 0 100%; height:0}' in adm, "la coupure entre les 2 rangees (8 + 0 + 8 = 16 px)"
assert "> .d-onglets, html body .d-ligne:has(#d-tour) > .d-iqp{order:1}" in adm and "> .d-adm-o{order:1; margin-left:auto}" in adm
assert "> #d-tour, html body .d-ligne:has(#d-tour) > #d-enc{order:3}" in adm and "> #d-preuve{order:3; flex:1 1 0; min-width:0}" in adm
assert "html body .ecran:has(#d-tour) .d-barre{margin-top:0}" in adm, "le meme espace avant la recherche"
assert "@media (max-width:409px){ html body .d-ligne:has(#d-tour) > .d-iqp{display:none} }" in s, "sous 410 px la pastille ne tient pas a cote des onglets"
assert re.search(r"\n\.tete-fixe\{display:flex; flex-direction:column; gap:16px\}", s), "l'espace de reference (titre -> onglets) a change : revoir les 16 px"
# l'app construite suit la source
a = open(os.path.join(ICI, "ui", "app.html"), encoding="utf-8").read()
assert 'id="d-iqp"' in a and 'id="md-loupe"' in a and 'id="md-q-x"' in a and 'id="md-iq"' not in a, "reconstruire ui/app.html"
print("OK test_radar_entete (pastille SlabIQ pres des onglets ; Mon radar + loupe + tri ; Voir dans Mon radar ; l'ordi inchange)")
