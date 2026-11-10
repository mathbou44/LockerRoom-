"""
SLABCOACH - le banc de validation (10 nov 2026).

Mathieu : « bati-toi un systeme de validation avec score et itere jusqu'a A+ ; je veux qu'on soit LA reference ».

Chaque jour (admin seulement), sur NOS donnees, sans rien montrer au public :
  1. VALEUR   : pour des centaines de cartes, on cache leur derniere vente et on la predit avec les ventes d'AVANT
                (backtest honnete : jamais une vente du futur). Plusieurs recettes s'affrontent (la regle actuelle, des
                variantes de ses parametres, mediane, recence...) ; on mesure l'ecart median et la part a +/- 15 % et 25 %.
  2. DEALS    : chaque deal montre est note (carnet) ; 14 jours plus tard, on regarde les VRAIES ventes de la meme carte
                apres le deal : etait-ce encore une bonne affaire ? -> la precision des deals.
  3. TENDANCE : il y a 28 jours, la tendance disait « hausse » ou « baisse » ; les 28 jours suivants ont-ils suivi ?
  4. DEMANDE  : le classement des joueurs sans ventes (demande_legale) contre celui des ventes (correlation de rang).
Chaque piece a un score sur 100 et une note (A+ a F). L'ITERATION : la meilleure variante de la regle de valeur est
adoptee toute seule (deals.valeur_sure la lit) quand elle bat la regle en place de 1 point ou plus, sur 150 cartes et plus.
"""
import json
import math
import os
import random
import statistics
import threading
import time
from datetime import datetime, timedelta

_ETAT = {"en_cours": False, "le": 0.0, "d": None, "mtime": None}
_verrou = threading.Lock()
MAX_CARTES = 400
NOTES = ((97, "A+"), (93, "A"), (90, "A-"), (87, "B+"), (83, "B"), (80, "B-"), (77, "C+"), (73, "C"), (70, "C-"), (60, "D"), (0, "F"))


def note(score):
    if score is None:
        return "—"
    return next(n for s, n in NOTES if score >= s)


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "banc.json")


def lire():
    try:
        mt = os.path.getmtime(_chemin())
    except OSError:
        return {}
    if _ETAT["mtime"] != mt:
        try:
            with open(_chemin(), encoding="utf-8") as f:
                _ETAT.update(d=json.load(f), mtime=mt)
        except (OSError, ValueError):
            pass
    return _ETAT["d"] or {}


def _ecrire(d):
    ch = _chemin()
    with open(ch + ".tmp", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(ch + ".tmp", ch)


_RECETTE = {"d": None, "le": 0.0}


def recette():
    """Les parametres adoptes pour la regle de valeur (deals.valeur_sure), relus aux 10 min. {} = la regle d'origine."""
    if _RECETTE["d"] is None or time.time() - _RECETTE["le"] > 600:
        try:
            _RECETTE.update(d=dict((lire().get("recette") or {}).get("valeur") or {}), le=time.time())
        except Exception:
            _RECETTE.update(d={}, le=time.time())
    return _RECETTE["d"] or {}


# -- les cartes et leurs ventes (base_ventes : le plan dit la carte exacte, q la recherche) -------------------------
def _cartes(n=MAX_CARTES, jours=400):
    import base_ventes
    import cartes_match
    depuis = (datetime.now() - timedelta(days=jours)).strftime("%Y-%m-%d")
    c = base_ventes._cx()
    try:
        plan = c.execute("SELECT cible, q FROM plan WHERE q IS NOT NULL").fetchall()
        rnd = random.Random(int(time.time() // 86400))          # un autre echantillon chaque jour
        rnd.shuffle(plan)
        out = []
        for cible, q in plan:
            if len(out) >= n:
                break
            rows = c.execute("SELECT titre, prix, le, url FROM ventes WHERE q=? AND le >= ? ORDER BY le", (q, depuis)).fetchall()
            if len(rows) < 6:
                continue
            cib = cartes_match.cible(cible)
            if cib.get("exclu") or not cib.get("joueur"):
                continue
            vus, vv = set(), []
            for t, p, le, u in rows:
                k = u or f"{t}|{le}|{p}"
                if not p or k in vus or cartes_match.raisons_refus(cib, t or ""):
                    continue
                vus.add(k)
                vv.append({"titre": t, "prix": float(p), "le": str(le)[:10], "url": u})
            if len(vv) >= 6:
                out.append((cible, vv))
            time.sleep(0.002)
        return out
    finally:
        c.close()


def _jours(v, ref):
    try:
        return (ref - datetime.fromisoformat(v["le"][:10])).days
    except ValueError:
        return 999


# -- 1. VALEUR : les recettes qui s'affrontent ----------------------------------------------------------------------
def _valeur_param(pv, ref, p, titre=""):
    """La regle de deals.valeur_sure avec des parametres (min_sures, jours_recents, jours_max, dernieres3), a la date ref."""
    import cartes_match
    pv = [v for v in pv if _jours(v, ref) <= p.get("jours_max", 90)]
    rec = [v for v in pv if _jours(v, ref) <= p.get("jours_recents", 60)]
    if len(rec) >= p.get("min_sures", 3):
        pv = rec
    if len(pv) < 2:
        return None
    prix = sorted(v["prix"] for v in pv)
    if len(pv) == 2:
        return prix[0] if prix[1] <= prix[0] * 1.35 else None
    m, garde = cartes_match.mediane_robuste(prix)
    if not m or len(garde) < p.get("min_sures", 3):
        return None
    if p.get("dernieres3", True):
        d3 = sorted(pv, key=lambda v: v["le"], reverse=True)[:3]
        if len(d3) == 3:
            m = min(m, statistics.median(v["prix"] for v in d3))
    return m


def _recettes():
    base = {"min_sures": 3, "jours_recents": 60, "jours_max": 90, "dernieres3": True}
    r = {"en_place": dict(base, **recette())}
    for ms in (2, 3, 4):
        for jr in (30, 45, 60, 90):
            for d3 in (True, False):
                k = f"ms{ms}_jr{jr}_{'d3' if d3 else 'med'}"
                r[k] = dict(base, min_sures=ms, jours_recents=jr, dernieres3=d3)
    return r


def _simples(pv, ref):
    """Des recettes simples, pour situer la regle : mediane des 5 dernieres, moyenne ponderee par la recence."""
    pv = [v for v in pv if _jours(v, ref) <= 90]
    if len(pv) < 2:
        return {}
    d5 = sorted(pv, key=lambda v: v["le"], reverse=True)[:5]
    poids = [(math.exp(-_jours(v, ref) / 30.0), v["prix"]) for v in pv]
    return {"mediane_5": statistics.median(v["prix"] for v in d5),
            "recence": sum(w * x for w, x in poids) / sum(w for w, _ in poids)}


def valider_valeur(cartes):
    rec = _recettes()
    res = {k: [] for k in list(rec) + ["mediane_5", "recence"]}
    tot = 0
    for _cible, vv in cartes:
        cible_v = vv[-1]                                          # la vente cachee : la plus recente
        ref = datetime.fromisoformat(cible_v["le"][:10])
        avant = [v for v in vv[:-1] if v["le"] < cible_v["le"]]  # jamais une vente du meme jour ou du futur
        if len(avant) < 3:
            continue
        tot += 1
        for k, p in rec.items():
            pr = _valeur_param(avant, ref, p)
            res[k].append(None if not pr else abs(pr - cible_v["prix"]) / cible_v["prix"])
        for k, pr in _simples(avant, ref).items():
            res[k].append(None if not pr else abs(pr - cible_v["prix"]) / cible_v["prix"])
    out = {}
    for k, l in res.items():
        ok = [e for e in l if e is not None]
        if not l:
            continue
        d25 = sum(1 for e in ok if e <= 0.25) / len(ok) if ok else 0
        out[k] = {"n": len(l), "couverture": round(len(ok) / len(l), 3), "ecart_median": round(statistics.median(ok), 3) if ok else None,
                  "dans15": round(sum(1 for e in ok if e <= 0.15) / len(ok), 3) if ok else 0, "dans25": round(d25, 3),
                  # le score : la precision (a +/- 25 %), un peu ponderee par la couverture (une regle qui se tait souvent ne gagne pas)
                  "score": round(100 * (0.85 * d25 + 0.15 * (len(ok) / len(l))), 1)}
    return {"cartes": tot, "recettes": out}


# -- 2. DEALS : le carnet et la verite d'apres -------------------------------------------------------------------
def noter_deals(d):
    """Garde chaque deal montre (une fois, a sa premiere apparition)."""
    try:
        import deals
        l = deals.lire().get("deals") or []
    except Exception:
        return d
    carnet = d.setdefault("carnet", {})
    auj = datetime.now().strftime("%Y-%m-%d")
    for x in l:
        iid = str(x.get("item_id") or "")
        if not iid or iid in carnet or not x.get("valeur") or not x.get("total"):
            continue
        carnet[iid] = {"titre": str(x.get("titre") or "")[:160], "total": x["total"], "valeur": x["valeur"], "le": auj,
                       "encan": bool(x.get("encan")), "source": x.get("valeur_source"), "n": x.get("n")}
    lim = (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d")
    d["carnet"] = {k: v for k, v in carnet.items() if v.get("le", "") >= lim}
    return d


def valider_deals(d):
    import base_ventes
    import cartes_match
    lim = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
    c = base_ventes._cx()
    bons = tot = 0
    ecarts, par_source = [], {}
    try:
        for iid, x in list((d.get("carnet") or {}).items())[:600]:
            if x.get("le", "9") > lim:
                continue                                          # trop recent : la verite n'est pas encore la
            cib = cartes_match.cible_titre(x["titre"])
            nom = [w for w in (cib.get("joueur") or "").split() if len(w) >= 3]
            if not nom or cib.get("exclu"):
                continue
            fin = (datetime.fromisoformat(x["le"]) + timedelta(days=30)).strftime("%Y-%m-%d")
            rows = c.execute("SELECT titre, prix, url FROM ventes WHERE le >= ? AND le <= ? AND titre LIKE ? LIMIT 400",
                             (x["le"], fin, "%" + nom[-1] + "%")).fetchall()
            vrais = [float(p) for t, p, u in rows if p and iid not in str(u or "") and not cartes_match.raisons_refus(cib, t or "")]
            if len(vrais) < 2:
                continue
            v_reel = statistics.median(vrais)
            tot += 1
            ok = x["total"] <= v_reel * 0.85                       # encore 15 % sous le marche reel : un vrai deal
            bons += ok
            ecarts.append(abs(x["valeur"] - v_reel) / v_reel)
            s = par_source.setdefault(x.get("source") or "vendues", [0, 0])
            s[0] += ok
            s[1] += 1
            time.sleep(0.002)
    finally:
        c.close()
    return {"verifies": tot, "precision": round(bons / tot, 3) if tot else None,
            "ecart_valeur_median": round(statistics.median(ecarts), 3) if ecarts else None,
            "par_source": {k: {"precision": round(a / b, 3), "n": b} for k, (a, b) in par_source.items()},
            "score": round(100 * bons / tot, 1) if tot >= 10 else None}


# -- 3. TENDANCE : la direction annoncee il y a 28 jours s'est-elle produite ? --------------------------------------
def valider_tendance(cartes, jours=28):
    bons = tot = 0
    t0 = datetime.now() - timedelta(days=jours)
    for _cible, vv in cartes:
        avant = [v["prix"] for v in vv if (t0 - timedelta(days=jours)).strftime("%Y-%m-%d") <= v["le"] < t0.strftime("%Y-%m-%d")]
        plus_avant = [v["prix"] for v in vv if (t0 - timedelta(days=jours * 3)).strftime("%Y-%m-%d") <= v["le"] < (t0 - timedelta(days=jours)).strftime("%Y-%m-%d")]
        apres = [v["prix"] for v in vv if v["le"] >= t0.strftime("%Y-%m-%d")]
        if len(avant) < 3 or len(plus_avant) < 3 or len(apres) < 3:
            continue
        a, b, c_ = statistics.median(plus_avant), statistics.median(avant), statistics.median(apres)
        pred = (b - a) / a if a else 0
        if abs(pred) < 0.10:
            continue                                              # « stable » : pas de pari
        reel = (c_ - b) / b if b else 0
        tot += 1
        bons += (pred > 0) == (reel > 0)
    return {"paris": tot, "justes": round(bons / tot, 3) if tot else None, "score": round(100 * bons / tot, 1) if tot >= 10 else None}


# -- la passe du jour ------------------------------------------------------------------------------------------
def passe():
    d = dict(lire())
    d = noter_deals(d)
    cartes = _cartes()
    v = valider_valeur(cartes)
    t = valider_tendance(cartes)
    dl = valider_deals(d)
    try:
        import demande_legale
        lb = (demande_legale.lire().get("labo") or {})
        g = (lb.get("combinaisons") or {}).get(lb.get("garde") or "") or {}
        dem = {"rho": g.get("rho"), "top20": g.get("top20"), "n": lb.get("n"), "score": round(100 * g["rho"], 1) if g.get("rho") is not None else None}
    except Exception:
        dem = {"score": None}
    rv = v.get("recettes") or {}
    en_place = (rv.get("en_place") or {}).get("score")
    meilleure = max((k for k in rv if k not in ("mediane_5", "recence")), key=lambda k: rv[k]["score"], default=None)
    adopte = None
    # l'iteration : une variante meilleure d'au moins 1 point, mesuree sur 150 cartes et plus, devient la regle
    if meilleure and meilleure != "en_place" and en_place is not None and v["cartes"] >= 150 and rv[meilleure]["score"] >= en_place + 1.0:
        p = {k: val for k, val in _recettes()[meilleure].items()}
        d.setdefault("recette", {})["valeur"] = p
        adopte = {"recette": meilleure, "avant": en_place, "apres": rv[meilleure]["score"], "le": datetime.now().isoformat(timespec="seconds")}
        d.setdefault("historique_recettes", []).append(adopte)
        _RECETTE["d"] = None
    scores = {"valeur": (rv.get("en_place") or {}).get("score"), "deals": dl.get("score"), "tendance": t.get("score"), "demande": dem.get("score")}
    valides = [s for s in scores.values() if s is not None]
    d["dernier"] = {"le": datetime.now().isoformat(timespec="seconds"), "valeur": v, "deals": dl, "tendance": t, "demande": dem,
                    "scores": scores, "notes": {k: note(s) for k, s in scores.items()},
                    "global": round(sum(valides) / len(valides), 1) if valides else None, "meilleure_valeur": meilleure, "adopte": adopte}
    d["dernier"]["note_globale"] = note(d["dernier"]["global"])
    hist = d.setdefault("serie", [])
    hist.append({"le": d["dernier"]["le"][:10], **{k: s for k, s in scores.items()}, "global": d["dernier"]["global"]})
    d["serie"] = hist[-120:]
    with _verrou:
        _ecrire(d)
    return d["dernier"]


def passe_si_besoin():
    """Une fois par jour (la nuit, heure du serveur), en arriere-plan."""
    if _ETAT["en_cours"] or time.time() - _ETAT["le"] < 20 * 3600 or os.environ.get("LR_BANC") == "0":
        return False
    der = (lire().get("dernier") or {}).get("le")
    if der and der[:10] == datetime.now().strftime("%Y-%m-%d"):
        _ETAT["le"] = time.time()
        return False
    _ETAT.update(en_cours=True, le=time.time())

    def tache():
        try:
            r = passe()
            print("Banc de validation :", r.get("note_globale"), r.get("scores"), flush=True)
        except Exception as e:
            print("Banc de validation : " + repr(e), flush=True)
        finally:
            _ETAT["en_cours"] = False
    threading.Thread(target=tache, daemon=True, name="banc").start()
    return True


def resume():
    d = lire()
    der = d.get("dernier") or {}
    return {"le": der.get("le"), "global": der.get("global"), "note": der.get("note_globale"), "scores": der.get("scores"),
            "notes": der.get("notes"), "valeur": der.get("valeur"), "deals": der.get("deals"), "tendance": der.get("tendance"),
            "demande": der.get("demande"), "adopte": der.get("adopte"), "meilleure_valeur": der.get("meilleure_valeur"),
            "serie": (d.get("serie") or [])[-30:], "recette": (d.get("recette") or {}).get("valeur"), "carnet": len(d.get("carnet") or {})}
