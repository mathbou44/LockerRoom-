"""
SLABCOACH - ce que le hobby sait des cartes des annees 90 (11 nov 2026).

Mathieu : « le livre sur les cartes des annees 90 (hockey, baseball, basketball, football) : SlabIQ doit l'utiliser pour
apprendre ». Les grandes cartes et les grands inserts de la decennie, tires de la recherche du guide audio (Cardboard
Connection, PuckJunk, CLLCT, Sports Collectors Daily, SI Collectibles, Old Sports Cards, Bleacher Report) : chaque regle
reconnait un titre d'annonce et donne un niveau :
  - « graal »  : une carte mythique de la decennie (Precious Metal Gems, Essential Credentials, Jeter SP 1993...) ;
  - « chasse » : un insert ou une parallele tres recherche (Finest Refractor 1993, Beam Team Members Only, Desert Shield,
                 Game Jersey 1996-97, autographes Be A Player, Contenders Rookie Ticket 1998...) ;
  - « cle »    : une recrue cle d'un grand joueur (Brodeur Score 1990, Thornton Black Diamond, Emmitt Smith Supplemental...).
Le niveau sert de PLANCHER au score SlabIQ (jamais il ne le baisse) et donne la raison, dite au client.
Aucune donnee eBay ni prix : le savoir public du hobby.
"""
import re

PLANCHER = {"graal": 88, "chasse": 78, "cle": 68}

# (niveau, motif sur le titre en minuscules, raison FR, raison EN)
REGLES = [
    # tous sports : les inserts mythiques de la fin des annees 90
    ("graal", r"precious metal gems?|\bpmg\b", "Precious Metal Gems : l'insert le plus célèbre des années 90 (100 par joueur)",
     "Precious Metal Gems: the most famous 90s insert (100 per player)"),
    ("graal", r"essential credentials?|credentials (now|future)", "Essential Credentials : numérotée selon le numéro de la carte",
     "Essential Credentials: numbered to the card number"),
    ("graal", r"star rub(y|ies)", "Star Rubies : parallèle mythique de Skybox Premium", "Star Rubies: legendary Skybox Premium parallel"),
    # baseball
    ("graal", r"\b1993\b.*\bsp\b.*\bjeter\b|\bjeter\b.*\b1993\b.*\bsp\b", "Jeter SP 1993 : la recrue de baseball de la décennie (6 sur 1 000 en 10)",
     "1993 SP Jeter: the baseball rookie of the decade (6 in 1,000 gem)"),
    ("graal", r"\bthomas\b.*(no name|nnof)|(no name|nnof).*\bthomas\b", "Frank Thomas « No Name » 1990 : l'erreur célèbre",
     "1990 Frank Thomas No Name: the famous error"),
    ("chasse", r"\b1994\b.*\bsp\b.*(rodriguez|a-rod)|(rodriguez|a-rod).*\b1994\b.*\bsp\b", "A-Rod SP 1994 : feuille métallique, très rare en 10",
     "1994 SP A-Rod: foil, very rare in gem"),
    ("chasse", r"desert shield", "Desert Shield 1991 : distribuée aux soldats, environ 7 000 par joueur",
     "1991 Desert Shield: troop issue, about 7,000 per player"),
    ("cle", r"\b1992\b.*bowman.*rivera|rivera.*\b1992\b.*bowman", "Rivera Bowman 1992 : sa seule vraie recrue", "1992 Bowman Rivera: his only true rookie"),
    ("cle", r"\b1992\b.*fleer update.*piazza|piazza.*\b1992\b.*fleer update", "Piazza Fleer Update 1992 : recrue clé", "1992 Fleer Update Piazza: key rookie"),
    ("cle", r"\b1991\b.*bowman.*chipper|chipper.*\b1991\b.*bowman", "Chipper Jones Bowman 1991 : recrue clé", "1991 Bowman Chipper Jones: key rookie"),
    # basketball
    ("chasse", r"\b199[34]\b.*finest.*refractor.*(jordan|mourning|shaq|o'?neal|barkley)|(jordan|mourning).*\b199[34]\b.*finest.*refractor",
     "Finest Refractor 1993-94 : les premiers réfracteurs du basketball", "1993-94 Finest Refractor: basketball's first refractors"),
    ("chasse", r"beam team.*members only|members only.*beam team", "Beam Team Members Only : environ 10 000 ensembles",
     "Beam Team Members Only: about 10,000 sets"),
    ("graal", r"\b1996\b.*topps chrome.*kobe.*refractor|kobe.*\b1996\b.*topps chrome.*refractor", "Kobe Topps Chrome Refractor 1996 : une des recrues reines",
     "1996 Topps Chrome Kobe Refractor: a top rookie"),
    ("chasse", r"\b1996\b.*topps chrome.*kobe|kobe.*\b1996\b.*topps chrome", "Kobe Topps Chrome 1996 : recrue chromée, 16 % en 10",
     "1996 Topps Chrome Kobe: chrome rookie, 16% gem"),
    ("cle", r"\b1997\b.*metal universe.*kobe|kobe.*\b1997\b.*metal universe", "Kobe Metal Universe 1997", "1997 Metal Universe Kobe"),
    ("cle", r"\b1996\b.*metal.*fresh foundation.*iverson|iverson.*fresh foundation", "Iverson Fresh Foundation 1996", "1996 Iverson Fresh Foundation"),
    # football
    ("graal", r"\b1998\b.*contenders.*manning|manning.*\b1998\b.*contenders", "Manning Contenders Rookie Ticket 1998 : 200 autographes",
     "1998 Manning Contenders Rookie Ticket: 200 autographs"),
    ("chasse", r"\b1998\b.*contenders.*(moss|ward)|(moss|ward).*\b1998\b.*contenders", "Contenders Rookie Ticket 1998 : autographe numéroté",
     "1998 Contenders Rookie Ticket: numbered autograph"),
    ("chasse", r"\b1998\b.*(topps|bowman) chrome.*manning|manning.*\b1998\b.*(topps|bowman) chrome", "Manning Chrome 1998 : recrue chromée",
     "1998 Manning Chrome: chrome rookie"),
    ("chasse", r"atomic refractor", "Atomic Refractor de Bowman's Best", "Bowman's Best Atomic Refractor"),
    ("cle", r"\b1993\b.*\bsp\b.*bettis|bettis.*\b1993\b.*\bsp\b", "Bettis SP 1993 : feuille métallique, très peu de 10", "1993 SP Bettis: foil, very few gems"),
    ("cle", r"\b1990\b.*score.*(supplemental|traded).*emmitt|emmitt.*\b1990\b.*score.*(supplemental|101t)", "Emmitt Smith Score Supplemental 1990",
     "1990 Score Supplemental Emmitt Smith"),
    ("cle", r"\b1991\b.*stadium club.*(favre|farve)|(favre|farve).*\b1991\b.*stadium club", "Favre Stadium Club 1991", "1991 Stadium Club Favre"),
    # hockey
    ("graal", r"gretzky.*be a player.*auto|be a player.*gretzky.*auto", "Gretzky Be A Player : son premier autographe en paquet (300)",
     "Gretzky Be A Player: his first pack autograph (300)"),
    ("chasse", r"\b199[4-9]\b.*be a player.*auto|be a player.*\b199[4-9]\b.*auto", "Autographe Be A Player des années 90 : signé sur la carte",
     "90s Be A Player autograph: on-card"),
    ("chasse", r"\b199[67]\b.*(upper deck|\bud\b).*game (jersey|worn)", "Game Jersey Upper Deck 1996-97 : les premières cartes de chandail (1 sur 2 500)",
     "1996-97 Upper Deck Game Jersey: the first jersey cards (1:2,500)"),
    ("chasse", r"stanley cup hologram|pro set.*hologram", "Hologramme de la Coupe Stanley Pro Set 1990-91 : 5 000 numérotés",
     "1990-91 Pro Set Stanley Cup hologram: 5,000 numbered"),
    ("cle", r"\b1990\b.*score.*brodeur|brodeur.*\b1990\b.*score", "Brodeur Score 1990 : seule recrue de l'année", "1990 Score Brodeur: only rookie that year"),
    ("cle", r"\b1990\b.*(upper deck|\bud\b|o-?pee-?chee premier|opc premier).*jagr|jagr.*\b1990\b.*(upper deck|\bud\b|premier)",
     "Jagr 1990-91 : recrue clé", "1990-91 Jagr: key rookie"),
    ("cle", r"\b1990\b.*score.*lindros|lindros.*\b1990\b.*score", "Lindros Score 1990 : « Future Superstar »", "1990 Score Lindros: Future Superstar"),
    ("cle", r"\b1996\b.*black diamond.*thornton|thornton.*black diamond", "Thornton Black Diamond : sans bordure, rare en parfait état",
     "Thornton Black Diamond: borderless, rare in mint"),
    ("cle", r"\b199[01]\b.*(upper deck|\bud\b).*(french|fran[cç]ais).*(jagr|selanne|brodeur|bure|fedorov|lindros)",
     "Version française Upper Deck : tirage plus petit", "Upper Deck French version: smaller print run"),
]
_REGLES = [(n, re.compile(m), fr, en) for n, m, fr, en in REGLES]
_ORDRE = {"graal": 0, "chasse": 1, "cle": 2}


def reconnaitre(titre):
    """-> {niveau, raison, raison_en, plancher} de la regle la plus forte qui reconnait le titre, ou None."""
    t = " " + " ".join(str(titre or "").lower().split()) + " "
    best = None
    for n, rx, fr, en in _REGLES:
        if rx.search(t) and (best is None or _ORDRE[n] < _ORDRE[best[0]]):
            best = (n, fr, en)
    if not best:
        return None
    return {"niveau": best[0], "raison": best[1], "raison_en": best[2], "plancher": PLANCHER[best[0]]}
