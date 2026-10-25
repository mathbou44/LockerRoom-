"""
LOCKERROOM - les deals pour les acheteurs (24 oct 2026).

Mathieu : « revoir la page deal ... ajouter des filtres au debut pour le/les sports choisis, deal se finissant
le plus tot, meilleur deal etc. Comme dans hall of cardz, on doit pouvoir voir les comp en cliquant sur la
pastille du deal ».

Un chasseur partage par tout le serveur (les deals sont les memes pour tous) : chaque heure, quelques
recherches eBay (joueurs les plus demandes x cartes recrues du catalogue), prix fixe ET encans qui finissent
bientot. Une annonce est un deal si elle coute 70 % ou moins de la mediane des MEMES cartes (cartes_match).
Chaque deal garde ses comparables (pour la pastille). Budget : ~15 recherches par heure.
"""
import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone

RATIO_DEAL = 0.70
VERSION = 2                      # 26 oct 2026 : valeur par annonce (les deals d'avant sont retires)
ENCAN_H = 6                      # 25 oct 2026 : un encan n'est montre que s'il finit dans 6 h (avant, la mise monte encore)
PAR_TOUR = 8                     # requetes par tour (x2 appels : prix fixe + encans)
FRAICHEUR_S = 3600
_verrou = threading.Lock()
_ETAT = {"en_cours": False}


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "deals_globaux.json")


def lire():
    try:
        with open(_chemin(), encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def _ecrire(d):
    tmp = _chemin() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, _chemin())


_VALIDES = {}


def valide(x):
    """La carte passe-t-elle les regles ACTUELLES du filtre ? (les deals gardes d'avant une correction sont retires)."""
    import cartes_match
    if int(x.get("v") or 0) < VERSION:
        return False
    k = (x.get("item_id"), x.get("q"), x.get("titre"))
    if k not in _VALIDES:
        if len(_VALIDES) > 5000:
            _VALIDES.clear()
        _VALIDES[k] = not x.get("q") or not cartes_match.raisons_refus(cartes_match.cible(x["q"]), x.get("titre") or "")
    return _VALIDES[k]


def requetes():
    """Les cartes que les acheteurs cherchent : recrues des produits du catalogue, joueurs les plus demandes d'abord."""
    import catalogue
    import valeurs
    dem = (valeurs._charger() or {}).get("joueurs") or {}
    out = []
    for p in catalogue.liste():
        try:
            prod = catalogue.charger(p["id"])
        except Exception:
            continue
        nom = str(prod.get("nom") or "")
        insert = "young guns" if "series" in nom.lower() or "extended" in nom.lower() else \
                 "future watch" if "sp authentic" in nom.lower() else "rookie"
        for c in prod.get("cartes") or []:
            if not c.get("recrue") or not c.get("joueur"):
                continue
            j = str(c["joueur"]).split("/")[0].strip()
            out.append({"q": f"{j} {insert}", "joueur": j, "sport": prod.get("sport") or "hockey",
                        "poids": float(dem.get(j) or 1.0)})
    vus, uniq = set(), []
    for r in sorted(out, key=lambda x: -x["poids"]):
        if r["q"].lower() not in vus:
            vus.add(r["q"].lower())
            uniq.append(r)
    return uniq[:120]


def _total(a):
    return round((a.get("prix_cad") or 0) + (a.get("port_cad") or 0), 2)


def valeur_annonce(a, ventes, actives):
    """La valeur de LA carte d'une annonce : mediane des ventes de la meme carte (3 au moins) ; sinon les autres
    annonces de la meme carte moins 15 % (3 au moins). -> (valeur, source, n, ventes) ou None."""
    import cartes_match
    cib = cartes_match.cible_titre(a.get("titre") or "")
    pv = [v for v in ventes or [] if v.get("prix") and not cartes_match.raisons_refus(cib, v.get("titre") or "")]
    if len(pv) >= 3:
        m = cartes_match.mediane_robuste([v["prix"] for v in pv])[0] if len(pv) >= 4 else sorted(v["prix"] for v in pv)[len(pv) // 2]
        pv.sort(key=lambda v: str(v.get("le") or ""), reverse=True)
        return round(m, 2), "vendues", len(pv), [{k: v.get(k) for k in ("titre", "prix", "le", "photo", "url")} for v in pv[:6]]
    pa = [_total(x) for x in actives or [] if x.get("item_id") != a.get("item_id")
          and not cartes_match.raisons_refus(cib, x.get("titre") or "")]
    if len(pa) >= 3:
        return round(cartes_match.mediane_robuste(pa)[0] * 0.85, 2), "annonces", len(pa), []
    return None


def chasser(n=PAR_TOUR, rechercher=None):
    """Un tour : n requetes (on reprend la ou on etait), deals gardes 48 h (encans : jusqu'a la fin)."""
    import cartes_match
    import ebay_compte
    rechercher = rechercher or ebay_compte.rechercher
    d = lire()
    reqs = requetes()
    if not reqs:
        return {"ok": True, "deals": 0}
    i0 = int(d.get("curseur") or 0) % len(reqs)
    lot = (reqs[i0:] + reqs[:i0])[:n]
    maint = datetime.now(timezone.utc)
    deals = {x["item_id"]: x for x in d.get("deals") or []}
    trouves = 0
    for r in lot:
        try:
            fixes = rechercher(r["q"], categorie="261328", limite=100, fond=True)
            encans = rechercher(r["q"], categorie="261328", limite=50, fond=True, encheres=True)
        except (RuntimeError, OSError):
            break
        _c, memes, _e = cartes_match.filtrer(r["q"], fixes)
        med, garde = cartes_match.mediane_robuste([_total(x) for x in memes])
        # 26 oct 2026 (Mathieu : « en quoi c'est 60 $ de profit ? » - un Purple Shock a 1 $ « vaut 70 $ » : la valeur
        # etait celle de TOUTE la recherche, autos et gradees comprises) : chaque annonce a SA valeur, celle des
        # ventes de la MEME carte (meme parallele, meme numero, brute ou gradee pareil), sinon pas de deal.
        try:
            import vendues
            q_v = cartes_match.requete_ebay(cartes_match.cible(r["q"])) or r["q"]
            brut_v = vendues.rechercher(q_v, fond=True).get("ventes") or []
        except Exception:
            brut_v = []
        # 25 oct 2026 (Mathieu : « base-toi toujours sur les last sold ») : valeur = ventes reelles ; sans ventes,
        # les prix demandes moins 15 % (ils sont souvent plus hauts que ce qui se vend vraiment)
        try:
            import vendues
            vs = vendues.memes(r["q"], requete=True, n=8, fond=True)
        except Exception:
            vs = {}
        vmed = vs.get("mediane") if (vs.get("nb") or 0) >= 3 else None
        if not vmed and (not med or len(garde) < 3):
            continue
        source = "vendues" if vmed else "annonces"
        med = vmed or round(med * 0.85, 2)
        ventes = [{k: v.get(k) for k in ("titre", "prix", "le", "photo", "url")} for v in (vs.get("ventes") or [])[:6]]
        comps = sorted(({"titre": x["titre"], "total": _total(x), "photo": x.get("photo"), "url": x.get("url")} for x in memes),
                       key=lambda x: abs(x["total"] - med))[:8]
        _c, memes_e, _e = cartes_match.filtrer(r["q"], encans)
        plafond = max([v["prix"] for v in brut_v] + [med or 0]) * RATIO_DEAL
        for a in memes + memes_e:
            t = _total(a)
            if not t or t > plafond:
                continue
            va = valeur_annonce(a, brut_v, memes)
            if not va:
                continue
            med_a, source_a, n_a, ventes_a = va
            if t > med_a * RATIO_DEAL:
                continue
            fin = a.get("fin")
            if a.get("encan"):
                try:
                    fin_dt = datetime.fromisoformat(str(fin).replace("Z", "+00:00"))
                except ValueError:
                    continue
                if fin_dt - maint > timedelta(hours=ENCAN_H):     # encan : seulement ceux qui finissent bientot
                    continue
            deals[a["item_id"]] = {"item_id": a["item_id"], "titre": a["titre"], "total": t, "photo": a.get("photo"), "url": a.get("url"),
                                   "valeur": med_a, "ratio": round(t / med_a, 3), "encan": bool(a.get("encan")), "fin": fin,
                                   "mises": a.get("mises"), "sport": r["sport"], "joueur": r["joueur"], "q": r["q"],
                                   "n": n_a, "valeur_source": source_a, "vendues": ventes_a or ventes,
                                   "comps": comps, "vu_le": maint.isoformat(timespec="seconds"), "v": VERSION}
            trouves += 1
    limite = (maint - timedelta(hours=48)).isoformat()
    garde_ = []
    for x in deals.values():
        if x.get("encan"):
            try:
                if datetime.fromisoformat(str(x.get("fin")).replace("Z", "+00:00")) < maint:
                    continue
            except ValueError:
                continue
        elif str(x.get("vu_le") or "") < limite:
            continue
        if not valide(x):
            continue
        garde_.append(x)
    garde_.sort(key=lambda x: x["ratio"])
    d.update(deals=garde_[:300], curseur=(i0 + len(lot)) % len(reqs), maj=maint.isoformat(timespec="seconds"))
    with _verrou:
        _ecrire(d)
    return {"ok": True, "deals": len(garde_), "nouveaux": trouves}


def chasser_si_besoin():
    """En arriere-plan, au plus une fois par heure, jamais deux a la fois."""
    d = lire()
    try:
        age = time.time() - datetime.fromisoformat(str(d.get("maj"))).timestamp()
    except ValueError:
        age = 1e9
    if age < FRAICHEUR_S:
        return False
    with _verrou:
        if _ETAT["en_cours"]:
            return False
        _ETAT["en_cours"] = True

    def tache():
        try:
            chasser()
        except Exception as e:
            print("Deals : " + repr(e), flush=True)
        finally:
            _ETAT["en_cours"] = False
    threading.Thread(target=tache, daemon=True, name="deals").start()
    return True
