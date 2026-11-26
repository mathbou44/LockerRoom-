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

JOURS = 120
RAW_MIN = 5
P10_MIN = 5                          # 4 -> 5 des le premier essai : a 4 ventes, une PSA 10 d'une autre parallele suffit a fausser la mediane
P9_MIN = 3
REFAIRE_J = 7                        # 26 nov, 15 h 06 (Mathieu : « le top 100 a grader qui se refresh chaque semaine ») : refaite chaque semaine,
                                     # une fois de plus quand la collecte PSA finit, et quand l'admin le demande
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


def classer(titre, joueur=None):
    """Un titre -> ((joueur, recherche raw, annee, /N), note) avec note = « raw », « 10 » ou « 9 » ; None si la vente ne doit
    pas compter (voir le point 2 du haut)."""
    import cartes_match as cm
    import tendance_sortes as ts
    t = str(titre or "")
    try:
        ct = cm.cible_titre(t, joueur)
    except Exception:
        return None
    if not ct.get("joueur") or ct.get("autres_joueurs") or not ct.get("carte_nommee") or not ct.get("ident"):
        return None                                           # il faut un SET : une couleur seule n'est pas une carte
    g = ct.get("grade")
    if g:
        if g.get("cie") != "psa" or str(g.get("note") or "") not in ("10", "9"):
            return None                                       # une autre compagnie, une autre note, « PSA ready »
        if cm.espere_note(t):
            return None                                       # « PSA 10 ? », « PSA 10 contender » : une raw qui espere (la regle des comps)
        note = str(g["note"])
    else:
        if ct.get("grade_bas") or _RE_GRADEE.search(t):
            return None                                       # une PSA 8, une SGC, une « graded 9 » : gradee, donc pas une raw
        if cm._RE_ABIMEE.search(t.lower()):
            return None                                       # abimee : pas une carte a grader
        note = "raw"
    serie = ct.get("serie")
    try:
        q_note = cm.requete_ebay(ct)
        if cm.raisons_refus(cm.cible(q_note + (f" /{serie}" if serie else "")), t):
            return None                                       # un lot ecrit avec « + », la suite d'un set, etc.
    except Exception:
        return None
    ct["grade"] = None
    q = cm.requete_ebay(ct)
    if len(q.split()) < 3 or ts.autre_carte(t, q):
        return None
    num = re.sub(r"[^a-z0-9]", "", str(ct.get("num") or "").lower()) or None
    return (ct["joueur"], q, ct.get("annee"), serie, num), note


def _q(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, max(0, int(round(p * (len(v) - 1)))))]


def _etale(prix):
    return (_q(prix, 0.75) / _q(prix, 0.25)) if len(prix) >= 4 and _q(prix, 0.25) > 0 else 1.0


def analyser(ventes, aujourd=None, jours=JOURS, respirer=None):
    """ventes : des (cle de la vente, titre, prix $ CA, date AAAA-MM-JJ, joueur ou None). -> {« cartes »: [...], « lues », « rangees »,
    « ecartees » : pourquoi une carte vue en PSA 10 n'est pas dans la liste}. La liste : le meilleur rapport PSA 10 / raw d'abord."""
    import tendance_sortes as ts
    auj = aujourd or datetime.now(timezone.utc).date()
    d_min = (auj - timedelta(days=jours)).isoformat()
    vues, cartes, lues, rangees = set(), {}, 0, 0
    noms = {}
    for i, (cle, titre, prix, le, joueur) in enumerate(ventes):
        if respirer and i % 200 == 199:
            respirer(i)
        le = str(le or "")[:10]
        if not prix or prix <= 0 or le < d_min or cle in vues:
            continue
        vues.add(cle)
        lues += 1
        r = classer(titre, joueur)
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
    out, ecartees = [], {"peu de PSA 10": 0, "peu de raw": 0, "periode trop courte": 0, "prix trop etales": 0}
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
        d0 = max(min(d for d, _ in g["raw"]), min(d for d, _ in g["10"]))            # la meme periode pour les deux
        raw = [p for d, p in g["raw"] if d >= d0]
        p10 = [p for d, p in g["10"] if d >= d0]
        p9 = [p for d, p in g["9"] if d >= d0]
        if len(raw) < RAW_MIN or len(p10) < P10_MIN:
            ecartees["periode trop courte"] += 1
            continue
        if _etale(raw) > DISPERSION_MAX or _etale(p10) > DISPERSION_MAX:
            ecartees["prix trop etales"] += 1
            continue
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
                    "du": d0, "jours": (auj - datetime.strptime(d0, "%Y-%m-%d").date()).days})
    out.sort(key=lambda x: (-x["rendement"], -x["reste10"]))
    return {"cartes": out[:N_LISTE], "n_cartes": len(out), "lues": lues, "rangees": rangees, "ecartees": ecartees,
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
    if mt is not None and time.time() - mt < REFAIRE_J * 86400 and not finie_apres:
        return None
    return lancer()


def top_tendances():
    """Pour l'onglet « A grader » de Trending (ADMIN seulement pour l'instant : la liste porte des prix) : les N_TOP premieres."""
    v = lire()
    return {"cartes": (v.get("cartes") or [])[:N_TOP], "n": v.get("n_cartes") or 0, "le": v.get("le"), "jours": v.get("jours") or JOURS,
            "frais_psa": v.get("frais_psa") or frais_psa(), "semaine": REFAIRE_J}


def page():
    """Pour l'admin : la liste, son age, et si un calcul tourne."""
    v = lire()
    return {"ok": True, "en_cours": ETAT["en_cours"], "texte": ETAT["texte"], "cartes": v.get("cartes") or [], "n_cartes": v.get("n_cartes") or 0,
            "lues": v.get("lues"), "rangees": v.get("rangees"), "ecartees": v.get("ecartees") or {}, "le": v.get("le"),
            "frais_psa": v.get("frais_psa") or frais_psa(), "frais_ebay": FRAIS_EBAY, "jours": v.get("jours") or JOURS,
            "regles": v.get("regles") or {"raw_min": RAW_MIN, "p10_min": P10_MIN, "p9_min": P9_MIN}}
