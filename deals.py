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
        if not med or len(garde) < 3:
            continue
        comps = sorted(({"titre": x["titre"], "total": _total(x), "photo": x.get("photo"), "url": x.get("url")} for x in memes),
                       key=lambda x: abs(x["total"] - med))[:8]
        _c, memes_e, _e = cartes_match.filtrer(r["q"], encans)
        for a in memes + memes_e:
            t = _total(a)
            if not t or t > med * RATIO_DEAL:
                continue
            fin = a.get("fin")
            if a.get("encan"):
                try:
                    fin_dt = datetime.fromisoformat(str(fin).replace("Z", "+00:00"))
                except ValueError:
                    continue
                if fin_dt - maint > timedelta(hours=24):          # encan : seulement ceux qui finissent bientot
                    continue
            deals[a["item_id"]] = {"item_id": a["item_id"], "titre": a["titre"], "total": t, "photo": a.get("photo"), "url": a.get("url"),
                                   "valeur": med, "ratio": round(t / med, 3), "encan": bool(a.get("encan")), "fin": fin,
                                   "mises": a.get("mises"), "sport": r["sport"], "joueur": r["joueur"], "q": r["q"], "n": len(garde),
                                   "comps": comps, "vu_le": maint.isoformat(timespec="seconds")}
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
