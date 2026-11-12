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


_RECRUES = {}


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
            r = _RECRUES.setdefault(c["joueur"], [0, 0])
            r[0] += 1 if c.get("recrue") else 0
            r[1] += 1
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


JOURS_APP = (0, 2, 4)    # 12 nov 2026 : on apprend des lundis, mercredis et vendredis (3x plus d'exemples) ; la note : les lundis


def _lundis(d_min, d_max):
    t = d_min + timedelta(days=(7 - d_min.weekday()) % 7)
    while t <= d_max:
        yield t
        t += timedelta(days=1)
        while t.weekday() not in JOURS_APP:
            t += timedelta(days=1)


NOMS_F = ["elan_prix", "elan_court", "niveau", "ventes_av", "ventes_ratio", "marche_elan", "marche_niveau", "buzz7", "buzz28",
          "notoriete", "pic3", "pts14", "pts28", "rythme", "gardien", "sans_lnh", "communaute7", "communaute_hausse",
          "volatilite", "prix", "cartes", "recrues"]


def _profil(cartes_j, d0, d1):
    """(volatilite : l'ecart-type des ventes autour de la mediane de LEUR carte ; le prix median (log) ; nb de cartes vendues)."""
    ecarts, prix, n = [], [], 0
    for pts in cartes_j:
        a = [lg for le, lg in pts if d0 <= le < d1]
        if not a:
            continue
        n += 1
        m = _med(a)
        prix.append(m)
        ecarts += [x - m for x in a]
    vol = statistics.pstdev(ecarts) if len(ecarts) >= 3 else 0.0
    return vol, (_med(prix) or 0.0), n
PAIRES_MIN = 2          # au moins 2 cartes differentes vendues avant ET apres
POIDS_MIN = 3           # et au moins 3 ventes comparables


def _exemples(par_j, wiki, nhl_, d_min, d_max, vivant=None):
    """-> X, y, meta, noms. Chaque exemple : un joueur, un lundi t. Tout ce qui entre dans X est connu AVANT t.
    vivant (une date) : les signaux de CE jour seulement, sans reponse (pour predire en direct)."""
    X, y, meta = [], [], []
    try:                                       # 11 nov 2026 : l'interet de la communaute SlabCoach (depuis qu'on le compte)
        import communaute
        cj = communaute.lire().get("jours") or {}
    except Exception:
        cj = {}
    debut = d_min.isoformat()
    lundis = [vivant] if vivant else list(_lundis(d_min + timedelta(days=56), d_max - timedelta(days=HORIZON_J)))
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
            if vivant:                         # en direct : assez de cartes vendues ce mois-ci pour juger dans 28 jours
                k = sum(1 for pts in cartes_j if any(_iso(t, -28) <= le < ts for le, _lg in pts))
                cible = 0.0
                if k < PAIRES_MIN:
                    continue
            else:
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
                *_communaute(cj, j, t),
                *_profil(cartes_j, _iso(t, -28), ts),
                (lambda r: r[0] / r[1] if r and r[1] else 0.0)(_RECRUES.get(j))])
            y.append(cl)
            meta.append((ts, j, round(cible, 4), k, t.weekday() == 0))
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


def _wilson(k, n, z=1.96):
    """La borne basse de l'intervalle de confiance a 95 % (Wilson) : la certitude minimale d'une precision k/n."""
    if not n:
        return 0.0
    p = k / n
    d = 1 + z * z / n
    return (p + z * z / (2 * n) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d


TOP_SEMAINE = (0.01, 0.02, 0.03, 0.05)


def _top_semaine(lignes, classes, y, meta):
    """12 nov 2026 : les alertes = le top q % des joueurs les plus surs de CHAQUE semaine (et non un seuil fixe, qui ne se
    transporte pas d'une saison a l'autre). -> {q: {alertes, justes, precision, certitude, exemples}}."""
    par = {}
    for i, p in lignes:
        k = int(max(range(len(p)), key=lambda q: p[q]))
        if classes[k] != 1:
            par.setdefault(meta[i][0], []).append((p[k], classes[k], y[i], i))
    out = {}
    for q in TOP_SEMAINE:
        al = []
        for d in sorted(par):
            l = sorted(par[d], key=lambda t: -t[0])
            al += l[:max(1, int(round(q * len(l))))]
        k = sum(1 for c, a, b, _i in al if a == b)
        mv = [100 * (math.exp(meta[i][2]) - 1) for _c, _a, _b, i in al]
        out[str(q)] = {"alertes": len(al), "justes": k, "precision": round(k / len(al), 3) if al else None,
                       "certitude": round(_wilson(k, len(al)), 3),
                       # 13 nov 2026 (Mathieu : « un rapport qui fait wow ») : ce que les alertes ont vraiment vu venir
                       "mouvement_moyen": round(sum(mv) / len(mv), 1) if mv else None,
                       "semaines": len({meta[i][0] for _c, _a, _b, i in al}),
                       "liste": [{"joueur": meta[i][1], "le": meta[i][0], "annonce": {0: "baisse", 2: "hausse"}[a],
                                  "vrai": {0: "baisse", 1: "stable", 2: "hausse"}[b], "confiance": round(c, 3),
                                  "mouvement_pct": round(100 * (math.exp(meta[i][2]) - 1), 1)}
                                 for c, a, b, i in sorted(al, key=lambda t: meta[t[3]][2] if t[1] == 0 else -meta[t[3]][2])][:40]}
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


ARBRES = 1.0             # les tests le baissent (plus rapide) ; le serveur garde 1.0


class _Vote:
    """Les modeles qui votent (la moyenne de leurs probabilites) : une alerte sure doit l'etre pour tous.
    12 nov 2026 (rejoue sur les vraies ventes, 20 essais) : foret aleatoire + arbres extremes + boosting prudent + regression
    -> 17/18 justes sur le 1 % le plus sur de chaque semaine jamais vue (l'ancien vote : 12/18). Un coeur (n_jobs=1)."""
    def __init__(self):
        from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        self.m = [RandomForestClassifier(n_estimators=int(400 * ARBRES), min_samples_leaf=20, max_features=0.4, n_jobs=1, random_state=7),
                  ExtraTreesClassifier(n_estimators=int(600 * ARBRES), min_samples_leaf=20, max_features=0.5, n_jobs=1, random_state=7),
                  HistGradientBoostingClassifier(max_iter=150, learning_rate=0.04, max_depth=3, min_samples_leaf=60,
                                                 l2_regularization=5.0, random_state=7),
                  make_pipeline(StandardScaler(), LogisticRegression(C=0.3, max_iter=3000))]
        self.classes_ = None

    def fit(self, X, y):
        import numpy as np
        X = np.nan_to_num(np.asarray(X, dtype=float))
        for m in self.m:
            m.fit(X, y)
        self.classes_ = self.m[0].classes_
        return self

    def predict_proba(self, X):
        import numpy as np
        X = np.nan_to_num(np.asarray(X, dtype=float))
        return np.mean([m.predict_proba(X) for m in self.m], axis=0)

    def predict(self, X):
        p = self.predict_proba(X)
        return self.classes_[p.argmax(axis=1)]

    def score(self, X, y):
        import numpy as np
        return float((self.predict(X) == np.asarray(y)).mean())

    def get_params(self, deep=False):
        return {}


def _modele():
    return _Vote()


def _pas_a_pas(X, y, meta, app_min=150, tous_les_j=7):
    """Rejoue le passe jour par jour : pour chaque jour d, le modele n'apprend que des exemples dont la reponse etait connue
    avant d (jour + 28 jours <= d), puis predit d ; il est reentraine chaque semaine. -> [(indice, proba)], classes, modele.
    Seuls les LUNDIS sont notes (les autres jours ne servent qu'a apprendre)."""
    par_d = {}
    for i, m in enumerate(meta):
        par_d.setdefault(m[0], []).append(i)
    dates = sorted(par_d)
    out, classes, mod, der = [], None, None, None
    for d in dates:
        ids = [i for i in par_d[d] if len(meta[i]) < 5 or meta[i][4]]
        if not ids:
            continue
        lim = (date.fromisoformat(d) - timedelta(days=HORIZON_J)).isoformat()
        if mod is None or (date.fromisoformat(d) - der).days >= tous_les_j:
            app = [i for i, m in enumerate(meta) if m[0] <= lim]
            if len(app) < app_min or len({y[i] for i in app}) < 3:
                continue
            time.sleep(0.01)
            mod = _modele()
            mod.fit([X[i] for i in app], [y[i] for i in app])
            classes, der = list(mod.classes_), date.fromisoformat(d)
        for i, p in zip(ids, mod.predict_proba([X[i] for i in ids]).tolist()):
            out.append((i, p))
    return out, classes, mod


TOP_DIRECT = 0.02         # le journal en direct : le top 2 % des joueurs les plus surs du jour


def _journal_lire():
    try:
        with open(_chemin("slabiq_journal.json"), encoding="utf-8") as f:
            return json.load(f) or {"alertes": []}
    except (OSError, ValueError):
        return {"alertes": []}


def _journal(par_j, wiki, nhl_, X, y, meta, d_min, d_max):
    """12 nov 2026 (Mathieu : « des exemples concrets de bons coups, verifiables ») : le JOURNAL EN DIRECT. Chaque passe, le
    modele (appris sur tout ce dont on connait la reponse) note le top 2 % des joueurs du jour, horodate ; 28 jours plus
    tard, la meme mesure que le test (meme carte avant / apres) dit juste ou faux. Rien ne s'efface : le vrai bilan."""
    jr = _journal_lire()
    al = jr.setdefault("alertes", [])
    # 1. noter les alertes dont les 28 jours sont passes
    for a in al:
        if a.get("vrai") or a.get("non_mesurable"):
            continue
        t = date.fromisoformat(a["le"])
        if (t + timedelta(days=HORIZON_J)).isoformat() > d_max.isoformat():
            continue
        cj_ = par_j.get(a["joueur"])
        m, k, poids = _mouv(cj_, _iso(t, -28), a["le"], a["le"], _iso(t, HORIZON_J)) if cj_ else (None, 0, 0)
        if m is None or k < PAIRES_MIN or poids < POIDS_MIN:
            a["non_mesurable"] = True
            continue
        a["vrai"] = "hausse" if m > SEUIL else "baisse" if m < -SEUIL else "stable"
        a["mouvement_pct"] = round(100 * (math.exp(m) - 1), 1)
        a["juste"] = a["vrai"] == a["annonce"]
    # 2. les alertes du jour (une passe par jour au plus)
    auj = min(date.today(), d_max + timedelta(days=1))
    if not any(a["le"] == auj.isoformat() for a in al):
        Xv, _yv, mv, _n = _exemples(par_j, wiki, nhl_, d_min, d_max, vivant=auj)
        if Xv and len(set(y)) == 3:
            mod = _modele()
            mod.fit(X, y)
            classes = list(mod.classes_)
            l = []
            for p, m_ in zip(mod.predict_proba(Xv).tolist(), mv):
                k = int(max(range(len(p)), key=lambda q: p[q]))
                if classes[k] != 1:
                    l.append((p[k], classes[k], m_[1]))
            l.sort(key=lambda t: -t[0])
            for c, cl, j in l[:max(1, int(round(TOP_DIRECT * len(l))))]:
                al.append({"le": auj.isoformat(), "cree": datetime.now().isoformat(timespec="seconds"), "joueur": j,
                           "annonce": {0: "baisse", 2: "hausse"}[cl], "confiance": round(c, 3), "parmi": len(l)})
    p = _chemin("slabiq_journal.json")
    try:
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            json.dump(jr, f, ensure_ascii=False)
        os.replace(p + ".tmp", p)
    except OSError:
        pass
    notes = [a for a in al if a.get("vrai")]
    k = sum(1 for a in notes if a.get("juste"))
    return {"justes": k, "notees": len(notes), "certitude": round(_wilson(k, len(notes)), 3),
            "ouvertes": [a for a in al if not a.get("vrai") and not a.get("non_mesurable")][-30:],
            "notees_l": notes[-40:]}


def passe_si_besoin():
    """La boucle du serveur (chaque heure) : le test et le journal en direct, une fois par semaine (le lundi ou plus tard)."""
    if _ETAT["en_cours"]:
        return None
    r = lire().get("rapport") or {}
    try:
        der = datetime.fromisoformat(str(r.get("le"))[:19])
    except ValueError:
        der = None
    if der and (datetime.now() - der).days < 7:
        return None
    return lancer()


def _donnees_sauver(par_j, wiki, nhl_, n_cartes):
    """12 nov 2026 (Mathieu : « tu peux pas tester direct avec les donnees de l'app ? ») : ce que le test a lu (les ventes
    carte par carte en log, Wikipedia jour par jour, les matchs LNH), en un fichier que l'admin telecharge pour rejouer
    le test ailleurs, sans aller-retour. Aucun compte, aucun titre, aucune annonce."""
    import gzip
    d = {"le": datetime.now().isoformat(timespec="seconds"), "cartes": par_j, "recrues": _RECRUES, "wiki": wiki, "nhl": nhl_,
         "n_cartes": n_cartes}
    try:
        p = _chemin("slabiq_test_donnees.json.gz")
        with gzip.open(p + ".tmp", "wt", encoding="utf-8") as f:
            json.dump(d, f, separators=(",", ":"))
        os.replace(p + ".tmp", p)
    except OSError:
        pass


def _donnees_lire(chemin):
    import gzip
    with gzip.open(chemin, "rt", encoding="utf-8") as f:
        d = json.load(f)
    par_j = {j: [[tuple(x) for x in pts] for pts in cj] for j, cj in d["cartes"].items()}
    nhl_ = {j: {**v, "matchs": [tuple(m) for m in v.get("matchs") or []]} for j, v in (d.get("nhl") or {}).items()}
    return par_j, d.get("recrues") or {}, d.get("wiki") or {}, nhl_, d.get("n_cartes") or 0


def executer(joueurs_max=JOUEURS_MAX, depuis=None):
    """depuis : un fichier slabiq_test_donnees.json.gz (rejouer le test hors du serveur, memes donnees)."""
    import base_ventes
    import nhl
    t0 = time.time()
    _ETAT.update(etape="ventes")
    _RECRUES.clear()
    if depuis:
        par_j, rec, wiki0, nhl0, n_c = _donnees_lire(depuis)
        _RECRUES.update(rec)
        return _apprendre(dict(sorted(par_j.items(), key=lambda kv: -sum(len(p) for p in kv[1]))[:joueurs_max]), wiki0, nhl0, n_c, t0)
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
    _donnees_sauver(par_j, wiki, nhl_, len(cartes))
    return _apprendre(par_j, wiki, nhl_, len(cartes), t0)


def _apprendre(par_j, wiki, nhl_, n_cartes, t0):
    toutes = [le for cj in par_j.values() for pts in cj for le, _e in pts]
    d_min, d_max = date.fromisoformat(min(toutes)), date.fromisoformat(max(toutes))
    _ETAT.update(etape="apprentissage")
    X, y, meta, noms_f = _exemples(par_j, wiki, nhl_, d_min, d_max)
    # combien de ventes on a, mois par mois : l'historique est le vrai carburant du test
    par_mois = {}
    for le in toutes:
        par_mois[le[:7]] = par_mois.get(le[:7], 0) + 1
    base = {"periode": [d_min.isoformat(), d_max.isoformat()], "joueurs": len(par_j), "cartes": n_cartes, "ventes": len(toutes),
            "ventes_mois": sorted(par_mois.items()), "exemples": sum(1 for m in meta if m[4]), "exemples_app": len(X)}
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
    top = _top_semaine(test, classes, y, meta)
    mv_t = [100 * (math.exp(meta[i][2]) - 1) for i, _p in test]
    marche_test = round(statistics.median(mv_t), 1) if mv_t else None    # le joueur median des memes semaines
    al1 = []
    for d in sorted({meta[i][0] for i, _p in test}):
        l = sorted([(max(p), i, p) for i, p in test if meta[i][0] == d and classes[int(max(range(len(p)), key=lambda q: p[q]))] != 1],
                   key=lambda t: -t[0])
        al1 += l[:max(1, int(round(TOP_SEMAINE[0] * len(l))))]
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
    for _c, i, p in sorted(al1, key=lambda t: -t[0]):           # 12 nov 2026 : les alertes du top 1 % de chaque semaine
        k = int(max(range(len(p)), key=lambda q: p[q]))
        if classes[k] != 1:
            ex.append({"joueur": meta[i][1], "le": meta[i][0], "annonce": {0: "baisse", 2: "hausse"}[classes[k]],
                       "confiance": round(max(p), 3), "vrai": {0: "baisse", 1: "stable", 2: "hausse"}[y[i]],
                       "mouvement_pct": round(100 * (math.exp(meta[i][2]) - 1), 1)})
        if len(ex) >= 40:
            break
    try:
        _ETAT.update(etape="direct")
        journal = _journal(par_j, wiki, nhl_, X, y, meta, d_min, d_max)
    except Exception as e:
        journal = {"erreur": f"{type(e).__name__} : {e}"[:200]}
    r = {"le": datetime.now().isoformat(timespec="seconds"), "duree_s": round(time.time() - t0), "methode": "v2-meme-carte-pas-a-pas",
         "direct": journal,
         **base, "testees": len(oos), "choix_seuil": len(choix), "test": len(test),
         "test_debut": meta[test[0][0]][0] if test else None,
         "repartition_test": {"baisse": y_te.count(0), "stable": y_te.count(1), "hausse": y_te.count(2)},
         "horizon_j": HORIZON_J, "seuil_pct": 10, "cible_precision": CIBLE_PRECISION,
         "resultat": res, "reperes": rep, "courbe": courbe, "meilleur": meilleur, "top_semaine": top, "marche_test_pct": marche_test,
         "signaux": [[k, round(v, 4)] for k, v in poids],
         "atteint": bool((top.get("0.01") or {}).get("certitude", 0) >= CIBLE_PRECISION),
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
            try:                                   # 12 nov 2026 : un seul coeur pour l'apprentissage, l'app garde l'autre
                from threadpoolctl import threadpool_limits
                lim = threadpool_limits(limits=1)
            except Exception:
                lim = None
            try:
                r = executer()
            finally:
                if lim is not None:
                    lim.unregister() if hasattr(lim, "unregister") else lim.restore_original_limits()
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
