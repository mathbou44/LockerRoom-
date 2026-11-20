"""Construit le dictionnaire EN d'une app et l'injecte dans son app.html (re-executable).
usage : python3 construire.py lr|hoc [--ecrire]"""
import json, glob, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cores import core
ICI = os.path.dirname(os.path.abspath(__file__))
# 20 nov 2026 (passation vers un autre compte Claude) : marche dans le DEPOT (LockerRoom-/source, i18n, ui) comme dans le
# bac a sable de l'ancien compte (/home/claude/src_app.html, lrtest/)
RACINE = os.path.dirname(ICI)
_depot = os.path.exists(os.path.join(RACINE, 'source', 'src_app.html'))
D = os.path.join(RACINE, 'i18n') if _depot else '/home/claude/lrtest/i18n'
APP = sys.argv[1]
CHEMIN = {'lr': os.path.join(RACINE, 'source', 'src_app.html') if _depot else '/home/claude/src_app.html',
          'hoc': os.path.expanduser('~/mnt/INVENTORY ANALYSIS/ui/app.html')}[APP]
T = {}
for f in sorted(glob.glob(D + '/en_*.json')):
    T.update(json.load(open(f)))
frags = json.load(open(f'{ICI}/{APP}_frag.json')) + json.load(open(f'{ICI}/{APP}_py_frag.json'))
def indexer(v, depart):
    """{} -> {depart}, {depart+1}... ; {k} -> {depart+k}"""
    if re.search(r'\{\d+\}', v):
        return re.sub(r'\{(\d+)\}', lambda m: '{%d}' % (depart + int(m.group(1))), v)
    i = [depart - 1]
    def f(m):
        i[0] += 1; return '{%d}' % i[0]
    return re.sub(r'\{\}', f, v)
def espaces(s):
    s = re.sub(r'(\{\d*\}|\d)\s+%', r'\1%', s)
    return re.sub(r'\s+([?!:;])', r'\1', s).replace('« ', '“').replace('«', '“').replace(' »', '”').replace('»', '”')
def bords(s, depart):
    i = [depart - 1]
    def f(m):
        i[0] += 1; return '{%d}' % i[0]
    return espaces(re.sub(r'\{\}', f, s))
DICO = {}
for p in frags:
    p = re.sub(r'\s+', ' ', p).strip()
    c = core(p)
    if c not in T or not T[c]:
        continue
    DICO[c] = T[c]
    if p == c:
        continue
    k = p.find(c)
    if k < 0:
        continue
    pre, post = p[:k], p[k + len(c):]
    n0, nc = pre.count('{}'), c.count('{}')
    DICO[p] = bords(pre, 0) + indexer(T[c], n0) + bords(post, n0 + nc)
for k, v in [kv for f in ('en_08.json', 'en_09.json') if os.path.exists(D + '/' + f) for kv in json.load(open(D + '/' + f)).items()]:   # mots courts (mois, unites) : toujours
    DICO.setdefault(k, v)
print(APP, 'dictionnaire :', len(DICO), 'entrees', sum(1 for k in DICO if '{}' in k), 'motifs')
if '--ecrire' not in sys.argv:
    sys.exit()
html = open(CHEMIN, encoding='utf-8').read()
coeur = open(f'{ICI}/i18n_core.js', encoding='utf-8').read()
css = open(f'{ICI}/i18n.css', encoding='utf-8').read()
CONF = {'lr': {'taux': '0.70', 'sauter': '.slide-titre, .nom, .titre-carte, .en-titre, script, style, textarea, input, .pref-pop, [data-nt]'},
        'hoc': {'taux': '0.7042', 'sauter': '.slide-titre, .titre-carte, .en-titre, .titre-btn, script, style, textarea, input, .pref-pop, [data-nt]'}}[APP]
coeur = coeur.replace('__APP__', APP).replace('__TAUX__', CONF['taux']).replace('__SAUTER__', CONF['sauter'])
coeur = coeur.replace('/*DICO*/{}/*FIN DICO*/', '/*DICO*/' + json.dumps(DICO, ensure_ascii=False, separators=(',', ':')) + '/*FIN DICO*/')
# 1. retirer une version precedente
html = re.sub(r'/\* I18N DEBUT[\s\S]*?/\* I18N FIN \*/\n?', '', html)
html = re.sub(r'/\* I18N CSS DEBUT[\s\S]*?/\* I18N CSS FIN \*/\n?', '', html)
# 2. dates et nombres dans la langue choisie
html = html.replace("'fr-CA'", 'LOC()')
# 3. montants : conversion + format de la langue
html = re.sub(r"function argent\(v, dec=2\)\{[\s\S]*?\n?\}\n", "function argent(v, dec=2){ const n = nb(v); return n === null ? '—' : fmtMontant(convertir(n), dec); }\n", html, count=1)
html = re.sub(r"function argentCourt\(v\)\{[\s\S]*?\n\}\n", "function argentCourt(v){\n  let n = nb(v); if (n === null) return '—'; n = convertir(n);\n  return Math.abs(n) >= 10000 ? fmtMontant(n / 1000, 1, true) : fmtMontant(Math.round(n), 0);\n}\n", html, count=1)
html = re.sub(r"function argentKpi\(v\)\{[\s\S]*?\n\}\n", "function argentKpi(v){\n  let n = nb(v); if (n === null) return '—'; n = convertir(n);\n  return Math.abs(n) >= 1000 ? fmtMontant(n / 1000, 1, true) : fmtMontant(Math.round(n), 0);\n}\n", html, count=1)
# 3b. virgule decimale seulement en francais (Hall of Cardz)
html = html.replace("const virg = (v) => String(v ?? '').replace('.', ',');", "const virg = (v) => LANGUE === 'en' ? String(v ?? '') : String(v ?? '').replace('.', ',');")
# 4. le bloc i18n en tete du script, la feuille de style a la fin du <style>
i = html.index('<script>') + len('<script>')
html = html[:i] + '\n' + coeur + html[i:]
j = html.index('</style>')
html = html[:j] + css + html[j:]
# 5. la pastille en haut a gauche (ordi : sous le logo du menu ; telephone : barre du haut)
def une_fois(h, avant, apres):
    return h if apres in h else h.replace(avant, apres, 1)
m = re.search(r'<div class="nav-logo">.*?</div>', html)
if m and 'id="nav-pref"' not in html:
    html = html[:m.end()] + '<div class="nav-pref" id="nav-pref"></div>' + html[m.end():]
if APP == 'lr':
    html = une_fois(html, '<section class="ecran choix-mode">', '<section class="ecran choix-mode"><div class="pref-coin">${htmlPref()}</div>')
    # 19 nov 2026 (Mathieu : « l'enlever de la, pas besoin de l'avoir a 2 places ») : a l'ordi, la langue et la devise sont en
    # haut a droite (badge-coin) ; plus dans le menu de gauche
    css_app = ".nav-pref{display:none !important} .pref-coin{align-self:flex-start}\n" + "html[lang=en] body.sandbox::before{content:'SANDBOX eBay \u00b7 test data'}\n"
    js_app = """
// 24 oct 2026 - langue et devise : gardees aussi sur le compte (memes choix sur tous tes appareils) + taux du jour
function prefSauver(l, d){ return API.reglages_sauver({langue:l, devise:d}); }
reglages().then(r => {
  let local = null; try { local = localStorage.getItem('lr_langue'); } catch (e) {}
  if (r && r.langue && !local) {
    try { localStorage.setItem('lr_langue', r.langue); localStorage.setItem('lr_devise', r.devise || 'CAD'); } catch (e) {}
    if (r.langue !== LANGUE || (r.devise || 'CAD') !== DEVISE) location.reload();
  }
}).catch(() => {});
API.taux_change().then(t => { const u = t && nb(t.usd); if (u > 0.4 && u < 1.2) { try { localStorage.setItem('lr_taux', String(u)); } catch (e) {} } }).catch(() => {});
"""
else:
    if 'id="barre-pref"' not in html:
        html = html.replace('<body>', '<body>\n<div class="barre-pref" id="barre-pref"></div>', 1)
    css_app = (".barre-pref{position:sticky; top:0; z-index:30; display:flex; align-items:center; padding:calc(var(--haut) - 6px) 14px 6px;"
               " background:rgba(11,11,12,.9); -webkit-backdrop-filter:blur(12px); backdrop-filter:blur(12px)} .nav-pref{display:none}\n"
               "@media (min-width:900px){ .barre-pref{display:none} .nav-pref{display:flex; padding:0 8px 14px} }\n")
    js_app = ""
html = re.sub(r'/\* I18N APP DEBUT \*/[\s\S]*?/\* I18N APP FIN \*/\n?', '', html)
j = html.index('</style>')
html = html[:j] + '/* I18N APP DEBUT */\n' + css_app + '/* I18N APP FIN */\n' + html[j:]
if js_app:
    k = html.rindex('</script>')
    html = html[:k] + '/* I18N APP DEBUT */' + js_app + '/* I18N APP FIN */\n' + html[k:]
SORTIE = os.path.join(RACINE, 'ui', 'app.html') if _depot else '/home/claude/lrtest/ui/app.html'; os.makedirs(os.path.dirname(SORTIE), exist_ok=True); open(SORTIE, 'w', encoding='utf-8').write(html)
print('ecrit', SORTIE, len(html))
# 13 nov 2026 (vitesse) : la page servie, allegee (commentaires et espaces) ; le source garde tout
import subprocess
if os.environ.get('LR_MINIFIER', '1') != '0':
    subprocess.run(['node', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'minifier.js'), SORTIE], check=True)
