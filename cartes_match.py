"""
LOCKERROOM - « est-ce la MEME carte ? » (24 oct 2026).

Mathieu : « la section research value ne sort pas les bonnes annonces. elle doit auto learn ou
utiliser un meilleur modele. j'ai ecrit will smith young guns et ca me sort tout sauf ca.
attention aux paralleles, gradation, auto patch, serial, refractor etc. »

  1. decoder(texte) : annee, numero, numerotation /99, gradation (PSA 10...), auto, patch/relique,
     paralleles (Exclusives, Silver, Refractor...), recrue, lot / reproduction.
  2. correspond(carte_cherchee, titre) : une annonce ne compte que si elle a TOUT ce qui est demande
     et RIEN de plus qui change le prix (une Young Guns de base n'est pas une Exclusives /100,
     une PSA 10, une auto ou un lot).
  3. apprentissage partage : « pas la bonne carte » sur une annonce -> elle est ecartee pour cette
     recherche, et un mot qui revient souvent dans les annonces refusees devient un mot d'exclusion
     pour tout le monde (sauf si on le cherche).
Aucun appel reseau ici : tout est local et rapide.
"""
import json
import os
import re
import statistics
import threading
import unicodedata

_verrou = threading.Lock()

# -- mots ---------------------------------------------------------------------------------------
SYNONYMES = [                       # forme courte -> forme longue (dans la recherche ET les titres)
    (r"\byg\b", "young guns"), (r"\bud\b", "upper deck"), (r"\bopc\b", "o-pee-chee"), (r"\bo pee chee\b", "o-pee-chee"),
    (r"\bspa\b", "sp authentic"), (r"\bfw\b", "future watch"), (r"\brr\b", "rated rookie"),
    (r"\bautograph(ed|s)?\b", "auto"), (r"\bsigned\b", "auto"), (r"\bsignature(s)?\b", "auto"), (r"\bautos\b", "auto"),
    (r"\brookie\b", "rc"), (r"\brookies\b", "rc"), (r"\bjsy\b", "jersey"), (r"\bmem\b", "relic"),
    (r"\bx-?fractor\b", "xfractor"), (r"\brefractors\b", "refractor"), (r"\bpatches\b", "patch"),
    (r"\bfirst\b", "1st"), (r"\bseries one\b", "series 1"), (r"\bseries two\b", "series 2"),
]
_SYN_RE = [(re.compile(a), b) for a, b in SYNONYMES]

# variantes qui changent le prix : une carte de base ne les a pas
PARALLELES = [
    "exclusives", "high gloss", "clear cut", "canvas", "outburst", "silver", "gold", "red", "blue", "green", "orange",
    "purple", "pink", "black", "platinum", "rainbow", "holo", "foil", "sparkle", "shimmer", "wave", "mojo",
    "cracked ice", "refractor", "xfractor", "superfractor", "atomic", "sepia", "retro", "deluxe", "spectrum", "violet",
    "aqua", "neon", "sapphire", "speckle", "lava", "tie dye", "camo", "disco", "hyper", "scope", "pulsar", "fast break",
    "choice", "flash", "velocity", "laser", "power", "prizm silver", "silver prizm", "printing plate", "blank back",
    "variation", "photo variation", "ssp", "short print", "die cut", "color", "dazzle", "glossy", "chrome",
    "french", "emerald", "ruby", "bronze", "copper", "mini", "acetate", "achievements", "rookie redemption",
    "artist proof", "premier", "jumbo", "fluorescent", "galactic", "nebula", "ice",
]
# mots qui ressemblent a une variante mais sont le NOM d'un produit (le chercher les exige quand meme)
PRODUITS = ["prizm", "optic", "mosaic", "select", "chrome", "ice", "platinum", "black diamond", "retro", "sapphire",
            "premier", "artifacts", "heritage", "finest", "stadium club", "contenders", "national treasures", "immaculate"]
EXCLUS = [r"\blots?\b", r"\bx\s?[2-9]\b", r"\(\s*[2-9]\s*\)", r"\b[2-9]\s*cards?\b", r"you pick", r"pick your", r"\bchoose\b",
          r"\breprint\b", r"\brp\b", r"\bcustom\b", r"\bdigital\b", r"\bproxy\b", r"\bfacsimile\b", r"\bnovelty\b",
          r"\bart card\b", r"\b(case|box|team|player|random|pack) break\b", r"\bbreak (spot|slot)\b", r"\bhobby box\b",
          r"\bblaster\b", r"\bpacks\b", r"\bunopened\b", r"\bsealed\b", r"\bteam set\b", r"\bset of\b", r"\bmystery\b",
          r"\bcomplete set\b", r"\brandom (team|player)\b"]
# noms d'equipes qui contiennent une couleur (« Red Wings » n'est pas une variante Red)
EQUIPES_COULEUR = ["red wings", "blue jackets", "blue jays", "red sox", "white sox", "green bay", "red devils", "golden knights",
                   "black hawks", "silver knights", "orange crush"]
PRODUITS_LONGS = ["black diamond", "stadium club", "national treasures", "young guns", "future watch", "sp authentic",
                  "rated rc", "color blast", "power play", "gold label", "red line"]
_EXCLUS_RE = [re.compile(x) for x in EXCLUS]
_RE_ANNEE = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\s*(?:[-/]\s*(\d{2,4}))?\b|\b(\d{2})\s*-\s*(\d{2})\b")
_RE_GRADE = re.compile(r"\b(psa|bgs|sgc|cgc|tag|ksa|hga|beckett|bccg)\s*-?\s*(gem\s*(?:mint|mt)?\s*|mint\s*|pristine\s*|black label\s*)?(10|9\.5|9|8\.5|8|7\.5|7|6|5|4|3|2|1)?\b")
_RE_SERIE = re.compile(r"(?:#\s*)?(?:\b\d{1,4}\s*)?/\s*0*(\d{1,4})\b|\b(\d{1,4})\s+of\s+(\d{1,4})\b|\b1\s*/\s*1\b|\bone of one\b")
_RE_NUM = re.compile(r"(?:#|\bno\.?\s*|\bcard\s*)\s*([a-z]{0,4}-?\d{1,4}[a-z]?)\b")
_RE_AUTO = re.compile(r"\bauto\b|\bon card\b|\bsticker auto\b")
_RE_PATCH = re.compile(r"\bpatch\b|\bjersey\b|\brelic\b|\bgame (used|worn)\b|\bswatch\b|\brpa\b|\bmemorabilia\b|\bgu\b|\bfabric\b|\bmaterials?\b|\bstick\b")
_RE_RC = re.compile(r"\brc\b|\byoung guns\b|\brated rc\b|\b1st bowman\b|\bbowman 1st\b|\bfuture watch\b|\bcanvas rc\b")
VIDES = set("the a an of and with for in on card cards hockey nhl nba nfl mlb football basketball baseball new mint nm nmmt "
            "near ex excellent sharp clean look hot invest investment beautiful rare ssp sp lot free shipping ship ships "
            "canada usa us read description see photos pic pics pictures box".split())


def norm(t):
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
    t = t.replace("&", " and ").replace("’", "'")
    t = re.sub(r"[^a-z0-9#/.\- ]+", " ", t)
    t = re.sub(r"(?<![a-z0-9])\.|\.(?![0-9])", " ", t)      # points isoles (garde 9.5)
    for rx, rempl in _SYN_RE:
        t = rx.sub(rempl, t)
    return re.sub(r"\s+", " ", t).strip()


def _a_mot(t, mot):
    return re.search(r"(?<![a-z0-9])" + re.escape(mot) + r"(?![a-z0-9])", t) is not None


def _annee(t):
    m = _RE_ANNEE.search(t)
    if not m:
        return None
    if m.group(1):
        a = int(m.group(1))
        return a
    a = int(m.group(3))
    return 2000 + a if a < 50 else 1900 + a


def decoder(texte):
    """Ce que dit un titre (ou une recherche) sur la carte."""
    t = norm(texte)
    g = _RE_GRADE.search(t)
    grade = None
    if g:
        if g.group(3) or g.group(1) in ("psa", "bgs", "sgc", "beckett", "cgc"):
            grade = {"cie": "bgs" if g.group(1) == "beckett" else g.group(1), "note": g.group(3)}
    serie = None
    for m in _RE_SERIE.finditer(t):
        txt = m.group(0)
        if re.match(r"\s*#?\s*(19|20)\d{2}\s*/", txt):         # « 2024/25 » : une saison, pas /25
            continue
        if re.search(r"1\s*/\s*1\b|one of one", txt):
            serie = 1
            break
        n = m.group(1) or m.group(3)
        if n and int(n) > 0:
            serie = int(n)
            break
    t_sans_grade = _RE_GRADE.sub(" ", t)
    t_sans_serie = _RE_SERIE.sub(" ", t_sans_grade)
    num = None
    m = _RE_NUM.search(t_sans_serie)
    if m:
        num = m.group(1).lstrip("0") or "0"
    t_par = t
    for x in EQUIPES_COULEUR + PRODUITS_LONGS:
        t_par = t_par.replace(x, " ")
    par = set()
    for p in PARALLELES:
        if _a_mot(t_par, p):
            par.add(p)
    if "prizm silver" in par or "silver prizm" in par:
        par -= {"prizm silver", "silver prizm"}
        par.add("silver")
    exclu = any(rx.search(t) for rx in _EXCLUS_RE)
    return {"texte": t, "annee": _annee(t), "num": num, "serie": serie, "grade": grade,
            "auto": bool(_RE_AUTO.search(t)), "patch": bool(_RE_PATCH.search(t)), "rc": bool(_RE_RC.search(t)),
            "paralleles": par, "exclu": exclu}


def _mots_requis(d):
    """Les mots de la recherche qui doivent etre dans le titre (joueur, produit, insert)."""
    t = d["texte"]
    t = _RE_GRADE.sub(" ", t)
    t = _RE_SERIE.sub(" ", t)
    t = _RE_NUM.sub(" ", t)
    t = _RE_ANNEE.sub(" ", t)
    for p in d["paralleles"]:
        if p not in PRODUITS:
            t = re.sub(r"(?<![a-z0-9])" + re.escape(p) + r"(?![a-z0-9])", " ", t)
    t = re.sub(r"\b(auto|patch|jersey|relic|rc|raw|ungraded|graded|numbered|serial|base|card|parallel)\b", " ", t)
    mots = [m for m in t.split() if m not in VIDES and len(m) > 1]
    return mots


def _produits_dans(t):
    return {p for p in PRODUITS if _a_mot(t, p)}


def cible(recherche):
    """Une recherche -> ce qu'on exige (et ce qu'on refuse) dans les annonces."""
    d = decoder(recherche)
    t = d["texte"]
    d["mots"] = _mots_requis(d)
    d["veut_grade"] = bool(d["grade"]) or bool(re.search(r"\bgraded\b|\bslab\b", t))
    d["brute"] = bool(re.search(r"\braw\b|\bungraded\b", t))
    d["veut_serie"] = d["serie"] is not None or bool(re.search(r"\bnumbered\b|\bserial\b|#\s*d\b", t))
    d["base"] = bool(re.search(r"\bbase\b", t))
    d["produits"] = _produits_dans(t)
    return d


def raisons_refus(c, titre, appris=None):
    """[] si l'annonce est la meme carte, sinon pourquoi pas (en mots simples)."""
    a = decoder(titre)
    t = a["texte"]
    r = []
    if a["exclu"] and not c["exclu"]:
        r.append("lot / pas une carte seule")
    manque = [m for m in c["mots"] if not _a_mot(t, m)]
    if manque:
        r.append("autre carte (" + " ".join(manque[:3]) + " absent)")
    # 24 oct 2026 - « Will Smith / Lekkerimaki checklist » n'est pas la Young Guns de Will Smith
    if _a_mot(t, "checklist") and not _a_mot(c["texte"], "checklist"):
        r.append("checklist")
    if c["mots"]:
        autres = [n for n in _noms_dans(t) if n.split()[-1] not in c["mots"]]      # meme nom de famille = meme joueur
        if autres:
            r.append("autre joueur (" + autres[0] + ")")
    if c["annee"] and a["annee"] and a["annee"] != c["annee"]:
        r.append("autre année")
    if c["num"] and a["num"] and a["num"] != c["num"]:
        r.append("autre numéro")
    # gradation
    if c["grade"]:
        if not a["grade"] or a["grade"]["cie"] != c["grade"]["cie"] or (c["grade"]["note"] and a["grade"]["note"] != c["grade"]["note"]):
            r.append("autre gradation")
    elif c["veut_grade"]:
        if not a["grade"]:
            r.append("pas gradée")
    elif a["grade"]:
        r.append("gradée")
    # auto, patch
    if c["auto"] != a["auto"]:
        r.append("autographe" if a["auto"] else "sans autographe")
    if c["patch"] != a["patch"]:
        r.append("patch / relique" if a["patch"] else "sans patch")
    # numerotation
    if c["serie"] is not None:
        if a["serie"] != c["serie"]:
            r.append("autre numérotation")
    elif c["veut_serie"]:
        if a["serie"] is None:
            r.append("pas numérotée")
    elif a["serie"] is not None:
        r.append("numérotée /" + str(a["serie"]))
    # paralleles : ceux demandes doivent y etre ; aucun autre (les noms de produits demandes ne comptent pas)
    voulus = set(c["paralleles"])
    en_trop = {p for p in a["paralleles"] - voulus if p not in c["produits"]}
    absents = {p for p in voulus if p not in a["paralleles"] and p not in c["produits"]}
    if absents:
        r.append("pas la variante " + ", ".join(sorted(absents)))
    if en_trop:
        r.append("variante " + ", ".join(sorted(en_trop)[:2]))
    # appris : des mots que les utilisateurs ont refuses souvent
    if appris:
        mauvais = [m for m in appris if _a_mot(t, m) and not _a_mot(c["texte"], m)]
        if mauvais:
            r.append("écartée (" + mauvais[0] + ")")
    return r


def resume(c):
    """Ce que l'app a compris de la recherche, en pastilles."""
    p = []
    if c["mots"]:
        p.append(" ".join(m if m[:1].isdigit() else m.capitalize() for m in c["mots"]))
    if c["annee"]:
        p.append(str(c["annee"]))
    if c["num"]:
        p.append("#" + c["num"])
    p += sorted(x.title() for x in c["paralleles"] - c["produits"]) or (["Base"] if not (c["auto"] or c["patch"]) else [])
    if c["serie"]:
        p.append("/" + str(c["serie"]))
    if c["auto"]:
        p.append("Auto")
    if c["patch"]:
        p.append("Patch")
    if c["grade"]:
        p.append((c["grade"]["cie"].upper() + " " + (c["grade"]["note"] or "")).strip())
    else:
        p.append("Gradée" if c["veut_grade"] else "Non gradée")
    return p


def requete_ebay(c):
    """La recherche envoyee a eBay : les mots qui comptent, sans le bruit. Annee, numero et /99 restent
    hors de la recherche (eBay exige TOUS les mots ; trop de vendeurs les ecrivent autrement) : le tri les verifie."""
    m = list(c["mots"])
    m += sorted(p for p in c["paralleles"] if p not in m)
    if c["auto"]:
        m.append("auto")
    if c["patch"]:
        m.append("patch")
    if c["grade"]:
        m.append((c["grade"]["cie"] + " " + (c["grade"]["note"] or "")).strip())
    return " ".join(m)[:100]


def mediane_robuste(prix):
    """Mediane sans les prix aberrants (moins du tiers ou plus du triple de la mediane)."""
    p = sorted(x for x in prix if x and x > 0)
    if not p:
        return None, []
    m = statistics.median(p)
    garde = [x for x in p if m / 3 <= x <= m * 3]
    return (round(statistics.median(garde), 2) if garde else round(m, 2)), garde


# -- apprentissage partage -----------------------------------------------------------------------
def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "apprentissage_comps.json")


def _lire():
    try:
        with open(_chemin(), encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        d = {}
    d.setdefault("refus", {})
    d.setdefault("bons", {})
    d.setdefault("items", {})
    d.setdefault("oui", {})
    return d


_JOUEURS = {"t": None}


def _mots_joueurs():
    """Les mots des noms de joueurs connus : jamais appris comme mots d'exclusion."""
    if _JOUEURS["t"] is None:
        try:
            import valeurs
            d = valeurs._charger() or {}
            _JOUEURS["t"] = {m for j in (d.get("joueurs") or {}) for m in norm(j).split()}
        except Exception:
            _JOUEURS["t"] = set()
    return _JOUEURS["t"]


def signature(recherche):
    c = cible(recherche)
    return requete_ebay(c)


def apprendre(recherche, item_id, titre, bonne):
    """L'utilisateur dit : cette annonce est (ou n'est pas) la carte cherchee."""
    sig = signature(recherche)
    mots_q = set(norm(recherche).split())
    mots_t = {m for m in norm(titre).split() if len(m) > 2 and m not in VIDES and not m.isdigit() and m not in mots_q}
    with _verrou:
        d = _lire()
        lst = d["items"].setdefault(sig, [])
        if not bonne and str(item_id) not in lst:
            lst.append(str(item_id))
            d["items"][sig] = lst[-200:]
        elif bonne:
            if str(item_id) in lst:
                lst.remove(str(item_id))
            oui = d["oui"].setdefault(sig, [])
            if str(item_id) not in oui:
                oui.append(str(item_id))
                d["oui"][sig] = oui[-200:]
        cpt = d["refus"] if not bonne else d["bons"]
        for m in mots_t:
            cpt[m] = cpt.get(m, 0) + 1
        tmp = _chemin() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(tmp, _chemin())
    return {"ok": True}


def appris(recherche=None):
    """(mots d'exclusion appris, annonces refusees pour cette recherche)."""
    d = _lire()
    joueurs = _mots_joueurs()
    mots = [m for m, n in d["refus"].items() if n >= 5 and n >= 3 * d["bons"].get(m, 0) and m not in joueurs]
    refuses = set(d["items"].get(signature(recherche), [])) if recherche else set()
    oui = set(d["oui"].get(signature(recherche), [])) if recherche else set()
    return mots, refuses, oui


def filtrer(recherche, annonces, titre_de=lambda a: a.get("titre"), id_de=lambda a: a.get("item_id")):
    """(gardees, ecartees avec raison). Utilise partout : valeur, sante de l'inventaire, prix suggere."""
    c = cible(recherche)
    mots, refuses, oui = appris(recherche)
    gardees, ecartees = [], []
    for a in annonces:
        if str(id_de(a)) in oui:
            gardees.append(a)
            continue
        if str(id_de(a)) in refuses:
            ecartees.append({**a, "raison": "écartée par toi"})
            continue
        r = raisons_refus(c, titre_de(a) or "", mots)
        if r:
            ecartees.append({**a, "raison": r[0]})
        else:
            gardees.append(a)
    return c, gardees, ecartees


# -- a partir du titre d'une de NOS cartes (inventaire, annonce a creer) ---------------------------
SETS_CLES = ["young guns", "future watch", "sp authentic", "the cup", "ultimate collection", "ultimate rookies", "black diamond",
             "artifacts", "mvp", "synergy", "credentials", "trilogy", "chronology", "premier", "allure", "spx", "sp game used",
             "o-pee-chee platinum", "o-pee-chee", "ice", "extended", "series 1", "series 2", "prizm", "optic", "select", "mosaic",
             "chrome", "bowman", "topps", "donruss", "rated rc", "contenders", "national treasures", "immaculate", "finest",
             "heritage", "stadium club", "update", "fleer", "score", "leaf", "panini", "upper deck", "flawless", "spectra",
             "obsidian", "certified", "absolute", "phoenix", "revolution", "hoops", "dynasty", "noir", "luminance", "clear cut",
             "canvas", "exclusives", "high gloss", "outburst", "rookie redemption"]
GENERIQUES = set("""upper deck ud panini topps bowman donruss leaf fleer score o-pee-chee opc series extended young guns future
watch sp authentic cup ultimate collection rookies rookie rc black diamond artifacts mvp synergy credentials trilogy chronology
premier allure spx game used ice prizm optic select mosaic chrome rated contenders national treasures immaculate finest heritage
stadium club update hoops flawless spectra obsidian certified absolute phoenix revolution dynasty noir luminance card cards
auto patch jersey relic numbered parallel base insert sticker hockey nhl nba nfl mlb football basketball baseball sharks rangers
lot short print sp ssp variation retro french canvas exclusives gloss clear cut outburst redemption sealed graded raw psa bgs
sgc cgc gem mint near rookies 1st edition set team prospects prospect draft picks pick stars star legends legend
future signatures materials premium rookie debut""".split())
_JOUEURS_CONNUS = {"t": None}


def _joueurs_connus():
    """Noms complets connus (valeur des joueurs + checklists du catalogue), normalises, les plus longs d'abord."""
    if _JOUEURS_CONNUS["t"] is None:
        noms = set()
        try:
            import valeurs
            noms |= {norm(j) for j in ((valeurs._charger() or {}).get("joueurs") or {})}
        except Exception:
            pass
        try:
            import catalogue
            for p in catalogue.liste():
                try:
                    for c in catalogue.charger(p["id"]).get("cartes") or []:
                        for j in re.split(r"\s*/\s*", str(c.get("joueur") or "")):
                            if j.strip():
                                noms.add(norm(j))
                except Exception:
                    continue
        except Exception:
            pass
        _JOUEURS_CONNUS["t"] = sorted((n for n in noms if len(n.split()) >= 2), key=len, reverse=True)
    return _JOUEURS_CONNUS["t"]


def _mots_equipes():
    try:
        import sports
        out = set()
        for d in sports.SPORTS.values():
            for v in d["equipes"].values():
                nom = v[0] if isinstance(v, (list, tuple)) else str(v)
                out |= set(norm(nom).split())
        return out
    except Exception:
        return set()


_EQUIPES_MOTS = {"t": None}


_RE_NOMS = {"rx": None}


def _noms_dans(t):
    """Les joueurs connus nommes dans un titre (une seule expression pour tous : rapide)."""
    if _RE_NOMS["rx"] is None:
        noms = _joueurs_connus()
        _RE_NOMS["rx"] = re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(n) for n in noms) + r")(?![a-z0-9])") if noms else False
    return _RE_NOMS["rx"].findall(t) if _RE_NOMS["rx"] else []


def joueur_du_titre(titre, joueur=None):
    """Le joueur d'un titre : la fiche s'il est connu, sinon un nom connu, sinon les mots qui ne sont ni produit, ni equipe."""
    if joueur:
        return norm(joueur)
    t = norm(titre)
    for n in _joueurs_connus():
        if _a_mot(t, n):
            return n
    if _EQUIPES_MOTS["t"] is None:
        _EQUIPES_MOTS["t"] = _mots_equipes()
    gen = GENERIQUES | VIDES | _EQUIPES_MOTS["t"] | set(PARALLELES)
    reste, out = re.sub(r"#\s*\S+|/\s*\d+|\b\d[\d\-./]*\b", " ", t).split(), []
    for m in reste:
        if m in gen or len(m) < 2 or not m.isalpha():
            if out:
                break
            continue
        out.append(m)
        if len(out) >= 3:
            break
    return " ".join(out)


def cible_titre(titre, joueur=None):
    """Notre carte (son titre) -> ce que les comparables doivent avoir."""
    c = cible(titre)
    t = c["texte"]
    j = joueur_du_titre(titre, joueur)
    sets = []
    for s_ in SETS_CLES:
        if _a_mot(t, s_) and not any(s_ in x for x in sets) and s_ not in ("upper deck", "panini", "topps", "series 1", "series 2", "extended"):
            sets.append(s_)
        if len(sets) >= 2:
            break
    c["mots"] = [m for m in (j.split() + " ".join(sets).split()) if m not in VIDES]
    c["joueur"] = j
    return c


def filtrer_carte(titre, annonces, joueur=None, exclure_id=None):
    """Comparables d'une de nos cartes : (cible, gardees, ecartees)."""
    c = cible_titre(titre, joueur)
    mots, _refuses, _oui = appris(None)
    gardees, ecartees = [], []
    for a in annonces:
        if exclure_id and str(a.get("item_id")) == str(exclure_id):
            continue
        r = raisons_refus(c, a.get("titre") or "", mots)
        (ecartees if r else gardees).append({**a, "raison": r[0]} if r else a)
    return c, gardees, ecartees


_RE_CARTE = re.compile(r"\b(19[5-9]\d|20[0-4]\d)(-\d{2})?\b.*\b(card|rc|rookie|#\s*\w+|psa|bgs|sgc|auto|patch|refractor|parallel|insert|/\d+)\b"
                       r"|\b(young guns|future watch|sp authentic|upper deck|panini|topps|bowman|donruss|o-pee-chee|prizm|optic|trading card)\b")


def est_carte(titre):
    """Une carte de sport ? (sinon : comparaison large, comme avant - LEGO, consoles, etc.)"""
    t = norm(titre)
    return bool(_RE_CARTE.search(t)) or any(_a_mot(t, n) for n in _joueurs_connus()[:2000])
