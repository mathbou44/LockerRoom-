"""
LOCKERROOM - la base des ventes reelles (26 oct 2026).

Mathieu : « ca manque de contenu (tendances), va chercher l'info au besoin pour nous faire une base de donnees
avec SoldComps ou 130point et Scrapfly ».

  - chaque recherche SoldComps faite par l'app (valeur d'une carte, deals, produits...) est gardee ici, vente par
    vente (titre, prix, date, photo) : ca ne coute rien de plus ;
  - en plus, chaque heure, quelques recherches planifiees (LR_BASE_JOUR par jour, 60 par defaut) sur les cartes
    qui comptent : recrues et vedettes des produits du catalogue, Young Guns, Canvas, autos... chaque carte est
    remise a jour au plus une fois par 5 jours ;
  - les tendances se calculent sur cette base : la MEME carte (cartes_match), 14 derniers jours vs les 28 d'avant.
SoldComps donne deja les ventes eBay avec le vrai prix des offres acceptees (ce que 130point affiche) : pas besoin
de Scrapfly (budget protege). Les taches de fond passent apres les recherches des utilisateurs (vendues : 70 %).
"""
import json
import os
import re
import sqlite3
import statistics
import threading
import time
from datetime import datetime, timedelta

_verrou = threading.Lock()
_ETAT = {"le": 0.0, "en_cours": False}
REFAIRE_J = 5


def par_jour():
    try:
        return max(0, int(os.environ.get("LR_BASE_JOUR") or 60))
    except ValueError:
        return 60


_FAITES = set()


def _cx():
    import comptes
    ch = os.path.join(comptes.DONNEES, "base_ventes.sqlite")
    deja = ch in _FAITES and os.path.exists(ch)
    c = sqlite3.connect(ch, timeout=30)
    if deja:                    # 4 nov 2026 (vitesse) : les tables une fois par processus
        return c
    c.execute("CREATE TABLE IF NOT EXISTS ventes (q TEXT, cle TEXT, titre TEXT, prix REAL, le TEXT, photo TEXT, url TEXT, "
              "offre INTEGER, vu_le TEXT, PRIMARY KEY (q, cle))")
    c.execute("CREATE INDEX IF NOT EXISTS ventes_le ON ventes (le)")
    # plan : cible = la carte exacte (« 2025-26 ivan demidov young guns »), q = la recherche SoldComps (sans l'annee,
    # comme vendues.memes : les vendeurs l'ecrivent de cent facons) ; le tri par cartes_match remet l'annee
    c.execute("CREATE TABLE IF NOT EXISTS plan (cible TEXT PRIMARY KEY, q TEXT, joueur TEXT, carte TEXT, produit TEXT, produit_id TEXT, "
              "recrue INTEGER, poids REAL, fait_le TEXT, nb INTEGER)")
    c.execute("CREATE INDEX IF NOT EXISTS plan_q ON plan (q)")
    _FAITES.add(ch)                      # apres les tables (un echec les refait au prochain appel)
    return c


def noter(q, ventes):
    """Appele par vendues.rechercher apres chaque vraie recherche : on garde toutes ses ventes."""
    q = " ".join(str(q or "").lower().split())
    if not q or not ventes:
        return 0
    maint = datetime.now().isoformat(timespec="seconds")
    lignes = []
    for v in ventes:
        if not v.get("prix") or not v.get("le"):
            continue
        cle = str(v.get("url") or "") or f"{v.get('titre')}|{v.get('le')}|{v.get('prix')}"
        lignes.append((q, cle[:300], str(v.get("titre") or "")[:200], float(v["prix"]), str(v["le"])[:10], v.get("photo"), v.get("url"),
                       1 if v.get("offre") else 0, maint))
    try:
        with _verrou:
            c = _cx()
            try:
                c.executemany("INSERT OR REPLACE INTO ventes VALUES (?,?,?,?,?,?,?,?,?)", lignes)
                c.execute("UPDATE plan SET fait_le=?, nb=? WHERE q=?", (maint, len(lignes), q))
                c.commit()
            finally:
                c.close()
    except sqlite3.Error:
        return 0
    return len(lignes)


# -- le plan : les cartes qui comptent ----------------------------------------------------------------------
_COURT = [(r"\bparallel\b", ""), (r"\s+-\s+", " "), (r"\bset\b", "")]


def _nom_carte(sous):
    t = str(sous or "")
    for a, b in _COURT:
        t = re.sub(a, b, t, flags=re.I)
    return " ".join(t.split())


VEDETTES_SORTES = ("young guns", "auto", "patch", "numbered")


def construire_plan(max_par_produit=None):
    """Pour chaque produit recent du catalogue : ses recrues (sous-ensembles de recrues sans numerotation) et ses
    joueurs les plus demandes (leurs hits). Une ligne = une recherche « saison joueur carte ».
    11 nov 2026 (Mathieu : « on est deja au forfait SoldComps de 50 000 requetes ») : SlabIQ apprend mieux avec plus de
    ventes (mesure : +0,9 point de precision quand on double). Le plan grandit avec le budget du jour (LR_BASE_JOUR) :
    plus de cartes par produit, et les joueurs les plus suivis (Indice) dans toutes leurs sortes de cartes, toutes saisons."""
    import cartes_match
    import catalogue
    import valeurs
    if max_par_produit is None:
        max_par_produit = max(60, min(400, par_jour() * REFAIRE_J // 25))
    dem = (valeurs._charger() or {}).get("joueurs") or {}
    an_min = datetime.now().year - (1 if datetime.now().month >= 6 else 2)
    lignes = {}
    for p in catalogue.liste():
        if int(str(p.get("saison") or "0")[:4] or 0) < an_min:
            continue
        prod = catalogue.charger(p["id"])
        se = {s["nom"]: s for s in prod.get("sous_ensembles") or []}
        vus = []
        for c in prod.get("cartes") or []:
            s = se.get(c.get("sous_ensemble")) or {}
            j = str(c.get("joueur") or "")
            if not j or "/" in j or s.get("parallele_de") or s.get("tirage") == 1:
                continue
            g = s.get("groupe") or "base"
            if g == "base" or (g == "insert" and not c.get("recrue")):
                continue
            recrue = g == "recrue" or bool(c.get("recrue"))
            poids = float(dem.get(j) or 0.6) * (2.0 if recrue else 1.0) * (1.5 if g in ("auto", "auto_memo") else 1.0)
            vus.append((poids, j, s["nom"], recrue))
        vus.sort(key=lambda x: -x[0])
        for poids, j, sous, recrue in vus[:max_par_produit]:
            full = " ".join(f"{p.get('saison')} {j} {_nom_carte(sous)}".lower().split())
            q = " ".join((cartes_match.requete_ebay(cartes_match.cible(full)) or full).lower().split())[:120]
            if full not in lignes:
                lignes[full] = (full, q, j, sous, p["nom"], p["id"], int(recrue), round(poids, 3))
    # les joueurs les plus suivis (actifs et legendes), dans leurs sortes de cartes les plus vendues, toutes saisons
    n_ved = max(0, min(400, (par_jour() * REFAIRE_J - len(lignes)) // len(VEDETTES_SORTES)))
    if n_ved:
        try:
            import indice_joueurs
            ved = [x["nom"] for x in indice_joueurs.top(n_ved, actifs=True)] + [x["nom"] for x in indice_joueurs.top(max(10, n_ved // 6), "legende", actifs=False)]
        except Exception:
            ved = []
        for k, j in enumerate(dict.fromkeys(ved)):
            for so in VEDETTES_SORTES:
                full = f"{j} {so}".lower()
                if full not in lignes:
                    lignes[full] = (full, full[:120], j, so, "", "", 0, round(1.0 - k / (len(ved) + 1), 3))
    with _verrou:
        c = _cx()
        try:
            for x in lignes.values():
                c.execute("INSERT INTO plan (cible, q, joueur, carte, produit, produit_id, recrue, poids) VALUES (?,?,?,?,?,?,?,?) "
                          "ON CONFLICT(cible) DO UPDATE SET poids=excluded.poids, q=excluded.q", x)
            c.commit()
        finally:
            c.close()
    return len(lignes)


def enrichir(n=None, rechercher=None):
    """Quelques recherches du plan : jamais faites d'abord, puis les plus vieilles, les plus demandees d'abord."""
    import vendues
    rechercher = rechercher or vendues.rechercher
    n = max(1, int(n or max(1, round(par_jour() / 24))))
    limite = (datetime.now() - timedelta(days=REFAIRE_J)).isoformat()
    c = _cx()
    try:
        if not c.execute("SELECT COUNT(*) FROM plan").fetchone()[0]:
            c.close()
            construire_plan()
            c = _cx()
        l = c.execute("SELECT q, MAX(poids) FROM plan WHERE fait_le IS NULL OR fait_le < ? GROUP BY q "
                      "ORDER BY MIN(fait_le IS NOT NULL), MAX(poids) DESC LIMIT ?", (limite, n)).fetchall()
    finally:
        c.close()
    faites = 0
    for q, _p in l:
        r = rechercher(q, fond=True)
        if r.get("erreur") in ("plafond du jour", "inactif", "clé SoldComps refusée", "quota SoldComps atteint"):
            break
        if r.get("cache"):                              # deja en cache (pas d'appel) : on note quand meme
            noter(q, r.get("ventes") or [])
        faites += 1
    return {"ok": True, "faites": faites}


def _plan_trop_petit():
    """Le budget (LR_BASE_JOUR) a grandi : le plan doit couvrir au moins ~5 jours de recherches."""
    try:
        c = _cx()
        try:
            n = c.execute("SELECT COUNT(DISTINCT q) FROM plan").fetchone()[0]
        finally:
            c.close()
        return n < par_jour() * REFAIRE_J * 0.6
    except Exception:
        return False


def enrichir_si_besoin():
    """Chaque heure (boucle du serveur) ; le plan est refait chaque semaine."""
    if par_jour() <= 0 or time.time() - _ETAT["le"] < 3500 or _ETAT["en_cours"]:
        return False
    _ETAT.update(le=time.time(), en_cours=True)

    def tache():
        try:
            import vendues
            if not vendues.actif():
                return
            if (datetime.now().weekday() == 0 and datetime.now().hour < 2) or (time.time() - _ETAT.get("plan_le", 0) > 86400 and _plan_trop_petit()):
                _ETAT["plan_le"] = time.time()
                construire_plan()
            enrichir()
        except Exception as e:
            print("Base des ventes : " + repr(e), flush=True)
        finally:
            _ETAT["en_cours"] = False
    threading.Thread(target=tache, daemon=True, name="base_ventes").start()
    return True


# -- les tendances ------------------------------------------------------------------------------------------
def _med(l):
    import cartes_match
    return cartes_match.mediane_robuste(l)[0] if len(l) >= 4 else round(statistics.median(l), 2)


def tendances(jours=14):
    """Sur la base : pour chaque carte du plan, la meme carte seulement ; 14 derniers jours vs les 28 d'avant."""
    import cartes_match
    auj = datetime.now()
    d1, d2, d7 = ((auj - timedelta(days=x)).strftime("%Y-%m-%d") for x in (jours, jours * 3, 7))
    try:
        c = _cx()
        try:
            plan = c.execute("SELECT q, cible, joueur, carte, produit, produit_id, recrue FROM plan WHERE fait_le IS NOT NULL").fetchall()
            ventes = {}
            for q, titre, prix, le, photo, url in c.execute("SELECT q, titre, prix, le, photo, url FROM ventes WHERE le >= ?", (d2,)):
                ventes.setdefault(q, []).append({"titre": titre, "prix": prix, "le": le, "photo": photo, "url": url})
            nb_total = c.execute("SELECT COUNT(*) FROM ventes").fetchone()[0]
        finally:
            c.close()
    except sqlite3.Error:
        return None
    hausses, baisses, vendues_7, records, cartes = [], [], [], [], []
    for q, full, j, carte, produit, pid, recrue in plan:
        cib = cartes_match.cible(full)
        l = [v for v in ventes.get(q) or [] if not cartes_match.raisons_refus(cib, v["titre"])]
        if not l:
            continue
        l.sort(key=lambda v: v["le"], reverse=True)
        recent = [v["prix"] for v in l if v["le"] >= d1]
        avant = [v["prix"] for v in l if v["le"] < d1]
        sem = [v for v in l if v["le"] >= d7]
        base = {"joueur": j, "carte": carte, "produit": produit, "produit_id": pid, "recrue": bool(recrue), "n": len(l),
                "n_7j": len(sem), "mediane": _med([v["prix"] for v in l[:30]]), "derniere": l[0]["le"],
                "points": [[v["le"], v["prix"]] for v in l[:40]][::-1], "photo": next((v["photo"] for v in l if v.get("photo")), None)}
        # 2 nov 2026 : chaque carte et ses ventes (la tendance PAR JOUEUR, tendance_stats)
        cartes.append({"joueur": j, "carte": carte, "produit_id": pid, "recrue": bool(recrue), "points": [[v["le"], v["prix"]] for v in l[:120]]})
        if len(recent) >= 3 and len(avant) >= 3:
            a, b = _med(avant), _med(recent)
            if a:
                x = {**base, "pct": round(100 * (b - a) / a), "avant": a, "recent": b, "n_t": len(recent) + len(avant)}
                (hausses if x["pct"] >= 5 else baisses if x["pct"] <= -5 else []).append(x)
        if sem:
            vendues_7.append(base)
            top = max(sem, key=lambda v: v["prix"])
            records.append({**base, "prix": top["prix"], "le": top["le"], "titre": top["titre"], "url": top["url"],
                            "photo": top.get("photo") or base["photo"]})
    return {"hausses": sorted(hausses, key=lambda x: -x["pct"])[:8], "baisses": sorted(baisses, key=lambda x: x["pct"])[:8],
            "plus_vendues": sorted(vendues_7, key=lambda x: (-x["n_7j"], -x["n"]))[:8],
            "records": sorted(records, key=lambda x: -x["prix"])[:8],
            "nb_ventes": nb_total, "nb_cartes": len({x["joueur"] + x["carte"] for x in vendues_7 + hausses + baisses}), "cartes": cartes}


def statut():
    try:
        c = _cx()
        try:
            return {"ventes": c.execute("SELECT COUNT(*) FROM ventes").fetchone()[0], "plan": c.execute("SELECT COUNT(*) FROM plan").fetchone()[0],
                    "faites": c.execute("SELECT COUNT(*) FROM plan WHERE fait_le IS NOT NULL").fetchone()[0], "par_jour": par_jour()}
        finally:
            c.close()
    except sqlite3.Error:
        return {}


# -- 3 nov 2026 (Mathieu : « on doit avoir plus de joueurs ; des veterans et des legendes, pas juste des recrues ; une mega
# liste avec toutes nos donnees ») : TOUTES les recherches gardees (le plan, mais aussi chaque recherche des deals, des
# fiches, des encans suivis : veterans et legendes compris), chacune = une carte exacte (ses ventes filtrees par
# cartes_match). Pour tendance_stats : la tendance par joueur, avec son epoque (recrue, veteran, legende).
NOUVELLES_MAX = 15000            # 3 nov 2026 : ventes nouvelles triees par passe (le reste a la passe suivante)


def cartes_toutes(jours=42, n_min=4, max_q=12000):
    import cartes_match
    import time as _t
    auj = datetime.now()
    d0 = (auj - timedelta(days=jours)).strftime("%Y-%m-%d")
    # 3 nov 2026 (Mathieu : « 5 min de loading ») : le tri des ventes (cartes_match, ~100 000 titres) refait aux 15 min
    # bloquait le serveur et vidait la memoire de cartes_match (les deals devenaient lents aussi). Le verdict de chaque vente
    # est maintenant GARDE (table accepte) : chaque calcul ne trie que les ventes nouvelles, au plus NOUVELLES_MAX par passe.
    try:
        c = _cx()
        try:
            c.execute("CREATE TABLE IF NOT EXISTS accepte (q TEXT, cle TEXT, ok INTEGER, PRIMARY KEY (q, cle))")
            plan = {q: (cible, j, carte, pid, rec) for cible, q, j, carte, pid, rec in
                    c.execute("SELECT cible, q, joueur, carte, produit_id, recrue FROM plan")}
            par_q = {}
            for q, cle, titre, prix, le, ok in c.execute("SELECT v.q, v.cle, v.titre, v.prix, v.le, a.ok FROM ventes v LEFT JOIN accepte a "
                                                         "ON a.q = v.q AND a.cle = v.cle WHERE v.le >= ?", (d0,)):
                par_q.setdefault(q, []).append((titre, prix, le, cle, ok))
        finally:
            c.close()
    except sqlite3.Error:
        return []
    nouveaux, budget = [], [NOUVELLES_MAX]
    an_rec = None
    try:
        import deals
        an_rec = deals.saison_recrues()
    except Exception:
        an_rec = auj.year - 1
    out = []
    qs = sorted((q for q, l in par_q.items() if len(l) >= n_min), key=lambda q: -len(par_q[q]))[:max_q]
    for i, q in enumerate(qs):
        if i % 25 == 0:
            _t.sleep(0.02)                               # 3 nov 2026 : laisse vraiment passer les requetes de l'app (un seul serveur)
        try:
            p = plan.get(q)
            cib = cartes_match.cible(p[0] if p else q)
            l = []
            for t, pr, le, cle, ok in par_q[q]:
                if ok is None:
                    if budget[0] <= 0:
                        continue                         # triee a la prochaine passe
                    budget[0] -= 1
                    ok = 0 if cartes_match.raisons_refus(cib, t or "") else 1
                    nouveaux.append((q, cle, ok))
                if ok:
                    l.append((t, pr, le))
            if len(l) < n_min:
                continue
            if p:
                j, carte, pid, rec = p[1], p[2], p[3], bool(p[4])
            else:
                j = cartes_match.joueur_du_titre(q)
                if not j or len(j.split()) < 2:
                    continue
                j = " ".join(re.sub(r"^(Mc|O')([a-z])", lambda m: m.group(1) + m.group(2).upper(), w.capitalize()) for w in j.split())
                carte, pid = q, "q:" + q
                rec = False
            an = cib.get("annee")
            try:
                an = int(str(an)[:4]) if an else None
            except ValueError:
                an = None
            if not p:
                rec = bool(cib.get("rc") or re.search(r"young guns|rookie|\brc\b|future watch", q)) and (an is None or an >= an_rec)
            try:                                         # 4 nov 2026 : le sport, d'apres les titres vendus (equipes, ligues)
                import sports
                sp = sports.detecter(" ".join(str(t2 or "") for t2, _p, _l in l[:8]), q, defaut="hockey")
            except Exception:
                sp = None
            out.append({"joueur": j, "carte": carte, "produit_id": pid, "recrue": rec, "annee": an, "sport": sp,
                        "points": [[le, pr] for _t2, pr, le in l]})
        except Exception:
            continue
    if nouveaux:
        try:
            with _verrou:
                c = _cx()
                try:
                    c.executemany("INSERT OR REPLACE INTO accepte VALUES (?,?,?)", nouveaux)
                    c.commit()
                finally:
                    c.close()
        except sqlite3.Error:
            pass
    return out
