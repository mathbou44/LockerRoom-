"""
SLABCOACH - le bareme SlabIQ de la SORTE de carte, ecrit avec l'expert (16 nov 2026).

Mathieu (questionnaire du 16 nov) : « les Young Guns, Future Watch Auto / Auto Patch, The Cup RPA, Premier RPA sont des
cartes A+ ultra recherchees (la carte seulement) ; base-toi sur nos ventes et sur ce que le hobby sait ». Nos ventes (246 000
ventes de hockey, mai-oct. 2026) confirment le volume des Young Guns ; elles sont trop biaisees par nos recherches pour classer
toutes les sortes : le bareme vient donc de l'expert, et les ventes le verifient a mesure.

LA SORTE (la carte seulement, pas le joueur) -> une lettre :
  A+ : Young Guns gradee 10 ; TOUTES les variantes de Young Guns (Exclusives, High Gloss, Canvas, Clear Cut, Outburst,
       Deluxe, Silver Foil, French, Retro, Photo Variation / SSP) ; The Cup RPA ; Premier Rookie Auto Patch ;
       SP Authentic Future Watch Auto (et Auto Patch) ; Kaboom, Downtown, Uptown (autres sports : pas au hockey)
  A  : Young Guns raw (et gradee 9 et moins) ; Ice Premieres
       (auto / patch), OPC Platinum Rookie Auto, Black Diamond Rookie Gems Auto ; Clear Cut, Manga, Color Blast
  B+ : Fluorescence
  B  : les autos de base de produits moyens ; patch / jersey sans auto ; Dazzlers
  Numerotees (une parallele sans autre raison) : /10 et moins A- ; /25 a /50 B+ ; /99 a /199 B ; /250 et plus C
  D  : une carte de base, sans numero
La sorte garde la MEILLEURE regle qui s'applique (une Future Watch Auto /99 reste A+).

LA NOTE FINALE (sorte x joueur) : l'expert : « une YG raw (A) d'un joueur moyen (C) -> C » ; « une base (D) d'une superstar
(A+) -> C ». Le plus faible des deux domine : note = min + 25 % de l'ecart (YG 88 / joueur 57 -> 65 = B ... 64 = C ;
base 40 / McDavid 95 -> 54 = C).
LE JOUEUR : sa cote de COLLECTION (la popularite dans le hobby, pas la forme de la semaine) : la lettre donnee par l'expert
(JOUEURS_EXPERT, questionnaires du 16 nov) ; sinon la demande de ses cartes dans nos ventes et sa notoriete (Indice SlabIQ).
EN FEU (en feu, en hausse, buzz) : un demi-cran de plus (FEU_PTS), et la raison « Marche chaud ».
"""
import re

NOTE = {"A+": 95, "A": 88, "A-": 82, "B+": 76, "B": 68, "C+": 61, "C": 55, "D": 40, "E": 25}
PART_ECART = 0.25
JOUEUR_INCONNU = 30              # 16 nov (« genre de carte qui devrait etre E ») : un joueur sans aucune demande connue
FEU_PTS = 4                     # « un joueur en feu : un demi-cran » (B -> B+)
PLAFOND_LOT = 45                # un lot, un checklist, une reimpression reste D, peu importe le joueur

# La cote de collection des joueurs, par l'expert (questionnaires du 16 nov 2026). A garder court : le reste vient des ventes.
JOUEURS_EXPERT = {
    "Connor McDavid": "A+", "Sidney Crosby": "A+", "Alex Ovechkin": "A+", "Connor Bedard": "A+", "Macklin Celebrini": "A+",
    "Cole Caufield": "A+", "Auston Matthews": "A+",
    "Ivan Demidov": "A", "Lane Hutson": "A", "Nick Suzuki": "A", "Kirill Kaprizov": "A", "Leon Draisaitl": "A",
    "Nathan MacKinnon": "A",
    "Matvei Michkov": "A-", "Juraj Slafkovsky": "A-", "William Nylander": "A-",
    "Adam Fantilli": "B+", "Mitch Marner": "B+", "Matt Duchene": "B+", "Mark Scheifele": "B+", "Mathew Barzal": "B+",
    "Quinn Hutson": "B", "Jakub Dobes": "B",
    "Tyler Bertuzzi": "C+",
    "Aliaksei Protas": "C", "Dylan Holloway": "C",
    "Brendan Smith": "D",
    # ronde 5 : les legendes et d'autres marches
    "Wayne Gretzky": "A+", "Mario Lemieux": "A+", "Patrick Roy": "A+",
    "Jaromir Jagr": "A", "Carey Price": "A", "Guy Lafleur": "A",
    "Patrick Kane": "A-", "Pavel Datsyuk": "A-", "Marc-Andre Fleury": "A-",
    "Jack Hughes": "A", "Quinn Hughes": "A-", "Matthew Schaefer": "A",
    "Easton Cowan": "B+", "Jacob Fowler": "A-", "Tim Stutzle": "A-", "Tim Stützle": "A-",
    "Brandon Hagel": "B", "Elias Pettersson": "B", "Matthew Tkachuk": "B+",
}
# La demande de ses cartes (nos ventes) et sa notoriete -> une note (points d'appui calibres sur les lettres de l'expert)
_APPUIS = ((30, 20), (45, 35), (55, 55), (65, 61), (75, 68), (85, 76), (92, 82), (96, 88), (99, 95), (100, 95))

_R = lambda m: re.compile(m)
YG = _R(r"\byoung guns?\b|\byg\b")
CUP_RPA = _R(r"\bthe cup\b")
PREMIER = _R(r"\bpremier\b")
FW = _R(r"\bfuture watch\b")
CASE_HITS = _R(r"\bkaboom\b|\bdowntowns?\b|\buptowns?\b")
HOCKEY_UD = _R(r"\bupper deck\b|\bo-pee-chee\b|\bopc\b|\bsp authentic\b|\bthe cup\b|\bud\b")
YG_VAR = _R(r"\bexclusives?\b|\bhigh gloss\b|\bcanvas\b|\bclear ?cut\b|\boutburst\b|\bdeluxe\b|\bsilver foil\b"
            r"|\bfrench\b|\bretro\b|\bphoto variations?\b|\bssp\b|\bsp variation\b")
CANVAS = _R(r"\bcanvas\b")
ICE_PREM = _R(r"\bice\b.*\bpremieres?\b|\bpremieres?\b.*\bice\b")
OPC_PLAT = _R(r"\bo-pee-chee platinum\b|\bopc platinum\b|\bplatinum\b")
BD_GEMS = _R(r"\bblack diamond\b")
INSERTS_A = _R(r"\bclear ?cut\b|\bmanga\b|\bcolou?r ?blast\b")
FLUO = _R(r"\bfluorescence\b")
DAZZ = _R(r"\bdazzlers?\b")


RC_AUTO_A = _R(r"\bultimate\b|\bsp game used\b|\bspx\b|\btrilogy\b")


def _annee(t):
    """L'annee de la saison (1979-80 -> 1979), sinon None."""
    m = re.search(r"\b(19[5-9]\d|20[0-3]\d)\b", t or "")
    return int(m.group(1)) if m else None


def _gem(g):
    n = str((g or {}).get("note") or "")
    return n in ("10", "9.5") or n.startswith("10")


def sorte(titre):
    """(lettre, raison) de la SORTE de carte, d'apres le titre (cartes_match le decode)."""
    import cartes_match
    d = cartes_match._decoder_memo(titre or "")
    t = " " + (d.get("texte") or str(titre or "").lower()) + " "
    auto, patch, serie, g = bool(d.get("auto")), bool(d.get("patch")), d.get("serie"), d.get("grade")
    rc = bool(d.get("rc")) or bool(re.search(r"\brookies?\b|\brc\b", t))
    c = []                                             # (lettre, raison) : on garde la meilleure
    if d.get("exclu") or re.search(r"\bchecklist\b|\blot\b|\breprint\b|\bcustom\b", t):
        return ("D", "lot_checklist")                  # un lot, un checklist, une reimpression : jamais une bonne sorte
    yg = bool(YG.search(t))
    brut = " " + str(titre or "").lower() + " "
    if yg and re.search(r"\bretro\b|\brenewed\b", brut) and not re.search(r"\brookies?\b|\brc\b|\(rc\)", brut):
        yg = False                                     # une « Retro / Renewed Young Guns » d'un veteran : un insert, pas sa YG
        c.append(("B", "insert_retro"))
    if yg and _gem(g) and not CANVAS.search(t):
        c.append(("A+", "yg10"))
    if CUP_RPA.search(t) and rc and auto and patch:
        c.append(("A+", "cup_rpa"))
    if PREMIER.search(t) and rc and auto and patch:
        c.append(("A+", "premier_rpa"))
    if FW.search(t) and auto:
        c.append(("A+", "fw_auto"))
    if CASE_HITS.search(t) and not HOCKEY_UD.search(t):
        c.append(("A+", "case_hit"))      # Kaboom, Downtown : des produits Panini (pas au hockey)
    if yg:
        c.append(("A", "yg"))
        if YG_VAR.search(t):
            c.append(("A+", "yg_variante"))   # « toutes les variantes de YG sont ultra recherchees »
    # ronde 5 : les grosses recrues autographes (Ultimate, SP Game Used, SPx, Trilogy, une RPA d'Artifacts...) : A
    if rc and auto and (patch or RC_AUTO_A.search(t)):
        c.append(("A", "rc_auto"))
    # ronde 5 : la vraie carte recrue d'avant les Young Guns (Gretzky OPC 1979, Lemieux OPC 1985, Jagr UD 1990) : comme une YG
    an = _annee(brut)
    if rc and not yg and an and an <= 1990 and not auto:
        c.append(("A+" if _gem(g) else "A", "rc_vintage"))
    if ICE_PREM.search(t) and (auto or patch):
        c.append(("A", "ice_premieres"))
    if OPC_PLAT.search(t) and rc and auto:
        c.append(("A", "opc_plat_auto"))
    if BD_GEMS.search(t) and rc and auto:
        c.append(("A", "bd_gems"))
    if INSERTS_A.search(t):
        c.append(("A", "insert_a"))
    if FLUO.search(t):
        c.append(("B+", "fluorescence"))
    if auto:
        c.append(("B", "auto"))
    if patch:
        c.append(("B", "patch"))
    if DAZZ.search(t):
        c.append(("B", "dazzlers"))
    if serie:
        s = int(serie)
        c.append(("A-" if s <= 10 else "B+" if s <= 50 else "B" if s <= 199 else "C", "numerotee"))
    if not c:
        c.append(("D", "base"))
    return max(c, key=lambda x: NOTE[x[0]])


JOUEUR_RECRUE_INCONNUE = 68    # « un rookie que SlabIQ ne connait pas encore = B » (il se corrige des qu'on a ses ventes)


def note_joueur(nom, criteres=None, recrue=False):
    """(note 0-100, lettre, source) : la cote de COLLECTION du joueur : l'expert, sinon la demande et la notoriete ;
    un inconnu vaut C, une recrue inconnue (sa carte recrue) vaut B."""
    l = JOUEURS_EXPERT.get(nom or "") or next((v for k, v in JOUEURS_EXPERT.items() if k.lower() == str(nom or "").lower()), None)
    if l:
        return float(NOTE[l]), l, "expert"
    c = criteres or {}
    if c.get("demande") is None and c.get("notoriete") is None:
        if recrue:
            return float(JOUEUR_RECRUE_INCONNUE), "B", "recrue_inconnue"
        return float(JOUEUR_INCONNU), "E", "inconnu"
    w = [(0.7, c.get("demande")), (0.3, c.get("notoriete"))]
    w = [(p, float(v)) for p, v in w if v is not None]
    x = sum(p * v for p, v in w) / sum(p for p, _ in w)
    n = _APPUIS[0][1] if x <= _APPUIS[0][0] else None
    for (a, na), (b, nb) in zip(_APPUIS, _APPUIS[1:]):
        if n is None and a <= x <= b:
            n = na + (nb - na) * (x - a) / (b - a) if b > a else nb
    n = round(n if n is not None else _APPUIS[-1][1], 1)
    if recrue and c.get("notoriete") is None and n < JOUEUR_RECRUE_INCONNUE:
        return float(JOUEUR_RECRUE_INCONNUE), "B", "recrue_inconnue"     # une recrue pas encore connue du public
    return n, lettre_joueur(n), "ventes"


def lettre_joueur(n):
    for s, l in ((92, "A+"), (85, "A"), (80, "A-"), (73, "B+"), (65, "B"), (58, "C+"), (50, "C"), (35, "D")):
        if n >= s:
            return l
    return "E"


def recrue_recente(titre, rc):
    """Une carte recrue de la saison en cours ou de la precedente (« un rookie inconnu = B » : seulement un VRAI nouveau ;
    une recrue de 2021 que personne n'achete n'est pas un rookie a decouvrir)."""
    if not rc:
        return False
    import datetime as _d
    a = _annee(str(titre or "").lower())
    if a is None:
        return True
    t = _d.date.today()
    saison = t.year if t.month >= 8 else t.year - 1
    return a >= saison - 1


def note_finale(n_sorte, n_joueur):
    """La note SlabIQ (0-100) : le plus faible des deux domine, plus 25 % de l'ecart."""
    a, b = float(n_sorte), float(n_joueur if n_joueur is not None else JOUEUR_INCONNU)
    lo, hi = min(a, b), max(a, b)
    return round(lo + PART_ECART * (hi - lo), 1)


def lettre(n):
    for s, l in ((92, "A+"), (85, "A"), (80, "A-"), (73, "B+"), (65, "B"), (50, "C"), (40, "D")):
        if n >= s:
            return l
    return "E"                 # 16 nov 2026 (Mathieu : « genre de carte qui devrait etre E ») : sous D
