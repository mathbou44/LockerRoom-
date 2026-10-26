"""
LOCKERROOM - fiche joueur, alertes, « vaut-il la peine d'ouvrir ? », tendances, collection, calendrier (26 oct 2026).

Mathieu : « tous » (les 7 idees proposees) :
  1. fiche joueur : portrait, courbe de ses ventes, ses cartes dans chaque produit, tendance ;
  2. alertes : suivre un joueur / une carte, etre prevenu quand une annonce passe sous son prix cible ;
  3. vaut-il la peine d'ouvrir : valeur revendable d'une boite vs son prix de vente ;
  4. tendances de la semaine : les recrues qui montent et qui baissent (ventes reelles) ;
  5. collection : la valeur de l'inventaire chaque jour, gain ou perte ;
  6. petites courbes de prix (points de ventes datees, dans vendues.memes) ;
  7. calendrier des sorties (catalogue + produits reperes sur eBay).
Rien n'est achete ni vendu automatiquement : une alerte previent, l'utilisateur decide.
"""
import json
import os
import re
import statistics
from datetime import datetime, timedelta

SCHEMA = """
CREATE TABLE IF NOT EXISTS alertes (id INTEGER PRIMARY KEY, q TEXT, prix_max REAL, cree_le TEXT, actif INTEGER DEFAULT 1,
    vus TEXT DEFAULT '[]', verifie_le TEXT);
CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY, alerte_id INTEGER, item_id TEXT, titre TEXT, total REAL,
    photo TEXT, url TEXT, le TEXT, lu INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS valeur_historique (jour TEXT PRIMARY KEY, valeur REAL, cout REAL, nb INTEGER);
"""


def _cx(api):
    c = api._db()
    c.executescript(SCHEMA)
    return c


def _dicts(rows):
    return [dict(r) for r in rows]


# -- 1. fiche joueur -------------------------------------------------------------------------------------------
def fiche_joueur(api, nom):
    import cartes_match
    import catalogue
    import valeur_produit
    import valeurs
    import vendues
    nom = re.sub(r"\s+", " ", str(nom or "")).strip()
    if len(nom) < 3:
        return {"ok": False, "erreur": "Nom du joueur ?"}
    n = cartes_match.norm(nom)
    cartes, equipes, rookie = [], {}, None
    for p in catalogue.liste():
        try:
            prod = catalogue.charger(p["id"])
        except Exception:
            continue
        se = {s["nom"]: s for s in prod.get("sous_ensembles") or []}
        taux, cache = prod.get("_taux") or {}, {}
        for c in prod.get("cartes") or []:
            js = [cartes_match.norm(x) for x in str(c.get("joueur") or "").split("/")]
            if n not in js:
                continue
            s = se.get(c.get("sous_ensemble")) or {}
            if s.get("parallele_de"):
                continue
            v, mes = valeurs.valeur_carte(prod, c["sous_ensemble"], c["joueur"], se, taux, cache)
            g = s.get("groupe") or "base"
            cartes.append({"produit": prod["nom"], "produit_id": prod["id"], "carte": c["sous_ensemble"], "numero": c.get("numero"),
                           "groupe": g, "valeur": round(v, 2), "mesuree": mes, "tirage": c.get("tirage") or s.get("tirage"),
                           "par_boite": round(taux.get(c["sous_ensemble"]) or 0, 4)})
            if c.get("equipe"):
                equipes[c["equipe"]] = equipes.get(c["equipe"], 0) + 1
            if g == "recrue" and "young guns" in c["sous_ensemble"].lower() and not rookie:
                rookie = prod
    cartes = [x for x in cartes if x["valeur"] >= 1.0]       # une carte de base a 0,25 $ n'est pas « a chasser »
    cartes.sort(key=lambda x: -x["valeur"])
    q = f"{nom} young guns" if rookie else nom
    try:
        vs = vendues.memes(q, requete=True, n=24)
    except Exception:
        vs = {"ventes": [], "points": [], "nb": 0}
    tend = vs.get("tendance")
    if not tend and rookie:                              # sinon la tendance mesuree avec le produit
        e = ((valeur_produit.de(rookie["id"]).get("sous") or {}).get("Young Guns") or {}).get("joueurs", {}).get(nom) or {}
        tend = e.get("t")
    try:
        deals = [d for d in api._deals_fusion() if n.split()[-1] in cartes_match.norm(d.get("titre") or "").split()][:8]
    except Exception:
        deals = []
    c = _cx(api)
    try:
        al = _dicts(c.execute("SELECT * FROM alertes WHERE actif=1 AND LOWER(q) LIKE ?", (f"%{n.split()[-1]}%",)))
    finally:
        c.close()
    return {"ok": True, "joueur": nom, "connu": valeurs.connu(nom), "demande": valeurs.demande(nom),
            "equipe": max(equipes.items(), key=lambda kv: kv[1])[0] if equipes else None,
            "recrue": rookie["nom"] if rookie else None, "requete": q,
            "cartes": cartes[:16], "ventes": vs.get("ventes") or [], "points": vs.get("points") or [], "mediane": vs.get("mediane"),
            "nb_ventes": vs.get("nb") or 0, "tendance": tend, "deals": deals, "alertes": al}


# -- 2. alertes ------------------------------------------------------------------------------------------------
def alerte_ajouter(api, q, prix_max):
    q = re.sub(r"\s+", " ", str(q or "")).strip()[:100]
    try:
        p = float(prix_max)
    except (TypeError, ValueError):
        return {"ok": False, "erreur": "Prix cible ?"}
    if len(q) < 3 or p <= 0:
        return {"ok": False, "erreur": "Écris la carte et ton prix cible"}
    c = _cx(api)
    try:
        if c.execute("SELECT COUNT(*) FROM alertes WHERE actif=1").fetchone()[0] >= 30:
            return {"ok": False, "erreur": "30 alertes au plus : retires-en une"}
        aid = c.execute("INSERT INTO alertes (q, prix_max, cree_le) VALUES (?,?,?)", (q, round(p, 2), datetime.now().isoformat(timespec="seconds"))).lastrowid
        c.commit()
    finally:
        c.close()
    return {"ok": True, "id": aid}


def alertes_liste(api):
    c = _cx(api)
    try:
        al = _dicts(c.execute("SELECT id, q, prix_max, cree_le, verifie_le FROM alertes WHERE actif=1 ORDER BY id DESC"))
        no = _dicts(c.execute("SELECT * FROM notifications ORDER BY id DESC LIMIT 40"))
    finally:
        c.close()
    return {"ok": True, "alertes": al, "notifications": no, "non_lues": sum(1 for x in no if not x["lu"])}


def alerte_supprimer(api, aid):
    c = _cx(api)
    try:
        c.execute("UPDATE alertes SET actif=0 WHERE id=?", (int(aid),))
        c.commit()
    finally:
        c.close()
    return {"ok": True}


def notifications_lues(api):
    c = _cx(api)
    try:
        c.execute("UPDATE notifications SET lu=1 WHERE lu=0")
        c.commit()
    finally:
        c.close()
    return {"ok": True}


def verifier_alertes(api, rechercher=None):
    """Chaque heure (taches de fond) : les annonces de chaque alerte (prix fixe + encans qui finissent), la MEME carte
    seulement (cartes_match), sous le prix cible -> une notification (une seule fois par annonce)."""
    import cartes_match
    import ebay_compte
    rechercher = rechercher or ebay_compte.rechercher
    c = _cx(api)
    try:
        al = _dicts(c.execute("SELECT * FROM alertes WHERE actif=1"))
    finally:
        c.close()
    nouvelles = 0
    for a in al:
        try:
            res = rechercher(a["q"], categorie="261328", limite=50, fond=True, recentes=True) or []
        except (RuntimeError, OSError):
            break
        _c, memes, _e = cartes_match.filtrer(a["q"], res)
        vus = set(json.loads(a.get("vus") or "[]"))
        c = _cx(api)
        try:
            for x in memes:
                tot = round((x.get("prix_cad") or 0) + (x.get("port_cad") or 0), 2)
                if not tot or tot > a["prix_max"] or str(x.get("item_id")) in vus:
                    continue
                vus.add(str(x.get("item_id")))
                c.execute("INSERT INTO notifications (alerte_id, item_id, titre, total, photo, url, le) VALUES (?,?,?,?,?,?,?)",
                          (a["id"], str(x.get("item_id")), x.get("titre"), tot, x.get("photo"), x.get("url"), datetime.now().isoformat(timespec="seconds")))
                nouvelles += 1
            c.execute("UPDATE alertes SET vus=?, verifie_le=? WHERE id=?", (json.dumps(sorted(vus)[-300:]), datetime.now().isoformat(timespec="seconds"), a["id"]))
            c.commit()
        finally:
            c.close()
        nouv_a = [x for x in memes if str(x.get("item_id")) in vus and str(x.get("item_id")) not in set(json.loads(a.get("vus") or "[]"))]
        if nouv_a and hasattr(api, "_push"):          # 26 oct 2026 - l'iPhone sonne (app App Store, notifications acceptees)
            x = min(nouv_a, key=lambda y: (y.get("prix_cad") or 0) + (y.get("port_cad") or 0))
            tot = round((x.get("prix_cad") or 0) + (x.get("port_cad") or 0), 2)
            try:
                api._push(f"🔔 {a['q']} : {tot:.2f} $", (x.get("titre") or "")[:140] + (f" (+{len(nouv_a) - 1})" if len(nouv_a) > 1 else ""),
                          {"lien": "#alertes"})
            except Exception as e:
                print("Push : " + repr(e), flush=True)
    return {"ok": True, "alertes": len(al), "nouvelles": nouvelles}


# -- 3. vaut-il la peine d'ouvrir ? -----------------------------------------------------------------------------
def verdict_ouvrir(ev_boite, prix_boite):
    """Valeur revendable attendue d'une boite vs son prix de vente scellee."""
    if not ev_boite or not prix_boite:
        return None
    r = ev_boite / prix_boite
    return {"ratio": round(r, 2), "pct": round(100 * (r - 1)),
            "verdict": "ouvrir" if r >= 1.05 else "neutre" if r >= 0.85 else "garder"}


# -- 4. tendances ----------------------------------------------------------------------------------------------
def tendances():
    """26 oct 2026 (Mathieu : « plus d'infos dans les tendances de la semaine ») : hausses, baisses et cartes les plus
    vendues, toutes les cartes mesurees des produits du catalogue (pas seulement les recrues), avec la courbe des
    ventes, le nombre de ventes et le prix d'avant / maintenant."""
    import catalogue
    import valeur_produit
    tout, vendues = {}, []
    for p in catalogue.liste():
        e = valeur_produit.de(p["id"]).get("sous") or {}
        for sn, s in e.items():
            for j, x in (s.get("joueurs") or {}).items():
                pts = [pt for pt in (x.get("p") or []) if pt and pt[0]][:30]
                base = {"joueur": j, "produit": p["nom"], "produit_id": p["id"], "carte": sn, "n": x.get("n") or 0,
                        "mediane": x.get("m"), "points": pts[::-1], "derniere": pts[0][0] if pts else None,
                        "recrue": bool(re.search(r"young guns|rookie|future watch|\brc\b", sn, re.I))}
                vendues.append(base)
                t = x.get("t")
                if not t or t.get("pct") is None or (t.get("n") or 0) < 4:
                    continue
                k = (j, p["id"])
                if k not in tout or abs(t["pct"]) > abs(tout[k]["pct"]):
                    tout[k] = {**base, "pct": t["pct"], "recent": t["recent"], "avant": t["avant"], "n_t": t["n"]}
    # 26 oct 2026 : la base des ventes (recherches planifiees + toutes celles de l'app) passe en premier
    try:
        import base_ventes
        b = base_ventes.tendances() or {}
    except Exception:
        b = {}
    # 26 oct 2026 (Mathieu : « bcp trop vide ») : une carte trop jeune pour « 30 j vs 60 j » (produit sorti il y a 3
    # semaines) a quand meme une tendance : ses 3 premieres ventes vs ses 3 dernieres (au moins 7 jours d'ecart)
    for p in catalogue.liste():
        e = valeur_produit.de(p["id"]).get("sous") or {}
        for sn, s_ in e.items():
            for j, x in (s_.get("joueurs") or {}).items():
                k = (j, p["id"])
                if k in tout:
                    continue
                pts = sorted((str(d)[:10], float(v)) for d, v in (x.get("p") or []) if d and v)
                if len(pts) < 6 or (datetime.fromisoformat(pts[-1][0]) - datetime.fromisoformat(pts[0][0])).days < 7:
                    continue
                a0 = statistics.median(v for _d, v in pts[:3])
                a1 = statistics.median(v for _d, v in pts[-3:])
                pct = round(100 * (a1 - a0) / a0) if a0 else None
                if pct is None or abs(pct) < 5:
                    continue
                tout[k] = {"joueur": j, "produit": p["nom"], "produit_id": p["id"], "carte": sn, "n": x.get("n") or len(pts),
                           "mediane": x.get("m"), "points": [[d, v] for d, v in pts], "derniere": pts[-1][0],
                           "recrue": bool(re.search(r"young guns|rookie|future watch|\brc\b", sn, re.I)),
                           "pct": pct, "avant": round(a0, 2), "recent": round(a1, 2), "n_t": 6, "periode": "debut"}
    l = list(tout.values())
    fiables = l
    def fusion(a, b2, cle, n=8):
        vus, out = set(), []
        for x in list(a or []) + list(b2 or []):
            k = (x["joueur"], x.get("carte"))
            if k not in vus:
                vus.add(k)
                out.append(x)
        return sorted(out, key=cle)[:n]
    return {"ok": True, "hausses": fusion(b.get("hausses"), [x for x in fiables if x["pct"] > 0], lambda x: -x["pct"]),
            "baisses": fusion(b.get("baisses"), [x for x in fiables if x["pct"] < 0], lambda x: x["pct"]),
            "plus_vendues": b.get("plus_vendues") or sorted(vendues, key=lambda x: -x["n"])[:8],
            "records": b.get("records") or [],
            "nb_cartes": max(len(vendues), b.get("nb_cartes") or 0), "nb_ventes": max(sum(x["n"] for x in vendues), b.get("nb_ventes") or 0),
            "maj": max((valeur_produit.de(p["id"]).get("maj") or "" for p in catalogue.liste()), default=None)}


# -- 5. collection ---------------------------------------------------------------------------------------------
def noter_collection(api, valeur, cout, nb):
    c = _cx(api)
    try:
        c.execute("INSERT OR REPLACE INTO valeur_historique VALUES (?,?,?,?)", (datetime.now().strftime("%Y-%m-%d"), round(valeur or 0, 2),
                                                                                round(cout or 0, 2), int(nb or 0)))
        c.commit()
    finally:
        c.close()


def collection(api):
    c = _cx(api)
    try:
        h = _dicts(c.execute("SELECT * FROM valeur_historique ORDER BY jour DESC LIMIT 120"))
    finally:
        c.close()
    h.reverse()
    der = h[-1] if h else None
    d30 = next((x for x in h if x["jour"] >= (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")), None)
    return {"ok": True, "historique": h, "valeur": der["valeur"] if der else None, "cout": der["cout"] if der else None,
            "gain": round(der["valeur"] - der["cout"], 2) if der and der["cout"] else None,
            "var_30j": round(der["valeur"] - d30["valeur"], 2) if der and d30 else None}


# -- 7. calendrier -----------------------------------------------------------------------------------------------
def calendrier():
    import catalogue
    import nouveaux_produits
    mois = {}
    for p in catalogue.liste():
        m = str(p.get("sortie") or "")[:7] or "?"
        mois.setdefault(m, []).append({"nom": p["nom"], "id": p["id"], "statut": "catalogue"})
    for x in nouveaux_produits.liste():
        m = str(x.get("vu_le") or "")[:7] or "?"
        mois.setdefault(m, []).append({"nom": x["nom"], "statut": "repere" if x.get("nb_annonces") else "demande",
                                       "prix_boite": x.get("prix_boite"), "demandes": x.get("demandes")})
    return {"ok": True, "mois": [{"mois": k, "produits": v} for k, v in sorted(mois.items(), reverse=True)]}
