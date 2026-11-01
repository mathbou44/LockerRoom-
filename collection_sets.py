"""
SLABCOACH - la collection par sets, la valeur de la collection dans le temps, l'export (1er nov 2026).

Mathieu : « CollX et Collectr, on doit etre mieux » -> les trois choses que les collectionneurs comparent en premier :
  1. la collection par SETS : chaque carte reliee a son produit et a son sous-ensemble du catalogue (memes checklists que
     les breaks) ; le % complete et les cartes qui manquent, a partager ou imprimer ;
  2. la valeur de la collection dans le temps (un point par jour) et les plus fortes hausses et baisses ;
  3. l'export de la collection en CSV.
Rien n'est invente : une carte qu'on ne relie pas surement a une ligne de checklist reste « hors checklist ».
"""
import csv
import io
import json
import re
import time
from datetime import datetime, timedelta

_SQL = "CREATE TABLE IF NOT EXISTS valeur_collection (jour TEXT PRIMARY KEY, valeur REAL, cout REAL, nb INTEGER)"
_NOTE = {}


def _n(t):
    import checklist_import
    return checklist_import._n(t)


def _num(v):
    v = re.sub(r"^#", "", str(v or "").strip().upper())
    v = re.sub(r"^0+(?=\d)", "", v)
    return v


def _cartes_collection(api):
    import lockerroom
    c = api._db()
    try:
        return lockerroom._dicts(c.execute("SELECT * FROM cartes WHERE emplacement='Collection' AND statut != 'Vendue'"))
    finally:
        c.close()


# -- 1. par sets -------------------------------------------------------------------------------------------------------------
def _produit_de(carte, liste, memo):
    import checklist_import
    cle = (carte.get("annee") or "", carte.get("marque") or "", carte.get("set_nom") or "")
    if cle in memo:
        return memo[cle]
    p = None
    if carte.get("set_nom") and carte.get("annee"):
        p = checklist_import.produit_semblable(" ".join(x for x in cle if x), liste)
    if not p and carte.get("titre"):
        # le titre : « 2025-26 Upper Deck Series 1 Young Guns Ivan Demidov #451 » -> le produit dont le nom y est en entier
        t = _n(carte["titre"])
        for x in sorted(liste, key=lambda x: -len(str(x.get("nom") or ""))):
            an, mots = checklist_import._mots_produit(x.get("nom"))
            if an and an in t and mots and all(re.search(rf"\b{re.escape(m)}\b", t) for m in mots):
                p = x
                break
    memo[cle] = p
    return p


def _sous_de(carte, prod):
    """La ligne de checklist de la carte : meme numero ; le sous-ensemble dont le nom ressemble le plus a son parallele."""
    num = _num(carte.get("numero"))
    if not num:
        return None
    idx = prod.get("_par_num")
    if idx is None:                                   # index numero -> cartes (garde avec le produit en memoire)
        idx = {}
        for c in prod.get("cartes") or []:
            idx.setdefault(_num(c.get("numero")), []).append(c)
        prod["_par_num"] = idx
    cands = idx.get(num) or []
    if not cands:
        return None
    se = {s["nom"]: s for s in prod.get("sous_ensembles") or []}
    par = set(_n(carte.get("parallele") or "").split()) - {"base", "set", "rc", "rookie"}
    j = set(_n(carte.get("joueur") or "").split())

    def score(c):
        s = se.get(c.get("sous_ensemble")) or {}
        nom = set(_n(c.get("sous_ensemble") or "").split())
        sc = 3 * len(par & nom) - len(nom - par - {"set", "base", "parallel"})
        if not par and not s.get("parallele_de"):
            sc += 2
        if par and not (par & nom):
            sc -= 3
        if j and j & set(_n(c.get("joueur") or "").split()):
            sc += 4
        return sc
    best = max(cands, key=score)
    if j and not (j & set(_n(best.get("joueur") or "").split())):
        return None                                   # le numero existe, mais pas pour ce joueur : pas sur
    return best


def sets(api):
    import catalogue
    liste = catalogue.liste()
    memo, prods, hors = {}, {}, 0
    for c in _cartes_collection(api):
        p = _produit_de(c, liste, memo)
        prod = catalogue.charger(p["id"]) if p else None
        ligne = _sous_de(c, prod) if prod else None
        if not ligne:
            hors += 1
            continue
        d = prods.setdefault(prod["id"], {"id": prod["id"], "nom": prod["nom"], "saison": prod.get("saison"), "n": 0, "valeur": 0.0, "sous": {}})
        d["n"] += 1
        d["valeur"] += float(c.get("valeur") or 0)
        s = d["sous"].setdefault(ligne["sous_ensemble"], set())
        s.add(_num(ligne.get("numero")))
    out = []
    for pid, d in prods.items():
        prod = catalogue.charger(pid)
        par_se = {}
        for c in prod.get("cartes") or []:
            par_se.setdefault(c.get("sous_ensemble"), []).append(c)
        sous = []
        for nom, eus in d["sous"].items():
            toutes = par_se.get(nom) or []
            tot = len({_num(c.get("numero")) for c in toutes}) or 1
            sous.append({"nom": nom, "possedees": len(eus), "total": tot, "pct": round(100 * len(eus) / tot)})
        sous.sort(key=lambda s: (-s["pct"], -s["possedees"]))
        out.append({"id": pid, "nom": d["nom"], "saison": d["saison"], "n": d["n"], "valeur": round(d["valeur"], 2), "sous": sous})
    out.sort(key=lambda x: (-x["n"], x["nom"]))
    return {"ok": True, "produits": out, "hors_checklist": hors}


def checklist(api, pid, sous_nom):
    """Toutes les cartes d'un sous-ensemble, celles qu'on a cochees (et sa valeur)."""
    import catalogue
    prod = catalogue.charger(pid)
    if not prod:
        return {"ok": False, "erreur": "Produit introuvable"}
    eus = {}
    liste, memo = catalogue.liste(), {}
    for c in _cartes_collection(api):
        p = _produit_de(c, liste, memo)
        if not p or p["id"] != pid:
            continue
        ligne = _sous_de(c, prod)
        if ligne and ligne.get("sous_ensemble") == sous_nom:
            eus.setdefault(_num(ligne.get("numero")), []).append(c["id"])
    vus, l = set(), []
    for c in prod.get("cartes") or []:
        if c.get("sous_ensemble") != sous_nom or _num(c.get("numero")) in vus:
            continue
        vus.add(_num(c.get("numero")))
        l.append({"numero": c.get("numero"), "joueur": c.get("joueur"), "equipe": c.get("equipe"), "a": _num(c.get("numero")) in eus,
                  "ids": eus.get(_num(c.get("numero")), [])})
    tirage = next((s.get("tirage") for s in prod.get("sous_ensembles") or [] if s["nom"] == sous_nom), None)
    return {"ok": True, "produit": prod["nom"], "sous": sous_nom, "tirage": tirage, "cartes": l,
            "possedees": sum(1 for x in l if x["a"]), "total": len(l)}


# -- 2. la valeur dans le temps ------------------------------------------------------------------------------------------------
def noter(api):
    """Un point par jour (au plus une ecriture aux 30 min si rien ne change)."""
    l = _cartes_collection(api)
    v = (round(sum(float(x.get("valeur") or 0) for x in l), 2), round(sum(float(x.get("cout") or 0) for x in l), 2), len(l),
         datetime.now().strftime("%Y-%m-%d"))
    cle = getattr(api, "chemin_db", None) or "x"
    avant = _NOTE.get(cle)
    if avant and avant[1] == v and time.time() - avant[0] < 1800:
        return
    _NOTE[cle] = (time.time(), v)
    c = api._db()
    try:
        c.execute(_SQL)
        c.execute("INSERT OR REPLACE INTO valeur_collection VALUES (?,?,?,?)", (v[3], v[0], v[1], v[2]))
        c.commit()
    finally:
        c.close()


def valeur(api):
    import lockerroom
    noter(api)
    c = api._db()
    try:
        c.execute(_SQL)
        h = lockerroom._dicts(c.execute("SELECT * FROM valeur_collection ORDER BY jour DESC LIMIT 400"))
        try:
            suivis = {r["carte_id"]: dict(r) for r in c.execute("SELECT carte_id, reference, derniere FROM suivi_valeur WHERE actif=1 AND reference > 0 AND derniere > 0")}
        except Exception:
            suivis = {}
    finally:
        c.close()
    h.reverse()
    der = h[-1] if h else None

    def depuis(j):
        lim = (datetime.now() - timedelta(days=j)).strftime("%Y-%m-%d")
        ref = next((x for x in h if x["jour"] >= lim), None)
        return round(der["valeur"] - ref["valeur"], 2) if der and ref and ref["jour"] < der["jour"] else None
    # hausses et baisses : depuis l'achat (valeur - prix paye), et la variation suivie chaque semaine quand l'alerte est active
    mouv = []
    for x in _cartes_collection(api):
        v, k = x.get("valeur"), x.get("cout")
        if v is None or not k:
            continue
        s = suivis.get(x["id"])
        mouv.append({"id": x["id"], "joueur": x.get("joueur") or x.get("titre"), "photo": x.get("photo"), "valeur": v, "cout": k,
                     "gain": round(v - k, 2), "pct": round(100 * (v / k - 1)) if k else None,
                     "semaine": round(100 * (s["derniere"] / s["reference"] - 1)) if s else None})
    # le gain total : seulement sur les cartes dont on connait le prix paye ET la valeur (sinon il serait gonfle)
    gain_connu = round(sum(m["gain"] for m in mouv), 2) if mouv else None
    hausses = sorted((m for m in mouv if m["gain"] > 0), key=lambda m: -m["gain"])[:5]
    baisses = sorted((m for m in mouv if m["gain"] < 0), key=lambda m: m["gain"])[:5]
    return {"ok": True, "historique": [{"jour": x["jour"], "valeur": x["valeur"]} for x in h], "valeur": der["valeur"] if der else 0,
            "cout": der["cout"] if der else 0, "nb": der["nb"] if der else 0, "var_30j": depuis(30), "var_90j": depuis(90),
            "hausses": hausses, "baisses": baisses, "gain_connu": gain_connu, "n_prix_connu": len(mouv)}


# -- 3. export CSV -----------------------------------------------------------------------------------------------------------
def csv_texte(api):
    f = io.StringIO()
    w = csv.writer(f)
    w.writerow(["Player", "Year", "Brand", "Set", "Card #", "Parallel", "Serial", "Grade", "Cert", "Paid (CAD)", "Value (CAD)", "Gain (CAD)",
                "Added", "Status"])
    for x in sorted(_cartes_collection(api), key=lambda x: (str(x.get("annee") or ""), str(x.get("set_nom") or ""), str(x.get("numero") or ""))):
        try:
            e = json.loads(x.get("envoi_json") or "null") or {}
        except ValueError:
            e = {}
        statut = ("At grading (" + str(e.get("compagnie") or "") + ")") if e.get("type") == "gradation" else \
                 ("Consigned (" + str(e.get("chez") or "") + ")") if e.get("type") == "encan" else "In collection"
        v, k = x.get("valeur"), x.get("cout")
        w.writerow([x.get("joueur") or x.get("titre") or "", x.get("annee") or "", x.get("marque") or "", x.get("set_nom") or "", x.get("numero") or "",
                    x.get("parallele") or "", ("/" + str(x["tirage"])) if x.get("tirage") else "", x.get("grade") or "", x.get("cert") or "",
                    k if k is not None else "", v if v is not None else "", round(v - k, 2) if v is not None and k else "",
                    str(x.get("cree_le") or "")[:10], statut])
    return {"ok": True, "csv": f.getvalue(), "nom": "slabcoach-collection-" + datetime.now().strftime("%Y-%m-%d") + ".csv"}
