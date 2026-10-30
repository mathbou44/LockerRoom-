"""
LOCKERROOM - sports (23 oct 2026, Mathieu : "il va falloir commencer a
elargir pour d'autres sports comme NFL, basket ... pour SlabCoach").

Choix de Mathieu : l'app DEVINE le sport de chaque carte (titre, equipe,
produit) et prend le « sport principal » des Reglages quand elle hesite -
zero geste de plus. Breaks : les equipes de la ligue du produit.

Ajouter un sport = ajouter une entree a SPORTS (rien d'autre a toucher).
Calculs purs : aucune base, aucun reseau.
"""
import re
import unicodedata


def _n(t):
    return "".join(c for c in unicodedata.normalize("NFKD", str(t or "")) if not unicodedata.combining(c)).lower().strip()


# code -> (nom complet, division). Noms en anglais (comme sur les cartes et eBay).
_LNH = {
    "ANA": ("Anaheim Ducks", "Pacifique"), "BOS": ("Boston Bruins", "Atlantique"),
    "BUF": ("Buffalo Sabres", "Atlantique"), "CGY": ("Calgary Flames", "Pacifique"),
    "CAR": ("Carolina Hurricanes", "Métropolitaine"), "CHI": ("Chicago Blackhawks", "Centrale"),
    "COL": ("Colorado Avalanche", "Centrale"), "CBJ": ("Columbus Blue Jackets", "Métropolitaine"),
    "DAL": ("Dallas Stars", "Centrale"), "DET": ("Detroit Red Wings", "Atlantique"),
    "EDM": ("Edmonton Oilers", "Pacifique"), "FLA": ("Florida Panthers", "Atlantique"),
    "LAK": ("Los Angeles Kings", "Pacifique"), "MIN": ("Minnesota Wild", "Centrale"),
    "MTL": ("Montreal Canadiens", "Atlantique"), "NSH": ("Nashville Predators", "Centrale"),
    "NJD": ("New Jersey Devils", "Métropolitaine"), "NYI": ("New York Islanders", "Métropolitaine"),
    "NYR": ("New York Rangers", "Métropolitaine"), "OTT": ("Ottawa Senators", "Atlantique"),
    "PHI": ("Philadelphia Flyers", "Métropolitaine"), "PIT": ("Pittsburgh Penguins", "Métropolitaine"),
    "SJS": ("San Jose Sharks", "Pacifique"), "SEA": ("Seattle Kraken", "Pacifique"),
    "STL": ("St. Louis Blues", "Centrale"), "TBL": ("Tampa Bay Lightning", "Atlantique"),
    "TOR": ("Toronto Maple Leafs", "Atlantique"), "UTA": ("Utah Mammoth", "Centrale"),
    "VAN": ("Vancouver Canucks", "Pacifique"), "VGK": ("Vegas Golden Knights", "Pacifique"),
    "WSH": ("Washington Capitals", "Métropolitaine"), "WPG": ("Winnipeg Jets", "Centrale"),
}
_NFL = {
    "BUF": ("Buffalo Bills", "AFC Est"), "MIA": ("Miami Dolphins", "AFC Est"),
    "NE": ("New England Patriots", "AFC Est"), "NYJ": ("New York Jets", "AFC Est"),
    "BAL": ("Baltimore Ravens", "AFC Nord"), "CIN": ("Cincinnati Bengals", "AFC Nord"),
    "CLE": ("Cleveland Browns", "AFC Nord"), "PIT": ("Pittsburgh Steelers", "AFC Nord"),
    "HOU": ("Houston Texans", "AFC Sud"), "IND": ("Indianapolis Colts", "AFC Sud"),
    "JAX": ("Jacksonville Jaguars", "AFC Sud"), "TEN": ("Tennessee Titans", "AFC Sud"),
    "DEN": ("Denver Broncos", "AFC Ouest"), "KC": ("Kansas City Chiefs", "AFC Ouest"),
    "LV": ("Las Vegas Raiders", "AFC Ouest"), "LAC": ("Los Angeles Chargers", "AFC Ouest"),
    "DAL": ("Dallas Cowboys", "NFC Est"), "NYG": ("New York Giants", "NFC Est"),
    "PHI": ("Philadelphia Eagles", "NFC Est"), "WAS": ("Washington Commanders", "NFC Est"),
    "CHI": ("Chicago Bears", "NFC Nord"), "DET": ("Detroit Lions", "NFC Nord"),
    "GB": ("Green Bay Packers", "NFC Nord"), "MIN": ("Minnesota Vikings", "NFC Nord"),
    "ATL": ("Atlanta Falcons", "NFC Sud"), "CAR": ("Carolina Panthers", "NFC Sud"),
    "NO": ("New Orleans Saints", "NFC Sud"), "TB": ("Tampa Bay Buccaneers", "NFC Sud"),
    "ARI": ("Arizona Cardinals", "NFC Ouest"), "LAR": ("Los Angeles Rams", "NFC Ouest"),
    "SF": ("San Francisco 49ers", "NFC Ouest"), "SEA": ("Seattle Seahawks", "NFC Ouest"),
}
_NBA = {
    "BOS": ("Boston Celtics", "Atlantique"), "BKN": ("Brooklyn Nets", "Atlantique"),
    "NYK": ("New York Knicks", "Atlantique"), "PHI": ("Philadelphia 76ers", "Atlantique"),
    "TOR": ("Toronto Raptors", "Atlantique"),
    "CHI": ("Chicago Bulls", "Centrale"), "CLE": ("Cleveland Cavaliers", "Centrale"),
    "DET": ("Detroit Pistons", "Centrale"), "IND": ("Indiana Pacers", "Centrale"),
    "MIL": ("Milwaukee Bucks", "Centrale"),
    "ATL": ("Atlanta Hawks", "Sud-Est"), "CHA": ("Charlotte Hornets", "Sud-Est"),
    "MIA": ("Miami Heat", "Sud-Est"), "ORL": ("Orlando Magic", "Sud-Est"),
    "WAS": ("Washington Wizards", "Sud-Est"),
    "DEN": ("Denver Nuggets", "Nord-Ouest"), "MIN": ("Minnesota Timberwolves", "Nord-Ouest"),
    "OKC": ("Oklahoma City Thunder", "Nord-Ouest"), "POR": ("Portland Trail Blazers", "Nord-Ouest"),
    "UTA": ("Utah Jazz", "Nord-Ouest"),
    "GSW": ("Golden State Warriors", "Pacifique"), "LAC": ("Los Angeles Clippers", "Pacifique"),
    "LAL": ("Los Angeles Lakers", "Pacifique"), "PHX": ("Phoenix Suns", "Pacifique"),
    "SAC": ("Sacramento Kings", "Pacifique"),
    "DAL": ("Dallas Mavericks", "Sud-Ouest"), "HOU": ("Houston Rockets", "Sud-Ouest"),
    "MEM": ("Memphis Grizzlies", "Sud-Ouest"), "NOP": ("New Orleans Pelicans", "Sud-Ouest"),
    "SAS": ("San Antonio Spurs", "Sud-Ouest"),
}
_MLB = {
    "BAL": ("Baltimore Orioles", "AL Est"), "BOS": ("Boston Red Sox", "AL Est"),
    "NYY": ("New York Yankees", "AL Est"), "TB": ("Tampa Bay Rays", "AL Est"),
    "TOR": ("Toronto Blue Jays", "AL Est"),
    "CWS": ("Chicago White Sox", "AL Centrale"), "CLE": ("Cleveland Guardians", "AL Centrale"),
    "DET": ("Detroit Tigers", "AL Centrale"), "KC": ("Kansas City Royals", "AL Centrale"),
    "MIN": ("Minnesota Twins", "AL Centrale"),
    "HOU": ("Houston Astros", "AL Ouest"), "LAA": ("Los Angeles Angels", "AL Ouest"),
    "ATH": ("Athletics", "AL Ouest"), "SEA": ("Seattle Mariners", "AL Ouest"),
    "TEX": ("Texas Rangers", "AL Ouest"),
    "ATL": ("Atlanta Braves", "NL Est"), "MIA": ("Miami Marlins", "NL Est"),
    "NYM": ("New York Mets", "NL Est"), "PHI": ("Philadelphia Phillies", "NL Est"),
    "WSH": ("Washington Nationals", "NL Est"),
    "CHC": ("Chicago Cubs", "NL Centrale"), "CIN": ("Cincinnati Reds", "NL Centrale"),
    "MIL": ("Milwaukee Brewers", "NL Centrale"), "PIT": ("Pittsburgh Pirates", "NL Centrale"),
    "STL": ("St. Louis Cardinals", "NL Centrale"),
    "ARI": ("Arizona Diamondbacks", "NL Ouest"), "COL": ("Colorado Rockies", "NL Ouest"),
    "LAD": ("Los Angeles Dodgers", "NL Ouest"), "SD": ("San Diego Padres", "NL Ouest"),
    "SF": ("San Francisco Giants", "NL Ouest"),
}

# mots qui designent le sport sans equipe (produits, ligues). Poids : 3 = sur, 1 = indice.
SPORTS = {
    "hockey": {"nom": "Hockey", "ligue": "NHL", "ebay_sport": "Ice Hockey", "equipes": _LNH,
               "mots": {3: ["hockey", "nhl", "young guns", "the cup", "o-pee-chee", "opc", "ice premieres",
                            "future watch", "upper deck series", "ud series", "black diamond", "artifacts",
                            "parkhurst", "synergy", "mvp hockey", "allure", "trilogy", "credentials",
                            "ultimate collection", "sp game used", "chl", "ahl"],
                        1: ["upper deck", "canvas", "rookie redemption"]},
               "alias": {"utah hockey club": "UTA", "mammoth": "UTA", "arizona coyotes": "UTA", "coyotes": "UTA", "ny rangers": "NYR", "ny islanders": "NYI",
                         "st louis blues": "STL", "montreal canadiens": "MTL", "habs": "MTL"}},
    "football": {"nom": "Football", "ligue": "NFL", "ebay_sport": "Football", "equipes": _NFL,
                 "mots": {3: ["nfl", "football", "contenders", "rated rookie", "rookie ticket", "absolute football",
                              "score football"],
                          1: ["prizm", "mosaic", "select", "donruss", "national treasures", "flawless", "phoenix"]},
                 "alias": {"niners": "SF", "pats": "NE", "bucs": "TB", "washington football team": "WAS"}},
    "basketball": {"nom": "Basketball", "ligue": "NBA", "ebay_sport": "Basketball", "equipes": _NBA,
                   "mots": {3: ["nba", "basketball", "hoops", "wnba", "court kings", "revolution basketball"],
                            1: ["prizm", "mosaic", "select", "optic", "national treasures", "flawless", "immaculate"]},
                   "alias": {"sixers": "PHI", "blazers": "POR", "cavs": "CLE", "mavs": "DAL", "wolves": "MIN",
                             "la clippers": "LAC"}},
    "baseball": {"nom": "Baseball", "ligue": "MLB", "ebay_sport": "Baseball", "equipes": _MLB,
                 "mots": {3: ["mlb", "baseball", "bowman", "1st bowman", "topps heritage", "allen & ginter",
                              "allen ginter", "topps update", "stadium club", "topps series 1", "topps series 2",
                              "topps chrome update", "gypsy queen", "topps archives"],
                          1: ["topps", "topps chrome", "topps now"]},
                 "alias": {"oakland athletics": "ATH", "a's": "ATH", "sacramento athletics": "ATH", "yanks": "NYY",
                           "jays": "TOR", "dbacks": "ARI", "d-backs": "ARI", "sox": None}},
    # 31 oct 2026 (Mathieu : « tu detectes aussi les cartes de F1 ? il y en a des fois chez Savage ») : Topps Chrome F1,
    # Turbo Attax, Paddock Pass, Topps Now F1... Les ecuries ne servent qu'aux mots exacts (alias) : « Williams » ou
    # « Martin » tout seuls sont aussi des noms de joueurs (Caleb Williams) et ne doivent pas faire un pilote de F1.
    "f1": {"nom": "F1", "ligue": "Formula 1", "ebay_sport": "Auto Racing", "index_manuel": True,
           "equipes": {"MCL": ("McLaren", "F1"), "FER": ("Ferrari", "F1"), "RBR": ("Red Bull Racing", "F1"),
                       "MER": ("Mercedes", "F1"), "AST": ("Aston Martin", "F1"), "ALP": ("Alpine", "F1"),
                       "WIL": ("Williams", "F1"), "RB": ("Racing Bulls", "F1"), "HAS": ("Haas", "F1"),
                       "AUD": ("Audi", "F1"), "CAD": ("Cadillac", "F1")},
           "mots": {6: ["formula 1", "formula one", "f1", "grand prix", "turbo attax", "paddock pass", "topps chrome f1",
                        "topps f1", "formula 1 racing", "f1 racing", "dynasty f1", "eccellenza", "scuderia ferrari",
                        "red bull racing", "mclaren f1", "mercedes amg", "aston martin aramco", "haas f1", "williams racing",
                        "kick sauber", "racing bulls", "visa cash app",
                        # les pilotes (nom complet quand le nom de famille existe ailleurs : Hamilton, Norris, Perez, Alonso)
                        "verstappen", "leclerc", "piastri", "lando norris", "lewis hamilton", "george russell", "carlos sainz",
                        "fernando alonso", "sergio perez", "checo perez", "gasly", "esteban ocon", "alex albon", "alexander albon",
                        "lance stroll", "hulkenberg", "bottas", "tsunoda", "antonelli", "oliver bearman", "colapinto", "hadjar",
                        "bortoleto", "liam lawson", "ricciardo", "vettel", "raikkonen", "ayrton senna", "michael schumacher",
                        "mick schumacher", "niki lauda", "zhou guanyu", "guanyu zhou", "logan sargeant"]},
           "alias": {"mclaren": "MCL", "scuderia ferrari": "FER", "ferrari": "FER", "red bull racing": "RBR", "oracle red bull": "RBR",
                     "mercedes amg": "MER", "mercedes": "MER", "aston martin": "AST", "alpine f1": "ALP", "bwt alpine": "ALP",
                     "williams racing": "WIL", "racing bulls": "RB", "visa cash app": "RB", "alphatauri": "RB", "haas f1": "HAS",
                     "haas": "HAS", "kick sauber": "AUD", "sauber": "AUD", "audi f1": "AUD", "cadillac f1": "CAD"}},
}
DEFAUT = "hockey"


def liste():
    """[{code, nom, ligue}] pour l'ecran Reglages."""
    return [{"code": k, "nom": v["nom"], "ligue": v["ligue"]} for k, v in SPORTS.items()]


def valide(sport):
    return sport if sport in SPORTS else DEFAUT


# -- index des equipes ---------------------------------------------------------------------
_INDEX = {}       # sport -> {texte normalise: code}
_UNIQUES = {}     # texte normalise -> sport, pour les noms qui n'existent que dans UNE ligue
for _s, _d in SPORTS.items():
    idx = {}
    villes = {}
    if _d.get("index_manuel"):                  # F1 : seulement les codes et les alias exacts
        for code in _d["equipes"]:
            idx[_n(code)] = code
        for a, code in _d.get("alias", {}).items():
            idx[_n(a)] = code
        _INDEX[_s] = idx
        continue
    for code, (nom, _div) in _d["equipes"].items():
        mots = nom.split()
        idx[_n(code)] = code
        idx[_n(nom)] = code
        # surnom : 2 mots si le 1er n'est pas une ville connue (« Maple Leafs », « Red Sox »)
        for k in (1, 2):
            if len(mots) > k:
                idx.setdefault(_n(" ".join(mots[-k:])), code)
        ville = _n(" ".join(mots[:-1]))
        villes.setdefault(ville, []).append(code)
    for ville, codes in villes.items():
        if ville and len(codes) == 1:       # « Montreal », « Toronto » ; pas « New York », « Los Angeles »
            idx.setdefault(ville, codes[0])
    for a, code in _d.get("alias", {}).items():
        if code:
            idx[_n(a)] = code
    _INDEX[_s] = idx
_compte = {}
for _s, idx in _INDEX.items():
    for cle in idx:
        if len(cle) > 3:
            _compte.setdefault(cle, set()).add(_s)
_VILLES = {_n(" ".join(nom.split()[:-1])) for d in SPORTS.values() for nom, _ in d["equipes"].values()}
for cle, ss in _compte.items():
    # une ville seule n'identifie pas le sport (« Toronto » = Leafs, Raptors ou Blue Jays)
    if len(ss) == 1 and cle not in _VILLES:
        _UNIQUES[cle] = next(iter(ss))


def equipes(sport=None):
    return SPORTS[valide(sport)]["equipes"]


def code_equipe(texte, sport=None):
    """« Montréal Canadiens », « MTL », « Canadiens » -> « MTL » (dans la ligue du sport) ; inconnu -> le texte."""
    idx = _INDEX[valide(sport)]
    t = _n(texte)
    if not t:
        return ""
    if t in idx:
        return idx[t]
    for cle, code in sorted(idx.items(), key=lambda kv: -len(kv[0])):
        if len(cle) > 3 and re.search(rf"(?<![a-z0-9]){re.escape(cle)}(?![a-z0-9])", t):
            return code
    return str(texte).strip()


def nom_equipe(code, sport=None):
    return equipes(sport).get(code, (code, ""))[0]


def division(code, sport=None):
    return equipes(sport).get(code, ("", "Autre"))[1] or "Autre"


def _mot_present(mot, t):
    return re.search(rf"(?<![a-z0-9]){re.escape(_n(mot))}(?![a-z0-9])", t) is not None


# un seul motif pour tous les mots (rapide : l'inventaire entier en quelques ms)
_POIDS_MOT = {}                     # mot normalise -> [(sport, poids)]
for _s, _d in SPORTS.items():
    for _p, _mots in _d["mots"].items():
        for _m in _mots:
            _POIDS_MOT.setdefault(_n(_m), []).append((_s, _p))
for _cle, _s in _UNIQUES.items():
    _POIDS_MOT.setdefault(_cle, []).append((_s, 3))
_MOTIF = re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(m) for m in sorted(_POIDS_MOT, key=len, reverse=True)) + r")(?![a-z0-9])")


def scores(*textes):
    """{sport: score} d'apres les mots du titre, de l'equipe, du produit."""
    t = " ".join(_n(x) for x in textes if x)
    out = {s: 0 for s in SPORTS}
    for m in set(_MOTIF.findall(t)):
        for s, p in _POIDS_MOT[m]:
            out[s] += p
    return out


# 31 oct 2026 (Mathieu : une « 2026 Bowman Chrome U Auto 1st Cam Cook » classee baseball : « c'est du foot ») : Bowman U /
# Bowman University = les universites americaines (football, et basketball quand le titre le dit) ; jamais le baseball
_RE_UNIV = re.compile(r"\bbowman (chrome |best |sterling )?(u|university)\b|\bbowman u (chrome|best)\b|\bncaa\b|\bcollege (football|basketball)\b"
                      r"|\b(running back|quarterback|wide receiver|tight end|linebacker|heisman)\b")
_RE_UNIV_BASKET = re.compile(r"\b(basketball|hoops|ncaab|march madness|college basketball)\b")


def detecter(*textes, defaut=None, bonus=None):
    """Sport le plus probable ; `defaut` (sport principal) quand rien ne tranche.
    `bonus` = {sport: points} (ex. joueur connu de la base de valeurs hockey)."""
    t = " ".join(_n(x) for x in textes if x)
    if _RE_UNIV.search(t):
        return "basketball" if _RE_UNIV_BASKET.search(t) else "football"
    sc = scores(*textes)
    for k, v in (bonus or {}).items():
        if k in sc:
            sc[k] += v
    meilleur = max(sc.values())
    gagnants = [s for s, v in sc.items() if v == meilleur]
    if meilleur >= 2 and len(gagnants) == 1:
        return gagnants[0]
    if defaut in gagnants and meilleur > 0:
        return defaut
    return valide(defaut)


def aspects_ebay(sport):
    """Champs eBay de la categorie 261328 (Sport, League)."""
    d = SPORTS[valide(sport)]
    return {"Sport": d["ebay_sport"], "League": d["ligue"]}
