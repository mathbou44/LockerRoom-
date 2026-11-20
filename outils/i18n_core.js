/* I18N DEBUT - 24 oct 2026 (Mathieu : « mettre l'option anglais et francais en haut a gauche de l'ecran avec les
   devises aussi ») : langue (FR / EN) et devise ($ CA / $ US), en haut a gauche. Les textes sont traduits a
   l'ecran par un dictionnaire (genere depuis i18n/en_*.json : ne pas editer a la main ici) ; les montants
   sont convertis au taux du jour. Le choix est garde dans ce navigateur. */
const I18N_APP = '__APP__';
let LANGUE = 'fr', DEVISE = 'CAD', TAUX_USD = __TAUX__;
try {
  const nav = (navigator.language || '').toLowerCase();
  LANGUE = localStorage.getItem(I18N_APP + '_langue') || (nav.startsWith('en') ? 'en' : 'fr');
  DEVISE = localStorage.getItem(I18N_APP + '_devise') || (nav === 'en-us' ? 'USD' : 'CAD');
  const t = parseFloat(localStorage.getItem(I18N_APP + '_taux')); if (t > 0.4 && t < 1.2) TAUX_USD = t;
} catch (e) {}
document.documentElement.lang = LANGUE;
function LOC(){ return LANGUE === 'en' ? 'en-CA' : 'fr-CA'; }
function convertir(n){ return DEVISE === 'USD' ? n * TAUX_USD : n; }
// n deja converti ; k = en milliers (12,4 k$ / $12.4k)
const FMT_M = new Map();
function fmtMontant(n, dec, k){
  const moins = n < 0 ? '-' : '', a = Math.abs(n);
  // 4 nov 2026 (vitesse) : un formateur par (langue, decimales), pas un nouveau a chaque montant (1 500 tuiles)
  const kf = LOC() + '|' + (k ? 'k' : dec);
  let F = FMT_M.get(kf);
  if (!F) { F = new Intl.NumberFormat(LOC(), k ? {maximumFractionDigits:1} : {minimumFractionDigits:dec, maximumFractionDigits:dec}); FMT_M.set(kf, F); }
  const chiffre = F.format(a);
  if (LANGUE === 'en') return moins + (DEVISE === 'USD' ? 'US$' : '$') + chiffre + (k ? 'k' : '');
  return moins + chiffre + (k ? '\u00a0k$' : '\u00a0$') + (DEVISE === 'USD' ? '\u00a0US' : '');   // 9 nov 2026 : le $ ne part jamais seul a la ligne
}
const DICO_EN = /*DICO*/{}/*FIN DICO*/;
const I18N = (() => {
  if (LANGUE !== 'en') return {tr: (s) => s};
  const exact = new Map(), motifs = [];
  const rx = (p) => p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  for (const [k, v] of Object.entries(DICO_EN)) {
    if (!k.includes('{}')) { exact.set(k, v); continue; }
    const parts = k.split('{}');
    const lit = parts.map(x => x.trim()).reduce((a, b) => b.length > a.length ? b : a, '');
    if (lit.replace(/[^A-Za-zÀ-ÿ]/g, '').length < 3) continue;          // trop vague : jamais
    motifs.push({re: new RegExp('^' + parts.map(rx).join('([\\s\\S]*?)') + '$'), lit, v, poids: k.replace(/\{\}/g, '').length});
  }
  motifs.sort((a, b) => b.poids - a.poids);
  const BORD = /^([\s\d.,:;·•\-–—+−~≈%$\/()#×?!…»«'’"|[\]]*)([\s\S]*?)([\s\d.,:;·•\-–—+−~≈%$\/()#×?!…»«'’"|[\]]*)$/;
  const espaces = (s) => s.replace(/(\d)\s+%/g, '$1%').replace(/\s+([?!:;])/g, '$1').replace(/«\s*/g, '“').replace(/\s*»/g, '”');
  const cache = new Map();
  function remplir(v, g, prof){ let i = 0; return v.replace(/\{(\d*)\}/g, (_, d) => { const x = g[d === '' ? i++ : +d]; return x === undefined ? '' : tr(x, prof + 1); }); }
  function tr(s, prof = 0){
    if (s && !prof && /\d\s%/.test(s)) s = s.replace(/(\d)\s+%/g, '$1%');
    if (s && /^\s*\d+\s?j(\s+\d+\s?(h|min))?\s*$/.test(s)) return s.replace(/(\d)\s?j\b/, '$1 d');   // durees : 1 j 2 h -> 1 d 2 h
    if (!s || prof > 3 || !/[A-Za-zÀ-ÿ]{2}/.test(s)) return s;
    if (!prof && cache.has(s)) return cache.get(s);
    const m = s.match(/^(\s*)([\s\S]*?)(\s*)$/), t = m[2].replace(/\s+/g, ' ');
    let out = exact.get(t);
    if (out === undefined) { const b = t.match(BORD); if (b && b[2] && b[2] !== t) { const x = exact.get(b[2]); if (x !== undefined) out = espaces(b[1]) + x + espaces(b[3]); } }
    const essai = (x) => { for (const p of motifs) { if (p.lit && !x.includes(p.lit)) continue; const g = x.match(p.re); if (g) return remplir(p.v, g.slice(1), prof); } };
    if (out === undefined) out = essai(t);
    if (out === undefined) { const b = t.match(BORD); if (b && b[2] && b[2] !== t) { const x = essai(b[2]); if (x !== undefined) out = espaces(b[1]) + x + espaces(b[3]); } }
    if (out === undefined && t.includes(' · ')) { const a = t.split(' · '), b = a.map(x => tr(x, prof + 1)); if (b.some((x, i) => x !== a[i])) out = b.join(' · '); }
    const r = out === undefined ? s : m[1] + out + m[3];
    if (!prof) cache.set(s, r);
    return r;
  }
  const SAUTER = '__SAUTER__', ATTRS = ['placeholder', 'title', 'aria-label', 'alt'];
  function noeud(root){
    if (!root) return;
    if (root.nodeType === 3) { const p = root.parentElement; if (p && !p.closest(SAUTER)) { const v = root.nodeValue, x = tr(v); if (x !== v) root.nodeValue = x; } return; }
    if (root.nodeType !== 1 || root.closest('.pref-pop, [data-nt]')) return;
    for (const el of [root, ...root.querySelectorAll('[placeholder],[title],[aria-label],[alt]')]) for (const a of ATTRS) {
      const v = el.getAttribute(a); if (v && !el.closest('.pref-pop, [data-nt]')) { const x = tr(v); if (x !== v) el.setAttribute(a, x); }
    }
    if (root.closest(SAUTER)) return;
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) { const p = n.parentElement; if (!p || p.closest(SAUTER)) continue; const v = n.nodeValue, x = tr(v); if (x !== v) n.nodeValue = x; }
  }
  const file = new Set(); let prevu = false;
  const ajouter = (ms) => { for (const m of ms) { if (m.type === 'childList') m.addedNodes.forEach(n => file.add(n)); else file.add(m.target); } };
  const obs = new MutationObserver((ms) => {
    ajouter(ms);
    if (prevu) return; prevu = true;
    // 4 nov 2026 (revue) : les changements arrives entre-temps sont pris (takeRecords) avant de debrancher, pas perdus
    queueMicrotask(() => { prevu = false; ajouter(obs.takeRecords()); obs.disconnect(); const f = [...file]; file.clear(); f.forEach(n => { if (n.isConnected) noeud(n); }); brancher(); });
  });
  const brancher = () => obs.observe(document.body, {childList:true, subtree:true, characterData:true, attributes:true, attributeFilter:ATTRS});
  const go = () => { noeud(document.body); brancher(); };
  if (document.body) go(); else document.addEventListener('DOMContentLoaded', go);
  return {tr};
})();
// -- la pastille Langue / Devise (en haut a gauche) --
function libDevise(d){ return d === 'USD' ? (LANGUE === 'en' ? 'US$' : '$ US') : (LANGUE === 'en' ? 'CA$' : '$ CA'); }
function htmlPref(){ return `<button class="pref" data-pref aria-label="Langue et devise / Language and currency"><span class="pref-g">${LANGUE === 'en' ? 'EN' : 'FR'}</span>${libDevise(DEVISE)}</button>`; }
document.addEventListener('click', (e) => { const b = e.target.closest && e.target.closest('[data-pref]'); if (b) { e.preventDefault(); e.stopPropagation(); ouvrirPref(b); } }, true);
function ouvrirPref(b){
  let p = document.getElementById('pref-pop'); if (p) { p.remove(); return; }
  p = document.createElement('div'); p.id = 'pref-pop'; p.className = 'pref-pop';
  const t = TAUX_USD.toLocaleString(LOC(), {minimumFractionDigits:2, maximumFractionDigits:3});
  p.innerHTML = `<div class="pref-l">Langue · Language</div>
    <div class="pref-seg">${[['fr', 'Français'], ['en', 'English']].map(([k, n]) => `<button data-l="${k}" class="${LANGUE === k ? 'on' : ''}">${n}</button>`).join('')}</div>
    <div class="pref-l">Devise · Currency</div>
    <div class="pref-seg">${[['CAD', 'CA$ · CAD'], ['USD', 'US$ · USD']].map(([k, n]) => `<button data-d="${k}" class="${DEVISE === k ? 'on' : ''}">${n}</button>`).join('')}</div>
    <div class="pref-n">1 CAD = ${t} USD</div>`;
  document.body.appendChild(p);
  const r = b.getBoundingClientRect();
  p.style.top = Math.round(r.bottom + 8) + 'px'; p.style.left = Math.max(8, Math.round(r.left)) + 'px';
  const choisir = (l, d) => {
    try { localStorage.setItem(I18N_APP + '_langue', l); localStorage.setItem(I18N_APP + '_devise', d); } catch (e) {}
    const tem = fetch('/langue?l=' + l, { method: 'POST', credentials: 'same-origin' }).catch(() => {});   // temoin HttpOnly
    if (typeof prefSauver === 'function') { Promise.all([tem, prefSauver(l, d)]).catch(() => {}).finally(() => location.reload()); } else tem.finally(() => location.reload());
  };
  p.querySelectorAll('[data-l]').forEach(x => x.onclick = () => choisir(x.dataset.l, DEVISE));
  p.querySelectorAll('[data-d]').forEach(x => x.onclick = () => choisir(LANGUE, x.dataset.d));
  setTimeout(() => document.addEventListener('click', function f(e){ if (!p.contains(e.target)) { p.remove(); document.removeEventListener('click', f); } }), 0);
}
(() => { for (const id of ['nav-pref', 'barre-pref']) { const z = document.getElementById(id); if (z) z.innerHTML = htmlPref(); } })();
/* I18N FIN */
