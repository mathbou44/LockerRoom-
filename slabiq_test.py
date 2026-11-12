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
  12 nov 2026 (1er rapport : 52 %, pas mieux que « toujours stable ») : la cible compare chaque carte A ELLE-MEME (avant /
  apres), aucune valeur de reference ne voit le futur, et le modele est reentraine semaine par semaine.
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
JOUEURS_MAX = 1000         # 12 nov 2026 : 400 -> 1000, plus de semaines pour apprendre (Wikipedia et LNH en cache)
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


def _med_pond(paires):
    """Mediane ponderee de [(valeur, poids)]."""
    if not paires:
        return None
    paires = sorted(paires)
    tot, acc = sum(p for _v, p in paires), 0.0
    for v, p in paires:
        acc += p
        if acc >= tot / 2:
            return v
    return paires[-1][0]


def _series(cartes):
    """-> {joueur: [[(date, log prix)] par carte]} : les ventes de chaque carte exacte, gardees carte par carte.
    12 nov 2026 : plus de « valeur habituelle » calculee sur toute l'annee (elle voyait le futur) ; on compare toujours une
    carte A ELLE-MEME, d'une periode a l'autre."""
    par_j = {}
    for c in cartes:
        pts = sorted((str(le)[:10], math.log(float(p))) for le, p in c.get("points") or [] if p and float(p) > 0 and le)
        if len(pts) < 4:
            continue
        gardes = []                                    # une vente aberrante (lot, autre carte) n'entre pas : comparee aux
        for le, lg in pts:                             # 10 ventes d'AVANT seulement (12 nov 2026 : rien du futur, meme ici)
            if len(gardes) < 3 or abs(lg - _med([g for _l, g in gardes[-10:]])) <= 1.6:
                gardes.append((le, lg))
        pts = gardes
        if len(pts) >= 4:
            par_j.setdefault(c["joueur"], []).append(pts)
    return par_j


def _n_ventes(cartes_j, d0, d1):
    return sum(1 for pts in cartes_j for le, _lg in pts if d0 <= le < d1)


def _mouv(cartes_j, a0, a1, b0, b1):
    """Le mouvement des cartes d'un joueur de la periode A a la periode B, MEME CARTE contre MEME CARTE :
    -> (mediane ponderee des ecarts de log, nb de cartes comparees, poids) ; le poids d'une carte = ses ventes du cote le plus mince."""
    ds = []
    for pts in cartes_j:
        a = [lg for le, lg in pts if a0 <= le < a1]
        b = [lg for le, lg in pts if b0 <= le < b1]
        if a and b:
            ds.append((_med(b) - _med(a), min(len(a), len(b))))
    if not ds:
        return None, 0, 0
    return _med_pond(ds), len(ds), sum(p for _d, p in ds)


def _iso(t, k):
    return (t + timedelta(days=k)).isoformat()


def _lundis(d_min, d_max):
    t = d_min + timedelta(days=(7 - d_min.weekday()) % 7)
    while t <= d_max:
        yield t
        t += timedelta(days=7)


NOMS_F = ["elan_prix", "elan_court", "niveau", "ventes_av", "ventes_ratio", "marche_elan", "marche_niveau", "buzz7", "buzz28",
          "notoriete", "pic3", "pts14", "pts28", "rythme", "gardien", "sans_lnh", "communaute7", "communaute_hausse"]
PAIRES_MIN = 2          # au moins 2 cartes differentes vendues avant ET apres
POIDS_MIN = 3           # et au moins 3 ventes comparables


def _exemples(par_j, wiki, nhl_, d_min, d_max):
    """-> X, y, meta, noms. Chaque exemple : un joueur, un lundi t. Tout ce qui entre dans X est connu AVANT t."""
    X, y, meta = [], [], []
    try:                                       # 11 nov 2026 : l'interet de la communaute SlabCoach (depuis qu'on le compte)
        import communaute
        cj = communaute.lire().get("jours") or {}
    except Exception:
        cj = {}
    debut = d_min.isoformat()
    lundis = list(_lundis(d_min + timedelta(days=56), d_max - timedelta(days=HORIZON_J)))
    # le marche : le mouvement median de tous les joueurs, connu a t (la saison, l'ete, la sortie d'un produit)
    marche = {}
    for t in lundis:
        time.sleep(0.005)                      # 12 nov 2026 : laisse passer les requetes de l'app (un seul serveur)
        e, n = [], []
        for cartes_j in par_j.values():
            m1, k1, _p = _mouv(cartes_j, _iso(t, -56), _iso(t, -28), _iso(t, -28), t.isoformat())
            if m1 is not None and k1 >= PAIRES_MIN:
                e.append(m1)
            m2, k2, _p = _mouv(cartes_j, debut, _iso(t, -28), _iso(t, -28), t.isoformat())
            if m2 is not None and k2 >= PAIRES_MIN:
                n.append(m2)
        marche[t] = (_med(e) or 0.0, _med(n) or 0.0)
    for i_j, (j, cartes_j) in enumerate(par_j.items()):
        if i_j % 10 == 0:
            time.sleep(0.005)
        w = wiki.get(j) or {}
        n = nhl_.get(j) or {}
        matchs = n.get("matchs") or []
        for t in lundis:
            ts = t.isoformat()
            cible, k, poids = _mouv(cartes_j, _iso(t, -28), ts, ts, _iso(t, HORIZON_J))
            if cible is None or k < PAIRES_MIN or poids < POIDS_MIN:
                continue
            nv = _n_ventes(cartes_j, _iso(t, -28), ts)
            nv0 = _n_ventes(cartes_j, _iso(t, -56), _iso(t, -28))
            elan, ke, _p = _mouv(cartes_j, _iso(t, -56), _iso(t, -28), _iso(t, -28), ts)
            court, kc, _p = _mouv(cartes_j, _iso(t, -28), _iso(t, -14), _iso(t, -14), ts)
            niv, kn, _p = _mouv(cartes_j, debut, _iso(t, -28), _iso(t, -28), ts)
            cl = 2 if cible > SEUIL else 0 if cible < -SEUIL else 1

            def vues(k0, k1):
                return sum(w.get((t - timedelta(days=q)).isoformat(), 0) for q in range(k0, k1))
            v7, v28, v60, v3 = vues(1, 8), vues(1, 29), vues(1, 61), vues(1, 4)
            base_j = max(1.0, v60 / 60.0)
            p14 = sum(p for le, p, _b in matchs if _iso(t, -14) <= le < ts)
            p28 = sum(p for le, p, _b in matchs if _iso(t, -28) <= le < ts)
            g28 = sum(1 for le, _p, _b in matchs if _iso(t, -28) <= le < ts)
            avant = [p for le, p, _b in matchs if le < _iso(t, -28)]
            ppm_av = (sum(avant) / len(avant)) if avant else None
            X.append([
                elan if elan is not None else 0.0,
                court if court is not None else 0.0,
                niv if niv is not None else 0.0,
                math.log1p(nv),
                (nv / max(1, nv0)) if nv0 else 1.0,
                marche[t][0],
                marche[t][1],
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
            meta.append((ts, j, round(cible, 4), k))
    return X, y, meta, NOMS_F


def _communaute(cj, joueur, t):
    """(interet des 7 jours avant t, hausse vs les 30 jours d'avant) ; 0 avant qu'on le compte."""
    if not cj:
        return [0.0, 1.0]
    import communaute
    s = [communaute.score_jour((cj.get((t - timedelta(days=k)).isoformat()) or {}).get(joueur)) for k in range(1, 38)]
    s7, s30 = sum(s[:7]), sum(s[7:])
    return [math.log1p(s7), (s7 / 7.0) / max(0.5, s30 / 30.0)]


def _alertes(proba, y, classes, s):
    """[(annonce, vrai)] des alertes (hausse/baisse) dont la confiance atteint s."""
    out = []
    for p, yy in zip(proba, y):
        k = int(max(range(len(p)), key=lambda q: p[q]))
        if p[k] >= s and classes[k] != 1:
            out.append((classes[k], yy))
    return out


def _courbe(proba, y, classes):
    """La precision des alertes et leur nombre, seuil par seuil (50 % a 99 %)."""
    mv = max(1, sum(1 for yy in y if yy != 1))
    out = []
    for s in [x / 100 for x in range(50, 100)]:
        al = _alertes(proba, y, classes, s)
        if not al:
            break
        out.append({"seuil": s, "alertes": len(al), "precision": round(sum(1 for a, b in al if a == b) / len(al), 3),
                    "couverture": round(len(al) / mv, 3)})
    return out


def _precision_seuil(proba, y, classes, cible=CIBLE_PRECISION, n_min=8):
    """Le plus petit seuil ou les alertes (hausse/baisse) atteignent la precision visee (au moins n_min alertes)."""
    for c in _courbe(proba, y, classes):
        if c["alertes"] >= n_min and c["precision"] >= cible:
            return c["seuil"]
    return None


def _mesure(proba, y, classes, seuil):
    pred = [classes[int(max(range(len(p)), key=lambda k: p[k]))] for p in proba]
    acc = sum(1 for a, b in zip(pred, y) if a == b) / max(1, len(y))
    out = {"exactitude": round(acc, 3), "n": len(y)}
    if seuil is not None:
        al = _alertes(proba, y, classes, seuil)
        out.update(seuil=seuil, alertes=len(al), precision_alertes=round(sum(1 for a, b in al if a == b) / len(al), 3) if al else None,
                   couverture=round(len(al) / max(1, sum(1 for yy in y if yy != 1)), 3))
    return out


def _modele():
    from sklearn.ensemble import HistGradientBoostingClassifier
    return HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_leaf_nodes=8, min_samples_leaf=25,
                                          l2_regularization=2.0, random_state=7)


def _pas_a_pas(X, y, meta, app_min=150, tous_les=2):
    """Rejoue le passe SEMAINE PAR SEMAINE : pour chaque lundi w, le modele n'apprend que des exemples dont la reponse etait
    connue avant w (lundi + 28 jours <= w), puis predit w. -> [(indice, proba)], classes, dernier modele."""
    par_d = {}
    for i, m in enumerate(meta):
        par_d.setdefault(m[0], []).append(i)
    dates = sorted(par_d)
    out, classes, mod, k = [], None, None, 0
    for d in dates:
        lim = (date.fromisoformat(d) - timedelta(days=HORIZON_J)).isoformat()
        app = [i for i, m in enumerate(meta) if m[0] <= lim]
        if len(app) < app_min or len({y[i] for i in app}) < 3:
            continue
        if mod is None or k % tous_les == 0:
            mod = _modele()
            mod.fit([X[i] for i in app], [y[i] for i in app])
            classes = list(mod.classes_)
        k += 1
        ids = par_d[d]
        for i, p in zip(ids, mod.predict_proba([X[i] for i in ids]).tolist()):
            out.append((i, p))
    return out, classes, mod


def executer(joueurs_max=JOUEURS_MAX):
    import base_ventes
    import nhl
    t0 = time.time()
    _ETAT.update(etape="ventes")
    cartes = [c for c in base_ventes.cartes_toutes(jours=420, n_min=4, max_q=20000) if (c.get("sport") or "hockey") == "hockey"]
    par_j = _series(cartes)
    par_j = dict(sorted(par_j.items(), key=lambda kv: -sum(len(p) for p in kv[1]))[:joueurs_max])
    if not par_j:
        return {"erreur": "Pas assez de ventes archivees pour rejouer le passe"}
    toutes = [le for cj in par_j.values() for pts in cj for le, _e in pts]
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
    # combien de ventes on a, mois par mois : l'historique est le vrai carburant du test
    par_mois = {}
    for le in toutes:
        par_mois[le[:7]] = par_mois.get(le[:7], 0) + 1
    base = {"periode": [d_min.isoformat(), d_max.isoformat()], "joueurs": len(par_j), "cartes": len(cartes), "ventes": len(toutes),
            "ventes_mois": sorted(par_mois.items()), "exemples": len(X)}
    if len(X) < 200:
        return {"erreur": f"Trop peu d'exemples ({len(X)}) : il faut plus d'historique de ventes (meme carte vendue avant et apres)",
                **base}
    oos, classes, mod = _pas_a_pas(X, y, meta)
    if len(oos) < 60:
        return {"erreur": f"Trop peu de semaines a tester ({len(oos)}) : il faut plus d'historique", **base}
    oos.sort(key=lambda ip: meta[ip[0]][0])
    # le seuil est CHOISI sur la premiere moitie des predictions, puis MESURE sur la seconde (jamais vue au choix)
    mi = len(oos) // 2
    while 0 < mi < len(oos) and meta[oos[mi][0]][0] == meta[oos[mi - 1][0]][0]:
        mi += 1
    choix, test = oos[:mi], oos[mi:]
    p_ch, y_ch = [p for _i, p in choix], [y[i] for i, _p in choix]
    p_te, y_te = [p for _i, p in test], [y[i] for i, _p in test]
    seuil = _precision_seuil(p_ch, y_ch, classes)
    seuil_mode = "95" if seuil is not None else None
    if seuil is None:
        # 12 nov 2026 : aucun seuil a 95 % sur la premiere moitie -> le plus sur qui garde au moins 8 alertes, choisi AVANT
        # de regarder le test (le chiffre affiche reste honnete)
        c_ch = [c for c in _courbe(p_ch, y_ch, classes) if c["alertes"] >= 8]
        if c_ch:
            seuil, seuil_mode = max(c_ch, key=lambda c: (c["precision"], -c["seuil"]))["seuil"], "meilleur"
    res = _mesure(p_te, y_te, classes, seuil)
    res["seuil_mode"] = seuil_mode
    courbe = _courbe(p_te, y_te, classes)
    meilleur = max((c for c in courbe if c["alertes"] >= 8), key=lambda c: (c["precision"], c["alertes"]), default=None)
    maj = max(set(y_te), key=y_te.count)
    naif = [2 if X[i][0] > SEUIL else 0 if X[i][0] < -SEUIL else 1 for i, _p in test]
    rep = {"toujours_" + {0: "baisse", 1: "stable", 2: "hausse"}[maj]: round(y_te.count(maj) / len(y_te), 3),
           "elan_naif": round(sum(1 for a, b in zip(naif, y_te) if a == b) / len(y_te), 3)}
    try:
        from sklearn.inspection import permutation_importance
        imp = permutation_importance(mod, [X[i] for i, _p in test], y_te, n_repeats=4, random_state=7)
        poids = sorted(zip(noms_f, imp.importances_mean.tolist()), key=lambda x: -x[1])
    except Exception:
        poids = []
    # des alertes du test : les plus confiantes d'abord, toutes dates
    ex = []
    s_ex = seuil if seuil is not None else (meilleur or {}).get("seuil", 0.8)
    for i, p in sorted(test, key=lambda ip: -max(ip[1])):
        k = int(max(range(len(p)), key=lambda q: p[q]))
        if max(p) >= s_ex and classes[k] != 1:
            ex.append({"joueur": meta[i][1], "le": meta[i][0], "annonce": {0: "baisse", 2: "hausse"}[classes[k]],
                       "confiance": round(max(p), 3), "vrai": {0: "baisse", 1: "stable", 2: "hausse"}[y[i]],
                       "mouvement_pct": round(100 * (math.exp(meta[i][2]) - 1), 1)})
        if len(ex) >= 40:
            break
    r = {"le": datetime.now().isoformat(timespec="seconds"), "duree_s": round(time.time() - t0), "methode": "v2-meme-carte-pas-a-pas",
         **base, "testees": len(oos), "choix_seuil": len(choix), "test": len(test),
         "test_debut": meta[test[0][0]][0] if test else None,
         "repartition_test": {"baisse": y_te.count(0), "stable": y_te.count(1), "hausse": y_te.count(2)},
         "horizon_j": HORIZON_J, "seuil_pct": 10, "cible_precision": CIBLE_PRECISION,
         "resultat": res, "reperes": rep, "courbe": courbe, "meilleur": meilleur,
         "signaux": [[k, round(v, 4)] for k, v in poids],
         "atteint": bool(res.get("precision_alertes") is not None and res["precision_alertes"] >= CIBLE_PRECISION and res.get("alertes", 0) >= 10),
         "exemples_alertes": ex}
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
