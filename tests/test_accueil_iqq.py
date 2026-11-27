"""27 nov 2026 (Mathieu, 12 h 41 : « quand je change de page puis je reviens sur Home, SlabIQ asks n'arrete pas d'apparaitre et
disparaitre ; s'il n'y a rien, elle devrait juste pas s'afficher » ; 12 h 42 : « On Fire devrait etre vert vu que c'est une nouvelle
positive ; on peut la confondre avec une nouvelle negative a cause que c'est rouge »). Mesure dans un vrai navigateur (390 x 844) :
sans question, la tuile n'apparait jamais (ni a la 1re visite, ni au retour) ; avec 3 questions, elle reste au retour.
python tests/test_accueil_iqq.py"""
import os, re, subprocess, json
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()
# ---- 1. la tuile : dessinee seulement si le dernier compte connu a des questions ; plus jamais « … »
assert "admin && iqqN() > 0 ? tuileFT('ft-iqq', 'conseils', tt('SlabIQ demande', 'SlabIQ asks'), String(iqqN())" in src
assert "tuileFT('ft-iqq', 'conseils', tt('SlabIQ demande', 'SlabIQ asks'), '…'" not in src
m = re.search(r"function iqqN\(n\)\{.*?\n", src)
JS = "const S = {}; let st = {}; globalThis.localStorage = {getItem: k => k in st ? st[k] : null, setItem: (k, v) => { st[k] = String(v); }};\n" + m.group(0) + """
const a = iqqN(); iqqN(4); const b = iqqN(); iqqN(0); const c = iqqN();
globalThis.localStorage = {getItem: () => { throw new Error('prive'); }, setItem: () => { throw new Error('prive'); }};
console.log(JSON.stringify([a, b, c, iqqN(), iqqN(2)]));"""
assert json.loads(subprocess.run(["node", "-e", JS], capture_output=True, text=True, check=True).stdout) == [0, 4, 0, 0, 2]
assert "const n = +q.n || 0, avant = iqqN(); iqqN(n);" in src and "if (n && !avant && (location.hash || '#accueil').startsWith('#accueil')) route();" in src
# ---- 2. « En feu » : vert partout (une nouvelle positive), jamais rouge
assert "en_feu: [tt('En feu', 'On fire'), 'rouge'" not in src and src.count("en_feu: [tt('En feu', 'On fire'), 'vert'") == 8
assert "['en_feu', tt('En feu', 'On fire'), 'rouge'" not in src and "kp('en_feu', tt('en feu cette semaine', 'on fire this week'), 'vert')" in src
assert "<b class=\"${k === 'recrue' ? 'or' : 'vert'}\">${r.compte[k]}</b>" in src
print("ACCUEIL ET EN FEU OK")
