"""24 nov 2026 (Mathieu, vue Pro, deux captures : « le bouton SlabIQ ne fonctionne pas, et revoir le layout/design de My radar,
c'est laid, ca brise l'experience "Apple" simple et beau »).
1. Les boutons de l'en-tete du Radar (pastille SlabIQ, « x SlabIQ », « ? ») n'etaient branches qu'a la fin de la liste des deals
   (Admin, Platine) : morts pour un compte Gratuit ou Pro. Ils sont branches des l'en-tete.
2. « Ton radar » est bati comme Reglages d'iOS, avec les pieces de la feuille Filtres : des groupes arrondis, une rangee de
   44 points par reglage (le nom a gauche, le choix en gris a droite), le budget dans le menu natif, les alertes en
   interrupteurs, « OK » en haut a droite. Chaque sous-fenetre a le meme cadre : Annuler | son nom | OK.
Mesure (vue/monradar2.py, 430 x 932 et 375 x 667, FR et EN) : chaque fenetre tient sans defiler, rien ne deborde."""
import os, re, sys
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()

# 1. l'en-tete du Radar : branche AVANT la liste, pour toutes les vues
e0 = s.index("const ao_ = $(\"#d-adm-o\")")
ent = s[e0:s.index("await chargerDeals();\n}", e0)]
for b in ("$('#d-x-iq'); if (dxi_) dxi_.onclick = () => { vibrer(); expliquerSlabIQ(); };",
          "$('#d-iqp'); if (dip_) dip_.onclick = () => { vibrer(); expliquerSlabIQ(); };",
          "$('#d-aide'); if (da_) da_.onclick = () => { vibrer(); (comps() ? feuilleAideDeals : expliquerSlabIQ)(); };"):
    assert b in ent, b
ch = s[s.index("async function chargerDeals("):]
assert ch.index("vueMesDeals(z, frais); return;") < ch.index("const dip = $('#d-iqp')")      # la raison : le Radar public sort avant

# 2. « Ton radar »
c0 = s.index("async function configurerRadar(")
cfg = s[c0:s.index("\nconst vignette = ", c0)]
assert "const bas = () => '';" in cfg and "tuto-bas" not in cfg                  # plus de « Fermer » ni de gros bouton en bas
assert "rq-recap" not in cfg and "rq-ck" not in cfg and "Voir mon radar" not in cfg
l0 = cfg.index("h = `<div class=\"io-tete\"><span></span><h3>${tt('Ton radar', 'Your radar')}</h3><button class=\"io-raz io-fin\" id=\"rq-ok\">${tt('OK', 'Done')}</button></div>")
liste = cfg[l0:cfg.index("</div>`;", l0)]
ordre = ["nav('v', tt('Afficher', 'Show')", "nav(0, tt('Joueurs et équipes', 'Players & teams')", "nav(1, tt('Cartes', 'Cards')",
         "ioMenu('rq-bud', tt('Budget par carte', 'Budget per card'), BL, budU)", "<div class=\"io-t\">${tt('Alertes', 'Alerts')}</div>",
         "nav(3, tt('Prix cibles', 'Target prices')", "inter('rq-a1', alm.prix_cible !== false", "inter('rq-a2', !!alm.en_feu", "nav(6, tt('Mes vendeurs eBay', 'My eBay sellers')"]
pos = [liste.index(x) for x in ordre]
assert pos == sorted(pos), pos
assert liste.count('<div class="io-g">') == 4                                    # quatre groupes arrondis
assert "const nav = (k, t, v, plus) => `<button class=\"io-r io-m\" data-aller=\"${k}\"><span class=\"io-l\">${t}${plus || ''}</span><span class=\"io-v\">${v}</span>${IO_FL}</button>`;" in cfg
# le budget et les alertes se reglent dans la liste meme, et sont gardes
assert "ioLier('rq-bud', async (v) => { budget = +v ? Math.round(versCAD(+v) * 100) / 100 : null; await sauverProfil(); });" in cfg
assert "API.alarmes_regler({prix_cible: e.target.checked})" in cfg and "API.radar_alerte_feu(e.target.checked)" in cfg
# un budget hors liste (regle ailleurs) reste montre tel quel, pas « Pas de limite »
assert "const budU = bOpt ? bOpt[0] : (budget ? Math.round(enDev(budget)) : 0);" in cfg and "...(budU ? [budU] : [])" in cfg
# « OK » ferme ; toucher a cote aussi ; on va au Radar seulement si un reglage a change ailleurs
assert "if (i === RECAP) { const ch_ = change; fin(false); if (!o.allerRadar && ch_ && location.hash !== '#deals') location.hash = '#deals'; return; }" in cfg
assert "f.onclick = i === RECAP ? (e) => { if (e.target === f) {" in cfg
assert "if (b.dataset.aller === 'v') { const v = o.voir; fin(false).then(() => { if (v) setTimeout(v, 80); }); return; }" in cfg
# 3. chaque sous-fenetre : Annuler | son nom | OK, et des listes a cocher
assert "h = `<div class=\"io-tete\"><button class=\"io-raz\" id=\"rq-ann\">${tt('Annuler', 'Cancel')}</button><h3>${T_[i] || ''}</h3><button class=\"io-raz io-fin\" id=\"rq-ok\">${tt('OK', 'Done')}</button></div>`" in cfg
assert "<div class=\"tuto quest a rq rq-ios ${i === RECAP ? 'rq-liste' : 'rq-fen'}\">" in cfg
assert "<button class=\"io-r io-m ${co.has(k) ? 'on' : ''}\" data-c=\"${k}\"><span class=\"io-l\">${t}</span>${IO_OK}</button>" in cfg      # Cartes : a cocher
assert "data-b=\"${v}\"><span class=\"io-l\">${v ? '≤ ' + argentCourt(versCAD(v)) : l}</span>${IO_OK}</button>" in cfg                       # Budget : un choix
assert "<form class=\"io-r io-aj\" id=\"rq-cf\">" in cfg and "class=\"io-x\" data-alx=\"${a.id}\"" in cfg                                    # Prix cibles
assert "<label class=\"io-r\"><input class=\"io-in\" data-rv=\"${k}\"" in cfg                                                                # Vendeurs
for k in ("rq-cq", "rq-cp", "rq-q", "rq-seg", "rq-g", "rq-sel"):                 # les champs que les gestes cherchent existent toujours
    assert 'id="%s"' % k in cfg, k
# 4. les styles : les pieces de la feuille Filtres, 44 points par rangee
for regle in (".tuto.rq.rq-ios{align-items:stretch; text-align:left; gap:14px; padding:12px 14px 16px; background:#131317; border-radius:22px}",
              ".io-fin{justify-self:end; font-weight:600;", ".io-ok{flex:none; width:16px; height:12px; color:var(--acc); opacity:0} .io-r.on .io-ok{opacity:1}",
              ".io-r{position:relative; display:flex; align-items:center; gap:10px; min-height:44px;"):
    assert regle in s, regle
assert "const IO_FL = `<svg class=\"io-fl\"" in s and "const IO_OK = `<svg class=\"io-ok\"" in s
print("OK test_radar_ios")
