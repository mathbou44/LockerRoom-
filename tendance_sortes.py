"""
SLABCOACH - la tendance d'une SORTE de carte (25 nov 2026).

Mathieu (capture des Tendances : « Au plus bas », « Au plus haut », par joueur) : « comme ca mais avec les sortes / paralleles » ;
« la progression de la moyenne du prix de vente de chacune des variantes » ; « l'integrer dans les tuiles du Radar : quelque chose
de clean, petit, style Apple ; et plus visible et comprehensible quand on clique sur la carte » ; « mis a jour aux 3 jours ».

La meme methode que la tendance d'un joueur (tendance_stats, expliquee a l'ecran), avec la SORTE a la place du joueur :
  1. ventes repetees : chaque carte exacte (un joueur, une sorte, raw et gradees a part) n'est comparee qu'a ELLE-MEME ; une sorte ne
     « monte » pas parce qu'une carte chere s'est vendue cette semaine ;
  2. les 30 derniers jours contre les 60 d'avant, medianes ; rendement logarithmique borne a x4 / div. 4 ;
  3. la moyenne des cartes de la sorte, ponderee par leur nombre de ventes ; retrecissement vers 0 (N / (N + 8)) ;
  4. test de Mann-Whitney sur les prix normalises : une hausse ou une baisse n'est « confirmee » que si p < 0,10 ;
  5. une sorte ne compte que si elle a assez de cartes differentes et de ventes (CARTES_MIN, VENTES_MIN) : sinon rien.
La courbe : l'indice de la sorte par semaine sur les 90 jours compares ; 100 = le niveau des 60 jours d'avant (chaque vente est
divisee par la mediane de SA carte dans ces 60 jours) : la courbe et le pourcentage racontent la meme chose, et une sorte dont la
courbe recente contredit le pourcentage n'est PAS annoncee (garde-fou « coherent »). JAMAIS un prix :
ce module ne rend que des pourcentages et un indice (le public ne voit aucune valeur tiree des ventes).
"""
import json
import math
import os
import re
import statistics
import threading
import time
from datetime import datetime, timedelta

JOURS_RECENT = 30
JOURS_AVANT = 60
JOURS_LUS = 130                  # la courbe : ~18 semaines
CARTES_MIN = 5                   # cartes differentes mesurees dans la sorte
VENTES_MIN = 40                  # ventes dans les deux periodes
SEMAINE_MIN = 12                 # ventes dans la fenetre glissante de 3 semaines pour un point de la courbe
PCT_MIN = 5                      # sous 5 % : « stable »
AUX_JOURS = 3                    # refait aux 3 jours (comme le score appris)
N_LISTE = 30
# 25 nov 2026 (Mathieu : « j'espere que le trend des types de carte est associe aux joueurs ? ») : mesure sur les ventes : dans les
# Young Guns, 117 joueurs en baisse, 70 en hausse, 37 stables (Fowler +83 %, Cole Hutson -29 %) : la sorte « tous joueurs » ne dit
# rien de LA carte d'un joueur. La mesure principale devient donc la carte = un joueur + une sorte ; la sorte reste a cote.
CARTE_VENTES_MIN = 12            # ventes de la carte dans les deux periodes
CARTE_PERIODE_MIN = 4            # au moins 4 ventes dans chacune des deux periodes
CARTE_SEMAINE_MIN = 4            # ventes dans la fenetre de 3 semaines pour un point de la courbe d'une carte
DISPERSION_MAX = 2.5             # q75 / q25 des prix d'avant : au-dela, la recherche melange plusieurs cartes : rien n'est annonce
N_LISTE_CARTES = 25
LISTE_VENTES_MIN = 20            # dans les listes « en hausse / en baisse » : une carte qui a au moins 20 ventes
# 25 nov 2026, 22 h 06 (Mathieu : « on se fout des paralleles sans valeur qui se vendent 20 $ et moins, a part les Young Guns ») :
# hors Young Guns, une carte ne compte que si elle se vend d'habitude 20 $ et plus (la mediane de ses ventes). Par la VALEUR et non
# par l'etiquette : un insert non numerote qui vaut cher (Tim Hortons, Fleer Ultra, un « case hit ») reste ; une numerotee a 8 $ sort.
PRIX_MIN_HORS_YG = 20.0
# 25 nov 2026, 22 h 07 (Mathieu : « double et triple verifie ; on n'a pas le droit a l'erreur ») : la verification sur le vrai chemin du
# serveur (export du 24 nov, 862 000 ventes) a montre trois choses, corrigees ici :
#   1. la meme vente est rangee sous plusieurs recherches (152 000 ventes sur 582 000 : « jacob fowler young guns », « jacob fowler
#      hockey »...) : les recherches d'une meme carte sont FONDUES et chaque vente (son numero) n'est comptee qu'UNE fois ;
#   2. une recherche sans annee peut ramener plusieurs saisons de la meme sorte : la saison se lit dans le titre de chaque vente, et
#      la carte ne compte que si SAISON_PART_MIN de ses ventes datees sont de la meme saison ;
#   3. « rookie auto », « auto », « psa 10 » ne nomment pas UNE carte (toutes les autos de recrue d'un joueur) : ecartees (_precise).
SAISON_PART_MIN = 0.90
SAISON_DATEES_MIN = 4
FRAIS_J = 10                     # la derniere vente lue de la carte a 10 jours ou moins (sinon « 30 derniers jours » serait faux)
PARTIEL_MAX = 0.02               # au plus 2 % des ventes de la fenetre pas encore triees, sinon on attend la passe suivante
ESSAI_S = 600                    # entre deux essais quand le tri des ventes n'est pas fini
COULEURS = {"gold", "red", "blue", "green", "silver", "black", "purple", "orange", "pink", "yellow", "white", "bronze", "emerald",
            "ruby", "sapphire", "violet", "rainbow", "teal", "aqua", "platinum", "copper", "magenta", "speckle"}
# Le nom d'un SET (ou d'un produit) seul ne nomme pas UNE carte : « bobby orr o-pee-chee » 1970-71, c'est sa carte de base, son
# etoile et ses trophees ; « connor mcdavid portfolio », quatre cartes. Il faut un nom de carte en plus du set (« young guns »,
# « dazzlers blue », « mvp gold script », « future watch ») : sinon la recherche est un panier, ecarte.
SETS = ("o-pee-chee platinum", "o-pee-chee", "opc platinum", "opc", "upper deck", "ud", "parkhurst", "topps", "score", "fleer ultra",
        "fleer", "ultra", "mvp", "artifacts", "ice", "spx", "sp game used", "game used", "sp authentic", "authentic", "sp",
        "black diamond", "portfolio", "allure", "synergy", "trilogy", "premier", "the cup", "cup", "ultimate collection", "ultimate",
        "stature", "credentials", "engrained", "chronology", "skybox", "metal universe", "bowman", "donruss", "pro set", "leaf",
        "pinnacle", "tim hortons", "series 1", "series 2", "extended", "be a player", "bap", "in the game", "itg", "pacific",
        "victory", "collector's choice", "select", "prizm", "chrome", "finest", "stadium club", "heritage", "clear cut", "platinum",
        "overtime", "compendium", "parkside", "team canada", "world juniors", "exquisite", "sp signature", "signature")
ATTRIBUTS = {"auto", "autograph", "autographs", "autographed", "signed", "patch", "rc", "rookie", "rookies", "numbered", "jersey",
             "relic", "base", "card", "cards", "hockey", "nhl", "ssp", "short", "print", "raw", "graded", "gem", "mint", "lot"}
P_CARTE = 0.01                   # LA carte d'un joueur : p < 0,01 (sur 200 cartes testees, 2 fausses alertes au plus, pas 20)
_PRECIS = {}
_ESSAI = {"le": 0.0}
_verrou = threading.Lock()
_MEM = {"mtime": None, "v": None, "idx": None}
_TITRES = {}

# des recherches qui ne sont pas une sorte : tout le joueur, une note seule, un mot seul qui ne dit pas quelle carte
PAS_SORTE = {"", "hockey", "nhl", "auto", "patch", "rc", "numbered", "population count", "gold", "red", "blue", "green", "silver", "black",
             "speckle", "rainbow", "card", "cards", "lot", "round draft", "team color", "relic", "jersey", "base", "insert", "parallel",
             "upper deck", "series 1", "series 2", "extended"}
_RE_NOTE_SEULE = re.compile(r"^(psa|bgs|sgc|cgc|ksa|gma|hga|tag|mnt|csg|beckett)( ?\d+(\.\d)?)?$")
_RE_NOTE = re.compile(r"\b(psa|bgs|sgc|cgc|ksa|gma|hga|tag|mnt|csg)\b ?(\d+(?:\.\d)?)?")
# l'ecriture a l'ecran (la cle est en minuscules, sans accents)
_ECRIT = (("young guns", "Young Guns"), ("o-pee-chee", "O-Pee-Chee"), ("rc auto", "Rookie Auto"), ("future watch", "Future Watch"),
          ("clear cut", "Clear Cut"), ("high gloss", "High Gloss"), ("black diamond", "Black Diamond"), ("game used", "SP Game Used"),
          ("ultimate collection", "Ultimate Collection"), ("metal universe", "Metal Universe"), ("tim hortons", "Tim Hortons"),
          ("the cup", "The Cup"), ("cup", "The Cup"), ("authentic", "SP Authentic"), ("spx", "SPx"), ("mvp", "MVP"), ("rc", "Rookie"),
          ("ud", "UD"), ("opc", "OPC"), ("ice", "Ice"), ("fw", "Future Watch"))


def _joueur_ok(j):
    return bool(j) and "/" not in j and not re.search(r"\d", j)


def cle_sorte(joueur, carte):
    """La sorte d'une carte : sa recherche sans le joueur ni l'annee (« ivan demidov young guns canvas » -> « young guns canvas »).
    None : pas une sorte (tout le joueur, une note seule, une equipe)."""
    import cartes_match
    t = cartes_match._norm(str(carte or ""))
    for w in cartes_match._norm(str(joueur or "")).split():
        t = re.sub(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", " ", t)
    t = re.sub(r"\b(19|20)\d\d(-\d\d(\d\d)?)?\b", " ", t)
    t = re.sub(r"#\s*\d+\b", " ", t)                    # le numero de la carte ; la numerotation (« /99 ») RESTE : une autre carte
    t = re.sub(r"/\s+(\d)", r"/\1", t)
    mots = t.split()
    # « clear cut clear cut auto » (le synonyme a double l'expression) : une seule fois
    out = []
    for i, w in enumerate(mots):
        if len(out) >= 2 and i + 1 < len(mots) and out[-2:] == [w, mots[i + 1]]:
            continue
        if out and out[-1] == w:
            continue
        out.append(w)
    for k in (2, 3):                                     # « a b a b » -> « a b »
        i = 0
        while i + 2 * k <= len(out):
            if out[i:i + k] == out[i + k:i + 2 * k]:
                del out[i + k:i + 2 * k]
            else:
                i += 1
    c = " ".join(out).strip()
    if c in PAS_SORTE or _RE_NOTE_SEULE.match(c) or len(c) > 48:
        return None
    try:                                                 # « young guns montreal canadiens », « york rangers » : une equipe
        import sports
        eq = {w for code in (getattr(sports, "_LNH", {}) or {}) for w in cartes_match._norm(" ".join(
            str(x) for x in (sports._LNH[code] if isinstance(sports._LNH[code], (list, tuple)) else [sports._LNH[code]]))).split() if len(w) >= 5}
        if any(w in eq for w in out):
            return None
    except Exception:
        pass
    return c


def libelle(cle):
    """Le nom a l'ecran (le meme en francais et en anglais : ce sont des noms de cartes)."""
    t = " " + str(cle or "") + " "
    t = _RE_NOTE.sub(lambda m: " " + m.group(1).upper() + ((" " + m.group(2)) if m.group(2) else "") + " ", t)
    pris = []
    for a, b in _ECRIT:
        t2 = re.sub(r"(?<![a-z0-9-])" + re.escape(a) + r"(?![a-z0-9-])", "\x00%d\x00" % len(pris), t)
        if t2 != t:
            pris.append(b)
            t = t2
    mots = [w if (w.isupper() or "\x00" in w) else w.capitalize() for w in t.split()]
    s = " ".join(mots)
    for i, b in enumerate(pris):
        s = s.replace("\x00%d\x00" % i, b)
    return s


def _jour(s):
    try:
        return datetime.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def _etalement(pts, av):
    """A quel point les prix d'une MEME semaine sont etales (q75 / q25 des ecarts a la mediane de la semaine). Une carte qui monte
    ou baisse garde des prix serres chaque semaine ; une recherche qui melange deux cartes, non. Pas assez de semaines pleines :
    l'etalement des 60 jours d'avant (q75 / q25)."""
    sem = {}
    for d, p in pts:
        sem.setdefault(d - timedelta(days=d.weekday()), []).append(math.log(p))
    res = []
    for l in sem.values():
        if len(l) >= 3:
            m = statistics.median(l)
            res += [x - m for x in l]
    if len(res) >= 8:
        q = statistics.quantiles(res, n=4)
        return math.exp(q[2] - q[0])
    if len(av) >= 4:
        q = statistics.quantiles(av, n=4)
        return q[2] / q[0] if q[0] > 0 else None
    return None


def mesure_carte(points, auj, lu=None):
    """Une carte : ses 30 derniers jours contre les 60 d'avant. -> {lr, n_av, n_re, mediane, norm_av, norm_re} ou None.
    lu : la date de la derniere lecture de ses ventes ; sans elle, la date de sa derniere vente. Plus de FRAIS_J jours : rien."""
    import tendance_stats as ts
    pts = sorted((d, float(p)) for d, p in ((_jour(a), b) for a, b in points or [] if a and b) if d and p > 0)
    if len(pts) < 4:
        return None
    vu = max(pts[-1][0], _jour(lu) or pts[-1][0])
    if (auj - vu).days > FRAIS_J:
        return None
    med = statistics.median(p for _d, p in pts)
    if med < ts.PRIX_MIN:
        return None
    d1, d2 = auj - timedelta(days=JOURS_RECENT), auj - timedelta(days=JOURS_RECENT + JOURS_AVANT)
    re_ = [p for d, p in pts if d >= d1]
    av = [p for d, p in pts if d2 <= d < d1]
    if len(re_) < 2 or len(av) < 2:
        return None                                      # pas de « premieres contre dernieres » ici : une sorte a assez de cartes
    a, b = statistics.median(av), statistics.median(re_)
    lr = max(-ts.BORNE_LR, min(ts.BORNE_LR, math.log(b / a)))
    lm = math.log(med)
    disp = _etalement([(d, p) for d, p in pts if d >= d2], av)
    return {"lr": lr, "disp": disp, "n_av": len(av), "n_re": len(re_), "mediane": med,
            "norm_av": [math.log(p) - lm for p in av], "norm_re": [math.log(p) - lm for p in re_],
            # la courbe : chaque vente des 90 jours compares, en ecart au niveau de SA carte dans les 60 jours d'avant
            # (0 = le niveau d'avant) : la courbe et le pourcentage racontent alors la meme chose
            "norm": [(d, math.log(p) - math.log(a)) for d, p in pts if d >= d2]}


def _agreger(mes, auj, semaine_min):
    """Plusieurs cartes exactes (chacune comparee a elle-meme) -> une mesure : le %, le test, la courbe, le garde-fou."""
    import tendance_stats as ts
    N = sum(m["n_av"] + m["n_re"] for m in mes)
    w = [m["n_av"] + m["n_re"] for m in mes]
    lr = sum(m["lr"] * x for m, x in zip(mes, w)) / sum(w)
    lr_s = lr * N / (N + ts.K_SHRINK)
    p = ts.mann_whitney_p([v for m in mes for v in m["norm_av"]], [v for m in mes for v in m["norm_re"]])
    pct = round(100 * (math.exp(lr_s) - 1))
    # la courbe : l'indice par semaine, 100 = le niveau des 60 jours d'avant (mediane des ecarts, chaque point = la semaine
    # et les deux d'avant : une courbe qui ne saute pas sur 5 ventes)
    lundi = lambda d: d - timedelta(days=d.weekday())
    sem = {}
    for m in mes:
        for d, v in m["norm"]:
            sem.setdefault(lundi(d), []).append(v)
    d1 = auj - timedelta(days=JOURS_RECENT)
    serie = []
    for s_ in sorted(sem):
        l = [v for k_ in (s_, s_ - timedelta(days=7), s_ - timedelta(days=14)) for v in sem.get(k_, ())]
        if len(l) >= semaine_min:
            serie.append([s_.strftime("%Y-%m-%d"), round(100 * math.exp(statistics.median(l)), 1)])
    if len(serie) < 2:
        serie = []
    rec = [v for s_, v in serie if _jour(s_) >= lundi(d1)]
    # garde-fou : la courbe des 30 derniers jours doit aller dans le meme sens que le pourcentage, sinon rien n'est annonce
    coherent = bool(rec) and (statistics.mean(rec) - 100) * pct > 0
    return {"pct": pct, "brut": round(100 * (math.exp(lr) - 1)), "p": round(p, 3) if p is not None else None, "n": N,
            "n_re": sum(m["n_re"] for m in mes), "serie": serie[-18:], "n_recents": len(rec), "d_rec": lundi(d1).strftime("%Y-%m-%d"),
            "coherent": coherent,
            "net": p is not None and p < ts.P_MAX and coherent}


def _sens(a, ok=True):
    confirme = bool(a["net"] and abs(a["pct"]) >= PCT_MIN and ok)
    return confirme, ("hausse" if a["pct"] >= PCT_MIN else "baisse" if a["pct"] <= -PCT_MIN else "stable") if confirme else "stable"


_CONNUS = {"t": None}


def _cle_joueur(j):
    """Le joueur, ecrit comme la liste des joueurs connus (valeurs + catalogue) ; None si ce n'est pas un joueur connu : une
    recherche « case hit serie select » ou « metal universe hobby box » donnait un « joueur » Case Hit et un Metal Universe Hobby.
    « Alexander Ovechkin » -> « alex ovechkin » (meme nom de famille, meme debut de prenom)."""
    import cartes_match
    jn = cartes_match._norm(j).strip()
    if not jn:
        return None
    if _CONNUS["t"] is None:
        _CONNUS["t"] = set(cartes_match._joueurs_connus())
    if jn in _CONNUS["t"]:
        return jn
    m = jn.split()
    f = (cartes_match._noms_famille() or {}).get(m[-1]) if len(m) >= 2 else None
    return f if f and f.split()[0][:3] == m[0][:3] else None


def _precise(joueur, k):
    """La sorte nomme-t-elle UNE carte ? « young guns », « young guns psa 10 », « dazzlers blue », « mvp gold script » : oui.
    « rookie auto » (toutes les autos de recrue du joueur), « gold auto », « psa 10 », « o-pee-chee », « sp authentic auto » (un
    set, sans le nom de la carte) : non, c'est un panier de cartes differentes."""
    if k in _PRECIS:
        return _PRECIS[k]
    t = " " + _RE_NOTE.sub(" ", k) + " "
    t = re.sub(r"/\s*\d+", " ", t)
    sans_set = t
    for nom in sorted(SETS, key=len, reverse=True):
        sans_set = sans_set.replace(" " + nom + " ", "  ")
    reste = [w for w in sans_set.split() if w not in ATTRIBUTS and not re.fullmatch(r"[\d.]+", w)]
    # un nom de carte (« young guns », « dazzlers ») ; ou un set ET une couleur (« mvp gold » : la parallele de sa carte de base)
    r = any(w not in COULEURS for w in reste) or (bool(reste) and sans_set != t)
    if len(_PRECIS) > 50000:
        _PRECIS.clear()
    _PRECIS[k] = r
    return r


_RE_NUMERO = re.compile(r"(\d{9,14})(?!.*\d{9,14})")


def _cartes_exactes(cartes):
    """Les entrees de base_ventes (une par RECHERCHE) -> {(joueur, sorte): ses ventes, une fois chacune, avec la saison lue dans le
    titre}. La meme vente arrive par plusieurs recherches (« jacob fowler young guns », « jacob fowler hockey ») : son numero la
    reconnait."""
    import cartes_match as cartes_m
    gr = {}
    for c in cartes or []:
        j = str(c.get("joueur") or "").strip()
        if not _joueur_ok(j) or (c.get("sport") or "hockey") != "hockey":
            continue
        k = cle_sorte(j, c.get("q") or c.get("carte"))
        jn = _cle_joueur(j)
        if not k or not jn or not _precise(j, k):
            continue
        nom = re.sub(r"(?<=-)[a-z]", lambda m_: m_.group(0).upper(), j.title() if j == j.lower() else j)      # « Brandsegg-Nygard »
        if cartes_m._norm(j).strip() != jn:
            nom = re.sub(r"(?<=-)[a-z]", lambda m_: m_.group(0).upper(), jn.title())                         # « Alex Ovechkin »
        g = gr.setdefault((jn, k), {"joueur": nom, "v": {}, "an_q": None, "detail": False, "lu": None})
        if c.get("annee") and re.search(r"\b(19|20)\d\d\b", str(c.get("q") or c.get("carte") or "")):
            g["an_q"] = int(c["annee"])                  # la recherche nomme sa saison
        if c.get("lu_le") and str(c["lu_le"]) > str(g["lu"] or ""):
            g["lu"] = str(c["lu_le"])
        ventes = c.get("ventes")
        if ventes is None:                               # sans le detail (essais) : pas de numero de vente ni de saison
            ventes = [[le, pr, None, None] for le, pr in c.get("points") or []]
        else:
            g["detail"] = True
        for i, (le, pr, cle, an) in enumerate(ventes):
            m = _RE_NUMERO.search(str(cle)) if cle else None
            key = (m.group(1) if m else str(cle)) if cle else (id(c), i)
            if key not in g["v"]:
                g["v"][key] = (le, pr, an)
    return gr


_RE_AN4 = re.compile(r"(?<!\d)((?:19|20)\d\d)(?!\d)")
_RE_AN2 = re.compile(r"(?<![\d#/])(\d\d)\s?[-/]\s?(\d\d)(?![\d/])")
_RE_LOT = re.compile(r"\s\+\s|\s&\s|\blots?\b|\b\d+\s?x\b|\bx\s?\d+\b|\b(you|u)\s?pick\b|\bpick from\b|\b(complete|team|your|full)\s+set\b|\b\d+\s?cards\b|\bcartes\b")


# Des cartes que cartes_match laisse passer sous la carte d'origine quand la recherche n'a pas d'annee : la « Young Guns Renewed »
# 2024-25 de Kaprizov (3 $) sous sa Young Guns 2020-21, les « tribute », les reimpressions. Si le mot est dans le titre et pas dans
# la recherche, c'est une AUTRE carte : la vente ne compte pas, et une annonce ne recoit pas la tendance.
AUTRES_CARTES = ("renewed", "tribute", "retrospective", "reprint", "reprints", "facsimile", "custom", "aceo", "novelty", "sticker")


def autre_carte(titre, recherche):
    """Le titre dit-il une autre carte que la recherche (une reedition, un lot) ?"""
    t = " " + re.sub(r"[^a-z0-9+&]+", " ", str(titre or "").lower()) + " "
    r = " " + str(recherche or "").lower() + " "
    return any((" " + w + " ") in t and (" " + w + " ") not in r for w in AUTRES_CARTES) or bool(_RE_LOT.search(str(titre or "").lower()))


def vente_detail(titre, recherche):
    """Pour base_ventes (detail) : la saison lue dans le titre d'une vente, ou False si la vente n'est pas la carte cherchee."""
    return False if autre_carte(titre, recherche) else saison_du_titre(titre)


def saison_du_titre(titre):
    """La saison ecrite dans un titre : « 2025-26 », « 2025 », « 2025/2026 » -> 2025 ; « 25/26 », « 25-26 » -> 2025 (cartes_match ne
    lit pas « 25/26 » : l'Elias Pettersson de 2025-26 passait pour celui de 2018-19). Rien d'ecrit : None."""
    t = str(titre or "").lower()
    m = _RE_AN4.search(t)
    if m:
        return int(m.group(1))
    for m in _RE_AN2.finditer(t):
        a, b = int(m.group(1)), int(m.group(2))
        if b == (a + 1) % 100:
            return 2000 + a if a < 50 else 1900 + a
    return None


def _saisons(g):
    """Les cartes exactes d'un groupe (joueur, sorte) : [(saison, ses ventes)]. Une recherche sans annee ramene parfois plusieurs
    saisons (les Dazzlers Blue de Celebrini : 2024-25, 2025-26, 2026-27 ; l'Elias Pettersson de 2018-19 et celui de 2025-26) : la
    saison se lit dans le titre de chaque vente. Une seule saison (SAISON_PART_MIN des ventes datees) : une carte, avec ses ventes
    sans annee ; les rares ventes d'une autre annee sont laissees de cote. Plusieurs saisons : une carte PAR saison, avec ses
    ventes datees seulement. Aucune tolerance « 2026 pour 2025-26 » : deux saisons voisines sont deux cartes."""
    v = list(g["v"].values())
    pt = lambda l: [(le, pr) for le, pr, _an in l]
    if not g["detail"]:
        return [(g["an_q"], pt(v))]
    ans = {}
    for _le, _pr, an in v:
        if an:
            ans[an] = ans.get(an, 0) + 1
    datees = sum(ans.values())
    if g["an_q"]:                                        # la recherche nomme sa saison
        y = g["an_q"]
        seule = datees and ans.get(y, 0) / datees >= SAISON_PART_MIN
        return [(y, pt([x for x in v if x[2] == y or (seule and not x[2])]))]
    if datees < SAISON_DATEES_MIN:
        return []                                        # saison inconnue : on ne peut pas dire que c'est UNE carte
    y = max(ans, key=lambda a: (ans[a], -a))
    if ans[y] / datees >= SAISON_PART_MIN:
        return [(y, pt([x for x in v if not x[2] or x[2] == y]))]
    return [(yy, pt([x for x in v if x[2] == yy])) for yy in sorted(ans) if ans[yy] >= SAISON_DATEES_MIN]


def _mesures(cartes, auj):
    """Une mesure par carte EXACTE (un joueur, une sorte, une saison) qui passe tous les garde-fous -> [(joueur, cle du joueur,
    sorte, mesure)]. Sert a la carte du joueur et a la sorte tous joueurs."""
    out = []
    for (jn, k), g in _cartes_exactes(cartes).items():
        for saison, pts in _saisons(g):
            m = mesure_carte(pts, auj, g["lu"])
            if not m:
                continue
            if "young guns" not in k and m["mediane"] < PRIX_MIN_HORS_YG:
                continue
            # des prix tres etales dans une meme semaine : la recherche melange encore plusieurs cartes
            if m.get("disp") and m["disp"] > DISPERSION_MAX:
                continue
            m["saison"] = saison
            out.append((g["joueur"], jn, k, m))
    return out


def par_sorte(cartes, auj=None, mesures=None):
    """-> {cle: mesure de la sorte, TOUS joueurs} : la moyenne des cartes exactes de cette sorte, chacune comparee a elle-meme."""
    auj = auj or datetime.now()
    gr = {}
    for _j, jn, k, m in (mesures if mesures is not None else _mesures(cartes, auj)):
        g = gr.setdefault(k, {"mes": [], "joueurs": set()})
        g["mes"].append(m)
        g["joueurs"].add(jn)
    out = {}
    for k, g in gr.items():
        mes = g["mes"]
        if len(mes) < CARTES_MIN or sum(m["n_av"] + m["n_re"] for m in mes) < VENTES_MIN:
            continue
        a = _agreger(mes, auj, SEMAINE_MIN)
        confirme, sens = _sens(a)
        out[k] = {"cle": k, "nom": libelle(k), "pct": a["pct"], "p": a["p"], "confirme": confirme, "n": a["n"], "n_re": a["n_re"],
                  "n_cartes": len(mes), "n_joueurs": len(g["joueurs"]), "serie": a["serie"], "n_recents": a["n_recents"],
                  "d_rec": a["d_rec"], "coherent": a["coherent"], "sens": sens}
    return out


def par_carte(cartes, auj=None, mesures=None):
    """LA carte d'un joueur : un joueur + une sorte (« Jacob Fowler · Young Guns »). -> {« joueur|sorte »: mesure}.
    Il faut CARTE_VENTES_MIN ventes et CARTE_PERIODE_MIN dans chaque periode ; tous les garde-fous de _mesures ont passe."""
    auj = auj or datetime.now()
    out = {}
    for j, jn, k, m in (mesures if mesures is not None else _mesures(cartes, auj)):
        if m["n_av"] + m["n_re"] < CARTE_VENTES_MIN or m["n_av"] < CARTE_PERIODE_MIN or m["n_re"] < CARTE_PERIODE_MIN or not m.get("disp"):
            continue
        a = _agreger([m], auj, CARTE_SEMAINE_MIN)
        a["net"] = bool(a["net"] and a["p"] is not None and a["p"] < P_CARTE)
        confirme, sens = _sens(a)
        cle = jn + "|" + k + ("|" + str(m["saison"]) if m.get("saison") else "")
        out[cle] = {"cle": cle, "sorte": k, "joueur": j, "nom": libelle(k), "saison": m.get("saison"), "pct": a["pct"], "brut": a["brut"],
                    "p": a["p"], "confirme": confirme, "n": a["n"], "n_re": a["n_re"], "n_cartes": 1, "serie": a["serie"],
                    "n_recents": a["n_recents"], "d_rec": a["d_rec"], "coherent": a["coherent"], "disp": round(m["disp"], 2), "sens": sens}
    return out


def listes(cartes, auj=None, n=N_LISTE):
    auj = auj or datetime.now()
    mes = _mesures(cartes, auj)
    ps, pc = par_sorte(None, auj, mes), par_carte(None, auj, mes)
    gros = {k: x for k, x in pc.items() if x["n"] >= LISTE_VENTES_MIN}
    tri = lambda d, s, nb: sorted((x for x in d.values() if x["sens"] == s), key=lambda x: ((-x["pct"] if s == "hausse" else x["pct"]), x["p"] or 1))[:nb]
    return {"hausses": tri(ps, "hausse", n), "baisses": tri(ps, "baisse", n), "sortes": ps, "n_sortes": len(ps),
            "cartes": pc, "cartes_hausses": tri(gros, "hausse", N_LISTE_CARTES), "cartes_baisses": tri(gros, "baisse", N_LISTE_CARTES),
            "n_cartes": len(pc), "n_ventes": sum(m["n_av"] + m["n_re"] for _j, _jn, _k, m in mes), "jours": [JOURS_RECENT, JOURS_AVANT]}


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "tendance_sortes.json")


def calculer(maint=None):
    """Refait la mesure sur nos ventes (base_ventes), la garde. Aucun credit, aucun appel. Si trop de ventes de la fenetre ne sont
    pas encore triees (base_ventes en trie 15 000 par passe), RIEN n'est ecrit : {« partiel »: n} et on reessaie plus tard."""
    import base_ventes
    cartes = base_ventes.cartes_toutes(jours=JOURS_LUS, n_min=4, max_q=20000, detail=True)
    reste = int((getattr(base_ventes, "A_TRIER", None) or {}).get("n") or 0)
    lues = sum(len(c.get("points") or ()) for c in cartes)
    if reste > PARTIEL_MAX * max(1, lues + reste):
        return {"partiel": reste, "lues": lues}
    cartes = [c for c in cartes if (c.get("sport") or "hockey") == "hockey"]
    r = listes(cartes, maint)
    r["le"] = (maint or datetime.now()).isoformat(timespec="seconds")
    r["n_cartes_lues"] = len(cartes)
    ch = _chemin()
    try:
        with open(ch + ".tmp", "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False)
        os.replace(ch + ".tmp", ch)
    except OSError as e:
        print("Tendance des sortes : " + repr(e)[:160], flush=True)
    with _verrou:
        _MEM.update(mtime=None, v=None, idx=None)
        _TITRES.clear()
    return r


def lire():
    ch = _chemin()
    try:
        mt = os.path.getmtime(ch)
    except OSError:
        return {}
    with _verrou:
        if _MEM["v"] is not None and _MEM["mtime"] == mt:
            return _MEM["v"]
    try:
        with open(ch, encoding="utf-8") as f:
            v = json.load(f) or {}
    except (OSError, ValueError):
        v = {}
    with _verrou:
        _MEM.update(mtime=mt, v=v, idx=None)
        _TITRES.clear()
    return v


def calculer_si_besoin():
    """Appele par la boucle du serveur : refait aux 3 jours (ou la premiere fois). Tant que le tri des ventes n'est pas fini,
    un essai aux 10 minutes au plus, et rien n'est publie."""
    try:
        age = time.time() - os.path.getmtime(_chemin())
    except OSError:
        age = None
    if age is not None and age < AUX_JOURS * 86400:
        return None
    if time.time() - _ESSAI["le"] < ESSAI_S:
        return None
    _ESSAI["le"] = time.time()
    r = calculer()
    if r.get("partiel"):
        print(f"Tendance des sortes : {r['partiel']} ventes encore a trier ({r['lues']} lues) : on attend la prochaine passe", flush=True)
        return None
    _ESSAI["le"] = 0.0
    print(f"Tendance des sortes : {r['n_cartes']} cartes mesurees ({len(r['cartes_hausses'])} en hausse, {len(r['cartes_baisses'])} en baisse "
          f"dans les listes), {r['n_sortes']} sortes mesurees ({r['n_cartes_lues']} recherches lues, {r['n_ventes']} ventes)", flush=True)
    return r


def _saison_txt(y):
    return f"{int(y)}-{(int(y) + 1) % 100:02d}" if y else None


def public(x):
    """Ce qu'un ecran recoit d'une carte ou d'une sorte : jamais un prix. « net » : le mouvement est confirme par le test (p < 0,10)
    et la courbe va dans le meme sens ; sinon AUCUN pourcentage n'est envoye (un +108 % sur 5 cartes n'est pas un fait).
    « niveau » : « carte » (un joueur + une sorte + sa saison) ou « sorte » (tous joueurs).
    « pct » est l'estimation PRUDENTE (ramenee vers 0 quand il y a peu de ventes) ; « brut » : l'ecart des deux medianes, tel quel.
    « serie » : l'indice par semaine ; « jours » : le jour de chaque point depuis le premier (l'axe du temps du graphique)."""
    import tendance_stats as ts
    net = x.get("p") is not None and x["p"] < (P_CARTE if x.get("joueur") else ts.P_MAX) and x.get("coherent", True)
    se = x.get("serie") or []
    d0 = _jour(se[0][0]) if se else None
    r = {"cle": x["cle"], "nom": x["nom"], "pct": x["pct"] if net else None, "sens": x["sens"], "net": bool(net), "n": x["n"],
         "n_re": x.get("n_re"), "n_cartes": x["n_cartes"], "n_joueurs": x.get("n_joueurs"), "serie": [v for _s, v in se],
         "jours": [(_jour(s_) - d0).days for s_, _v in se] if d0 else [],
         "j_rec": (_jour(x["d_rec"]) - d0).days if d0 and x.get("d_rec") else None,
         "n_recents": x.get("n_recents"), "du": se[0][0] if se else None, "au": se[-1][0] if se else None,
         "niveau": "carte" if x.get("joueur") else "sorte"}
    if x.get("joueur"):
        r["joueur"] = x["joueur"]
        r["saison"] = _saison_txt(x.get("saison"))
        r["brut"] = x.get("brut") if net else None
    return r


def page():
    """Pour la page Tendances : les CARTES (un joueur + une sorte) en hausse et en baisse, et les sortes tous joueurs."""
    r = lire() or {}
    ps, pc = r.get("sortes") or {}, r.get("cartes") or {}
    if not ps and not pc:
        return None
    return {"hausses": [public(x) for x in r.get("cartes_hausses") or []], "baisses": [public(x) for x in r.get("cartes_baisses") or []],
            "toutes": [public(x) for x in sorted(ps.values(), key=lambda x: -x["n"])], "n_sortes": len(ps), "n_cartes": len(pc),
            "n_ventes": r.get("n_ventes"), "le": r.get("le"), "jours": r.get("jours") or [JOURS_RECENT, JOURS_AVANT]}


def _index_cartes(v):
    idx = {}
    for x in (v.get("cartes") or {}).values():
        idx.setdefault(x["cle"].split("|")[0], {}).setdefault(x["sorte"], []).append(x)
    return idx


def _de_saison(cartes, an_t):
    """Parmi les cartes mesurees d'un joueur et d'une sorte, celle de la saison de l'annonce, exactement. Annonce sans annee :
    seulement s'il n'y a qu'une carte. Une annonce d'une autre saison est une autre carte : rien."""
    if not an_t:
        return cartes[0] if len(cartes) == 1 else None
    for x in cartes:
        if not x.get("saison") or x["saison"] == an_t:
            return x
    return None


def de_titre(titre, joueur=None):
    """La tendance d'une annonce (son titre), ou None. D'abord LA carte du joueur (« Jacob Fowler · Young Guns 2025-26 ») ; sinon la
    sorte tous joueurs. Toujours la sorte la plus precise dont tous les mots sont dans le titre ET qui est bien la meme carte pour
    cartes_match (une Young Guns Exclusives n'est jamais jugee sur les Young Guns), de la meme saison."""
    v = lire() or {}
    ps = v.get("sortes") or {}
    if (not ps and not v.get("cartes")) or not titre:
        return None
    k0 = str(titre)[:200] + "|" + str(joueur or "")
    if k0 in _TITRES:
        return _TITRES[k0]
    res = None
    try:
        import cartes_match
        if joueur is None:
            joueur = (cartes_match.cible_titre(titre) or {}).get("joueur")
        if joueur:
            with _verrou:
                if _MEM.get("idx") is None:
                    _MEM["idx"] = _index_cartes(v)
                pj = _MEM["idx"].get(_cle_joueur(joueur) or "") or {}
            if _RE_LOT.search(str(titre).lower()):
                raise LookupError("lot")                 # « Young Guns + Dazzlers », « you pick » : pas UNE carte
            meme0 = lambda k: not autre_carte(titre, k)  # une « Young Guns Renewed » n'est pas la Young Guns
            tn = " " + cartes_match._norm(titre) + " "
            an_t = saison_du_titre(titre)
            dans = lambda k: all((" " + w + " ") in tn for w in k.split())
            ordre = lambda src: sorted((k for k in src if dans(k)), key=lambda k: (-len(k.split()), -len(k)))[:6]
            meme = lambda k: not cartes_match.raisons_refus(cartes_match.cible(f"{joueur} {k}"), titre)
            for k in ordre(pj):
                x = _de_saison(pj[k], an_t)
                if x and meme0(k) and meme(k):
                    res = public(x)
                    break
            if not res:
                for k in ordre(ps):
                    if meme0(k) and meme(k):
                        res = public(ps[k])
                        break
    except LookupError:
        res = None
    except Exception as e:
        print("Tendance des sortes (titre) : " + repr(e)[:120], flush=True)
    if len(_TITRES) > 20000:
        _TITRES.clear()
    _TITRES[k0] = res
    return res
