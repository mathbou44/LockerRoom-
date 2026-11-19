"""
SLABCOACH - la prediction des series (admin) (19 nov 2026).

Mathieu : « on vend les cartes a 3 mois minimum differe : estimer si l'equipe est en place pour les series, car en series tout se
vend plus cher et plus vite ». Une seule pastille, legere : la chance de l'equipe d'aller en series, sa couleur, et le conseil.

1. La chance d'aller en series : le classement de la LNH (api-web.nhle.com, public, gratuit), une regression logistique sur
   l'ecart avec la ligne des series (8e/9e de l'association, en % de points, x racine des matchs joues), le differentiel de buts
   par match et la part de saison qui reste. Apprise sur 11 saisons (2013-14 a 2025-26 sans 2019-20 et 2020-21, 2 052 cas),
   chaque saison predite sans la voir : quand elle dit 60 %, c'est arrive 61 % du temps ; 77 % de bonnes reponses fin novembre,
   88 % a la mi-fevrier (Brier 0,126 contre 0,25 pour le hasard).
2. Ce que les series font aux prix (nos ventes 2026, meme carte meme grade, janv.-mars contre fin avril-mi-juin) : equipe en
   series +13 %, pas en series -15 % ; sortie au 1er tour -23 %, 2e tour +14 %, finale d'association et plus +39 % (ventes +76 %).
   Le pic : fin avril a fin mai. Une seule saison mesuree : a re-mesurer chaque printemps.
Admin et Platine seulement ; aucun prix n'est montre.
"""
import json
import math
import os
import threading
import time
import unicodedata
import urllib.request
from datetime import date, datetime

W = (0.060524784931197596, 3.677417086690473, 0.6325000279840607, -0.11016413158613811, -0.09446767493548824)
PRIME_SERIES, PRIME_HORS = 0.13, -0.15
SEUIL_MAI, SEUIL_MARS = 0.70, 0.35
FRAICHEUR_S = 12 * 3600
_ETAT = {"en_cours": False}
_MEM = {"t": 0.0, "d": None}


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "series.json")


def _lire():
    if _MEM["d"] is not None and time.time() - _MEM["t"] < 60:
        return _MEM["d"]
    try:
        with open(_chemin(), encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        d = {}
    _MEM.update(t=time.time(), d=d)
    return d


def _ecrire(d):
    tmp = _chemin() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, _chemin())
    _MEM.update(t=time.time(), d=d)


def _get(u):
    req = urllib.request.Request(u, headers={"User-Agent": "SlabCoach"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def norm(s):
    return " ".join(unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower().replace(".", " ").replace("-", " ").split())


def probabilite(ecart, mj, dg_par_match, reste_part):
    """La chance (0-1) d'aller en series. ecart : % de points moins la ligne des series ; mj : matchs joues."""
    x1, x2, x3 = ecart * math.sqrt(max(mj, 0)), dg_par_match, reste_part
    z = W[0] + W[1] * x1 + W[2] * x2 + W[3] * x3 + W[4] * x1 * x3
    return 1 / (1 + math.exp(-z))


def calculer(standings, aujourdhui=None):
    """{equipe: p} depuis le classement de la LNH (la reponse de /v1/standings/...)."""
    out = {}
    for conf in {x.get("conferenceAbbrev") for x in standings}:
        C = sorted([x for x in standings if x.get("conferenceAbbrev") == conf], key=lambda x: -float(x.get("pointPctg") or 0))
        if len(C) < 9:
            continue
        ligne = (float(C[7].get("pointPctg") or 0) + float(C[8].get("pointPctg") or 0)) / 2
        for x in C:
            mj = int(x.get("gamesPlayed") or 0)
            p = probabilite(float(x.get("pointPctg") or 0) - ligne, mj, float(x.get("goalDifferential") or 0) / max(mj, 1), (82 - mj) / 82)
            out[x["teamAbbrev"]["default"]] = {"p": round(p, 3), "mj": mj, "nom": (x.get("teamName") or {}).get("default")}
    return out


def _vivantes(saison):
    """Pendant les series : {equipe: 'vivante' | 'eliminee'} (le tableau des series de la LNH)."""
    try:
        d = _get(f"https://api-web.nhle.com/v1/playoff-series/carousel/{saison}/")
    except Exception:
        return {}
    st = {}
    for r in d.get("rounds") or []:
        for s in r.get("series") or []:
            a, b = s.get("topSeed") or {}, s.get("bottomSeed") or {}
            for x, y in ((a, b), (b, a)):
                if x.get("abbrev"):
                    st.setdefault(x["abbrev"], "vivante")
                    if int(y.get("wins") or 0) >= 4:
                        st[x["abbrev"]] = "eliminee"
    return st


def rafraichir():
    if _ETAT["en_cours"]:
        return False
    _ETAT["en_cours"] = True
    try:
        st = _get("https://api-web.nhle.com/v1/standings/now").get("standings") or []
        if not st:
            return False
        eq = calculer(st)
        mj = sorted(v["mj"] for v in eq.values())
        phase = "saison" if mj and mj[len(mj) // 2] >= 5 else "hors"
        saison = str(st[0].get("seasonId") or "")
        if mj and min(mj) >= 82 and date.today().month <= 6:
            phase = "series"
            viv = _vivantes(saison)
            for k, v in eq.items():
                v["p"] = 1.0 if viv.get(k) == "vivante" else 0.0
                v["etat"] = viv.get(k) or "hors"
        joueurs = {}
        for k in eq:
            try:
                r = _get(f"https://api-web.nhle.com/v1/roster/{k}/current")
                for g in ("forwards", "defensemen", "goalies"):
                    for p in r.get(g) or []:
                        joueurs[norm((p.get("firstName") or {}).get("default", "") + " " + (p.get("lastName") or {}).get("default", ""))] = k
            except Exception:
                continue
        _ecrire({"le": time.time(), "jour": date.today().isoformat(), "phase": phase, "saison": saison, "equipes": eq, "joueurs": joueurs})
        return True
    except Exception as e:
        print("Series : " + str(e), flush=True)
        return False
    finally:
        _ETAT["en_cours"] = False


def rafraichir_si_besoin():
    d = _lire()
    if d.get("equipes") and time.time() - d.get("le", 0) < FRAICHEUR_S:
        return False
    threading.Thread(target=rafraichir, daemon=True, name="series").start()
    return True


def conseil(p, phase="saison", etat=None):
    """(ton, cle) : vert = vendre en mai (le pic) ; rouge = vendre avant mars ; or = a suivre."""
    if phase == "series":
        return ("vert", "maintenant") if etat == "vivante" else ("rouge", "trop_tard")
    if p >= SEUIL_MAI:
        return "vert", "mai"
    if p <= SEUIL_MARS:
        return "rouge", "mars"
    return "or", "suivre"


def pour_joueur(nom):
    """La pastille d'un joueur de la LNH : {eq, p (0-100), effet (%), ton, conseil} ; None hors saison ou joueur inconnu."""
    d = _lire()
    if d.get("phase") not in ("saison", "series"):
        return None
    eq = (d.get("joueurs") or {}).get(norm(nom))
    v = (d.get("equipes") or {}).get(eq or "")
    if not v:
        return None
    p = float(v.get("p") or 0)
    ton, cle = conseil(p, d.get("phase"), v.get("etat"))
    return {"eq": eq, "p": round(p * 100), "effet": round(100 * (p * PRIME_SERIES + (1 - p) * PRIME_HORS)), "ton": ton, "conseil": cle}
