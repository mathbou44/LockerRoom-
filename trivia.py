"""20 nov 2026 (Mathieu : « un genre de Trivia Crack pour apprendre le monde de la carte sportive ; hockey d'abord ; de nouvelles
questions chaque semaine : parallèles, exploits, ventes, tout ce qui est intéressant dans le hobby ; dans Admin pour l'instant ») :
5 questions par jour, 4 choix.

Règle d'or : une mauvaise réponse et on perd notre crédibilité, donc AUCUNE question inventée.
  - les questions de checklist sortent de NOS checklists (catalogue : tirages, boîtes, Young Guns) ; les nouveaux produits en
    ajoutent chaque semaine, tout seuls ;
  - les exploits sortent des stats de la LNH qu'on lit déjà (indice_joueurs : la semaine de chaque joueur) ;
  - une petite banque écrite à la main : seulement des faits sûrs et stables (vocabulaire du hobby, gradation, numéros,
    trophées).
Pas de prix : la licence eBay interdit d'en montrer un tiré d'eBay au public.
La série du jour est la même pour tous (on peut comparer), elle change chaque jour ; la banque tourne chaque semaine."""
import hashlib
import random
import re
from datetime import date, datetime

N_JOUR = 5


def _q(theme, fr, en, bonne_fr, bonne_en, mauvaises_fr, mauvaises_en, expl_fr="", expl_en=""):
    return {"theme": theme, "fr": fr, "en": en, "bonne": [bonne_fr, bonne_en], "mauvaises": list(zip(mauvaises_fr, mauvaises_en)),
            "expl": [expl_fr, expl_en]}


# ---- la banque écrite à la main : des faits sûrs et stables -------------------------------------------------------------
BANQUE = [
    _q("histoire", "La carte recrue la plus célèbre de Wayne Gretzky vient de quelle série ?",
       "Wayne Gretzky's most famous rookie card comes from which set?",
       "1979-80 O-Pee-Chee", "1979-80 O-Pee-Chee", ["1980-81 Topps", "1979-80 Upper Deck", "1981-82 O-Pee-Chee"],
       ["1980-81 Topps", "1979-80 Upper Deck", "1981-82 O-Pee-Chee"],
       "La #18 de 1979-80 O-Pee-Chee (Topps a aussi sa #18 la même année). Upper Deck n'existait pas encore.",
       "1979-80 O-Pee-Chee #18 (Topps also has a #18 that year). Upper Deck didn't exist yet."),
    _q("histoire", "Upper Deck a sorti sa toute première série de hockey en…", "Upper Deck released its very first hockey set in…",
       "1990-91", "1990-91", ["1985-86", "1995-96", "2000-01"], ["1985-86", "1995-96", "2000-01"],
       "1990-91 : la première série de hockey d'Upper Deck.", "1990-91: Upper Deck's first hockey set."),
    _q("vocab", "Que veut dire « RC » sur une carte ?", "What does “RC” mean on a card?",
       "Rookie Card (carte recrue)", "Rookie Card", ["Rare Collection", "Random Card", "Refractor Card"],
       ["Rare Collection", "Random Card", "Refractor Card"], "La première carte officielle d'un joueur.", "A player's first official card."),
    _q("vocab", "Une carte numérotée /99 existe en combien d'exemplaires ?", "A card numbered /99 exists in how many copies?",
       "99", "99", ["9", "199", "Illimité"], ["9", "199", "Unlimited"],
       "Chaque copie porte son numéro, de 1/99 à 99/99.", "Each copy carries its number, from 1/99 to 99/99."),
    _q("vocab", "Une carte « 1/1 », c'est…", "A “1/1” card is…",
       "La seule copie au monde", "The only copy in the world", ["La première carte du set", "Une carte de la 1re ronde", "Une carte gradée 10"],
       ["The first card of the set", "A first-round pick card", "A card graded 10"], "Un seul exemplaire existe.", "Only one copy exists."),
    _q("vocab", "« SSP » veut dire…", "“SSP” stands for…", "Super Short Print", "Super Short Print",
       ["Special Signed Patch", "Super Star Parallel", "Sealed Single Pack"], ["Special Signed Patch", "Super Star Parallel", "Sealed Single Pack"],
       "Une carte imprimée en très petite quantité, souvent sans numéro.", "A card printed in very small quantity, often unnumbered."),
    _q("vocab", "Un « case hit », c'est une carte qui sort environ…", "A “case hit” is a card that comes out about…",
       "Une fois par caisse", "Once per case", ["Une fois par paquet", "Une fois par boîte", "Une fois par saison"],
       ["Once per pack", "Once per box", "Once per season"], "Une caisse contient plusieurs boîtes : c'est rare.", "A case holds several boxes: it's rare."),
    _q("vocab", "Une carte « raw », c'est…", "A “raw” card is…", "Une carte pas gradée", "An ungraded card",
       ["Une carte abîmée", "Une carte sans photo", "Une carte de base"], ["A damaged card", "A card without a photo", "A base card"],
       "Raw = hors boîtier, jamais envoyée à PSA, BGS ou SGC.", "Raw = out of a slab, never sent to PSA, BGS or SGC."),
    _q("vocab", "Un « parallèle », c'est…", "A “parallel” is…", "La même carte dans un autre fini ou une autre couleur",
       "The same card in another finish or color", ["Une carte de deux joueurs", "Une carte d'une autre année", "Une carte autographiée"],
       ["A card with two players", "A card from another year", "An autographed card"],
       "Souvent numéroté : plus il est rare, plus il est recherché.", "Often numbered: the rarer, the more wanted."),
    _q("vocab", "Une carte « patch » contient…", "A “patch” card contains…", "Un morceau de chandail", "A piece of jersey",
       ["Un autographe", "Une photo dédicacée", "Un hologramme"], ["An autograph", "A signed photo", "A hologram"],
       "Souvent un morceau multicolore (logo, numéro) : les plus beaux valent plus.", "Often a multicolor piece (logo, number): the nicest are worth more."),
    _q("gradation", "PSA, c'est…", "PSA stands for…", "Professional Sports Authenticator", "Professional Sports Authenticator",
       ["Premium Slab Association", "Pro Sports Archive", "Player Signature Authority"], ["Premium Slab Association", "Pro Sports Archive", "Player Signature Authority"],
       "La plus grande compagnie de gradation au monde.", "The largest grading company in the world."),
    _q("gradation", "PSA note une carte sur quelle échelle ?", "PSA grades a card on what scale?", "1 à 10", "1 to 10",
       ["1 à 5", "1 à 100", "A à F"], ["1 to 5", "1 to 100", "A to F"], "10 = Gem Mint, la note parfaite.", "10 = Gem Mint, the perfect grade."),
    _q("gradation", "Le « Black Label », c'est la note parfaite de quelle compagnie ?", "The “Black Label” is the perfect grade of which company?",
       "BGS (Beckett)", "BGS (Beckett)", ["PSA", "SGC", "CGC"], ["PSA", "SGC", "CGC"],
       "Un 10 avec quatre sous-notes de 10 : centrage, coins, bords, surface.", "A 10 with four sub-grades of 10: centering, corners, edges, surface."),
    _q("gradation", "Combien de sous-notes a une carte BGS ?", "How many sub-grades does a BGS card have?", "4", "4", ["2", "3", "6"], ["2", "3", "6"],
       "Centrage, coins, bords et surface.", "Centering, corners, edges and surface."),
    _q("gradation", "Un centrage « 50/50 », c'est…", "A “50/50” centering is…", "Parfaitement centré", "Perfectly centered",
       ["Moitié abîmée", "Une chance sur deux d'avoir 10", "Centré sur un seul côté"], ["Half damaged", "A coin flip for a 10", "Centered on one side only"],
       "Les bordures sont égales des deux côtés.", "The borders are equal on both sides."),
    _q("produits", "Les Young Guns se trouvent dans quels produits ?", "Young Guns are found in which products?",
       "Upper Deck Series 1, 2 et Extended", "Upper Deck Series 1, 2 and Extended", ["SP Authentic", "The Cup", "O-Pee-Chee"],
       ["SP Authentic", "The Cup", "O-Pee-Chee"], "La recrue de base la plus suivie au hockey.", "The most followed base rookie in hockey."),
    _q("produits", "La « Future Watch » est la recrue de quel produit ?", "“Future Watch” is the rookie of which product?",
       "SP Authentic", "SP Authentic", ["Upper Deck Series 1", "The Cup", "Parkhurst"], ["Upper Deck Series 1", "The Cup", "Parkhurst"]),
    _q("lnh", "Quel numéro porte Connor McDavid ?", "What number does Connor McDavid wear?", "97", "97", ["99", "87", "29"], ["99", "87", "29"]),
    _q("lnh", "Quel numéro porte Sidney Crosby ?", "What number does Sidney Crosby wear?", "87", "87", ["97", "71", "8"], ["97", "71", "8"],
       "Une carte de Crosby numérotée 87/99 vaut plus que les autres : son numéro.", "A Crosby card numbered 87/99 is worth more: his number."),
    _q("lnh", "Quel numéro porte Alex Ovechkin ?", "What number does Alex Ovechkin wear?", "8", "8", ["88", "18", "91"], ["88", "18", "91"]),
    _q("lnh", "Quel numéro est retiré dans toute la LNH ?", "Which number is retired across the whole NHL?", "99", "99", ["66", "9", "4"], ["66", "9", "4"],
       "Le 99 de Wayne Gretzky, retiré par toute la ligue en 2000.", "Wayne Gretzky's 99, retired league-wide in 2000."),
    _q("lnh", "Quel numéro portait Mario Lemieux ?", "What number did Mario Lemieux wear?", "66", "66", ["99", "68", "77"], ["99", "68", "77"]),
    _q("lnh", "Quel numéro porte Connor Bedard ?", "What number does Connor Bedard wear?", "98", "98", ["97", "89", "19"], ["97", "89", "19"]),
    _q("lnh", "Quel numéro porte Macklin Celebrini ?", "What number does Macklin Celebrini wear?", "71", "71", ["17", "91", "98"], ["17", "91", "98"]),
    _q("lnh", "Quel numéro porte Auston Matthews ?", "What number does Auston Matthews wear?", "34", "34", ["16", "91", "43"], ["16", "91", "43"]),
    _q("lnh", "Le trophée Calder récompense…", "The Calder Trophy goes to…", "La meilleure recrue", "The best rookie",
       ["Le meilleur gardien", "Le meilleur pointeur", "Le joueur le plus utile"], ["The best goalie", "The top scorer", "The most valuable player"],
       "Une recrue qui le gagne voit ses cartes recrues bondir.", "A rookie who wins it sees his rookie cards jump."),
    _q("lnh", "Le trophée Art Ross récompense…", "The Art Ross Trophy goes to…", "Le meilleur pointeur", "The top point scorer",
       ["Le meilleur buteur", "La meilleure recrue", "Le meilleur défenseur"], ["The top goal scorer", "The best rookie", "The best defenseman"]),
    _q("lnh", "Le trophée Hart récompense…", "The Hart Trophy goes to…", "Le joueur le plus utile à son équipe", "The player most valuable to his team",
       ["Le meilleur gardien", "La meilleure recrue", "Le capitaine"], ["The best goalie", "The best rookie", "The captain"]),
    _q("lnh", "Combien d'équipes compte la LNH en 2025-26 ?", "How many teams are in the NHL in 2025-26?", "32", "32", ["30", "31", "34"], ["30", "31", "34"]),
    _q("lnh", "Qui a gagné la Coupe Stanley en 2025 ?", "Who won the Stanley Cup in 2025?", "Panthers de la Floride", "Florida Panthers",
       ["Oilers d'Edmonton", "Stars de Dallas", "Hurricanes de la Caroline"], ["Edmonton Oilers", "Dallas Stars", "Carolina Hurricanes"],
       "Une deuxième coupe de suite, contre les Oilers en finale les deux fois.", "A second straight Cup, beating the Oilers in the final both times."),
]


# ---- les questions tirées de nos checklists (de nouvelles chaque semaine avec les nouveaux produits) ---------------------
def _nom_court(p):
    return re.sub(r"^\d{4}-\d{2}\s+", "", p.get("nom") or "")


def _de_checklist(p, rnd):
    """Quelques questions vraies sur UN produit (ses sous-ensembles tels que publiés)."""
    out, nom = [], p.get("nom") or ""
    ses = [s for s in (p.get("sous_ensembles") or []) if isinstance(s, dict) and s.get("nom")]
    # 1. le tirage d'un parallele numerote
    num = [s for s in ses if isinstance(s.get("tirage"), int) and 1 <= s["tirage"] <= 999 and s.get("groupe") != "base"]
    if num:
        s = rnd.choice(num)
        t = s["tirage"]
        pool = sorted({x["tirage"] for x in ses if isinstance(x.get("tirage"), int) and x["tirage"] != t and 1 <= x["tirage"] <= 999})
        pool += [v for v in (1, 5, 10, 25, 49, 99, 149, 199, 249, 499, 999) if v != t and v not in pool]
        rnd.shuffle(pool)
        txt = lambda v: "1/1" if v == 1 else f"/{v}"
        out.append(_q("parallèles", f"Dans {nom}, « {s['nom']} » est numéroté à…", f"In {nom}, “{s['nom']}” is numbered to…",
                      txt(t), txt(t), [txt(v) for v in pool[:3]], [txt(v) for v in pool[:3]],
                      f"Selon la checklist de {nom}.", f"Per the {nom} checklist."))
    # 2. les paquets d'une boite hobby
    f = next((x for x in (p.get("formats") or []) if "hobby" in str(x.get("format", "")).lower() and x.get("paquets")), None)
    if f:
        b = int(f["paquets"])
        m = [v for v in (4, 6, 8, 10, 12, 16, 18, 20, 24, 36) if v != b]
        rnd.shuffle(m)
        out.append(_q("produits", f"Combien de paquets dans une boîte hobby de {nom} ?", f"How many packs in a {nom} hobby box?",
                      str(b), str(b), [str(v) for v in m[:3]], [str(v) for v in m[:3]],
                      f"{b} paquets de {f.get('cartes_par_paquet')} cartes." if f.get("cartes_par_paquet") else "",
                      f"{b} packs of {f.get('cartes_par_paquet')} cards." if f.get("cartes_par_paquet") else ""))
    # 3. qui a un Young Guns dans ce produit
    cartes = p.get("cartes") or []
    yg = sorted({c["joueur"] for c in cartes if c.get("joueur") and str(c.get("sous_ensemble") or "").strip().lower() == "young guns"})
    if len(yg) >= 1:
        autres = sorted({c["joueur"] for c in cartes if c.get("joueur") and not c.get("recrue")
                         and str(c.get("sous_ensemble") or "").lower().startswith("base")} - set(yg))
        if len(autres) >= 3:
            j = rnd.choice(yg)
            m = rnd.sample(autres, 3)
            out.append(_q("recrues", f"Lequel de ces joueurs a un Young Guns dans {nom} ?", f"Which of these players has a Young Guns in {nom}?",
                          j, j, m, m, "Les trois autres y ont seulement une carte de base.", "The other three only have a base card in it."))
    return out


def _nouveautes(prods, rnd):
    """Quelle sortie est la plus récente (la date de sortie de nos fiches produits)."""
    d = [p for p in prods if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(p.get("sortie") or ""))]
    if len(d) < 4:
        return []
    l = rnd.sample(d, 4)
    l.sort(key=lambda p: p["sortie"], reverse=True)
    if l[0]["sortie"] == l[1]["sortie"]:
        return []
    return [_q("produits", "Lequel de ces produits est sorti le plus récemment ?", "Which of these products came out most recently?",
               l[0]["nom"], l[0]["nom"], [p["nom"] for p in l[1:]], [p["nom"] for p in l[1:]],
               f"Sorti le {l[0]['sortie']}.", f"Released {l[0]['sortie']}.")]


# ---- les exploits de la semaine (stats de la LNH) --------------------------------------------------------------------------
def _exploits(rnd):
    try:
        import indice_joueurs
        I = (indice_joueurs.lire() or {}).get("indice") or {}
    except Exception:
        return []
    sem = [(nom, v["semaine"]) for nom, v in I.items() if v.get("actif") and isinstance(v.get("semaine"), dict)
           and isinstance(v["semaine"].get("pts"), (int, float)) and v["semaine"].get("mj")]
    sem.sort(key=lambda x: -x[1]["pts"])
    if len(sem) < 8 or sem[0][1]["pts"] <= sem[1][1]["pts"]:
        return []
    haut = sem[0]
    bas = rnd.sample([x for x in sem[6:40] if x[1]["pts"] < haut[1]["pts"]], 3)
    w = haut[1]
    return [_q("exploits", "Lequel de ces joueurs a le plus de points dans ses derniers matchs ?",
               "Which of these players has the most points in his last games?", haut[0], haut[0], [x[0] for x in bas], [x[0] for x in bas],
               f"{haut[0]} : {int(w['pts'])} points en {int(w['mj'])} matchs (stats de la LNH).",
               f"{haut[0]}: {int(w['pts'])} points in {int(w['mj'])} games (NHL stats).")]


def _graine(*parties):
    return int(hashlib.sha256("|".join(str(x) for x in parties).encode()).hexdigest()[:12], 16)


def pool_semaine(sport="hockey", jour=None):
    """Toutes les questions possibles cette semaine : la banque + nos checklists (nouveaux produits d'abord) + les exploits."""
    jour = jour or date.today()
    an, sem, _ = jour.isocalendar()
    rnd = random.Random(_graine(sport, an, sem))
    out = [dict(q) for q in BANQUE] if sport == "hockey" else []
    try:
        import catalogue
        prods = [p for p in catalogue.liste() if (p.get("sport") or "hockey") == sport] if sport != "hockey" else \
            [p for p in catalogue.liste() if (p.get("sport") or "hockey") == "hockey"]
        prods.sort(key=lambda p: str(p.get("sortie") or ""), reverse=True)
        for p in prods[:12]:                              # les 12 plus récents : la semaine suivante en amène d'autres
            try:
                full = catalogue.charger(p["id"])
            except Exception:
                full = None
            if full:
                out += _de_checklist(full, rnd)
        out += _nouveautes(prods, rnd)
    except Exception as e:
        print("Trivia (checklists) : " + repr(e)[:160], flush=True)
    out += _exploits(rnd)
    return out


def jour(langue="fr", sport="hockey", quand=None):
    """Les 5 questions du jour (les mêmes pour tous), choix mélangés. -> [{id, theme, q, choix, bonne, expl}]"""
    quand = quand or date.today()
    pool = pool_semaine(sport, quand)
    rnd = random.Random(_graine("jour", sport, quand.isoformat()))
    # au moins une question de checklist et un exploit s'il y en a : le hobby d'abord
    themes = {}
    for q in pool:
        themes.setdefault(q["theme"], []).append(q)
    choisies = []
    for t in ("parallèles", "recrues", "exploits"):
        if themes.get(t):
            choisies.append(rnd.choice(themes[t]))
    reste = [q for q in pool if q not in choisies]
    rnd.shuffle(reste)
    choisies = (choisies + reste)[:N_JOUR]
    rnd.shuffle(choisies)
    i = 1 if langue == "en" else 0
    out = []
    for q in choisies:
        choix = [q["bonne"][i]] + [m[i] for m in q["mauvaises"][:3]]
        if len(set(choix)) < 4:
            continue                                     # deux choix pareils : on ne pose pas une question ambigue
        rnd.shuffle(choix)
        out.append({"id": hashlib.md5((q["fr"] + q["bonne"][0]).encode()).hexdigest()[:10], "theme": q["theme"],
                    "q": q["en"] if i else q["fr"], "choix": choix, "bonne": choix.index(q["bonne"][i]), "expl": q["expl"][i]})
    return out


def noter(etat, bonnes, total, quand=None):
    """La série de jours (comme Duolingo) et le meilleur score. etat : {serie, meilleur, dernier, score_jour, parties}"""
    quand = (quand or date.today()).isoformat()
    e = dict(etat or {})
    if e.get("dernier") == quand:
        return e                                          # une partie comptée par jour
    hier = date.fromordinal(date.fromisoformat(quand).toordinal() - 1).isoformat()
    e["serie"] = (int(e.get("serie") or 0) + 1) if e.get("dernier") == hier else 1
    e["dernier"], e["score_jour"] = quand, [int(bonnes), int(total)]
    e["parties"] = int(e.get("parties") or 0) + 1
    e["bonnes"] = int(e.get("bonnes") or 0) + int(bonnes)
    e["meilleure_serie"] = max(int(e.get("meilleure_serie") or 0), e["serie"])
    e["le"] = datetime.now().isoformat(timespec="seconds")
    return e
