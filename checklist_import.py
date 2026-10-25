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
    "tirage": ("print run", "serial", "serial #", "numbered", "seq", "seq.", "/#", "#'d", "run"),
    "notes": ("notes", "note", "rc", "rookie", "info", "attributes"),
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
    auto = bool(re.search(r"auto|signature|signed|ink|chirography|inscri", t))
    memo = bool(re.search(r"patch|jersey|material|relic|memorabilia|swatch|game[- ]used|game[- ]worn|fabric|stick|threads", t))
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
    cartes, idx, titre = [], None, None
    feuille_prec = None
    for feuille, cells in rangs:
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
            # mise en page 2 : titre de sous-ensemble seul sur sa ligne, puis « numero joueur equipe »
            if len(pleines) == 1 and not _est_numero(pleines[0]):
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
        codes = [sports.code_equipe(e, sport) for e in re.split(r"\s*/\s*|\s*,\s*", str(equipe_txt)) if e.strip()]
        rc = bool(re.search(r"\bRC\b|rookie", notes + " " + joueur + " " + str(g("equipe") or ""), re.I))
        joueur = re.sub(r"\s*\bRC\b\s*", " ", joueur).strip(" ,")
        se = re.sub(r"\s+", " ", str(se)).strip()
        cartes.append({"numero": str(num).strip(), "joueur": joueur, "equipe": "/".join(c for c in codes if c) or str(equipe_txt).strip(),
                       "sous_ensemble": se, "recrue": rc or groupe_de(se) == "recrue", "auto": groupe_de(se) in ("auto", "auto_memo"),
                       "memo": groupe_de(se) in ("memo", "auto_memo"),
                       "tirage": _tirage_colonne(g("tirage") if idx else "") or tirage_de(notes, se)})
    noms = []
    for c in cartes:
        if c["sous_ensemble"] not in noms:
            noms.append(c["sous_ensemble"])
    sous = []
    for nom in noms:
        lot = [c for c in cartes if c["sous_ensemble"] == nom]
        tir = {c["tirage"] for c in lot if c["tirage"]}
        sous.append({"nom": nom, "groupe": groupe_de(nom), "nb_cartes": len(lot), "tirage": tir.pop() if len(tir) == 1 else None,
                     "parallele_de": None, "par_boite": None, "cotes": None})
    return {"sous_ensembles": sous, "cartes": cartes, "lignes": len(cartes)}


def fusionner(existant, lu):
    """Produit deja au catalogue : on remplace les cartes des sous-ensembles lus et on GARDE leurs cotes par boite."""
    if not existant:
        return None
    se_old = {s["nom"]: s for s in existant.get("sous_ensembles") or []}
    # « BASE SET » (Beckett) = « Base » (catalogue) : meme sous-ensemble, on garde son nom et ses cotes
    cle = lambda n: re.sub(r"\b(set|cards?|checklist)\b", " ", _n(n)).replace("  ", " ").strip()
    par_cle = {cle(n): n for n in se_old}
    for c in lu["cartes"]:
        c["sous_ensemble"] = par_cle.get(cle(c["sous_ensemble"]), c["sous_ensemble"])
    for s in lu["sous_ensembles"]:
        s["nom"] = par_cle.get(cle(s["nom"]), s["nom"])
    noms_lus = {s["nom"] for s in lu["sous_ensembles"]}
    cartes = [c for c in existant.get("cartes") or [] if c.get("sous_ensemble") not in noms_lus] + lu["cartes"]
    sous = list(existant.get("sous_ensembles") or [])
    for s in lu["sous_ensembles"]:
        if s["nom"] in se_old:
            se_old[s["nom"]].update(nb_cartes=s["nb_cartes"], tirage=se_old[s["nom"]].get("tirage") or s["tirage"])
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
        if communs < 2:
            continue
        sa = int((re.search(r"(19|20)\d{2}", str(a.get("nom"))) or [0])[0] or 0)
        score = communs * 10 + (5 if ma == mots else 0) - min(abs(saison - sa), 5) \
            + sum(1 for s in a.get("sous_ensembles") or [] if s.get("par_boite"))
        if score > score_m:
            meilleur, score_m = a, score
    if not meilleur:
        return prod, None
    cle = lambda n: re.sub(r"\b(set|cards?|checklist)\b", " ", _n(n)).replace("  ", " ").strip()
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
