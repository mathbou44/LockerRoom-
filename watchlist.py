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
PROCHE_MIN = 120                # la boucle de 5 min relit sur eBay les encans qui finissent dans 2 h (31 oct 2026 : 75 -> 120)
RATIO = 0.70                    # la mise max : 70 % de la valeur (comme les deals), port compris


def _cx(api):
    c = api._db()
    c.executescript(SCHEMA)
    try:                                         # 29 oct 2026 : la mise max choisie par l'utilisateur pour une carte
        c.execute("ALTER TABLE watchlist ADD COLUMN mise_perso INTEGER DEFAULT 0")
    except Exception:
        pass
    try:                                         # 31 oct 2026 : quand la carte a ete envoyee dans la watchlist eBay
        c.execute("ALTER TABLE watchlist ADD COLUMN ebay_le TEXT")
    except Exception:
        pass
    return c


# 29 oct 2026 (Mathieu : « laisser l'utilisateur choisir les valeurs, mais laisser celles-ci par defaut pour les alarmes »)
DEFAUT = {"fin_min": FIN_MIN, "ratio_pct": int(RATIO * 100), "alerte_fin": True, "alerte_seuil": True, "ebay_auto": False}
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
    for k in ("alerte_fin", "alerte_seuil", "ebay_auto"):
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
    for k in ("alerte_fin", "alerte_seuil", "ebay_auto"):
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
    out = {"ok": True, "ids": ids(api)}
    if reglages(api).get("ebay_auto"):                   # l'utilisateur a choisi « aussi sur eBay a chaque etoile »
        try:
            r = vers_ebay(api, [iid])
            out["ebay"] = bool(r.get("ajoutees") or r.get("deja"))
            if r.get("erreurs"):
                out["ebay_erreur"] = r["erreurs"][0]["erreur"]
        except Exception as e:
            out["ebay"], out["ebay_erreur"] = False, str(e)[:160]
    return out


def retirer(api, item_id):
    iid = str(item_id or "")
    c = _cx(api)
    try:
        r = c.execute("SELECT ebay_le FROM watchlist WHERE item_id=?", (iid,)).fetchone()
        c.execute("DELETE FROM watchlist WHERE item_id=?", (iid,))
        c.commit()
    finally:
        c.close()
    out = {"ok": True, "ids": ids(api)}
    if r and r[0] and reglages(api).get("ebay_auto"):    # envoyee par nous : on la retire aussi d'eBay
        try:
            _appel_ebay("RemoveFromWatchList", [iid])
            out["ebay"] = True
        except Exception as e:
            out["ebay"], out["ebay_erreur"] = False, str(e)[:160]
    return out


# -- 31 oct 2026 (Mathieu : « que la watchlist sur mon app ait l'option de la televerser dans la watchlist eBay ») --------
# Trading API AddToWatchList / RemoveFromWatchList, avec le compte eBay connecte de l'utilisateur. Toujours sur un geste
# de l'utilisateur (le bouton, ou l'option « a chaque etoile » qu'il a activee). eBay : 400 cartes au plus par watchlist.
PAR_APPEL = 10
_DEJA = ("already", "déjà", "deja")
_FINIE = ("ended", "not active", "no longer", "terminé", "invalid item", "does not exist", "not found")


def _appel_ebay(appel, item_ids):
    import ebay_compte
    from xml.sax.saxutils import escape
    corps = (f'<?xml version="1.0" encoding="utf-8"?><{appel}Request xmlns="urn:ebay:apis:eBLBaseComponents">'
             + "".join(f"<ItemID>{escape(str(i))}</ItemID>" for i in item_ids) + f"</{appel}Request>")
    r = ebay_compte.trading(appel, corps)
    return {"n": ebay_compte._txt(r, "e:WatchListCount"), "max": ebay_compte._txt(r, "e:WatchListMaximum")}


def vers_ebay(api, ids_=None, appel=None):
    """Envoie les cartes de la watchlist (encore en vente) dans la watchlist eBay du compte connecte.
    {ok, ajoutees, deja, finies, erreurs:[{item_id, erreur}], total_ebay, max_ebay}"""
    import ebay_compte
    if not ebay_compte.statut().get("connecte"):
        return {"ok": False, "erreur": "Connecte ton compte eBay (Réglages) pour envoyer ta watchlist"}
    appel = appel or _appel_ebay
    c = _cx(api)
    try:
        lst = [dict(r) for r in c.execute("SELECT * FROM watchlist")]
    finally:
        c.close()
    maint = _maint()
    voulus = {str(i) for i in ids_} if ids_ else None
    a_envoyer = [x["item_id"] for x in lst if (voulus is None or str(x["item_id"]) in voulus) and _etat(x, maint) != "fini"]
    out = {"ok": True, "ajoutees": 0, "deja": 0, "finies": len([x for x in lst if (voulus is None or str(x["item_id"]) in voulus)]) - len(a_envoyer),
           "erreurs": [], "total_ebay": None, "max_ebay": None}
    reussies = []

    def noter(rep):
        if rep and rep.get("n"):
            out["total_ebay"], out["max_ebay"] = rep["n"], rep.get("max")

    for k in range(0, len(a_envoyer), PAR_APPEL):
        lot = a_envoyer[k:k + PAR_APPEL]
        try:
            noter(appel("AddToWatchList", lot))
            reussies += lot
            out["ajoutees"] += len(lot)
            continue
        except Exception as e:
            if len(lot) == 1:
                lot_err = {lot[0]: str(e)}
            else:
                lot_err = {}
                for iid in lot:                          # une carte refusee ne bloque pas les autres
                    try:
                        noter(appel("AddToWatchList", [iid]))
                        reussies.append(iid)
                        out["ajoutees"] += 1
                    except Exception as e1:
                        lot_err[iid] = str(e1)
        for iid, m in lot_err.items():
            b = m.lower()
            if any(t in b for t in _DEJA):
                out["deja"] += 1
                reussies.append(iid)
            elif any(t in b for t in _FINIE):
                out["finies"] += 1
            else:
                out["erreurs"].append({"item_id": iid, "erreur": m.replace("eBay a refusé : ", "")[:160]})
                if "limite quotidienne" in b or "400" in b and "watch" in b:
                    break
    if reussies:
        c = _cx(api)
        try:
            c.executemany("UPDATE watchlist SET ebay_le=? WHERE item_id=?", [(maint.isoformat(timespec="seconds"), i) for i in reussies])
            c.commit()
        finally:
            c.close()
    if out["erreurs"] and not reussies:
        out["ok"] = False
        out["erreur"] = out["erreurs"][0]["erreur"]
    return out


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
    # 31 oct 2026 (Mathieu : « trier par defaut ceux qui finissent en premier vers les derniers ») : par heure de fin
    # seulement (une mise depassee reste a sa place) ; les prix fixes ensuite, les encans termines a la fin
    lst.sort(key=lambda x: (1 if x["etat"] == "fini" else 0, x["reste_min"] if x["reste_min"] is not None else 10 ** 7))
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


# -- 31 oct 2026 (Mathieu : « comment accelerer mes mises sur plusieurs cartes ? j'utilise Gixen » ; « le garder pour moi
# (admin) ») : les encans suivis, prets a coller dans Gixen : numero eBay + mise max DANS LA DEVISE DE L'ANNONCE (une
# annonce americaine se mise en USD : 54 $ CA = 39 $ US). Rien n'est mise par SlabCoach : c'est l'admin qui colle.
# eBay : le pas minimum entre deux mises (meme grille en $ US et en $ CA)
PAS_MISE = ((1, 0.05), (5, 0.25), (25, 0.50), (100, 1.00), (250, 2.50), (500, 5.00), (1000, 10.00), (2500, 25.00), (5000, 50.00))


def mise_minimum(prix, mises):
    """La plus petite mise qu'eBay accepte : le prix de depart sans mise, sinon la mise du moment + le pas."""
    if prix is None:
        return None
    if not mises:
        return round(float(prix), 2)
    pas = next((p for lim, p in PAS_MISE if prix < lim), 100.0)
    return round(float(prix) + pas, 2)


def gixen(api, lire_article=None):
    return preparer(api, lire_article)


def preparer(api, lire_article=None):
    """31 oct 2026 : les encans suivis, prets a miser : mise max dans la devise de l'annonce, mise minimum d'eBay."""
    import ebay_compte
    lire_article = lire_article or (lambda i: ebay_compte.article(i, fond=False, frais=True))
    maint = _maint()
    out = []
    for x in liste(api)["cartes"]:
        if not x.get("encan") or x.get("etat") == "fini" or x.get("mise_max") is None:
            continue
        y = {"item_id": str(x["item_id"]), "titre": x.get("titre"), "url": x.get("url"), "photo": x.get("photo"),
             "reste_min": x.get("reste_min"), "fin": x.get("fin"), "mise_max_cad": x["mise_max"], "total_cad": x.get("total"),
             "etat": x.get("etat"), "devise": "CAD", "mise_max": x["mise_max"], "mise_actuelle": None, "taux": 1.0,
             "mise_min": None, "mises": None, "valeur_cad": x.get("valeur"), "mise_perso": bool(x.get("mise_perso"))}
        try:
            a = lire_article(y["item_id"])
            dev = a.get("devise") or "CAD"
            t = ebay_compte._taux_vers_cad(dev) or 0
            if t:
                y["devise"] = dev
                # arrondi vers le bas, au dollar (une mise de 39,73 $ US -> 39 $ US) : jamais au-dessus de la mise max
                y["mise_max"] = float(int(x["mise_max"] / t)) if dev != "CAD" else float(int(x["mise_max"]))
                y["mise_actuelle"] = a.get("prix_devise") or (a.get("prix_cad") / t if a.get("prix_cad") else None)
                y["taux"], y["mises"] = t, a.get("mises")
                y["mise_min"] = mise_minimum(y["mise_actuelle"], a.get("mises"))
            if a.get("fin"):
                y["fin"] = a["fin"]
                f = _dt(a["fin"])
                y["reste_min"] = int((f - maint).total_seconds() // 60) if f else y["reste_min"]
        except Exception as e:
            y["erreur"] = str(e)[:120]
        y["trop_bas"] = (y["mise_actuelle"] is not None and y["mise_actuelle"] >= y["mise_max"]) or \
            (y["mise_min"] is not None and y["mise_min"] > y["mise_max"])
        out.append(y)
    out.sort(key=lambda z: z["reste_min"] if z["reste_min"] is not None else 10 ** 7)
    return {"ok": True, "cartes": out, "texte": "\n".join(f"{z['item_id']} {z['mise_max']:.2f}" for z in out if not z["trop_bas"])}
