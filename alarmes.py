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

TYPES = ["prix_cible", "gros_deal", "encan_fin", "en_feu", "acheteurs", "vendu", "mes_joueurs", "iq_nouvelle", "iq_occasion"]
# 28 oct 2026 (audit Apple 4.5.4) : les alertes « promotionnelles » (deals, joueur en feu) seulement si l'utilisateur les coche
DEFAUT = {"prix_cible": True, "gros_deal": False, "encan_fin": True, "en_feu": False, "acheteurs": True, "vendu": True,
          "mes_joueurs": False, "iq_nouvelle": False, "iq_occasion": False, "seuil_deal": 40}
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


def _notifier(api, etat, cle, titre, texte, lien, total=None, photo=None, maint=None, force=False):
    """Une alerte, une seule fois : dans la cloche toujours ; sur l'iPhone si le quota du jour et l'heure le permettent.
    force (29 oct 2026, watchlist) : une alerte que l'utilisateur a demandee pour UNE carte (« place ta mise ») part
    meme la nuit et hors quota : les encans finissent souvent le soir."""
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
        # 9 nov 2026 (« on distingue pas le but de la notif ») : le detail est garde aussi (2e ligne dans l'app)
        c.execute("INSERT INTO notifications (alerte_id, item_id, titre, total, photo, url, le, texte) VALUES (?,?,?,?,?,?,?,?)",
                  (None, cle, titre, total, photo, lien, datetime.now().isoformat(timespec="seconds"), str(texte or "")[:240]))
        c.commit()
    finally:
        c.close()
    try:                                                 # 3 nov 2026 (revue) : le jour de Montreal (le serveur est en UTC)
        from zoneinfo import ZoneInfo
        jour = datetime.now(ZoneInfo("America/Toronto")).strftime("%Y-%m-%d")
    except Exception:
        jour = datetime.now().strftime("%Y-%m-%d")
    q = etat.setdefault("push", {})
    if q.get("jour") != jour:
        q.clear()
        q.update(jour=jour, n=0)
    h = _heure_locale(maint)
    nuit = h >= NUIT[0] or h < NUIT[1]
    if (force or (not nuit and q["n"] < MAX_JOUR)) and hasattr(api, "_push"):
        try:
            if api._push(titre, texte, {"lien": lien}) and not force:
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
    import lockerroom as _lr                   # 10 nov 2026 : deals = admin seulement (licence eBay §8.5 c, §9.5)
    if (r["gros_deal"] or r["encan_fin"]) and _lr.ebay_prix_actif(api):
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
                if _notifier(api, etat, "deal:" + str(x["item_id"]), f"Deal −{rab} % : {cartes_match_titre(x)}",
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
                if _notifier(api, etat, "fin:" + str(x["item_id"]), f"Finit dans {mn} min : {cartes_match_titre(x)}",
                             f"Mise actuelle {x.get('total', 0):.0f} $, vaut ~{x.get('valeur', 0):.0f} $", "#deals", x.get("total"), x.get("photo"), maint):
                    faits["encan_fin"] = faits.get("encan_fin", 0) + 1

    # -- joueur en feu : l'Indice joueur de la semaine (stats et donnees publiques, jamais un prix eBay) --------------
    # 10 nov 2026 (Mathieu : « une alerte quand ton joueur est en feu, avant que le marche reagisse ») : ses joueurs = ceux
    # de son inventaire + ceux de son Radar (questionnaire) ; une alerte par joueur par semaine, une seule par passe
    if r["en_feu"]:
        try:
            import indice_joueurs
            suivis = dict(mes)
            try:
                for f in (api.deals_profil_lire().get("favoris") or []):
                    suivis.setdefault(cartes_match.norm(f), 0)
            except Exception:
                pass
            semaine = datetime.now().strftime("%G-%V")
            I = indice_joueurs.lire().get("indice") or {}
            for nom, v in sorted(I.items(), key=lambda kv: -(kv[1].get("criteres", {}).get("forme") or 0)):
                k = cartes_match.norm(nom)
                if k not in suivis:
                    continue
                p, w = v.get("pastilles") or [], v.get("semaine") or {}
                n = suivis[k]
                fin_t = (f" · tu as {n} de ses cartes" if n else " · ses cartes sont dans ton Radar")
                if "en_feu" in p and (w.get("pts") or 0) >= 3:
                    if _notifier(api, etat, f"feu:{k}:{semaine}", f"{nom} est en feu",
                                 f"{w.get('pts')} points ({w.get('b', 0)} buts) en {w.get('mj')} matchs cette semaine" + fin_t,
                                 "#joueur/" + nom, maint=maint):
                        faits["en_feu"] = faits.get("en_feu", 0) + 1
                        break
                elif "buzz" in p:
                    if _notifier(api, etat, f"buzz:{k}:{semaine}", f"{nom} fait jaser",
                                 "Tout le monde le cherche cette semaine (visites en forte hausse)" + fin_t, "#joueur/" + nom, maint=maint):
                        faits["en_feu"] = faits.get("en_feu", 0) + 1
                        break
        except Exception as e:
            print("Alertes en feu : " + repr(e), flush=True)

    # -- 13 nov 2026 (Mathieu : « SlabIQ doit connaitre les cartes de l'inventaire et lui dire s'il devrait verifier la
    # valeur de son annonce si bonne nouvelle » ; « dans les notifs que l'utilisateur peut activer ») ------------------
    # iq_nouvelle : un joueur de TES cartes a une nouvelle forte (Temple, honneur, trophee, exploit, pic de recherches) ->
    # verifie le prix de ton annonce ; une mauvaise nouvelle -> ne brade pas tout de suite. Une fois par joueur par semaine.
    # iq_occasion : un bon joueur (tes joueurs suivis, ou un grand nom) en creux ou apres une mauvaise nouvelle : ses
    # cartes baissent souvent pour un temps. Des faits publics seulement : jamais un prix.
    if r.get("iq_nouvelle") or r.get("iq_occasion"):
        try:
            import indice_joueurs
            I = indice_joueurs.lire().get("indice") or {}
            semaine = datetime.now().strftime("%G-%V")
            if r.get("iq_nouvelle") and mes:
                for nom, v in sorted(I.items(), key=lambda kv: -((kv[1].get("ev_pos") or 0) + 4 * (kv[1].get("pic") or 0))):
                    k = cartes_match.norm(nom)
                    if k not in mes:
                        continue
                    p, evs, n = v.get("pastilles") or [], v.get("evenements") or [], mes[k]
                    bon = next((e for e in evs if e.get("sens", 0) > 0), None)
                    mauv = next((e for e in evs if e.get("sens", 0) < 0), None)
                    cartes = f"tu as {n} de ses cartes" if n > 1 else "tu as une de ses cartes"
                    if (v.get("ev_pos") or 0) >= 10 or "honneur" in p or (v.get("pic") or 0) >= 3:
                        quoi = (bon or {}).get("titre") or "Tout le monde le cherche ces jours-ci (recherches en forte hausse)"
                        if _notifier(api, etat, f"iqn:{k}:{semaine}", f"Bonne nouvelle pour {nom}",
                                     f"{quoi[:120]} · {cartes} : vérifie le prix de ton annonce", "#iqcartes/" + nom, maint=maint):
                            faits["iq_nouvelle"] = faits.get("iq_nouvelle", 0) + 1
                            break
                    elif "mauvaise" in p and mauv:
                        if _notifier(api, etat, f"iqm:{k}:{semaine}", f"Mauvaise nouvelle pour {nom}",
                                     f"{mauv['titre'][:120]} · {cartes} : ne baisse pas ton prix trop vite, ça passe souvent", "#iqcartes/" + nom, maint=maint):
                            faits["iq_nouvelle"] = faits.get("iq_nouvelle", 0) + 1
                            break
            if r.get("iq_occasion"):
                suivis = set()
                try:
                    suivis = {cartes_match.norm(f) for f in (api.deals_profil_lire().get("favoris") or [])}
                except Exception:
                    pass
                cands = [(nom, v) for nom, v in I.items() if "occasion" in (v.get("pastilles") or [])
                         and (cartes_match.norm(nom) in suivis or (v.get("indice") or 0) >= 55 or (v.get("criteres") or {}).get("demande", 0) >= 70)]
                for nom, v in sorted(cands, key=lambda kv: -(kv[1].get("indice") or 0)):
                    k = cartes_match.norm(nom)
                    mauv = next((e for e in v.get("evenements") or [] if e.get("sens", 0) < 0), None)
                    pq = (mauv["titre"][:110] + " · ") if mauv else ("En creux cette saison · " if v.get("creux") else "")
                    if _notifier(api, etat, f"iqo:{k}:{semaine}", f"Bonne occasion : {nom}",
                                 pq + "ses cartes baissent souvent pour un temps : c'est le moment de regarder", "#joueur/" + nom, maint=maint):
                        faits["iq_occasion"] = faits.get("iq_occasion", 0) + 1
                        break
        except Exception as e:
            print("Alertes SlabIQ : " + repr(e), flush=True)

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
                if _notifier(api, etat, "ach:" + str(neufs[0]), "Des acheteurs surveillent tes cartes",
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
            if _notifier(api, etat, "vendu:" + str(k.get("id")), f"Vendue : {nom}",
                         f"{(k.get('prix_vendu') or 0):.0f} $" + (f" · profit {k['profit']:+.0f} $" if k.get("profit") is not None else ""),
                         "#inventaire", k.get("prix_vendu"), k.get("photo"), maint):
                faits["vendu"] = faits.get("vendu", 0) + 1
    _ecrire(etat)
    return faits


def mes_joueurs(api, maint=None):
    """31 oct 2026 (Mathieu : « avertir l'utilisateur que ses joueurs suivis ont pop dans les deals ») : aux 5 min, un deal
    (ou un encan d'un gros vendeur a 70 % ou moins de sa valeur) sur un des joueurs / equipes suivis -> une alerte, une
    seule fois par annonce. Au plus 3 par passage. -> nombre envoye."""
    if not reglages(api).get("mes_joueurs"):
        return 0
    import lockerroom as _lr
    if not _lr.ebay_prix_actif(api):              # 10 nov 2026 : deals = admin seulement (licence eBay)
        return 0
    p = api.reglages_lire().get("deals_profil") or {}
    favs = [(f, api._norm_fav(f)) for f in (p.get("favoris") or []) if len(str(f).strip()) >= 3]
    if not favs:
        return 0
    import deals as _d
    d = _d.lire_vite()
    cands = [x for x in d.get("deals") or [] if _d.valide(x) and _d.encore_ouvert(x)]
    cands += [x for x in d.get("suivis") or [] if x.get("valeur") and _d.encore_ouvert(x)
              and (x.get("total") or 0) <= _d.prix_max(x["valeur"])]
    etat = _lire()
    n = 0
    for x in sorted(cands, key=lambda y: (y.get("total") or 0) / (y.get("valeur") or 1)):
        t = api._norm_fav((x.get("titre") or "") + " " + str(x.get("joueur") or ""))
        f = next((nom for nom, k in favs if k in t), None)
        if not f or "fav:" + str(x.get("item_id")) in (etat.get("vus") or {}):
            continue
        rab = round(100 * (1 - (x.get("total") or 0) / x["valeur"])) if x.get("valeur") else None
        quoi = tt_fin(x)
        if _notifier(api, etat, "fav:" + str(x["item_id"]), f"{f} : deal{f' −{rab} %' if rab else ''}",
                     f"{cartes_match_titre(x)} · {x.get('total', 0):.0f} $" + quoi, "#deals", x.get("total"), x.get("photo"), maint):
            n += 1
        if n >= 3:
            break
    _ecrire(etat)
    return n


def tt_fin(x):
    if not x.get("encan") or not x.get("fin"):
        return ""
    try:
        from datetime import timezone
        m = int((datetime.fromisoformat(str(x["fin"]).replace("Z", "+00:00")) - datetime.now(timezone.utc)).total_seconds() // 60)
    except ValueError:
        return ""
    if m <= 0:
        return ""
    return f" · finit dans {m // 60} h {m % 60:02d}" if m >= 60 else f" · finit dans {m} min"


def cartes_match_titre(x):
    t = str(x.get("titre") or "")
    return t if len(t) <= 60 else t[:57] + "…"
