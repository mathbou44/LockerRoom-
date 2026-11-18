"""
SLABCOACH - le bareme SlabIQ du BASEBALL (18 nov 2026, apercu admin).

Mathieu : « renseigne-toi le max possible sur tous les sites et forums sur le baseball (tips, trends) ; le baseball a une tres
tres vieille histoire avec les cartes, beaucoup de choses a savoir, surtout le vintage ; tu dois tout connaitre. Je n'en connais
pas beaucoup : je vais etre le parfait testeur. »

Meme logique que le hockey (bareme_iq) : la SORTE de carte x la cote de COLLECTION du joueur ; le plus faible domine.
Les regles viennent de sources verifiees (Topps « Ripped » pour la definition d'une recrue, Cardboard Connection pour les
parallels Chrome, Beckett pour les Golden Mirror, Old Sports Cards / Pre-War Cards pour le vintage, All Vintage Cards pour la
« junk wax »). Les lettres des joueurs sont le consensus du hobby ; la cote marche (ventes SoldComps du baseball) les corrigera.

LA SORTE :
  A+ : 1st Bowman Chrome AUTO ; une SuperFractor 1/1 ; une Red /5 ; une recrue vintage d'un membre du Temple (1979 et avant) ;
       les grandes cartes d'avant-guerre (T206, Goudey 1933, Cracker Jack, Play Ball 1939...) d'une vedette
  A  : 1st Bowman Chrome ; Topps Chrome RC auto ; une carte vintage (1948-1979) d'une vedette du Temple ; une PSA 10 d'une recrue
       Topps Chrome ; les erreurs celebres de la « junk wax » (Frank Thomas sans nom, Billy Ripken...)
  A- : Golden Mirror / variation photo SSP ; Topps Chrome RC (base) ; une refractor numerotee /50 et moins
  B+ : recrue Topps flagship (Series 1, 2, Update) ; 1st Bowman papier ; refractor /99 a /199 ; Heritage SP
  B  : une auto ou une relique d'un produit moyen ; une refractor non numerotee
  C  : Topps Now (imprimee sur commande : pas rare) ; Panini sans licence MLB (pas de logos) ; une base moderne
  D  : une base 1986-1994 (« junk wax », imprimee a des millions) ; un lot, un checklist
"""
import re

NOTE = {"A+": 95, "A": 88, "A-": 82, "B+": 76, "B": 68, "B-": 64, "C+": 61, "C": 55, "D": 40, "E": 25}
JOUEUR_INCONNU = 45

_R = lambda m: re.compile(m, re.I)

# La cote de COLLECTION des joueurs de baseball (consensus du hobby, novembre 2026). A garder court : la cote marche fait le reste.
JOUEURS_BB = {
    # les legendes : le vintage
    "Mickey Mantle": "A+", "Babe Ruth": "A+", "Lou Gehrig": "A+", "Honus Wagner": "A+", "Ty Cobb": "A+",
    "Jackie Robinson": "A+", "Hank Aaron": "A+", "Willie Mays": "A+", "Roberto Clemente": "A+", "Sandy Koufax": "A+",
    "Ted Williams": "A+", "Joe DiMaggio": "A+", "Shoeless Joe Jackson": "A+", "Cy Young": "A", "Walter Johnson": "A",
    "Christy Mathewson": "A", "Stan Musial": "A", "Nolan Ryan": "A", "Pete Rose": "A", "Johnny Bench": "A-",
    "Reggie Jackson": "A-", "Yogi Berra": "A-", "Ernie Banks": "A-", "Bob Gibson": "A-", "Tom Seaver": "A-",
    "Roy Campanella": "A-", "Duke Snider": "A-", "Whitey Ford": "B+", "Eddie Mathews": "A-", "Satchel Paige": "A",
    "Josh Gibson": "A", "Mike Schmidt": "A-", "George Brett": "A-", "Rickey Henderson": "A-", "Cal Ripken Jr.": "A-",
    "Ken Griffey Jr.": "A", "Derek Jeter": "A", "Tony Gwynn": "B+", "Frank Thomas": "B+", "Chipper Jones": "B+",
    "Ichiro Suzuki": "A-", "Albert Pujols": "B+", "Mariano Rivera": "B+",
    # l'integration (1947-1952) : les anciens des Negro Leagues entres dans la MLB (Temple de la renommee)
    "Larry Doby": "B+", "Monte Irvin": "B", "Minnie Minoso": "B", "Don Newcombe": "B",
    # les recrues cles des annees 60 (Cardboard Connection) et les Japonais (cartes BBM)
    "Carl Yastrzemski": "B+", "Willie McCovey": "B+", "Lou Brock": "B", "Rod Carew": "B", "Willie Stargell": "B",
    "Hideki Matsui": "B", "Hideo Nomo": "B",
    # les recrues des annees 70 (Cardboard Connection)
    "Robin Yount": "B+", "Ozzie Smith": "B+", "Thurman Munson": "B+", "Eddie Murray": "B", "Paul Molitor": "B",
    "Dennis Eckersley": "B", "Carlton Fisk": "B", "Dave Winfield": "B",
    # les vedettes d'aujourd'hui
    "Shohei Ohtani": "A+", "Aaron Judge": "A+", "Mike Trout": "A", "Paul Skenes": "A", "Juan Soto": "A-",
    "Ronald Acuna Jr.": "A-", "Bobby Witt Jr.": "A-", "Elly De La Cruz": "A-", "Gunnar Henderson": "A-",
    "Julio Rodriguez": "B+", "Jackson Holliday": "B+", "Roki Sasaki": "A-", "Mookie Betts": "B+", "Fernando Tatis Jr.": "B+",
    "Corbin Carroll": "B+", "Bryce Harper": "B+", "Jackson Chourio": "B+", "Wyatt Langford": "B", "James Wood": "B+",
    "Jackson Merrill": "B+", "Freddie Freeman": "B", "Yoshinobu Yamamoto": "B+", "Vladimir Guerrero Jr.": "B+",
}
_ALIAS = {"ken griffey jr": "Ken Griffey Jr.", "cal ripken": "Cal Ripken Jr.", "ronald acuna": "Ronald Acuna Jr.",
          "ronald acuña": "Ronald Acuna Jr.", "julio rodríguez": "Julio Rodriguez", "bobby witt": "Bobby Witt Jr.", "ohtani": "Shohei Ohtani", "mantle": "Mickey Mantle",
          "clemente": "Roberto Clemente", "koufax": "Sandy Koufax", "gehrig": "Lou Gehrig", "dimaggio": "Joe DiMaggio",
          "skenes": "Paul Skenes", "griffey": "Ken Griffey Jr.",
          "yastrzemski": "Carl Yastrzemski", "yaz": "Carl Yastrzemski",
          "fernando tatis": "Fernando Tatis Jr.", "vladimir guerrero jr": "Vladimir Guerrero Jr.", "joe jackson": "Shoeless Joe Jackson"}

# Les vedettes du Temple (Hall of Fame) dont une carte vintage compte toujours (meme en mauvais etat)
TEMPLE = {k for k, v in JOUEURS_BB.items() if v in ("A+", "A", "A-")} - {
    "Shohei Ohtani", "Aaron Judge", "Mike Trout", "Paul Skenes", "Juan Soto", "Ronald Acuna Jr.", "Bobby Witt Jr.",
    "Elly De La Cruz", "Gunnar Henderson", "Roki Sasaki", "Pete Rose", "Ken Griffey Jr.", "Derek Jeter", "Ichiro Suzuki"} | {
    "Ken Griffey Jr.", "Derek Jeter", "Ichiro Suzuki"}

AVANT_GUERRE = _R(r"\bt20[56]\b|\bt205\b|\bgoudey\b|\bcracker jack\b|\bplay ball\b|\bold judge\b|\bn172\b|\be90\b|\be121\b|\be120\b"
                  r"|\bm101\b|\bsporting news\b|\bdiamond stars\b|\bbaltimore news\b|\bt3\b|\bmayo\b|\bramly\b")
PREMIER_BOWMAN = _R(r"\b1st bowman\b|\bfirst bowman\b|\b1st\b.*\bbowman\b|\bbowman\b.*\b1st\b|\bbdc-?\d|\bbcp-?\d|\bcpa-?[a-z]")
BOWMAN_CHROME = _R(r"\bbowman chrome\b|\bbowman draft chrome\b|\bchrome prospects?\b|\bbowman.*\bchrome\b")
TOPPS_CHROME = _R(r"\btopps chrome\b|\bchrome update\b")
FLAGSHIP = _R(r"\btopps\b(?!.*\b(?:chrome|now|heritage|finest|stadium club|allen|ginter|gypsy|archives|tribute|dynasty|"
              r"transcendent|museum|definitive|tier one|inception|sterling|five star|luminaries|gold label|pristine|bowman)\b)")
SUPERFRACTOR = _R(r"\bsuperfractor\b|\bsuper ?fractor\b")
GOLDEN_MIRROR = _R(r"\bgolden mirror\b|\bimage variations?\b|\bphoto variations?\b|\bssp\b|\bsuper short print\b|\bsp variation\b")
TOPPS_NOW = _R(r"\btopps now\b")
PANINI = _R(r"\bpanini\b|\bdonruss\b(?!.*\b19[89]\d\b)|\bprizm\b|\bdiamond kings\b|\bchronicles\b|\bstars (?:&|and) stripes\b")
HERITAGE = _R(r"\bheritage\b")
REFRACTOR = _R(r"\brefractor\b|\bfractor\b|\bx-?fractor\b|\batomic\b|\bwave\b|\bsapphire\b|\bspeckle\b|\bmojo\b")
RC = _R(r"\brookie\b|\brc\b|\br/c\b|\(rc\)")
AUTO = _R(r"\bauto\b|\bautograph(?:ed|s)?\b|\bsigned\b|\bon[- ]card\b|\bsignature\b")
RELIQUE = _R(r"\brelic\b|\bjersey\b|\bpatch\b|\bgame[- ]used\b|\bmemorabilia\b")
ERREURS_CELEBRES = _R(r"\bno name\b|\bnnof\b|\bfrank thomas\b.*\b(?:error|no name)\b|\bf(?:\*|u)ck face\b|\bff\b.*\bripken\b|\bripken\b.*\bff\b"
                      r"|\bbilly ripken\b.*\berror\b|\btiffany\b|\bdesert shield\b|\bcopper\b.*\b1990\b")
LOT = _R(r"\blot\b|\bchecklist\b|\breprint\b|\bcustom\b|\bu-? ?pick\b|\byou pick\b|\bcomplete (?:your )?set\b|\bfactory set\b|\bbulk\b")
ANNEE = _R(r"\b(18[89]\d|19\d\d|20[0-3]\d)\b")
SERIE = _R(r"(?:#|/|\bto\b ?)\s?(\d{1,4})\b(?! ?(?:rc|card))")
NUMEROTEE = _R(r"/\s?(\d{1,4})\b|\b\d{1,4}\s?/\s?(\d{1,4})\b")
GEM = _R(r"\b(?:psa|sgc|bgs|cgc)\s?(?:gem )?(?:mint )?(10|9\.5)\b")


# 18 nov 2026 : les recrues ICONIQUES (Sports Illustrated, Cardboard Connection) : la carte porte le joueur, quelle que soit l'epoque
ICONES = [
    (_R(r"\b1951\b.*\bbowman\b.*\bmantle\b|\bmantle\b.*\b1951\b.*\bbowman\b"), "A+"),
    (_R(r"\b1948\b.*\bleaf\b.*\b(?:robinson|paige)\b"), "A+"),
    (_R(r"\b1963\b.*\btopps\b.*\brose\b"), "A+"),
    (_R(r"\b1973\b.*\b(?:o-pee-chee|opc|topps)\b.*\bschmidt\b"), "A"),
    (_R(r"\b1980\b.*\btopps\b.*\b(?:rickey )?henderson\b"), "A+"),
    (_R(r"\b1984\b.*\bfleer update\b.*\b(?:clemens|puckett|gooden)\b|\b(?:clemens|puckett|gooden)\b.*\b1984\b.*\bfleer update\b"), "A"),
    (_R(r"\b1982\b.*\btopps traded\b.*\bripken\b"), "A-"),
    (_R(r"\b1983\b.*\btopps\b.*\bgwynn\b"), "A-"),
    (_R(r"\b1989\b.*\bupper deck\b.*\bgriffey\b"), "A-"),
    (_R(r"\b1993\b.*\bsp\b.*\bjeter\b"), "A+"),
    (_R(r"\b2001\b.*\bbowman chrome\b.*\bpujols\b.*\bauto"), "A+"),
    (_R(r"\b2001\b.*\btopps traded\b.*\b(?:pujols|ichiro)\b"), "A"),
    (_R(r"\b2009\b.*\bbowman\b.*\btrout\b"), "A+"),
    (_R(r"\b2011\b.*\btopps update\b.*\btrout\b|\bus175\b"), "A+"),
    (_R(r"\b2013\b.*\bbowman\b.*\bjudge\b"), "A+"),
    (_R(r"\b2018\b.*\bbowman chrome\b.*\bohtani\b"), "A+"),
    # 18 nov (nuit) : la vraie 1re carte pro d'Ohtani : 2013 BBM 1st Version « Red Wing » (829 gradees PSA ; une PSA 10 vendue
    # 11 200 $, Sports Illustrated) ; les recrues 1955 Topps Koufax #123, Killebrew #124, Clemente #164
    (_R(r"\b2013\b.*\bbbm\b.*\bohtani\b|\bohtani\b.*\b2013\b.*\bbbm\b"), "A+"),
    (_R(r"\b2013\b.*\bcalbee\b.*\bohtani\b|\bohtani\b.*\b2013\b.*\bcalbee\b"), "A"),
    (_R(r"\b1955\b.*\btopps\b.*\b(?:koufax|clemente|killebrew)\b"), "A+"),
    # 18 nov : la 1re refractor de l'histoire (1993 Finest, ~241 copies de chacune, jamais confirme par Topps ; Baseball Cardpedia)
    (_R(r"\b1993\b.*\bfinest\b.*\brefractor\b|\b1993\b.*\brefractor\b.*\bfinest\b"), "A"),
    # 18 nov (2e passe) : Bowman 1948-1955 (Topps Ripped, All Vintage Cards) : la Ted Williams 1954 #66 retiree des paquets
    # (dispute de contrat avec Topps) ; les Mantle 1952 #101, 1953 couleur #59, 1955 #202 ; Mays 1952 #218 ; Aaron 1955 #179
    (_R(r"\b1954\b.*\bbowman\b.*\bwilliams\b|\bwilliams\b.*\b1954\b.*\bbowman\b"), "A+"),
    (_R(r"\b195[235]\b.*\bbowman\b.*\bmantle\b|\bmantle\b.*\b195[235]\b.*\bbowman\b"), "A"),
    (_R(r"\b1952\b.*\bbowman\b.*\bmays\b|\b1955\b.*\bbowman\b.*\b(?:mays|aaron)\b"), "A"),
    # l'integration (Old Sports Cards) : la 1952 Topps #312 Robinson est sa carte la plus chere ; 1949 Bowman Robinson #50 et
    # Paige #224 (sa seule autre carte d'epoque) ; Doby 1948 Leaf #138 (1re carte du 1er joueur noir de la Ligue americaine)
    (_R(r"\b1952\b.*\btopps\b.*\brobinson\b|\brobinson\b.*\b1952\b.*\btopps\b"), "A+"),
    (_R(r"\b1949\b.*\bbowman\b.*\b(?:robinson|paige)\b|\b(?:robinson|paige)\b.*\b1949\b.*\bbowman\b"), "A"),
    (_R(r"\b1948\b.*\bleaf\b.*\bdoby\b|\bdoby\b.*\b1948\b.*\bleaf\b"), "A"),
    # 18 nov (4e passe) : les 10 recrues des annees 60 (Cardboard Connection) ; plusieurs sont des cartes a 2-4 recrues :
    # 1968 #177 Ryan/Koosman, 1968 #247 Bench/Tompkins, 1967 #581 Seaver/Denehy, 1967 #569 Carew/Allen, 1963 #553 Stargell
    (_R(r"\b1968\b.*\btopps\b.*\b(?:ryan|koosman)\b|\b(?:ryan|koosman)\b.*\b1968\b.*\btopps\b"), "A+"),
    (_R(r"\b1968\b.*\btopps\b.*\bbench\b|\bbench\b.*\b1968\b.*\btopps\b"), "A+"),
    (_R(r"\b1967\b.*\btopps\b.*\bseaver\b|\bseaver\b.*\b1967\b.*\btopps\b"), "A+"),
    (_R(r"\b1969\b.*\btopps\b.*\b(?:reggie )?jackson\b.*(?:#\s?260|\brc\b|\brookie\b)|\b1969\b.*\btopps\b.*#\s?260\b"), "A+"),
    (_R(r"\b1960\b.*\btopps\b.*\b(?:yastrzemski|mccovey)\b|\b1962\b.*\btopps\b.*\bbrock\b"
        r"|\b1967\b.*\btopps\b.*\bcarew\b|\b1963\b.*\btopps\b.*\bstargell\b"), "A-"),
    # les Japonais (Cardboard Connection, Topps Ripped) : la vraie 1re carte d'Ichiro est la 1993 BBM #239 (beaucoup de
    # contrefacons) ; la 1994 Calbee Hokkaido (vendue quelques semaines) ; la 1995 UD Collector's Choice Japan (100-200 copies) ;
    # Matsui 1993 BBM #423
    (_R(r"\b1993\b.*\bbbm\b.*\b(?:ichiro|suzuki)\b|\b(?:ichiro|suzuki)\b.*\b1993\b.*\bbbm\b"), "A+"),
    (_R(r"\b1994\b.*\bcalbee\b.*\b(?:ichiro|suzuki)\b.*\bhokkaido\b|\b1994\b.*\bcalbee\b.*\bhokkaido\b.*\b(?:ichiro|suzuki)\b"), "A"),
    (_R(r"\b1995\b.*\bcollector'?s choice\b.*\bjapan\b.*\b(?:ichiro|suzuki)\b|\b(?:ichiro|suzuki)\b.*\b1995\b.*\bcollector'?s choice\b.*\bjapan\b"), "A"),
    (_R(r"\b1993\b.*\bbbm\b.*\bmatsui\b|\bmatsui\b.*\b1993\b.*\bbbm\b"), "A-"),
    # 18 nov (5e passe) : les recrues des annees 70 (Cardboard Connection, prix PSA 8) : Brett 1975 #228, Yount 1975 #223,
    # Ozzie Smith 1979 #116, Munson 1970 #189 ; puis Blyleven 1971 #26, Garvey 1971 #341, Fisk 1972 #79, Winfield 1974 #456,
    # Eckersley 1976 #98, Murray 1978 #36, Molitor/Trammell 1978 #707, Rice 1975 #616, Carter 1975 #620, Baker/Baylor 1971 #709
    (_R(r"\b1975\b.*\btopps\b.*\b(?:brett|yount)\b|\b1979\b.*\btopps\b.*\bozzie\b|\b1970\b.*\btopps\b.*\bmunson\b"), "A"),
    (_R(r"\b1971\b.*\btopps\b.*\b(?:blyleven|garvey|baylor|dusty baker)\b|\b1972\b.*\btopps\b.*\bfisk\b|\b1974\b.*\btopps\b.*\bwinfield\b"
        r"|\b1976\b.*\btopps\b.*\beckersley\b|\b1978\b.*\btopps\b.*\b(?:eddie murray|molitor|trammell)\b|\b1975\b.*\btopps\b.*\b(?:jim rice|gary carter)\b"), "A-"),
    # les inserts legendaires des annees 90 (Sports Illustrated) : 1998 Metal Universe Precious Metal Gems (baseball : 50 copies
    # au plus), 1997 Flair Showcase Masterpieces (les 1res 1/1 en paquets) ; 1998 Donruss Crusade (Red /25, Purple /100,
    # Green /250) ; 1991 Donruss Elite (1re insert numerotee, /10 000) ; 1997 Metal Universe Mother Lode (1:288, Baseball Cardpedia)
    (_R(r"\bprecious metal gems?\b|\bpmg\b"), "A+"),
    (_R(r"\bflair\b.*\bmasterpieces?\b"), "A+"),
    (_R(r"\bmother lode\b"), "A-"),
    (_R(r"\b199[78]\b.*\bcrusade\b"), "B+"),
    (_R(r"\b199[1-3]\b.*\bdonruss\b.*\belite\b"), "B+"),
]
# Topps Heritage (Cardlines 2022) : les variations RARES (Throwback 1:22 487, Error 1:9 506, Nickname 1:4 753, couleur de l'icone
# 1:3 961) ; la variation photo (« Image », 1:64) et le changement de couleur du nom (1:382) sont bien plus courants
HERITAGE_RARE = _R(r"\bthrowback\b|\berror\b|\bnickname\b|\bicon\b.*\bcolor\b|\bcolor swap\b.*\bicon\b")
HERITAGE_COURANTE = _R(r"\bimage variation\b|\bphoto variation\b|\bvariation\b|\bname color\b|\bcolor swap\b")
# Les « high numbers » vintage : la derniere serie, imprimee en plus petit nombre (1952 Topps #311-407, 1955 Bowman #225-320,
# 1973 Topps : la Schmidt #615)
HIGH_VINTAGE = _R(r"\bhigh (?:number|#|series)\b|\bhi(?:gh)?[- ]#\b")
# Le vintage O-Pee-Chee (Canada) : imprime en bien plus petit nombre que Topps (la Schmidt 1973 : 299 OPC gradees contre 19 468
# Topps, Sports Illustrated) ; un cran de plus que la meme Topps
OPC = _R(r"\bo-?pee-?chee\b|\bopc\b")


def _annee(t):
    m = ANNEE.findall(t or "")
    return min(int(a) for a in m) if m else None


def _tirage(t):
    t = re.sub(r"\b50\s?/\s?50\b", " ", t or "")          # la saison 50/50 d'Ohtani n'est pas un tirage
    m = NUMEROTEE.search(t)
    if not m:
        return None
    try:
        return int(m.group(2) or m.group(1))
    except (TypeError, ValueError):
        return None


def _high_connu(t, an):
    """Les series « high numbers » connues, d'apres le numero de la carte."""
    m = re.search(r"#\s?(\d{1,3})\b", t)
    if not m:
        return False
    n = int(m.group(1))
    return ((an == 1952 and "topps" in t and 311 <= n <= 407) or (an == 1955 and "bowman" in t and 225 <= n <= 320)
            or (an == 1973 and "topps" in t and 529 <= n <= 660))


def sorte(titre):
    """(lettre, raison) de la SORTE d'une carte de baseball, d'apres le titre."""
    t = " " + str(titre or "").lower() + " "
    if LOT.search(t):
        return ("D", "lot_checklist")
    an, rc, auto, tir = _annee(t), bool(RC.search(t)), bool(AUTO.search(t)), _tirage(t)
    gem = bool(GEM.search(t))
    j = joueur_connu(titre)
    vedette = j in TEMPLE
    c = []
    for rx, l in ICONES:
        if rx.search(t):
            c.append(("A+" if gem else l, "icone"))
            break
    if SUPERFRACTOR.search(t) or tir == 1:
        c.append(("A+", "un_sur_un"))
    if tir and tir <= 5:
        c.append(("A+", "rouge_5"))
    # l'avant-guerre (avant 1946) : le plus vieux hobby ; une vedette = A+, le reste A (meme en mauvais etat)
    if an and an < 1946 and (AVANT_GUERRE.search(t) or an < 1940):
        c.append(("A+" if vedette else "A", "avant_guerre"))
    # le vintage d'apres-guerre (1946-1979) : la recrue d'une vedette du Temple est la carte reine
    if an and 1946 <= an <= 1979:
        opc = bool(OPC.search(t))
        if vedette and rc:
            c.append(("A+", "rc_vintage_temple"))
        elif vedette:
            c.append(("A+" if opc else "A", "vintage_temple"))
        elif HIGH_VINTAGE.search(t) or _high_connu(t, an):
            c.append(("B+" if rc or opc else "B", "vintage_high"))
        else:
            c.append((("B+" if rc else "B") if opc else ("B" if rc else "C+"), "vintage_opc" if opc else "vintage"))
    # la « junk wax » (1986-1994) : imprimee a des millions ; seules les erreurs celebres et les Tiffany comptent
    if an and 1986 <= an <= 1994:
        if ERREURS_CELEBRES.search(t):
            c.append(("A", "erreur_celebre"))
        elif not (auto or tir or gem):
            c.append(("D", "junk_wax"))
    if PREMIER_BOWMAN.search(t) or ("bowman" in t and "prospect" in t and auto):
        if BOWMAN_CHROME.search(t) and auto:
            c.append(("A+", "1st_bowman_chrome_auto"))
        elif BOWMAN_CHROME.search(t):
            c.append(("A", "1st_bowman_chrome"))
        else:
            c.append(("B+", "1st_bowman"))
    if TOPPS_CHROME.search(t) and rc:
        c.append(("A" if auto else "A+" if gem else "A-", "topps_chrome_rc"))
    heritage = bool(HERITAGE.search(t))
    if heritage and HERITAGE_RARE.search(t):
        c.append(("A+" if gem else "A-", "heritage_rare"))
    elif heritage and HERITAGE_COURANTE.search(t) and not re.search(r"\bssp\b|\bsuper short print\b", t):
        c.append(("B+", "heritage_variation"))
    elif GOLDEN_MIRROR.search(t):
        c.append(("A+" if gem else "A-", "ssp"))
    if FLAGSHIP.search(t) and rc and not (an and an < 2000):
        c.append(("A-" if gem else "B+", "flagship_rc"))
    # Allen & Ginter (Cardboard Connection 2025) : la mini Wood 1/1 et les mini « No Number » /50 ; les mini autos encadrees
    if re.search(r"\bginter\b", t):
        if re.search(r"\bwood\b", t) and re.search(r"\bmini\b", t):
            c.append(("A+", "ginter_wood"))
        elif re.search(r"\bno number\b", t):
            c.append(("A-", "ginter_no_number"))
        elif re.search(r"\bframed\b", t) and auto:
            c.append(("A-" if tir and tir <= 25 else "B+", "ginter_framed_auto"))
    if HERITAGE.search(t) and re.search(r"\bsp\b|short print|\bhigh number\b", t):
        c.append(("B+", "heritage_sp"))
    if tir:
        c.append(("A-" if tir <= 50 else "B+" if tir <= 199 else "B", "numerotee"))
    if REFRACTOR.search(t) and not tir:
        c.append(("B", "refractor"))
    if auto:
        c.append(("B+" if rc else "B", "auto"))
    if RELIQUE.search(t):
        c.append(("B", "relique"))
    if TOPPS_NOW.search(t):
        c.append(("C", "topps_now"))                    # imprimee sur commande : le tirage suit la demande
    if PANINI.search(t) and not auto and not tir:
        c.append(("C", "panini_sans_licence"))          # pas de logos MLB : le hobby les paie moins
    if gem and rc:
        c.append(("A-", "rc_gem"))
    if not c:
        c.append(("C", "base"))
    # une base de la junk wax reste D meme si une autre regle faible s'applique
    if any(r == "junk_wax" for _, r in c) and not any(r in ("erreur_celebre", "un_sur_un", "numerotee", "auto", "icone") for _, r in c):
        return ("D", "junk_wax")
    if any(r == "topps_now" for _, r in c) and not any(NOTE[l] >= NOTE["A-"] for l, _ in c):
        return ("C", "topps_now")
    return max(c, key=lambda x: NOTE[x[0]])


def _n(s):
    import unicodedata
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower().replace(".", "").strip()


_NOMS = sorted(((_n(k), k) for k in JOUEURS_BB), key=lambda x: -len(x[0]))


def joueur_connu(titre):
    t = " " + _n(titre) + " "
    for a, k in sorted(((_n(a), k) for a, k in _ALIAS.items()), key=lambda x: -len(x[0])):
        if " " + a + " " in t or " " + a in t:
            return k
    for n, k in _NOMS:
        if " " + n + " " in t or " " + n.replace(" jr", "") + " " in t:
            return k
    return None


def note_joueur(nom):
    """(note, lettre, source) du joueur : la liste du hobby, sinon la cote marche du baseball, sinon inconnu."""
    k = joueur_connu(nom or "") or nom
    if k in JOUEURS_BB:
        return NOTE[JOUEURS_BB[k]], JOUEURS_BB[k], "hobby"
    try:
        import cote_marche
        m = (cote_marche.lire_balayage().get("baseball") or {}).get(k) or {}
        if m.get("n", 0) >= 20:
            return 76.0, "B+", "marche"
        if m.get("n", 0) >= 8:
            return 61.0, "C+", "marche"
    except Exception:
        pass
    return float(JOUEUR_INCONNU), "D", "inconnu"


def lettre(n):
    for l in ("A+", "A", "A-", "B+", "B", "B-", "C+", "C", "D"):
        if n >= NOTE[l] - 3:
            return l
    return "E"


def score(titre, joueur=None):
    """La note SlabIQ d'une carte de baseball (apercu admin) : sorte x joueur, le plus faible domine (comme au hockey)."""
    so, so_r = sorte(titre)
    nom = joueur or joueur_connu(titre)
    try:
        if not nom:
            import mlb
            j = mlb.joueur_du_titre(titre)
            nom = (j or {}).get("nom")
    except Exception:
        pass
    nj, lj, src = note_joueur(nom) if nom else (float(JOUEUR_INCONNU), "D", "inconnu")
    ns = NOTE[so]
    # une carte d'avant-guerre ou une recrue vintage du Temple : la carte porte le joueur (pas de « plus faible domine »)
    if so_r in ("avant_guerre", "rc_vintage_temple", "vintage_temple", "un_sur_un", "erreur_celebre", "icone"):
        total = max(ns, nj)
    else:
        lo, hi = min(ns, nj), max(ns, nj)
        total = lo + 0.25 * (hi - lo)
    return {"score": int(round(total)), "lettre": lettre(total), "joueur": nom,
            "bareme": {"sorte": so, "sorte_raison": so_r, "joueur": lj, "joueur_note": round(nj, 1), "joueur_source": src}}
