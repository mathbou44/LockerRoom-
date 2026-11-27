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
VERSION = 6                          # 2 = la regle des 60 derniers jours (26 nov) ; 3 = les titres ecrits comme l'etiquette PSA ; 4 = 12 mois, les fausses raw jetees ; 5 = la pastille « A grader » (27 nov) ;
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

# 27 nov 2026, 11 h 24 (Mathieu : « dans notre tableau trend ou si on a une pastille dans Radar, il faut vraiment, mais vraiment que ce
# soit tres, tres simple pour le end user de comprendre rapidement qu'est-ce qui est a grader ou non. On peut meme mettre cette
# pastille-la dans les cartes en inventaire, pas encore sur eBay, pour que la personne decide si elle l'affiche non gradee ou
# l'envoie grader si elle est assez belle »). UNE pastille, « A grader » : elle y est ou elle n'y est pas.
# La regle (une seule, la meme partout ; mesuree sur la liste du 27 nov : 207 cartes sur 495) :
#   - si elle revient PSA 10, il reste au moins PASTILLE_PROFIT $ une fois tout paye (la carte, PSA, eBay) ;
#   - ET le risque est petit : il suffit d'au plus 1 dix sur 4 pour ne pas perdre (le seuil, calcule avec le vrai prix de la PSA 9) ;
#   - la PSA 9 pas mesuree (trop peu de ventes) : seulement si un 10 rapporte au moins PASTILLE_SANS9 fois la mise.
# Toujours aucune chance de 10 supposee : le seuil dit ce qu'il FAUT, pas ce qui arrivera.
PASTILLE_SEUIL = 0.25
PASTILLE_PROFIT = 40.0
PASTILLE_SANS9 = 3.0

# ---- VERSION 6 (27 nov 2026, 17 h 17 ; Mathieu : « on doit etre parfait sur tous les parametres avec les cartes a grader [...] Je veux
# le mettre dans la version Pro avec confiance ») : la regle rejouee dans le passe (au 1er de chaque mois, juin 2024 -> avril 2026,
# seulement les ventes d'avant), jugee avec les VRAIS prix 5 a 8 mois plus tard (le delai PSA d'aujourd'hui). Ce que ca a change :
#   1. LES VRAIS FRAIS. PSA Value au Canada : 56,99 $ CA par carte (rouvert le 29 oct 2026, 90-100 jours ouvrables, assurance max
#      500 $ US) ; au-dela, Standard 59,99 $ US (1 000 $), Priority 79,99 $ US (1 500 $), Express 199 $ US (2 500 $) ; la taxe sur le
#      service ; l'envoi aller-retour ; la raw achetee : port + TPS/TVQ ; la revente : les frais de l'app (deals.net_revente).
#      Avant : 41 $ en tout, sans taxe ni port. Avec les vrais frais, une PSA 9 ne paie presque jamais : on grade pour un 10.
#   2. LES PSA 8. Le decodeur ne les rangeait pas ; mesurees : une PSA 8 se vend au prix de la raw (mediane 0,98). Une carte qui ne
#      sort pas 10 vaut une 9 ou une 8 dans la proportion vendue de cette carte (avant : toujours une 9). « 1 dix sur 4 suffit »
#      n'etait vrai au retour que 28 a 42 % du temps avec les vrais frais.
#   3. LES CARTES NEUVES (premiere vente il y a moins de 6 mois) : leur PSA 10 vaut 0,77 a 0,85 de son prix au retour : x 0,80.
#   4. LA CONFIANCE PAR CARTE : la chance que la promesse tienne au retour (si elle sort 10 elle rapporte, ET il faut au plus 1 dix
#      sur 2 pour ne pas perdre), apprise sur toutes les cartes mesurees (regression logistique + arbres, modeles/a_grader_confiance.json).
#      Mois gardes de cote (oct 2025 -> avr 2026), modele appris sans eux : confiance >= 85 % -> la promesse a tenu 95 % du temps
#      (borne basse 89 %, 26 cartes) pour un acheteur, 96 % (borne basse 92 %, 48 cartes) pour une carte deja a soi.
FX_USD = 1.425                                # $ CA pour 1 $ US (nov 2026)
PSA_PALIERS = ((500 * FX_USD, 56.99), (1000 * FX_USD, 59.99 * FX_USD), (1500 * FX_USD, 79.99 * FX_USD), (2500 * FX_USD, 199 * FX_USD), (1e12, 349 * FX_USD))
ENVOI_PSA = 8.0                               # $ CA par carte : l'envoi a PSA et le retour, en lot
PORT_ACHAT = 6.0                              # $ CA : le port de la raw achetee
NEUF_J, NEUF_FACTEUR = 180, 0.80
P8_DEFAUT = 0.85                              # PSA 8 pas mesuree : 85 % de la raw
P8_MIN = 3
PROMESSE = 0.5                                # il faut au plus 1 dix sur 2
CONFIANCE_MIN = 0.85
# 5. LE GARDE-FOU DE LA CHANCE (27 nov, 18 h) : la confiance juge les PRIX, pas la chance d'un 10. Une Gretzky 1987 O-Pee-Chee (raw 22 $,
#    PSA 10 2 543 $) avait 98 % de confiance alors que 8 % seulement de ses gradees vendues sont des 10. La part de 10 qu'il faut ne doit
#    pas depasser CHANCE_REALISTE x la part des 10 parmi les gradees vendues de la carte (reduite : on revend plus souvent un 10 qu'un 8,
#    comme grader.py). Mois gardes : la promesse a tenu 97 % (acheteur, borne basse 89 %) et 99 % (deja a soi, borne basse 98 %).
CHANCE_REALISTE = 0.7
VARIABLES = ("marge9", "seuil", "marge10", "cout", "marge_n10", "age", "n10", "c10", "et10", "et_raw", "elan", "part10", "part9", "fenetre",
             "a9", "elan_joueur", "n_cartes_joueur", "saisons", "young_guns")
_MODELE = {"v": None, "essaye": False}


def _taxe():
    import deals
    return deals.TAXE_ACHAT


def _net(v):
    import deals
    return deals.net_revente(v)


def frais_psa_de(v10):
    """PSA pour une carte dont la PSA 10 vaut v10 ($ CA) : le palier qu'il faut, la taxe sur le service, l'envoi."""
    f = next(fr for cap, fr in PSA_PALIERS if v10 <= cap)
    return f * (1 + _taxe()) + ENVOI_PSA


def regle(x, proprio=False):
    """Une carte mesuree -> ce qu'elle rapporte si elle sort 10, si elle sort 9, et la part de 10 qu'il faut pour ne pas perdre.
    proprio : la carte est deja a soi (l'inventaire) : elle « coute » ce qu'on aurait en la vendant raw ; sinon on l'achete (port, taxes)."""
    d = NEUF_FACTEUR if (x.get("age_j") or 0) < NEUF_J else 1.0
    raw = float(x["raw"]); v10 = float(x["psa10"]) * d
    v9 = float(x["psa9"]) * d if x.get("psa9") else None
    v8 = min(float(x["psa8"]) * d if x.get("psa8") else raw * P8_DEFAUT, raw * 1.5)
    a9, a8 = x.get("c9") or 0, (x.get("c8") or 0) + (x.get("c7") or 0)
    s9 = a9 / (a9 + a8) if a9 + a8 >= 5 else 0.5
    vn = (s9 * v9 + (1 - s9) * v8) if v9 is not None else v8
    c = (_net(raw) if proprio else (raw + PORT_ACHAT) * (1 + _taxe())) + frais_psa_de(v10)
    r10, rn = _net(v10) - c, _net(vn) - c
    s = 0.0 if rn >= 0 else (9.9 if r10 <= 0 else -rn / (r10 - rn))
    return {"cout": c, "v10": v10, "vn": vn, "r10": r10, "r9": (_net(v9) - c) if v9 is not None else None, "seuil": s}


def variables(x, proprio=False, auj=None):
    """Les variables de la confiance (dans l'ordre de VARIABLES ; les memes que l'apprentissage)."""
    import math
    r = regle(x, proprio); c = r["cout"]
    r9 = r["r9"] if r["r9"] is not None else -999
    a9, a8 = x.get("c9") or 0, (x.get("c8") or 0) + (x.get("c7") or 0)
    n = (x.get("c10") or 0) + a9 + a8
    p10 = float(x["psa10"])
    auj = str(auj or x.get("auj") or datetime.now(timezone.utc).date().isoformat())
    saisons = min(max(int(auj[:4]) - int(x.get("annee") or auj[:4]) - (auj[5:7] < "09"), 0), 10) / 10
    return [math.copysign(math.log1p(abs(max(r9, -500)) / 10), r9), min(r["seuil"], 1.5), math.log(max(_net(r["v10"]), 1) / c), math.log(c),
            math.log(max(_net(r["vn"]), 1) / c), min(x.get("age_j") or 0, 365) / 365, math.log1p(x.get("n10") or 0), math.log1p(x.get("c10") or 0),
            float(x.get("et10") or 1.0), float(x.get("et_raw") or 1.0), math.log((x.get("p10_90") or p10) / (x.get("p10_365") or p10)),
            (x.get("c10") or 0) / n if n else 0.0, a9 / (a9 + a8) if a9 + a8 else 0.5, (x.get("fenetre") or JOURS) / 365, 1.0 if x.get("psa9") else 0.0,
            float(x.get("elan_j") or 0.0), math.log(max(1, x.get("n_j") or 1)), saisons, 1.0 if "young guns" in str(x.get("q") or "") else 0.0]


def _modele():
    """Le modele de confiance (texte, jamais pickle) : {« achat » | « proprio » : (moyennes, ecarts, poids, biais, [arbres])}."""
    if _MODELE["essaye"]:
        return _MODELE["v"]
    _MODELE["essaye"] = True
    try:
        import lightgbm as lgb
        import numpy as np
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "modeles", "a_grader_confiance.json"), encoding="utf-8") as f:
            m = json.load(f)
        assert tuple(m["variables"]) == VARIABLES
        _MODELE["v"] = {k: (np.array(v["mu"]), np.array(v["sd"]), np.array(v["coef"]), float(v["biais"]), [lgb.Booster(model_str=t) for t in v["arbres"]])
                        for k, v in m["modeles"].items()}
    except Exception as e:
        print("A grader (modele de confiance) : " + repr(e)[:160], flush=True)
    return _MODELE["v"]


def confiance(x, proprio=False, auj=None):
    """La chance (0 a 1) que la promesse tienne quand la carte reviendra de PSA ; None sans modele."""
    M = _modele()
    if not M:
        return None
    import numpy as np
    mu, sd, w, b, arbres = M["proprio" if proprio else "achat"]
    X = np.array([variables(x, proprio, auj)], dtype=float)
    lr = 1 / (1 + np.exp(-(((X - mu) / sd) @ w + b)))
    return float((lr[0] + np.mean([a.predict(X)[0] for a in arbres])) / 2)


def _part10(x):
    n = sum(int(x.get(k) or 0) for k in ("c10", "c9", "c8", "c7"))
    return round(int(x.get("c10") or 0) / n, 3) if n else 0.0


def pourquoi_non(e):
    """Une carte mesuree SANS pastille (sa forme courte, _compact) -> « gain » (un 10 ne rapporte pas 40 $), « confiance » (pas
    assez sur que ca tienne au retour) ou « chance » (il faudrait plus de 10 que cette carte n'en donne)."""
    if not e or e.get("ok"):
        return None
    if e.get("g10") is None or float(e["g10"]) < PASTILLE_PROFIT or e.get("s") is None:
        return "gain"
    if e.get("c") is None or float(e["c"]) < CONFIANCE_MIN:
        return "confiance"
    return "chance"


def vaut_grader(x, proprio=False):
    """Une carte mesuree de la liste -> True si elle porte la pastille « A grader » : si elle sort 10, il reste au moins
    PASTILLE_PROFIT $, la confiance que la promesse tienne au retour est d'au moins CONFIANCE_MIN, et la part de 10 qu'il faut reste
    realiste (CHANCE_REALISTE x la part des 10 parmi les gradees vendues de la carte)."""
    try:
        r10 = x.get("reste10_p" if proprio else "reste10")
        c = x.get("conf_p" if proprio else "conf")
        s = x.get("seuil_p" if proprio else "seuil")
        n = sum(int(x.get(k) or 0) for k in ("c10", "c9", "c8", "c7"))
        part10 = int(x.get("c10") or 0) / n if n else 0.0
        return (r10 is not None and c is not None and s is not None and float(r10) >= PASTILLE_PROFIT and float(c) >= CONFIANCE_MIN
                and float(s) <= CHANCE_REALISTE * part10)
    except (TypeError, ValueError):
        return False


def _compact(x):
    """Ce que la pastille garde d'une carte (pour la retrouver par un titre, et l'expliquer en une ligne)."""
    return {"j": x.get("cle_joueur"), "q": x.get("q"), "an": x.get("annee"), "se": x.get("serie"), "num": x.get("num"), "joueur": x.get("joueur"), "nom": x.get("nom"),
            "r": x.get("rendement"), "s": x.get("seuil"), "raw": x.get("raw"), "p10": x.get("psa10"), "p9": x.get("psa9"), "g10": x.get("reste10"), "g9": x.get("reste9"),
            "jours": x.get("jours"), "ok": bool(x.get("grader") if "grader" in x else vaut_grader(x)),
            "c": x.get("conf"), "cp": x.get("conf_p"), "g10p": x.get("reste10_p"), "sp": x.get("seuil_p"), "rp": x.get("rendement_p"), "pt": _part10(x),
            "okp": bool(x.get("grader_p") if "grader_p" in x else vaut_grader(x, proprio=True))}

# une carte gradee que le decodeur laisse sans note (PSA 8 et moins, une compagnie rare) : jamais comptee comme une raw
_RE_GRADEE = re.compile(r"\b(psa|bgs|bvg|sgc|cgc|csg|tag|beckett|ksa|hga|gma|mnt|isa|aca|bccg|ags|rcg)\s*\d|\b(graded|slab|slabbed|gradee?)\b", re.I)


def frais_psa():
    """v6 : ce que coute PSA pour une carte au palier Value (56,99 $ CA), taxe sur le service et envoi compris (a l'ecran)."""
    return round(frais_psa_de(0), 2)


# la mesure de la couverture (voir analyser) : le titre DIT-il PSA 10 ou PSA 9 ? et les mots d'un titre qui peuvent nommer une sorte
_RE_NOTE_TITRE = re.compile(r"\bpsa[\s\-]*(10|9)(?![\d.])", re.I)
_RE_NOTE_BAS = re.compile(r"\bpsa[\s\-]*(8|7)(?![\d.])", re.I)       # v6 : les PSA 8 et 7 (le decodeur ne les range pas)
_RE_AUTRE_CIE = re.compile(r"\b(bgs|bvg|sgc|cgc|csg|tag|beckett|ksa)\b", re.I)
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
            # v6 : une PSA 8 ou 7 : le titre lu comme une PSA 9 pour trouver LA carte (un lot « PSA 7 PSA 8 » ou une autre compagnie : non)
            t8 = str(titre or "")
            m8 = _RE_NOTE_BAS.search(t8)
            if m8 and not _RE_AUTRE_CIE.search(t8) and len({z.group(1) for z in _RE_NOTE_BAS.finditer(t8)}) == 1:
                try:
                    r8 = classer(_RE_NOTE_BAS.sub("PSA 9", t8), joueur)
                except Exception:
                    r8 = None
                if r8 and r8[1] == "9":
                    cartes.setdefault(r8[0], {"raw": [], "10": [], "9": [], "8": [], "7": []})[m8.group(1)].append((le, float(prix)))
            continue
        rangees += 1
        cartes.setdefault(r[0], {"raw": [], "10": [], "9": [], "8": [], "7": []})[r[1]].append((le, float(prix)))
        if joueur:
            noms.setdefault(r[0][0], joueur)
    # une vente sans annee (ou sans numero) dans son titre : a la saison (au numero) de la carte s'il n'y en a qu'une (90 % des
    # ventes qui la disent), sinon ecartee. D'abord l'annee (parmi les ventes du meme numero quand elle en a un), puis le numero
    # (parmi les ventes de la meme saison).
    vide = lambda: {"raw": [], "10": [], "9": [], "8": [], "7": []}
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
        # v6 (voir regle) : la PSA 8, combien de chaque note en 12 mois, l'etalement, la PSA 10 des 90 derniers jours, l'age de la carte
        h8 = [p for d, p in g["8"] if d >= d0]
        d90 = (auj - timedelta(days=90)).isoformat()
        r90 = [p for d, p in g["10"] if d >= d90]
        tous10 = [p for _, p in g["10"]]
        prem = min(d for k in g for d, _ in g[k])
        sorte = " ".join(w for w in q.split() if w not in set(j.split()))
        x = {"joueur": noms.get(j) or beau_nom(j), "cle_joueur": j, "q": q, "nom": ts.libelle(sorte), "annee": an, "serie": se, "num": num,
             "raw": round(m_raw, 2), "psa10": round(m10, 2), "psa9": round(m9, 2) if m9 is not None else None,
             "psa8": round(statistics.median(h8), 2) if len(h8) >= P8_MIN else None,
             "n_raw": len(raw), "n10": len(p10), "n9": len(p9), "n8": len(h8), "rapport": round(m10 / m_raw, 2),
             "c10": len(g["10"]), "c9": len(g["9"]), "c8": len(g["8"]), "c7": len(g["7"]), "et_raw": round(_etale(raw), 4), "et10": round(_etale(p10), 4),
             "p10_90": statistics.median(r90) if len(r90) >= 3 else None, "p10_365": statistics.median(tous10) if len(tous10) >= 3 else None,
             "age_j": (auj - datetime.strptime(prem, "%Y-%m-%d").date()).days, "auj": auj.isoformat(),
             "du": d0, "jours": (auj - datetime.strptime(d0, "%Y-%m-%d").date()).days, "fenetre": fenetre}
        a, b = regle(x), regle(x, proprio=True)
        x.update(rendement=round(_net(a["v10"]) / a["cout"], 2), cout=round(a["cout"], 2), reste10=round(a["r10"], 2),
                 reste9=round(a["r9"], 2) if a["r9"] is not None else None, seuil=None if a["seuil"] >= 9 else round(a["seuil"], 3),
                 reste10_p=round(b["r10"], 2), seuil_p=None if b["seuil"] >= 9 else round(b["seuil"], 3), rendement_p=round(_net(b["v10"]) / b["cout"], 2))
        out.append(x)
    # v6 : l'elan du JOUEUR (la mediane, sur ses cartes mesurees, de sa PSA 10 des 90 derniers jours contre 12 mois), puis la confiance
    import math
    elan = {}
    for x in out:
        elan.setdefault(x["cle_joueur"], []).append(math.log((x["p10_90"] or x["psa10"]) / (x["p10_365"] or x["psa10"])))
    for i, x in enumerate(out):
        if respirer and i % 50 == 49:
            respirer(i)
        x["elan_j"], x["n_j"] = round(float(statistics.median(elan[x["cle_joueur"]])), 5), len(elan[x["cle_joueur"]])
        cf, cp = confiance(x), confiance(x, proprio=True)
        x["conf"], x["conf_p"] = (round(cf, 3) if cf is not None else None), (round(cp, 3) if cp is not None else None)
    out.sort(key=lambda x: (-x["rendement"], -x["reste10"]))
    for x in out:
        x["grader"], x["grader_p"] = vaut_grader(x), vaut_grader(x, proprio=True)
    for n in ("10", "9"):
        couv[n]["raisons"] = dict(sorted(couv[n]["raisons"].items(), key=lambda x: -x[1]))
    couv["sortes_inconnues"] = [[d, n] for d, n in sorted(mots_inconnus.items(), key=lambda x: (-x[1], x[0]))[:N_INCONNUES] if n >= 3]
    couv["exemples"] = {d: ex_duo.get(d) or [] for d, _ in couv["sortes_inconnues"]}
    couv["exemples_lot"] = ex_lot
    return {"version": VERSION, "cartes": out[:N_LISTE], "n_cartes": len(out), "index": [_compact(x) for x in out[:5000]], "n_grader": sum(1 for x in out if x["grader"]), "lues": lues, "rangees": rangees, "ecartees": ecartees, "raw_gradees": raw_gradees, "couverture": couv,
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
    journal(r)
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


def journal(r):
    """27 nov 2026 (la pastille ouverte a Pro ; la condition du rapport de confiance) : chaque liste calculee garde ses pastilles
    (la carte, la confiance, les prix du jour) dans DONNEES/a_grader_journal.jsonl, pour les juger 6 a 8 mois plus tard avec les
    vraies ventes : si la promesse tombe sous 85 % pendant 3 mois, la pastille retourne en admin. Une ligne par carte, une fois par jour."""
    try:
        le = datetime.now(timezone.utc).date().isoformat()
        ch = os.path.join(os.path.dirname(_chemin()), "a_grader_journal.jsonl")
        if os.path.exists(ch) and os.path.getsize(ch) > 50_000_000:
            return
        with open(ch, "a", encoding="utf-8") as f:
            for x in r.get("cartes") or []:
                if x.get("grader") or x.get("grader_p"):
                    f.write(json.dumps({"le": le, "v": VERSION, "j": x.get("cle_joueur"), "q": x.get("q"), "an": x.get("annee"), "se": x.get("serie"), "num": x.get("num"),
                                        "raw": x.get("raw"), "p10": x.get("psa10"), "p9": x.get("psa9"), "p8": x.get("psa8"), "s": x.get("seuil"), "sp": x.get("seuil_p"),
                                        "c": x.get("conf"), "cp": x.get("conf_p"), "a": bool(x.get("grader")), "p": bool(x.get("grader_p"))}, ensure_ascii=False) + "\n")
    except Exception as e:
        print("A grader (journal) : " + repr(e)[:120], flush=True)


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


PRIX_LISTE = ("raw", "psa10", "psa9", "psa8", "reste10", "reste9", "reste10_p", "cout", "p10_90", "p10_365")


def pour_niveau(t, niveau):
    """27 nov 2026 (Mathieu : « go pousse tout dans Pro, Platine et admin ; pour le free on doit limiter ») : l'onglet « A grader »
    selon le forfait. « comps » (admin, Platine) : tout ; « pro » : la liste SANS AUCUN PRIX (regle des comps) ; « gratuit » : le
    nombre de cartes seulement, le reste verrouille (Passe a Pro)."""
    if niveau == "comps":
        return t
    if niveau == "pro":
        return {**{k: v for k, v in t.items() if k != "frais_psa"}, "cartes": [{k: v for k, v in x.items() if k not in PRIX_LISTE} for x in t.get("cartes") or []]}
    return {"cartes": [], "verrou": True, "n_grader": t.get("n_grader") or len(t.get("cartes") or []), "n": t.get("n"), "le": t.get("le")}


def top_tendances():
    """Pour l'onglet « A grader » de Trending (ADMIN seulement pour l'instant : la liste porte des prix) : les N_TOP premieres."""
    v = lire()
    # 27 nov 2026 : l'onglet ne montre plus que les cartes qui portent la pastille (avant : les 100 meilleurs rendements, dont des
    # cartes ou il faut beaucoup de 10 pour ne pas perdre). Une liste d'avant la pastille : la regle est appliquee a la lecture.
    bonnes = [x for x in (v.get("cartes") or []) if (x.get("grader") if "grader" in x else vaut_grader(x))]
    return {"cartes": bonnes[:N_TOP], "n": v.get("n_cartes") or 0, "n_grader": v.get("n_grader") if v.get("n_grader") is not None else len(bonnes), "le": v.get("le"), "jours": v.get("jours") or JOURS,
            "jours_recent": v.get("jours_recent"), "frais_psa": v.get("frais_psa") or frais_psa(), "semaine": REFAIRE_J}


_IDX = {"mtime": None, "d": None, "joueurs": (), "titres": {}}


def _index():
    """Les cartes qui portent la pastille, rangees par (joueur, recherche, /N) ; refait quand la liste change."""
    v = lire()
    with _verrou:
        mt = _MEM["mtime"]
        if _IDX["d"] is not None and _IDX["mtime"] == mt:
            return _IDX["d"]
    L = v.get("index")
    if L is None:                                             # une liste d'avant la pastille : ses 200 premieres cartes
        L = [_compact(x) for x in (v.get("cartes") or [])]
    d = {}
    for e in L:
        if e.get("j") and e.get("q"):
            d.setdefault((e["j"], e["q"], e.get("se")), []).append(e)
    with _verrou:
        _IDX.update(mtime=mt, d=d, joueurs=tuple(sorted({k[0] for k in d})), titres={})
    return d


def pastille(titre, joueur=None, proprio=False):
    """La carte de la liste qui porte la pastille « A grader » (voir mesure), ou None. proprio : une carte deja a soi (l'inventaire)."""
    e = mesure(titre, joueur)
    return e if e and e.get("okp" if proprio else "ok", True) else None


def mesure(titre, joueur=None):
    """Le titre d'une carte NON gradee (une annonce du Radar, une carte de l'inventaire) -> la carte MESUREE de la liste
    (qu'elle porte la pastille ou non : e["ok"]), ou None. Jamais au hasard : il faut le meme joueur, la meme sorte, le meme tirage ; la saison et le
    numero du titre doivent concorder ; un titre sans saison ne passe que si le joueur n'a qu'UNE carte de cette sorte."""
    t = re.sub(r"\s+", " ", str(titre or "")).strip()
    if len(t) < 8:
        return None
    d = _index()
    if not d:
        return None
    cle = (t, str(joueur or ""))
    with _verrou:
        if cle in _IDX["titres"]:
            return _IDX["titres"][cle]
    r = None
    bas = (t + " " + str(joueur or "")).lower()
    if any(j.split()[-1] in bas for j in _IDX["joueurs"]):   # vite : le nom de famille d'un joueur de la liste est la
        try:
            c = classer(t, joueur)
        except Exception:
            c = None
        if c and c[1] == "raw":
            j, q, an, se, num = c[0]
            L = d.get((j, q, se)) or []
            if an is not None:
                L = [e for e in L if e.get("an") == an]
            if num is not None:
                L = [e for e in L if e.get("num") in (None, num)]
            if len(L) == 1:
                r = L[0]
    with _verrou:
        if len(_IDX["titres"]) > 30000:
            _IDX["titres"].clear()
        _IDX["titres"][cle] = r
    return r


def pour_client(e, prix=False, verrou=False):
    """Ce que l'app recoit pour une pastille : le rendement et le seuil ; les prix seulement pour l'admin (regle des comps).
    verrou (27 nov 2026, un compte gratuit) : la pastille seule ; la toucher ouvre « Passe a Pro »."""
    if not e:
        return None
    if verrou:
        return {"verrou": True, "nom": e.get("nom"), "joueur": e.get("joueur"), "an": e.get("an")}
    o = {"r": e.get("r"), "s": e.get("s"), "c": e.get("c"), "jours": e.get("jours"), "nom": e.get("nom"), "joueur": e.get("joueur"), "an": e.get("an")}
    if prix:
        o.update(raw=e.get("raw"), p10=e.get("p10"), p9=e.get("p9"), g10=e.get("g10"))
    return o


def page():
    """Pour l'admin : la liste, son age, et si un calcul tourne."""
    v = lire()
    return {"ok": True, "en_cours": ETAT["en_cours"], "texte": ETAT["texte"], "cartes": v.get("cartes") or [], "n_cartes": v.get("n_cartes") or 0,
            "lues": v.get("lues"), "rangees": v.get("rangees"), "ecartees": v.get("ecartees") or {}, "le": v.get("le"),
            "frais_psa": v.get("frais_psa") or frais_psa(), "frais_ebay": FRAIS_EBAY, "jours": v.get("jours") or JOURS,
            "jours_recent": v.get("jours_recent"), "n_recent": v.get("n_recent"), "fenetres": v.get("fenetres"), "par_fenetre": v.get("par_fenetre"),
            "regles": v.get("regles") or {"raw_min": RAW_MIN, "p10_min": P10_MIN, "p9_min": P9_MIN}}
