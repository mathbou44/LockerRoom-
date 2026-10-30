"""
LOCKERROOM - importer une checklist Excel (Beckett) dans le catalogue (24 oct 2026).

Mathieu : « Les checklists sont maintenant sur le site de Beckett pour les sortes de cartes ... sur la premiere
page de Beckett, il va avoir le lien pour telecharger l'Excel. C'est comme ca pour toutes les sortes de cartes. »

Le fichier (.xlsx ou .csv) est telecharge par l'utilisateur sur beckett.com puis depose dans l'app.
On lit : sous-ensemble (set / insert), numero, joueur, equipe, numerotation (/99), recrue (RC).
Deux mises en page sont reconnues :
  1. une ligne d'en-tete (Set | Card # | Player | Team | Print Run...) ;
  2. des titres de sous-ensemble sur une ligne seule, suivis de lignes « numero  joueur  equipe ».
Les cotes par boite (« Young Guns : 6 par boite ») ne sont pas dans l'Excel : on garde celles du produit
s'il existe deja, sinon elles restent a completer (jamais inventees).
"""
import csv
import io
import re
import unicodedata

ENTETES = {
    "set": ("set", "subset", "insert", "card set", "set name", "subset name", "category", "type", "program"),
    "numero": ("card #", "card number", "card no", "card", "#", "no", "no.", "number", "num", "card num"),
    "joueur": ("player", "name", "player name", "athlete", "subject", "description"),
    "equipe": ("team", "team name", "club"),
    "tirage": ("print run", "serial", "serial #", "numbered", "seq", "seq.", "/#", "#'d", "run", "serial #'d", "serial #d",
               "serial numbered", "serial number", "#d"),
    "notes": ("notes", "note", "info", "attributes"),
    # 25 oct 2026 - format GTS Distribution (gogts.net) : Set Name | Card | Description | Team City | Team Name | Rookie |
    # Auto | Tech | Serial #'d | SPs | Stated Odds | Point
    "ville": ("team city", "city"),
    "recrue": ("rookie", "rc", "rookie card", "rc?"),
    "auto": ("auto", "autograph", "autographed", "signed"),
    "tech": ("tech", "technology", "finish"),
    "sp": ("sps", "sp", "short print", "sp/ssp"),
    "cotes": ("stated odds", "odds", "insertion odds", "pack odds"),
}


def _n(t):
    t = unicodedata.normalize("NFKD", str(t if t is not None else "")).encode("ascii", "ignore").decode().lower().strip()
    return re.sub(r"\s+", " ", t)


def _rangs_xlsx(brut):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(brut), read_only=True, data_only=True)
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            yield ws.title, ["" if v is None else str(v).strip() for v in row]


def _rangs_csv(brut):
    texte = brut.decode("utf-8-sig", "ignore")
    dial = csv.Sniffer().sniff(texte[:4000], delimiters=",;\t") if texte.strip() else csv.excel
    for row in csv.reader(io.StringIO(texte), dial):
        yield "", [c.strip() for c in row]


def _colonnes(cells):
    """Index des colonnes d'une ligne d'en-tete, ou None."""
    idx = {}
    for i, c in enumerate(cells):
        k = _n(c)
        for champ, mots in ENTETES.items():
            if champ not in idx and k in mots:
                idx[champ] = i
    return idx if "joueur" in idx and ("numero" in idx or "set" in idx) else None


_RE_TIRAGE = re.compile(r"(?:^|[\s#/])/?\s*(\d{1,4})\s*$|/\s*(\d{1,4})\b|\b1\s*/\s*1\b")


def tirage_de(*textes):
    for t in textes:
        t = str(t or "")
        if re.search(r"\b1\s*/\s*1\b|one of one", t, re.I):
            return 1
        m = re.search(r"/\s*(\d{1,4})\b", t)
        if m and int(m.group(1)) > 0:
            return int(m.group(1))
    return None


def _tirage_colonne(v):
    v = str(v or "").strip()
    if re.fullmatch(r"\d{1,4}(\.0)?", v) and float(v) > 0:
        return int(float(v))
    return tirage_de(v)


def groupe_de(nom):
    t = _n(nom)
    # 27 oct 2026 (revue) : « ink » et « stick » en mots entiers (« Pink », « Rink », « Stickers » ne sont ni auto ni memo)
    auto = bool(re.search(r"auto|signature|signed|\bink(ed)?\b|chirography|inscri", t))
    memo = bool(re.search(r"patch|jersey|material|relic|memorabilia|swatch|game[- ]used|game[- ]worn|fabric|\bsticks?\b|threads", t))
    if auto and memo:
        return "auto_memo"
    if auto:
        return "auto"
    if memo:
        return "memo"
    if re.search(r"young guns|rookie|future watch|\brc\b|rated rookie|1st bowman|freshman|debut", t):
        return "recrue"
    if re.search(r"\bbase\b|base set|^base$", t):
        return "base"
    return "insert"


def _est_numero(c):
    c = str(c).strip()
    return bool(re.fullmatch(r"[A-Za-z]{0,6}-?\d{1,4}[A-Za-z]?", c) or re.fullmatch(r"[A-Za-z]{1,6}-[A-Za-z]{1,6}\d{0,3}", c))


def lire(brut, nom_fichier="checklist.xlsx", sport=None):
    """-> {"sous_ensembles": [...], "cartes": [...], "lignes": n} (format catalogue/SCHEMA.md)."""
    import sports
    rangs = _rangs_xlsx(brut) if str(nom_fichier).lower().endswith((".xlsx", ".xlsm")) else _rangs_csv(brut)
    # 31 oct 2026 (Premier 2025-26 : 7 onglets, dont « Master Card List » en tableau et 5 resumes en texte libre) : quand un
    # onglet a une vraie ligne d'en-tete (Set Name, Card, Description...), SEULS les onglets en tableau sont lus. Avant, les
    # resumes etaient lus aussi : chaque carte 2 ou 3 fois, et des « sous-ensembles » comme « 57 cards » ou « Platinum 1/1 »
    rangs = list(rangs)
    tableau = any(_colonnes(cells) for _f, cells in rangs)
    cartes, idx, titre = [], None, None
    feuille_prec = None
    titre_doc = None                    # 30 oct 2026 : « 2025-26 Upper Deck Series 2 Hockey Checklist » en haut du fichier
    for feuille, cells in rangs:
        if titre_doc is None:
            for x in [feuille] + [c for c in cells if c][:2]:
                if x and re.search(r"(19|20)\d{2}", str(x)) and re.search(r"[a-z]{4,}", str(x), re.I) and len(str(x)) < 120 \
                        and not _est_numero(str(x)):
                    titre_doc = str(x).strip()
                    break
        if feuille != feuille_prec:
            feuille_prec, idx = feuille, None
            titre = feuille if feuille and not re.fullmatch(r"sheet\s*\d*|feuil\w*\s*\d*|checklist", _n(feuille)) else None
        pleines = [c for c in cells if c]
        if not pleines:
            continue
        col = _colonnes(cells)
        if col:
            idx = col
            continue
        if idx:
            g = lambda k: cells[idx[k]] if k in idx and idx[k] < len(cells) else ""
            joueur, num = g("joueur"), g("numero")
            se = g("set") or titre or "Base"
            if not joueur:
                continue
            notes = " ".join([g("notes")] + [c for i, c in enumerate(cells) if i not in idx.values()])
        else:
            if tableau:                     # un onglet sans en-tete dans un fichier en tableau : resume, pas des cartes
                continue
            # mise en page 2 : titre de sous-ensemble seul sur sa ligne, puis « numero joueur equipe »
            if len(pleines) == 1 and not _est_numero(pleines[0]):
                if not est_bruit(pleines[0]):
                    titre = pleines[0]
                continue
            if not _est_numero(pleines[0]) or len(pleines) < 2:
                continue
            num, joueur = pleines[0], pleines[1]
            reste = pleines[2:]
            se = titre or "Base"
            notes = " ".join(reste)
            g = lambda k: (reste[0] if reste else "") if k == "equipe" else ""
        equipe_txt = re.sub(r"#?\s*/\s*\d+|\bRC\b|\brookie\b", " ", str(g("equipe") or ""), flags=re.I).strip()
        villes = [v.strip() for v in re.split(r"\s*/\s*", str(g("ville") or "")) if v.strip()]
        noms_eq = [e for e in re.split(r"\s*/\s*|\s*,\s*", str(equipe_txt)) if e.strip()]
        if villes and len(villes) == len(noms_eq):              # GTS : « New York » + « Rangers »
            noms_eq = [f"{v} {e}" for v, e in zip(villes, noms_eq)]
        codes = [sports.code_equipe(e, sport) for e in noms_eq]
        rc = bool(re.search(r"\bRC\b|rookie", notes + " " + joueur + " " + str(g("equipe") or ""), re.I)) or bool(str(g("recrue") or "").strip())
        tech, sp, cote_txt = str(g("tech") or "").strip(), str(g("sp") or "").strip().upper(), str(g("cotes") or "").strip()
        joueur = re.sub(r"\s*\bRC\b\s*", " ", joueur).strip(" ,")
        # 31 oct 2026 : une inscription (Celebrini « I Like Fishing », Leonard « Hi Mom ») : le meme joueur (sa valeur, son
        # equipe), la carte marquee « inscription » (plus rare)
        insc = re.search(r"\s*[\"“”«]([^\"“”»]{1,40})[\"“”»]\s*", joueur)
        if insc:
            joueur = (joueur[:insc.start()] + " " + joueur[insc.end():]).strip(" ,")
        se = re.sub(r"\s+", " ", str(se)).strip()
        tir = 1 if re.search(r"\bplate", tech + " " + se, re.I) else (_tirage_colonne(g("tirage") if idx else "") or tirage_de(notes, se))
        carte = {"numero": str(num).strip(), "joueur": joueur, "equipe": "/".join(c for c in codes if c) or str(equipe_txt).strip(),
                 "sous_ensemble": se, "recrue": rc or groupe_de(se) == "recrue",
                 "auto": groupe_de(se) in ("auto", "auto_memo") or bool(str(g("auto") or "").strip()),
                 "memo": groupe_de(se) in ("memo", "auto_memo"), "tirage": tir}
        if sp in ("SP", "SSP"):
            carte["sp"] = sp
        if insc:
            carte["inscription"] = insc.group(1).strip()
            carte.setdefault("sp", "SSP")              # une inscription sort beaucoup moins que la signature seule
        if cote_txt:
            carte["_cotes"] = cote_txt
        cartes.append(carte)
    # 31 oct 2026 (Mathieu : « pourquoi ca bug a chaque fois ? il va falloir que je passe par toi ? ») : nettoyage automatique
    # des lignes qui ne sont pas des cartes (resumes « 57 cards », « Gold /15 », cotes) et des doublons exacts
    n0 = len(cartes)
    cartes = [c for c in cartes if not est_bruit(c["sous_ensemble"])]
    bruit = n0 - len(cartes)
    vus, uniques = set(), []
    for c in cartes:
        k = (c["sous_ensemble"], c["numero"], _n(c["joueur"]), c.get("inscription"))
        if k not in vus:
            vus.add(k)
            uniques.append(c)
    doublons = len(cartes) - len(uniques)
    cartes = uniques
    noms = []
    for c in cartes:
        if c["sous_ensemble"] not in noms:
            noms.append(c["sous_ensemble"])
    sous = []
    for nom in noms:
        lot = [c for c in cartes if c["sous_ensemble"] == nom]
        tir = {c["tirage"] for c in lot if c["tirage"]}
        cotes = [c.pop("_cotes") for c in lot if c.get("_cotes")]
        txt = max(set(cotes), key=cotes.count) if cotes else None
        g = groupe_de(nom)
        if g not in ("auto", "auto_memo") and lot and all(c["auto"] for c in lot):
            g = "auto"
        s = {"nom": nom, "groupe": g, "nb_cartes": len(lot), "tirage": tir.pop() if len(tir) == 1 else None,
             "parallele_de": None, "par_boite": None, "cotes": txt}
        ch = cote_hobby(txt)
        if ch:
            s["cote_hobby"] = ch
        sous.append(s)
    _paralleles(sous, cartes)
    _paralleles_famille(sous, cartes)
    return {"sous_ensembles": sous, "cartes": cartes, "lignes": len(cartes), "titre_doc": titre_doc,
            "nettoye": {"bruit": bruit, "doublons": doublons}, "annonces": annonces_resumes(rangs) if tableau else {}}


_RE_BRUIT = {"rx": None}


def _rx_bruit():
    if _RE_BRUIT["rx"] is None:
        _RE_BRUIT["rx"] = re.compile(r"^\s*(\d+\s+cards?|parallels?|base|checklist|\d+\s*:\s*\d+.*|.*\bpacks?\b.*|.*\bnot listed\b.*"
                                     r"|.*\bor fewer\b.*|.*\bsee list\b.*|(" + _COULEURS + r"|crest patch|patch|tag|chest patch|premium patch)"
                                     r"[a-z ]*\s*(/\s*\d+|1/1)\s*|(veterans|legends|rookies)\s*:.*)$", re.I)
    return _RE_BRUIT["rx"]


def est_bruit(nom):
    """Un « sous-ensemble » qui est en fait du texte de resume : « 57 cards », « Gold /15 », « 1:18 packs », « Parallels »."""
    return bool(_rx_bruit().match(str(nom or "")))


def annonces_resumes(rangs):
    """Les onglets de resume (texte libre) : « Auto Parallel » puis « 60 cards » -> {« Auto Parallel »: 60}."""
    out, dernier = {}, None
    for _f, cells in rangs:
        pleines = [c for c in cells if c]
        if len(pleines) != 1:
            if len(pleines) > 1:
                dernier = None
            continue
        t = pleines[0].strip()
        m = re.fullmatch(r"(\d+)\s+cards?", t, re.I)
        if m and dernier:
            out.setdefault(dernier, int(m.group(1)))
            dernier = None
        elif not est_bruit(t) and not _est_numero(t) and len(t) > 3:
            dernier = t
    return out


def verifier(lu):
    """Le rapport montre a l'importation (31 oct 2026) : ce qui est bon, et ce qui merite un coup d'oeil, en mots simples.
    -> {"ok": [...], "alertes": [...]}"""
    sous, cartes = lu["sous_ensembles"], lu["cartes"]
    nums = {}
    for c in cartes:                       # une inscription est une carte de plus (Celebrini « I Like Fishing »)
        nums.setdefault(c["sous_ensemble"], set()).add((c["numero"], c.get("inscription")))
    enfants = {}
    for s in sous:
        if s.get("parallele_de"):
            enfants.setdefault(s["parallele_de"], []).append(s["nom"])
    ok = [f"{len(cartes)} cartes lues dans {len(sous)} sets",
          f"{sum(1 for s in sous if s.get('parallele_de'))} parallèles reliées à leur carte de base"]
    rares = sum(1 for c in cartes if c.get("sp")) + sum(1 for c in cartes if c.get("inscription"))
    if rares:
        ok.append(f"{rares} cartes SP, SSP ou à inscription (comptées plus rares)")
    alertes = []
    ne = lu.get("nettoye") or {}
    if ne.get("bruit"):
        ok.append(f"{ne['bruit']} lignes de résumé ignorées (pas des cartes)")
    if ne.get("doublons"):
        ok.append(f"{ne['doublons']} doublons retirés")
    # ce que le fichier annonce (« 60 cards ») contre ce qu'on a trouve (la carte de base + les joueurs seulement numerotes)
    exacts = {_n(s["nom"]): s["nom"] for s in sous}
    cles = {cle_sous(s["nom"]): s["nom"] for s in sous}
    for nom_a, n in (lu.get("annonces") or {}).items():
        nom = exacts.get(_n(nom_a)) or cles.get(cle_sous(nom_a))
        if not nom:
            continue
        # « Base Set : 150 cards » couvre aussi « Base Set - Legends » et « Base Set - Rookies »
        groupe = [nom] + [s["nom"] for s in sous if _n(s["nom"]).startswith(_n(nom) + " - ")]
        trouves = set()
        for g in groupe:
            trouves |= {(g2, k) for g2 in [g] for k in nums.get(g) or set()}
            for e in enfants.get(g, []):
                trouves |= {(g, k) for k in nums.get(e) or set()}
        if len(trouves) < n:
            alertes.append(f"{nom} : {n} cartes annoncées, {len(trouves)} trouvées (il en manque {n - len(trouves)} dans le fichier)")
    seules = [s["nom"] for s in sous if re.search(r"\bparallel", s["nom"], re.I) and not s.get("parallele_de")
              and s.get("groupe") in ("base", "recrue", "insert")]
    if seules:
        alertes.append(f"{len(seules)} parallèle(s) sans carte de base reconnue, évaluée(s) à part : " + ", ".join(seules[:3]) + ("…" if len(seules) > 3 else ""))
    sans_equipe = sum(1 for c in cartes if not c.get("equipe"))
    if sans_equipe > len(cartes) * 0.2:
        alertes.append(f"{sans_equipe} cartes sans équipe reconnue : la vue par équipe sera incomplète")
    return {"ok": ok, "alertes": alertes[:8]}


def cote_hobby(txt):
    """« 1:30 h, 1:90 b » -> 30 (1 carte tous les 30 paquets hobby) ; « 3:1 h » -> 0.333. None sans cote hobby."""
    m = re.search(r"(\d[\d,]*)\s*:\s*(\d[\d,]*)\s*(?:h|hobby)\b", str(txt or ""), re.I)
    if not m:
        return None
    a, b = float(m.group(1).replace(",", "")), float(m.group(2).replace(",", ""))
    return round(b / a, 4) if a > 0 and b > 0 else None


_COULEURS = r"green|red|orange|blue|gold|purple|black|silver|pink|yellow|white|bronze|copper|teal|aqua|emerald|ruby|sapphire|platinum"


def _paralleles(sous, cartes):
    """« Green Foil Parallel » = parallele de « Base Set » : meme liste de numeros, sous-ensemble non parallele avant lui.
    31 oct 2026 (Stature 2025-26) : « Green Auto Parallel - Rookies » = parallele de « Auto Parallel - Rookies » (le meme nom
    sans la couleur), meme si le parent s'appelle lui aussi « Parallel » et qu'il manque des joueurs dans certaines couleurs
    (les vedettes SSP ne commencent qu'aux petits tirages)."""
    nums = {}
    for c in cartes:
        nums.setdefault(c["sous_ensemble"], set()).add(c["numero"])
    par_nom = {_n(s["nom"]): s for s in sous}
    for s in sous:
        m = re.match(rf"^(.*?\b)?({_COULEURS})\s+(.+)$", s["nom"].strip(), re.I)
        if not m:
            continue
        base = _n(((m.group(1) or "") + m.group(3)).strip())
        p = par_nom.get(base)
        if p and p is not s and not p.get("parallele_de") and (nums.get(s["nom"], set()) & nums.get(p["nom"], set())):
            s["parallele_de"] = p["nom"]
            if s["groupe"] == "insert":
                s["groupe"] = p["groupe"]
    for i, s in enumerate(sous):
        if s.get("parallele_de") or not re.search(r"\bparallel", s["nom"], re.I):
            continue
        for p in sous[:i]:
            if not re.search(r"\bparallel", p["nom"], re.I) and nums.get(p["nom"]) == nums.get(s["nom"]):
                s["parallele_de"] = p["nom"]
                if s["groupe"] == "insert":
                    s["groupe"] = p["groupe"]
                break


_DESCRIPTEURS = set("""parallel parallels chest crest tag logo logos shoulder sleeve number numbers commemorative premium jumbo
spectrum the and of""".split())
_MEMO_MOTS = set("jersey jerseys patch patches memorabilia relic relics nameplate swatch fabric fabrics material".split())


def _cle_famille(nom):
    """« Premier Rookie Auto Patch Parallel » et « Premier Rookie Auto Jersey » -> la meme cle (premier rookie auto + memo)."""
    t = re.sub(r"\(.*?\)", " ", _n(nom))
    mots = {"memo"} if re.search(r"\b(shoulder|sleeve|chest|crest|tag|nameplate)\b", t) else set()
    for w in re.split(r"[^a-z0-9]+", t):
        if not w or re.fullmatch(_COULEURS, w) or w in _DESCRIPTEURS:
            continue
        mots.add("memo" if w in _MEMO_MOTS else w)
    return frozenset(mots)


def _paralleles_famille(sous, cartes):
    """31 oct 2026 (Premier 2025-26) : « Acetate Patch Auto Gold Parallel » -> « Acetate Patch Auto », « Premier Rookie Auto
    Patch Parallel » -> « Premier Rookie Auto Jersey », « Nameplate Parallel » -> « Jersey Parallel » : meme famille (memes
    mots, sans la couleur ni la sorte de patch) et la plupart des memes numeros."""
    nums = {}
    for c in cartes:
        nums.setdefault(c["sous_ensemble"], set()).add(c["numero"])
    for i, s in enumerate(sous):
        if s.get("parallele_de") or not re.search(r"\bparallel", s["nom"], re.I):
            continue
        k = _cle_famille(s["nom"])
        if len(k) < 1 or k == frozenset(["memo"]) and not re.search(r"jersey|memorabilia|nameplate|patch", s["nom"], re.I):
            continue
        ns = nums.get(s["nom"]) or set()
        for p in sous:
            if p is s or p.get("parallele_de") or _cle_famille(p["nom"]) != k:
                continue
            np_ = nums.get(p["nom"]) or set()
            if ns and len(ns & np_) >= 0.5 * len(ns) and (sous.index(p) < i or not re.search(r"\bparallel", p["nom"], re.I)):
                s["parallele_de"] = p["nom"]
                break


def cle_sous(nom):
    """Cle de rapprochement de deux noms de sous-ensemble (Beckett, GTS, catalogue) :
    « Deluxe Parallel - Young Guns » = « Young Guns Deluxe » ; « Population Count 500 Parallel » = « Population Count /500 »."""
    t = _n(nom).replace("&", " and ")
    t = re.sub(r"[^a-z0-9]+", " ", t)
    mots = [w for w in t.split() if w not in ("set", "sets", "card", "cards", "checklist", "parallel", "parallels", "the")]
    if len(mots) > 1:
        mots = [w for w in mots if w != "base"]
    mots = [w[:-1] if len(w) > 4 and w.endswith("s") and not w.endswith("ss") else w for w in mots]   # Bootlegs = Bootleg
    return " ".join(sorted(set(mots)))


def par_boite_depuis_cotes(prod):
    """Cotes hobby de la checklist -> cartes par boite (paquets de la boite hobby / cote), sans ecraser une valeur connue."""
    paquets = next((f.get("paquets") for f in prod.get("formats") or [] if f.get("paquets") and "hobby" in _n(f.get("format"))), None)
    n = 0
    if not paquets:
        return 0
    for s in prod.get("sous_ensembles") or []:
        if s.get("par_boite") is None and s.get("cote_hobby"):
            s["par_boite"] = round(paquets / s["cote_hobby"], 3)
            n += 1
    return n


def fusionner(existant, lu):
    """Produit deja au catalogue : on remplace les cartes des sous-ensembles lus et on GARDE leurs cotes par boite."""
    if not existant:
        return None
    se_old = {s["nom"]: s for s in existant.get("sous_ensembles") or []}
    # « BASE SET » (Beckett) = « Base » (catalogue) : meme sous-ensemble, on garde son nom et ses cotes
    cle = cle_sous
    par_cle = {cle(n): n for n in se_old}
    # meme liste de numeros, nom different (« Dazzlers » = « Dazzlers Blue ») : c'est le meme sous-ensemble
    nums = lambda cartes, nom: frozenset(c.get("numero") for c in cartes if c.get("sous_ensemble") == nom)
    libres = [n for n in se_old if not any(cle(s["nom"]) == cle(n) for s in lu["sous_ensembles"])]
    for s in lu["sous_ensembles"]:
        if cle(s["nom"]) in par_cle or s.get("parallele_de"):
            continue
        ns = nums(lu["cartes"], s["nom"])
        for n in libres:
            if ns and nums(existant.get("cartes") or [], n) == ns and not (se_old[n].get("parallele_de")):
                par_cle[cle(s["nom"])] = n
                libres.remove(n)
                break
    for c in lu["cartes"]:
        c["sous_ensemble"] = par_cle.get(cle(c["sous_ensemble"]), c["sous_ensemble"])
    for s in lu["sous_ensembles"]:
        s["nom"] = par_cle.get(cle(s["nom"]), s["nom"])
    noms_lus = {s["nom"] for s in lu["sous_ensembles"]}
    cartes = [c for c in existant.get("cartes") or [] if c.get("sous_ensemble") not in noms_lus] + lu["cartes"]
    sous = list(existant.get("sous_ensembles") or [])
    for s in lu["sous_ensembles"]:
        if s["nom"] in se_old:
            o = se_old[s["nom"]]
            o.update(nb_cartes=s["nb_cartes"], tirage=o.get("tirage") or s["tirage"], cotes=o.get("cotes") or s.get("cotes"),
                     parallele_de=o.get("parallele_de") or (par_cle.get(cle(s["parallele_de"]), s["parallele_de"]) if s.get("parallele_de") else None))
            if s.get("cote_hobby") and not o.get("cote_hobby"):
                o["cote_hobby"] = s["cote_hobby"]
        else:
            sous.append(s)
    out = {k: v for k, v in existant.items() if not k.startswith("_")}
    out.update(cartes=cartes, sous_ensembles=sous)
    return out


# 24 oct 2026 - Mathieu : « je veux un service cle en main, je veux pas que le user ait a telecharger le fichier ».
# Seul l'administrateur importe (une fois par produit, plusieurs fichiers d'un coup) ; tous les comptes en profitent.
# Le nom vient du nom du fichier ; les cotes par boite, du meme produit d'une autre annee / serie (jamais inventees).
_MOTS_FICHIER = r"\b(checklist|check list|hockey|baseball|basketball|football|soccer|cards?|set|beckett|final|updated?|v\d+|xlsx?|csv)\b"


def nom_devine(nom_fichier):
    """« 2025-26-Upper-Deck-Series-2-Hockey-Checklist.xlsx » -> « 2025-26 Upper Deck Series 2 »."""
    n = re.sub(r"\.(xlsx|xlsm|xls|csv)$", "", str(nom_fichier or ""), flags=re.I)
    n = re.sub(r"(?<=\d{4})[-_ ](?=\d{2}\b)", "§", n)            # garde le tiret de la saison 2025-26
    n = re.sub(r"[-_.]+", " ", n).replace("§", "-")
    n = re.sub(_MOTS_FICHIER, " ", n, flags=re.I)
    n = re.sub(r"\(\d+\)", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return " ".join(w if (w.isupper() or any(ch.isdigit() for ch in w)) else w.capitalize() for w in n.split())


def _mots_ligne(nom):
    """Les mots qui definissent la ligne du produit (sans la saison) : « upper deck series 2 »."""
    t = _n(nom).replace("ud ", "upper deck ")
    return [w for w in re.sub(r"(19|20)\d{2}(-\d{2})?", " ", t).split() if w]


def cotes_modele(prod, autres):
    """Copie formats et cotes par boite du produit le plus proche (meme marque et ligne, saison la plus proche).
    Renvoie (produit, nom_du_modele | None)."""
    mots = _mots_ligne(prod.get("nom"))
    saison = int((re.search(r"(19|20)\d{2}", str(prod.get("nom"))) or [0])[0] or 0)
    meilleur, score_m = None, 0
    for a in autres or []:
        if not a or a.get("id") == prod.get("id") or str(a.get("sport") or "hockey") != str(prod.get("sport") or "hockey"):
            continue
        ma = _mots_ligne(a.get("nom"))
        communs = len(set(mots) & set(ma))
        # 25 oct 2026 : « Upper Deck » seul ne suffit pas (Artifacts n'a pas les cotes de Series 1)
        if communs < 2 or not (_mots_produit(prod.get("nom"))[1] & _mots_produit(a.get("nom"))[1]):
            continue
        sa = int((re.search(r"(19|20)\d{2}", str(a.get("nom"))) or [0])[0] or 0)
        score = communs * 10 + (5 if ma == mots else 0) - min(abs(saison - sa), 5) \
            + sum(1 for s in a.get("sous_ensembles") or [] if s.get("par_boite"))
        if score > score_m:
            meilleur, score_m = a, score
    if not meilleur:
        return prod, None
    cle = cle_sous
    ref = {cle(s["nom"]): s for s in meilleur.get("sous_ensembles") or []}
    copie = 0
    for s in prod.get("sous_ensembles") or []:
        r = ref.get(cle(s["nom"]))
        if r and r.get("par_boite") is not None and s.get("par_boite") is None:
            s["par_boite"] = r["par_boite"]
            s["nom"] = r["nom"]
            copie += 1
    if not copie:
        return prod, None
    noms = {s["nom"] for s in prod["sous_ensembles"]}
    for c in prod.get("cartes") or []:          # memes noms que le modele (Base Set -> Base)
        k = ref.get(cle(c.get("sous_ensemble") or ""))
        if k and k["nom"] in noms:
            c["sous_ensemble"] = k["nom"]
    if meilleur.get("formats"):
        prod["formats"] = [dict(f) for f in meilleur["formats"]]
    if meilleur.get("groupes_boite"):
        prod["groupes_boite"] = [dict(g) for g in meilleur["groupes_boite"]]
    prod["notes"] = [x for x in prod.get("notes") or [] if "à compléter" not in x] + \
        [f"Cotes par boîte reprises de {meilleur.get('nom')} ({copie} sous-ensembles) : à confirmer"]
    return prod, meilleur.get("nom")


_MARQUES = {"upper", "deck", "ud", "topps", "panini", "leaf", "in", "the", "game", "hockey", "nhl", "cards", "card"}


def _mots_produit(nom):
    t = _n(nom).replace("series one", "series 1").replace("series two", "series 2")
    an = (re.search(r"(19|20)\d{2}", t) or [""])[0]
    mots = set(re.sub(r"(19|20)\d{2}(-\d{2})?", " ", t).replace("-", " ").split()) - _MARQUES
    mots |= {w for w in ("game",) if re.search(r"\bgame used\b", t)}    # « SP Game Used » garde « game »
    return an, mots


def produit_semblable(nom, produits):
    """Le produit du catalogue qui est le meme que `nom` (meme saison ; les mots de l'un contenus dans l'autre,
    marques mises a part) : « 2025-26 Upper Deck SP Authentic » = « 2025-26 SP Authentic ». -> produit | None."""
    an, mots = _mots_produit(nom)
    if not an or not mots:
        return None
    meilleur = None
    for p in produits or []:
        a2, m2 = _mots_produit(p.get("nom"))
        if a2 != an or not m2:
            continue
        if mots == m2:
            return p
        petit, grand = (mots, m2) if len(mots) <= len(m2) else (m2, mots)
        if petit <= grand and (len(petit) >= 2 or grand - petit <= {"series", "edition", "set"}) and len(grand - petit) <= 2:
            meilleur = meilleur or p
    return meilleur
