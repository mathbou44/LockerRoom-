"""
SLABCOACH - « À grader » : les cartes qui valent la peine d'etre envoyees chez PSA (26 nov 2026). ADMIN seulement.

Mathieu (12 h 22, 12 h 31) : « savoir les cartes qui valent le plus la peine d'etre gradees [...] on partirait de toutes nos
ventes des 3 derniers mois, ou plus [...] de toutes les paralleles de cartes qui ont ete vendues en PSA 10. Puis on regarde la
version raw, combien elle a ete vendue en moyenne, versus la moyenne des vendus PSA 10 pour le meme genre de time frame. Puis on
regarde ceux avec le meilleur rapport achat versus vente. [...] On va commencer a l'implanter dans Admin, le temps qu'elle soit
parfaite. »

LA METHODE (rien n'est suppose, tout vient de ventes reelles) :
1. Chaque vente est rangee par son TITRE, jamais par la recherche qui l'a trouvee : la carte exacte (le joueur, les mots de
   l'app pour cette carte, l'annee, le /N) et sa note (raw, PSA 10, PSA 9). Le meme decodeur et les memes refus que les comps
   (cartes_match) et que les tendances (tendance_sortes.autre_carte).
2. Ecartees, parce qu'elles fausseraient un prix :
   - une carte raw qui se dit « PSA 10 ? », « PSA 10 contender », « possible PSA 10 » (le decodeur y lit une PSA 10) : la
     meme regle que les comps de l'app (cartes_match.espere_note) ;
   - une carte abimee (pli, coin mou...) : on n'envoie pas ca chez PSA ;
   - un lot, une reedition, une carte a plusieurs joueurs, une autre compagnie (BGS, SGC, CGC), une autre note.
3. LA MEME PERIODE pour les trois prix : on ne garde que les ventes depuis le jour ou la raw ET la PSA 10 sont toutes deux
   couvertes (une carte tres vendue n'a parfois que ses 2 dernieres semaines en raw : sa PSA 10 d'il y a 3 mois ne lui est pas
   comparee).
4. Le prix = la MEDIANE (une vente a 3 fois le prix ne tire pas le chiffre). Il faut RAW_MIN ventes raw et P10_MIN ventes
   PSA 10 ; la PSA 9 est donnee des P9_MIN ventes, sinon elle reste vide (jamais « 45 % de la PSA 10 » : grader.py le supposait,
   les vraies ventes disent plutot 25 %).
5. Trois garde-fous contre deux cartes melangees (essai du 26 nov sur nos archives : « Sennecke Outburst » raw 70 $ contre
   PSA 10 1 527 $, « Jack Hughes Gold ») :
   - la carte doit nommer un SET (« Young Guns », « O-Pee-Chee Platinum »...) : une couleur seule (« Gold ») n'est pas une carte ;
   - le NUMERO de la carte (#451) fait partie de la carte : deux numeros = deux cartes ; une vente sans numero ne compte que
     si la carte n'a qu'un seul numero (90 % des ventes numerotees) ;
   - des prix trop etales (q75 / q25 > DISPERSION_MAX) -> la carte n'est pas listee.
6. L'argent : ce qui reste si elle revient 10, ce qui reste si elle revient 9 (frais eBay de la revente, frais PSA, envoi),
   le SEUIL (la part de 10 qu'il faut pour ne pas perdre) et le RENDEMENT si 10 : ce qui revient pour 1 $ mis (la carte + les
   frais PSA). La liste est classee par ce rendement : « le meilleur rapport achat versus vente », frais compris (classer par
   PSA 10 / raw mettrait en tete des cartes a 2 $ ou il reste 10 $). On n'ecrit JAMAIS une chance de 10 ni un profit espere : sans la
   population PSA (qu'on n'utilise pas), personne ne la connait.

Les montants : admin seulement (regle des comps).
"""
import json
import os
import re
import sqlite3
import statistics
import threading
import time
from datetime import datetime, timedelta, timezone

JOURS = 365                          # 26 nov, 18 h 50 (Mathieu : « besoin de plus de data [...] au moins entre 500 et 1 000 » ; son choix :
                                     # « 12 mois + 500 joueurs ») : une carte rare en PSA 10 se compte sur 12 mois
RAW_MIN = 5
P10_MIN = 5                          # 4 -> 5 des le premier essai : a 4 ventes, une PSA 10 d'une autre parallele suffit a fausser la mediane
P9_MIN = 3
VERSION = 4                          # 2 = la regle des 60 derniers jours (26 nov) ; 3 = les titres ecrits comme l'etiquette PSA ; 4 = 12 mois, les fausses raw jetees ;
                                     # une liste d'une autre version est refaite seule
NUM_MIN = 5                          # titre « etiquette » : la carte doit deja avoir 5 ventes qui disent ce numero...
NUM_NOTE_MIN = 3                     # ... dont 3 de la meme note, et le prix doit etre de 0,4 a 2,5 fois leur mediane
NUM_PRIX = (0.4, 2.5)
JOURS_RECENT = 60                    # 26 nov, 16 h 36 (Mathieu : « le temps est important » ; son « Oui ») : la periode la plus RECENTE qui a
FENETRES = (60, 120)                 # assez de ventes (raw, PSA 10, et PSA 9 si la carte a un prix PSA 9) : 60 jours, sinon 120, sinon
                                     # toute la fenetre (12 mois). Une vieille vente ne sert que si la carte n'en a pas assez de recentes.
REFAIRE_J = 7                        # 26 nov, 15 h 06 (Mathieu : « le top 100 a grader qui se refresh chaque semaine ») : refaite chaque semaine,
                                     # une fois de plus quand la collecte PSA finit, et quand l'admin le demande
REFAIRE_COLLECTE_MIN = 110           # pendant une collecte PSA : la liste suit, refaite aux 2 heures (12 mois de ventes : ~10 minutes)
N_TOP = 100
ETAT = {"en_cours": False, "texte": None}
_verrou = threading.Lock()
_MEM = {"mtime": None, "v": None}
DISPERSION_MAX = 3.0
FRAIS_EBAY = 0.1325                  # la revente sur eBay (comme grader.calculer)
FRAIS_FIXE = 0.40
N_LISTE = 200

# une carte gradee que le decodeur laisse sans note (PSA 8 et moins, une compagnie rare) : jamais comptee comme une raw
_RE_GRADEE = re.compile(r"\b(psa|bgs|bvg|sgc|cgc|csg|tag|beckett|ksa|hga|gma|mnt|isa|aca|bccg|ags|rcg)\s*\d|\b(graded|slab|slabbed|gradee?)\b", re.I)


def frais_psa():
    import grader
    return grader.FRAIS_PSA + grader.ENVOI_PSA


# la mesure de la couverture (voir analyser) : le titre DIT-il PSA 10 ou PSA 9 ? et les mots d'un titre qui peuvent nommer une sorte
_RE_NOTE_TITRE = re.compile(r"\bpsa[\s\-]*(10|9)(?![\d.])", re.I)
N_INCONNUES = 25
N_EXEMPLES = 2                       # vrais titres gardes par paire de mots (le journal : c'est par la que je les lis)
_MOTS_VIDES = set("psa gem mint mt rc rookie rookies card cards hockey nhl the and of for with a an in on upper deck ud graded grade pop new "
                  "sp ssp rare hot invest low nm near pack fresh free shipping ship auto autograph signed jersey patch read see pics "
                  "year first 1st nice sharp centered clean beautiful stunning must have look wow tm inc co ltd lot edition hof".split())


def _etiquette(titre, joueur):
    """26 nov 2026 (le fichier de la collecte PSA : « 2024 UD #451 MACKLIN CELEBRINI PSA 10 », « 2025 UD UD CANVAS #C-231 IVAN
    DEMIDOV ROOKIE RC PSA 10 » : 877 ventes PSA 10 sans le nom de la sorte, dont les Young Guns les plus vendues) : un titre
    ecrit comme l'etiquette PSA. -> (joueur, annee, numero, note, mots de parallele) si le titre donne une annee, un numero,
    une note PSA 10 ou 9, UN joueur, pas de /N et AUCUN mot distinctif ; sinon None. Le numero dira quelle carte (analyser)."""
    import cartes_match as cm
    t = str(titre or "")
    try:
        ct = cm.cible_titre(t, joueur)
    except Exception:
        return None
    g = ct.get("grade") or {}
    if g.get("cie") != "psa" or str(g.get("note") or "") not in ("10", "9") or cm.espere_note(t):
        return None
    if not ct.get("joueur") or ct.get("autres_joueurs") or ct.get("serie") or ct.get("ident"):
        return None
    num = re.sub(r"[^a-z0-9]", "", str(ct.get("num") or "").lower())
    if not num or not ct.get("annee"):
        return None
    par = frozenset(w for x in (ct.get("paralleles") or ()) for w in str(x).split())
    return ct["joueur"], ct["annee"], num, str(g["note"]), par


def _nomme(titre, joueur):
    """Le titre nomme-t-il ce joueur ? Un mot qui commence comme son prenom (« Alex » / « Alexander »), puis son nom de famille
    juste apres (un mot d'ecart au plus). 26 nov 2026 (le fichier de la collecte) : « Cam Schlittler New York Yankees » avait
    un « cam » et un « york » : la recherche « cam york psa 10 » a ramene 1 480 ventes de baseball et de football."""
    import cartes_match as cm
    mots = cm.norm(titre).split()
    nom = cm.norm(joueur).split()
    if not nom:
        return True
    if len(nom) < 2:
        return nom[0] in mots
    fin = nom[1:]
    for i, m in enumerate(mots):
        if m.startswith(nom[0][:3]) and (mots[i + 1:i + 1 + len(fin)] == fin or mots[i + 2:i + 2 + len(fin)] == fin):
            return True
    return False


def _duos(titre, joueur=None):
    """Les paires de mots voisins d'un titre, sans le nom du joueur, les annees, les numeros ni les mots de vendeur : ce qui
    reste nomme presque toujours le set ou la parallele (« fleer retro », « metal universe »...)."""
    nom = set(re.findall(r"[a-z]+", str(joueur or "").lower()))
    try:
        import cartes_match as cm
        for n in cm._noms_dans(cm.norm(titre)):               # les joueurs connus nommes dans le titre
            nom.update(n.split())
    except Exception:
        pass
    mots = [w for w in re.findall(r"[a-z][a-z'\-]*[a-z]", str(titre or "").lower()) if w not in _MOTS_VIDES and w not in nom]
    return {mots[k] + " " + mots[k + 1] for k in range(len(mots) - 1)}


_NOMS = {"le": 0.0, "d": {}}


def beau_nom(j):
    """« connor mcdavid » -> « Connor McDavid » (le nom de l'indice SlabIQ) ; sinon la majuscule simple."""
    if time.time() - _NOMS["le"] > 3600:
        try:
            import cartes_match as cm
            import indice_joueurs
            _NOMS["d"] = {cm.joueur_du_titre(n): n for n in (indice_joueurs.lire().get("indice") or {})}
        except Exception:
            _NOMS["d"] = {}
        _NOMS["le"] = time.time()
    return _NOMS["d"].get(j) or " ".join(w.capitalize() for w in str(j or "").split())


def classer(titre, joueur=None, pourquoi=None):
    """Un titre -> ((joueur, recherche raw, annee, /N), note) avec note = « raw », « 10 » ou « 9 » ; None si la vente ne doit
    pas compter (voir le point 2 du haut). `pourquoi` (une liste) recoit alors la raison, pour mesurer ce qu'on laisse passer."""
    import cartes_match as cm
    import tendance_sortes as ts
    def non(raison):
        if pourquoi is not None:
            pourquoi.append(raison)
        return None
    t = str(titre or "")
    try:
        ct = cm.cible_titre(t, joueur)
    except Exception:
        return non("titre illisible")
    if not ct.get("joueur"):
        return non("joueur pas reconnu")
    if ct.get("autres_joueurs"):
        return non("plusieurs joueurs")
    if not ct.get("carte_nommee") or not ct.get("ident"):
        return non("sorte pas reconnue")                      # il faut un SET : une couleur seule n'est pas une carte
    g = ct.get("grade")
    if g:
        if g.get("cie") != "psa" or str(g.get("note") or "") not in ("10", "9"):
            return non("autre note ou compagnie")             # une autre compagnie, une autre note, « PSA ready »
        if cm.espere_note(t):
            return non("pas encore gradee")                      # « PSA 10 ? », « PSA 10 contender » : une raw qui espere (la regle des comps)
        note = str(g["note"])
    else:
        if ct.get("grade_bas") or _RE_GRADEE.search(t):
            return non("autre note ou compagnie")             # une PSA 8, une SGC, une « graded 9 » : gradee, donc pas une raw
        if cm._RE_ABIMEE.search(t.lower()):
            return non("abimee")                              # abimee : pas une carte a grader
        note = "raw"
    serie = ct.get("serie")
    try:
        q_note = cm.requete_ebay(ct)
        if cm.raisons_refus(cm.cible(q_note + (f" /{serie}" if serie else "")), t):
            return non("lot ou autre carte")                  # un lot ecrit avec « + », la suite d'un set, etc.
    except Exception:
        return non("titre illisible")
    ct["grade"] = None
    q = cm.requete_ebay(ct)
    if len(q.split()) < 3 or ts.autre_carte(t, q):
        return non("lot ou autre carte")
    num = re.sub(r"[^a-z0-9]", "", str(ct.get("num") or "").lower()) or None
    return (ct["joueur"], q, ct.get("annee"), serie, num), note


def _q(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, max(0, int(round(p * (len(v) - 1)))))]


def _etale(prix):
    return (_q(prix, 0.75) / _q(prix, 0.25)) if len(prix) >= 4 and _q(prix, 0.25) > 0 else 1.0


def _meme_periode(g, depuis, jetees=None):
    """Les prix raw, PSA 10 et PSA 9 d'une carte depuis `depuis`, sur LA MEME periode (elle commence a la plus tardive des
    premieres ventes raw et PSA 10). -> (« ok », debut, raw, psa 10, psa 9), ou (la raison,) si la carte ne peut pas etre mesuree.
    26 nov 2026, 19 h 13 (Mathieu, la fiche Dylan Larkin Young Guns Canvas : raw 152 $, PSA 10 131 $ : « impossible, une raw ne
    se vend jamais plus chere qu'une PSA 10 »). Les vraies ventes : 3 des 5 « raw » (152 $, 156 $, 171 $) portaient le titre
    automatique d'eBay (« 2015-16 Upper Deck - Ud Canvas Young Guns Dylan Larkin #C112 (RC) »), sans note ecrite : des cartes
    GRADEES ; les vraies raw : 10 $ a 64 $. Une vente « raw » au prix median de la PSA 10 ou plus n'est pas une raw : elle est
    jetee, et la carte n'est mesuree que s'il reste assez de vraies raw. `jetees` (une liste) recoit leur nombre."""
    raw = [(d, p) for d, p in g["raw"] if d >= depuis]
    p10 = [(d, p) for d, p in g["10"] if d >= depuis]
    if len(raw) < RAW_MIN or len(p10) < P10_MIN:
        return ("periode trop courte",)
    d0 = max(min(d for d, _ in raw), min(d for d, _ in p10))
    raw = [p for d, p in raw if d >= d0]
    p10 = [p for d, p in p10 if d >= d0]
    if len(raw) < RAW_MIN or len(p10) < P10_MIN:
        return ("periode trop courte",)
    m10 = statistics.median(p10)
    vraies = [p for p in raw if p < m10]
    if len(vraies) < len(raw):
        if len(vraies) < RAW_MIN:
            return ("raw melangee a des gradees",)
        if jetees is not None:
            jetees.append(len(raw) - len(vraies))
        raw = vraies
    if _etale(raw) > DISPERSION_MAX or _etale(p10) > DISPERSION_MAX:
        return ("prix trop etales",)
    return "ok", d0, raw, p10, [p for d, p in g["9"] if d >= d0]


def analyser(ventes, aujourd=None, jours=JOURS, respirer=None):
    """ventes : des (cle de la vente, titre, prix $ CA, date AAAA-MM-JJ, joueur ou None). -> {« cartes »: [...], « lues », « rangees »,
    « ecartees » : pourquoi une carte vue en PSA 10 n'est pas dans la liste}. La liste : le meilleur rapport PSA 10 / raw d'abord."""
    import tendance_sortes as ts
    auj = aujourd or datetime.now(timezone.utc).date()
    d_min = (auj - timedelta(days=jours)).isoformat()
    vues, cartes, lues, rangees = set(), {}, 0, 0
    noms = {}
    # 26 nov 2026 (Mathieu : « je veux juste etre sur qu'on capte tous les paralleles les plus vendus de PSA 10 puis PSA 9 ») :
    # on le MESURE au lieu de le supposer. Pour les ventes dont le titre dit PSA 10 (ou PSA 9) : combien sont rangees dans une
    # carte exacte, pourquoi les autres ne le sont pas, et les mots qui reviennent le plus dans celles dont on ne reconnait
    # pas la sorte (un set ou une parallele que le decodeur ne connait pas encore).
    # 26 nov, 16 h 18 (premiere mesure sur le serveur : 45 % ; les mots sans sorte : « ozzie cardinals », « emmitt cowboys »...) :
    # la recherche « will smith psa 10 » ramene aussi Ozzie Smith et Emmitt Smith. Une vente qui ne nomme PAS le joueur
    # cherche n'est pas une vente qu'on rate : elle est comptee a part (« autre_joueur »), hors de la mesure.
    couv = {n: {"lues": 0, "rangees": 0, "autre_joueur": 0, "raisons": {}} for n in ("10", "9")}
    mots_inconnus = {}
    ex_duo, ex_lot = {}, []                                   # quelques vrais titres, pour ecrire la regle qui manque au decodeur
    etiquettes = []                                           # les titres ecrits comme l'etiquette PSA (voir _etiquette)
    for i, (cle, titre, prix, le, joueur) in enumerate(ventes):
        if respirer and i % 200 == 199:
            respirer(i)
        le = str(le or "")[:10]
        if not prix or prix <= 0 or le < d_min or cle in vues:
            continue
        vues.add(cle)
        lues += 1
        m = _RE_NOTE_TITRE.search(str(titre or ""))
        dit = m.group(1) if m else None
        pq = [] if dit else None
        r = classer(titre, joueur, pq)
        if dit and not r and pq and pq[0] == "sorte pas reconnue":
            e = _etiquette(titre, joueur)
            if e:
                etiquettes.append(e + (le, float(prix)))
        if dit and not r and joueur and not _nomme(titre, joueur):
            couv[dit]["autre_joueur"] += 1
        elif dit:
            cv = couv[dit]
            cv["lues"] += 1
            if r and r[1] == dit:
                cv["rangees"] += 1
            else:
                raison = pq[0] if pq else "autre note ou compagnie"
                cv["raisons"][raison] = cv["raisons"].get(raison, 0) + 1
                if raison == "sorte pas reconnue" and dit == "10" and len(mots_inconnus) < 200000:
                    for duo in _duos(titre, joueur):
                        mots_inconnus[duo] = mots_inconnus.get(duo, 0) + 1
                        if len(ex_duo) < 20000 or duo in ex_duo:
                            e = ex_duo.setdefault(duo, [])
                            if len(e) < N_EXEMPLES:
                                e.append(str(titre)[:110])
                elif raison == "lot ou autre carte" and dit == "10" and len(ex_lot) < 4 * N_EXEMPLES and i % 7 == 0:
                    ex_lot.append(str(titre)[:110])
        if not r:
            continue
        rangees += 1
        cartes.setdefault(r[0], {"raw": [], "10": [], "9": []})[r[1]].append((le, float(prix)))
        if joueur:
            noms.setdefault(r[0][0], joueur)
    # une vente sans annee (ou sans numero) dans son titre : a la saison (au numero) de la carte s'il n'y en a qu'une (90 % des
    # ventes qui la disent), sinon ecartee. D'abord l'annee (parmi les ventes du meme numero quand elle en a un), puis le numero
    # (parmi les ventes de la meme saison).
    vide = lambda: {"raw": [], "10": [], "9": []}
    nb = lambda g: sum(len(x) for x in g.values())
    def seul(compte):
        tot = sum(compte.values())
        return next((v for v, n in compte.items() if tot >= ts.SAISON_DATEES_MIN and n >= ts.SAISON_PART_MIN * tot), None)
    def verser(dest, cle, g):
        f = dest.setdefault(cle, vide())
        for k in f:
            f[k] = f[k] + g[k]
    datees = {}
    par_carte = {}
    for (j, q, an, se, num), g in cartes.items():
        par_carte.setdefault((j, q, se), []).append((an, num, g))
    for (j, q, se), L in par_carte.items():
        for an, num, g in L:
            if an is None:
                memes = [(a2, n2, g2) for a2, n2, g2 in L if a2 is not None and (num is None or n2 == num)]
                compte = {}
                for a2, _n2, g2 in memes:
                    compte[a2] = compte.get(a2, 0) + nb(g2)
                an = seul(compte)
                if an is None:
                    continue
            verser(datees, (j, q, an, se, num), g)
    finales = {}
    par_saison = {}
    for (j, q, an, se, num), g in datees.items():
        par_saison.setdefault((j, q, an, se), []).append((num, g))
    for (j, q, an, se), L in par_saison.items():
        compte = {n: nb(g) for n, g in L if n is not None}
        le_num = seul(compte)
        for num, g in L:
            if num is None and compte:
                if le_num is None:
                    continue                                  # plusieurs numeros existent : on ne sait pas laquelle
                num = le_num
            verser(finales, (j, q, an, se, num), g)
    # Les titres « etiquette » : rangees dans la Young Guns (ou sa parallele nommee : Canvas, Outburst...) du MEME joueur, de la
    # MEME saison et du MEME numero, si cette carte existe deja par ses ventes normales (NUM_MIN ventes qui disent le numero,
    # NUM_NOTE_MIN de la meme note) et si le prix leur ressemble. Une carte de base (« 2024 UD #411 ») ou une autre serie
    # (« 2024 UD #743 ») n'a pas de Young Guns a ce numero : elle reste dehors. Jamais pour une raw.
    par_num = {}
    for (j, q, an, se, num), g in finales.items():
        if se is None and num and an is not None:
            par_num.setdefault((j, an, num), []).append(q)
    n_etiq = {"10": 0, "9": 0}
    pas_rangees = {"pas de Young Guns a ce numero": 0, "carte trop peu vendue": 0, "prix trop different": 0}
    ajouts = {}
    for j, an, num, note, par, le, prix in etiquettes:
        veut = {"young", "guns"} | set(par)
        qs = [q for q in par_num.get((j, an, num), ()) if set(q.split()) - set(j.split()) == veut]
        if len(qs) != 1:
            pas_rangees["pas de Young Guns a ce numero"] += 1
            continue
        cle = (j, qs[0], an, None, num)
        normales = [p for _, p in finales[cle][note]]
        if nb(cartes.get(cle) or vide()) < NUM_MIN or len(normales) < NUM_NOTE_MIN:
            pas_rangees["carte trop peu vendue"] += 1
            continue
        med = statistics.median(normales)
        if not (NUM_PRIX[0] * med <= prix <= NUM_PRIX[1] * med):
            pas_rangees["prix trop different"] += 1
            continue
        ajouts.setdefault(cle, {"10": [], "9": []})[note].append((le, prix))
        n_etiq[note] += 1
    for cle, g in ajouts.items():
        for note in ("10", "9"):
            finales[cle][note] = finales[cle][note] + g[note]
    couv["etiquettes"] = {"vues": len(etiquettes), "rangees": n_etiq["10"] + n_etiq["9"], **pas_rangees}
    for note in ("10", "9"):
        couv[note]["par_numero"] = n_etiq[note]
        couv[note]["rangees"] += n_etiq[note]
        if n_etiq[note]:
            reste = couv[note]["raisons"].get("sorte pas reconnue", 0) - n_etiq[note]
            if reste > 0:
                couv[note]["raisons"]["sorte pas reconnue"] = reste
            else:
                couv[note]["raisons"].pop("sorte pas reconnue", None)
    out, ecartees = [], {"peu de PSA 10": 0, "peu de raw": 0, "periode trop courte": 0, "prix trop etales": 0, "raw melangee a des gradees": 0}
    raw_gradees = 0                                           # les « raw » au prix de la PSA 10, jetees (voir _meme_periode)
    fp = frais_psa()
    net = lambda p: p * (1 - FRAIS_EBAY) - FRAIS_FIXE
    for (j, q, an, se, num), g in finales.items():
        if an is None:
            continue                                          # aucune vente ne dit la saison : on ne sait pas quelle carte
        if len(g["10"]) < P10_MIN:
            if g["10"]:
                ecartees["peu de PSA 10"] += 1
            continue
        if len(g["raw"]) < RAW_MIN:
            ecartees["peu de raw"] += 1
            continue
        # 26 nov 2026 (Mathieu : « le temps est important la-dedans » ; mesure : en 120 jours la PSA 10 de Misa est passee de 417 $ a
        # 309 $, x4,39 -> x3,26) : la periode la plus RECENTE ou la carte se mesure (assez de raw et de PSA 10, des prix qui se
        # tiennent) : 60 jours, sinon 120, sinon toute la fenetre. On saute une periode courte si la carte y perd son prix PSA 9
        # (moins de P9_MIN ventes) alors qu'une plus longue le donne : il fait le seuil.
        essais = []
        for f in [f for f in FENETRES if f < jours] + [jours]:
            jt = []
            essais.append((f, _meme_periode(g, (auj - timedelta(days=f)).isoformat() if f < jours else d_min, jt), sum(jt)))
        bons = [e for e in essais if e[1][0] == "ok"]
        if not bons:
            ecartees[essais[-1][1][0]] += 1
            continue
        avec9 = [e for e in bons if len(e[1][4]) >= P9_MIN]
        fenetre, (_, d0, raw, p10, p9), n_jetees = (avec9 or bons)[0]
        raw_gradees += n_jetees
        m_raw, m10 = statistics.median(raw), statistics.median(p10)
        m9 = statistics.median(p9) if len(p9) >= P9_MIN else None
        if m_raw <= 0:
            continue
        cout = m_raw + fp
        r10 = net(m10) - cout
        r9 = (net(m9) - cout) if m9 is not None else None
        seuil = None                                           # la part de 10 qu'il faut pour ne pas perdre (si la 9 est connue)
        if r9 is not None:
            seuil = 0.0 if r9 >= 0 else (None if r10 <= 0 else round(-r9 / (r10 - r9), 3))
        sorte = " ".join(w for w in q.split() if w not in set(j.split()))
        out.append({"joueur": noms.get(j) or beau_nom(j), "cle_joueur": j, "q": q, "nom": ts.libelle(sorte), "annee": an, "serie": se, "num": num,
                    "rendement": round(net(m10) / cout, 2),
                    "raw": round(m_raw, 2), "psa10": round(m10, 2), "psa9": round(m9, 2) if m9 is not None else None,
                    "n_raw": len(raw), "n10": len(p10), "n9": len(p9), "rapport": round(m10 / m_raw, 2),
                    "reste10": round(r10, 2), "reste9": round(r9, 2) if r9 is not None else None, "seuil": seuil,
                    "du": d0, "jours": (auj - datetime.strptime(d0, "%Y-%m-%d").date()).days, "fenetre": fenetre})
    out.sort(key=lambda x: (-x["rendement"], -x["reste10"]))
    for n in ("10", "9"):
        couv[n]["raisons"] = dict(sorted(couv[n]["raisons"].items(), key=lambda x: -x[1]))
    couv["sortes_inconnues"] = [[d, n] for d, n in sorted(mots_inconnus.items(), key=lambda x: (-x[1], x[0]))[:N_INCONNUES] if n >= 3]
    couv["exemples"] = {d: ex_duo.get(d) or [] for d, _ in couv["sortes_inconnues"]}
    couv["exemples_lot"] = ex_lot
    return {"version": VERSION, "cartes": out[:N_LISTE], "n_cartes": len(out), "lues": lues, "rangees": rangees, "ecartees": ecartees, "raw_gradees": raw_gradees, "couverture": couv,
            "jours_recent": JOURS_RECENT if jours > JOURS_RECENT else None,
            "n_recent": sum(1 for x in out if jours > JOURS_RECENT and x["fenetre"] == JOURS_RECENT),
            "fenetres": [f for f in FENETRES if f < jours] + [jours], "par_fenetre": {str(f): sum(1 for x in out if x["fenetre"] == f) for f in sorted({x["fenetre"] for x in out})},
            "frais_psa": fp, "frais_ebay": FRAIS_EBAY, "jours": jours, "le": datetime.now().isoformat(timespec="seconds"),
            "regles": {"raw_min": RAW_MIN, "p10_min": P10_MIN, "p9_min": P9_MIN}}


# -- sur le serveur ------------------------------------------------------------------------------------------------------
def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "a_grader.json")


def _ventes_serveur(jours=JOURS):
    """Les ventes a ranger : toute la collecte PSA (banque_psa), puis nos archives pour les memes joueurs (leurs recherches
    commencent par leur nom : « connor bedard young guns »...). Une vente vue deux fois ne compte qu'une fois (analyser)."""
    import banque_psa
    d_min = (datetime.now(timezone.utc).date() - timedelta(days=jours)).isoformat()
    joueurs = {}
    # 26 nov 2026, 14 h 58 (journal : la collecte PSA morte sur « database is locked » 22 s apres le depart de ce calcul) : la base
    # de la collecte n'est JAMAIS tenue ouverte pendant le calcul (un curseur ouvert pendant des minutes bloquait ses ecritures).
    # On lit par blocs de 5 000 ventes, une connexion courte par bloc (la suite : apres le dernier rowid lu).
    def bloc(sql, args):
        c = banque_psa._cx()
        try:
            return c.execute(sql, args).fetchall()
        finally:
            c.close()
    try:
        for q, j in bloc("SELECT q, joueur FROM plan WHERE phase=1 AND joueur IS NOT NULL", ()):
            joueurs.setdefault(j, q.rsplit(" psa ", 1)[0])
        dernier = 0
        while True:
            rows = bloc("SELECT rowid, cle, titre, prix, le, joueur FROM ventes WHERE rowid > ? AND le >= ? ORDER BY rowid LIMIT 5000", (dernier, d_min))
            if not rows:
                break
            dernier = rows[-1][0]
            for r in rows:
                yield r[1:]
    except sqlite3.Error as e:
        print("A grader (collecte PSA) : " + repr(e)[:120], flush=True)
    if not joueurs:                                           # la collecte n'a pas commence : les joueurs du haut de l'indice
        try:
            joueurs = {n: banque_psa._mots_joueur(n) for n in banque_psa.joueurs_cibles()}
        except Exception:
            joueurs = {}
    try:
        import base_ventes
        for j, mots in joueurs.items():
            if len(mots.split()) < 2:
                continue
            c = base_ventes._cx()                             # une connexion courte par joueur : rien n'est tenu pendant le calcul
            try:
                rows = c.execute("SELECT cle, titre, prix, le FROM ventes WHERE q >= ? AND q < ? AND le >= ? AND prix > 0",
                                 (mots + " ", mots + "!", d_min)).fetchall()                # « ! » suit l'espace : les recherches « <joueur> ... »
            finally:
                c.close()
            for cle, titre, prix, le in rows:
                yield cle, titre, prix, le, j
    except Exception as e:
        print("A grader (archives) : " + repr(e)[:120], flush=True)


def _cle_vente(cle):
    """Le numero de l'annonce eBay quand la cle est un lien (nos archives), sinon la cle telle quelle (la collecte PSA) : la meme
    vente trouvee des deux cotes ne compte qu'une fois."""
    m = re.search(r"(\d{9,14})(?!.*\d{9,14})", str(cle or ""))
    return m.group(1) if m else str(cle or "")


def calculer():
    """Refait la liste (plusieurs minutes : des centaines de milliers de titres), la garde. Aucun credit, aucun appel."""
    t0 = time.time()
    def respirer(i):
        time.sleep(0.01)                                      # le serveur respire
        if i % 20000 == 19999:
            ETAT["texte"] = f"{i + 1} ventes lues"
    r = analyser(((_cle_vente(c), t, p, le, j) for c, t, p, le, j in _ventes_serveur()), respirer=respirer)
    r["secondes"] = round(time.time() - t0)
    ch = _chemin()
    with open(ch + ".tmp", "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False)
    os.replace(ch + ".tmp", ch)
    print(f"A grader : {r['n_cartes']} cartes ({r['lues']} ventes lues, {r['rangees']} rangees, {r['secondes']} s)", flush=True)
    try:
        if r.get("raw_gradees") or (r.get("ecartees") or {}).get("raw melangee a des gradees"):
            print(f"A grader : {r.get('raw_gradees') or 0} ventes « raw » au prix de la PSA 10 jetees (gradees sans note dans le titre) ; "
                  f"{(r.get('ecartees') or {}).get('raw melangee a des gradees') or 0} cartes sorties (trop peu de vraies raw)", flush=True)
        if r.get("par_fenetre"):
            print("A grader : periode mesuree : " + ", ".join(f"{k} jours {v} cartes" for k, v in r["par_fenetre"].items()), flush=True)
        cv = r.get("couverture") or {}
        for n in ("10", "9"):
            x = cv.get(n) or {}
            if x.get("lues"):
                pq = ", ".join(f"{k} {v}" for k, v in list((x.get("raisons") or {}).items())[:6])
                print(f"A grader : PSA {n} : {x['rangees']} ventes rangees sur {x['lues']} ({100 * x['rangees'] // x['lues']} %)" + (" ; le reste : " + pq if pq else "")
                      + (f" ; dont {x['par_numero']} rangees par leur numero (titre « etiquette PSA »)" if x.get("par_numero") else "")
                      + (f" ; hors mesure, {x['autre_joueur']} ventes d'un autre joueur" if x.get("autre_joueur") else ""), flush=True)
        if cv.get("sortes_inconnues"):
            print("A grader : mots des PSA 10 sans sorte reconnue : " + ", ".join(f"{d} {n}" for d, n in cv["sortes_inconnues"]), flush=True)
        print("A grader : cartes vues en PSA 10 hors de la liste : " + ", ".join(f"{k} {v}" for k, v in (r.get("ecartees") or {}).items()), flush=True)
        if (cv.get("etiquettes") or {}).get("vues"):
            print("A grader : titres « etiquette PSA » (sans le nom de la sorte) : " + ", ".join(f"{k} {v}" for k, v in cv["etiquettes"].items()), flush=True)
        for d, ex in list((cv.get("exemples") or {}).items())[:N_INCONNUES]:
            if ex:
                print(f"A grader : ex. « {d} » : " + " | ".join(ex), flush=True)
        if cv.get("exemples_lot"):
            print("A grader : ex. « lot ou autre carte » : " + " | ".join(cv["exemples_lot"]), flush=True)
    except Exception as e:
        print("A grader (couverture) : " + repr(e)[:120], flush=True)
    return r


def lire():
    ch = _chemin()
    try:
        mt = os.path.getmtime(ch)
    except OSError:
        return {}
    with _verrou:
        if _MEM["v"] is not None and _MEM["mtime"] == mt:
            return _MEM["v"]
    try:
        with open(ch, encoding="utf-8") as f:
            v = json.load(f) or {}
    except (OSError, ValueError):
        v = {}
    with _verrou:
        _MEM.update(mtime=mt, v=v)
    return v


def lancer():
    """L'admin demande la liste (ou la boucle du serveur, une fois par REFAIRE_H heures) : le calcul part en fond."""
    with _verrou:
        if ETAT["en_cours"]:
            return {"ok": True, "deja": True}
        ETAT.update(en_cours=True, texte="Démarrage")
    def tache():
        try:
            calculer()
        except Exception as e:
            print("A grader : " + repr(e)[:200], flush=True)
        finally:
            ETAT.update(en_cours=False, texte=None)
    threading.Thread(target=tache, daemon=True, name="a-grader").start()
    return {"ok": True, "lancee": True}


def refaire_si_besoin():
    """La boucle du serveur : la liste est refaite chaque semaine, et une fois quand la collecte PSA vient de finir (ses ventes
    sont plus recentes que la liste). Jamais sans ventes collectees (l'admin peut alors la demander lui-meme)."""
    if ETAT["en_cours"]:
        return None
    try:
        mt = os.path.getmtime(_chemin())
    except OSError:
        mt = None
    try:
        import banque_psa
        b = banque_psa._run()
        if not banque_psa.bilan().get("ventes"):
            return None
    except Exception:
        return None
    finie_apres = mt is not None and b.get("statut") == "terminee" and (b.get("battement") or 0) > mt
    # 26 nov 2026 : la liste de 15 h 02 datait d'AVANT les recherches raw de la collecte (presque seulement des Young Guns, la
    # seule sorte dont on avait deja les raw) et serait restee telle quelle jusqu'a la fin. Pendant une collecte, elle suit :
    # refaite a chaque tour de la boucle (une fois l'heure), sans que personne clique.
    suit = mt is not None and b.get("statut") == "en_cours" and time.time() - mt >= REFAIRE_COLLECTE_MIN * 60
    # 26 nov 2026 : une regle de calcul change (les 60 derniers jours) : sans ca, la liste gardait l'ancienne mesure jusqu'a la
    # semaine suivante. Une liste faite par une autre VERSION est refaite au premier tour de la boucle, une seule fois.
    vieille_regle = mt is not None and lire().get("version") != VERSION
    if mt is not None and time.time() - mt < REFAIRE_J * 86400 and not finie_apres and not suit and not vieille_regle:
        return None
    return lancer()


def top_tendances():
    """Pour l'onglet « A grader » de Trending (ADMIN seulement pour l'instant : la liste porte des prix) : les N_TOP premieres."""
    v = lire()
    return {"cartes": (v.get("cartes") or [])[:N_TOP], "n": v.get("n_cartes") or 0, "le": v.get("le"), "jours": v.get("jours") or JOURS,
            "jours_recent": v.get("jours_recent"), "frais_psa": v.get("frais_psa") or frais_psa(), "semaine": REFAIRE_J}


def page():
    """Pour l'admin : la liste, son age, et si un calcul tourne."""
    v = lire()
    return {"ok": True, "en_cours": ETAT["en_cours"], "texte": ETAT["texte"], "cartes": v.get("cartes") or [], "n_cartes": v.get("n_cartes") or 0,
            "lues": v.get("lues"), "rangees": v.get("rangees"), "ecartees": v.get("ecartees") or {}, "le": v.get("le"),
            "frais_psa": v.get("frais_psa") or frais_psa(), "frais_ebay": FRAIS_EBAY, "jours": v.get("jours") or JOURS,
            "jours_recent": v.get("jours_recent"), "n_recent": v.get("n_recent"), "fenetres": v.get("fenetres"), "par_fenetre": v.get("par_fenetre"),
            "regles": v.get("regles") or {"raw_min": RAW_MIN, "p10_min": P10_MIN, "p9_min": P9_MIN}}
