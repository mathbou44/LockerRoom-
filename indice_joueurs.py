"""
SLABCOACH - l'Indice joueur de la semaine (10 nov 2026).

Mathieu : « les stats de chacune des ligues pour voir les meilleurs joueurs, ceux qui ont les meilleures ascensions depuis
une semaine ; si un joueur a 6 buts cette semaine il tombe tres haut (les scores sont reattribues chaque semaine) ; les effets
legendes (Crosby, Ovechkin…), actifs, non actifs ; une base qui prend en consideration tous les facteurs qui peuvent
influencer la popularite d'un joueur ». 100 % legal : AUCUNE donnee eBay ici (licence eBay §9.5) - des stats (Highlightly,
usage commercial permis) et des donnees publiques (Wikipedia, notre catalogue). L'indice classe les JOUEURS ; il ne juge
jamais le prix d'une annonce.

Les criteres (chacun en rang 0-100 parmi les joueurs du meme sport, recalcules chaque jour) :
  forme      : points des 7 derniers jours (difference des totaux de saison notes chaque jour), les buts comptent plus
  ascension  : points par match cette saison contre ses saisons d'avant (la « percee »)
  rythme     : points par match cette saison (un gardien : son temps de glace a defaut)
  buzz       : visites Wikipedia des 20 derniers jours contre la moyenne d'avant (un evenement : intronisation, record…)
  notoriete  : visites Wikipedia des 60 jours (le niveau)
  demande    : le score de demande legal (modele foret, valide sur nos ventes en admin)
  recrue     : recrue LNH cette saison (regle du Calder ; les cartes de recrue sont les plus suivies)
  legende    : Temple, top 100, trophees (ponderes), carriere ; plancher pour les legendes, actives ou non
Indice = melange pondere ; un joueur retire est note sur sa legende, son buzz et sa notoriete seulement.
Pastilles : « En creux » / « Sort de son creux » (11 nov : jeune talent sous ses standards), « En feu » (forme >= 95), « En hausse » (ascension >= 85), « Buzz » (buzz >= 90), « Legende », « Recrue ».

Appels Highlightly : 1 par joueur par jour (le total de saison). Forfait gratuit (90/jour) : les favoris des utilisateurs,
puis les plus demandes ; Pro (7 500/jour) : tout le monde, 4 sports.
"""
import reseau
import json
import math
import os
import re
import threading
import time
import unicodedata
from datetime import date, timedelta

POIDS_ACTIF = {"forme": 0.38, "ascension": 0.11, "rythme": 0.09, "buzz": 0.09, "notoriete": 0.05, "demande": 0.11,
               "recrue": 0.05, "legende": 0.05, "actu": 0.07, "communaute": 0.05,
               # 13 nov 2026 (Mathieu : « les equipes qui ont le plus d'acheteurs doivent avoir un score plus eleve ») : le
               # marche de son club (le plus de ventes de cartes dans nos archives = 100), americain ou canadien
               "marche": 0.08}
PIC_MOYEN, PIC_FORT = 2.6, 4.5     # 14 nov 2026 : le pic de visites (3 jours) qui compte (etude des evenements)
PIC_BONUS_MOYEN, PIC_BONUS_FORT, PIC_BONUS_EXPLOIT = 4.0, 8.0, 6.0
BONUS_FEU = 6                      # « 6 buts cette semaine = tres haut » : la semaine en feu passe devant tout le monde
POIDS_RETIRE = {"legende": 0.33, "buzz": 0.22, "notoriete": 0.33, "actu": 0.12, "communaute": 0.06}
ECHELLE_RETIRE = 0.85              # une semaine en feu passe devant ; une legende reste quand meme haut
GARDE_JOURS = 70
_verrou = threading.Lock()
_ETAT = {"le": 0.0, "en_cours": False, "d": None, "mt": None}

# -- 1c. le joueur qui change d'equipe (14 nov 2026) ----------------------------------------------------------------------
# Mathieu : « Matthew Knies : un bon joueur des Leafs echange en debut de saison a Columbus ; la valeur de ses cartes a
# drastiquement diminue ; SlabIQ aurait du le capter ». Etude sur nos ventes (mai-oct 2026, niveau des cartes contre ce que
# le titre predit, moins le marche) : Knies (Toronto -> Columbus) -50 %, Robertson (Toronto -> Pittsburgh) -47 %,
# Marchenko (Columbus -> Toronto) +161 %, Kreider (Anaheim -> Montreal) +143 % ; les autres changements : pas de sens net
# (mediane ~0) mais deux fois plus d'ecart. Donc : quitter Toronto ou Montreal = baisse ; y arriver = hausse ; le reste =
# des ventes d'avant moins fiables.
GRANDS_MARCHES = ("TOR", "MTL")
ECHANGE_JOURS = 150                # l'effet d'un changement d'equipe sur ses cartes : environ une demi-saison
ECHANGE_POINTS = 8.0               # l'indice : -8 (quitte Toronto/Montreal) ou +8 (y arrive)
EQUIPES_ABREV = {
    "anaheim ducks": "ANA", "boston bruins": "BOS", "buffalo sabres": "BUF", "calgary flames": "CGY", "carolina hurricanes": "CAR",
    "chicago blackhawks": "CHI", "colorado avalanche": "COL", "columbus blue jackets": "CBJ", "dallas stars": "DAL",
    "detroit red wings": "DET", "edmonton oilers": "EDM", "florida panthers": "FLA", "los angeles kings": "LAK", "minnesota wild": "MIN",
    "montreal canadiens": "MTL", "nashville predators": "NSH", "new jersey devils": "NJD", "new york islanders": "NYI",
    "new york rangers": "NYR", "ottawa senators": "OTT", "philadelphia flyers": "PHI", "pittsburgh penguins": "PIT",
    "san jose sharks": "SJS", "seattle kraken": "SEA", "st louis blues": "STL", "tampa bay lightning": "TBL",
    "toronto maple leafs": "TOR", "utah mammoth": "UTA", "utah hockey club": "UTA", "vancouver canucks": "VAN",
    "vegas golden knights": "VGK", "washington capitals": "WSH", "winnipeg jets": "WPG", "arizona coyotes": "ARI"}
EQUIPES_NOM = {"ANA": "Anaheim", "BOS": "Boston", "BUF": "Buffalo", "CGY": "Calgary", "CAR": "Caroline", "CHI": "Chicago",
               "COL": "Colorado", "CBJ": "Columbus", "DAL": "Dallas", "DET": "Detroit", "EDM": "Edmonton", "FLA": "Floride",
               "LAK": "Los Angeles", "MIN": "Minnesota", "MTL": "Montréal", "NSH": "Nashville", "NJD": "New Jersey",
               "NYI": "Islanders", "NYR": "Rangers", "OTT": "Ottawa", "PHI": "Philadelphie", "PIT": "Pittsburgh",
               "SJS": "San Jose", "SEA": "Seattle", "STL": "St. Louis", "TBL": "Tampa Bay", "TOR": "Toronto", "UTA": "Utah",
               "VAN": "Vancouver", "VGK": "Vegas", "WSH": "Washington", "WPG": "Winnipeg", "ARI": "Arizona"}


def abrev_equipe(nom):
    """« Toronto Maple Leafs » -> « TOR » ; une abreviation reste telle quelle ; None si inconnue."""
    s = str(nom or "").strip()
    if not s:
        return None
    if s.upper() in EQUIPES_NOM:
        return s.upper()
    return EQUIPES_ABREV.get(re.sub(r"\s+", " ", re.sub(r"[^a-z ]", " ", _norm(s))).strip())


def sens_echange(de, vers):
    """Le sens d'un changement d'equipe pour ses cartes : « baisse » (quitte Toronto/Montreal), « hausse » (y arrive), sinon
    « neutre »."""
    g_de, g_vers = de in GRANDS_MARCHES, vers in GRANDS_MARCHES
    return "baisse" if g_de and not g_vers else "hausse" if g_vers and not g_de else "neutre"


def _debut_saison(aujourdhui):
    an = aujourdhui.year if aujourdhui.month >= 7 else aujourdhui.year - 1
    return an, date(an, 10, 1)


def detecter_echange(h, vu=None, aujourdhui=None):
    """Le dernier changement d'equipe d'un joueur, s'il est recent : {de, vers, le, source} ou None.
    1. vu = {eq, le} : l'equipe notee a la derniere passe ; une autre aujourd'hui = un changement DU JOUR (date exacte).
    2. Sinon, ses saisons LNH (h["equipes"] : [saison, nom du club, matchs]) : l'equipe d'avant, si c'etait la saison
       derniere (changement d'ete : date = debut de la saison, ou aujourd'hui avant octobre) ou cette saison (date inconnue :
       aujourd'hui, par prudence)."""
    aujourdhui = aujourdhui or date.today()
    abr = abrev_equipe((h or {}).get("equipe"))
    if not abr:
        return None
    if vu and vu.get("eq") and vu["eq"] != abr:
        return {"de": vu["eq"], "vers": abr, "le": aujourdhui.isoformat(), "source": "vu"}
    an, debut = _debut_saison(aujourdhui)
    cour, prec = an * 10000 + an + 1, (an - 1) * 10000 + an
    eqs = [(int(e[0] or 0), abrev_equipe(e[1])) for e in (h or {}).get("equipes") or [] if isinstance(e, (list, tuple)) and len(e) >= 2]
    eqs = [(sa, a) for sa, a in eqs if a]
    for k in range(len(eqs) - 1, -1, -1):
        sa, a = eqs[k]
        if a == abr:
            continue
        if sa == cour:                                        # change pendant cette saison
            return {"de": a, "vers": abr, "le": aujourdhui.isoformat(), "source": "saisons"}
        if sa == prec and not any(s2 == prec and a2 == abr for s2, a2 in eqs[k + 1:]):      # change cet ete
            return {"de": a, "vers": abr, "le": min(aujourdhui, debut).isoformat(), "source": "saisons"}
        return None                                           # l'equipe d'avant est plus vieille : pas recent
    return None


# 14 nov 2026 (Mathieu : « pourquoi Knies est encore a 87 ? ») : les fiches LNH de nos joueurs se relisent lentement (Knies
# n'en avait pas, ou une vieille : « TOR »). La verite de chaque jour : les alignements des 32 clubs (API publique de la LNH,
# 64 appels par jour) : l'equipe de CETTE saison et celle(s) de la saison derniere de chaque joueur.
ROSTERS_H = 20
ROSTERS_PREC_J = 7


def rosters_lnh(vieux=None, maintenant=None, force=False):
    """{le, le_prec, saison, cour: {nom normalise: club}, prec: {nom normalise: [clubs]}} ; relu au plus aux 20 h.
    23 nov 2026 (Larkin echange a Montreal un dimanche soir : 20 h, c'est trop long) : force=True relit tout de suite les
    alignements de CETTE saison (32 appels) ; ceux de la saison d'avant ne changent plus : relus aux 7 jours seulement."""
    if not force and vieux and vieux.get("cour") and time.time() - (vieux.get("le") or 0) < ROSTERS_H * 3600:
        return vieux
    import urllib.request
    an, _deb = _debut_saison(maintenant or date.today())
    cour_s, prec_s = f"{an}{an + 1}", f"{an - 1}{an}"
    garder_prec = bool(vieux and vieux.get("prec") and vieux.get("saison") == cour_s
                       and time.time() - (vieux.get("le_prec") or vieux.get("le") or 0) < ROSTERS_PREC_J * 86400)
    cour, prec, ok = {}, {}, 0
    for club in sorted(k for k in EQUIPES_NOM if k != "ARI"):
        for saison, dest in ((cour_s, "c"),) if garder_prec else ((cour_s, "c"), (prec_s, "p")):
            u = f"https://api-web.nhle.com/v1/roster/{'UTA' if club == 'UTA' else club}/{saison}"
            try:
                with reseau.ouvrir(urllib.request.Request(u, headers={"User-Agent": "SlabCoach"}), timeout=15) as r:
                    j = json.loads(r.read().decode())
                ok += 1
            except Exception:
                continue
            for grp in ("forwards", "defensemen", "goalies"):
                for x in j.get(grp) or []:
                    n = _norm(f"{(x.get('firstName') or {}).get('default', '')} {(x.get('lastName') or {}).get('default', '')}")
                    if not n:
                        continue
                    if dest == "c":
                        cour[n] = club
                    else:
                        prec.setdefault(n, [])
                        if club not in prec[n]:
                            prec[n].append(club)
    if ok < (10 if garder_prec else 20) and vieux:
        return vieux                                         # la LNH ne repond pas : on garde la derniere lecture
    maint = time.time()
    if garder_prec:
        return {"le": maint, "le_prec": vieux.get("le_prec") or vieux.get("le") or maint, "saison": cour_s, "cour": cour, "prec": vieux["prec"]}
    return {"le": maint, "le_prec": maint, "saison": cour_s, "cour": cour, "prec": prec}


# 23 nov 2026 (Mathieu : « echange entre Montreal et Detroit : on devrait absolument l'avoir capte ») : une nouvelle d'echange
# FERME (pas une rumeur) qui nomme un de nos joueurs fait relire les alignements tout de suite, au lieu d'attendre 20 h.
ECHANGE_FERME = re.compile(r"\btraded?s?\b|\bacquire[sd]?\b|\bdealt\b|\b[ée]chang[ée]e?s?\b|\bacquis\b|\bacquiert\b|\bacqui[eè]rent\b|\bobtien(?:t|nent)\b", re.I)
ECHANGE_RUMEUR = re.compile(r"rumou?r|rumeur|\bcould\b|\bshould\b|\bmight\b|\bwould\b|\btargets?\b|\bif\b|\?|\bmock\b|proposal|\binterest|int[ée]r[êe]t|"
                            r"deadline|\bwatch\b|\btalks?\b|\bmarket\b|\bbait\b|\bboard\b|\bblock\b|\btiers?\b|candidat|potenti|\boptions?\b|destinations?|landing spot|\bwants?\b|\brequest|\bdemande\b|pourrait|devrait|\bsi\b", re.I)
ROSTERS_VITE_S = 75 * 60           # apres une nouvelle d'echange : au plus une relecture aux 75 minutes...
ROSTERS_VITE_MAX = 10              # ... et au plus 10 par jour (320 appels)


def echange_annonce(d, base, aujourdhui=None, items=None):
    """Nos joueurs nommes dans une nouvelle d'echange ferme d'aujourd'hui ou d'hier, dont le changement d'equipe n'est pas encore
    note (une fois note, on arrete de relire)."""
    aujourdhui = aujourdhui or date.today()
    items = [x for x in (actu(2) if items is None else items)
             if ECHANGE_FERME.search(x.get("titre") or "") and not ECHANGE_RUMEUR.search(x.get("titre") or "")]
    if not items:
        return []
    noms = set(base or {}) | set((d or {}).get("indice") or {})
    par = set(_actu_par_joueur(noms, items))
    # « Larkin traded to Canadiens » : le nom de famille seul suffit ICI (6 lettres et plus, un seul de nos joueurs le porte) :
    # une fausse alerte ne coute qu'une relecture, ce sont les alignements qui disent la verite
    fam = {}
    for n in noms:
        k = _norm(n).split()
        if len(k) >= 2 and len(k[-1]) >= 6:
            fam.setdefault(k[-1], []).append(n)
    for x in items:
        for w in set(re.findall(r"[a-z'\-]{6,}", _norm(x.get("titre")))):
            if len(fam.get(w) or []) == 1:
                par.add(fam[w][0])
    ech, lim = (d or {}).get("echanges") or {}, (aujourdhui - timedelta(days=2)).isoformat()
    return sorted(n for n in par if not (n in ech and str(ech[n].get("le") or "") >= lim))


# 23 nov 2026 : le matin apres l'echange, Larkin n'etait sur AUCUN alignement (retire de Detroit, pas encore ajoute a Montreal) :
# les alignements seuls auraient pris des jours. Les manchettes le disent tout de suite. Garde-fous : mots FERMES (pas une rumeur),
# UNE seule equipe d'arrivee possible dans le titre, et une confirmation : deux manchettes d'accord, ou une manchette et le
# joueur absent de l'alignement de son club. Les alignements gardent le dernier mot (ils confirment, ou ils effacent).
_EQ_TITRE = {"ducks": "ANA", "anaheim": "ANA", "bruins": "BOS", "boston": "BOS", "sabres": "BUF", "buffalo": "BUF", "flames": "CGY",
             "calgary": "CGY", "hurricanes": "CAR", "canes": "CAR", "carolina": "CAR", "caroline": "CAR", "blackhawks": "CHI", "chicago": "CHI",
             "avalanche": "COL", "colorado": "COL", "blue jackets": "CBJ", "columbus": "CBJ", "dallas": "DAL", "red wings": "DET",
             "detroit": "DET", "oilers": "EDM", "edmonton": "EDM", "panthers": "FLA", "florida": "FLA", "floride": "FLA",
             "los angeles": "LAK", "minnesota": "MIN", "canadiens": "MTL", "canadien": "MTL", "habs": "MTL", "montreal": "MTL",
             "predators": "NSH", "nashville": "NSH", "devils": "NJD", "new jersey": "NJD", "islanders": "NYI", "rangers": "NYR",
             "senators": "OTT", "senateurs": "OTT", "ottawa": "OTT", "flyers": "PHI", "philadelphia": "PHI", "philadelphie": "PHI",
             "penguins": "PIT", "pittsburgh": "PIT", "sharks": "SJS", "san jose": "SJS", "kraken": "SEA", "seattle": "SEA",
             "st louis": "STL", "lightning": "TBL", "tampa bay": "TBL", "tampa": "TBL", "maple leafs": "TOR", "leafs": "TOR",
             "toronto": "TOR", "mammoth": "UTA", "utah": "UTA", "canucks": "VAN", "vancouver": "VAN", "golden knights": "VGK",
             "vegas": "VGK", "capitals": "WSH", "washington": "WSH", "winnipeg": "WPG"}
_RE_EQ_TITRE = re.compile(r"\b(" + "|".join(sorted((re.escape(k) for k in _EQ_TITRE), key=len, reverse=True)) + r")\b")
NOUVELLES_SANS_SUITE_J = 3         # une manchette jamais confirmee : effacee si le joueur est encore dans son club 3 jours apres
NOUVELLES_MAX_J = 10               # ... ou s'il n'est nulle part apres 10 jours


def equipes_du_titre(titre):
    """Les clubs nommes dans une manchette -> {abreviations}."""
    t = re.sub(r"[^a-z ]", " ", _norm(titre))
    return {_EQ_TITRE[m] for m in _RE_EQ_TITRE.findall(t)}


def echange_par_nouvelles(d, base, aujourdhui=None, items=None):
    """Note dans d["echanges"] le changement d'equipe annonce par les manchettes (source « nouvelles »). -> les joueurs notes."""
    aujourdhui = aujourdhui or date.today()
    items = [x for x in (actu(2) if items is None else items)
             if ECHANGE_FERME.search(x.get("titre") or "") and not ECHANGE_RUMEUR.search(x.get("titre") or "")]
    if not items:
        return []
    noms = set(base or {}) | set((d or {}).get("indice") or {})
    ech, vus = d.setdefault("echanges", {}), d.get("equipes_vues") or {}
    R = d.get("rosters") or {}
    rc, frais = R.get("cour") or {}, time.time() - (R.get("le") or 0) < 26 * 3600
    lim, faits = (aujourdhui - timedelta(days=2)).isoformat(), []
    for nom in sorted(echange_annonce(d, base, aujourdhui, items)):
        k = _norm(nom)
        club = rc.get(k) or (vus.get(nom) or {}).get("eq") or abrev_equipe((((base or {}).get(nom) or {}).get("nhl") or {}).get("equipe"))
        if not club:
            continue
        voix = {}                                            # club d'arrivee -> {source : jour}
        fam = k.split()[-1]
        for x in items:
            t = _norm(x.get("titre"))
            if not (k in t or (len(fam) >= 6 and re.search(r"\b" + re.escape(fam) + r"\b", t))):
                continue
            S = equipes_du_titre(x.get("titre"))
            arr = (S - {club}) if club in S else S
            if len(arr) != 1:
                continue                                     # aucune ou plusieurs equipes d'arrivee possibles : on ne devine pas
            src = re.sub(r"^https?://(www\.)?", "", str(x.get("lien") or x.get("titre") or ""))[:60].split("/")[0]
            voix.setdefault(next(iter(arr)), {})[src] = max(str(x.get("date") or "")[:10], lim)
        if len(voix) != 1:
            continue
        vers, par = next(iter(voix.items()))
        if vers == club or not (len(par) >= 2 or (frais and k not in rc)):
            continue
        if nom in ech and ech[nom].get("vers") == vers:
            continue
        ech[nom] = {"de": club, "vers": vers, "le": min(min(par.values()), aujourdhui.isoformat()), "source": "nouvelles"}
        faits.append(nom)
    if faits:
        print("Echange (manchettes) : " + ", ".join(f"{n} {ech[n]['de']} -> {ech[n]['vers']}" for n in faits[:6]), flush=True)
    return faits


def rosters_vite(d, base, aujourdhui=None, items=None, lecteur=None):
    """Relit les alignements de cette saison si une nouvelle d'echange nomme un de nos joueurs. -> les joueurs, ou []."""
    aujourdhui = aujourdhui or date.today()
    noms = echange_annonce(d, base, aujourdhui, items)
    if not noms:
        return []
    R, V = d.get("rosters") or {}, d.get("rosters_vite") or {}
    if V.get("jour") != aujourdhui.isoformat():
        V = {"jour": aujourdhui.isoformat(), "n": 0}
    if time.time() - (R.get("le") or 0) < ROSTERS_VITE_S or V["n"] >= ROSTERS_VITE_MAX:
        return []
    d["rosters"] = (lecteur or rosters_lnh)(R, force=True)
    V["n"] += 1
    d["rosters_vite"] = V
    print("Alignements LNH relus (nouvelle d'echange) : " + ", ".join(noms[:6]), flush=True)
    return noms


def suivre_echanges(d, base, aujourdhui=None):
    """Garde dans d l'equipe vue de chaque joueur actif et ses changements recents (d["echanges"]) ; enleve les vieux.
    14 nov 2026 : l'equipe vient d'abord des alignements LNH du jour (d["rosters"]), sinon de la fiche du joueur."""
    aujourdhui = aujourdhui or date.today()
    vus, ech = d.setdefault("equipes_vues", {}), d.setdefault("echanges", {})
    R = d.get("rosters") or {}
    rc, rp = R.get("cour") or {}, R.get("prec") or {}
    an, debut = _debut_saison(aujourdhui)
    noms = set(base or {}) | set(d.get("indice") or {})
    for nom in noms:
        e = (base or {}).get(nom) or {}
        h = (e or {}).get("nhl") or {}
        if h.get("actif") is False:
            continue
        k = _norm(nom)
        abr = rc.get(k) or abrev_equipe(h.get("equipe"))
        if not abr:
            continue
        # les alignements : dans un club cette saison, dans un AUTRE la saison derniere (jamais celui-ci) = change cet ete
        # ou depuis le debut de la saison
        if rc.get(k) and rp.get(k) and rc[k] not in rp[k] and not (nom in ech and ech[nom].get("vers") == rc[k]):
            ech[nom] = {"de": rp[k][-1], "vers": rc[k], "le": min(aujourdhui, debut).isoformat(), "source": "alignements"}
        h = dict(h, equipe=abr)
        vu = vus.get(nom)
        x = detecter_echange(h, vu if vu and vu.get("eq") else None, aujourdhui)
        if x and (vu and vu.get("eq") and vu["eq"] != abr or nom not in ech):
            if not (nom in ech and ech[nom].get("vers") == x["vers"] and x["source"] != "vu"):
                if nom in ech and ech[nom].get("vers") == x["vers"] and str(ech[nom].get("source") or "").startswith("nouvelles"):
                    x = dict(x, le=min(str(ech[nom].get("le") or x["le"]), x["le"]), source="nouvelles+vu")   # annonce, puis confirme
                ech[nom] = x
        if not vu or vu.get("eq") != abr:
            vus[nom] = {"eq": abr, "le": aujourdhui.isoformat()}
    lim = (aujourdhui - timedelta(days=ECHANGE_JOURS)).isoformat()
    for nom in [n for n, x in ech.items() if str(x.get("le") or "") < lim]:
        ech.pop(nom, None)
    for nom in [n for n, x in ech.items() if x.get("source") == "nouvelles"]:      # 23 nov 2026 : une manchette jamais confirmee
        x, la = ech[nom], rc.get(_norm(nom))
        try:
            age = (aujourdhui - date.fromisoformat(str(x.get("le"))[:10])).days
        except ValueError:
            age = NOUVELLES_MAX_J
        if (la == x.get("de") and age >= NOUVELLES_SANS_SUITE_J) or (la != x.get("vers") and age >= NOUVELLES_MAX_J):
            ech.pop(nom, None)
    return ech


def echange_de(nom, d=None):
    """Le changement d'equipe recent d'un joueur, avec son sens et les noms des clubs ; None sinon."""
    d = d if d is not None else lire()
    E = d.get("echanges") or {}
    x = E.get(nom)
    if x is None:
        k = _norm(nom)
        x = next((v for n, v in E.items() if _norm(n) == k), None)
    if not x:
        return None
    return {**x, "sens": sens_echange(x["de"], x["vers"]), "de_nom": EQUIPES_NOM.get(x["de"], x["de"]),
            "vers_nom": EQUIPES_NOM.get(x["vers"], x["vers"])}


_ECH_IDX = {"mt": None, "m": {}}


def echange_titre(titre):
    """Le changement d'equipe recent du joueur NOMME dans un titre d'annonce (rapide : seulement les joueurs echanges)."""
    d = lire()
    if _ECH_IDX["mt"] != _ETAT.get("mt") or not _ECH_IDX["m"] and d.get("echanges"):
        _ECH_IDX["m"] = {_norm(n): n for n in (d.get("echanges") or {})}
        _ECH_IDX["mt"] = _ETAT.get("mt")
    if not _ECH_IDX["m"]:
        return None
    t = " " + _norm(titre) + " "
    for k, nom in _ECH_IDX["m"].items():
        if " " + k + " " in t:
            x = echange_de(nom, d)
            return dict(x, joueur=nom) if x else None
    return None


# les gros trophees comptent plus (meme echelle que demande_legale)
TROPHEES_POIDS = {"Stanley Cup": 2.0, "Hart Memorial Trophy": 3.0, "Art Ross Trophy": 2.5, "Conn Smythe Trophy": 2.5,
                  "Maurice “Rocket” Richard Trophy": 2.0, "Calder Memorial Trophy": 2.0, "Vezina Trophy": 2.0,
                  "James Norris Memorial Trophy": 2.0, "Ted Lindsay Award": 1.5}


def _norm(n):
    n = unicodedata.normalize("NFKD", str(n or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]+", " ", n).strip()


def _chemin():
    try:
        import comptes
        d = comptes.DONNEES
    except Exception:
        d = os.environ.get("LOCKERROOM_DONNEES") or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(d, "indice_joueurs.json")


def lire():
    p = _chemin()
    # 24 nov 2026 (vitesse, lu dans les piles du serveur : « getmtime < indice_joueurs.lire < indice < score_slab.score ») :
    # lire() est appele une fois PAR CARTE (le score de chaque annonce) et demandait chaque fois la date du fichier au disque
    # (lent sur le disque de Render). Au plus une verification aux 2 secondes ; une ecriture (_ecrire) se voit tout de suite.
    m_ = time.monotonic()
    if _ETAT["d"] is not None and _ETAT.get("p") == p and m_ - _ETAT.get("vu", 0.0) < 2.0:
        return _ETAT["d"]
    try:
        mt = os.path.getmtime(p)
    except OSError:
        return {"joueurs": {}, "indice": {}, "le": 0}
    _ETAT["vu"], _ETAT["p"] = m_, p
    if _ETAT["d"] is None or _ETAT["mt"] != mt:
        try:
            with open(p, encoding="utf-8") as f:
                _ETAT["d"] = json.load(f)
            _ETAT["mt"] = mt
        except (OSError, ValueError):
            return {"joueurs": {}, "indice": {}, "le": 0}
    return _ETAT["d"]


def _ecrire(d):
    p = _chemin()
    with _verrou:
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(p + ".tmp", p)
    _ETAT["d"], _ETAT["mt"] = d, os.path.getmtime(p)
    _ETAT["vu"], _ETAT["p"] = time.monotonic(), p


# -- 1. les totaux de saison, notes chaque jour ------------------------------------------------------------------
def _valeur(st, *noms):
    for n in noms:
        if n in st:
            return st[n]
    return None


def saison_courante(s):
    """La saison en cours d'une reponse highlightly.stats : la plus recente, la saison reguliere si elle est la."""
    sa = [x for x in (s or {}).get("saisons") or [] if x.get("saison")]
    if not sa:
        return None, []
    an = max(x["saison"] for x in sa)
    cour = [x for x in sa if x["saison"] == an]
    c = next((x for x in cour if (x.get("partie") or "").lower() == "season"), cour[0])
    avant = {}
    for x in sa:
        if x["saison"] < an and (x["saison"] not in avant or (x.get("partie") or "").lower() == "season"):
            avant[x["saison"]] = x
    return c, [avant[k] for k in sorted(avant)]


def totaux(x):
    st = (x or {}).get("stats") or {}
    return {"mj": _valeur(st, "Total Games Played", "Games Played"), "b": _valeur(st, "Total Goals", "Goals"),
            "a": _valeur(st, "Total Assists", "Assists"), "pts": _valeur(st, "Total Points", "Points"),
            "tirs": _valeur(st, "Total Shots", "Shots"), "toi": _valeur(st, "Avg. Time On Ice Per Game"),
            "an": (x or {}).get("saison"), "ligue": (x or {}).get("ligue"),
            "equipe": next((e.get("abrev") or e.get("nom") for e in (x or {}).get("equipes") or [] if e), None)}


def noter_jour(d, nom, s, jour=None):
    """Garde le total de saison du jour (et le pts/match des saisons d'avant) pour un joueur."""
    jour = jour or date.today().isoformat()
    c, avant = saison_courante(s)
    if not c:
        return False
    t = totaux(c)
    j = d.setdefault("joueurs", {}).setdefault(nom, {"jours": {}})
    j["jours"][jour] = t
    for k in sorted(j["jours"])[:-GARDE_JOURS]:
        j["jours"].pop(k, None)
    j["ligues"] = sorted({x.get("ligue") for x in [c] + avant[-4:] if x.get("ligue")})[:6]
    av = [totaux(x) for x in avant[-3:]]
    mj = sum((x["mj"] or 0) for x in av)
    j["avant_ppm"] = round(sum((x["pts"] or 0) for x in av) / mj, 3) if mj >= 20 else None
    j["le"] = time.time()
    return True


def forme_semaine(j, aujourdhui=None):
    """Points, buts et matchs des ~7 derniers jours : la difference entre le total d'aujourd'hui et celui d'il y a 6-9 jours.
    Une nouvelle saison (total qui recule) : rien."""
    jours = sorted((j or {}).get("jours") or {})
    if len(jours) < 2:
        return None
    fin = jours[-1]
    d_fin = date.fromisoformat(fin)
    ref = [k for k in jours[:-1] if 5 <= (d_fin - date.fromisoformat(k)).days <= 9]
    if not ref:
        return None
    a, b = j["jours"][ref[-1]], j["jours"][fin]
    if a.get("an") != b.get("an") or (b.get("mj") or 0) < (a.get("mj") or 0):
        return None
    dif = {k: (b.get(k) or 0) - (a.get(k) or 0) for k in ("mj", "b", "a", "pts")}
    dif["jours"] = (d_fin - date.fromisoformat(ref[-1])).days
    return dif


# -- 2. les criteres, en rangs --------------------------------------------------------------------------------------
# -- 1b. le joueur « en creux » (11 nov 2026) ------------------------------------------------------------------------
# Mathieu : « un tres bon jeune joueur qui connait une periode plus difficile (Frank Nazar, Josh Doan) : c'est un tres bon
# moment pour acheter s'il va remonter ». Que des stats publiques (LNH), jamais un prix : on dit « a surveiller », jamais
# « achete ». Conditions : jeune (25 ans et moins ou 4 saisons et moins), talent DEMONTRE (saison de reference solide,
# ou haut choix au repechage), et un rythme NETTEMENT sous ses standards (<= 75 %) sur assez de matchs.
# « Sort de son creux » : ses 5 derniers matchs sont revenus a son rythme d'avant.
CREUX_RATIO = 0.75
CREUX_MJ_MIN = 8


def _toi_s(t):
    try:
        m, s = str(t or "").split(":")[:2]
        return int(m) * 60 + int(s)
    except (ValueError, TypeError):
        return None


def creux(h, aujourdhui=None):
    """h = la fiche LNH (demande_legale) -> {etat: creux|rebond, ppm, avant_ppm, ecart_pct, age, repech, l5, toi_ratio} ou None."""
    h = h or {}
    if h.get("actif") is False or not h.get("equipe") or h.get("pos") == "G":
        return None
    today = aujourdhui or date.today()
    age = None
    try:
        n = date.fromisoformat(str(h.get("naissance") or "")[:10])
        age = today.year - n.year - ((today.month, today.day) < (n.month, n.day))
    except ValueError:
        pass
    if not ((age is not None and age <= 25) or (h.get("saisons") or 99) <= 4):
        return None
    nhl = sorted([x for x in h.get("par_saison") or [] if x.get("l") == "NHL" and x.get("s")], key=lambda x: x["s"])
    if not nhl:
        return None
    cour = nhl[-1]
    sa = h.get("saison") or {}
    mj, pts = sa.get("gamesPlayed") or cour.get("gp") or 0, sa.get("points") if sa.get("points") is not None else cour.get("p")
    if mj < CREUX_MJ_MIN or pts is None:
        return None
    avant = [x for x in nhl[:-1] if (x.get("gp") or 0) >= 40][-2:]
    if not avant:
        return None
    ref = max(x["p"] / x["gp"] for x in avant)
    d_ = h.get("pos") == "D"
    if ref < (0.35 if d_ else 0.45):
        return None
    pick = h.get("repech")
    if not ((pick and pick <= 40) or ref >= (0.5 if d_ else 0.6)):
        return None
    ppm = pts / mj
    if ppm > CREUX_RATIO * ref:
        return None
    l5 = h.get("l5")
    t0, t1 = _toi_s(next((x.get("toi") for x in reversed(avant)), None)), _toi_s(cour.get("toi"))
    out = {"etat": "rebond" if (l5 is not None and l5 / 5.0 >= 0.9 * ref) else "creux", "ppm": round(ppm, 2), "avant_ppm": round(ref, 2),
           "ecart_pct": round(100 * (ppm / ref - 1)), "mj": mj, "age": age, "repech": pick, "l5": l5,
           "toi_ratio": round(t1 / t0, 2) if t0 and t1 else None}
    out["potentiel"] = round(min(1.0, (ref - ppm) / ref) * (1.0 + (0.3 if pick and pick <= 15 else 0.0)) * min(1.5, ref / 0.6), 3)
    return out


def _rangs(valeurs):
    """{cle: valeur} -> {cle: rang 0-100} (les egalites au meme rang ; None ignore)."""
    v = {k: x for k, x in valeurs.items() if x is not None}
    if not v or len(set(v.values())) == 1:          # aucune difference (ex. aucune nouvelle cette semaine) : critere ignore
        return {}
    tri = sorted(v.values())
    n = len(tri)
    out = {}
    for k, x in v.items():
        bas = sum(1 for y in tri if y < x)
        eg = sum(1 for y in tri if y == x)
        out[k] = round(100 * (bas + (eg - 1) / 2) / max(1, n - 1), 1) if n > 1 else 50.0
    return out


def _legende_brute(h):
    h = h or {}
    t = sum(TROPHEES_POIDS.get(k, 0.6) * n for k, n in (h.get("trophees_c") or {}).items())
    car = (h.get("carriere") or {}).get("points") or 0
    return (6 if h.get("hhof") else 0) + (4 if h.get("top100") else 0) + math.log1p(t) * 2 + math.log1p(car / 100)


def saison_lnh(aujourdhui=None):
    """La saison LNH en cours, au format de la LNH (20262027) : elle commence en septembre."""
    d = aujourdhui or date.today()
    y = d.year if d.month >= 9 else d.year - 1
    return y * 10000 + y + 1


def recrue_lnh(h, aujourdhui=None):
    """13 nov 2026 (Mathieu : « assure-toi que le badge Rookie, ce soit bel et bien des recrues de 2026-27 ; Easton Cowan et
    Schaefer ne sont plus en saison recrue ») : la regle de la LNH (Calder) : aucune saison d'avant avec 25 matchs et plus,
    pas 6 matchs et plus dans deux saisons d'avant, et moins de 26 ans au 15 septembre. Avant : « 2 saisons ou
    moins » (une 2e annee comptait comme recrue)."""
    cour = saison_lnh(aujourdhui)
    if not (h or {}).get("par_saison"):                  # fiche ancienne (sans le detail par saison) : 1re saison seulement
        return (h or {}).get("saisons") is not None and int(h.get("saisons") or 0) <= 1
    nhl = [x for x in (h or {}).get("par_saison") or [] if x.get("l") == "NHL" and x.get("s")]
    avant = {}
    for x in nhl:
        if int(x["s"]) < cour:
            avant[int(x["s"])] = avant.get(int(x["s"]), 0) + int(x.get("gp") or 0)
    if any(g >= 25 for g in avant.values()):
        return False
    if sum(1 for g in avant.values() if g >= 6) >= 2:   # 6 matchs et plus dans deux saisons d'avant (n'importe lesquelles)
        return False
    try:
        n = date.fromisoformat(str((h or {}).get("naissance") or "")[:10])
        sept = date(cour // 10000, 9, 15)
        if (sept - n).days / 365.25 >= 26:
            return False
    except ValueError:
        pass
    return True


# 10 nov 2026 (Mathieu : « s'il est parle beaucoup, s'il y a eu un trophee recemment ; a chaque jour ») : les nouvelles du
# hockey des 7 derniers jours (nos flux RSS publics) : combien de fois le joueur y est nomme, et les evenements forts
EVENEMENTS = re.compile(r"hall of fame|temple|trophy|troph|award|record|hat[- ]trick|tour du chapeau|milestone|\b(500|600|700|800|900|1000)(th)?\b|"
                        r"called up|recalled|rappel|promoted|debut|first nhl|premier but|signs|signe|extension|traded|echange|named captain|capitaine|"
                        r"all-star|player of the week|joueur de la semaine|star of the week", re.I)


# 13 nov 2026 (Mathieu : « Price intronise au Temple, standing ovation au Centre Bell, sa plaque mise au Centre Bell :
# automatiquement ses cartes se vendent plus ; on doit capter TOUS les evenements qui peuvent affecter la valeur d'un
# joueur ») : chaque nouvelle est classee (type, sens, poids) et compte de moins en moins avec les jours (demi-vie ~3 jours).
# Bonnes nouvelles : honneurs (Temple, chandail retire, plaque, statue, hommage, ovation), trophees, exploits, rappels.
# Mauvaises : blessure, suspension, ballottage, retrogradation, arrestation. Des TITRES publics seulement (licence eBay : aucun prix).
TYPES_EVENEMENTS = [
    ("temple", +30, re.compile(r"hall of fame|temple de la renomm|inducted|induction|intronis", re.I)),
    ("honneur", +25, re.compile(r"retir\w*\s.{0,30}(jersey|number|sweater|no\.)|jersey retire|retire[sd]? (his |the )?(number|jersey|no\.)|number retire|chandail retir|num[ée]ro retir|plaque|statue|"
                                r"ring of honou?r|banner|tribute|hommage|honou?r(ed|s)?\b|standing ovation|ovation|c[ée]l[ée]br|soir[ée]e .*honneur|ceremon", re.I)),
    ("trophee", +20, re.compile(r"\btroph|\baward|\bmvp\b|conn smythe|hart\b|calder|vezina|norris|art ross|rocket richard|stanley cup", re.I)),
    ("exploit", +15, re.compile(r"hat[- ]trick|tour du chapeau|milestone|record|career[- ]high|\b(500|600|700|800|900|1000|1,000)(th|e)?\b|"
                                r"player of the (week|month)|joueur de la semaine|star of the week|first (career )?(nhl )?goal|premier but|shutout|blanchissage", re.I)),
    ("rappel", +12, re.compile(r"called up|recalled|rappel[ée]|promoted|debut|d[ée]but|first nhl|signs? entry|named captain|capitaine|all-star", re.I)),
    ("contrat", +6, re.compile(r"extension|\bcontract\b|signs?\b|prolongation|contrat", re.I)),
    # 14 nov 2026 : un echange n'est ni bon ni mauvais en soi (Knies a Columbus : -50 %) ; son sens vient des marches
    ("echange", 0, re.compile(r"\btraded?\b|\bacquir|\bdealt\b|[ée]chang", re.I)),
    # 14 nov 2026 (Mathieu : « Cousins, c'est parce qu'il s'est fait defoncer par Chychrun ») : une grosse mise en echec, une
    # bagarre : tout le monde en parle (le buzz), sans dire si c'est bon pour ses cartes
    ("choc", 4, re.compile(r"\bbig hit\b|huge hit|massive hit|\blays? out\b|\blaid out\b|\blevell?ed\b|\bcrushe[sd]\b|\bdestroy|demolish|"
                           r"\bfight\b|drops? the gloves|\bscrap\b|bagarre|mise en [ée]chec|\bejected\b|match penalty|hit on\b|cheap shot|"
                           r"\bsuspension hearing\b", re.I)),
    ("blessure", -15, re.compile(r"leaves? (the )?game|injur|\bIR\b|day-to-day|surgery|concussion|upper[- ]body|lower[- ]body|bless[ée]|infirmerie|op[ée]r[ée]|commotion|out (indefinitely|for)", re.I)),
    ("negatif", -18, re.compile(r"waive|waivers|sent down|demot|suspen|healthy scratch|ballottage|r[ée]trograd|arrest|charged|benched|slump", re.I)),
]
DEMI_VIE_J = 3.0


def classer_evenement(titre):
    """Le titre d'une nouvelle -> (type, poids) du plus fort evenement reconnu, ou (None, 0)."""
    meil = (None, 0)
    for t, poids, rx in TYPES_EVENEMENTS:
        if rx.search(titre or "") and abs(poids) > abs(meil[1]):
            meil = (t, poids)
    return meil


# -- 25 nov 2026 (Mathieu, Bedard opere a l'epaule, absent 4 mois : « il devrait avoir le badge injured, non ? ») --------
# Une blessure dure plus longtemps que sa manchette : « Mauvaise nouvelle » s'eteint en 3 jours (DEMI_VIE_J) et le fil ne garde
# que 7 jours. Ici on garde l'ETAT du joueur : d["blessures"][nom] = {depuis, jusqu, titre, lien, explicite, fini}.
#   - la duree vient de la manchette (« out four months », « absent 6 a 8 semaines », « season-ending ») ; sans duree :
#     BLESSURE_DEFAUT_J (30 jours pour une operation ou « indefinitely », 14 « week-to-week », 3 « day-to-day ») ;
#   - l'etat finit a la date prevue, quand une manchette annonce son retour, ou des qu'il rejoue (ses matchs joues montent) ;
#   - une manchette au nom de famille seul (« Bedard out four months for Blackhawks ») compte si ce nom est unique chez les
#     joueurs actifs ET que la manchette nomme son equipe (jamais un homonyme).
# Des TITRES publics seulement (nos flux RSS d'editeurs) : aucun prix, aucun texte d'article.
BLESSURE_DEFAUT_J = 10
_NB = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
       "eleven": 11, "twelve": 12, "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "sept": 7, "huit": 8, "neuf": 9,
       "dix": 10, "onze": 11, "douze": 12}
_N = r"(\d{1,2}|" + "|".join(sorted(_NB, key=len, reverse=True)) + r")"
_RE_DUREE = re.compile(r"\b(?:" + _N + r"\s*(?:-|–|to|a|à|ou|or)\s*)?" + _N + r"[\s-]*(days?|weeks?|months?|jours?|semaines?|mois)\b", re.I)
_RE_SAISON_FINIE = re.compile(r"season[- ]ending|rest of (?:the )?(?:regular )?season|out for (?:the )?(?:season|year)|remainder of (?:the )?season|"
                              r"fin de (?:la )?saison|reste de la saison|saison (?:est )?termin[ée]e", re.I)
_RE_RETOUR = re.compile(r"\breturns (?:to|from|after|against|vs\.?|tonight|for)\b|\bactivated\b|back in (?:the )?lineup|cleared to (?:play|return)|"
                        r"\bmakes? (?:his )?(?:season )?return\b|de retour au jeu|revient au jeu|effectue (?:son|un) retour|de retour dans la formation", re.I)
# « expected to return in four months », « no timetable for his return » : pas un retour (le retour net gagne sur « surgery »)
_RE_PAS_RETOUR = re.compile(r"expected to|could|might|\bmay\b|won.?t|will not|\bnot\b|no timetable|timeline|hopes?|eyes|nearing|targets?|"
                            r"retour pr[ée]vu|pas de retour|ne reviendra pas|devrait|pourrait", re.I)
_UNITE_J = {"d": 1, "j": 1, "w": 7, "s": 7, "m": 30}


def _nb(x):
    x = str(x or "").lower()
    return int(x) if x.isdigit() else _NB.get(x)


def duree_blessure(titre, le=None):
    """(jours, explicite) : la duree d'absence que dit la manchette (la borne HAUTE d'un « 4 a 6 semaines »), sinon un defaut."""
    t = str(titre or "")
    if _RE_SAISON_FINIE.search(t):
        j0 = le or date.today()
        fin = date(j0.year + (1 if j0.month >= 7 else 0), 6, 30)
        return max(1, (fin - j0).days), True
    m = _RE_DUREE.search(t)
    if m:
        n = _nb(m.group(2))
        if n:
            return min(365, n * _UNITE_J[m.group(3)[0].lower()]), True
    if re.search(r"week[- ]to[- ]week|semaine en semaine", t, re.I):
        return 14, False
    if re.search(r"day[- ]to[- ]day|au jour le jour", t, re.I):
        return 3, False
    if re.search(r"indefinitely|ind[ée]termin[ée]e|surgery|op[ée]r[ée]|long[- ]term|\bLTIR\b|long terme", t, re.I):
        return 30, False
    return BLESSURE_DEFAUT_J, False


def _surnoms_equipe(code):
    """Les mots qui nomment une equipe dans une manchette : « Blackhawks », « Chicago », « Maple Leafs » -> {leafs, toronto}."""
    try:
        import sports
        nom = (sports._LNH.get(str(code or "").upper()) or ("",))[0]
    except Exception:
        nom = ""
    m = _norm(nom).split()
    if not m:
        return set()
    out = {m[-1]}
    if m[-1].endswith("s"):
        out.add(m[-1][:-1])                            # « le Canadien », « les Canadiens »
    ville = " ".join(m[:-1]) if len(m) == 2 else " ".join(m[:-2] if m[-2] in ("maple", "red", "blue", "golden") else m[:-1])
    if ville and ville not in ("new york",):           # deux equipes a New York : la ville ne dit pas laquelle
        out.add(ville)
    return out


def _joueurs_de_la_manchette(titre, par_famille, info):
    """Les joueurs que la manchette nomme : le nom complet ; ou le nom de famille seul, unique chez les actifs, avec son equipe."""
    t = " " + _norm(titre) + " "
    out = []
    for mot in set(t.split()):
        cands = par_famille.get(mot)
        if not cands:
            continue
        pleins = [n for n in cands if " " + _norm(n) + " " in t]
        if pleins:
            out += pleins
            continue
        actifs = [n for n in cands if (info.get(n) or {}).get("actif")]
        if len(mot) >= 5 and len(actifs) == 1 and any(" " + s_ + " " in t for s_ in _surnoms_equipe((info.get(actifs[0]) or {}).get("equipe"))):
            out.append(actifs[0])
    return list(dict.fromkeys(out))


# Meme jour (Mathieu : « pourquoi on n'a pas capte Bedard ? On doit TOUS les capter ») : les manchettes ne suffiront jamais (un nom
# de famille seul, un flux en panne, un joueur dont personne ne parle). Les MATCHS, eux, ne mentent pas : signal_joueurs lit deja
# chaque soir le sommaire de tous les matchs de la LNH (qui a joue). Un patineur toujours dans l'alignement de son club, qui
# jouait regulierement et qui a rate ses ABSENT_MIN derniers matchs, est « absent » : avec une manchette de blessure il est
# « blesse », sans manchette il reste « absent » (jamais « blesse » sans preuve : une suspension, un joueur laisse de cote).
# Les gardiens ne jouent pas tous les matchs : pour eux, les manchettes seulement.
ABSENT_MIN = 2
ABSENT_FENETRE_J = 45


def matchs_par_joueur(base, M=None):
    """{nom: [dates de ses matchs, triees]} de nos patineurs, d'apres les sommaires lus chaque soir (signal_joueurs)."""
    if M is None:
        try:
            import signal_joueurs
            M = signal_joueurs.lire_matchs()
        except Exception:
            M = {}
    J = (M or {}).get("joueurs") or {}
    out = {}
    for nom, e in (base or {}).items():
        h = (e or {}).get("nhl") or {}
        g = J.get(str(h.get("id") or ""))
        if g and h.get("pos") != "G":
            out[nom] = sorted(str(x[0])[:10] for x in g.get("m") or [])
    return out


def absents(info, matchs, alignement=None, aujourdhui=None):
    """{nom: {rates, depuis, dernier}} : les patineurs qui ont rate les derniers matchs de leur club. alignement = les noms
    (normalises) de l'alignement du jour : un joueur qui n'y est plus (renvoye, echange) n'est pas « absent »."""
    auj = aujourdhui or date.today()
    lim = (auj - timedelta(days=ABSENT_FENETRE_J)).isoformat()
    clubs = {}
    for nom, dates in (matchs or {}).items():
        i = info.get(nom) or {}
        if i.get("actif") and i.get("equipe") and (alignement is None or _norm(nom) in alignement):
            clubs.setdefault(i["equipe"], {})[nom] = [x for x in dates if x >= lim]
    out = {}
    for club, joueurs in clubs.items():
        compte = {}
        for dates in joueurs.values():
            for x in dates:
                compte[x] = compte.get(x, 0) + 1
        actifs_n = sum(1 for dates in joueurs.values() if dates)
        seuil = max(4, 0.4 * actifs_n)                 # un match du club = un soir ou une bonne part de ses joueurs ont joue
        T = sorted(x for x, n in compte.items() if n >= seuil)
        if len(T) < 5 or T[-1] < (auj - timedelta(days=7)).isoformat():
            continue                                   # pas assez de matchs lus, ou la saison est arretee
        for nom, dates in joueurs.items():
            D = set(dates)
            joues = [x for x in T if x in D]
            if not joues:
                continue
            rates = [x for x in T if x > joues[-1]]
            avant = [x for x in T if x <= joues[-1]][-5:]
            if len(rates) >= ABSENT_MIN and len(avant) >= 3 and sum(1 for x in avant if x in D) >= 3:
                out[nom] = {"rates": len(rates), "depuis": rates[0], "dernier": joues[-1]}
    return out


def suivre_blessures(d, items, info, stats_j=None, aujourdhui=None, absents_=None, matchs=None):
    """Met a jour d["blessures"] avec les manchettes du fil (7 jours) -> {nom: etat} des joueurs blesses AUJOURD'HUI.
    absents_ : un joueur blesse qui rate encore ses matchs reste blesse, meme passe la date prevue. matchs : il a rejoue."""
    B = d.setdefault("blessures", {})
    auj = aujourdhui or date.today()
    par_famille = {}
    for n in info:
        p = _norm(n).split()
        if len(p) >= 2:
            par_famille.setdefault(p[-1], []).append(n)
    for x in sorted(items or [], key=lambda x: str(x.get("date") or "")):
        titre = x.get("titre") or ""
        retour = bool(_RE_RETOUR.search(titre)) and not _RE_PAS_RETOUR.search(titre)
        if not retour and classer_evenement(titre)[0] != "blessure":
            continue
        le = str(x.get("date") or auj.isoformat())[:10]
        try:
            j_le = date.fromisoformat(le)
        except ValueError:
            continue
        for nom in _joueurs_de_la_manchette(titre, par_famille, info):
            b = B.get(nom)
            if retour:
                if b and not b.get("fini") and le >= b["depuis"]:
                    b["fini"] = le
                continue
            if b and b.get("fini") and le <= b["fini"]:
                continue                               # une vieille manchette, relue : il est deja revenu
            jours, explicite = duree_blessure(titre, j_le)
            jusqu = (j_le + timedelta(days=jours)).isoformat()
            if not b or b.get("fini") or b["jusqu"] < le:
                B[nom] = {"depuis": le, "jusqu": jusqu, "titre": titre[:160], "lien": x.get("lien"), "explicite": explicite}
            elif explicite and (not b.get("explicite") or le >= b.get("vu", b["depuis"])):
                b.update({"jusqu": jusqu, "titre": titre[:160], "lien": x.get("lien"), "explicite": True, "vu": le})   # la plus recente qui dit la duree
            elif not b.get("explicite") and jusqu > b["jusqu"]:
                b["jusqu"] = jusqu
    out = {}
    for nom in list(B):
        b = B[nom]
        if not b.get("fini"):                          # il a joue un match apres la manchette (sommaires de la LNH)
            apres = [x for x in (matchs or {}).get(nom) or [] if x > b["depuis"]]
            if apres:
                b["fini"] = apres[0]
        if not b.get("fini"):                          # il rejoue : ses matchs joues ont monte depuis la blessure
            jr = ((stats_j or {}).get(nom) or {}).get("jours") or {}
            dates = sorted(jr)
            try:
                seuil = (date.fromisoformat(b["depuis"]) + timedelta(days=2)).isoformat()
            except ValueError:
                seuil = b["depuis"]
            avant = [k for k in dates if k <= seuil]
            if avant and dates[-1] > seuil and (jr[dates[-1]].get("mj") or 0) > (jr[avant[-1]].get("mj") or 0) \
                    and jr[dates[-1]].get("an") == jr[avant[-1]].get("an"):
                b["fini"] = dates[-1]
        encore = not b.get("fini") and nom in (absents_ or {})          # la date prevue est passee, mais il rate encore ses matchs
        if not encore and (b["jusqu"] < (auj - timedelta(days=14)).isoformat() or (b.get("fini") and b["fini"] < (auj - timedelta(days=14)).isoformat())):
            B.pop(nom)                                 # du passe : on oublie
        elif not b.get("fini") and (b["jusqu"] >= auj.isoformat() or encore):
            out[nom] = b
    return out


def _age_j(dt, aujourdhui=None):
    try:
        return max(0.0, ((aujourdhui or date.today()) - date.fromisoformat(str(dt)[:10])).days)
    except (TypeError, ValueError):
        return 3.0


def actu(jours=7):
    """{nom normalise: {"n": mentions, "ev": evenements, "titres": [{titre, lien, date}]}} des nouvelles recentes."""
    try:
        import nouvelles
        items = ((nouvelles.lire_cache().get("sports") or {}).get("hockey")) or []
    except Exception:
        return {}
    limite = (date.today() - timedelta(days=jours)).isoformat()
    return [x for x in items if str(x.get("date") or "") >= limite]


# 14 nov 2026 (Mathieu : « mettre les grosses nouvelles des joueurs qui expliquent le score dans leur fiche ») : le fil ne
# garde que 7 jours ; les evenements d'un joueur (trophee, blessure, echange, grosse mise en echec...) restent 30 jours
# avec lui (titre + lien seulement), les plus forts d'abord.
GROSSES_JOURS = 30
GROSSES_MAX = 6


def garder_grosses(d, nouvelles_j, aujourdhui=None):
    G = d.setdefault("grosses", {})
    lim = ((aujourdhui or date.today()) - timedelta(days=GROSSES_JOURS)).isoformat()
    for nom, na in (nouvelles_j or {}).items():
        evs = [e for e in na.get("evs") or [] if e.get("titre")]
        if not evs:
            continue
        l = G.setdefault(nom, [])
        vus = {e["titre"] for e in l}
        for e in evs:
            if e["titre"] not in vus:
                l.append({k: e.get(k) for k in ("titre", "lien", "date", "type", "sens")})
                vus.add(e["titre"])
    for nom in list(G):
        G[nom] = sorted([e for e in G[nom] if str(e.get("date") or "") >= lim], key=lambda e: str(e.get("date") or ""), reverse=True)[:GROSSES_MAX]
        if not G[nom]:
            G.pop(nom)
    return G


def _actu_par_joueur(noms, items):
    out = {}
    if not items:
        return out
    textes = [(_norm(x.get("titre")), x) for x in items]
    for nom in noms:
        k = _norm(nom)
        p = k.split()
        if len(p) < 2:
            continue
        fam = p[-1]
        for t, x in textes:
            if k in t or (len(fam) >= 5 and re.search(r"\b" + re.escape(fam) + r"\b", t) and p[0][:1] and re.search(r"\b" + re.escape(p[0]) + r"\b", t)):
                o = out.setdefault(nom, {"n": 0, "ev": 0, "titres": [], "pos": 0.0, "neg": 0.0, "evs": []})
                o["n"] += 1
                if EVENEMENTS.search(x.get("titre") or ""):
                    o["ev"] += 1
                ty, po = classer_evenement(x.get("titre") or "")
                if ty:
                    f = 0.5 ** (_age_j(x.get("date")) / DEMI_VIE_J)
                    if po > 0:
                        o["pos"] += po * f
                    else:
                        o["neg"] += -po * f
                    if len(o["evs"]) < 4:
                        o["evs"].append({"type": ty, "sens": 1 if po > 0 else -1, "titre": (x.get("titre") or "")[:160], "lien": x.get("lien"), "date": x.get("date")})
                if len(o["titres"]) < 3:
                    o["titres"].append({"titre": (x.get("titre") or "")[:160], "lien": x.get("lien"), "date": x.get("date")})
    return out


def calculer(d=None, base=None, demande=None):
    """L'indice de chaque joueur : {nom: {indice, criteres, pastilles, actif, forme}}.
    base = demande_legale.lire()["joueurs"] (LNH, Wikipedia) ; demande = fonction nom -> score."""
    d = d if d is not None else lire()
    if base is None:
        import demande_legale
        base = (demande_legale.lire() or {}).get("joueurs") or {}
        demande = demande or demande_legale.demande
    stats_j = d.get("joueurs") or {}
    noms = set(base) | set(stats_j)
    brut = {k: {} for k in ("forme", "ascension", "rythme", "buzz", "notoriete", "demande", "recrue", "legende", "actu", "pic", "communaute",
                            "marche")}
    try:
        import demande_legale as _dl_m
        marche_eq = _dl_m.marche_equipe
    except Exception:
        marche_eq = None
    nouvelles_j = _actu_par_joueur(noms, actu())
    try:                                         # 15 nov 2026 : la banque Young Guns garde chaque titre (titre + lien + date)
        import banque_yg
        banque_yg.archiver_nouvelles(nouvelles_j)
    except Exception as e:
        print("Banque YG (nouvelles) : " + repr(e)[:120], flush=True)
    try:
        garder_grosses(d, nouvelles_j)
    except Exception as e:
        print("Grosses nouvelles : " + repr(e)[:120], flush=True)
    try:
        echange_par_nouvelles(d, base)            # 23 nov 2026 : la manchette d'abord, l'alignement confirme ensuite
    except Exception as e:
        print("Echanges (manchettes) : " + repr(e)[:160], flush=True)
    try:
        echanges = suivre_echanges(d, base)
    except Exception as e:
        print("Echanges : " + repr(e), flush=True)
        echanges = {}
    # 11 nov 2026 (Mathieu : « ce que nos utilisateurs regardent, suivent, ajoutent : un signal que personne d'autre n'a ») :
    # l'interet de la communaute SlabCoach (fiches, annonces, watchlists, favoris) des 7 et 30 derniers jours
    try:
        import communaute
        comm = {k.lower(): v for k, v in communaute.par_joueur(30).items()}
    except Exception:
        comm = {}
    info = {}
    rc_ = (d.get("rosters") or {}).get("cour") or {}
    for nom in noms:
        e = base.get(nom) or {}
        h, w = e.get("nhl") or {}, e.get("wiki") or {}
        if rc_.get(_norm(nom)) and h.get("actif") is not False:
            h = dict(h, equipe=rc_[_norm(nom)])               # 14 nov 2026 : l'equipe du jour (alignements LNH)
        j = stats_j.get(nom) or {}
        actif = h.get("actif") is not False and bool(h.get("equipe") or j.get("jours"))
        fs = forme_semaine(j)
        # 11 nov 2026 (Mathieu : « c'est un gardien, pas les points ») : un gardien n'est jamais note sur ses points (1 passe
        # en 8 matchs le faisait « En hausse ») : sa forme, sa percee et son rythme ne comptent pas ; le reste oui
        if h.get("pos") == "G":
            fs = None
        der = j["jours"][sorted(j["jours"])[-1]] if j.get("jours") and h.get("pos") != "G" else None
        ppm = (der["pts"] or 0) / der["mj"] if der and (der.get("mj") or 0) >= 3 and der.get("pts") is not None else None
        if fs and fs["mj"]:
            brut["forme"][nom] = fs["pts"] + 0.5 * fs["b"] + 0.15 * fs["mj"]
        elif actif and h.get("l5") is not None and not j.get("jours") and h.get("pos") != "G":
            brut["forme"][nom] = (h.get("l5") or 0) * 7 / 12.0          # en attendant 7 jours de notes : ses 5 derniers matchs
        if ppm is not None:
            brut["rythme"][nom] = ppm
            if j.get("avant_ppm"):
                brut["ascension"][nom] = (ppm + 0.05) / (j["avant_ppm"] + 0.05)
            elif (h.get("saisons") or 0) <= 1:
                brut["ascension"][nom] = (ppm + 0.05) / 0.35            # une recrue : contre une recrue moyenne
        v60, v20 = w.get("v60") or 0, w.get("v20") or 0
        if v60 >= 200:
            brut["buzz"][nom] = v20 / max(1.0, (v60 - v20) / 2)
            brut["notoriete"][nom] = math.log1p(v60)
            v3 = w.get("v3")                              # 13 nov 2026 : le pic des 3 derniers jours (un evenement d'hier)
            if v3 is not None:
                brut["pic"][nom] = v3 / max(1.0, (v60 - v3) / 57.0 * 3)
        if demande:
            try:
                s = demande(nom)
            except Exception:
                s = None
            if s:
                brut["demande"][nom] = s
        brut["recrue"][nom] = 1.0 if actif and recrue_lnh(h) else 0.0
        cm = comm.get(nom.lower())
        if cm and cm[1] > 0:
            brut["communaute"][nom] = cm[0] + 0.3 * cm[1]
        na = nouvelles_j.get(nom)
        brut["actu"][nom] = (na["n"] + 2 * na["ev"] + 0.2 * na.get("pos", 0)) if na else 0.0
        brut["legende"][nom] = _legende_brute(h)
        if actif and h.get("equipe") and marche_eq:
            try:
                mq = marche_eq(h.get("equipe"))
            except Exception:
                mq = None
            if mq is not None:
                brut["marche"][nom] = mq
        try:
            cx = creux(h)
        except Exception:
            cx = None
        info[nom] = {"creux": cx, "actif": actif, "forme": fs, "equipe": h.get("equipe"), "legende_vraie": bool(h.get("hhof") or h.get("top100") or (h.get("trophees_n") or 0) >= 5)}
    try:
        matchs_j = matchs_par_joueur(base)
        absents_ = absents(info, matchs_j, set(rc_) if rc_ else None)
    except Exception as e:
        print("Absents : " + repr(e)[:160], flush=True)
        matchs_j, absents_ = {}, {}
    try:
        blesses = suivre_blessures(d, actu(), info, stats_j, absents_=absents_, matchs=matchs_j)
    except Exception as e:
        print("Blessures : " + repr(e)[:160], flush=True)
        blesses = {}
    d["absents"] = absents_                            # garde pour la fiche du joueur (« a rate N matchs »)
    rangs = {k: _rangs(v) for k, v in brut.items()}
    out = {}
    for nom in noms:
        i = info[nom]
        r = {k: rangs[k].get(nom) for k in rangs}
        poids = POIDS_ACTIF if i["actif"] else POIDS_RETIRE
        pres = {k: p for k, p in poids.items() if r.get(k) is not None}
        if not pres or sum(pres.values()) < 0.2:
            continue
        val = sum(r[k] * p for k, p in pres.items()) / sum(pres.values())
        if not i["actif"]:
            val *= ECHELLE_RETIRE
        if i["legende_vraie"]:
            val = max(val, 55 + 0.3 * (r.get("legende") or 0))              # plancher : une legende reste en haut
        past = []
        if i["actif"] and (r.get("forme") or 0) >= 95 and (i["forme"] or {}).get("pts", 1) >= 1:
            past.append("en_feu")
        if i["actif"] and (r.get("ascension") or 0) >= 85:
            past.append("en_hausse")
        if (r.get("buzz") or 0) >= 90:
            past.append("buzz")
        if i["legende_vraie"]:
            past.append("legende")
        if r.get("recrue") and brut["recrue"].get(nom):
            past.append("recrue")
        if nouvelles_j.get(nom) and (nouvelles_j[nom]["ev"] or nouvelles_j[nom]["n"] >= 2):
            past.append("actu")
        if i.get("creux"):
            past.append("rebond" if i["creux"]["etat"] == "rebond" else "en_creux")
        if "en_feu" in past:
            val = min(100.0, val + BONUS_FEU)
        # 13 nov 2026 : les evenements du moment. Une bonne nouvelle fraiche (honneur, Temple, trophee, exploit) monte le joueur
        # tout de suite ; un pic de visites (3 jours) aussi. Un BON joueur avec une mauvaise nouvelle ou en creux : « Bonne
        # occasion » pour les acheteurs (ses cartes baissent souvent pour un temps)
        na = nouvelles_j.get(nom) or {}
        pos, neg = na.get("pos", 0.0), na.get("neg", 0.0)
        pic = brut["pic"].get(nom)
        if pos >= 10:
            val = min(100.0, val + min(14.0, 0.45 * pos))
            if any(e["type"] in ("temple", "honneur", "trophee") and e["sens"] > 0 for e in na.get("evs") or []):
                past.append("honneur")
        # 14 nov 2026 (Mathieu : « integre les evenements dans SlabIQ si ca aide : teste sur des joueurs, categorise, regarde la
        # mediane des cartes vendues a la date de l'evenement ») : etude sur nos ventes (mai-nov 2026, 216 joueurs, 154
        # evenements = pics de visites Wikipedia) : jours temoins -2,3 % ; pic x3-5 -4,3 % (rien) ; x5-10 +4,2 % ; x10+ +8,9 % ;
        # un pic le jour d'un gros match (3 pts+) +32,6 % (encore +16 % 3 semaines apres) ; hors saison (contrat, echange) +8,9 %.
        # Donc : un petit pic ne compte plus ; un gros pic oui ; un gros pic + un exploit, encore plus. Banc (correlation bonus /
        # cartes 7 jours apres) : 0,071 -> 0,092, la nouvelle regle gagne 89 % des tirages. Le pic ici = 3 jours (un pic d'un
        # jour x5 ~ x2,6 sur 3 jours ; x10 ~ x4,5).
        if pic is not None and pic >= PIC_MOYEN and (w_ := (base.get(nom) or {}).get("wiki") or {}).get("v3", 0) >= 300:
            bonus = PIC_BONUS_FORT if pic >= PIC_FORT else PIC_BONUS_MOYEN
            exploit = "en_feu" in past or any(e.get("type") == "exploit" and e.get("sens", 0) > 0 for e in (na.get("evs") or []))
            if exploit:
                bonus += PIC_BONUS_EXPLOIT
            val = min(100.0, val + bonus)
            if "buzz" not in past:
                past.append("buzz")
        # 14 nov 2026 (Knies, Toronto -> Columbus) : un changement d'equipe recent
        ex = echange_de(nom, {"echanges": echanges}) if i["actif"] and nom in echanges else None
        if ex:
            if ex["sens"] == "baisse":
                val = max(0.0, val - ECHANGE_POINTS)
                past.append("echange_baisse")
            elif ex["sens"] == "hausse":
                val = min(100.0, val + ECHANGE_POINTS)
                past.append("echange_hausse")
            else:
                past.append("echange")
        bon = i["legende_vraie"] or (r.get("demande") or 0) >= 70 or (r.get("notoriete") or 0) >= 80 or (r.get("rythme") or 0) >= 75
        if neg >= 8 and pos < neg and nom not in blesses and nom not in absents_:
            past.append("mauvaise")                    # blesse / absent s'affichent deja « Mauvaise nouvelle » (une seule pastille)
        if nom in blesses:
            past.insert(0, "blesse")                   # 25 nov 2026 : en premier (la tuile du Radar montre UNE pastille de joueur)
        elif nom in absents_:
            past.insert(0, "absent")                   # il rate ses matchs, sans manchette de blessure : « Absent », pas « Blessé »
        if bon and i["actif"] and ("en_creux" in past or (neg >= 8 and pos < neg)):
            past.append("occasion")
        out[nom] = {"indice": round(val, 1), "criteres": {k: v for k, v in r.items() if v is not None}, "pastilles": past,
                    "actif": i["actif"], "equipe": i["equipe"], "semaine": i["forme"],
                    "dem": brut["demande"].get(nom)}           # la demande brute (le Score SlabCoach s'en sert sans recalculer)
        if nouvelles_j.get(nom):
            out[nom]["actu"] = nouvelles_j[nom]["titres"]
            if nouvelles_j[nom].get("evs"):
                out[nom]["evenements"] = nouvelles_j[nom]["evs"]
                out[nom]["ev_pos"], out[nom]["ev_neg"] = round(pos, 1), round(neg, 1)
        if pic is not None:
            out[nom]["pic"] = round(pic, 2)
        if ex:
            out[nom]["echange"] = {k: ex[k] for k in ("de", "vers", "le", "sens", "de_nom", "vers_nom")}
        if i.get("creux"):
            out[nom]["creux"] = i["creux"]
    return out


# -- 3. la passe du jour ---------------------------------------------------------------------------------------------
def _ordre(base, demande, favoris=()):
    """Qui lire en premier : les favoris des utilisateurs, puis les recrues et les plus demandes (actifs seulement)."""
    fav = [n for n in favoris if n in base]
    act = [n for n, e in base.items() if (e.get("nhl") or {}).get("actif") is not False and (e.get("nhl") or {}).get("equipe")]

    def cle(n):
        try:
            s = demande(n) or 0
        except Exception:
            s = 0
        rec = 1.5 if recrue_lnh(base[n].get("nhl") or {}) else 1.0
        return -s * rec
    return list(dict.fromkeys(fav + sorted(act, key=cle)))


def favoris_utilisateurs():
    """Les joueurs suivis par les utilisateurs (questionnaire du Radar), sans savoir qui suit qui (lecture seule)."""
    out = []
    try:
        import comptes
        import sqlite3
        racine = comptes.DOSSIER_COMPTES
        for cid in sorted(os.listdir(racine))[:5000]:
            for nom_db in ("lockerroom.db",):
                p = os.path.join(racine, cid, nom_db)
                if not os.path.isfile(p):
                    continue
                try:
                    c = sqlite3.connect("file:" + p + "?mode=ro", uri=True, timeout=2)
                    try:
                        r = c.execute("SELECT v FROM reglages WHERE k='deals_profil'").fetchone()
                    finally:
                        c.close()
                    if r:
                        out += [str(x)[:40] for x in ((json.loads(r[0]) or {}).get("favoris") or [])]
                except Exception:
                    continue
    except Exception:
        pass
    return list(dict.fromkeys(out))


def passe(max_appels=None, sport="hockey"):
    """Lit le total de saison des joueurs dus aujourd'hui (Highlightly), puis recalcule l'indice de tout le monde."""
    import demande_legale
    import highlightly
    d = lire()
    d = {"joueurs": dict(d.get("joueurs") or {}), "indice": d.get("indice") or {}, "le": d.get("le") or 0,
         "equipes_vues": dict(d.get("equipes_vues") or {}), "echanges": dict(d.get("echanges") or {}), "rosters": d.get("rosters"),
         "grosses": dict(d.get("grosses") or {}), "rosters_vite": d.get("rosters_vite"), "blessures": dict(d.get("blessures") or {}),
         "absents": dict(d.get("absents") or {})}
    base = (demande_legale.lire() or {}).get("joueurs") or {}
    try:
        d["rosters"] = rosters_lnh(d.get("rosters"))
        rosters_vite(d, base)                     # 23 nov 2026 : une nouvelle d'echange -> on relit tout de suite
    except Exception as e:
        print("Alignements LNH : " + repr(e)[:160], flush=True)
    jour = date.today().isoformat()
    lus = 0
    if highlightly.actif():
        reste = max(0, highlightly.plafond_jour() - highlightly.utilisees() - 4)       # 4 appels gardes pour l'essai admin
        if max_appels is not None:
            reste = min(reste, max_appels)
        for nom in _ordre(base, demande_legale.demande, favoris_utilisateurs()):
            if reste <= 0:
                break
            if jour in ((d["joueurs"].get(nom) or {}).get("jours") or {}):
                continue
            avant = highlightly.utilisees()
            s = highlightly.stats_joueur(nom, sport)
            reste -= max(1, highlightly.utilisees() - avant)
            if s and noter_jour(d, nom, s, jour):
                lus += 1
            if highlightly.statut().get("pause"):
                break
    d["indice"] = calculer(d, base, demande_legale.demande)
    d["le"] = time.time()
    d["lus_aujourdhui"] = lus
    _ecrire(d)
    try:
        creux_noter(d["indice"])
    except Exception as e:
        print("Creux (journal) : " + repr(e), flush=True)
    try:                                   # 12 nov 2026 : la photo du jour (« ce que tu as manque » compare a la derniere visite)
        import quoi_de_neuf
        quoi_de_neuf.hist_noter(d["indice"])
    except Exception as e:
        print("Indice (historique) : " + repr(e), flush=True)
    try:                                   # 13 nov 2026 : le journal des evenements (pourquoi les cartes bougent : mouvements.py)
        import mouvements
        mouvements.journal_noter(d["indice"])
    except Exception as e:
        print("Mouvements (journal) : " + repr(e), flush=True)
    return {"lus": lus, "joueurs": len(d["indice"])}


# 11 nov 2026 (Mathieu : « valider avec les ventes ») : est-ce que les joueurs « en creux » remontent vraiment ? Les ventes
# de mai a octobre (hors saison) ne permettent pas de le mesurer apres coup : on le mesure EN AVANT. Chaque joueur signale
# est note avec le niveau de ses cartes ce jour-la (memoire du marche de SlabIQ, admin) ; 30 et 60 jours plus tard, on regarde.
def _creux_chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "creux_journal.json")


def _niveau_marche(nom):
    """Le niveau des cartes du joueur (ecart moyen prix / titre sur 30 jours, memoire de SlabIQ) ou None."""
    try:
        import score_appris
        c = score_appris._etat_cx()
        if c is None:
            return None
        try:
            r = c.execute("SELECT v FROM mem WHERE k = ?", ("j\x1f" + nom,)).fetchone()
        finally:
            c.close()
        if not r:
            return None
        v = json.loads(r[0])
        n = len(score_appris.HL)
        fa = 0.5 ** ((date.today().toordinal() - v[2 * n]) / 30.0)
        S, W = v[1] * fa, v[n + 1] * fa
        return round(S / (W + 1.0), 4) if W > 0.5 else None
    except Exception:
        return None


def creux_noter(I, aujourdhui=None):
    jour = (aujourdhui or date.today()).isoformat()
    try:
        with open(_creux_chemin()) as f:
            J = json.load(f)
    except (OSError, ValueError):
        J = {"signales": []}
    deja = {(x["nom"], x["jour"][:7]) for x in J["signales"]}         # un signalement par joueur par mois
    for nom, v in I.items():
        cx = v.get("creux")
        if not cx or (nom, jour[:7]) in deja:
            continue
        J["signales"].append({"nom": nom, "jour": jour, "etat": cx["etat"], "ppm": cx["ppm"], "avant_ppm": cx["avant_ppm"],
                              "niveau": _niveau_marche(nom)})
    J["signales"] = J["signales"][-2000:]
    tmp = _creux_chemin() + ".tmp"
    with open(tmp, "w") as f:
        json.dump(J, f)
    os.replace(tmp, _creux_chemin())
    return J


def creux_bilan(aujourdhui=None):
    """{signales, mesurables_30, remontes_30 (part dont les cartes valent plus 30+ jours apres), ...} : admin."""
    try:
        with open(_creux_chemin()) as f:
            J = json.load(f)
    except (OSError, ValueError):
        return {"signales": 0}
    auj = (aujourdhui or date.today())
    out = {"signales": len(J.get("signales") or [])}
    for jours in (30, 60):
        l = [x for x in J.get("signales") or [] if x.get("niveau") is not None
             and (auj - date.fromisoformat(x["jour"])).days >= jours]
        haut = 0
        for x in l:
            n = _niveau_marche(x["nom"])
            if n is not None and n > x["niveau"]:
                haut += 1
        out[f"mesurables_{jours}"] = len(l)
        out[f"remontes_{jours}"] = round(haut / len(l), 3) if l else None
    return out


def passe_si_besoin():
    """Chaque heure : une passe s'il reste des joueurs a lire aujourd'hui (le quota se partage sur la journee)."""
    if _ETAT["en_cours"] or time.time() - _ETAT["le"] < 3000:
        return False
    _ETAT["le"] = time.time()

    def tache():
        _ETAT["en_cours"] = True
        try:
            passe()
        except Exception as e:
            print("Indice joueurs : " + repr(e), flush=True)
        finally:
            _ETAT["en_cours"] = False
    threading.Thread(target=tache, daemon=True, name="indice_joueurs").start()
    return True


# -- 4. lectures ------------------------------------------------------------------------------------------------------
_IDX_NORM = {"id": None, "d": {}}


def indice(nom):
    I = lire().get("indice") or {}
    if nom in I:
        return I[nom]
    # 21 nov 2026 (vitesse) : un nom ecrit autrement (accent, casse) faisait normaliser les ~900 noms a CHAQUE appel (des
    # centaines d'appels par ecran de break) ; la table des noms normalises est faite une fois par version de l'indice
    # (on garde l'objet lui-meme, pas son id() : Python redonne le meme id a un nouvel objet une fois l'ancien libere, et la
    # table d'hier aurait servi pour l'indice d'aujourd'hui)
    if _IDX_NORM["id"] is not I:
        d = {}
        for n, v in I.items():
            d.setdefault(_norm(n), v)
        _IDX_NORM["d"], _IDX_NORM["id"] = d, I
    return _IDX_NORM["d"].get(_norm(nom))


def top(n=12, filtre=None, actifs=None):
    """Les joueurs les mieux classes ; filtre = une pastille (en_feu, en_hausse, buzz, legende, recrue)."""
    I = lire().get("indice") or {}
    l = [(nom, v) for nom, v in I.items() if (not filtre or filtre in v.get("pastilles", [])) and (actifs is None or v.get("actif") == actifs)]
    if filtre == "en_feu":
        l.sort(key=lambda x: -(x[1].get("criteres", {}).get("forme") or 0))
    elif filtre in ("en_creux", "rebond"):
        l.sort(key=lambda x: -(((x[1].get("creux") or {}).get("potentiel") or 0) + 0.002 * x[1]["indice"]))
    else:
        l.sort(key=lambda x: -x[1]["indice"])
    return [{"nom": nom, **{k: v.get(k) for k in ("indice", "pastilles", "actif", "equipe", "semaine", "creux")}} for nom, v in l[:n]]


def statut():
    d = lire()
    J = d.get("joueurs") or {}
    jour = date.today().isoformat()
    return {"joueurs": len(d.get("indice") or {}), "lus_aujourdhui": sum(1 for j in J.values() if jour in (j.get("jours") or {})),
            "suivis": len(J), "avec_semaine": sum(1 for j in J.values() if forme_semaine(j)), "le": d.get("le"),
            "en_feu": [x["nom"] for x in top(5, "en_feu")]}


def pourquoi(nom):
    """10 nov 2026 (Mathieu : « pourquoi il monte ») : le contexte d'un joueur, en faits : sa semaine, son rythme contre ses
    saisons d'avant, son buzz, sa legende, ses ligues. Jamais un prix. -> dict (vide si inconnu)."""
    d = lire()
    v = indice(nom) or {}
    k = _norm(nom)
    nom_vrai = next((n for n in (d.get("indice") or {}) if _norm(n) == k), nom)
    j = (d.get("joueurs") or {}).get(nom_vrai) or {}
    try:
        import demande_legale
        base = (demande_legale.lire() or {}).get("joueurs") or {}
        e = base.get(nom_vrai) or next((x for n, x in base.items() if _norm(n) == k), {}) or {}
    except Exception:
        e = {}
    h, w = e.get("nhl") or {}, e.get("wiki") or {}
    out = {"indice": v.get("indice"), "pastilles": v.get("pastilles") or [], "criteres": v.get("criteres") or {}, "actif": v.get("actif")}
    if v.get("echange"):
        out["echange"] = v["echange"]                 # 14 nov 2026 : {de_nom, vers_nom, le, sens}
    gr = (d.get("grosses") or {}).get(nom_vrai) or next((x for n, x in (d.get("grosses") or {}).items() if _norm(n) == k), None)
    if gr:
        out["nouvelles"] = gr                         # 14 nov 2026 : les evenements des 30 derniers jours (titre + lien)
    bl = (d.get("blessures") or {}).get(nom_vrai)
    if bl and not bl.get("fini") and str(bl.get("jusqu") or "") >= date.today().isoformat():
        out["blessure"] = {k: bl.get(k) for k in ("depuis", "jusqu", "titre", "lien", "explicite")}   # 25 nov 2026
    ab = (d.get("absents") or {}).get(nom_vrai)
    if ab:
        out["absent"] = ab                            # {rates, depuis, dernier} : il a rate ses derniers matchs
    I = d.get("indice") or {}
    if v.get("indice") is not None:
        pairs = [x for x in I.values() if x.get("actif") == v.get("actif")]
        out["rang"] = 1 + sum(1 for x in pairs if x.get("indice", 0) > v["indice"])
        out["sur"] = len(pairs)
    gardien = h.get("pos") == "G"
    out["gardien"] = gardien or None
    out["semaine"] = None if gardien else (v.get("semaine") or forme_semaine(j))
    if not gardien and not out["semaine"] and h.get("l5") is not None and v.get("actif"):
        out["cinq"] = h.get("l5")
    jours = {} if gardien else (j.get("jours") or {})
    if jours:
        der = jours[sorted(jours)[-1]]
        if (der.get("mj") or 0) >= 3 and der.get("pts") is not None:
            out["saison"] = {"mj": der["mj"], "pts": der["pts"], "b": der.get("b"), "ppm": round(der["pts"] / der["mj"], 2),
                             "ligue": der.get("ligue"), "equipe": der.get("equipe")}
            if j.get("avant_ppm"):
                out["saison"]["avant_ppm"] = j["avant_ppm"]
                out["saison"]["ecart_pct"] = round(100 * (out["saison"]["ppm"] / j["avant_ppm"] - 1)) if j["avant_ppm"] else None
    if j.get("ligues"):
        out["ligues"] = j["ligues"]
    v60, v20 = w.get("v60") or 0, w.get("v20") or 0
    if v60 >= 200:
        out["buzz"] = {"pct": round(100 * (v20 / max(1.0, (v60 - v20) / 2) - 1)), "vues_60": v60}
    leg = {}
    if h.get("hhof"):
        leg["temple"] = True
    if h.get("top100"):
        leg["top100"] = True
    tc = h.get("trophees_c") or {}
    if tc.get("Stanley Cup"):
        leg["coupes"] = tc["Stanley Cup"]
    if h.get("trophees_n"):
        leg["trophees"] = h["trophees_n"]
    if tc:                                    # 20 nov 2026 (« je peux pas cliquer sur ses awards ») : la liste, pour la fenetre
        leg["liste"] = sorted(([str(k), int(v or 1)] for k, v in tc.items() if k), key=lambda x: (-x[1], x[0]))[:24]
    car = h.get("carriere") or {}
    if car.get("points"):
        leg["carriere"] = {"pts": car.get("points"), "mj": car.get("gamesPlayed"), "b": car.get("goals")}
    if leg:
        out["legende"] = leg
    if h.get("saisons"):
        out["saisons"] = h["saisons"]
    if h.get("an_repech"):
        out["repechage"] = {"an": h.get("an_repech"), "ronde": h.get("ronde"), "rang": h.get("repech")}
    if v.get("creux") or creux(h):
        out["creux"] = v.get("creux") or creux(h)
    if v.get("actu"):
        out["actu"] = v["actu"]
    else:
        na = _actu_par_joueur([nom_vrai], actu()).get(nom_vrai)
        if na:
            out["actu"] = na["titres"]
    return out
