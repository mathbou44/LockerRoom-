"""
SLABCOACH - la variation du prix de chaque carte de l'inventaire (3 nov 2026).

Mathieu : « est-ce que les cartes d'inventaire ont un indice de variation de prix, genre +5 % depuis la semaine passee et
+10 % depuis le mois passe ? » -> une pastille sur chaque carte (30 jours) et le detail dans sa fiche (7, 30, 90 jours).

Sans aucun credit SoldComps : seulement ce que SlabCoach connait deja.
  1. les ventes deja lues de CETTE carte (base des ventes, gardee depuis le debut, et le cache des recherches) : mediane de la
     periode recente contre celle d'avant (3 ventes au moins de chaque cote, sinon rien : pas de hasard affiche) ;
  2. sinon, l'historique de SA valeur dans l'inventaire (une photo par jour quand elle change : suivi de valeur, mise a jour).
Une fois par jour par compte, dans la boucle horaire (alarmes_verifier).
"""
import json
import statistics
from datetime import datetime, timedelta

SCHEMA = """
CREATE TABLE IF NOT EXISTS carte_valeur_hist (carte_id INTEGER, jour TEXT, valeur REAL, PRIMARY KEY (carte_id, jour));
CREATE TABLE IF NOT EXISTS carte_tendance (carte_id INTEGER PRIMARY KEY, maj TEXT, t7 REAL, t30 REAL, t90 REAL, source TEXT,
  n INTEGER, detail TEXT);
"""
MIN_VENTES = 3
MAX_CARTES = 1500
# (cle, jours de la periode recente, debut et fin de la periode de reference, en jours avant aujourd'hui)
FENETRES = (("t7", 7, 7, 37), ("t30", 30, 30, 60), ("t90", 30, 90, 120))


def _cx(api):
    c = api._db()
    c.executescript(SCHEMA)
    return c


def _med(l):
    import cartes_match
    if len(l) >= 4:
        m = cartes_match.mediane_robuste(l)[0]
        if m:
            return m
    return statistics.median(l)


def ventes_connues(titre):
    """Les ventes deja lues de CETTE carte (aucun appel) : [{prix, le}]."""
    import base_ventes
    import cartes_match
    import vendues
    cib = cartes_match.cible_titre(titre or "")
    q = (cartes_match.requete_ebay(cib) or "").strip()
    if not q:
        return []
    l, vus = [], set()
    try:
        c = base_ventes._cx()
        try:
            l += [{"titre": t, "prix": p, "le": le, "url": u} for t, p, le, u in c.execute("SELECT titre, prix, le, url FROM ventes WHERE q=?", (" ".join(q.lower().split()),))]
        finally:
            c.close()
    except Exception:
        pass
    l += [v for v in (vendues.en_cache(q) or [])]
    out = []
    for v in l:
        k = v.get("url") or f"{v.get('titre')}|{v.get('le')}|{v.get('prix')}"
        if k in vus or not v.get("prix") or not v.get("le") or cartes_match.raisons_refus(cib, v.get("titre") or ""):
            continue
        vus.add(k)
        out.append({"prix": float(v["prix"]), "le": str(v["le"])[:10]})
    return out


def par_ventes(ventes, maint=None):
    """-> {t7, t30, t90: % ou None, n: {t7: (recent, avant)...}}"""
    maint = maint or datetime.now()
    j = lambda n: (maint - timedelta(days=n)).strftime("%Y-%m-%d")
    out, n = {}, {}
    for k, rec, a, b in FENETRES:
        recent = [v["prix"] for v in ventes if v["le"] > j(rec)]
        avant = [v["prix"] for v in ventes if j(b) < v["le"] <= j(a)]
        if len(recent) >= MIN_VENTES and len(avant) >= MIN_VENTES:
            m1, m0 = _med(recent), _med(avant)
            out[k] = round(100 * (m1 / m0 - 1), 1) if m0 else None
            n[k] = (len(recent), len(avant))
        else:
            out[k] = None
    return out, n


def par_historique(hist, valeur, maint=None):
    """hist : [(jour, valeur)] trie ; -> {t7, t30, t90}. La reference : la valeur gardee il y a au moins N jours."""
    maint = maint or datetime.now()
    out = {}
    for k, _rec, a, _b in FENETRES:
        lim = (maint - timedelta(days=a)).strftime("%Y-%m-%d")
        ref = [v for d, v in hist if d <= lim and v]
        out[k] = round(100 * (valeur / ref[-1] - 1), 1) if ref and valeur else None
    return out


def maj(api, maint=None, forcer=False):
    """Une fois par jour : la photo de la valeur de chaque carte, puis ses variations. -> nombre de cartes avec une variation."""
    maint = maint or datetime.now()
    auj = maint.strftime("%Y-%m-%d")
    c = _cx(api)
    try:
        der = c.execute("SELECT MAX(maj) FROM carte_tendance").fetchone()[0]
        if der and str(der)[:10] == auj and not forcer:
            return None
        cartes = [dict(r) for r in c.execute("SELECT id, titre, valeur FROM cartes WHERE statut != 'Vendue' ORDER BY id DESC LIMIT ?", (MAX_CARTES,))]
        hist = {}
        for cid, jour, v in c.execute("SELECT carte_id, jour, valeur FROM carte_valeur_hist ORDER BY jour"):
            hist.setdefault(cid, []).append((jour, v))
        # la photo du jour, seulement si la valeur a change depuis la derniere
        photos = [(x["id"], auj, x["valeur"]) for x in cartes if x.get("valeur") and (not hist.get(x["id"]) or hist[x["id"]][-1][1] != x["valeur"])]
        c.executemany("INSERT OR REPLACE INTO carte_valeur_hist VALUES (?,?,?)", photos)
        for cid, j, v in photos:
            hist.setdefault(cid, []).append((j, v))
        c.commit()
    finally:
        c.close()
    lignes, n_ok = [], 0
    for x in cartes:
        try:
            vs = ventes_connues(x.get("titre") or "")
        except Exception:
            vs = []
        t, n = par_ventes(vs, maint)
        src = "ventes"
        if all(v is None for v in t.values()) and x.get("valeur"):
            t, src, n = par_historique(hist.get(x["id"]) or [], x["valeur"], maint), "valeur", {}
        if any(v is not None for v in t.values()):
            n_ok += 1
        lignes.append((x["id"], maint.isoformat(timespec="seconds"), t["t7"], t["t30"], t["t90"], src, len(vs), json.dumps(n)))
    c = _cx(api)
    try:
        c.execute("DELETE FROM carte_tendance")
        c.executemany("INSERT INTO carte_tendance VALUES (?,?,?,?,?,?,?,?)", lignes)
        c.commit()
    finally:
        c.close()
    return n_ok


def lire(api):
    """-> {carte_id: {t7, t30, t90, source, n}} (seulement les cartes qui ont au moins une variation)."""
    c = _cx(api)
    try:
        out = {}
        for cid, t7, t30, t90, src, n in c.execute("SELECT carte_id, t7, t30, t90, source, n FROM carte_tendance"):
            if t7 is not None or t30 is not None or t90 is not None:
                out[cid] = {"t7": t7, "t30": t30, "t90": t90, "source": src, "n": n}
        return out
    finally:
        c.close()
