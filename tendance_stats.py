"""
SLABCOACH - la tendance d'un JOUEUR, mesuree avec des methodes statistiques eprouvees (2 nov 2026).

Mathieu : « devrait juste etre le joueur ; une petite ampoule qui explique comment notre trend est analyse ; toujours se
baser sur des techniques prouvees en statistiques et dans le monde de la carte ».

La methode (ce que l'ampoule explique a l'ecran) :
  1. Ventes repetees (repeat sales, comme les indices de prix Case-Shiller et les indices de cartes) : chaque carte n'est
     comparee qu'a ELLE-MEME (meme set, meme parallele, meme numero ; raw et gradees separees). Un joueur ne « monte » pas
     parce qu'une carte chere de lui s'est vendue cette semaine.
  2. Fenetres : les 14 derniers jours contre les 4 semaines d'avant ; medianes (une vente extreme ne fait rien bouger).
     Une carte trop jeune pour avoir « avant » : ses premieres ventes contre ses dernieres (au moins 7 jours d'ecart).
  3. Rendements logarithmiques, bornes a x4 / div. 4 (winsorisation), puis la moyenne des cartes du joueur ponderee par le
     nombre de ventes de chaque carte (une carte vendue 30 fois pese plus qu'une carte vendue 3 fois).
  4. Retrecissement (shrinkage, estimateur de type James-Stein / bayesien) vers 0 : avec peu de ventes, la variation est
     ramenee vers « pas de changement » (N / (N + 8)). +465 % sur 6 ventes devient beaucoup plus modeste.
  5. Test de Mann-Whitney (non parametrique) sur les prix normalises de chaque carte : on ne montre une hausse ou une baisse
     que si elle est significative (p < 0,10), avec au moins 8 ventes et des cartes de 5 $ et plus (les cartes a 1 $ :
     surtout le port et le hasard).
  6. Plus vendues : le volume des 7 derniers jours (toutes les cartes du joueur), la mesure de liquidite du hobby.
"""
import math
import re
import statistics
from datetime import datetime, timedelta

JOURS_RECENT = 14
JOURS_AVANT = 28
PRIX_MIN = 5.0
N_MIN = 8
P_MAX = 0.10
P_FAIBLE = 0.30                 # « a confirmer »
N_FAIBLE = 6
K_SHRINK = 8.0
BORNE_LR = math.log(4)
ANNEE_LEGENDE = 2000             # 3 nov 2026 : une carte d'avant 2000 = une legende (Gretzky, Lemieux, Jordan...)


def _d(s):
    try:
        return datetime.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def _phi(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def mann_whitney_p(a, b):
    """p bilateral du test U de Mann-Whitney (approximation normale, correction des ex aequo et de continuite)."""
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2:
        return 1.0
    tout = sorted([(v, 0) for v in a] + [(v, 1) for v in b])
    rangs, i, ties = [0.0] * len(tout), 0, 0.0
    while i < len(tout):
        j = i
        while j + 1 < len(tout) and tout[j + 1][0] == tout[i][0]:
            j += 1
        r = (i + j) / 2 + 1
        for k in range(i, j + 1):
            rangs[k] = r
        t = j - i + 1
        ties += t ** 3 - t
        i = j + 1
    r1 = sum(r for r, (_v, g) in zip(rangs, tout) if g == 0)
    u1 = r1 - n1 * (n1 + 1) / 2
    mu = n1 * n2 / 2
    n = n1 + n2
    var = n1 * n2 / 12 * ((n + 1) - ties / (n * (n - 1)))
    if var <= 0:
        return 1.0
    z = (abs(u1 - mu) - 0.5) / math.sqrt(var)
    return max(0.0, min(1.0, 2 * (1 - _phi(max(0.0, z)))))


def mesure_carte(points, auj=None):
    """points : [[date, prix], ...] d'UNE carte. -> {lr, n_av, n_re, av, re, norm_av, norm_re, mediane} ou None."""
    auj = auj or datetime.now()
    pts = sorted((d, float(p)) for d, p in ((_d(a), b) for a, b in points or [] if a and b) if d and p > 0)
    if len(pts) < 4:
        return None
    med = statistics.median(p for _d, p in pts)
    if med < PRIX_MIN:
        return None
    d1, d2 = auj - timedelta(days=JOURS_RECENT), auj - timedelta(days=JOURS_RECENT + JOURS_AVANT)
    re = [p for d, p in pts if d >= d1]
    av = [p for d, p in pts if d2 <= d < d1]
    if len(re) < 2 or len(av) < 2:                      # carte jeune : ses premieres ventes contre ses dernieres
        if (pts[-1][0] - pts[0][0]).days < 7 or len(pts) < 6:
            return None
        k = len(pts) // 2
        av, re = [p for _d, p in pts[:k]], [p for _d, p in pts[k:]]
    a, b = statistics.median(av), statistics.median(re)
    lr = max(-BORNE_LR, min(BORNE_LR, math.log(b / a)))
    lm = math.log(med)
    return {"lr": lr, "n_av": len(av), "n_re": len(re), "av": round(a, 2), "re": round(b, 2), "mediane": round(med, 2),
            "norm_av": [math.log(p) - lm for p in av], "norm_re": [math.log(p) - lm for p in re]}


def par_joueur(cartes, auj=None):
    """cartes : [{joueur, recrue, points, ...}] (une entree par carte exacte). -> {joueur: mesure du joueur}."""
    auj = auj or datetime.now()
    sept = auj - timedelta(days=7)
    an_rec = auj.year - 1 if auj.month >= 7 else auj.year - 2
    gr = {}
    for c in cartes or []:
        j = str(c.get("joueur") or "").strip()
        if not j or "/" in j:                         # une carte a 2 joueurs ne dit rien d'UN joueur
            continue
        g = gr.setdefault(j.lower(), {"joueur": j, "recrue": False, "mes": [], "n_7j": 0, "n": 0, "pts": [], "cartes": set(), "an": None})
        an_c = c.get("annee")
        if not an_c:
            m_ = re.match(r"(?:q:)?.*?\b((?:19|20)\d\d)", str(c.get("produit_id") or "") + " " + str(c.get("carte") or ""))
            an_c = int(m_.group(1)) if m_ else None
        # une recrue = une carte de recrue de la saison (une Young Guns de 2023 : c'est un joueur de 3e annee)
        g["recrue"] = g["recrue"] or (bool(c.get("recrue")) and (an_c is None or an_c >= an_rec))
        if an_c:                                         # 3 nov 2026 : l'annee de sa plus vieille carte (legende, veteran)
            g["an"] = min(g["an"] or 9999, int(an_c))
        cle = (c.get("produit_id"), c.get("carte"))
        if cle in g["cartes"]:
            continue
        g["cartes"].add(cle)
        pts = c.get("points") or []
        prix = [float(p) for _d0, p in pts if p]
        if not prix or statistics.median(prix) < PRIX_MIN:      # les cartes a 1 $ ne font ni la tendance ni le volume
            continue
        g["n"] += len(pts)
        g["n_7j"] += sum(1 for d, _p in pts if (_d(d) or datetime.min) >= sept)
        m = mesure_carte(pts, auj)
        if m:
            g["mes"].append(m)
            lm = math.log(m["mediane"])
            g["pts"] += [(str(d)[:10], math.log(float(p)) - lm) for d, p in pts if d and p and float(p) > 0]
    out = {}
    for j, g in gr.items():
        if not g["n"]:
            continue
        mes = g["mes"]
        N = sum(m["n_av"] + m["n_re"] for m in mes)
        ere = "recrue" if g["recrue"] else "legende" if g["an"] and g["an"] < ANNEE_LEGENDE else "veteran"
        res = {"joueur": g["joueur"], "recrue": g["recrue"], "ere": ere, "n": g["n"], "n_7j": g["n_7j"], "n_cartes": len(g["cartes"])}
        if mes and N >= N_FAIBLE:
            w = [m["n_av"] + m["n_re"] for m in mes]
            lr = sum(m["lr"] * x for m, x in zip(mes, w)) / sum(w)
            lr_s = lr * N / (N + K_SHRINK)
            p = mann_whitney_p([v for m in mes for v in m["norm_av"]], [v for m in mes for v in m["norm_re"]])
            pts = sorted(g["pts"])
            # la courbe : l'indice du joueur (prix normalises, mediane mobile de 5 ventes), base 100
            idx = []
            for i in range(len(pts)):
                f = [v for _d, v in pts[max(0, i - 4):i + 1]]
                idx.append([pts[i][0], round(100 * math.exp(statistics.median(f)), 1)])
            res.update(pct=round(100 * (math.exp(lr_s) - 1)), p=round(p, 3), n_t=N, significatif=p < P_MAX and N >= N_MIN and abs(lr_s) >= math.log(1.05),
                       points=idx[-40:], recent=round(statistics.median(m["re"] for m in mes), 2),
                       avant=round(statistics.median(m["av"] for m in mes), 2), n_mesurees=len(mes))
        out[j] = res
    return out


def listes(cartes, auj=None, n=80):
    """-> {hausses, baisses, plus_vendues} par joueur."""
    pj = par_joueur(cartes, auj)
    # 2 nov 2026 (Mathieu : « juste eux comme rising ? ») : d'abord les tendances CONFIRMEES (p < 0,10) ; la liste se complete
    # avec les tendances « a confirmer » (p < 0,30, au moins 6 ventes, au moins 5 %), marquees comme telles a l'ecran
    for x in pj.values():
        x["confirme"] = bool(x.get("significatif"))
    faibles = [x for x in pj.values() if not x.get("significatif") and x.get("pct") is not None and x.get("p") is not None
               and x["p"] < P_FAIBLE and (x.get("n_t") or 0) >= N_FAIBLE and abs(x["pct"]) >= 5]
    sig = [x for x in pj.values() if x.get("significatif")]
    def liste(signe):
        a = sorted((x for x in sig if x["pct"] * signe > 0), key=lambda x: (-abs(x["pct"]), x["p"]))
        b = sorted((x for x in faibles if x["pct"] * signe > 0), key=lambda x: (-abs(x["pct"]), x["p"]))
        return (a + b)[:n]
    return {"hausses": liste(1), "baisses": liste(-1),
            "plus_vendues": sorted((x for x in pj.values() if x["n_7j"]), key=lambda x: (-x["n_7j"], -x["n"]))[:n]}
