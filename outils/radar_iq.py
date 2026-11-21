"""
SLABCOACH - la regle du Radar Pro, choisie sur le resultat qui compte (20 nov 2026).

Mathieu : « une carte pas trop pire, mais il est pogne avec : il faut etre sur que ces cartes soient assez liquides et qu'ils
les vendent ; des cartes assez desirees. Il faut un ecart notable avec quelqu'un qui choisit au hasard. »

  python3 outils/radar_iq.py [A_maintenant.json.gz du banc tests_site]

LE RESULTAT : un achat est REUSSI si la meme carte (meme compagnie, meme note) se revend dans la periode qui suit (elle est
liquide : l'acheteur n'est pas pogne avec) ET a au moins 90 % du prix paye (elle garde sa valeur). On mesure aussi le profit
apres les frais d'eBay (13,25 % + 0,40 $). Le point de comparaison : tous les achats de la meme gamme de prix, au hasard.

CE QUE LA REGLE SAIT AU MOMENT DE L'ACHAT (jamais le futur) :
  s      : la note SlabIQ (lettres fixees avant la coupe C0 du banc) ;
  liq    : le nombre de ventes de la meme carte dans les 60 jours d'avant (la liquidite passee) ;
  rabais : le prix paye contre la mediane ponderee par la recence (15 j) des ventes d'avant de la meme carte ;
  joueur : le nombre de ventes des cartes du joueur dans les 30 jours d'avant (sa demande).

LA METHODE (rien de choisi sur la periode de test) :
  1. APPRENTISSAGE : achats du 18 au 28 sept., resultat sur les ventes du 28 sept. au 19 oct. (tout avant la coupe C0) ;
     une grille de regles (s, liq, rabais, joueur) ; on garde la meilleure qui fait assez d'achats ;
  2. TEST, une seule fois : achats du 19 au 29 oct. (la fenetre du banc publie), resultat apres le 29 oct.
"""
import bisect
import collections
import datetime as dt
import itertools
import json
import os
import gzip
import json                      # 20 nov 2026 (Aikido) : le fichier du banc en JSON, plus de pickle
import random
import statistics as st
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
import liquidite  # noqa: E402
FRAIS, FIXE = 0.1325, 0.40
PRIX_MIN = 30.0


def _d(s):
    return dt.date.fromisoformat(s)


def preparer(A):
    par = collections.defaultdict(list)
    parj = collections.defaultdict(list)
    for a in A:
        par[(a["k"], a["gr"])].append((a["j"], a["p"]))
        parj[a["nom"]].append(a["j"])
    for v in par.values():
        v.sort()
    for v in parj.values():
        v.sort()
    return par, parj


def achats(A, par, parj, de, a_, w0, w1):
    """Les achats de la fenetre [de, a_) avec leurs signaux (d'avant) et leur resultat (ventes de [w0, w1))."""
    out = []
    for a in A:
        if not (de <= a["j"] < a_) or a["p"] < PRIX_MIN or a["ra"] in ("base", "lot_checklist"):
            continue
        L = par[(a["k"], a["gr"])]
        js = [x for x, _ in L]
        i = bisect.bisect_left(js, a["j"])
        hist = L[:i]
        l60 = (_d(a["j"]) - dt.timedelta(days=60)).isoformat()
        liq = i - bisect.bisect_left(js, l60)
        med = liquidite.mediane_recente(hist, a["j"], avant=True)      # la meme fonction que le site
        jj = parj[a["nom"]]
        l30 = (_d(a["j"]) - dt.timedelta(days=30)).isoformat()
        joueur = bisect.bisect_left(jj, a["j"]) - bisect.bisect_left(jj, l30)
        apres = [p for x, p in L[bisect.bisect_left(js, w0):bisect.bisect_left(js, w1)]]
        m_ = st.median(apres) if apres else None
        out.append({"s": a["s"], "liq": liq, "rabais": (a["p"] / med - 1) if med else None, "joueur": joueur, "p": a["p"],
                    "revendue": bool(apres), "garde": bool(m_ is not None and m_ >= 0.9 * a["p"]),
                    "profit": bool(m_ is not None and m_ * (1 - FRAIS) - FIXE >= a["p"]), "k": a["k"], "nom": a["nom"]})
    return out


def resume(L, runs=1000, seed=5):
    if not L:
        return {"n": 0}
    n = len(L)
    rev = sum(x["revendue"] for x in L)
    rng = random.Random(seed)
    bs = sorted(sum(x["revendue"] and x["garde"] for x in rng.choices(L, k=n)) / n for _ in range(runs))
    return {"n": n, "reussi": round(sum(x["revendue"] and x["garde"] for x in L) / n, 3),
            "reussi_ic95": [round(bs[int(.025 * runs)], 3), round(bs[int(.975 * runs)], 3)],
            "revendue": round(rev / n, 3), "garde_si_revendue": round(sum(x["garde"] for x in L if x["revendue"]) / rev, 3) if rev else None,
            "profit_apres_frais": round(sum(x["profit"] for x in L) / n, 3)}


def regle(s_min, liq_min, rabais_max, joueur_min):
    def f(x):
        return (x["s"] >= s_min and x["liq"] >= liq_min and x["joueur"] >= joueur_min
                and (rabais_max is None or (x["rabais"] is not None and x["rabais"] <= rabais_max)))
    return f


GRILLE = {"s_min": (0, 76, 82, 86, 90), "liq_min": (0, 1, 2, 3, 5, 8), "rabais_max": (None, 0.10, 0.0, -0.10, -0.20),
          "joueur_min": (0, 20, 50, 100)}


def lancer(chemin):
    with gzip.open(chemin, "rt", encoding="utf-8") as f:
        A = json.load(f)["A"]
    par, parj = preparer(A)
    T_app = achats(A, par, parj, "2026-09-18", "2026-09-28", "2026-09-28", "2026-10-19")
    T_test = achats(A, par, parj, "2026-10-19", "2026-10-29", "2026-10-29", "2026-11-20")
    T_nov = achats(A, par, parj, "2026-11-01", "2026-11-08", "2026-11-08", "2026-11-20")
    print(f"apprentissage : {len(T_app)} achats ; test : {len(T_test)} achats", flush=True)
    base_app = resume(T_app)
    n_min = max(150, int(0.02 * len(T_app)))            # une regle qui achete trop peu ne sert a personne
    essais = []
    for combo in itertools.product(*GRILLE.values()):
        f = regle(*combo)
        L = [x for x in T_app if f(x)]
        if len(L) < n_min:
            continue
        r = resume(L, runs=1)
        essais.append((r["reussi"], combo, r["n"]))
    essais.sort(reverse=True)
    print("apprentissage, hasard :", base_app)
    print("les 8 meilleures regles (apprentissage) :")
    for r, c, n in essais[:8]:
        print("  ", dict(zip(GRILLE, c)), "reussi", r, "n", n)
    meilleure = dict(zip(GRILLE, essais[0][1]))
    actuelle = {"s_min": 86, "liq_min": 0, "rabais_max": None, "joueur_min": 0}          # le Radar Pro d'avant le 20 nov
    site = {"s_min": liquidite.NOTE_MIN, "liq_min": liquidite.LIQ_MIN, "rabais_max": liquidite.RABAIS_MAX, "joueur_min": 0}
    out = {"apprentissage": {"hasard": base_app, "meilleure": meilleure}, "test": {}}
    for nom, R in (("hasard", None), ("radar_pro_actuel", actuelle), ("nouvelle_regle", meilleure), ("regle_du_site", site)):
        L = T_test if R is None else [x for x in T_test if regle(**R)(x)]
        out["test"][nom] = resume(L)
        print(f"TEST oct {nom:18s}", out["test"][nom], flush=True)
        L = T_nov if R is None else [x for x in T_nov if regle(**R)(x)]
        out.setdefault("test_nov", {})[nom] = resume(L)
        print(f"TEST nov {nom:18s}", out["test_nov"][nom], flush=True)
    json.dump(out, open("/tmp/claude-0/radar_iq.json", "w"), indent=1, ensure_ascii=False)
    return out


if __name__ == "__main__":
    lancer(sys.argv[1] if len(sys.argv) > 1 else "/tmp/claude-0/ts_std/A_maintenant.json.gz")
