"""
SLABCOACH - le test de prediction de SlabIQ (11 nov 2026).

Mathieu : « as-tu essaye de predire la variation de la valeur des cartes d'un joueur avec les nouvelles, pour voir si le
modele fonctionne ? Sinon, fais-le jusqu'a un taux de confiance de 95 % minimum ».

On REJOUE LE PASSE avec nos propres ventes (base_ventes) :
  1. Chaque carte exacte (cartes_toutes) donne ses ventes ; chaque vente devient un ecart a la valeur habituelle de SA carte
     (log du prix moins la mediane de la carte) : le melange de cartes (base, autos, gradees) ne fausse plus la mesure.
  2. Pour chaque joueur et chaque lundi t : l'indice des 28 jours AVANT t et celui des 28 jours APRES t. La cible : hausse
     (+10 % et plus), baisse (-10 % et plus) ou stable.
  3. Les signaux connus LE JOUR t seulement (aucune information du futur) : l'elan des prix et des ventes des semaines
     d'avant, les visites Wikipedia jour par jour (le buzz : honneurs, records, rumeurs, blessures), les points LNH match par
     match, la position (gardien), l'age de la carriere.
  4. Apprentissage sur le debut de la periode, test sur la fin (jamais vue). Le seuil de confiance est choisi sur une tranche
     de validation, puis mesure sur le test : la precision des alertes (hausse/baisse annoncees) et la part des cas couverts.
Aucune donnee eBay en direct, aucun appel payant : nos archives, Wikimedia (pages vues) et l'API publique de la LNH.
Le rapport est garde dans slabiq_test.json (admin).
"""
import json
import math
import os
import statistics
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

HORIZON_J = 28
SEUIL = math.log(1.10)
VENTES_MIN = 6
JOUEURS_MAX = 400
CIBLE_PRECISION = 0.95
UA = "SlabCoach/1.0 (+https://www.slabcoach.com; contact via site)"
_ETAT = {"en_cours": False, "etape": None, "debut": None}
_verrou = threading.Lock()


def _chemin(nom):
    import comptes
    return os.path.join(comptes.DONNEES, nom)


def lire():
    try:
        with open(_chemin("slabiq_test.json"), encoding="utf-8") as f:
            r = json.load(f)
    except (OSError, ValueError):
        r = None
    return {"ok": True, "rapport": r, "en_cours": _ETAT["en_cours"], "etape": _ETAT["etape"]}


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    for essai in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(min(60, int(e.headers.get("retry-after") or 10) + 2))
                continue
            return None
        except Exception:
            time.sleep(1 + essai)
    return None


def _cache_lire():
    try:
        with open(_chemin("slabiq_test_cache.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"wiki": {}, "nhl": {}}


def _cache_ecrire(c):
    ch = _chemin("slabiq_test_cache.json")
    try:
        with open(ch + ".tmp", "w", encoding="utf-8") as f:
            json.dump(c, f)
        os.replace(ch + ".tmp", ch)
    except OSError:
        pass


def _vues_jour(titre, d0, d1):
    """Visites Wikipedia (anglais) jour par jour -> {AAAA-MM-JJ: vues}."""
    u = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/"
         f"{urllib.parse.quote(str(titre).replace(' ', '_'), safe='')}/daily/{d0:%Y%m%d}/{d1:%Y%m%d}")
    d = _get(u)
    out = {}
    for it in (d or {}).get("items") or []:
        ts = str(it.get("timestamp") or "")
        if len(ts) >= 8:
            out[f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"] = int(it.get("views") or 0)
    time.sleep(0.25)
    return out


def _matchs_lnh(pid, saisons):
    """Les matchs LNH d'un joueur -> [(AAAA-MM-JJ, points, buts)] et sa position."""
    out, pos = [], None
    for s in saisons:
        d = _get(f"https://api-web.nhle.com/v1/player/{pid}/game-log/{s}/2")
        for g in (d or {}).get("gameLog") or []:
            le = str(g.get("gameDate") or "")[:10]
            if le:
                out.append((le, int(g.get("points") or 0), int(g.get("goals") or 0)))
        time.sleep(0.2)
    land = _get(f"https://api-web.nhle.com/v1/player/{pid}/landing")
    if isinstance(land, dict):
        pos = land.get("position")
    return sorted(out), pos


def _med(l):
    return statistics.median(l) if l else None


def _series(cartes):
    """-> {joueur: [(date, ecart_log)]} : chaque vente comparee a la valeur habituelle de SA carte."""
    par_j = {}
    for c in cartes:
        pts = [(str(le)[:10], float(p)) for le, p in c.get("points") or [] if p and float(p) > 0 and le]
        if len(pts) < 4:
            continue
        logs = [math.log(p) for _le, p in pts]
        base = _med(logs)
        for (le, _p), lg in zip(pts, logs):
            e = lg - base
            if abs(e) <= 1.6:                              # une vente aberrante (lot, autre carte) n'entre pas
                par_j.setdefault(c["joueur"], []).append((le, e))
    for j in par_j:
        par_j[j].sort()
    return par_j


def _fenetre(serie, d0, d1):
    return [e for le, e in serie if d0 <= le < d1]


def _lundis(d_min, d_max):
    t = d_min + timedelta(days=(7 - d_min.weekday()) % 7)
    while t <= d_max:
        yield t
        t += timedelta(days=7)


def _exemples(par_j, wiki, nhl_, d_min, d_max):
    X, y, meta = [], [], []
    noms_f = ["elan_prix", "niveau", "ventes_av", "ventes_ratio", "buzz7", "buzz28", "notoriete", "pic3", "pts14", "pts28", "rythme",
              "gardien", "sans_lnh", "communaute7", "communaute_hausse"]
    try:                                       # 11 nov 2026 : l'interet de la communaute SlabCoach (depuis qu'on le compte)
        import communaute
        cj = communaute.lire().get("jours") or {}
    except Exception:
        communaute, cj = None, {}
    for j, serie in par_j.items():
        w = wiki.get(j) or {}
        n = nhl_.get(j) or {}
        matchs = n.get("matchs") or []
        for t in _lundis(d_min + timedelta(days=56), d_max - timedelta(days=HORIZON_J)):
            ts = t.isoformat()
            a = _fenetre(serie, (t - timedelta(days=28)).isoformat(), ts)
            b = _fenetre(serie, ts, (t + timedelta(days=HORIZON_J)).isoformat())
            if len(a) < VENTES_MIN or len(b) < VENTES_MIN:
                continue
            a0 = _fenetre(serie, (t - timedelta(days=56)).isoformat(), (t - timedelta(days=28)).isoformat())
            ma, mb = _med(a), _med(b)
            delta = mb - ma
            cl = 2 if delta > SEUIL else 0 if delta < -SEUIL else 1
            def vues(k0, k1):
                return sum(w.get((t - timedelta(days=k)).isoformat(), 0) for k in range(k0, k1))
            v7, v28, v60 = vues(1, 8), vues(1, 29), vues(1, 61)
            v3 = vues(1, 4)
            base_j = max(1.0, v60 / 60.0)
            p14 = sum(p for le, p, _b in matchs if (t - timedelta(days=14)).isoformat() <= le < ts)
            p28 = sum(p for le, p, _b in matchs if (t - timedelta(days=28)).isoformat() <= le < ts)
            g28 = sum(1 for le, _p, _b in matchs if (t - timedelta(days=28)).isoformat() <= le < ts)
            avant = [p for le, p, _b in matchs if le < (t - timedelta(days=28)).isoformat()]
            ppm_av = (sum(avant) / len(avant)) if avant else None
            X.append([
                (ma - _med(a0)) if len(a0) >= 4 else 0.0,
                ma,
                math.log1p(len(a)),
                (len(a) / max(1, len(a0))) if a0 else 1.0,
                (v7 / 7.0) / base_j if w else 1.0,
                (v28 / 28.0) / base_j if w else 1.0,
                math.log1p(v60),
                (v3 / 3.0) / base_j if w else 1.0,
                p14,
                (p28 / g28 - ppm_av) if g28 and ppm_av is not None else 0.0,
                p28 / g28 if g28 else 0.0,
                1.0 if n.get("position") == "G" else 0.0,
                0.0 if matchs else 1.0,
                *_communaute(cj, j, t)])
            y.append(cl)
            meta.append((ts, j))
    return X, y, meta, noms_f


def _communaute(cj, joueur, t):
    """(interet des 7 jours avant t, hausse vs les 30 jours d'avant) ; 0 avant qu'on le compte."""
    if not cj:
        return [0.0, 1.0]
    import communaute
    s = [communaute.score_jour((cj.get((t - timedelta(days=k)).isoformat()) or {}).get(joueur)) for k in range(1, 38)]
    s7, s30 = sum(s[:7]), sum(s[7:])
    return [math.log1p(s7), (s7 / 7.0) / max(0.5, s30 / 30.0)]


def _precision_seuil(proba, y, classes, cible=CIBLE_PRECISION):
    """Le plus petit seuil de confiance ou les alertes (hausse/baisse) atteignent la precision visee."""
    best = None
    for s in [x / 100 for x in range(50, 100)]:
        alertes = [(int(max(range(len(p)), key=lambda k: p[k])), yy) for p, yy in zip(proba, y)
                   if max(p) >= s and classes[int(max(range(len(p)), key=lambda k: p[k]))] != 1]
        if len(alertes) >= 5:
            prec = sum(1 for k, yy in alertes if classes[k] == yy) / len(alertes)
            if prec >= cible:
                best = s
                break
    return best


def _mesure(proba, y, classes, seuil):
    pred = [classes[int(max(range(len(p)), key=lambda k: p[k]))] for p in proba]
    acc = sum(1 for a, b in zip(pred, y) if a == b) / max(1, len(y))
    out = {"exactitude": round(acc, 3), "n": len(y)}
    if seuil is not None:
        al = [(pp, yy) for p, pp, yy in zip(proba, pred, y) if max(p) >= seuil and pp != 1]
        out.update(seuil=seuil, alertes=len(al), precision_alertes=round(sum(1 for pp, yy in al if pp == yy) / len(al), 3) if al else None,
                   couverture=round(len(al) / max(1, sum(1 for yy in y if yy != 1)), 3))
    return out


def executer(joueurs_max=JOUEURS_MAX):
    import base_ventes
    import nhl
    t0 = time.time()
    _ETAT.update(etape="ventes")
    cartes = [c for c in base_ventes.cartes_toutes(jours=420, n_min=4, max_q=20000) if (c.get("sport") or "hockey") == "hockey"]
    par_j = _series(cartes)
    par_j = dict(sorted(par_j.items(), key=lambda kv: -len(kv[1]))[:joueurs_max])
    if not par_j:
        return {"erreur": "Pas assez de ventes archivees pour rejouer le passe"}
    toutes = [le for s in par_j.values() for le, _e in s]
    d_min, d_max = date.fromisoformat(min(toutes)), date.fromisoformat(max(toutes))
    cache = _cache_lire()
    try:
        import demande_legale
        base_d = (demande_legale.lire() or {}).get("joueurs") or {}
    except Exception:
        base_d = {}
    _ETAT.update(etape="wikipedia")
    wiki = {}
    for i, j in enumerate(par_j):
        titre = ((base_d.get(j) or {}).get("wiki") or {}).get("titre") or (j + " (ice hockey)")
        k = f"{titre}|{d_min - timedelta(days=70)}|{d_max}"
        if k not in cache["wiki"]:
            cache["wiki"][k] = _vues_jour(titre, d_min - timedelta(days=70), d_max) or _vues_jour(j, d_min - timedelta(days=70), d_max)
            if i % 25 == 0:
                _cache_ecrire(cache)
        wiki[j] = cache["wiki"][k]
    _ETAT.update(etape="lnh")
    saisons = sorted({f"{y}{y + 1}" for y in range(d_min.year - 1, d_max.year + 1) if date(y, 9, 1) <= d_max})
    nhl_ = {}
    for i, j in enumerate(par_j):
        k = j + "|" + ",".join(saisons)
        if k not in cache["nhl"]:
            r = None
            try:
                r = nhl._chercher(j)
            except Exception:
                r = None
            if r and r.get("id"):
                m, pos = _matchs_lnh(r["id"], saisons)
                cache["nhl"][k] = {"matchs": m, "position": pos}
            else:
                cache["nhl"][k] = {"matchs": [], "position": None}
            if i % 25 == 0:
                _cache_ecrire(cache)
        nhl_[j] = cache["nhl"][k]
    _cache_ecrire(cache)
    _ETAT.update(etape="apprentissage")
    X, y, meta, noms_f = _exemples(par_j, wiki, nhl_, d_min, d_max)
    if len(X) < 200:
        return {"erreur": f"Trop peu d'exemples ({len(X)}) : il faut plus d'historique de ventes", "exemples": len(X),
                "joueurs": len(par_j), "periode": [d_min.isoformat(), d_max.isoformat()]}
    ordre = sorted(range(len(X)), key=lambda i: meta[i][0])
    dates = sorted({meta[i][0] for i in ordre})
    c_app, c_val = dates[int(len(dates) * 0.6)], dates[int(len(dates) * 0.8)]
    # l'apprentissage s'arrete HORIZON_J jours avant la validation (ses cibles ne voient pas la periode testee)
    lim_app = (date.fromisoformat(c_app) - timedelta(days=HORIZON_J)).isoformat()
    lim_val = (date.fromisoformat(c_val) - timedelta(days=HORIZON_J)).isoformat()
    app = [i for i in ordre if meta[i][0] < lim_app]
    val = [i for i in ordre if c_app <= meta[i][0] < lim_val]
    test = [i for i in ordre if meta[i][0] >= c_val]
    from sklearn.ensemble import HistGradientBoostingClassifier
    mod = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=15, l2_regularization=1.0, random_state=7)
    mod.fit([X[i] for i in app], [y[i] for i in app])
    classes = list(mod.classes_)
    p_val = mod.predict_proba([X[i] for i in val]).tolist() if val else []
    seuil = _precision_seuil(p_val, [y[i] for i in val], classes) if val else None
    p_test = mod.predict_proba([X[i] for i in test]).tolist()
    y_test = [y[i] for i in test]
    res = _mesure(p_test, y_test, classes, seuil)
    # les reperes : toujours « stable », et « le prix continue comme il allait » (l'elan)
    maj = max(set(y_test), key=y_test.count)
    naif = [2 if X[i][0] > SEUIL else 0 if X[i][0] < -SEUIL else 1 for i in test]
    rep = {"toujours_" + {0: "baisse", 1: "stable", 2: "hausse"}[maj]: round(y_test.count(maj) / len(y_test), 3),
           "elan_naif": round(sum(1 for a, b in zip(naif, y_test) if a == b) / len(y_test), 3)}
    try:
        from sklearn.inspection import permutation_importance
        imp = permutation_importance(mod, [X[i] for i in test], y_test, n_repeats=4, random_state=7)
        poids = sorted(zip(noms_f, imp.importances_mean.tolist()), key=lambda x: -x[1])
    except Exception:
        poids = []
    # des alertes du test, pour voir avec les yeux
    ex = []
    for i, p in zip(test, p_test):
        k = int(max(range(len(p)), key=lambda q: p[q]))
        if seuil is not None and max(p) >= seuil and classes[k] != 1:
            ex.append({"joueur": meta[i][1], "le": meta[i][0], "annonce": {0: "baisse", 2: "hausse"}[classes[k]],
                       "confiance": round(max(p), 3), "vrai": {0: "baisse", 1: "stable", 2: "hausse"}[y[i]]})
    r = {"le": datetime.now().isoformat(timespec="seconds"), "duree_s": round(time.time() - t0), "periode": [d_min.isoformat(), d_max.isoformat()],
         "joueurs": len(par_j), "cartes": len(cartes), "exemples": len(X), "apprentissage": len(app), "validation": len(val), "test": len(test),
         "repartition_test": {"baisse": y_test.count(0), "stable": y_test.count(1), "hausse": y_test.count(2)},
         "horizon_j": HORIZON_J, "seuil_pct": 10, "cible_precision": CIBLE_PRECISION,
         "resultat": res, "reperes": rep, "signaux": [[k, round(v, 4)] for k, v in poids],
         "atteint": bool(res.get("precision_alertes") is not None and res["precision_alertes"] >= CIBLE_PRECISION and res.get("alertes", 0) >= 10),
         "exemples_alertes": ex[:40]}
    return r


def lancer():
    """Lance le test en arriere-plan (un seul a la fois). Le rapport arrive dans slabiq_test.json."""
    with _verrou:
        if _ETAT["en_cours"]:
            return {"ok": True, "deja": True, "etape": _ETAT["etape"]}
        _ETAT.update(en_cours=True, etape="debut", debut=time.time())
    import contextvars
    ctx = contextvars.copy_context()

    def tache():
        try:
            r = executer()
        except Exception as e:
            r = {"erreur": f"{type(e).__name__} : {e}"[:300]}
        r.setdefault("le", datetime.now().isoformat(timespec="seconds"))
        try:
            with open(_chemin("slabiq_test.json"), "w", encoding="utf-8") as f:
                json.dump(r, f, ensure_ascii=False)
        except OSError:
            pass
        _ETAT.update(en_cours=False, etape=None)
    threading.Thread(target=lambda: ctx.run(tache), daemon=True, name="slabiq-test").start()
    return {"ok": True, "lance": True}
