"""
SLABCOACH - le signal par joueur, en direct (23 nov 2026, Mathieu : « go »). ADMIN SEULEMENT tant qu'il n'a pas fait ses preuves.

La recherche du 22 nov (docs/RECHERCHE_MODELE_22NOV.md) : ce qui fait bouger les cartes d'un joueur, c'est ce qu'il fait sur
la glace, au jour pres. On reconnait d'abord LE CAS (recrue de l'annee, jeune, veteran), puis l'evenement du soir (gros match,
tour du chapeau, sequence en feu, panne) ou un echange, et le tableau de decision donne Achete / Vends / Attends.

  - Le declencheur ne lit AUCUN prix : seulement les matchs de la LNH (api-web.nhle.com, public) et les echanges deja suivis
    par indice_joueurs. Chaque soir : 1 appel pour les matchs du jour + 1 appel par match termine (leger et poli).
  - Le JOURNAL ne se retouche pas : une ligne par signal, ecrite une fois, avec l'heure. « direct » = ecrite dans les 36 h du
    match ; sinon « rattrapage » (un soir relu apres coup : note a part).
  - La NOTE (une fois par jour) : la MEME carte, ses ventes des 7 jours d'avant contre celles des jours 8 a 60 apres
    (nos archives de ventes). Bon conseil = le prix est alle du bon cote. Mesure interne, jamais montree aux clients.
LR_SIGNAL_JOUEURS=0 coupe tout.
"""
import json
import math
import os
import statistics
import threading
import time
import unicodedata
import urllib.request
from datetime import date, datetime, timedelta

import reseau

PLAFOND_APPELS = 40                # appels a la LNH par passe (une passe par heure)
JOURS_RELUS = 45                   # on rattrape au plus 45 jours de matchs
MATCHS_GARDES = 130                # par joueur
RATTRAPAGE_JOUEURS = 5             # historiques de joueurs relus par passe (2 appels chacun)
GRANDS = ("ACHETE", "FENETRE", "VENDS", "ATTENDS")
_verrou = threading.Lock()
_ETAT = {"le": 0.0, "en_cours": False, "note_jour": None}


def actif():
    return os.environ.get("LR_SIGNAL_JOUEURS", "1") != "0"


def _norm(s):
    s = unicodedata.normalize("NFD", str(s or "").lower())
    return " ".join("".join(c for c in s if unicodedata.category(c) != "Mn").replace("-", " ").split())


def _chemin(nom):
    import comptes
    return os.path.join(comptes.DONNEES, nom)


def _lire(nom, defaut):
    try:
        with open(_chemin(nom), encoding="utf-8") as f:
            return json.load(f) or defaut
    except (OSError, ValueError):
        return defaut


def _ecrire(nom, d):
    p = _chemin(nom)
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(p + ".tmp", p)


def lire_matchs():
    return _lire("signal_matchs.json", {"joueurs": {}, "jours": {}})


def lire_journal():
    return _lire("signal_journal.json", {"journal": [], "notes": {}, "depuis": None})


# ------------------------------------------------------------------------------------------------- les regles (fonctions pures)
def saison(d):
    return d.year - (d.month < 8)


def annee_recrue(h):
    """La saison recrue (regle du Calder, sans l'age) : la derniere saison LNH jouee sans 25 matchs dans une saison d'avant ni
    6 matchs et plus dans deux saisons d'avant. C'est aussi la saison de sa carte recrue. None si on ne sait pas."""
    nhl = {}
    for x in (h or {}).get("par_saison") or []:
        if x.get("l") == "NHL" and x.get("s"):
            y = int(str(x["s"])[:4])
            nhl[y] = nhl.get(y, 0) + int(x.get("gp") or 0)
    rs, avant = None, []
    for y in sorted(nhl):
        if nhl[y] > 0 and not any(g >= 25 for g in avant) and sum(1 for g in avant if g >= 6) < 2:
            rs = y
        avant.append(nhl[y])
    return rs


def cas_joueur(annee, d):
    """recrue = sa saison recrue ; jeune = 1 ou 2 saisons apres ; veteran sinon (ou inconnu)."""
    if not annee:
        return "veteran"
    a = saison(d) - int(annee)
    return "recrue" if a <= 0 else "jeune" if a <= 2 else "veteran"


def evenements(G, i, cas):
    """G = [[jour, points, buts]] en ordre ; i = le match du soir. -> (evenements declenches par CE match, deja chaud ?)."""
    pts = [g[1] for g in G]
    p, b, ev = G[i][1], G[i][2], []
    chaud = i >= 5 and sum(pts[i - 5:i]) >= 5
    if cas == "recrue":
        if i < 3:
            return ev, chaud
        if b >= 3:
            ev.append("chapeau")
        if p >= 3 or b >= 2:
            ev.append("gros")
        if i >= 5 and sum(pts[i - 2:i + 1]) >= 5 and sum(pts[i - 3:i]) < 5:
            ev.append("feu")
        if i >= 8 and sum(pts[i - 3:i + 1]) == 0 and sum(pts[i - 4:i]) > 0 and sum(pts[:i - 3]) / (i - 3) >= 0.4:
            ev.append("panne")
        return ev, chaud
    if i < 40:
        return ev, chaud
    base = sum(pts[i - 40:i]) / 40
    if b >= 3:
        ev.append("chapeau")
    if p >= 3 or b >= 2:
        ev.append("gros")
    if sum(pts[i - 4:i + 1]) >= 5 * (base + 0.6) and sum(pts[i - 5:i]) < 5 * (base + 0.6):
        ev.append("feu")
    if base >= 0.5 and sum(pts[i - 3:i + 1]) == 0 and sum(pts[i - 4:i]) > 0:
        ev.append("panne")
    return ev, chaud


# (cas, evenement) -> (signal, raison). Les regles retirees par la recherche (aucun effet mesure) restent OBSERVE : on continue
# de les noter sans rien conseiller. Le premier evenement de ORDRE qui s'applique gagne.
ORDRE = ("panne", "chapeau", "gros", "feu")
REGLES = {
    ("recrue", "panne"): ("VENDS", "Recrue en panne : 4 matchs sans point"),
    ("jeune", "panne"): ("ATTENDS", "En panne : 4 matchs sans point"),
    ("veteran", "panne"): ("OBSERVE", "Vétéran en panne : 4 matchs sans point"),
    ("recrue", "chapeau"): ("OBSERVE", "Recrue : tour du chapeau"),
    ("recrue", "gros"): ("OBSERVE", "Recrue : gros match"),
    ("recrue", "feu"): ("OBSERVE", "Recrue en feu"),
    ("jeune", "chapeau"): ("ACHETE", "Tour du chapeau ce soir"), ("veteran", "chapeau"): ("ACHETE", "Tour du chapeau ce soir"),
    ("jeune", "gros"): ("ACHETE", "Gros match ce soir"), ("veteran", "gros"): ("ACHETE", "Gros match ce soir"),
    ("jeune", "feu"): ("ACHETE", "Séquence en feu qui commence"),
    ("veteran", "feu"): ("OBSERVE", "Vétéran en feu, sans gros match"),
}


def decision(cas, evs, chaud=False):
    """-> {signal, raison, ev, fort} ou None s'il n'y a rien ce soir. fort = tour du chapeau, ou gros match d'un joueur deja
    chaud (5 points et plus a ses 5 matchs d'avant) : le critere qui pesait le plus dans la recherche. Signaux : ACHETE (garder
    1 a 3 mois), FENETRE (fenetre de vente de 2 semaines), ATTENDS, VENDS, OBSERVE (note en silence)."""
    for e in ORDRE:
        if e in evs:
            s, r = REGLES[(cas, e)]
            fort = bool(s == "ACHETE" and (chaud or "chapeau" in evs))
            # 23 nov 2026 (la boucle complete, boucle.py / profil.py) : un gros match ISOLE fait monter les cartes 2 semaines (+7 a
            # +11 %), puis ca retombe a zero en 30 a 60 jours : pas un achat, une FENETRE de vente. Deja chaud : +13 a +17 % a 30 j,
            # et ca tient 4 mois (jeune joueur : +21 a +36 % a 60 j, 12 a 14 joueurs, a confirmer).
            if s == "ACHETE" and e == "gros" and not fort:
                s, r = "FENETRE", "Gros match isolé : ça monte 2 semaines, puis ça retombe"
            elif fort and chaud and e != "chapeau":
                r = "Gros match, déjà en feu"
            return {"signal": s, "raison": r, "ev": e, "fort": fort}
    return None


def decision_echange(sens):
    """Un echange : arriver a Toronto ou Montreal = Achete (fort) ; en partir = Vends ; le reste = observe."""
    if sens == "hausse":
        return {"signal": "ACHETE", "raison": "Échangé vers un gros marché", "ev": "echange", "fort": True}
    if sens == "baisse":
        return {"signal": "VENDS", "raison": "Quitte un gros marché", "ev": "echange", "fort": False}
    return {"signal": "OBSERVE", "raison": "Nouvelle équipe", "ev": "echange", "fort": False}


# ------------------------------------------------------------------------------------------------- les matchs de la LNH
def _get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "SlabCoach/1.0 (+https://www.slabcoach.com)"})
    try:
        with reseau.ouvrir(req, timeout=15) as r:
            return json.loads(r.read() or b"null")
    except Exception:
        return None


def lire_soir(jour, deja=(), plafond=PLAFOND_APPELS, get=None):
    """Les matchs de saison reguliere d'un jour : -> {appels, total, lus: [ids de matchs lus cette fois], fini, lignes: {id joueur:
    [points, buts]}}. deja = les matchs deja lus. fini = tous les matchs du jour sont termines ET lus."""
    get = get or _get
    s = get(f"https://api-web.nhle.com/v1/score/{jour}")
    out = {"appels": 1, "total": 0, "lus": [], "fini": False, "lignes": {}, "ok": isinstance(s, dict)}
    if not out["ok"]:
        return out
    jeux = [g for g in s.get("games") or [] if isinstance(g, dict) and g.get("gameType") == 2 and str(g.get("gameDate") or jour)[:10] == jour]
    out["total"] = len(jeux)
    reste = 0
    for g in jeux:
        gid = str(g.get("id"))
        if gid in deja:
            continue
        if g.get("gameState") not in ("OFF", "FINAL") or out["appels"] >= plafond:
            reste += 1
            continue
        b = get(f"https://api-web.nhle.com/v1/gamecenter/{gid}/boxscore")
        out["appels"] += 1
        pb = (b or {}).get("playerByGameStats") if isinstance(b, dict) else None
        n = 0
        for cote in ("awayTeam", "homeTeam"):
            for grp in ("forwards", "defense"):
                for x in ((pb or {}).get(cote) or {}).get(grp) or []:
                    if isinstance(x, dict) and x.get("playerId"):
                        out["lignes"][str(x["playerId"])] = [int(x.get("points") or 0), int(x.get("goals") or 0)]
                        n += 1
        if n < 20:                                   # sommaire illisible : on reviendra
            reste += 1
            continue
        out["lus"].append(gid)
    out["fini"] = reste == 0
    return out


def historique(pid, saisons, get=None):
    """Les matchs de saison reguliere d'un joueur (2 saisons) -> [[jour, points, buts]]."""
    get = get or _get
    out = []
    for s in saisons:
        d = get(f"https://api-web.nhle.com/v1/player/{pid}/game-log/{s}/2")
        for g in (d or {}).get("gameLog") or [] if isinstance(d, dict) else []:
            le = str(g.get("gameDate") or "")[:10]
            if le:
                out.append([le, int(g.get("points") or 0), int(g.get("goals") or 0)])
    return sorted(out)


def _ajouter(M, pid, jour, pts, buts, nom=None):
    j = M["joueurs"].setdefault(pid, {"m": []})
    if nom:
        j["nom"] = nom
    if any(x[0] == jour for x in j["m"]):
        return False
    j["m"].append([jour, pts, buts])
    j["m"].sort()
    del j["m"][:-MATCHS_GARDES]
    return True


def _suivis():
    """Nos joueurs actifs : {id LNH: (nom, fiche LNH)}."""
    try:
        import demande_legale
        base = (demande_legale.lire() or {}).get("joueurs") or {}
    except Exception:
        base = {}
    out = {}
    for nom, e in base.items():
        h = (e or {}).get("nhl") or {}
        if h.get("id") and h.get("actif") is not False:
            out[str(h["id"])] = (nom, h)
    return out


def _amorcer(M, suivis):
    """Une fois : l'historique deja garde par le test SlabIQ (les 600 joueurs les plus vendus), sans un seul appel."""
    if M.get("amorce"):
        return 0
    M["amorce"] = True
    try:
        import slabiq_test
        cache = (slabiq_test._cache_lire() or {}).get("nhl") or {}
    except Exception:
        return 0
    par_nom = {_norm(nom): pid for pid, (nom, _h) in suivis.items()}
    n = 0
    for k, v in cache.items():
        pid = par_nom.get(_norm(k.split("|")[0]))
        for g in (v or {}).get("matchs") or [] if pid else []:
            n += _ajouter(M, pid, str(g[0])[:10], int(g[1]), int(g[2]))
    return n


def _entree(pid, nom, jour, cas, dec, pts, buts, maint, direct_h=36):
    try:
        age_h = (maint - datetime.fromisoformat(jour + "T22:00:00")).total_seconds() / 3600
    except ValueError:
        age_h = 999
    return {"id": f"{pid}:{jour}:{dec['ev']}", "nom": nom, "jour": jour, "cas": cas, "ev": dec["ev"], "signal": dec["signal"],
            "fort": dec["fort"], "raison": dec["raison"], "pts": pts, "buts": buts, "cree": maint.isoformat(timespec="minutes"),
            "direct": age_h <= direct_h}


def passe(maintenant=None, get=None, suivis=None, echanges=None):
    """Lit les soirs manquants (les plus vieux d'abord), ecrit les signaux. -> {appels, soirs, signaux}."""
    maint = maintenant or datetime.now()
    auj = maint.date()
    suivis = _suivis() if suivis is None else suivis
    with _verrou:
        M, J = lire_matchs(), lire_journal()
    _amorcer(M, suivis)
    vus = {e["id"] for e in J["journal"]}
    J["depuis"] = J.get("depuis") or (auj - timedelta(days=2)).isoformat()
    appels, soirs, nouveaux = 0, 0, []
    a_rattraper = [tuple(x) for x in M.get("file") or []]      # les soirs en attente d'un historique (gardes d'une passe a l'autre)
    for k in range(JOURS_RELUS, -1, -1):
        jour = (auj - timedelta(days=k)).isoformat()
        e = M["jours"].get(jour) or {}
        if e.get("fini") or appels >= PLAFOND_APPELS - 1:
            continue
        if k == 0 and maint.hour < 15:               # aujourd'hui : pas avant l'apres-midi (les matchs commencent le soir)
            continue
        r = lire_soir(jour, set(e.get("lus") or []), PLAFOND_APPELS - appels, get)
        appels += r["appels"]
        if not r["ok"]:
            break
        soirs += 1
        essais = int(e.get("essais") or 0) + 1               # un match remis ou illisible : on n'insiste pas plus de 6 fois
        M["jours"][jour] = {"total": r["total"], "lus": sorted(set(e.get("lus") or []) | set(r["lus"])), "essais": essais,
                            "fini": bool(r["fini"] and (k > 0 or r["total"] > 0)) or (k > 2 and essais >= 6)}
        for pid, (pts, buts) in r["lignes"].items():
            nom = (suivis.get(pid) or (None,))[0]
            if not _ajouter(M, pid, jour, pts, buts, nom) or pid not in suivis:
                continue
            nom, h = suivis[pid]
            cas = cas_joueur(annee_recrue(h), date.fromisoformat(jour))
            G = M["joueurs"][pid]["m"]
            i = next(x for x, g in enumerate(G) if g[0] == jour)
            court = i < 9 if cas == "recrue" else (i < 40 and (pts >= 3 or buts >= 2 or cas == "jeune"))
            if court and not M["joueurs"][pid].get("relu"):
                a_rattraper.append((pid, jour))          # pas assez d'historique pour juger : on le relit, puis on rejuge
                continue
            evs, chaud = evenements(G, i, cas)
            dec = decision(cas, evs, chaud)
            if dec:
                en = _entree(pid, nom, jour, cas, dec, pts, buts, maint)
                if en["id"] not in vus:
                    vus.add(en["id"]); nouveaux.append(en)
    # l'historique des joueurs qui en manquent (quelques-uns par passe), puis leur soir est rejuge
    an = saison(auj)
    a_rattraper = list(dict.fromkeys(x for x in a_rattraper if x[0] in suivis))
    M["file"] = [list(x) for x in a_rattraper[RATTRAPAGE_JOUEURS:][:300]]
    for pid, jour in a_rattraper[:RATTRAPAGE_JOUEURS]:
        for g in historique(pid, (f"{an - 1}{an}", f"{an}{an + 1}"), get):
            _ajouter(M, pid, g[0], g[1], g[2])
        appels += 2
        M["joueurs"][pid]["relu"] = True
        nom, h = suivis[pid]
        cas = cas_joueur(annee_recrue(h), date.fromisoformat(jour))
        G = M["joueurs"][pid]["m"]
        i = next((x for x, g in enumerate(G) if g[0] == jour), None)
        if i is None:
            continue
        evs, chaud = evenements(G, i, cas)
        dec = decision(cas, evs, chaud)
        if dec:
            en = _entree(pid, nom, jour, cas, dec, G[i][1], G[i][2], maint)
            if en["id"] not in vus:
                vus.add(en["id"]); nouveaux.append(en)
    # les echanges (deja suivis par indice_joueurs : alignements et manchettes)
    if echanges is None:
        try:
            import indice_joueurs
            echanges = {n: indice_joueurs.echange_de(n) for n in (indice_joueurs.lire().get("echanges") or {})}
        except Exception:
            echanges = {}
    for nom, x in (echanges or {}).items():
        if not x or str(x.get("le") or "") < J["depuis"] or x.get("source") == "saisons" or x.get("source") == "alignements":
            continue                                     # seulement les echanges dates du jour (vus ou annonces), depuis le depart
        dec = decision_echange(x.get("sens"))
        en = _entree("ech", nom, str(x["le"])[:10], "echange", dec, 0, 0, maint, direct_h=72)
        en["id"] = f"ech:{_norm(nom)}:{x.get('vers')}"
        en["raison"] = f"{dec['raison']} : {x.get('de_nom') or x.get('de')} → {x.get('vers_nom') or x.get('vers')}"
        if en["id"] not in vus:
            vus.add(en["id"]); nouveaux.append(en)
    J["journal"].extend(sorted(nouveaux, key=lambda e: (e["jour"], e["nom"])))
    M["le"] = J["le"] = time.time()
    with _verrou:
        _ecrire("signal_matchs.json", M)
        _ecrire("signal_journal.json", J)
    return {"appels": appels, "soirs": soirs, "signaux": len(nouveaux)}


# ------------------------------------------------------------------------------------------------- la note (meme carte, avant / apres)
def _cle_carte(titre, nom):
    import cartes_match
    d = cartes_match._decoder_memo(titre)
    g = d.get("grade") or {}
    par = tuple(sorted(d.get("paralleles") or ()))
    if d.get("num"):
        coeur = "#" + str(d["num"])
    else:
        mots, marques = cartes_match.identite(titre, nom)
        coeur = tuple(sorted(mots | marques))
    return (d.get("annee"), coeur, d.get("serie"), par, bool(d.get("auto")), bool(d.get("patch")), bool(d.get("inscr")), g.get("cie"), g.get("note"))


def _carte_forte(titre):
    try:
        import bareme_iq
        so, _ra = bareme_iq.sorte(titre)
        return bareme_iq.NOTE[so] >= 88
    except Exception:
        return False


def ventes_de(noms, depuis):
    """Nos archives : {nom normalise: [(jour, prix, titre)]} pour ces joueurs, depuis ce jour. Lu en continu (peu de memoire)."""
    import base_ventes
    import cartes_match
    out = {k: [] for k in noms}
    try:
        c = base_ventes._cx()
    except Exception:
        return out
    try:
        plan = {q: j for q, j in c.execute("SELECT q, joueur FROM plan WHERE joueur IS NOT NULL")}
        larges, memo = set(getattr(base_ventes, "SORTES_Q", ()) or ()), {}
        for n_, (q, titre, prix, le) in enumerate(c.execute("SELECT q, titre, prix, le FROM ventes WHERE le >= ? AND prix >= 3", (depuis,))):
            if n_ % 2000 == 1999:
                time.sleep(0.01)                      # on laisse respirer le serveur (lecture longue, en arriere-plan)
            if q in larges:
                k = _norm(cartes_match.joueur_du_titre(titre or ""))
            else:
                if q not in memo:
                    memo[q] = _norm(plan.get(q) or cartes_match.joueur_du_titre(q or ""))
                k = memo[q]
            if k in out:
                out[k].append((str(le)[:10], float(prix), titre or ""))
    except Exception as e:
        print("Signal joueurs (ventes) : " + repr(e)[:160], flush=True)
    finally:
        c.close()
    return out


def mesurer(ventes, nom, jour, auj):
    """ventes = [(jour, prix, titre)] du joueur. -> {y, n, yf, nf} : la mediane, sur ses cartes, de ln(prix des jours 8 a 60 apres /
    prix des 7 jours d'avant), pour toutes ses cartes (y, n) et pour les cartes fortes selon SlabIQ (yf, nf). None si rien."""
    d = date.fromisoformat(jour)
    a0, a1 = (d - timedelta(days=7)).isoformat(), (d - timedelta(days=1)).isoformat()
    b0, b1 = (d + timedelta(days=8)).isoformat(), min(d + timedelta(days=60), auj).isoformat()
    c0, c1 = (d + timedelta(days=2)).isoformat(), min(d + timedelta(days=14), auj).isoformat()      # la fenetre de vente (FENETRE)
    C = {}
    for le, prix, titre in ventes:
        cotes = (["a"] if a0 <= le <= a1 else []) + (["b"] if b0 <= le <= b1 else []) + (["c"] if c0 <= le <= c1 else [])
        for cote in cotes:
            C.setdefault(_cle_carte(titre, nom), {"a": [], "b": [], "c": [], "t": titre})[cote].append(prix)
    tous, forts, tot = [], [], []
    for c in C.values():
        if c["a"] and c["b"]:
            v = math.log(statistics.median(c["b"]) / statistics.median(c["a"]))
            tous.append(v)
            if _carte_forte(c["t"]):
                forts.append(v)
        if c["a"] and c["c"]:
            tot.append(math.log(statistics.median(c["c"]) / statistics.median(c["a"])))
    if not tous and not tot:
        return None
    return {"y": round(statistics.median(tous), 4) if tous else None, "n": len(tous), "yf": round(statistics.median(forts), 4) if forts else None,
            "nf": len(forts), "y14": round(statistics.median(tot), 4) if tot else None, "n14": len(tot)}


def noter(maintenant=None, ventes=None):
    """Une fois par jour : note les signaux de 9 a 75 jours (la note bouge jusqu'au jour 60, puis elle est finale)."""
    auj = (maintenant or datetime.now()).date()
    with _verrou:
        J = lire_journal()
    a_noter = [e for e in J["journal"] if (auj - date.fromisoformat(e["jour"])).days >= 9 and not (J["notes"].get(e["id"]) or {}).get("final")]
    if not a_noter:
        return 0
    noms = {_norm(e["nom"]) for e in a_noter}
    depuis = (min(date.fromisoformat(e["jour"]) for e in a_noter) - timedelta(days=8)).isoformat()
    V = ventes_de(noms, depuis) if ventes is None else ventes
    n = 0
    for e in a_noter:
        final = (auj - date.fromisoformat(e["jour"])).days >= 61
        m = mesurer(V.get(_norm(e["nom"])) or [], e["nom"], e["jour"], auj)
        if m or final:
            J2 = dict(m or {}, le=auj.isoformat(), final=final)
            J["notes"][e["id"]] = J2
            n += 1
    with _verrou:
        frais = lire_journal()                       # le journal a pu grandir pendant la note : on ne garde que les notes
        frais["notes"] = dict(frais.get("notes") or {}, **J["notes"])
        _ecrire("signal_journal.json", frais)
    return n


def bilan(J=None):
    """Le tableau de bord : par signal, combien, combien de notes, la mediane et « bon conseil sur 10 »."""
    J = J or lire_journal()
    N = J.get("notes") or {}

    def ligne(L, sens, cle="y"):
        v = [N[e["id"]][cle] for e in L if (N.get(e["id"]) or {}).get(cle) is not None]
        if not v:
            return {"n": len(L), "notes": 0}
        bon = sum(1 for x in v if (x > 0 if sens > 0 else x < 0)) / len(v)
        return {"n": len(L), "notes": len(v), "med": round(100 * (math.exp(statistics.median(v)) - 1), 1), "bon": round(10 * bon, 1)}
    out = {}
    for nom_, filtre in (("direct", lambda e: e.get("direct")), ("rattrapage", lambda e: not e.get("direct"))):
        L = [e for e in J.get("journal") or [] if filtre(e)]
        A = [e for e in L if e["signal"] == "ACHETE"]
        out[nom_] = {"achete": ligne(A, 1), "achete_fort": ligne([e for e in A if e.get("fort")], 1), "achete_cartes_fortes": ligne(A, 1, "yf"),
                     "fenetre": ligne([e for e in L if e["signal"] == "FENETRE"], 1, "y14"),
                     "vends": ligne([e for e in L if e["signal"] == "VENDS"], -1), "attends": ligne([e for e in L if e["signal"] == "ATTENDS"], -1),
                     "observe": {"n": sum(1 for e in L if e["signal"] == "OBSERVE")}}
    return out


def admin():
    """Pour la feuille Admin -> Mesures -> Signal par joueur."""
    J, M = lire_journal(), lire_matchs()
    N = J.get("notes") or {}
    dern = sorted(J.get("journal") or [], key=lambda e: (e["jour"], e.get("cree") or ""), reverse=True)
    lignes = [dict({k: e.get(k) for k in ("nom", "jour", "signal", "fort", "raison", "cas", "ev", "pts", "buts", "direct")},
                   note=(lambda n, k: None if not n or n.get(k) is None else round(100 * (math.exp(n[k]) - 1), 1))(N.get(e["id"]), "y14" if e["signal"] == "FENETRE" else "y"))
              for e in dern if e["signal"] in GRANDS][:40]
    jours = M.get("jours") or {}
    return {"ok": True, "actif": actif(), "depuis": J.get("depuis"), "le": J.get("le"), "signaux": len(J.get("journal") or []),
            "soirs": sum(1 for x in jours.values() if x.get("fini")), "dernier_soir": max((k for k, x in jours.items() if x.get("lus")), default=None),
            "joueurs": len(M.get("joueurs") or {}), "bilan": bilan(J), "derniers": lignes}


def passe_si_besoin():
    """Chaque heure (server.py) : les soirs manquants ; une fois par jour : la note."""
    if not actif() or _ETAT["en_cours"] or time.time() - _ETAT["le"] < 3000:
        return False
    _ETAT["le"] = time.time()

    def tache():
        _ETAT["en_cours"] = True
        try:
            r = passe()
            if r.get("signaux"):
                print("Signal joueurs : " + json.dumps(r), flush=True)
            jour = date.today().isoformat()
            if _ETAT["note_jour"] != jour and datetime.now().hour >= 4:
                _ETAT["note_jour"] = jour
                n = noter()
                if n:
                    print(f"Signal joueurs : {n} notes", flush=True)
        except Exception as e:
            print("Signal joueurs : " + repr(e)[:200], flush=True)
        finally:
            _ETAT["en_cours"] = False
    threading.Thread(target=tache, daemon=True, name="signal_joueurs").start()
    return True
