"""23 nov 2026 (Aikido, critique : pickle ; Mathieu : « oui » au retrait en deux temps) : le modele d'arbres de la demande des
joueurs (demande_legale) part AUSSI en JSON a chaque passe, avec notre propre predicteur. 1er temps : on lit encore pickle, mais
le JSON est ecrit et compare a scikit-learn (labo.arbres_json). Ce test prouve que le predicteur rend les MEMES reponses que
scikit-learn, pour une foret comme pour un gradient boosting, y compris pile sur les seuils des arbres (compares en float32)."""
import json, os, sys, tempfile, random
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ICI)
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp(prefix="lr_arbres_")
os.environ["LR_DEMANDE_LEGALE"] = "0"
import demande_legale as dl
try:
    import numpy as np
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
except ImportError:
    print("OK test_arbres_json (scikit-learn absent ici : rien a comparer)")
    raise SystemExit(0)
rng = random.Random(7)
P = len(dl.PIECES)
X = [[rng.choice([0, 1, rng.random() * 40, rng.gauss(0, 3), round(rng.random() * 9)]) for _ in range(P)] for _ in range(320)]
y = [sum(x[:5]) * 0.05 + (x[5] > 1) * 0.8 + rng.gauss(0, 0.3) for x in X]
for m in (RandomForestRegressor(n_estimators=40, min_samples_leaf=3, max_features=0.33, random_state=0, n_jobs=2),
          GradientBoostingRegressor(n_estimators=60, max_depth=4, learning_rate=0.03, subsample=0.8, min_samples_leaf=8, random_state=0)):
    m.fit(np.array(X), np.array(y))
    d = dl._exporter_arbres(m)
    json.loads(json.dumps(d))                                    # rien que des nombres, des listes et du texte
    a = dl.ArbresJson(json.loads(json.dumps(d)))
    assert a.n_features_in_ == P and len(d["arbres"]) == m.n_estimators and d["moyenne"] == (d["type"] == "RandomForestRegressor")
    # des lignes neuves, et des lignes posees PILE sur des seuils (la ou une comparaison en float64 se tromperait de branche)
    T = [[rng.random() * 40 - 5 for _ in range(P)] for _ in range(200)]
    for arbre in d["arbres"][:25]:
        for f, s in zip(arbre["f"], arbre["s"]):
            if f >= 0:
                l = list(rng.choice(X)); l[f] = s; T.append(l)
                l = list(rng.choice(X)); l[f] = float(np.float32(s)); T.append(l)
    ecart = max(abs(float(u) - float(v)) for u, v in zip(m.predict(np.array(T)), a.predict(T)))
    assert ecart < 1e-9, (d["type"], ecart)
    # l'ecriture : le fichier est du JSON relisible, et l'ecart mesure sur place est nul
    r = dl._sauver_arbres_json(m, X)
    assert r["ok"] and r["ecart"] < 1e-9 and r["n"] == len(X) and r["arbres"] == m.n_estimators and r["type"] == d["type"], r
    relu = dl.ArbresJson(json.load(open(dl._chemin_arbres_json(), encoding="utf-8")))
    assert max(abs(float(u) - float(v)) for u, v in zip(m.predict(np.array(X[:50])), relu.predict(X[:50]))) < 1e-9
    assert not os.path.exists(dl._chemin_arbres_json() + ".tmp")
# un modele qu'on ne connait pas n'est pas exporte de travers ; un fichier abime n'est pas lu
try:
    dl._exporter_arbres(object()); raise SystemExit("un modele inconnu doit etre refuse")
except TypeError:
    pass
try:
    dl.ArbresJson({"v": 2, "arbres": []}); raise SystemExit("un fichier d'une autre version doit etre refuse")
except ValueError:
    pass
# le 1er temps : labo() ecrit le JSON et note son etat ; la lecture, elle, n'a pas encore change (2e temps apres une passe en ligne)
src = open(os.path.join(ICI, "demande_legale.py"), encoding="utf-8").read()
assert 'aj = _sauver_arbres_json(gb["modele"], [[l[1][k] for k in PIECES] for l in lignes])' in src and '"arbres_json": aj}' in src
assert '"; arbres JSON", (r.get("labo") or {}).get("arbres_json")' in src, "le journal de la passe dit si le JSON est bon"
print("OK test_arbres_json (foret et gradient boosting : memes reponses que scikit-learn, seuils compris ; le fichier se relit)")
