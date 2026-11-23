"""Les fichiers de travail des scripts de recherche, SANS pickle.

23 nov 2026 (Aikido, « Using Pickle can lead to remote code execution », critique) : lire un fichier pickle, c'est executer
ce qu'il contient. Ces scripts ne lisent que leurs propres fichiers, mais un outil d'analyse ne peut pas le savoir, et un
.pkl recu d'ailleurs resterait un risque. Ici : du JSON compresse pour les objets Python (dictionnaires, listes, tuples,
ensembles, cles qui ne sont pas du texte) et du CSV compresse pour les tableaux pandas. Rien n'est jamais execute a la
lecture. tests/test_sans_pickle.py interdit le retour de pickle dans le depot.

    import cache_recherche as cr
    cr.sauver(objet, "by2.json.gz") ; objet = cr.charger("by2.json.gz")
    cr.sauver_df(df, "jeu.csv.gz")  ; df = cr.charger_df("jeu.csv.gz")
"""
import gzip
import json
import math

_T, _S, _D, _F = "__t__", "__s__", "__d__", "__f__"          # tuple, ensemble, dictionnaire a cles non textuelles, nombre special


def _coder(x):
    if x is None or isinstance(x, (bool, str)):
        return x
    if isinstance(x, int):
        return x
    if isinstance(x, float):
        return x if math.isfinite(x) else {_F: "nan" if x != x else "inf" if x > 0 else "-inf"}
    if isinstance(x, tuple):
        return {_T: [_coder(v) for v in x]}
    if isinstance(x, list):
        return [_coder(v) for v in x]
    if isinstance(x, (set, frozenset)):
        return {_S: [_coder(v) for v in sorted(x, key=repr)]}
    if isinstance(x, dict):
        if all(isinstance(k, str) and not (k.startswith("__") and k.endswith("__")) for k in x):
            return {k: _coder(v) for k, v in x.items()}
        return {_D: [[_coder(k), _coder(v)] for k, v in x.items()]}
    if hasattr(x, "item") and not hasattr(x, "__len__"):                 # nombres numpy
        return _coder(x.item())
    if hasattr(x, "tolist"):                                              # tableaux numpy
        return _coder(x.tolist())
    if hasattr(x, "isoformat"):                                           # dates
        return x.isoformat()
    raise TypeError("cache_recherche : type non pris en charge : " + type(x).__name__)


def _decoder(x):
    if isinstance(x, list):
        return [_decoder(v) for v in x]
    if isinstance(x, dict):
        if len(x) == 1:
            (k, v), = x.items()
            if k == _T:
                return tuple(_decoder(e) for e in v)
            if k == _S:
                return set(_decoder(e) for e in v)
            if k == _D:
                return {_decoder(a): _decoder(b) for a, b in v}
            if k == _F:
                return float(v)
        return {k: _decoder(v) for k, v in x.items()}
    return x


def sauver(objet, chemin):
    """Ecrit `objet` (dict, list, tuple, set, nombres, texte, imbriques) en JSON compresse. Un defaultdict devient un dict."""
    with gzip.open(chemin, "wt", encoding="utf-8", compresslevel=5) as f:
        json.dump(_coder(objet), f, ensure_ascii=False, separators=(",", ":"))


def charger(chemin):
    with gzip.open(chemin, "rt", encoding="utf-8") as f:
        return _decoder(json.load(f))


_NA = "\\N"            # une case vide (NaN) : ainsi un texte vide '' ou le nom « NA » restent du texte


def sauver_df(df, chemin):
    """Un tableau pandas en CSV compresse. 1re ligne : le type de chaque colonne (float32, les categories... seraient perdus) ;
    l'index est garde dans la colonne __idx__ ; les nombres sont relus au bit pres."""
    cats = {str(c): [str(v) for v in df[c].cat.categories] for c in df.columns if str(df[c].dtype) == "category"}
    with gzip.open(chemin, "wt", encoding="utf-8", newline="", compresslevel=5) as f:
        f.write(json.dumps({"types": {str(c): str(t) for c, t in df.dtypes.items()}, "categories": cats}) + "\n")
        df.to_csv(f, index=True, index_label="__idx__", na_rep=_NA)


def charger_df(chemin):
    import pandas as pd
    with gzip.open(chemin, "rt", encoding="utf-8", newline="") as f:
        tete = json.loads(f.readline())
        df = pd.read_csv(f, index_col="__idx__", low_memory=False, float_precision="round_trip", na_values=[_NA], keep_default_na=False)
    df.index.name = None
    for c, t in tete["types"].items():
        if c not in df.columns or str(df[c].dtype) == t:
            continue
        try:
            df[c] = pd.Categorical(df[c], categories=tete.get("categories", {}).get(c)) if t == "category" else df[c].astype(t)
        except (TypeError, ValueError):
            pass                                   # un type que pandas ne sait pas refaire depuis du texte : on garde celui lu
    return df
