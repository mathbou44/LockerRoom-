// 13 nov 2026 (Mathieu : « ameliore la vitesse d'execution ») : app.html allegee pour le telephone : les commentaires et
// les espaces du JavaScript (terser, SANS renommer ni reecrire le code) et les commentaires du CSS. Le source (src_app.html)
// garde tout ; seule la page servie est allegee. Usage : node minifier.js app.html
const fs = require('fs');
let terser; try { terser = require('terser'); } catch (e) { terser = require('/tmp/tersr/node_modules/terser'); }
(async () => {
  const f = process.argv[2]; let h = fs.readFileSync(f, 'utf8'); const avant = h.length;
  const parts = []; let i = 0; const re = /<script(?![^>]*\bsrc=)([^>]*)>([\s\S]*?)<\/script>/g; let m;
  while ((m = re.exec(h))) {
    if (/type=["'](?!text\/javascript|module)/i.test(m[1])) continue;     // JSON, modeles : intouches
    const r = await terser.minify(m[2], {compress: false, mangle: false, format: {comments: false, ascii_only: false}, ecma: 2020});
    if (r.error || r.code == null) throw r.error || new Error('terser');
    parts.push([m.index, m.index + m[0].length, `<script${m[1]}>${r.code}</script>`]);
  }
  for (const [a, b, s] of parts.reverse()) h = h.slice(0, a) + s + h.slice(b);
  h = h.replace(/<style([^>]*)>([\s\S]*?)<\/style>/g, (t, at, css) => `<style${at}>${css.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\n\s*\n+/g, '\n').replace(/^[ \t]+/gm, '')}</style>`);
  fs.writeFileSync(f, h);
  console.log('minifie', avant, '->', h.length);
})().catch(e => { console.error('MINIFIER ECHEC', e.message); process.exit(1); });
