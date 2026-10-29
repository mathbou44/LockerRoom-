"""
SLABCOACH - la watchlist (29 oct 2026, Mathieu : « quand la personne defile les deals, elle peut mettre une etoile pour
l'enregistrer dans une watchlist, pour avoir une notification quand l'annonce a depasse le seuil de rentabilite ou est
vraiment proche de finir, il faut qu'il place son enchere. En attendant d'avoir acces aux mises par l'API eBay »).

Une etoile sur un deal -> la carte est suivie (par compte). Deux alertes, une seule fois chacune, meme la nuit (c'est
l'utilisateur qui les a demandees, une par carte) :
  fin    un encan finit dans 15 min et la mise est encore sous la mise max : « place ta mise »
  seuil  la mise (ou le prix) depasse la mise max : plus rentable
Rien n'est mise ni achete par SlabCoach : le bouton ouvre l'annonce sur eBay.
"""
from datetime import datetime, timedelta, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist (item_id TEXT PRIMARY KEY, titre TEXT, photo TEXT, url TEXT, valeur REAL, mise_max REAL,
  total REAL, port REAL, encan INTEGER, fin TEXT, ajoute_le TEXT, maj_le TEXT, statut TEXT DEFAULT 'ok',
  notif_fin INTEGER DEFAULT 0, notif_seuil INTEGER DEFAULT 0);
"""
MAX = 60                        # cartes suivies par compte
FIN_MIN = 15                    # « finit dans 15 min : place ta mise »
PROCHE_MIN = 75                 # la boucle de 5 min relit sur eBay les encans qui finissent dans 75 min
RATIO = 0.70                    # la mise max : 70 % de la valeur (comme les deals), port compris


def _cx(api):
    c = api._db()
    c.executescript(SCHEMA)
    try:                                         # 29 oct 2026 : la mise max choisie par l'utilisateur pour une carte
        c.execute("ALTER TABLE watchlist ADD COLUMN mise_perso INTEGER DEFAULT 0")
    except Exception:
        pass
    return c


# 29 oct 2026 (Mathieu : « laisser l'utilisateur choisir les valeurs, mais laisser celles-ci par defaut pour les alarmes »)
DEFAUT = {"fin_min": FIN_MIN, "ratio_pct": int(RATIO * 100), "alerte_fin": True, "alerte_seuil": True}
CHOIX_FIN = (5, 10, 15, 30, 60)


def reglages(api):
    r = (api.reglages_lire() or {}).get("watch")
    r = r if isinstance(r, dict) else {}
    out = dict(DEFAUT)
    if r.get("fin_min") in CHOIX_FIN:
        out["fin_min"] = int(r["fin_min"])
    try:
        out["ratio_pct"] = max(30, min(100, int(r.get("ratio_pct", out["ratio_pct"]))))
    except (TypeError, ValueError):
        pass
    for k in ("alerte_fin", "alerte_seuil"):
        if k in r:
            out[k] = bool(r[k])
    return out


def regler(api, d):
    """Les alarmes de la watchlist : minutes avant la fin, % de la valeur pour la mise max, chaque alerte on/off.
    Un nouveau % refait la mise max des cartes que l'utilisateur n'a pas reglees a la main (et leur alerte repart)."""
    d = d or {}
    cfg = reglages(api)
    if d.get("fin_min") is not None:
        try:
            if int(d["fin_min"]) in CHOIX_FIN:
                cfg["fin_min"] = int(d["fin_min"])
        except (TypeError, ValueError):
            pass
    ancien = cfg["ratio_pct"]
    if d.get("ratio_pct") is not None:
        try:
            cfg["ratio_pct"] = max(30, min(100, int(d["ratio_pct"])))
        except (TypeError, ValueError):
            pass
    for k in ("alerte_fin", "alerte_seuil"):
        if k in d:
            cfg[k] = bool(d[k])
    api.reglages_sauver({"watch": cfg})
    if cfg["ratio_pct"] != ancien:
        c = _cx(api)
        try:
            c.execute("UPDATE watchlist SET mise_max=ROUND(valeur*?-COALESCE(port,0),2), notif_seuil=0 "
                      "WHERE COALESCE(mise_perso,0)=0 AND valeur IS NOT NULL", (cfg["ratio_pct"] / 100,))
            c.commit()
        finally:
            c.close()
    return {"ok": True, **cfg}


def mise_max(api, item_id, valeur):
    """La mise max d'UNE carte, choisie par l'utilisateur (vide = revient au % par defaut)."""
    v = _f(valeur)
    cfg = reglages(api)
    c = _cx(api)
    try:
        if v and v > 0:
            c.execute("UPDATE watchlist SET mise_max=?, mise_perso=1, notif_seuil=0 WHERE item_id=?", (v, str(item_id)))
        else:
            c.execute("UPDATE watchlist SET mise_max=ROUND(valeur*?-COALESCE(port,0),2), mise_perso=0, notif_seuil=0 "
                      "WHERE item_id=? AND valeur IS NOT NULL", (cfg["ratio_pct"] / 100, str(item_id)))
        c.commit()
    finally:
        c.close()
    return liste(api)


def _f(v):
    try:
        return round(float(v), 2) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _maint():
    return datetime.now(timezone.utc)


def _dt(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


def ajouter(api, x):
    x = x or {}
    iid = str(x.get("item_id") or "").strip()
    if not iid or len(iid) > 20:
        return {"ok": False, "erreur": "Annonce inconnue"}
    valeur, port = _f(x.get("valeur")), _f(x.get("port"))
    mm = _f(x.get("mise_max"))
    if mm is None and valeur:
        mm = round(valeur * reglages(api)["ratio_pct"] / 100 - (port or 0), 2)
    c = _cx(api)
    try:
        if c.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0] >= MAX and not c.execute(
                "SELECT 1 FROM watchlist WHERE item_id=?", (iid,)).fetchone():
            return {"ok": False, "erreur": f"{MAX} cartes au plus dans ta watchlist"}
        maint = _maint().isoformat(timespec="seconds")
        c.execute("INSERT OR REPLACE INTO watchlist (item_id, titre, photo, url, valeur, mise_max, total, port, encan, fin, ajoute_le, "
                  "maj_le, statut, notif_fin, notif_seuil) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'ok',0,0)",
                  (iid, str(x.get("titre") or "")[:200], str(x.get("photo") or "")[:600], str(x.get("url") or "")[:600], valeur, mm,
                   _f(x.get("total")), port, 1 if x.get("encan") else 0, x.get("fin"), maint, maint))
        c.commit()
    finally:
        c.close()
    return {"ok": True, "ids": ids(api)}


def retirer(api, item_id):
    c = _cx(api)
    try:
        c.execute("DELETE FROM watchlist WHERE item_id=?", (str(item_id or ""),))
        c.commit()
    finally:
        c.close()
    return {"ok": True, "ids": ids(api)}


def ids(api):
    c = _cx(api)
    try:
        return [r[0] for r in c.execute("SELECT item_id FROM watchlist")]
    finally:
        c.close()


def _etat(x, maint=None):
    """ok (encore rentable) | depasse (au-dessus de la mise max) | fini."""
    maint = maint or _maint()
    f = _dt(x.get("fin"))
    if x.get("statut") == "fini" or (x.get("encan") and f and f < maint):
        return "fini"
    if x.get("mise_max") is not None and x.get("total") is not None and x["total"] - (x.get("port") or 0) > x["mise_max"]:
        return "depasse"
    return "ok"


def _du_chasseur(lst):
    """Le prix du moment, gratuit : le chasseur revoit ses deals sur eBay a chaque tour."""
    try:
        import deals as _d
        dd = _d.lire_vite()
        par = {str(x.get("item_id")): x for x in (dd.get("deals") or []) + (dd.get("pres") or [])}
    except Exception:
        return
    for x in lst:
        y = par.get(str(x["item_id"]))
        if y and str(y.get("vu_le") or "") > str(x.get("maj_le") or ""):
            x.update(total=y.get("total", x.get("total")), fin=y.get("fin") or x.get("fin"), maj_le=y.get("vu_le"))
            if y.get("port") is not None:
                x["port"] = y["port"]


def liste(api):
    c = _cx(api)
    try:
        lst = [dict(r) for r in c.execute("SELECT * FROM watchlist")]
    finally:
        c.close()
    _du_chasseur(lst)
    maint = _maint()
    for x in lst:
        x["encan"] = bool(x.get("encan"))
        x["etat"] = _etat(x, maint)
        f = _dt(x.get("fin"))
        x["reste_min"] = int((f - maint).total_seconds() // 60) if f and x["encan"] else None
    rang = {"ok": 0, "depasse": 1, "fini": 2}
    lst.sort(key=lambda x: (rang[x["etat"]], x["reste_min"] if x["reste_min"] is not None else 10 ** 7))
    return {"ok": True, "cartes": lst, "n": len(lst), "reglages": reglages(api)}


def verifier(api, proches=False, lire_article=None, maint=None):
    """Toutes les 5 min (proches=True) : les encans qui finissent dans 75 min, relus sur eBay. Chaque heure : le reste
    (prix du chasseur d'abord ; eBay pour les cartes qu'il ne revoit pas, 20 au plus). -> nombre d'alertes envoyees."""
    import alarmes
    maint = maint or _maint()
    cfg = reglages(api)
    fin_min = cfg["fin_min"]
    proche_min = max(PROCHE_MIN, fin_min + 15)
    if lire_article is None:
        import ebay_compte
        lire_article = lambda i: ebay_compte.article(i, fond=True, frais=proches)     # noqa: E731
    c = _cx(api)
    try:
        lst = [dict(r) for r in c.execute("SELECT * FROM watchlist WHERE statut != 'fini'")]
    finally:
        c.close()
    if not lst:
        return 0
    _du_chasseur(lst)
    etat_a = alarmes._lire()
    n_ebay, envoyees = 0, 0
    for x in lst:
        f = _dt(x.get("fin"))
        reste = (f - maint) if f else None
        proche = bool(x.get("encan") and reste is not None and timedelta(0) < reste <= timedelta(minutes=proche_min))
        vieux = str(x.get("maj_le") or "") < (maint - timedelta(minutes=70)).isoformat()
        if proche if proches else (proche or (vieux and n_ebay < 20)):
            try:
                a = lire_article(x["item_id"])
                n_ebay += 1
                if a and a.get("prix_cad"):
                    x.update(total=round(a["prix_cad"] + (a.get("port_cad") or 0), 2), port=a.get("port_cad"),
                             fin=a.get("fin") or x.get("fin"), maj_le=maint.isoformat(timespec="seconds"))
                    f = _dt(x.get("fin"))
                    reste = (f - maint) if f else None
            except RuntimeError as e:
                if "404" in str(e) or "11001" in str(e):
                    x["statut"] = "fini"                 # vendue, retiree ou finie
            except OSError:
                pass
        if x.get("encan") and f and f < maint:
            x["statut"] = "fini"
        e = _etat(x, maint)
        titre = alarmes.cartes_match_titre(x)
        mm = x.get("mise_max")
        if e == "depasse" and not x.get("notif_seuil") and cfg["alerte_seuil"]:
            if alarmes._notifier(api, etat_a, "watch-seuil:" + x["item_id"], f"📈 {titre}",
                                 f"{'La mise' if x.get('encan') else 'Le prix'} ({(x.get('total') or 0):.0f} $) dépasse ta mise max ({(mm or 0):.0f} $) : plus rentable.",
                                 "#deals/watch", x.get("total"), x.get("photo"), force=True):
                envoyees += 1
            x["notif_seuil"] = 1
        if e == "ok" and x.get("encan") and reste is not None and timedelta(0) < reste <= timedelta(minutes=fin_min) and not x.get("notif_fin") \
                and cfg["alerte_fin"]:
            mn = max(1, int(reste.total_seconds() // 60))
            if alarmes._notifier(api, etat_a, "watch-fin:" + x["item_id"], f"⏱ {mn} min : place ta mise",
                                 f"{titre} · mise {(x.get('total') or 0):.0f} $ · ta mise max {(mm or 0):.0f} $",
                                 "#deals/watch", x.get("total"), x.get("photo"), force=True):
                envoyees += 1
            x["notif_fin"] = 1
    c = _cx(api)
    try:
        for x in lst:
            c.execute("UPDATE watchlist SET total=?, port=?, fin=?, maj_le=?, statut=?, notif_fin=?, notif_seuil=? WHERE item_id=?",
                      (x.get("total"), x.get("port"), x.get("fin"), x.get("maj_le"), x.get("statut") or "ok", x.get("notif_fin") or 0,
                       x.get("notif_seuil") or 0, x["item_id"]))
        c.commit()
    finally:
        c.close()
    alarmes._ecrire(etat_a)
    return envoyees
