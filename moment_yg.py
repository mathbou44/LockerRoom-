"""
SLABCOACH - le MOMENT d'achat d'un joueur, lu sur sa Young Guns (15 nov 2026).

Mathieu : « SlabIQ doit aider a choisir quel joueur et quelle carte acheter, a quel moment, et pourquoi ; on doit etre parfait
sur le timing » ; « la Young Guns est la carte mere d'Upper Deck : si elle perd, tout le reste du joueur perd » ; « itere
jusqu'a ce que le gain soit reel » ; « on ne doit jamais arreter d'iterer et d'ameliorer SlabIQ ».

Ce que l'etude de 18 mois (banque YG : 62 858 ventes, 160 joueurs, mai 2025 - nov 2026) a montre :
  - un modele appris sur le timing seul fait gagner ~5 % et se trompe quand le marche change de sens ;
  - des REGLES SIMPLES sur la YG du joueur tiennent dans le marche qui monte ET dans celui qui baisse :
      chute de 20 %+ en 2 semaines : +15 % deux mois apres ; sous sa moyenne de 6 mois (z <= -1) : +11 a +25 % ;
      flambee de 15 %+ en 2 semaines : -11 a -13 % ; au-dessus de sa moyenne de 6 mois (z >= +1) : -8 a -12 % ;
  - le gain REEL vient du rabais (payer sous le marche) COMBINE au moment : une vraie vente a -25 % dans un moment
    favorable valait plus 2 mois apres 91 % du temps (profit apres frais 13 % : 81 %) ; -25 % et au plus bas depuis 6 mois :
    96 % (86 %) ; un achat typique : 35 % (22 %).

Ce module :
  1. range les ventes de la banque : la YG de BASE du joueur, raw et PSA 10 (memes filtres que l'etude) ;
  2. fait l'indice YG du joueur (mediane des 14 derniers jours, raw et PSA 10 combines) et ses facteurs ;
  3. dit l'ETAT du joueur (creux_fort, creux, neutre, flambee) et le VERDICT d'une annonce (etat x rabais), avec le pourquoi ;
  4. ITERE sans arret (chaque semaine) : remesure les regles sur les ventes les plus recentes, essaie des seuils voisins
     (le « challenger »), et ne remplace les regles en place que si le challenger fait mieux sur les mois RECENTS qu'il n'a
     pas servi a choisir. Chaque essai est garde (historique), et les taux affiches viennent de la derniere mesure.
Les prix viennent des ventes (CompSniper) : comps = admin seulement (lockerroom.comps_permis).
"""
import json
import math
import re
import threading
import time
from collections import defaultdict
from datetime import date

import numpy as np

W = 14                                   # jours de la mediane
FRAIS = math.log(1 / 0.87)               # 13 % de frais a la revente
H0, H1 = 46, 74                          # « deux mois apres » : la mediane des ventes entre J+46 et J+74
REGLES_V1 = {"chute14": -0.10, "z_bas": -1.0, "sous_sommet56": -0.25, "flambee14": 0.15, "flambee28": 0.25, "z_haut": 1.0,
             "volume_x": 2.0, "rabais_bon": 0.15, "rabais_fort": 0.25}
_verrou = threading.Lock()
_CACHE = {"jour": None, "etats": {}, "regles": None, "stats": None}

EXCL = re.compile(r"renewed|checklist|canvas|clear ?cut|exclusive|high gloss|silver|foil|french|retro|\bauto|patch|\blot\b|\bx\d|w/|\bset\b|oversiz|"
                  r"outburst|dazzler|reprint|custom|gmg|\bread\b|portrait|achievement|mini\b|jumbo|\d+/\d+|#'?d\b|numbered|\bsp\b|deluxe|blue|red|"
                  r"gold|green|purple|orange|pink|black|rainbow|sparkle|printing plate|1/1|proof|mystery|seal|box|pack|hobby box|case|bundle|2x|3x|"
                  r"\(2\)|\(3\)|pick|choose|you pick|complete|team set|insert|cgc|bgs|sgc|tag\b|\bksa\b|\bhga\b|\bisa\b|beckett|mnt|ace\b|psa (?!10)")
EQUIPES = re.compile(r"red wings|blue jackets|st\.? louis blues|\bblues\b|golden knights|blackhawks|black hawks|maple leafs|flyers|kraken|"
                     r"lightning|hurricanes|devils|rangers|islanders|penguins|capitals|bruins|sabres|senators|canadiens|habs|oilers|flames|"
                     r"canucks|jets|wild|predators|stars|avalanche|coyotes|utah|mammoth|sharks|kings|ducks|panthers|red\s*/\s*white|white\s*border")
GR10 = re.compile(r"psa\s*10|psa\s*gem\s*m?t?\s*10|psa\s*gem mint 10")


def _annee(t):
    m = re.search(r"\b(19|20)(\d\d)\s*[-/]\s*(\d\d)\b", t) or re.search(r"\b(19|20)(\d\d)\b", t)
    return int(m.group(1) + m.group(2)) if m else None


def classer(titre, joueur):
    """-> 'raw' | 'psa10' | None : la YG de BASE du joueur seulement (pas les paralleles, lots, autres gradeurs)."""
    t = str(titre or "").lower()
    if "young guns" not in t and " yg " not in f" {t} ":
        return None
    fam = str(joueur or "").lower().split()[-1:] or [""]
    if not fam[0] or fam[0] not in t:
        return None
    psa10 = bool(GR10.search(t))
    t2 = EQUIPES.sub(" ", GR10.sub(" ", t))
    if EXCL.search(t2) or re.search(r"\bpsa\b", t2):
        return None
    return "psa10" if psa10 else "raw"


def ventes_par_joueur(lignes):
    """lignes : (joueur, titre, prix_usd, le 'AAAA-MM-JJ') -> {joueur: {'raw': [(jour_ordinal, prix)], 'psa10': [...]}}
    (l'annee de la YG = la plus frequente dans ses titres : les ventes d'une autre annee sont ecartees)."""
    R = defaultdict(lambda: defaultdict(list))
    for j, titre, prix, le in lignes:
        try:
            p = float(prix)
            o = date.fromisoformat(str(le)[:10]).toordinal()
        except (TypeError, ValueError):
            continue
        if p <= 0.5:
            continue
        g = classer(titre, j)
        if g:
            R[j][g].append((o, p, _annee(str(titre).lower())))
    out = {}
    for j, gg in R.items():
        out[j] = {}
        for g, l in gg.items():
            ans = defaultdict(int)
            for _, _, a in l:
                if a:
                    ans[a] += 1
            a0 = max(ans, key=ans.get) if ans else None
            out[j][g] = sorted((o, p) for o, p, a in l if a in (a0, None))
    return out


def _offset(r, s):
    """L'ecart (log) PSA 10 / raw, mois par mois ; None si trop peu de mois en commun."""
    mr, ms = defaultdict(list), defaultdict(list)
    for o, p in r:
        mr[o // 30].append(math.log(p))
    for o, p in s:
        ms[o // 30].append(math.log(p))
    dif = [np.median(ms[m]) - np.median(mr[m]) for m in ms if m in mr and len(ms[m]) >= 3 and len(mr[m]) >= 3]
    return float(np.median(dif)) if len(dif) >= 2 else None


def indice(vj):
    """vj = {'raw': [...], 'psa10': [...]} -> {'P': {jour: log mediane 14 j}, 'N': {jour: ventes 14 j}, 'd0': 1re vente} ou None."""
    r, s = vj.get("raw") or [], vj.get("psa10") or []
    if len(r) + len(s) < 40:
        return None
    if len(r) >= 15 and len(s) >= 15:
        off = _offset(r, s)
        V = [(o, math.log(p)) for o, p in r] + ([(o, math.log(p) - off) for o, p in s] if off is not None else [])
    else:
        V = [(o, math.log(p)) for o, p in (r if len(r) >= len(s) else s)]
    V.sort()
    o = np.array([v[0] for v in V])
    lp = np.array([v[1] for v in V])
    P, N = {}, {}
    for d in range(int(o[0]) + W, int(o[-1]) + 1):
        a, b = np.searchsorted(o, d - W, "right"), np.searchsorted(o, d, "right")
        if b - a >= 3:
            P[d] = float(np.median(lp[a:b]))
        N[d] = int(b - a)
    return {"P": P, "N": N, "d0": int(o[0])} if P else None


def _avant(D, d, recul=3):
    for k in range(d, d - recul - 1, -1):
        if k in D:
            return D[k]
    return None


def facteurs(ix, d):
    """Les facteurs du jour d (le passe seulement). None si l'indice n'a pas de prix ce jour-la (ou 3 jours avant)."""
    P = ix["P"]
    p = _avant(P, d)
    if p is None:
        return None
    h56 = [P[k] for k in range(d - 56, d + 1) if k in P]
    h182 = [P[k] for k in range(d - 182, d + 1) if k in P]
    if len(h56) < 15:
        return None
    q14, q28 = _avant(P, d - 14), _avant(P, d - 28)
    n14 = ix["N"].get(d, 0)
    n56 = np.mean([ix["N"].get(d - k, 0) for k in (14, 28, 42, 56)])
    return {"mom14": p - q14 if q14 is not None else None, "mom28": p - q28 if q28 is not None else None,
            "dd56": p - max(h56), "z182": (p - float(np.mean(h182))) / (float(np.std(h182)) + 0.05) if len(h182) > 30 else None,
            "volrel": n14 / (n56 + 0.5), "niveau": p}


def etat_de(f, R=None):
    """facteurs -> (etat, raisons). etat : creux_fort | creux | neutre | flambee."""
    R = R or REGLES_V1
    if not f:
        return "inconnu", []
    m14, m28, z, dd, vr = f.get("mom14"), f.get("mom28"), f.get("z182"), f.get("dd56"), f.get("volrel") or 0
    pct = lambda v: round(100 * (math.exp(v) - 1))
    if (m14 is not None and m14 >= math.log(1 + R["flambee14"])) or (m28 is not None and m28 >= math.log(1 + R["flambee28"])) \
            or (z is not None and z >= R["z_haut"]):
        rs = []
        if m14 is not None and m14 >= math.log(1 + R["flambee14"]):
            rs.append(f"YG +{pct(m14)} % en 2 semaines")
        elif m28 is not None and m28 >= math.log(1 + R["flambee28"]):
            rs.append(f"YG +{pct(m28)} % en 4 semaines")
        if z is not None and z >= R["z_haut"]:
            rs.append("au-dessus de sa moyenne de 6 mois")
        return "flambee", rs
    bon, rs = False, []
    if m14 is not None and m14 <= math.log(1 + R["chute14"]):
        bon = True
        rs.append(f"YG {pct(m14)} % en 2 semaines")
    if z is not None and z <= R["z_bas"]:
        bon = True
        rs.append("au plus bas depuis 6 mois")
    if dd <= math.log(1 + R["sous_sommet56"]):
        bon = True
        rs.append(f"{pct(dd)} % sous son sommet de 8 semaines")
    if bon and vr >= R["volume_x"]:
        return "neutre", rs + ["mais beaucoup de ventes d'un coup"]
    if bon:
        return ("creux_fort" if (z is not None and z <= R["z_bas"]) else "creux"), rs
    return "neutre", []


def verdict(etat, rabais_pct, R=None, stats=None):
    """L'etat du joueur x le rabais de l'annonce (% sous la valeur) -> {niveau 0-3, texte, taux (mesure), ...} ou None."""
    R = R or REGLES_V1
    if etat in (None, "inconnu"):
        return None
    r = (rabais_pct or 0) / 100.0
    if etat == "flambee":
        return {"niveau": 0, "texte": "Attendre", "cle": "flambee"}
    cle = None
    if etat in ("creux", "creux_fort") and r >= R["rabais_fort"]:
        cle = "fort_bas" if etat == "creux_fort" else "fort"
    elif etat in ("creux", "creux_fort") and r >= R["rabais_bon"]:
        cle = "bon"
    if not cle:
        return None
    st = (stats or {}).get(cle) or {}
    return {"niveau": 3 if cle in ("fort", "fort_bas") else 2, "texte": "Bon moment" if cle == "bon" else "Feu vert", "cle": cle,
            "taux_vaut_plus": st.get("vaut_plus"), "taux_profit": st.get("profit"), "n": st.get("n")}


# -- la mesure (backtest) et l'iteration continue ---------------------------------------------------------------------
def _ventes_test(V, IX):
    """Chaque vraie vente YG : (joueur, jour, rabais log vs mediane 14 j de la meme gradation, issue log 2 mois apres, grade)."""
    out = []
    for j, gg in V.items():
        if j not in IX:
            continue
        for g, l in gg.items():
            if len(l) < 30:
                continue
            o = np.array([x[0] for x in l])
            lp = np.log([x[1] for x in l])
            for k in range(len(o)):
                d = int(o[k])
                a, b = np.searchsorted(o, d - 14, "right"), np.searchsorted(o, d, "left")
                if b - a < 3:
                    continue
                disc = lp[k] - float(np.median(lp[a:b]))
                if disc < math.log(0.55):           # trop beau : une autre carte, une carte abimee
                    continue
                a2, b2 = np.searchsorted(o, d + H0), np.searchsorted(o, d + H1)
                y = float(np.median(lp[a2:b2])) - lp[k] if b2 - a2 >= 3 else None
                out.append((j, d, disc, y, g))
    return out


def mesurer(T, IX, R, depuis=None, jusqua=None):
    """Les taux de chaque verdict sur les ventes test T (entre depuis et jusqua, en jours ordinaux)."""
    acc = defaultdict(list)
    for j, d, disc, y, g in T:
        if y is None or (depuis and d < depuis) or (jusqua and d >= jusqua):
            continue
        e, _ = etat_de(facteurs(IX[j], d), R)
        acc["tout"].append(y)
        v = verdict(e, -100 * (math.exp(disc) - 1), R)
        if v:
            acc[v["cle"]].append(y)
            if v["cle"] in ("fort", "fort_bas"):
                acc["feu_vert"].append(y)
    st = {}
    for k, ys in acc.items():
        a = np.array(ys)
        st[k] = {"n": int(len(a)), "vaut_plus": round(100 * float((a > 0).mean())), "profit": round(100 * float((a > FRAIS).mean())),
                 "gain_median": round(100 * (math.exp(float(np.median(a))) - 1), 1)}
    return st


def _note(st):
    """Ce qu'on cherche a maximiser : le profit apres frais des Feux verts, s'il y en a assez (sinon tres bas)."""
    f = st.get("feu_vert") or {}
    if (f.get("n") or 0) < 60:
        return -1.0
    return f["profit"] + 0.25 * (st.get("bon") or {}).get("profit", 0) + 2.0 * math.log(f["n"] / 60.0)


def voisins(R):
    """Les challengers : chaque seuil pousse d'un cran de chaque cote (un a la fois)."""
    pas = {"chute14": 0.05, "z_bas": 0.25, "sous_sommet56": 0.05, "flambee14": 0.05, "flambee28": 0.05, "z_haut": 0.25,
           "volume_x": 0.5, "rabais_bon": 0.05, "rabais_fort": 0.05}
    out = []
    for k, s in pas.items():
        for sens in (-1, 1):
            r2 = dict(R)
            r2[k] = round(R[k] + sens * s, 3)
            if r2["rabais_bon"] < 0.05 or r2["rabais_fort"] <= r2["rabais_bon"] or r2["rabais_fort"] > 0.4 or r2["volume_x"] < 1.2:
                continue
            out.append(r2)
    return out


def iterer(V, aujourd=None, R=None):
    """Une iteration : les regles en place vs leurs voisines. On CHOISIT sur les mois plus anciens (jusqu'a 4 mois avant
    aujourd'hui) et on VALIDE sur les 4 derniers mois mesurables (jamais vus pendant le choix). Le challenger ne gagne que s'il
    fait mieux aux deux endroits. -> {regles, change, stats (sur tout), choix, validation}."""
    R = dict(R or REGLES_V1)
    IX = {j: ix for j, ix in ((j, indice(v)) for j, v in V.items()) if ix}
    T = _ventes_test(V, IX)
    auj = (aujourd or date.today()).toordinal()
    fin = auj - H1                                  # une vente plus recente n'a pas encore son « deux mois apres »
    coupe = fin - 120
    base_a, base_b = mesurer(T, IX, R, jusqua=coupe), mesurer(T, IX, R, depuis=coupe, jusqua=fin)
    best, best_a = R, _note(base_a)
    for r2 in voisins(R):
        na = _note(mesurer(T, IX, r2, jusqua=coupe))
        if na > best_a + 1.0:
            best, best_a = r2, na
    change = False
    if best is not R:
        vb = mesurer(T, IX, best, depuis=coupe, jusqua=fin)
        if _note(vb) >= _note(base_b) + 1.0:     # mieux aussi sur les mois recents : il remplace les regles en place
            R, base_b, change = best, vb, True
    return {"regles": R, "change": change, "stats": mesurer(T, IX, R, jusqua=fin), "validation": base_b,
            "ventes_test": len(T), "joueurs": len(IX)}


# -- la base : etats du jour, regles en place, historique des iterations ------------------------------------------------
def _cx():
    import banque_yg
    c = banque_yg._cx()
    c.execute("CREATE TABLE IF NOT EXISTS moment (joueur TEXT PRIMARY KEY, jour TEXT, etat TEXT, raisons TEXT, facteurs TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS moment_regles (id INTEGER PRIMARY KEY AUTOINCREMENT, le TEXT, regles TEXT, stats TEXT,"
              " validation TEXT, change INTEGER, ventes_test INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS moment_journal (cle TEXT PRIMARY KEY, jour TEXT, joueur TEXT, titre TEXT, total REAL,"
              " valeur REAL, rabais INTEGER, etat TEXT, verdict TEXT, plus_tard REAL, verifie_le TEXT)")
    return c


def _lignes_banque():
    c = _cx()
    try:
        return c.execute("SELECT joueur, titre, prix_usd, le FROM ventes WHERE prix_usd IS NOT NULL").fetchall()
    finally:
        c.close()


def regles_en_place():
    c = _cx()
    try:
        r = c.execute("SELECT regles, stats FROM moment_regles ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        c.close()
    if not r:
        return dict(REGLES_V1), None
    return {**REGLES_V1, **json.loads(r[0])}, json.loads(r[1] or "null")


def calculer_jour(aujourd=None):
    """Chaque jour : l'etat de chaque joueur de la banque. -> nombre de joueurs."""
    jour = (aujourd or date.today())
    V = ventes_par_joueur(_lignes_banque())
    R, st = regles_en_place()
    lignes = []
    for j, vj in V.items():
        ix = indice(vj)
        if not ix:
            continue
        d = min(jour.toordinal(), max(ix["P"]) + 3)
        f = facteurs(ix, d) if jour.toordinal() - max(ix["P"]) <= 21 else None    # pas de vente depuis 3 semaines : inconnu
        e, rs = etat_de(f, R)
        lignes.append((j, jour.isoformat(), e, json.dumps(rs, ensure_ascii=False),
                       json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in (f or {}).items()})))
    with _verrou:
        c = _cx()
        try:
            c.executemany("INSERT OR REPLACE INTO moment VALUES (?,?,?,?,?)", lignes)
            c.commit()
        finally:
            c.close()
    _CACHE.update(jour=None)
    return len(lignes)


def _charger_cache():
    auj = date.today().isoformat()
    if _CACHE["jour"] == auj:
        return
    try:
        c = _cx()
        try:
            et = {j: (e, json.loads(r or "[]"), jr) for j, jr, e, r in c.execute("SELECT joueur, jour, etat, raisons FROM moment")}
        finally:
            c.close()
        R, st = regles_en_place()
    except Exception:
        et, R, st = {}, dict(REGLES_V1), None
    _CACHE.update(jour=auj, etats=et, regles=R, stats=st)


def _norm(n):
    import unicodedata
    return "".join(ch for ch in unicodedata.normalize("NFD", str(n or "").lower()) if unicodedata.category(ch) != "Mn").strip()


def etat(joueur):
    """-> {etat, raisons, jour} ou None (joueur hors banque)."""
    _charger_cache()
    E = _CACHE["etats"]
    v = E.get(joueur)
    if v is None and joueur:
        nj = _norm(joueur)
        v = next((x for k, x in E.items() if _norm(k) == nj), None)
    if v is None:
        return None
    return {"etat": v[0], "raisons": v[1], "jour": v[2]}


def annoter(x):
    """Une annonce (deal) : x['moment'] = {etat, raisons, verdict} quand le joueur est dans la banque."""
    e = etat(x.get("joueur"))
    if not e or e["etat"] == "inconnu":
        return x
    v = verdict(e["etat"], x.get("rabais"), _CACHE["regles"], _CACHE["stats"])
    x["moment"] = {**e, "verdict": v}
    return x


def iterer_maintenant(aujourd=None):
    """L'iteration de la semaine : mesure, challenger, garde l'historique ; puis les etats du jour avec les regles gagnantes."""
    R0, _ = regles_en_place()
    out = iterer(ventes_par_joueur(_lignes_banque()), aujourd, R0)
    with _verrou:
        c = _cx()
        try:
            c.execute("INSERT INTO moment_regles (le, regles, stats, validation, change, ventes_test) VALUES (?,?,?,?,?,?)",
                      (date.today().isoformat(), json.dumps(out["regles"]), json.dumps(out["stats"]), json.dumps(out["validation"]),
                       1 if out["change"] else 0, out["ventes_test"]))
            c.commit()
        finally:
            c.close()
    calculer_jour(aujourd)
    return out


# -- le journal en direct : chaque Feu vert / Bon moment note, puis verifie 60 jours plus tard ---------------------------
def journal_noter(deals, aujourd=None):
    jour = (aujourd or date.today()).isoformat()
    lignes = []
    for x in deals or []:
        m = (x.get("moment") or {})
        v = m.get("verdict")
        if not v or not x.get("item_id") or not x.get("total"):
            continue
        lignes.append((str(x["item_id"]), jour, x.get("joueur"), str(x.get("titre") or "")[:200], float(x["total"]),
                       float(x.get("valeur") or 0) or None, x.get("rabais"), m.get("etat"), v.get("cle")))
    if not lignes:
        return 0
    with _verrou:
        c = _cx()
        try:
            c.executemany("INSERT OR IGNORE INTO moment_journal (cle, jour, joueur, titre, total, valeur, rabais, etat, verdict)"
                          " VALUES (?,?,?,?,?,?,?,?,?)", lignes)
            c.commit()
        finally:
            c.close()
    return len(lignes)


def journal_verifier(valeur_actuelle, aujourd=None, max_n=60):
    """Les signaux de 60 jours et plus : la valeur de la carte aujourd'hui (valeur_actuelle(titre) -> $ ou None)."""
    auj = aujourd or date.today()
    lim = date.fromordinal(auj.toordinal() - 60).isoformat()
    c = _cx()
    try:
        a_voir = c.execute("SELECT cle, titre FROM moment_journal WHERE verifie_le IS NULL AND jour <= ? LIMIT ?", (lim, max_n)).fetchall()
    finally:
        c.close()
    n = 0
    for cle, titre in a_voir:
        try:
            v = valeur_actuelle(titre)
        except Exception:
            v = None
        with _verrou:
            c = _cx()
            try:
                c.execute("UPDATE moment_journal SET plus_tard=?, verifie_le=? WHERE cle=?", (v, auj.isoformat(), cle))
                c.commit()
            finally:
                c.close()
        n += 1
    return n


def journal_bilan():
    c = _cx()
    try:
        L = c.execute("SELECT verdict, total, plus_tard FROM moment_journal").fetchall()
    finally:
        c.close()
    out = {"signales": len(L)}
    for cle in ("fort_bas", "fort", "bon"):
        l = [(t, p) for v, t, p in L if v == cle and p]
        out[cle] = {"signales": sum(1 for v, _, _ in L if v == cle), "verifies": len(l),
                    "vaut_plus": round(100 * sum(1 for t, p in l if p > t) / len(l)) if l else None,
                    "profit": round(100 * sum(1 for t, p in l if 0.87 * p > t) / len(l)) if l else None}
    return out


def bilan():
    """Pour la console admin : regles en place, derniere mesure, historique des iterations, journal en direct."""
    c = _cx()
    try:
        H = c.execute("SELECT le, regles, stats, validation, change, ventes_test FROM moment_regles ORDER BY id DESC LIMIT 12").fetchall()
        E = c.execute("SELECT etat, COUNT(*) FROM moment GROUP BY etat").fetchall()
        creux = c.execute("SELECT joueur, etat, raisons FROM moment WHERE etat IN ('creux_fort','creux') ORDER BY etat DESC, joueur LIMIT 30").fetchall()
    finally:
        c.close()
    R, st = regles_en_place()
    return {"ok": True, "regles": R, "stats": st, "etats": dict(E),
            "creux": [{"joueur": j, "etat": e, "raisons": json.loads(r or "[]")} for j, e, r in creux],
            "iterations": [{"le": le, "change": bool(ch), "ventes_test": n, "stats": json.loads(s or "null"),
                            "validation": json.loads(v or "null")} for le, rg, s, v, ch, n in H],
            "journal": journal_bilan()}
