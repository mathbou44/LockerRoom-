"""
SLABCOACH - les types de cartes qui comptent le plus (12 nov 2026).

Mathieu : « est-ce que SlabIQ prend en consideration les types de cartes plus populaires, comme des Young Guns gradees,
des Future Watch Auto, des autopatchs, Premier, Stature ? Une Dazzler PSA 10 versus une Young Guns PSA 10, ca n'a rien a
voir. Regarde dans nos databases. »

Chaque vente de nos archives (base_ventes, 365 jours) recoit un TYPE : la famille de la carte (Young Guns, Future Watch Auto,
The Cup RPA, Premier, Dazzlers...) et sa note (gradee 10, gradee 9, autre gradee, non gradee). Pour chaque type :
  - prime : combien la carte vaut par rapport a la carte typique du MEME joueur (mediane de prix / prix / mediane du joueur) :
    on compare des Lundell a des Lundell, la popularite du joueur ne fausse rien ;
  - volume : le nombre de ventes et de joueurs (la liquidite, telle que nos archives la voient) ;
  - score 0-100 : 75 % le rang de la prime, 25 % le rang du volume.
  - fiabilite : le classement des 8 premiers mois contre celui des 4 derniers (correlation de rangs).
Par joueur (assez de ventes) : ses types du plus fort au plus faible. Le public voit le CLASSEMENT et le score, jamais un prix
(licence eBay) ; l'admin voit les primes.
"""
import json
import math
import os
import re
import statistics
import threading
import time
from datetime import datetime, timedelta

_verrou = threading.Lock()
_ETAT = {"mt": None, "d": None, "en_cours": False}
N_MIN = 25            # ventes d'un type pour le classer
J_MIN = 4             # joueurs differents
JOUEUR_MIN = 8        # ventes d'un joueur pour son propre classement

# (cle, nom, motif sur le texte normalise de cartes_match : yg -> young guns, fw -> future watch, autograph/signature -> auto)
FAMILLES = [
    ("cup_rpa", "The Cup RPA", r"\bthe cup\b.*\b(rpa|rc auto patch|auto patch|patch auto|rc patch auto)\b"),
    ("cup_auto", "The Cup Auto", r"\bthe cup\b.*\bauto\b"),
    ("cup", "The Cup", r"\bthe cup\b"),
    ("premier_auto", "Premier Auto Patch", r"\bpremier\b.*\b(auto|patch|rpa|swatch)\b"),
    ("fw_auto", "Future Watch Auto", r"\bfuture watch\b.*\bauto\b|\bauto\b.*\bfuture watch\b"),
    ("ice_premieres", "Ice Premieres", r"\bice\b.*\bpremieres?\b|\bpremieres?\b.*\bice\b"),
    ("yg_canvas", "Young Guns Canvas", r"\byoung guns?\b.*\bcanvas\b|\bcanvas\b.*\byoung guns?\b"),
    ("yg_exclusives", "Young Guns Exclusives", r"\byoung guns?\b.*\b(exclusives|high gloss|outburst|clear cut)\b"),
    ("young_guns", "Young Guns", r"\byoung guns?\b"),
    ("future_watch", "Future Watch", r"\bfuture watch\b"),
    ("decades", "Decades", r"\bdecades?\b"),
    ("black_diamond", "Black Diamond", r"\bblack diamond\b"),
    ("trilogy", "Trilogy", r"\btrilogy\b"),
    ("artifacts", "Artifacts", r"\bartifacts\b"),
    ("spgu", "SP Game Used", r"\bsp game used\b|\bspgu\b"),
    ("sp_authentic", "SP Authentic", r"\bsp authentic\b"),
    ("ice", "Ice", r"\bice\b"),
    ("stature", "Stature", r"\bstature\b"),
    ("synergy", "Synergy", r"\bsynergy\b"),
    ("allure", "Allure", r"\ballure\b"),
    ("chronology", "Chronology", r"\bchronology\b"),
    ("credentials", "Credentials", r"\bcredentials\b"),
    ("dazzlers", "Dazzlers", r"\bdazzlers?\b"),
    ("opc_platinum", "O-Pee-Chee Platinum", r"\bo-pee-chee platinum\b|\bopc platinum\b"),
    ("opc", "O-Pee-Chee", r"\bo-pee-chee\b"),
    ("mvp", "MVP", r"\bmvp\b"),
    ("metal", "Metal Universe", r"\bmetal universe\b|\bskybox metal\b"),
    ("auto_patch", "Auto Patch", r"\bauto\b.*\b(patch|swatch|jersey|relic)\b|\b(patch|swatch|jersey|relic)\b.*\bauto\b"),
    ("auto", "Auto", r"\bauto\b"),
    ("patch", "Patch / jersey", r"\b(patch|swatch|jersey|relic)\b"),
    ("upper_deck", "Upper Deck (base)", r"\bupper deck\b"),
]
_FAM = [(k, n, re.compile(m)) for k, n, m in FAMILLES]
NOTES = {"10": "gradée 10", "9": "gradée 9", "g": "gradée", "r": ""}          # 10 = PSA 10, BGS 9.5 et plus, SGC 10


def _texte(titre):
    import cartes_match
    try:
        return cartes_match._decoder_memo(titre or "")
    except Exception:
        return {"texte": str(titre or "").lower(), "grade": None}


def note_de(grade):
    if not grade:
        return "r"
    n = str(grade.get("note") or "")
    if n in ("10", "9.5") or n.startswith("10"):
        return "10"
    if n.startswith("9"):
        return "9"
    return "g"


def famille(titre):
    """Le titre -> (cle, nom) de sa famille, ou (None, None)."""
    t = _texte(titre).get("texte") or ""
    for k, n, rx in _FAM:
        if rx.search(t):
            return k, n
    return None, None


def type_de(titre):
    """Le titre -> « famille|note » (ex. « young_guns|10 »), ou None."""
    d = _texte(titre)
    t = d.get("texte") or ""
    for k, _n, rx in _FAM:
        if rx.search(t):
            return k + "|" + note_de(d.get("grade"))
    return None


def nom_type(cle, court=False):
    f, _, nt = str(cle).partition("|")
    nom = next((n for k, n, _ in FAMILLES if k == f), f)
    lib = NOTES.get(nt, "")
    return (nom + (" " + lib if lib else "")).strip()


# -- l'apprentissage --------------------------------------------------------------------------------------------------
def _rangs(d):
    """{cle: valeur} -> {cle: rang 0-100}."""
    l = sorted(d, key=lambda k: d[k])
    n = len(l)
    return {k: (100.0 * i / (n - 1) if n > 1 else 50.0) for i, k in enumerate(l)}


def _spearman(a, b):
    ks = [k for k in a if k in b]
    if len(ks) < 5:
        return None
    ra, rb = _rangs({k: a[k] for k in ks}), _rangs({k: b[k] for k in ks})
    ma, mb = statistics.mean(ra.values()), statistics.mean(rb.values())
    num = sum((ra[k] - ma) * (rb[k] - mb) for k in ks)
    den = math.sqrt(sum((ra[k] - ma) ** 2 for k in ks) * sum((rb[k] - mb) ** 2 for k in ks))
    return round(num / den, 3) if den else None


def _primes(ventes):
    """[(joueur, cle, prix)] -> {cle: [log(prix / mediane du joueur)]}, {joueur: {cle: [log ratio]}}."""
    par_j = {}
    for j, k, p in ventes:
        par_j.setdefault(j, []).append(p)
    med = {j: statistics.median(l) for j, l in par_j.items() if len(l) >= 3}
    out, pj = {}, {}
    for j, k, p in ventes:
        m = med.get(j)
        if not m or p <= 0:
            continue
        x = math.log(p / m)
        out.setdefault(k, []).append((j, x))
        pj.setdefault(j, {}).setdefault(k, []).append(x)
    return out, pj


def _table(v):
    """[(joueur, type, prix, le)] -> {type: {nom, n, joueurs, prime, score}}."""
    prim, _ = _primes([(x[0], x[1], x[2]) for x in v])
    vol = {}
    for x in v:
        k = x[1]
        vol[k] = vol.get(k, 0) + 1
    types = {}
    for k, l in prim.items():
        js = {j for j, _ in l}
        if len(l) < N_MIN or len(js) < J_MIN:
            continue
        types[k] = {"nom": nom_type(k), "n": vol.get(k, len(l)), "joueurs": len(js),
                    "prime": round(math.exp(statistics.median([x for _, x in l])), 2)}
    rp = _rangs({k: math.log(t["prime"]) for k, t in types.items()})
    rv = _rangs({k: math.log(t["n"]) for k, t in types.items()})
    for k, t in types.items():
        t["score"] = round(0.75 * rp[k] + 0.25 * rv[k])
    return types


def _rangs_moy(xs):
    """Les rangs (les ex aequo prennent leur rang moyen)."""
    o = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and xs[o[j + 1]] == xs[o[i]]:
            j += 1
        for k in range(i, j + 1):
            r[o[k]] = (i + j) / 2.0
        i = j + 1
    return r


def _rho(xs, ys):
    """La correlation de rangs (Spearman) de deux listes de meme longueur."""
    if len(xs) < 30:
        return None
    a, b = _rangs_moy(xs), _rangs_moy(ys)
    ma, mb = statistics.mean(a), statistics.mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return round(num / den, 3) if den else None


def mesurer(v, coupe, n_max=20000):
    """12 nov 2026 (Mathieu : « si tu changes l'algorithme, teste pour etre sur qu'on est encore meilleur ») : sur les ventes
    APRES la coupe (jamais vues par la table apprise AVANT), est-ce que la part carte du score classe mieux les cartes d'un
    meme joueur (prix / sa carte typique) avec les types qu'avant ? -> {avant, apres, n} (correlations de rangs)."""
    import score_slab
    tab = _table([x for x in v if x[3] < coupe])
    test = [x for x in v if x[3] >= coupe and len(x) > 4][:n_max]
    if not tab or len(test) < 30:
        return None
    meds = {}
    for j, _k, p, _le, _t in test:
        meds.setdefault(j, []).append(p)
    meds = {j: statistics.median(l) for j, l in meds.items() if len(l) >= 3}
    xs, avant, apres = [], [], []
    for j, k, p, _le, titre in test:
        if j not in meds:
            continue
        try:
            s0 = score_slab.carte(titre, avec_type=False)["score"]
        except Exception:
            continue
        s1 = 0.7 * min(100.0, s0) + 0.3 * tab[k]["score"] if k in tab else s0
        xs.append(math.log(p / meds[j]))
        avant.append(s0)
        apres.append(s1)
    return {"avant": _rho(avant, xs), "apres": _rho(apres, xs), "n": len(xs), "types_appris": len(tab)}


def apprendre(ventes, maintenant=None, mesure=True):
    """ventes = [(joueur, titre, prix, le AAAA-MM-JJ)] -> la table (voir l'en-tete)."""
    maintenant = maintenant or datetime.now()
    v = []
    for j, titre, p, le in ventes:
        try:
            p = float(p)
        except (TypeError, ValueError):
            continue
        if not j or p < 1:
            continue
        k = type_de(titre)
        if k:
            v.append((j, k, p, str(le or "")[:10], titre))
    _, pj = _primes([(j, k, p) for j, k, p, *_ in v])
    types = _table(v)
    # la fiabilite : le classement des 8 premiers mois contre celui des 4 derniers
    coupe = (maintenant - timedelta(days=120)).strftime("%Y-%m-%d")
    a, _ = _primes([(j, k, p) for j, k, p, le, _t in v if le < coupe])
    b, _ = _primes([(j, k, p) for j, k, p, le, _t in v if le >= coupe])
    ma = {k: statistics.median([x for _, x in l]) for k, l in a.items() if len(l) >= 15 and k in types}
    mb = {k: statistics.median([x for _, x in l]) for k, l in b.items() if len(l) >= 15 and k in types}
    # par joueur : ses types (au moins 2 ventes du type), du plus fort au plus faible
    joueurs = {}
    for j, d in pj.items():
        n = sum(len(l) for l in d.values())
        if n < JOUEUR_MIN:
            continue
        l = [(k, len(x), math.exp(statistics.median(x))) for k, x in d.items() if len(x) >= 2]
        if len(l) >= 2:
            l.sort(key=lambda t: -(t[2] * (1 + 0.05 * min(10, t[1]))))
            joueurs[j] = [[k, n_, round(pr, 2)] for k, n_, pr in l[:10]]
    if len(joueurs) > 1500:
        joueurs = dict(sorted(joueurs.items(), key=lambda kv: -sum(x[1] for x in kv[1]))[:1500])
    out = {"le": maintenant.isoformat(timespec="seconds"), "ventes": len(v), "types": types, "joueurs": joueurs,
           "fiabilite": _spearman(ma, mb), "fiabilite_n": len(set(ma) & set(mb))}
    if mesure:
        try:
            out["mesure"] = mesurer(v, coupe)
        except Exception as e:
            out["mesure"] = {"erreur": repr(e)[:200]}
    return out


# -- le fichier ---------------------------------------------------------------------------------------------------------
def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "types_cartes.json")


def lire():
    p = _chemin()
    try:
        mt = os.path.getmtime(p)
    except OSError:
        return {}
    if _ETAT["mt"] != mt:
        try:
            with open(p, encoding="utf-8") as f:
                _ETAT["d"] = json.load(f) or {}
            _ETAT["mt"] = mt
        except (OSError, ValueError):
            return {}
    return _ETAT["d"] or {}


def ecrire(d):
    p = _chemin()
    with _verrou:
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(p + ".tmp", p)


def passe(jours=365):
    import base_ventes
    t0 = time.time()
    d = apprendre(base_ventes.ventes_titres(jours))
    d["duree_s"] = round(time.time() - t0, 1)
    ecrire(d)
    return d


def passe_si_besoin():
    """Une fois par semaine (la boucle du serveur, chaque heure)."""
    try:
        if time.time() - os.path.getmtime(_chemin()) < 6 * 86400:
            return None
    except OSError:
        pass
    if _ETAT["en_cours"]:
        return None
    _ETAT["en_cours"] = True

    def tache():
        try:
            r = passe()
            print("Types de cartes : %d ventes, %d types, fiabilite %s" % (r["ventes"], len(r["types"]), r.get("fiabilite")), flush=True)
        except Exception as e:
            print("Types de cartes : " + repr(e), flush=True)
        finally:
            _ETAT["en_cours"] = False
    threading.Thread(target=tache, daemon=True, name="types-cartes").start()
    return True


def aide():
    """Le type compte dans le score de la carte SEULEMENT si le test avant / apres (mesurer) dit qu'il classe mieux."""
    m = lire().get("mesure") or {}
    if m.get("apres") is None or m.get("avant") is None:
        return True
    return m["apres"] > m["avant"]


# -- les lectures -------------------------------------------------------------------------------------------------------
def info(titre):
    """Le type d'une carte et son score 0-100 (None si le type n'est pas encore classe)."""
    k = type_de(titre)
    if not k:
        return None
    T = lire().get("types") or {}
    t = T.get(k)
    if not t:
        return {"type": k, "nom": nom_type(k)}
    rang = 1 + sum(1 for x in T.values() if x["score"] > t["score"])
    return {"type": k, "nom": t["nom"], "score": t["score"], "rang": rang, "sur": len(T)}


def classement(n=20, admin=False):
    T = lire().get("types") or {}
    l = sorted(T.items(), key=lambda kv: -kv[1]["score"])[:n]
    return [{"type": k, "nom": t["nom"], "score": t["score"], "joueurs": t["joueurs"],
             **({"prime": t["prime"], "n": t["n"]} if admin else {})} for k, t in l]


def du_joueur(nom, admin=False):
    """Les types de cartes du joueur, du plus fort au plus faible : les siens s'il a assez de ventes, sinon le classement
    general. -> {"source": "joueur"|"general", "types": [{type, nom, rang}]}."""
    d = lire()
    J = d.get("joueurs") or {}
    k = next((x for x in J if x.lower() == str(nom or "").strip().lower()), None)
    if k:
        return {"source": "joueur", "types": [{"type": c, "nom": nom_type(c), "rang": i + 1, **({"prime": pr, "n": n_} if admin else {})}
                                              for i, (c, n_, pr) in enumerate(J[k][:8])]}
    return {"source": "general", "types": [{"type": x["type"], "nom": x["nom"], "rang": i + 1} for i, x in enumerate(classement(8, admin))]}
