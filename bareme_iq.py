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
  B  : les autos de base de produits moyens ; patch / jersey sans auto
  C  : Dazzlers (18 nov) ; D : Fluorescence, Young Guns Renewed (18 nov ; numerotee = la regle des numerotees, 25 nov :
       Renewed Exclusives /100 B, Renewed High Gloss /10 A-)
  Courtes impressions (18 nov) : SSP / 16-Bit A- ; SP B+ ; gradee 10 : A+
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
# 18 nov 2026 (Mathieu : « les SSP au moins A-, gradees PSA 10 tres tres recherchees, comme la 16-Bit » ; la liste des inserts
# aussi durs a sortir, cotes officielles Upper Deck 2025-26 : Beckett, Breakninja, Cardboard Connection, Checklist Insider) :
# ils comptent comme des SSP (A- bruts, A+ en PSA 10)
# 18 nov 2026 (nuit, 325 000 ventes du blitz) : chaque insert garde ici a ete MESURE (prix / prix median du meme joueur) :
# SSP x2,3 · 16-Bit x5,6 · Dazzlers Gold x2,7 · Sign of the Times Rookies x2,6 · Pro Visions x2,4 · case hit x2,0 · Dark Matter
# x1,4 · Authentic Moments x1,4. RETIRES (le marche ne les paie pas) : HoloGrFX x0,16, Front Row Talent x0,23, Swagnificent
# x0,49, Fanimation x0,64, Standing On Their Head x0,76, Day With The Cup x0,96, Impressions x0,98, Canvas noir et blanc x1,1,
# Snow Spray x1,2. Les autres (Bootleg, Holotypes, Incarnations...) : trop peu de ventes pour juger, gardes d'apres leurs cotes.
SSP = _R(r"\bssp\b|\bsuper short print\b|\bcase hit\b|\b16[ -]?bit\b"
         r"|\bdazzlers (?:blue )?gold\b|\bcelebration variations?\b|\bbootleg\b|\bholotypes?\b|\bwhite house visit\b|\bincarnations?\b"
         r"|\brookie debut game jersey\b|\bstar view\b|\bkiller keepers\b|\btile variations?\b|\bsign of the times rookies\b"
         r"|\bauthentic moments\b|\bsheer dominance\b|\bpro visions\b|\b3-?d marquee rookies\b|\bplatinum portraits?\b|\bbrush off\b|\bdark matter\b"
         # 26 nov 2026 (Mathieu, McDavid Electric Soul #ES-8 notee C : « c'est une SSP, c'est ecrit dans les comps mais on devrait le
         # savoir, c'est pas une note de C ») : l'insert de la Serie 1 2026-27 (1:2 880 paquets). MESURE comme les autres sur nos
         # ventes : 14 ventes, x6,4 le prix median du meme joueur (McDavid 349 a 448 $), 9 titres sur 14 disent SSP ou case hit.
         r"|\belectric soul\b")
SP_PRODUIT = _R(r"\b(?:\d{4}(?:-\d{2,4})?|upper deck|ud)\s+sp\b(?!\s*(?:short|ssp))|\bsp\s+hockey\b")
SP_ = _R(r"\bsp\b(?! ?(?:authentic|game|signature|legendary|premier|x\b))|\bshort print\b|\bvariations?\b|\bphoto var\b|\bimage var")
CANVAS = _R(r"\bcanvas\b")
ICE_PREM = _R(r"\bice\b.*\bpremieres?\b|\bpremieres?\b.*\bice\b")
OPC_PLAT = _R(r"\bo-pee-chee platinum\b|\bopc platinum\b|\bplatinum\b")
BD_GEMS = _R(r"\bblack diamond\b")
INSERTS_A = _R(r"\bclear ?cut\b|\bmanga\b|\bcolou?r ?blast\b")
FLUO = _R(r"\bfluorescence\b")
DAZZ = _R(r"\bdazzlers?\b")


# 18 nov 2026 (Mathieu : « SPx, Trilogy, SP Game Used sont moins recherches que SP Authentic, The Cup, Premier, Stature, Ice ;
# entre les deux, Black Diamond ; Splendor et Tableau sont au top avec The Cup ») : les recrues autographes par produit
RC_AUTO_TOP = _R(r"\bsplendor\b|\btableau\b|\bthe cup\b")                       # A+
RC_AUTO_A = _R(r"\bultimate\b|\bsp authentic\b|\bpremier\b|\bstature\b|\bice\b")    # A
RC_AUTO_MOY = _R(r"\bsp game used\b|\bspgu\b|\bspx\b|\btrilogy\b")                 # B+ (A- avec une patch)


def _annee(t):
    """L'annee de la saison (1979-80 -> 1979), sinon None."""
    m = re.search(r"\b(19[5-9]\d|20[0-3]\d)\b", t or "")
    return int(m.group(1)) if m else None


def _gem(g):
    n = str((g or {}).get("note") or "")
    return n in ("10", "9.5") or n.startswith("10")


def renewed(brut, serie, base="D"):
    """La sorte d'une Young Guns Renewed. 18 nov 2026 (Mathieu, apres la mesure) : la Renewed de base = D.
    25 nov 2026 (Mathieu, Makar Renewed Exclusives /100 notee C : « Renewed Exclusives est une carte B ») : nos ventes de hockey
    (export du 23 nov, sans les gradees) : Renewed de base 2,86 $ en mediane (6 820 ventes), Renewed Exclusives /100 51,57 $ (299),
    Renewed High Gloss /10 212 $ (52). Une Renewed NUMEROTEE suit donc la regle des numerotees (/100 -> B, /10 -> A-) ; les mots
    « Exclusives » et « High Gloss » disent le tirage quand le titre ne le dit pas."""
    s = int(serie) if serie else (10 if re.search(r"\bhigh gloss\b", brut) else 100 if re.search(r"\bexclusives?\b", brut) else None)
    if s:
        return ("A-" if s <= 10 else "B+" if s <= 50 else "B" if s <= 199 else "C", "yg_renewed_num")
    return (base, "yg_renewed")


def sorte(titre):
    """(lettre, raison) de la SORTE de carte, d'apres le titre (cartes_match le decode)."""
    import cartes_match
    d = cartes_match._decoder_memo(titre or "")
    t = " " + (d.get("texte") or str(titre or "").lower()) + " "
    auto, patch, serie, g = bool(d.get("auto")), bool(d.get("patch")), d.get("serie"), d.get("grade")
    rc = bool(d.get("rc")) or bool(re.search(r"\brookies?\b|\brc\b|\br/c\b|\(rc\)", t + " " + str(titre or "").lower()))
    c = []                                             # (lettre, raison) : on garde la meilleure
    # 22 nov 2026 (Mathieu, Schaefer / Gatcomb Young Guns #499 notee A+ : « plus B que A+, c'est une Young Guns duo ») : la carte
    # des Young Guns a DEUX recrues (le « checklist » de la serie) n'est la Young Guns d'aucun des deux : B, pas A+ (ni D)
    yg_duo = False
    if YG.search(t) and not re.search(r"\blots?\b|\breprint\b|\bcustom\b|\bu-? ?pick\b|\byou pick\b|\bpick (?:from|your|one)\b|\byou choose\b", t):
        try:
            yg_duo = bool(re.search(r"\bchecklist\b", t)) or bool(cartes_match.cible_titre(titre or "").get("autres_joueurs"))
        except Exception:
            yg_duo = bool(re.search(r"\bchecklist\b", t))
    if not yg_duo and (d.get("exclu") or re.search(r"\bchecklist\b|\blot\b|\breprint\b|\bcustom\b|\bu-? ?pick\b|\byou pick\b|\bpick (?:from|your|one)\b"
                                          r"|\b(?:complete|finish) your set\b|\byou choose\b|\bfrom list\b|\bpick list\b", t)):
        return ("D", "lot_checklist")                  # un lot, un checklist, une reimpression : jamais une bonne sorte
    yg = bool(YG.search(t)) and not yg_duo
    if yg_duo:
        c.append(("B", "yg_duo"))
    brut = " " + str(titre or "").lower() + " "
    # 21 nov 2026 (Mathieu : « POE = Program of Excellence et non Young Guns ; le prix est tres different ») : nos ventes :
    # Celebrini 69 $ (sa YG Canvas : 900 $ et plus), Schaefer 51 $, Bedard 43 $, Misa 13,50 $ ; les autres 3 $. Un insert Canvas,
    # au niveau du 1st Round Draft ; jamais une YG ni une variante de YG, meme si le titre dit « Young Guns »
    poe = bool(re.search(r"\bpoe\b|\bprogram(?:me)?s? of excellence\b", t + brut))
    if poe:
        yg = False
    # 17 nov 2026 (audit : « UD Series 1 Outburst #224 Sandis Vilmanis R/C » note D) : sans les mots « Young Guns », le numero
    # dit si c'est une YG (Series 1 : 201-250, Series 2 : 451-500, Extended : 701-750) quand c'est une recrue Upper Deck
    # 18 nov 2026 (Mathieu : « Bedard 1st Round Draft a 12 $ note A+ : c'est plus un B+ ») : l'insert 1st Round Draft d'Extended
    # porte un numero dans la plage des YG (#740) ; ce n'est PAS une YG (nos ventes : Bedard 27 $ contre 254 $ pour sa YG)
    frd = bool(re.search(r"\b(?:1st|first) round draft\b|\bfrd\b", brut))
    if not yg and not yg_duo and not frd and rc and re.search(r"\bupper deck\b|\bud\b", brut) and not re.search(r"\bsp\b|\bice\b|\bartifacts\b|\bcup\b|\bpremier\b|\bmvp\b|\bo-pee-chee\b|\bopc\b|\bcanvas\b|\bchronology\b|\bsynergy\b|\btrilogy\b|\bultimate\b|\bclear cut\b|\bblack diamond\b|\bcredentials\b|\ballure\b|\bstature\b|\bmetal\b|\bengrained\b|\btim hortons\b|\bpremieres\b|\bauto", brut):
        mn = re.search(r"#\s*(\d{3})\b", brut)
        no = int(mn.group(1)) if mn else None
        if no and ((re.search(r"\bseries (?:1|one|i)\b", brut) and 201 <= no <= 250) or (re.search(r"\bseries (?:2|two|ii)\b", brut) and 451 <= no <= 500)
                   or (re.search(r"\bextended\b", brut) and 701 <= no <= 750)):
            yg = True
    # 16 nov 2026 (Mathieu : « les Young Guns Renewed ne valent presque rien ; seulement McDavid, Crosby, Ovechkin passent
    # 10 $ » ; verifie sur nos ventes : McDavid 15 $, Crosby 13,50 $, Ovechkin 12,60 $, les autres 2 a 6 $, la masse 1,90 $)
    if yg and re.search(r"\brenewed\b", brut):
        return renewed(brut, serie)
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
    if rc and (auto or patch) and RC_AUTO_TOP.search(t):
        c.append(("A+", "rc_auto_top"))               # Splendor, Tableau, The Cup : le haut du hobby
    if rc and auto and RC_AUTO_MOY.search(t):
        vraie_patch = bool(re.search(r"\bpatch\b|\bjersey\b|\brelic\b|\bswatch\b|\bmaterials?\b|\btag\b", brut))   # « Game Used » = le nom du produit
        c.append(("A-" if vraie_patch else "B+", "rc_auto_moyen"))
    elif rc and auto and (patch or RC_AUTO_A.search(t)):
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
        c.append(("A", "bd_gems"))                    # 18 nov (Mathieu, apres la mesure : se vend comme une A+ ; A- -> A)
    if INSERTS_A.search(t):
        c.append(("A", "insert_a"))
    if poe and not auto and not serie:
        return ("B-", "poe")                          # teste aussi a C : accord 80,0 % (B- : 80,2 %) ; on garde B-
    if frd and not yg:
        c.append(("B", "frd"))                        # joueur A+ (Bedard) -> B+ ; joueur moyen -> C
    if FLUO.search(t):
        c.append(("D", "fluorescence"))               # 18 nov (Mathieu : « ca vaut pas grand-chose » ; mesure E ; B+ -> D)
    if auto:
        c.append(("B+", "auto"))                      # 20 nov 2026 (nuit, teste sur ventes jamais vues) : B -> B+ ; le marche dit A-
                                                      # (10 187 ventes) ; accord 0,797 -> 0,803, A/E 9,6x -> 10,7x, Radar Pro egal
    if patch:
        c.append(("B", "patch"))
    if DAZZ.search(t):
        c.append(("C", "dazzlers"))                   # 18 nov (Mathieu ; mesure D, x0,5 ; B -> C)
    if serie:
        s = int(serie)
        c.append(("A-" if s <= 10 else "B+" if s <= 50 else "B" if s <= 199 else "C", "numerotee"))
    # 20 nov 2026 (Mathieu : « les OPC Platinum Marquee Rookie numerotees sont tres recherchees et collectionnees, surtout avec Lane
    # Hutson ») : mesure sur nos 648 000 ventes de hockey (prix / prix median du meme joueur) : OPC Platinum recrue /1-10 x5,2 ·
    # /11-50 x1,8 · /51-99 x1,1 · /100-199 x0,77 · /200-299 x0,52, contre x2,4 · x1,2 · x0,64 · x0,33 pour les autres recrues
    # numerotees : une tranche plus haut a tirage egal. Teste avant/apres (ventes jamais vues) : accord 80,2 -> 79,9 %, Radar Pro
    # inchange (71 %) ; garde sur decision de Mathieu (« go »)
    if serie and rc and OPC_PLAT.search(t) and not auto:
        s = int(serie)
        c.append(("A+" if s <= 10 else "A-" if s <= 50 else "B+" if s <= 199 else "B", "opc_plat_num"))   # Mathieu : « les OPC Platinum numerotees sont toutes des cartes B a A+ »
    if yg and serie:
        c.append(("A+", "yg_variante"))               # une YG numerotee est une variante
    # 18 nov 2026 (Mathieu : « les SSP sont au moins A-, les SP B+ ; gradees PSA 10, elles sont tres tres recherchees,
    # comme la 16-Bit ») : SSP A-, SP B+, et une SSP / SP gradee 10 : A+
    if not serie and SSP.search(brut):
        c.append(("A+" if _gem(g) else "A-", "ssp10" if _gem(g) else "ssp"))
    # « SP » = short print ici, jamais le PRODUIT (SP Authentic, SP Game Used, SPx, et « 2025-26 SP » / « Upper Deck SP Hockey »)
    elif not serie and SP_.search(SP_PRODUIT.sub(" ", brut)):
        c.append(("A+" if _gem(g) else "B+", "sp10" if _gem(g) else "sp"))
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
COTE_MARCHE_N = 20           # ventes en 90 jours pour que la cote marche decide


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


_AUDIT = {"t": 0.0, "d": {}}


def cotes_audit():
    """18 nov 2026 : les plafonds de l'audit Pro (audit_pro) : un joueur dont les annonces Pro sont souvent a 3x leurs comps."""
    if time.time() - _AUDIT["t"] > 30:
        try:
            import slabiq_expert
            _AUDIT["d"] = {str(k).lower(): v for k, v in (slabiq_expert.lire().get("cotes_audit") or {}).items() if v in NOTE}
        except Exception:
            _AUDIT["d"] = {}
        _AUDIT["t"] = time.time()
    return _AUDIT["d"]


def note_joueur(nom, criteres=None, recrue=False, jeune=False):
    """La cote du joueur (_note_joueur0), corrigee par l'audit Pro (jamais un joueur cote par l'expert)."""
    r = _note_joueur0(nom, criteres, recrue=recrue, jeune=jeune)
    if r[2] != "expert":
        # 18 nov 2026 : l'audit Pro corrige d'un cran, dans un sens ou dans l'autre (annonces surpayees, prix final des encans)
        cap = cotes_audit().get(str(nom or "").lower())
        if cap and cap != r[1]:
            return float(NOTE[cap]), cap, "marche"
    return r


def _note_joueur0(nom, criteres=None, recrue=False, jeune=False):
    """(note 0-100, lettre, source) : la cote de COLLECTION du joueur : l'expert, sinon la demande et la notoriete ;
    un inconnu vaut C, une recrue inconnue (sa carte recrue) vaut B."""
    # 18 nov 2026 (Mathieu : « quand je reponds aux questions, ca doit s'appliquer directement dans l'app ») : sa reponse dans
    # « SlabIQ demande » passe avant la liste de depart de l'expert (meme pour Crosby ou McDavid)
    la = cotes_apprises().get(str(nom or "").lower())
    if la:
        return float(NOTE[la]), la, "expert"
    l = JOUEURS_EXPERT.get(nom or "") or next((v for k, v in JOUEURS_EXPERT.items() if k.lower() == str(nom or "").lower()), None)
    if not l:
        l = _alias_expert(nom)
    if l:
        return float(NOTE[l]), l, "expert"
    # 17 nov 2026 (Mathieu : « la moyenne de vente d'un joueur sur 3 mois et le nombre de fois qu'il a ete transige : avec ca
    # on fait varier les cotes de maniere solide, chaque semaine ») : la cote MARCHE (cote_marche) passe avant les signaux
    try:
        import cote_marche
        cm = cote_marche.joueur(nom)
        if cm and cm.get("lettre") in NOTE and (cm.get("n") or 0) >= COTE_MARCHE_N:
            return float(NOTE[cm["lettre"]]), cm["lettre"], "marche"
    except Exception:
        pass
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
     [("Splendor, Tableau, The Cup", "Splendor, Tableau, The Cup", "A+"),
      ("SP Authentic, Premier, Stature, Ice, Ultimate", "SP Authentic, Premier, Stature, Ice, Ultimate", "A"),
      ("OPC Platinum (auto)", "OPC Platinum (auto)", "A"),
      ("Black Diamond (auto)", "Black Diamond (auto)", "A"),
      ("SPx, Trilogy, SP Game Used", "SPx, Trilogy, SP Game Used", "B+"),
      ("Recrue d’avant 1990 (A+ en 10)", "Pre-1990 rookie (A+ in a 10)", "A")]),
    ("inserts_a", "A", "Les inserts vedettes", "Star inserts", [("Clear Cut, Manga, Color Blast", "Clear Cut, Manga, Color Blast", "A")]),
    ("num", "A- à B", "Les numérotées", "Numbered cards",
     [("/10 et moins", "/10 or less", "A-"), ("/50 et moins", "/50 or less", "B+"), ("/199 et moins", "/199 or less", "B")]),
    ("sp", "A+ à B+", "Les courtes impressions", "Short prints",
     [("SSP ou SP gradée PSA 10", "SSP or SP graded PSA 10", "A+"), ("SSP, 16-Bit, case hit", "SSP, 16-Bit, case hit", "A-"),
      ("SP, variation", "SP, variation", "B+")]),
    # 21 nov 2026 (Mathieu : « pas tout a fait vrai, ca ») : « Auto, Patch : B » sous « autres inserts » : un auto n'est pas un
    # insert, et le bareme lui donne B+ depuis le 20 nov (B pour une patch sans auto). La vue dit maintenant ce que le bareme fait.
    ("inserts", "B+ à C", "Autos, patchs et autres inserts", "Autos, patches & other inserts",
     [("Auto (hors recrue)", "Auto (non-rookie)", "B+"), ("Patch ou jersey, sans auto", "Patch or jersey, no auto", "B"),
      ("Retro Young Guns d’un vétéran", "Veteran Retro Young Guns", "B"),
      ("Young Guns Renewed Exclusives /100", "Young Guns Renewed Exclusives /100", "B"),
      ("Dazzlers", "Dazzlers", "C")]),
    ("eviter", "D", "À éviter", "Skip these",
     [("Bases, lots, checklists", "Base cards, lots, checklists", "D"), ("Young Guns Renewed, Fluorescence", "Young Guns Renewed, Fluorescence", "D")]),
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
