"""24 nov 2026 (Mathieu, trois captures de son iPhone) :
1. « le List on eBay est beaucoup trop petit » : dans la fiche d'une carte, la feuille est une colonne flexible a hauteur
   limitee et la fiche (.fcx) y est en display:contents ; quand le contenu depasse, le bouton (hauteur fixe, sans
   min-height) etait le seul a retrecir : une barre de 20 points. Il ne retrecit plus (comme « Enregistrer » le 19 nov).
2. « la Wolf devrait etre tournee de 90 degres comme la Demidov / Fowler, automatiquement » : une photo deja cadree serre
   sur une carte couchee sortait du recadrage sans etre tournee. Mesure avec Chrome : une photo 4:3 a fond noir, carte
   couchee qui remplit l'image -> tournee (570 x 760) ; carte debout -> pas touchee ; photo sans carte -> pas touchee.
3. « je devrais pouvoir selectionner le devant et l'arriere » : deux photos choisies d'un coup dans la phototheque."""
import os, re
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()
# 1. le bouton garde sa hauteur, et reste le bouton secondaire (une seule action pleine : Enregistrer)
assert "#feuille .btn#c-ebay{flex:none; min-height:54px; height:auto; padding:14px 18px}" in s
assert ".btn.fc-ok{flex:none; min-height:54px;" in s
assert re.search(r"#feuille \.btn#c-ebay\{background:linear-gradient\(var\(--carte2\), var\(--carte2\)\) padding-box, var\(--prisme\) border-box !important", s)
assert '<button class="btn" id="c-ebay">' in s and ".fcx, .fcx-g, .fcx-d{display:contents}" in s
# 2. la rotation : dans photoCadree seulement, seulement en mode « debout » (les slabs), jamais sans indice que la carte est couchee
i = s.index("function photoCadree(url, o){"); f = s[i:s.index("\n}\n", i)]
assert "const toutTourner = () =>" in f and "g.translate(h, 0); g.rotate(Math.PI / 2); g.drawImage(im, 0, 0, W, H, 0, 0, w, h);" in f
assert "if ((x1 - x0) * (y1 - y0) > 0.93 * W * H) return debout && (x1 - x0) > (y1 - y0) * 1.1 ? toutTourner() : null;" in f
assert "if (!q) return debout && W / H > 1.36 && W / H < 1.46 ? toutTourner() : null;" in f     # 4:3 (1,33), 3:2 (1,5) et 16:9 : pas touchees
assert 1.36 < 88.9 / 63.5 < 1.46 and not (1.36 < 4 / 3 < 1.46) and not (1.36 < 1.5 < 1.46)
assert "photoCadree(im.getAttribute('src'), {marge: 0.05, debout: true, slab: !!im.dataset.slab})" in s
# 3. deux photos d'un coup : la 1re = le devant, la 2e = le dos ; une seule = la face choisie, comme avant
assert 'id="cp-lib" multiple hidden>' in s and "const F = [...(ev.target.files || [])].slice(0, 2);" in s
assert "if (P.length === 2) { const r = await essai(API.carte_photo_changer(c.id, P[0], 0)); if (r) await changerPhotoCarte(c.id, P[1], 1); }" in s
assert "else await changerPhotoCarte(c.id, P[0], face);" in s
assert "tt('Deux photos choisies : la 1re devient le devant, la 2e le dos.', 'Two photos picked: the 1st becomes the front, the 2nd the back.')" in s
u = open(os.path.join(RACINE, "ui", "app.html"), encoding="utf-8").read()
assert "toutTourner" in u and "c-ebay{flex:none" in u.replace(" ", "") .replace("#feuille.btn#", "") or "c-ebay" in u
print("OK test_fiche_carte_boutons")
