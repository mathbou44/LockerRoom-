"""
SLABCOACH - les joueurs cles et leur marche « au plus bas » (16 nov 2026).

Mathieu : « comprendre les marches des joueurs vraiment populaires (pas un joueur de 4e trio) : grandes carrieres, grande
popularite, beaucoup de saisons dans la meme equipe ; les joueurs que le monde aime acheter et suit. Savoir quand un de ces
joueurs est plus bas qu'a l'habitude : comme a la bourse, ca tend a remonter quand le monde se rend compte qu'il est bas ».
« Ca doit etre integre dans SlabIQ : une pastille, et dans le Trending ; jamais alourdir la vue ».

1. LES JOUEURS CLES (cles) : un score 0-100 sur des criteres publics (LNH : Temple, top 100, trophees, carriere, saisons
   dans la meme equipe) et nos propres donnees (le nombre de ventes de ses cartes dans nos archives, le nombre de membres qui
   le suivent). Les vedettes de SlabCoach (deals.VEDETTES) en sont toujours. Au plus N_CLES joueurs.
2. L'INDICE DE MARCHE d'un joueur, comme un indice boursier : chaque vente de ses cartes (nos archives, base_ventes) est
   comparee a la NORMALE de sa sorte de carte (types_cartes : famille + note, et la tranche de tirage) sur les 180 jours
   d'avant ; l'indice = la mediane de ces rapports sur les 14 derniers jours. 1,00 = normal ; 0,82 = 18 % sous la normale.
   On mesure le JOUEUR, pas une carte : une Young Guns et une Kaboom se comparent chacune a elles-memes.
3. LE SIGNAL « marche bas » : l'indice sous 1 - seuil, avec assez de ventes. Pour les joueurs de la banque Young Guns, l'etat
   « creux » de moment_yg (deja mesure sur 62 858 ventes) compte aussi.
4. LA VERIFICATION (chaque semaine, avant d'afficher quoi que ce soit) : sur l'annee de ventes, chaque semaine passee ou un
   joueur cle etait bas est rejouee : son marche etait-il plus haut 46 a 74 jours plus tard ? On essaie plusieurs seuils et on
   garde celui dont la borne basse (Wilson) bat le plus le taux de TOUS les joueurs cles au meme moment (le hasard). Si aucun
   seuil ne bat le hasard, rien n'est affiche (actif = False) ; l'admin voit les taux.
Les prix viennent de nos archives de ventes : le public voit l'ecart en % et la pastille, jamais un prix.
"""
import json
import math
import os
import statistics
import threading
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

N_CLES = 120
SCORE_CLE_MIN = 35
W = 14                  # jours de l'indice
BASE = 180              # jours de la normale
N_BASE_MIN = 4          # ventes d'une sorte dans la normale
N_W_MIN = 6             # ventes comparees dans les 14 jours
H0, H1 = 46, 74         # « deux mois apres » (comme moment_yg)
SEUILS = (0.10, 0.15, 0.20, 0.25, 0.30)
N_TEST_MIN = 30         # creux passes pour juger un seuil
REMONTE = 1.05          # « remonte » : 5 % plus haut que le jour du creux
_ETAT = {"mt": None, "d": None, "en_cours": False}
_verrou = threading.Lock()


# -- 1. les joueurs cles --------------------------------------------------------------------------------------------------
def fidelite(h):
    """Le plus de saisons LNH (20 matchs et plus) jouees dans la MEME equipe."""
    c = Counter()
    for x in (h or {}).get("equipes") or []:
        try:
            s, eq, gp = x[0], x[1], int(x[2] or 0)
        except (TypeError, ValueError, IndexError):
            continue
        if eq and gp >= 20:
            c[eq] += 1
    return max(c.values()) if c else 0


def _pct_rangs(d):
    """{cle: valeur} -> {cle: 0..1} (rang centile ; 0 si la valeur est 0)."""
    l = sorted(v for v in d.values() if v > 0)
    if not l:
        return {}
    import bisect
    return {k: (bisect.bisect_right(l, v) / len(l) if v > 0 else 0.0) for k, v in d.items()}


def score_cle(h, r_ventes=0.0, r_suivis=0.0):
    """(score 0-100, raisons) d'un joueur : sa carriere (fiche LNH h) et ce que le monde achete / suit (rangs 0..1)."""
    h = h or {}
    raisons = []
    s = 0.0
    if h.get("hhof"):
        s += 25
        raisons.append("temple")
    if h.get("top100"):
        s += 15
        raisons.append("top100")
    tw = 0.0
    try:
        import indice_joueurs
        tp = indice_joueurs.TROPHEES_POIDS
    except Exception:
        tp = {}
    for k, n in (h.get("trophees_c") or {}).items():
        tw += tp.get(k, 0.6) * int(n or 0)
    if tw:
        s += min(15.0, 4.0 * math.log1p(tw))
        if tw >= 4:
            raisons.append("trophees")
    pts = float(((h.get("carriere") or {}).get("points")) or 0)
    s += min(10.0, pts / 120.0)
    fi = fidelite(h)
    if fi >= 6:
        s += min(10.0, (fi - 5) * 2.0)
    if fi >= 10:
        raisons.append("fidele")
    s += 15.0 * float(r_ventes or 0)
    s += 10.0 * float(r_suivis or 0)
    if (r_ventes or 0) >= 0.8:
        raisons.append("achete")
    if (r_suivis or 0) >= 0.8:
        raisons.append("suivi")
    return round(min(100.0, s), 1), raisons


def favoris_compte():
    """Le nombre de membres qui suivent chaque joueur (questionnaire du Radar ; aucune identite)."""
    c = Counter()
    try:
        import comptes
        import sqlite3
        racine = comptes.DOSSIER_COMPTES
        for cid in sorted(os.listdir(racine))[:5000]:
            p = os.path.join(racine, cid, "lockerroom.db")
            if not os.path.isfile(p):
                continue
            try:
                cx = sqlite3.connect("file:" + p + "?mode=ro", uri=True, timeout=2)
                try:
                    r = cx.execute("SELECT v FROM reglages WHERE k='deals_profil'").fetchone()
                finally:
                    cx.close()
                if r:
                    for x in set(str(y)[:40] for y in ((json.loads(r[0]) or {}).get("favoris") or [])):
                        c[_titre(x)] += 1
            except Exception:
                continue
    except Exception:
        pass
    return c


def _titre(n):
    return " ".join(w[:1].upper() + w[1:] for w in str(n or "").lower().split())


def cles(base=None, ventes_n=None, suivis=None, n=N_CLES):
    """[{nom, score, raisons}] : les joueurs cles, du plus fort au plus faible."""
    if base is None:
        try:
            import demande_legale
            base = (demande_legale.lire() or {}).get("joueurs") or {}
        except Exception:
            base = {}
    if ventes_n is None:
        try:
            import base_ventes
            ventes_n = base_ventes.ventes_par_joueur(180)
        except Exception:
            ventes_n = {}
    if suivis is None:
        suivis = favoris_compte()
    vn = {_titre(k): v for k, v in (ventes_n or {}).items()}
    sv = {_titre(k): v for k, v in (suivis or {}).items()}
    noms = {_titre(k) for k in base} | set(vn) | set(sv)
    rv, rs = _pct_rangs({k: vn.get(k, 0) for k in noms}), _pct_rangs({k: sv.get(k, 0) for k in noms})
    bt = {_titre(k): v for k, v in base.items()}
    out = []
    for nom in noms:
        h = (bt.get(nom) or {}).get("nhl") or {}
        s, r = score_cle(h, rv.get(nom, 0), rs.get(nom, 0))
        out.append({"nom": nom, "score": s, "raisons": r})
    try:
        import deals
        ved = {_titre(v) for v in deals.VEDETTES}
    except Exception:
        ved = set()
    for x in out:
        if x["nom"] in ved:
            x["score"] = max(x["score"], SCORE_CLE_MIN)
            x["raisons"].append("vedette")
    out = [x for x in out if x["score"] >= SCORE_CLE_MIN]
    out.sort(key=lambda x: -x["score"])
    return out[:n]


# -- 2. l'indice de marche ------------------------------------------------------------------------------------------------
def _tranche(titre):
    try:
        import cartes_match
        s = cartes_match._decoder_memo(titre).get("serie")
    except Exception:
        s = None
    if not s:
        return "-"
    return "1" if s == 1 else "10" if s <= 10 else "25" if s <= 25 else "99" if s <= 99 else "x"


def sorte(titre):
    """La sorte de carte (pour la normale) : le type (famille + note) et la tranche de tirage."""
    try:
        import types_cartes
        k = types_cartes.type_de(titre)
    except Exception:
        k = None
    return f"{k}|{_tranche(titre)}" if k else None


def _ord(le):
    try:
        return date.fromisoformat(str(le)[:10]).toordinal()
    except ValueError:
        return None


def series(ventes, noms):
    """[(joueur, titre, prix, le)] -> {joueur: {sorte: [(jour ordinal, prix)] tries}} pour les joueurs cles."""
    garde = set(noms)
    S = defaultdict(lambda: defaultdict(list))
    for j, titre, p, le in ventes:
        j = _titre(j)
        if j not in garde:
            continue
        try:
            p = float(p)
        except (TypeError, ValueError):
            continue
        d = _ord(le)
        k = sorte(titre)
        if p >= 1 and d and k:
            S[j][k].append((d, p))
    for j in S:
        for k in S[j]:
            S[j][k].sort()
    return S


def _fen(l, a, b):
    """Les prix de l (tries) dont le jour est dans ]a, b]."""
    return [p for d, p in l if a < d <= b]


def normale(sj, jour):
    """{sorte: mediane des prix sur ]jour - W - BASE, jour - W]} (assez de ventes seulement)."""
    out = {}
    for k, l in sj.items():
        b = _fen(l, jour - W - BASE, jour - W)
        if len(b) >= N_BASE_MIN:
            out[k] = statistics.median(b)
    return out


def indice_a(sj, jour, nor=None, a=None, b=None):
    """L'indice (mediane des prix / normale de leur sorte) des ventes de ]a, b] (defaut : les 14 jours finissant a jour)."""
    nor = normale(sj, jour) if nor is None else nor
    a = jour - W if a is None else a
    b = jour if b is None else b
    r = []
    for k, m in nor.items():
        r += [p / m for p in _fen(sj[k], a, b)]
    if len(r) < N_W_MIN:
        return None, len(r)
    return statistics.median(r), len(r)


# -- 3. la verification (chaque semaine) ----------------------------------------------------------------------------------
def wilson(k, n, z=1.96):
    if not n:
        return 0.0
    p = k / n
    d = 1 + z * z / n
    return (p + z * z / (2 * n) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d


def points_passes(S, fin=None, pas=7):
    """[(joueur, jour, indice, indice 46-74 jours apres)] : chaque semaine ou l'indice et la suite sont connus."""
    fin = fin or date.today().toordinal()
    out = []
    for j, sj in S.items():
        tous = [d for l in sj.values() for d, _ in l]
        if not tous:
            continue
        d0 = min(tous) + W + BASE
        for jour in range(d0, fin - H1 + 1, pas):
            nor = normale(sj, jour)
            if not nor:
                continue
            ix, _ = indice_a(sj, jour, nor)
            if ix is None:
                continue
            fx, _ = indice_a(sj, jour, nor, jour + H0, jour + H1)
            if fx is not None:
                out.append((j, jour, ix, fx))
    return out


def verifier(P):
    """Les seuils contre le hasard. -> {seuil, taux, n, base, base_n, gain_med, actif, essais}."""
    base_n = len(P)
    base_k = sum(1 for _, _, ix, fx in P if fx >= ix * REMONTE)
    base = base_k / base_n if base_n else None
    essais, best = [], None
    for s in SEUILS:
        l = [(ix, fx) for _, _, ix, fx in P if ix <= 1 - s]
        k = sum(1 for ix, fx in l if fx >= ix * REMONTE)
        e = {"seuil": s, "n": len(l), "taux": round(k / len(l), 3) if l else None, "borne": round(wilson(k, len(l)), 3),
             "gain_med": round(statistics.median([fx / ix - 1 for ix, fx in l]) * 100, 1) if l else None}
        essais.append(e)
        if len(l) >= N_TEST_MIN and base is not None and e["borne"] > base and (best is None or e["borne"] > best["borne"]):
            best = e
    out = {"base": round(base, 3) if base is not None else None, "base_n": base_n, "essais": essais, "actif": best is not None}
    if best:
        out.update(seuil=best["seuil"], taux=best["taux"], n=best["n"], gain_med=best["gain_med"])
    return out


# -- le calcul de la semaine ----------------------------------------------------------------------------------------------
def calculer(ventes=None, liste=None, aujourd=None):
    aujourd = aujourd or date.today()
    if liste is None:
        liste = cles()
    if ventes is None:
        import base_ventes
        ventes = base_ventes.ventes_titres(BASE + W + H1 + 365)
    noms = [x["nom"] for x in liste]
    S = series(ventes, noms)
    V = verifier(points_passes(S, aujourd.toordinal()))
    jour = aujourd.toordinal()
    etats = {}
    for x in liste:
        sj = S.get(x["nom"])
        if not sj:
            continue
        ix, n = indice_a(sj, jour)
        if ix is None:
            continue
        etats[x["nom"]] = {"indice": round(ix, 3), "n": n, "ecart_pct": round((ix - 1) * 100)}
    return {"le": datetime.now().isoformat(timespec="seconds"), "jour": aujourd.isoformat(), "verif": V,
            "cles": {x["nom"]: {"score": x["score"], "raisons": x["raisons"]} for x in liste}, "etats": etats}


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "marche_cles.json")


def lire():
    p = _chemin()
    try:
        mt = os.path.getmtime(p)
    except OSError:
        return {}
    if _ETAT["d"] is None or _ETAT["mt"] != mt:
        try:
            with open(p, encoding="utf-8") as f:
                _ETAT["d"] = json.load(f)
            _ETAT["mt"] = mt
        except (OSError, ValueError):
            return {}
    return _ETAT["d"]


def ecrire(d):
    with _verrou:
        tmp = _chemin() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(tmp, _chemin())


def passe():
    d = calculer()
    ecrire(d)
    return d


def passe_si_besoin():
    """Une fois par jour (les etats) ; la verification se refait a chaque passe (la boucle du serveur, chaque heure)."""
    try:
        if time.time() - os.path.getmtime(_chemin()) < 20 * 3600:
            return None
    except OSError:
        pass
    if _ETAT["en_cours"]:
        return None
    _ETAT["en_cours"] = True

    def tache():
        try:
            d = passe()
            v = d.get("verif") or {}
            print("Marche des joueurs cles : %d cles, %d etats, actif %s (seuil %s, %s vs hasard %s, n %s)" % (
                len(d.get("cles") or {}), len(d.get("etats") or {}), v.get("actif"), v.get("seuil"), v.get("taux"), v.get("base"), v.get("n")), flush=True)
        except Exception as e:
            print("Marche des joueurs cles : " + repr(e), flush=True)
        finally:
            _ETAT["en_cours"] = False
    threading.Thread(target=tache, daemon=True, name="marche-cles").start()
    return True


# -- les lectures ---------------------------------------------------------------------------------------------------------
def _yg(nom):
    try:
        import moment_yg
        e = moment_yg.etat(nom)
        return e and e.get("etat") in ("creux", "creux_fort")
    except Exception:
        return False


def bas(nom):
    """{ecart_pct, source} si le joueur cle est « marche bas » (verifie), sinon None. Public : l'ecart en %, jamais un prix."""
    d = lire()
    k = _titre(nom)
    if not k or k not in (d.get("cles") or {}):
        return None
    V = d.get("verif") or {}
    e = (d.get("etats") or {}).get(k)
    if V.get("actif") and e and e["indice"] <= 1 - V["seuil"]:
        return {"ecart_pct": e["ecart_pct"], "source": "marche"}
    if _yg(k):
        return {"ecart_pct": e["ecart_pct"] if e and e["ecart_pct"] < 0 else None, "source": "yg"}
    return None


def liste_bas():
    """[{nom, ecart_pct, score}] : les joueurs cles au marche bas, le plus bas d'abord."""
    d = lire()
    out = []
    for nom, c in (d.get("cles") or {}).items():
        b = bas(nom)
        if b:
            out.append({"nom": nom, "ecart_pct": b["ecart_pct"], "score": c.get("score")})
    out.sort(key=lambda x: (x["ecart_pct"] if x["ecart_pct"] is not None else 0, -(x["score"] or 0)))
    return out


def statut():
    d = lire()
    return {"le": d.get("le"), "cles": len(d.get("cles") or {}), "etats": len(d.get("etats") or {}), "verif": d.get("verif"),
            "bas": len(liste_bas()) if d else 0}
