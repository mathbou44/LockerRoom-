"""23 nov 2026 (Aikido, critique : « Using Pickle can lead to remote code execution ») : lire un fichier pickle, c'est executer
ce qu'il contient. Le 20 nov, outils/banc_valeur.py et outils/radar_iq.py sont passes au JSON ; les 22-23 nov, 34 scripts de
recherche l'avaient ramene. Regle : AUCUN pickle (ni pandas read_pickle / to_pickle, ni shelve, marshal, dill, joblib) dans le
code du depot. Les fichiers de travail de la recherche passent par outils/recherche/cache_recherche.py (JSON et CSV compresses).
La derniere exception (demande_legale.py, le modele de la demande des joueurs) est partie le 23 nov en deux temps : le modele
est ecrit et relu en JSON (tests/test_arbres_json.py). Il n'y a plus AUCUNE exception."""
import ast, os, sys, tempfile, math, collections
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INTERDITS = {"pickle", "cPickle", "_pickle", "shelve", "marshal", "dill", "joblib", "cloudpickle"}
APPELS = {"read_pickle", "to_pickle"}
EXCEPTIONS = {}                                         # aucune : ne rien ajouter ici sans en parler a Mathieu
vus, fautes = 0, []
for racine, dossiers, fichiers in os.walk(ICI):
    dossiers[:] = [d for d in dossiers if d not in (".git", "__pycache__", "node_modules", ".venv", "venv")]
    for f in fichiers:
        if not f.endswith(".py"):
            continue
        ch = os.path.join(racine, f); rel = os.path.relpath(ch, ICI).replace(os.sep, "/")
        try:
            arbre = ast.parse(open(ch, encoding="utf-8").read())
        except SyntaxError:
            continue
        vus += 1
        permis = EXCEPTIONS.get(rel, set())
        for n in ast.walk(arbre):
            noms = []
            if isinstance(n, ast.Import):
                noms = [a.name.split(".")[0] for a in n.names]
            elif isinstance(n, ast.ImportFrom):
                noms = [(n.module or "").split(".")[0]]
            elif isinstance(n, ast.Attribute) and n.attr in APPELS:
                noms = [n.attr]
            for nom in noms:
                if (nom in INTERDITS or nom in APPELS) and nom not in permis:
                    fautes.append(f"{rel}:{getattr(n, 'lineno', '?')} {nom}")
assert vus > 150, vus
assert not fautes, "pickle (ou un cousin) est revenu : passer par outils/recherche/cache_recherche.py -> " + ", ".join(fautes[:12])
assert not EXCEPTIONS, "plus aucune exception : le modele de la demande est en JSON depuis le 23 nov"
# le remplacant : ce qui entre ressort identique, et rien n'est execute a la lecture
sys.path.insert(0, os.path.join(ICI, "outils", "recherche"))
import cache_recherche as cr
d = tempfile.mkdtemp(prefix="lr_cache_")
o = {"a": [1, 2.5, None, True, "x", ""], ("carte", 1): [(1, 2), (3, (4, 5))], 3: {"s": {1, 2, 3}, "nan": float("nan"), "inf": float("-inf")},
     "__t__": 5, "dd": collections.defaultdict(list, {("a", "b"): [1]}), "vide": {}, "liste": [], "t0": ()}
cr.sauver(o, os.path.join(d, "o.json.gz")); r = cr.charger(os.path.join(d, "o.json.gz"))
assert r["a"] == o["a"] and r[("carte", 1)] == o[("carte", 1)] and r[3]["s"] == {1, 2, 3} and math.isnan(r[3]["nan"]) and r[3]["inf"] == float("-inf")
assert r["__t__"] == 5 and r["dd"] == {("a", "b"): [1]} and r["vide"] == {} and r["liste"] == [] and r["t0"] == () and isinstance(r[("carte", 1)][0], tuple)
try:
    cr.sauver({"x": object()}, os.path.join(d, "non.json.gz")); raise SystemExit("un objet quelconque ne doit pas passer")
except TypeError:
    pass
try:
    import pandas as pd, numpy as np
except ImportError:
    pd = None
if pd is not None:
    df = pd.DataFrame({"n": [1, 2, 3], "f": [0.1, float("nan"), 1 / 3], "f32": np.array([0.1, 0.2, 0.3], dtype="float32"), "t": ["", "NA", "Connor McDavid"],
                       "c": pd.Categorical(["yg", "auto", "yg"], categories=["auto", "base", "yg"])}, index=[10, 20, 35])
    cr.sauver_df(df, os.path.join(d, "t.csv.gz")); r = cr.charger_df(os.path.join(d, "t.csv.gz"))
    pd.testing.assert_frame_equal(df, r, check_exact=True)
print(f"OK test_sans_pickle ({vus} fichiers Python lus, AUCUN pickle, sans exception ; le cache JSON/CSV rend ce qu'on lui donne)")
