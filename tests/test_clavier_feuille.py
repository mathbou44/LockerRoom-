"""26 nov 2026 (Mathieu, capture de la Watchlist : « on voit plus la zone de texte quand on clique pour changer le prix ») : le
clavier de l'iPhone se pose par-dessus le bas de l'ecran, la ou la fenetre est collee : le champ « Ma mise max » etait dessous.
La fenetre monte de la hauteur du clavier (visualViewport -> --clavier)."""
import os, subprocess, json, tempfile
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()
ui = open(os.path.join(RACINE, "ui", "app.html"), encoding="utf-8").read()
i = src.index("const hautClavier = (hEcran, hVisible, haut) =>")
ligne = src[i:src.index("\n", i)]
js = ligne + "\nconsole.log(JSON.stringify([hautClavier(852, 516, 0), hautClavier(852, 852, 0), hautClavier(852, 800, 0), hautClavier(852, 516, 40), hautClavier(852, 476, 40), hautClavier()]));"
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
    f.write(js)
r = subprocess.run(["node", f.name], capture_output=True, text=True, timeout=60)
assert r.returncode == 0, r.stderr[-400:]
o = json.loads(r.stdout)
assert o[0] == 336, "le clavier cache 336 px en bas"
assert o[1] == 0 and o[2] == 0, "pas de clavier ; une barre du navigateur (52 px) n'est pas un clavier"
assert o[3] == 296 and o[4] == 336, "si l'ecran a deja glisse vers le haut (offsetTop), on ne monte que du reste"
assert o[5] == 0
j = src.index("const vv = window.visualViewport; if (!vv) return;", i)
bloc = src[j:src.index("})();", j)]
assert "hautClavier(window.innerHeight, vv.height, vv.offsetTop)" in bloc and "setProperty('--clavier', k + 'px')" in bloc
assert "vv.addEventListener('resize', maj); vv.addEventListener('scroll', maj);" in bloc
assert ".fond-feuille{padding-bottom:var(--clavier, 0px)}" in src, "la fenetre du bas monte au-dessus du clavier"
assert "html.clavier .fond-feuille .feuille{max-height:calc(100vh - var(--clavier, 0px) - 20px); padding-bottom:16px}" in src, "et elle tient dans ce qui reste de l'ecran"
assert "html.clavier .fond-feuille.centre{padding-bottom:calc(16px + var(--clavier, 0px))}" in src
assert 'id="wm-v" type="number" inputmode="decimal"' in src
assert "hautClavier" in ui and "--clavier" in ui, "ui/app.html n'est pas reconstruit"
print("test_clavier_feuille OK")
