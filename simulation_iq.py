"""
SLABCOACH - deux collectionneurs, le meme budget : avec et sans SlabIQ (16 nov 2026).

Mathieu : « quelqu'un arrive dans le hobby : "je veux collectionner Connor Bedard". Il achete des cartes au hasard, des encans
qu'il gagne, sans savoir quoi ni quand acheter. L'autre a SlabIQ : quoi acheter, quand l'acheter, les drapeaux. Meme budget,
sur un an ou deux : combien de cartes chacun a, ce qu'il a paye, ce qu'elles valent a la fin. Plusieurs joueurs, plusieurs
equipes, en faisant varier les variables ; le montrer sur le site. »

Les donnees : la banque Young Guns (les vraies ventes de la YG de base, raw et PSA 10, de 160 joueurs, mai 2025 - nov 2026).
Chaque vente est une occasion d'achat a son prix reel (quelqu'un l'a vraiment payee). Les deux collectionneurs recoivent le
meme budget chaque mois et paient les memes frais d'achat (taxes et port).
  - A (sans SlabIQ) : « aleatoire » : chaque mois, il prend des ventes au hasard parmi celles du mois, jusqu'au bout de son
    budget ; « FOMO » : il achete surtout quand le prix monte (les jours ou le marche du joueur est en hausse).
  - B (avec SlabIQ) : il n'achete jamais pendant une flambee, une retombee ou la vague de sortie d'un produit (moment_yg) ;
    il achete les ventes sous le prix median recent de la meme carte (rabais >= seuil), en priorite dans un creux. Ce qu'il ne
    depense pas reste dans son budget ; apres 3 mois sans occasion, il prend les meilleures du mois (jamais en flambee).
SlabIQ ne voit jamais le futur : chaque decision n'utilise que les ventes d'AVANT le jour de l'achat.
A la fin : la valeur de chaque carte = la mediane des ventes de la meme carte (meme gradation) des 30 derniers jours ; l'argent
pas depense compte a sa valeur. -> le total de chacun, le gain en %, le nombre de cartes ; sur des centaines de scenarios
(joueurs, equipes, paniers de joueurs, dates de depart, durees, budgets, seuils), la part ou B bat A.
Limites (dites a l'ecran) : des Young Guns seulement ; 18 mois de donnees ; les regles de SlabIQ ont ete choisies sur ces
memes mois (validees sur des mois jamais vus a l'epoque) ; le test en direct (moment_yg, journal) continue chaque semaine.
"""
import json
import math
import os
import random
import statistics
import time
from collections import defaultdict
from datetime import date, datetime

import numpy as np

FRAIS_ACHAT = 0.10          # taxes et frais d'achat (meme pour les deux)
PORT = 5.0                  # port par carte (USD)
FIN_JOURS = 30              # la valeur finale : mediane des ventes des 30 derniers jours
HORIZONS = (180, 365, 540)
BUDGETS = (50, 100, 250)
SEUILS = (0.10, 0.15, 0.25)
NAIFS = ("aleatoire", "fomo")
RESERVE_MOIS = 2           # B ne garde jamais plus de 2 mois de budget de cote


def _cout(p):
    return p * (1 + FRAIS_ACHAT) + PORT


class Joueur:
    """Les ventes d'un joueur, ses etats SlabIQ jour par jour (le passe seulement) et ses medianes recentes."""

    def __init__(self, nom, vj, ix, R, sortie=None):
        import moment_yg as m
        self.nom = nom
        vj = {g: nettoyer(vj.get(g) or []) for g in ("raw", "psa10")}
        self.ventes = sorted([(o, p, g) for g in ("raw", "psa10") for o, p in vj[g]])
        self.par_g = {g: (np.array([o for o, _ in vj[g]]), np.array([p for _, p in vj[g]])) for g in ("raw", "psa10")}
        self.etat = {}
        if ix:
            for d in range(ix["d0"] + 60, max(ix["P"]) + 1):
                f = m.facteurs(ix, d)
                age = d - sortie if sortie else None
                self.etat[d] = m.etat_de(f, R, age)[0]

    def mediane(self, g, d, jours=14, avant=True):
        o, p = self.par_g[g]
        if not len(o):
            return None
        a, b = np.searchsorted(o, d - jours, "left"), np.searchsorted(o, d, "left" if avant else "right")
        return float(np.median(p[a:b])) if b - a >= 3 else None

    def valeur_fin(self, g, fin):
        v = self.mediane(g, fin, FIN_JOURS, avant=False)
        return v if v is not None else self.mediane(g, fin, 90, avant=False)


def nettoyer(l, fen=30, bas=0.45, haut=2.2):
    """Les ventes qui ne sont pas la carte (un checklist #500 « Bedard / Carlsson » a 5 $, un Tribute, une reimpression,
    un lot) sortent : une vente sous 45 % ou au-dessus de 220 % de la mediane de la meme carte (+/- 30 jours, sans elle).
    C'est du NETTOYAGE (est-ce la meme carte ?), pas une decision d'achat : les deux collectionneurs ont les memes occasions."""
    if len(l) < 5:
        return list(l)
    o = np.array([x[0] for x in l])
    p = np.array([x[1] for x in l])
    out = []
    for k in range(len(l)):
        a, b = np.searchsorted(o, o[k] - fen, "left"), np.searchsorted(o, o[k] + fen, "right")
        autres = np.concatenate([p[a:k], p[k + 1:b]])
        if len(autres) >= 4:
            med = float(np.median(autres))
            if not (bas * med <= p[k] <= haut * med):
                continue
        out.append(l[k])
    return out


def _mois(debut, horizon):
    return [(debut + k * 30, min(debut + (k + 1) * 30, debut + horizon)) for k in range(horizon // 30)]


def simuler(joueurs, debut, horizon, budget, naif, seuil, graine=0):
    """Un scenario : la liste de Joueur, le jour de depart, la duree, le budget mensuel (USD), le type de A, le seuil de B.
    -> {A: {...}, B: {...}} (paye, cartes, valeur, cash, total, gain_pct)."""
    rnd = random.Random(graine)
    fin = debut + horizon
    porte = {"A": [], "B": []}
    cash = {"A": 0.0, "B": 0.0}
    paye = {"A": 0.0, "B": 0.0}
    sans = 0
    for a, b in _mois(debut, horizon):
        cash["A"] += budget
        cash["B"] += budget
        occ = [(o, p, g, j) for j in joueurs for (o, p, g) in j.ventes if a <= o < b]
        if not occ:
            continue
        # A : au hasard (ou FOMO : les jours de hausse d'abord)
        lA = occ[:]
        rnd.shuffle(lA)
        if naif == "fomo":
            lA.sort(key=lambda x: 0 if x[3].etat.get(x[0]) in ("flambee", "retombee", "sortie") else 1)
        for o, p, g, j in lA:
            c = _cout(p)
            if c <= cash["A"]:
                cash["A"] -= c
                paye["A"] += c
                porte["A"].append((j, g))
        # B : SlabIQ, le passe seulement
        cands = []
        for o, p, g, j in occ:
            e = j.etat.get(o, "inconnu")
            if e in ("flambee", "retombee", "sortie"):
                continue
            med = j.mediane(g, o)
            if not med:
                continue
            r = 1 - p / med
            cands.append((0 if e in ("creux", "creux_fort") else 1, -r, o, p, g, j, r))
        cands.sort(key=lambda x: (x[0], x[1]))
        achete = False
        for prio, _, o, p, g, j, r in cands:
            if r >= seuil or sans >= 3:
                c = _cout(p)
                if c <= cash["B"]:
                    cash["B"] -= c
                    paye["B"] += c
                    porte["B"].append((j, g))
                    achete = True
        # il INVESTIT son budget : jamais plus de 2 mois d'argent de cote ; le surplus va aux meilleures occasions du mois
        # (les moins cheres par rapport a leur mediane, jamais en flambee) -> on compare des collectionneurs, pas de l'epargne
        if cash["B"] > RESERVE_MOIS * budget:
            for prio, _, o, p, g, j, r in cands:
                if cash["B"] <= RESERVE_MOIS * budget:
                    break
                c = _cout(p)
                if c <= cash["B"]:
                    cash["B"] -= c
                    paye["B"] += c
                    porte["B"].append((j, g))
                    achete = True
        sans = 0 if achete else sans + 1
    out = {}
    for k in ("A", "B"):
        val = 0.0
        for j, g in porte[k]:
            v = j.valeur_fin(g, fin)
            val += v if v is not None else 0.0
        tot = val + cash[k]
        mise = budget * (horizon // 30)
        out[k] = {"paye": round(paye[k], 2), "cartes": len(porte[k]), "valeur": round(val, 2), "cash": round(cash[k], 2),
                  "total": round(tot, 2), "gain_pct": round(100 * (tot / mise - 1), 1) if mise else 0.0,
                  "rendement_pct": round(100 * (val / paye[k] - 1), 1) if paye[k] else None}
    return out


def charger(lignes=None):
    """Les joueurs de la banque (assez de ventes), avec leurs etats SlabIQ."""
    import moment_yg as m
    if lignes is None:
        lignes = m._lignes_banque()
    V = m.ventes_par_joueur(lignes)
    try:
        R = m.regles_en_place()[0] or m.REGLES_V2
    except Exception:
        R = m.REGLES_V2
    titres = defaultdict(list)
    for j, t, _p, _le in lignes:
        if len(titres[j]) < 200:
            titres[j].append(t)
    J = {}
    for nom, vj in V.items():
        ix = m.indice(vj)
        if not ix:
            continue
        J[nom] = Joueur(nom, vj, ix, R, m.sortie_yg(titres.get(nom) or []))
    return J


def equipes_de(noms):
    """{equipe: [joueurs]} d'apres la fiche LNH (demande_legale) ; les equipes de 3 joueurs et plus."""
    try:
        import demande_legale as dl
        base = (dl.lire() or {}).get("joueurs") or {}
    except Exception:
        base = {}
    E = defaultdict(list)
    for n in noms:
        eq = ((base.get(n) or {}).get("nhl") or {}).get("equipe")
        if eq:
            E[eq].append(n)
    return {k: v for k, v in E.items() if len(v) >= 3}


def lancer(J=None, max_scenarios=6000, graine=7):
    """Tous les scenarios : chaque joueur seul, chaque equipe, des paniers de 5 joueurs ; departs aux 60 jours ; 3 durees,
    3 budgets, 2 sortes de A, 3 seuils de B. -> le resume (et quelques exemples), garde dans simulation_iq.json."""
    t0 = time.time()
    J = J if J is not None else charger()
    if not J:
        return {"ok": False, "erreur": "pas de donnees"}
    rnd = random.Random(graine)
    d_min = min(min(j.etat) for j in J.values() if j.etat)
    d_max = max(max(j.etat) for j in J.values() if j.etat)
    coll = [("joueur", n, [J[n]]) for n in J]
    for eq, l in equipes_de(list(J)).items():
        coll.append(("equipe", eq, [J[n] for n in l]))
    noms = sorted(J)
    for k in range(40):
        l = rnd.sample(noms, min(5, len(noms)))
        coll.append(("panier", " · ".join(l), [J[n] for n in l]))
    sc = []
    for typ, nom, js in coll:
        for h in HORIZONS:
            for debut in range(d_min, d_max - h + 1, 60):
                for bud in BUDGETS:
                    for naif in NAIFS:
                        for s in SEUILS:
                            sc.append((typ, nom, js, debut, h, bud, naif, s))
    rnd.shuffle(sc)
    sc = sc[:max_scenarios]
    res = []
    for k, (typ, nom, js, debut, h, bud, naif, s) in enumerate(sc):
        r = simuler(js, debut, h, bud, naif, s, graine=k)
        if r["A"]["cartes"] == 0 and r["B"]["cartes"] == 0:
            continue
        res.append({"type": typ, "nom": nom, "debut": date.fromordinal(debut).isoformat(), "jours": h, "budget": bud, "naif": naif,
                    "seuil": s, "A": r["A"], "B": r["B"]})
    d = resumer(res)
    d.update(le=datetime.now().isoformat(timespec="seconds"), duree_s=round(time.time() - t0, 1), joueurs=len(J),
             periode=[date.fromordinal(d_min).isoformat(), date.fromordinal(d_max).isoformat()])
    d["exemples"] = exemples(res)
    ecrire(d)
    return d


def _stats(l):
    if not l:
        return {"n": 0}
    gagne = sum(1 for x in l if x["B"]["total"] > x["A"]["total"])
    ecart = [x["B"]["gain_pct"] - x["A"]["gain_pct"] for x in l]
    return {"n": len(l), "b_gagne": round(gagne / len(l), 3), "ecart_median": round(statistics.median(ecart), 1),
            "gain_A": round(statistics.median([x["A"]["gain_pct"] for x in l]), 1),
            "gain_B": round(statistics.median([x["B"]["gain_pct"] for x in l]), 1),
            "rend_A": round(statistics.median([x["A"]["rendement_pct"] for x in l if x["A"]["rendement_pct"] is not None] or [0]), 1),
            "rend_B": round(statistics.median([x["B"]["rendement_pct"] for x in l if x["B"]["rendement_pct"] is not None] or [0]), 1),
            "cash_B": round(statistics.median([x["B"]["cash"] / max(1, x["budget"] * (x["jours"] // 30)) * 100 for x in l]), 1),
            "cartes_A": round(statistics.mean([x["A"]["cartes"] for x in l]), 1),
            "cartes_B": round(statistics.mean([x["B"]["cartes"] for x in l]), 1)}


def resumer(res):
    out = {"ok": True, "scenarios": len(res), "total": _stats(res)}
    for cle, f in (("par_type", "type"), ("par_duree", "jours"), ("par_budget", "budget"), ("par_naif", "naif"), ("par_seuil", "seuil")):
        g = defaultdict(list)
        for x in res:
            g[str(x[f])].append(x)
        out[cle] = {k: _stats(v) for k, v in sorted(g.items())}
    pj = defaultdict(list)
    for x in res:
        if x["type"] == "joueur":
            pj[x["nom"]].append(x)
    out["par_joueur"] = {k: _stats(v) for k, v in sorted(pj.items(), key=lambda kv: -len(kv[1]))}
    pe = defaultdict(list)
    for x in res:
        if x["type"] == "equipe":
            pe[x["nom"]].append(x)
    out["par_equipe"] = {k: _stats(v) for k, v in sorted(pe.items())}
    return out


def exemples(res):
    """Quelques histoires a raconter (1 an, 100 $ par mois, A au hasard, seuil 15 %) : les joueurs connus d'abord."""
    vedettes = ("Connor Bedard", "Macklin Celebrini", "Ivan Demidov", "Lane Hutson", "Matvei Michkov", "Leo Carlsson", "Adam Fantilli")
    l = [x for x in res if x["jours"] == 365 and x["budget"] == 100 and x["naif"] == "aleatoire" and x["seuil"] == 0.15]
    l.sort(key=lambda x: (x["nom"] not in vedettes, x["type"] != "joueur", x["nom"], x["debut"]))
    vus, out = set(), []
    for x in l:
        if x["nom"] in vus:
            continue
        vus.add(x["nom"])
        out.append(x)
        if len(out) >= 12:
            break
    return out


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "simulation_iq.json")


def lire():
    try:
        with open(_chemin(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def ecrire(d):
    tmp = _chemin() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, _chemin())


_ETAT = {"en_cours": False}


def passe_si_besoin():
    """Une fois par semaine (la boucle du serveur), en fond : les ventes de la banque grandissent chaque jour."""
    import threading
    try:
        if time.time() - os.path.getmtime(_chemin()) < 6.5 * 86400:
            return None
    except OSError:
        pass
    if _ETAT["en_cours"]:
        return None
    _ETAT["en_cours"] = True

    def tache():
        try:
            d = lancer(max_scenarios=8000)
            print("Simulation SlabIQ : %s scenarios, SlabIQ gagne %s" % (d.get("scenarios"), (d.get("total") or {}).get("b_gagne")), flush=True)
        except Exception as e:
            print("Simulation SlabIQ : " + repr(e), flush=True)
        finally:
            _ETAT["en_cours"] = False
    threading.Thread(target=tache, daemon=True, name="simulation-iq").start()
    return True
