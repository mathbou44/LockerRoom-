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
  recrue     : 1re ou 2e saison (les cartes de recrue sont les plus suivies)
  legende    : Temple, top 100, trophees (ponderes), carriere ; plancher pour les legendes, actives ou non
Indice = melange pondere ; un joueur retire est note sur sa legende, son buzz et sa notoriete seulement.
Pastilles : « En creux » / « Sort de son creux » (11 nov : jeune talent sous ses standards), « En feu » (forme >= 95), « En hausse » (ascension >= 85), « Buzz » (buzz >= 90), « Legende », « Recrue ».

Appels Highlightly : 1 par joueur par jour (le total de saison). Forfait gratuit (90/jour) : les favoris des utilisateurs,
puis les plus demandes ; Pro (7 500/jour) : tout le monde, 4 sports.
"""
import json
import math
import os
import re
import threading
import time
import unicodedata
from datetime import date, datetime, timedelta

POIDS_ACTIF = {"forme": 0.38, "ascension": 0.11, "rythme": 0.09, "buzz": 0.09, "notoriete": 0.05, "demande": 0.11,
               "recrue": 0.05, "legende": 0.05, "actu": 0.07}
BONUS_FEU = 6                      # « 6 buts cette semaine = tres haut » : la semaine en feu passe devant tout le monde
POIDS_RETIRE = {"legende": 0.33, "buzz": 0.22, "notoriete": 0.33, "actu": 0.12}
ECHELLE_RETIRE = 0.85              # une semaine en feu passe devant ; une legende reste quand meme haut
GARDE_JOURS = 70
_verrou = threading.Lock()
_ETAT = {"le": 0.0, "en_cours": False, "d": None, "mt": None}

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
    try:
        mt = os.path.getmtime(p)
    except OSError:
        return {"joueurs": {}, "indice": {}, "le": 0}
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


# 10 nov 2026 (Mathieu : « s'il est parle beaucoup, s'il y a eu un trophee recemment ; a chaque jour ») : les nouvelles du
# hockey des 7 derniers jours (nos flux RSS publics) : combien de fois le joueur y est nomme, et les evenements forts
EVENEMENTS = re.compile(r"hall of fame|temple|trophy|troph|award|record|hat[- ]trick|tour du chapeau|milestone|\b(500|600|700|800|900|1000)(th)?\b|"
                        r"called up|recalled|rappel|promoted|debut|first nhl|premier but|signs|signe|extension|traded|echange|named captain|capitaine|"
                        r"all-star|player of the week|joueur de la semaine|star of the week", re.I)


def actu(jours=7):
    """{nom normalise: {"n": mentions, "ev": evenements, "titres": [{titre, lien, date}]}} des nouvelles recentes."""
    try:
        import nouvelles
        items = ((nouvelles.lire_cache().get("sports") or {}).get("hockey")) or []
    except Exception:
        return {}
    limite = (date.today() - timedelta(days=jours)).isoformat()
    return [x for x in items if str(x.get("date") or "") >= limite]


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
                o = out.setdefault(nom, {"n": 0, "ev": 0, "titres": []})
                o["n"] += 1
                if EVENEMENTS.search(x.get("titre") or ""):
                    o["ev"] += 1
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
    brut = {k: {} for k in ("forme", "ascension", "rythme", "buzz", "notoriete", "demande", "recrue", "legende", "actu")}
    nouvelles_j = _actu_par_joueur(noms, actu())
    info = {}
    for nom in noms:
        e = base.get(nom) or {}
        h, w = e.get("nhl") or {}, e.get("wiki") or {}
        j = stats_j.get(nom) or {}
        actif = h.get("actif") is not False and bool(h.get("equipe") or j.get("jours"))
        fs = forme_semaine(j)
        der = j["jours"][sorted(j["jours"])[-1]] if j.get("jours") else None
        ppm = (der["pts"] or 0) / der["mj"] if der and (der.get("mj") or 0) >= 3 and der.get("pts") is not None else None
        if fs and fs["mj"]:
            brut["forme"][nom] = fs["pts"] + 0.5 * fs["b"] + 0.15 * fs["mj"]
        elif actif and h.get("l5") is not None and not j.get("jours"):
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
        if demande:
            try:
                s = demande(nom)
            except Exception:
                s = None
            if s:
                brut["demande"][nom] = s
        brut["recrue"][nom] = 1.0 if actif and (h.get("saisons") or 9) <= 2 else 0.0
        na = nouvelles_j.get(nom)
        brut["actu"][nom] = (na["n"] + 2 * na["ev"]) if na else 0.0
        brut["legende"][nom] = _legende_brute(h)
        try:
            cx = creux(h)
        except Exception:
            cx = None
        info[nom] = {"creux": cx, "actif": actif, "forme": fs, "equipe": h.get("equipe"), "legende_vraie": bool(h.get("hhof") or h.get("top100") or (h.get("trophees_n") or 0) >= 5)}
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
        out[nom] = {"indice": round(val, 1), "criteres": {k: v for k, v in r.items() if v is not None}, "pastilles": past,
                    "actif": i["actif"], "equipe": i["equipe"], "semaine": i["forme"],
                    "dem": brut["demande"].get(nom)}           # la demande brute (le Score SlabCoach s'en sert sans recalculer)
        if nouvelles_j.get(nom):
            out[nom]["actu"] = nouvelles_j[nom]["titres"]
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
        rec = 1.5 if ((base[n].get("nhl") or {}).get("saisons") or 9) <= 2 else 1.0
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
    d = {"joueurs": dict(d.get("joueurs") or {}), "indice": d.get("indice") or {}, "le": d.get("le") or 0}
    base = (demande_legale.lire() or {}).get("joueurs") or {}
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
def indice(nom):
    I = lire().get("indice") or {}
    if nom in I:
        return I[nom]
    k = _norm(nom)
    return next((v for n, v in I.items() if _norm(n) == k), None)


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
    I = d.get("indice") or {}
    if v.get("indice") is not None:
        pairs = [x for x in I.values() if x.get("actif") == v.get("actif")]
        out["rang"] = 1 + sum(1 for x in pairs if x.get("indice", 0) > v["indice"])
        out["sur"] = len(pairs)
    out["semaine"] = v.get("semaine") or forme_semaine(j)
    if not out["semaine"] and h.get("l5") is not None and v.get("actif"):
        out["cinq"] = h.get("l5")
    jours = j.get("jours") or {}
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
