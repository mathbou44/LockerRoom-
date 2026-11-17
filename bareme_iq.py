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
import time

NOTE = {"A+": 95, "A": 88, "A-": 82, "B+": 76, "B": 68, "B-": 64, "C+": 61, "C": 55, "D": 40, "E": 25}
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
    "Brandon Hagel": "B", "Dawson Mercer": "B-", "Sebastian Aho": "B+",
    # ronde 6 (16 nov) : les joueurs du milieu
    "Quinton Byfield": "B", "Mavrik Bourque": "B-", "Kirby Dach": "C+", "Matthew Knies": "B+", "Dylan Guenther": "B+",
    # 17 nov 2026 (Mathieu : « Gridin est bien plus qu'un D : un 2e annee avec un bon potentiel, au moins un B+ »)
    "Matvei Gridin": "B+", "Jonathan Lekkerimaki": "B+",
    "Logan Cooley": "A-", "Elias Pettersson": "B", "Matthew Tkachuk": "B+",
}
# La demande de ses cartes (nos ventes) et sa notoriete -> une note (points d'appui calibres sur les lettres de l'expert)
# 16 nov 2026 (Mathieu : « Byfield et Bourque ne sont surement pas des E ») : un joueur MOYEN (demande au milieu des ~870
# joueurs suivis) vaut C, pas D ; D et E restent pour le bas de la liste (le quart le moins demande)
_APPUIS = ((10, 25), (25, 40), (45, 52), (55, 57), (65, 61), (75, 68), (85, 76), (92, 82), (96, 88), (99, 95), (100, 95))

_R = lambda m: re.compile(m)
YG = _R(r"\byoung guns?\b|\byg\b")
CUP_RPA = _R(r"\bthe cup\b")
PREMIER = _R(r"\bpremier\b")
FW = _R(r"\bfuture watch\b")
CASE_HITS = _R(r"\bkaboom\b|\bdowntowns?\b|\buptowns?\b")
HOCKEY_UD = _R(r"\bupper deck\b|\bo-pee-chee\b|\bopc\b|\bsp authentic\b|\bthe cup\b|\bud\b")
YG_VAR = _R(r"\bexclusives?\b|\bhigh gloss\b|\bcanvas\b|\bclear ?cut\b|\boutburst\b|\bdeluxe\b|\bsilver foil\b"
            r"|\bfrench\b|\bretro\b|\bphoto variations?\b|\bssp\b|\bsp variation\b"
            # 17 nov 2026 (Mathieu : « tous les Young Guns paralleles sont mega recherches : Outburst, Clear Cut, Acetate,
            # Outburst Gold, Red... ») : les couleurs aussi (sans confondre Red Wings, Blue Jackets, Golden Knights)
            r"|\bacetate\b|\bgold\b|\bred\b(?! wings)|\bblue\b(?! jackets)|\bgreen\b|\bpurple\b|\borange\b|\bpink\b"
            r"|\bblack\b|\brainbow\b|\bfoil\b|\bparallel\b|\bvariations?\b|\bglossy\b")
# 17 nov 2026 (Mathieu : « parfois elle n'est pas numerotee mais c'est une SSP ou une SP et devient rare, comme les OPC
# Platinum Marquee Rookie variation ») : la courte impression non numerotee
SSP = _R(r"\bssp\b|\bsuper short print\b|\bcase hit\b")
SP_ = _R(r"\bsp\b(?! ?(?:authentic|game|signature|legendary|premier|x\b))|\bshort print\b|\bvariations?\b|\bphoto var\b|\bimage var")
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
    rc = bool(d.get("rc")) or bool(re.search(r"\brookies?\b|\brc\b|\br/c\b|\(rc\)", t + " " + str(titre or "").lower()))
    c = []                                             # (lettre, raison) : on garde la meilleure
    if d.get("exclu") or re.search(r"\bchecklist\b|\blot\b|\breprint\b|\bcustom\b|\bu-? ?pick\b|\byou pick\b|\bpick (?:from|your|one)\b"
                                          r"|\b(?:complete|finish) your set\b|\byou choose\b|\bfrom list\b|\bpick list\b", t):
        return ("D", "lot_checklist")                  # un lot, un checklist, une reimpression : jamais une bonne sorte
    yg = bool(YG.search(t))
    brut = " " + str(titre or "").lower() + " "
    # 17 nov 2026 (audit : « UD Series 1 Outburst #224 Sandis Vilmanis R/C » note D) : sans les mots « Young Guns », le numero
    # dit si c'est une YG (Series 1 : 201-250, Series 2 : 451-500, Extended : 701-750) quand c'est une recrue Upper Deck
    if not yg and rc and re.search(r"\bupper deck\b|\bud\b", brut) and not re.search(r"\bsp\b|\bice\b|\bartifacts\b|\bcup\b|\bpremier\b|\bmvp\b|\bo-pee-chee\b|\bopc\b|\bcanvas\b|\bchronology\b|\bsynergy\b|\btrilogy\b|\bultimate\b|\bclear cut\b|\bblack diamond\b|\bcredentials\b|\ballure\b|\bstature\b|\bmetal\b|\bengrained\b|\btim hortons\b|\bpremieres\b|\bauto", brut):
        mn = re.search(r"#\s*(\d{3})\b", brut)
        no = int(mn.group(1)) if mn else None
        if no and ((re.search(r"\bseries (?:1|one|i)\b", brut) and 201 <= no <= 250) or (re.search(r"\bseries (?:2|two|ii)\b", brut) and 451 <= no <= 500)
                   or (re.search(r"\bextended\b", brut) and 701 <= no <= 750)):
            yg = True
    # 16 nov 2026 (Mathieu : « les Young Guns Renewed ne valent presque rien ; seulement McDavid, Crosby, Ovechkin passent
    # 10 $ » ; verifie sur nos ventes : McDavid 15 $, Crosby 13,50 $, Ovechkin 12,60 $, les autres 2 a 6 $, la masse 1,90 $)
    if yg and re.search(r"\brenewed\b", brut):
        return ("E", "yg_renewed")
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
        # 17 nov 2026 (Mathieu : Lekkerimaki Ultimate Collection Rookie Auto /299 « la carte est un B ») : une recrue auto sans
        # patch tiree a plus de 199 copies reste B
        c.append(("B" if not patch and serie and int(serie) > 199 else "A", "rc_auto"))
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
    if yg and serie:
        c.append(("A+", "yg_variante"))               # une YG numerotee est une variante
    if not serie and SSP.search(brut):
        c.append(("B+", "ssp"))
    elif not serie and SP_.search(brut):
        c.append(("B+" if rc else "B", "sp"))          # une variation de recrue (Marquee Rookie variation) : B+
    if not c:
        c.append(("D", "base"))
    best = max(c, key=lambda x: NOTE[x[0]])
    # 17 nov 2026 : la lettre d'une sorte choisie par l'expert en repondant a la boucle de validation (validation_iq)
    so = cotes_sortes().get(best[1])
    return (so, best[1]) if so and best[1] != "numerotee" else best


_SORTES = {"t": 0.0, "d": {}}


def cotes_sortes():
    if time.time() - _SORTES["t"] > 30:
        try:
            import slabiq_expert
            _SORTES["d"] = {k: v for k, v in (slabiq_expert.lire().get("sortes") or {}).items() if v in NOTE}
        except Exception:
            pass
        _SORTES["t"] = time.time()
    return _SORTES["d"]


JOUEUR_RECRUE_INCONNUE = 68    # « un rookie que SlabIQ ne connait pas encore = B » (il se corrige des qu'on a ses ventes)


_APPRIS = {"t": 0.0, "d": {}}


def cotes_apprises():
    """17 nov 2026 (Mathieu : « l'algo doit trouver un moyen de valider sa cote et, s'il n'est pas sur, m'ecrire ») : les cotes
    donnees par l'expert en repondant aux questions de SlabIQ (slabiq_expert), relues au plus toutes les 30 s."""
    if time.time() - _APPRIS["t"] > 30:
        try:
            import slabiq_expert
            _APPRIS["d"] = {str(k).lower(): v for k, v in (slabiq_expert.lire().get("cotes") or {}).items() if v in NOTE}
        except Exception:
            pass
        _APPRIS["t"] = time.time()
    return _APPRIS["d"]


_AUTO = {"t": 0.0, "d": {}}


def cotes_auto():
    """17 nov 2026 : les cotes corrigees par la boucle de validation (validation_iq) : le marche les contredit de 2 crans et
    plus, de facon stable, avec assez de ventes ; jamais une cote de l'expert."""
    if time.time() - _AUTO["t"] > 30:
        try:
            import slabiq_expert
            _AUTO["d"] = {str(k).lower(): v for k, v in (slabiq_expert.lire().get("cotes_auto") or {}).items() if v in NOTE}
        except Exception:
            pass
        _AUTO["t"] = time.time()
    return _AUTO["d"]


def note_joueur(nom, criteres=None, recrue=False, jeune=False):
    """(note 0-100, lettre, source) : la cote de COLLECTION du joueur : l'expert, sinon la demande et la notoriete ;
    un inconnu vaut C, une recrue inconnue (sa carte recrue) vaut B."""
    l = JOUEURS_EXPERT.get(nom or "") or next((v for k, v in JOUEURS_EXPERT.items() if k.lower() == str(nom or "").lower()), None)
    if not l:
        l = _alias_expert(nom)
    if l:
        return float(NOTE[l]), l, "expert"
    la = cotes_apprises().get(str(nom or "").lower())
    if la:
        return float(NOTE[la]), la, "expert"
    lm = cotes_auto().get(str(nom or "").lower())
    if lm:
        return float(NOTE[lm]), lm, "marche"
    c = criteres or {}
    if c.get("demande") is None and c.get("notoriete") is None:
        lg = _legende(nom)
        if lg:
            return float(NOTE[lg]), lg, "legende"
        if recrue and len(str(nom or "").split()) >= 2:          # une recrue NOMMEE (prenom + nom), pas un titre sans joueur
            return float(JOUEUR_RECRUE_INCONNUE), "B", "recrue_inconnue"
        return float(JOUEUR_INCONNU), "E", "inconnu"
    # 17 nov 2026 (Gridin, Lekkerimaki : 2e et 3e annees notes D) : un jeune joueur a encore peu de ventes de cartes ; son
    # potentiel se lit aussi dans sa notoriete et les recherches (buzz)
    w = ([(0.5, c.get("demande")), (0.3, c.get("notoriete")), (0.2, c.get("buzz"))] if jeune
         else [(0.7, c.get("demande")), (0.3, c.get("notoriete"))])
    w = [(p, float(v)) for p, v in w if v is not None]
    x = sum(p * v for p, v in w) / sum(p for p, _ in w)
    n = _APPUIS[0][1] if x <= _APPUIS[0][0] else None
    for (a, na), (b, nb) in zip(_APPUIS, _APPUIS[1:]):
        if n is None and a <= x <= b:
            n = na + (nb - na) * (x - a) / (b - a) if b > a else nb
    n = round(n if n is not None else _APPUIS[-1][1], 1)
    # 17 nov 2026 (Gridin, 2e annee, note D : ses cartes ont encore peu de ventes) : une recrue recente ne descend jamais sous B
    # (comme une recrue inconnue) ; la demande de ses cartes la remonte quand elle arrive
    if recrue and n < JOUEUR_RECRUE_INCONNUE:
        return float(JOUEUR_RECRUE_INCONNUE), "B", "recrue_inconnue"     # une recrue pas encore connue du public
    return n, lettre_joueur(n), "ventes"


def _alias_expert(nom):
    """17 nov 2026 (audit : « Alexander Ovechkin » ne trouvait pas « Alex Ovechkin » : sa YG BGS 9.5 notee 46) : meme nom de
    famille et un prenom qui commence comme l'autre (Alex / Alexander, Mitch / Mitchell, Matt / Matthew)."""
    m = str(nom or "").lower().replace(".", "").split()
    if len(m) < 2:
        return None
    for k, v in JOUEURS_EXPERT.items():
        e = k.lower().replace(".", "").split()
        if len(e) >= 2 and e[-1] == m[-1] and (e[0].startswith(m[0][:4]) or m[0].startswith(e[0][:4])) and min(len(e[0]), len(m[0])) >= 3:
            return v
    import difflib                                     # « Connor Bednard » : le meme prenom, le nom a une lettre pres
    for k, v in JOUEURS_EXPERT.items():
        e = k.lower().replace(".", "").split()
        if len(e) >= 2 and e[0] == m[0] and len(m[-1]) >= 5 and difflib.SequenceMatcher(None, e[-1], m[-1]).ratio() >= 0.86:
            return v
    return None


# 17 nov 2026 (audit : Ken Dryden, Theoren Fleury, Ray Bourque notes E parce qu'ils ne jouent plus : absents de l'indice des
# joueurs actifs) : les legendes retraitees, utilisees seulement quand SlabIQ n'a aucune donnee sur le joueur
LEGENDES = {"Bobby Orr": "A+", "Gordie Howe": "A", "Maurice Richard": "A", "Jean Beliveau": "A-", "Joe Sakic": "A-",
            "Steve Yzerman": "A-", "Peter Forsberg": "A-", "Mark Messier": "A-", "Martin Brodeur": "A-", "Ken Dryden": "A-",
            "Ray Bourque": "B+", "Nicklas Lidstrom": "B+", "Teemu Selanne": "B+", "Pavel Bure": "B+", "Brett Hull": "B+",
            "Bobby Hull": "B+", "Dominik Hasek": "B+", "Eric Lindros": "B+", "Phil Esposito": "B+", "Jarome Iginla": "B+",
            "Paul Kariya": "B+", "Mike Bossy": "B+", "Guy Lafleur": "A", "Henrik Lundqvist": "B+", "Henrik Zetterberg": "B",
            "Mike Modano": "B", "Joe Thornton": "B", "Theoren Fleury": "B", "Mats Sundin": "B", "Doug Gilmour": "B",
            "Mario Lemieux": "A+", "Wayne Gretzky": "A+", "Patrick Roy": "A+", "Jaromir Jagr": "A", "Pavel Datsyuk": "A-",
            "Tony Esposito": "B", "Bryan Trottier": "B", "Denis Potvin": "B", "Grant Fuhr": "B", "Jari Kurri": "B", "Paul Coffey": "B"}


def _legende(nom):
    n = str(nom or "").lower()
    return next((v for k, v in LEGENDES.items() if k.lower() == n), None)


def lettre_joueur(n):
    for s, l in ((92, "A+"), (85, "A"), (80, "A-"), (73, "B+"), (66, "B"), (62, "B-"), (58, "C+"), (50, "C"), (35, "D")):
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


# 17 nov 2026 (Mathieu : « revoir comment presenter les cartes, il y a une chier de sortes » ; « tous les Young Guns paralleles
# sont mega recherches ») : la liste des cartes recherchees montre les FAMILLES du bareme (la meme lettre que SlabIQ donne),
# pas 40 sortes apprises une a une. (cle, lettre affichee, nom FR, nom EN, [(exemple FR, exemple EN, lettre)])
FAMILLES_VUE = [
    ("yg", "A+", "Young Guns et leurs parallèles", "Young Guns & parallels",
     [("Young Guns gradée 10", "Graded 10 Young Guns", "A+"), ("Exclusives, High Gloss", "Exclusives, High Gloss", "A+"),
      ("Outburst, Outburst Gold, Red…", "Outburst, Outburst Gold, Red…", "A+"), ("Clear Cut, Acetate", "Clear Cut, Acetate", "A+"),
      ("Canvas, Deluxe, Silver Foil, French", "Canvas, Deluxe, Silver Foil, French", "A+"), ("Photo Variation, SSP", "Photo Variation, SSP", "A+"),
      ("Young Guns raw", "Raw Young Guns", "A")]),
    ("rpa", "A+", "Les grosses recrues autographes", "Top rookie autographs",
     [("The Cup RPA", "The Cup RPA", "A+"), ("Premier Auto Patch", "Premier Auto Patch", "A+"), ("Future Watch Auto", "Future Watch Auto", "A+")]),
    ("rc_auto", "A", "Recrues autographes et vintage", "Rookie autos & vintage rookies",
     [("Ultimate, SP Game Used, SPx, Trilogy", "Ultimate, SP Game Used, SPx, Trilogy", "A"),
      ("Ice Premieres, OPC Platinum, Black Diamond (auto)", "Ice Premieres, OPC Platinum, Black Diamond (auto)", "A"),
      ("Recrue d’avant 1990 (A+ en 10)", "Pre-1990 rookie (A+ in a 10)", "A")]),
    ("inserts_a", "A", "Les inserts vedettes", "Star inserts", [("Clear Cut, Manga, Color Blast", "Clear Cut, Manga, Color Blast", "A")]),
    ("num", "A- à B", "Les numérotées", "Numbered cards",
     [("/10 et moins", "/10 or less", "A-"), ("/50 et moins", "/50 or less", "B+"), ("/199 et moins", "/199 or less", "B")]),
    ("sp", "B+ à B", "Les courtes impressions", "Short prints",
     [("SSP, variation de recrue", "SSP, rookie variation", "B+"), ("SP, variation", "SP, variation", "B")]),
    ("inserts", "B+ à B", "Les autres inserts", "Other inserts",
     [("Fluorescence", "Fluorescence", "B+"), ("Auto, Patch, Dazzlers", "Auto, Patch, Dazzlers", "B"),
      ("Retro Young Guns d’un vétéran", "Veteran Retro Young Guns", "B")]),
    ("eviter", "D à E", "À éviter", "Skip these",
     [("Bases, lots, checklists", "Base cards, lots, checklists", "D"), ("Young Guns Renewed", "Young Guns Renewed", "E")]),
]


def familles():
    return [{"cle": k, "lettre": l, "nom": n, "nom_en": ne, "ex": [{"nom": a, "nom_en": b, "lettre": c} for a, b, c in ex]}
            for k, l, n, ne, ex in FAMILLES_VUE]



def doute(nom, criteres=None, jeune=False):
    """17 nov 2026 : SlabIQ doute de sa cote quand ses signaux ne s'entendent pas -> (lettre proposee, raison FR, raison EN), sinon
    None. Les cotes de l'expert (ecrites ou apprises) ne sont jamais en doute."""
    n, l, src = note_joueur(nom, criteres, jeune=jeune)
    if src != "ventes":
        return None
    c = criteres or {}
    de, no, bz, fo = (float(c.get(k)) if c.get(k) is not None else None for k in ("demande", "notoriete", "buzz", "forme"))
    if jeune and NOTE.get(l, 0) < NOTE["B"] and max(no or 0, de or 0) >= 55:
        return l, "Jeune joueur : ses cartes ont encore peu de ventes, sa vraie cote est peut-être plus haute", "Young player: few card sales yet, his real rating may be higher"
    if no is not None and de is not None and no - de >= 35:
        return l, "Très connu, mais ses cartes se vendent peu", "Well known, but his cards sell little"
    if no is not None and de is not None and de - no >= 40:
        return l, "Ses cartes se vendent bien, mais il est peu connu", "His cards sell well, but he is little known"
    if bz is not None and bz >= 90 and NOTE.get(l, 0) <= NOTE["C"] and max(no or 0, de or 0) >= 50:
        return l, "Beaucoup de recherches en ce moment pour une cote basse", "Lots of searches right now for a low rating"
    if fo is not None and fo >= 90 and NOTE.get(l, 0) <= NOTE["C"]:
        return l, "Il joue très bien, mais sa cote est basse", "He is playing very well, but his rating is low"
    return None
