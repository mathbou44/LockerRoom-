"""
SLABCOACH - les alertes que l'utilisateur coche (29 oct 2026, Mathieu : « l'utilisateur doit pouvoir regler ses alarmes de
maniere simple et efficace » ; choix : le paquet de 6 ; « il peut les cocher pour choisir lesquels il veut »).

Un seul ecran « Mes alertes » : une case par alerte, un seul reglage au besoin. Verifiees chaque heure (boucle du serveur),
pour chaque compte. Chaque alerte part UNE seule fois (cle unique). Au plus 3 notifications sur l'iPhone par jour et rien la
nuit (22 h a 8 h, heure de Montreal) : au-dela, elles attendent dans la cloche de l'app.

  prix_cible  une carte que tu suis passe sous ton prix (les alertes de prix existantes)
  gros_deal   un deal a -X % ou plus (40 % par defaut) sur un joueur de tes cartes, ou qui rentre dans ton budget
  encan_fin   un encan d'un deal sur tes joueurs ou tes alertes finit dans l'heure, la mise est encore un deal
  en_feu      un joueur de tes cartes connait une grosse sequence (LNH, 5 derniers matchs)
  acheteurs   des acheteurs surveillent tes annonces eBay : tu peux leur envoyer une offre
  vendu       une de tes cartes vient de se vendre
"""
import json
import os
import time
from datetime import datetime, timedelta

TYPES = ["prix_cible", "gros_deal", "encan_fin", "en_feu", "acheteurs", "vendu"]
DEFAUT = {"prix_cible": True, "gros_deal": True, "encan_fin": True, "en_feu": True, "acheteurs": True, "vendu": True, "seuil_deal": 40}
MAX_JOUR = 3
NUIT = (22, 8)


def _chemin():
    import comptes
    return os.path.join(comptes.dossier() or comptes.DONNEES, "alarmes_etat.json")


def _lire():
    try:
        with open(_chemin(), encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def _ecrire(d):
    p = _chemin()
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(d, f)
    os.replace(p + ".tmp", p)


def reglages(api):
    r = api.reglages_lire().get("alarmes") or {}
    out = dict(DEFAUT)
    out.update({k: bool(v) for k, v in r.items() if k in TYPES})
    try:
        out["seuil_deal"] = max(20, min(80, int(r.get("seuil_deal") or DEFAUT["seuil_deal"])))
    except (TypeError, ValueError):
        pass
    return out


def regler(api, d):
    cur = reglages(api)
    for k, v in (d or {}).items():
        if k in TYPES:
            cur[k] = bool(v)
        elif k == "seuil_deal":
            try:
                cur[k] = max(20, min(80, int(v)))
            except (TypeError, ValueError):
                pass
    api.reglages_sauver({"alarmes": cur})
    return cur


def _heure_locale(maint=None):
    try:
        from zoneinfo import ZoneInfo
        return (maint or datetime.now(ZoneInfo("America/Toronto"))).hour
    except Exception:
        return (maint or datetime.now()).hour


def _notifier(api, etat, cle, titre, texte, lien, total=None, photo=None, maint=None):
    """Une alerte, une seule fois : dans la cloche toujours ; sur l'iPhone si le quota du jour et l'heure le permettent."""
    vus = etat.setdefault("vus", {})
    if cle in vus:
        return False
    vus[cle] = time.time()
    if len(vus) > 600:                                   # on garde les 600 plus recentes
        for k in sorted(vus, key=vus.get)[:len(vus) - 600]:
            del vus[k]
    import marche
    c = marche._cx(api)
    try:
        c.execute("INSERT INTO notifications (alerte_id, item_id, titre, total, photo, url, le) VALUES (?,?,?,?,?,?,?)",
                  (None, cle, titre, total, photo, lien, datetime.now().isoformat(timespec="seconds")))
        c.commit()
    finally:
        c.close()
    jour = datetime.now().strftime("%Y-%m-%d")
    q = etat.setdefault("push", {})
    if q.get("jour") != jour:
        q.clear()
        q.update(jour=jour, n=0)
    h = _heure_locale(maint)
    nuit = h >= NUIT[0] or h < NUIT[1]
    if not nuit and q["n"] < MAX_JOUR and hasattr(api, "_push"):
        try:
            if api._push(titre, texte, {"lien": lien}):
                q["n"] += 1
        except Exception as e:
            print("Push : " + repr(e), flush=True)
    return True


def _mes_joueurs(api):
    import cartes_match
    out = {}
    for k in api.inventaire_liste({}) or []:
        if k.get("statut") == "Vendue":
            continue
        j = cartes_match.norm(k.get("joueur") or "")
        if j:
            out[j] = out.get(j, 0) + 1
    return out


def verifier(api, maint=None):
    """Chaque heure, pour le compte courant : les alertes cochees. -> {type: nombre envoye}"""
    import cartes_match
    r = reglages(api)
    etat = _lire()
    faits = {}
    mes = _mes_joueurs(api)

    def a_moi(titre):
        t = " " + cartes_match.norm(titre or "") + " "
        return any(" " + j + " " in t for j in mes)

    # -- deals (communs a tous) : gros deal et encan qui finit ---------------------------------------------------
    if r["gros_deal"] or r["encan_fin"]:
        import deals as _d
        l = [x for x in (_d.lire().get("deals") or []) if _d.valide(x) and _d.encore_ouvert(x)]
        budget = None
        try:
            b = api.budget_etat()
            budget = b.get("reste") if b.get("budget") else None
        except Exception:
            pass
        alertes = []
        try:
            import marche
            c = marche._cx(api)
            try:
                alertes = [dict(a) for a in c.execute("SELECT q FROM alertes WHERE actif=1")]
            finally:
                c.close()
        except Exception:
            pass
        if r["gros_deal"]:
            seuil = 1 - r["seuil_deal"] / 100
            bons = [x for x in l if (x.get("ratio") or 1) <= seuil and (a_moi(x.get("titre")) or (budget is not None and (x.get("total") or 0) <= budget)
                                                                       or (not mes and budget is None))]
            for x in sorted(bons, key=lambda y: y.get("ratio") or 1)[:2]:
                rab = round(100 * (1 - (x.get("ratio") or 1)))
                if _notifier(api, etat, "deal:" + str(x["item_id"]), f"🔥 Deal −{rab} % : {cartes_match_titre(x)}",
                             f"{x.get('total', 0):.0f} $ pour une carte qui vaut ~{x.get('valeur', 0):.0f} $", "#deals",
                             x.get("total"), x.get("photo"), maint):
                    faits["gros_deal"] = faits.get("gros_deal", 0) + 1
        if r["encan_fin"]:
            from datetime import timezone
            now = datetime.now(timezone.utc)
            for x in l:
                if not x.get("encan"):
                    continue
                try:
                    reste = datetime.fromisoformat(str(x.get("fin")).replace("Z", "+00:00")) - now
                except ValueError:
                    continue
                if not (timedelta(0) < reste <= timedelta(minutes=75)):
                    continue
                suivie = a_moi(x.get("titre")) or any(not cartes_match.raisons_refus(cartes_match.cible(a["q"]), x.get("titre") or "") for a in alertes)
                if not suivie:
                    continue
                mn = int(reste.total_seconds() // 60)
                if _notifier(api, etat, "fin:" + str(x["item_id"]), f"⏱ Finit dans {mn} min : {cartes_match_titre(x)}",
                             f"Mise actuelle {x.get('total', 0):.0f} $, vaut ~{x.get('valeur', 0):.0f} $", "#deals", x.get("total"), x.get("photo"), maint):
                    faits["encan_fin"] = faits.get("encan_fin", 0) + 1

    # -- joueur en feu (LNH) --------------------------------------------------------------------------------------
    if r["en_feu"] and mes:
        try:
            import nhl
            semaine = datetime.now().strftime("%G-%V")
            for f in nhl.chauds():
                n = mes.get(cartes_match.norm(f["joueur"]))
                if n:
                    if _notifier(api, etat, f"feu:{cartes_match.norm(f['joueur'])}:{semaine}", f"🔥 {f['joueur']} est en feu",
                                 f"{f['points']} points en {f['matchs']} matchs · tu as {n} de ses cartes", "#joueur/" + f["joueur"], maint=maint):
                        faits["en_feu"] = faits.get("en_feu", 0) + 1
                    break
        except Exception as e:
            print("Alertes en feu : " + repr(e), flush=True)

    # -- vendeur : acheteurs interesses, carte vendue -------------------------------------------------------------
    if r["acheteurs"]:
        try:
            import ebay_offres
            g = ebay_offres.eligibles()
            ids = [i for i in (g.get("ids") or []) if i not in ebay_offres.recentes()] if g.get("ok") else []
            neufs = [i for i in ids if "ach:" + str(i) not in (etat.get("vus") or {})]
            if neufs:
                for i in neufs[1:]:
                    etat.setdefault("vus", {})["ach:" + str(i)] = time.time()
                if _notifier(api, etat, "ach:" + str(neufs[0]), "👀 Des acheteurs surveillent tes cartes",
                             f"{len(ids)} annonce{'s' if len(ids) > 1 else ''} : envoie-leur une offre en un tap", "#offres", maint=maint):
                    faits["acheteurs"] = 1
        except Exception as e:
            print("Alertes acheteurs : " + repr(e), flush=True)
    if r["vendu"]:
        lim = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        for k in api.inventaire_liste({"statut": "Vendue"}) or []:
            if str(k.get("vendu_le") or "") < lim:
                continue
            nom = k.get("joueur") or k.get("titre") or "Ta carte"
            if _notifier(api, etat, "vendu:" + str(k.get("id")), f"💰 Vendue : {nom}",
                         f"{(k.get('prix_vendu') or 0):.0f} $" + (f" · profit {k['profit']:+.0f} $" if k.get("profit") is not None else ""),
                         "#inventaire", k.get("prix_vendu"), k.get("photo"), maint):
                faits["vendu"] = faits.get("vendu", 0) + 1
    _ecrire(etat)
    return faits


def cartes_match_titre(x):
    t = str(x.get("titre") or "")
    return t if len(t) <= 60 else t[:57] + "…"
