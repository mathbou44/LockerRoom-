"""
SLABCOACH - le test SlabIQ du BASEBALL, la meme methode que le hockey (outils/tests_site.py) (20 nov 2026).

Mathieu : « le fichier baseball est telecharge ; l'analyse ultra precise pour arriver au meme resultat final que la LNH ».

  python3 outils/tests_site_bb.py [ventes_baseball.tsv.gz]

La meme methode que le hockey, rien d'ajuste a la main :
  1. les ventes de baseball (Entrainer SlabIQ -> Ventes Baseball), dedoublonnees (titre, prix, jour) ; une vente sous 3 $ ecartee ;
  2. deux dates : C0 (65 % des ventes) et C (80 %). Tout ce que SlabIQ sait (la cote marche des joueurs, les corrections) vient des
     ventes d'AVANT C0 ; tout ce qui est mesure vient de ventes qu'il n'a jamais vues ;
  3. la note suit l'app (bareme_bb.score : la sorte x la cote du joueur ; la cote d'un joueur hors de la liste du hobby = la cote
     marche de cote_marche : 20 ventes et plus -> B+, 8 et plus -> C+, sinon inconnu) ;
  4. « avant » = le bareme tel quel ; « maintenant » = + les corrections du marche apprises avant C0 (validation_iq : ecart de
     2 crans et plus, stable sur les deux moities, 25 ventes et plus ; jamais sur une legende A+ / A du hobby) ;
  5. on mesure, comme au hockey : l'accord avec le marche (ventes d'apres C0), les reventes par lettre (cartes vues avant C,
     revendues apres), le Radar Pro (achats entre C0 et C, revendus apres C a au moins 90 % du prix), la simulation et le defi.
     Le baseball n'a que quelques semaines de ventes denses : la simulation et le defi se font par SEMAINE (le hockey : par mois).
Le joueur d'une vente : la liste du hobby (bareme_bb), sinon le joueur cherche (colonne q) s'il est dans le titre.
Resultats : $LR_TESTS_TRAV_BB (defaut /tmp/claude-0/ts_bb)/resultats_bb.json. Rien n'est ecrit sur le site.
"""
import collections
import datetime as dt
import gzip
import json
import os
import random
import re
import statistics as st
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
TRAV = os.environ.get("LR_TESTS_TRAV_BB") or "/tmp/claude-0/ts_bb"
G = re.compile(r"\b(psa|bgs|sgc|cgc|tag|ksa|hga|beckett|bccg|csg|gma|isa|ags|mnt)\s*-?\s*(?:gem\s*(?:mint|mt)?\s*|mint\s*|pristine\s*)?(\d+(?:\.\d)?)\b", re.I)
SUFFIXES = {"baseball", "card", "cards", "bowman", "chrome", "1st", "auto", "autograph", "psa", "10", "9", "refractor", "rookie", "rc",
            "topps", "classic", "greats", "prospect", "prospects", "sapphire", "update", "heritage", "finest", "gold", "superfractor"}
PROTEGES = ("A+", "A")                       # les legendes du hobby : la valeur est intrinseque (comme l'expert au hockey)


def _n(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", s.replace(".", "").replace("'", "")).split())


def nom_de_q(q):
    mots = [m for m in _n(q).split() if m not in SUFFIXES]
    return " ".join(mots)


def joueur(titre, q):
    import bareme_bb as bb
    k = bb.joueur_connu(titre)
    if k:
        return k
    n = nom_de_q(q)
    if len(n.split()) >= 2 and all((" " + w + " ") in (" " + _n(titre) + " ") for w in n.replace(" jr", "").split()):
        return " ".join(w.capitalize() for w in n.split())
    return None


# ---------------------------------------------------------------- etape 1 : les ventes
def charger(chemin):
    import sports
    vus, out, ecartees = set(), [], collections.Counter()
    with gzip.open(chemin, "rt", encoding="utf-8") as f:
        next(f)
        for l in f:
            p = l.rstrip("\n").split("\t")
            if len(p) < 4 or not p[2]:
                continue
            try:
                pr = float(p[1])
            except ValueError:
                continue
            r = (p[0], pr, p[2][:10])
            if r in vus:
                ecartees["doublon"] += 1
                continue
            vus.add(r)
            if pr < 3:
                ecartees["sous_3"] += 1
                continue
            sp = sports.sport_de(p[0])
            if sp not in ("baseball", None, "autre") and not joueur(p[0], p[3]):
                ecartees["autre_sport"] += 1
                continue
            nom = joueur(p[0], p[3])
            if not nom:
                ecartees["sans_joueur"] += 1
                continue
            out.append((p[0], pr, p[2][:10], nom))
    return out, ecartees


# ---------------------------------------------------------------- etape 2 : les lettres (comme bareme_bb.score)
def cote_marche(rows, avant):
    """Le nombre de ventes de chaque joueur AVANT la coupe (ce que cote_marche mesure chez SoldComps)."""
    return collections.Counter(nom for t, p, j, nom in rows if j < avant)


def annoter(rows, n_marche, corrections=None):
    import bareme_bb as bb
    import validation_iq as v
    corrections = corrections or {}
    memo, out = {}, []
    for t, p, j, nom in rows:
        so, ra = bb.sorte(t)
        if ra == "lot_checklist":
            continue
        if nom not in memo:
            if nom in bb.JOUEURS_BB:
                nj, lj, src = bb.NOTE[bb.JOUEURS_BB[nom]], bb.JOUEURS_BB[nom], "hobby"
            elif n_marche.get(nom, 0) >= 20:
                nj, lj, src = 76.0, "B+", "marche"
            elif n_marche.get(nom, 0) >= 8:
                nj, lj, src = 61.0, "C+", "marche"
            else:
                nj, lj, src = float(bb.JOUEUR_INCONNU), "D", "inconnu"
            if nom in corrections:
                lj, nj, src = corrections[nom], float(bb.NOTE[corrections[nom]]), "auto"
            memo[nom] = (nj, lj, src)
        nj, lj, src = memo[nom]
        ns = bb.NOTE[so]
        if ra in ("avant_guerre", "rc_vintage_temple", "vintage_temple", "un_sur_un", "erreur_celebre", "icone"):
            s_ = max(ns, nj)
        else:
            lo, hi = min(ns, nj), max(ns, nj)
            s_ = lo + 0.25 * (hi - lo)
        g = G.search(t)
        out.append(dict(t=t[:120], p=p, j=j, so=so, ns=ns, ra=ra, nom=nom, lj=lj, nj=nj, src=src, connu=src != "inconnu",
                        k=v.cle_carte(t), gr=float(g.group(2)) if g else 0.0, s=s_, fin=bb.lettre(s_)))
    return out


def mesurer(A):
    """La mesure de validation_iq (accord avec le marche, lettres, inversions), sur des ventes deja annotees."""
    import validation_iq as v
    avant = v._annoter
    v._annoter = lambda rows: [dict(x) for x in rows]
    try:
        return v.mesurer(A)
    finally:
        v._annoter = avant


def decider(m):
    """Les corrections automatiques des joueurs, avec les seuils du hockey (validation_iq.decider)."""
    import bareme_bb as bb
    import validation_iq as v
    auto = {}
    for x in m.get("joueurs") or []:
        if not x["crans"] or bb.JOUEURS_BB.get(x["nom"]) in PROTEGES:
            continue
        if abs(x["crans"]) >= 2 and x["stable"] and x["n"] >= v.N_JOUEUR_AUTO:
            auto[x["nom"]] = x["marche"]
    return auto


# ---------------------------------------------------------------- etape 3 : les mesures (comme le hockey, par semaine)
def _semaines(debut, fin):
    d = dt.date.fromisoformat(debut)
    d -= dt.timedelta(days=d.weekday())
    P = []
    while d.isoformat() < fin:
        n_ = d + dt.timedelta(days=7)
        P.append((d.isoformat(), min(n_.isoformat(), fin)))
        d = n_
    return P


def mesures(A, C0, C, R):
    import numpy as np
    par = collections.defaultdict(list)
    for a in A:
        par[(a["k"], a["gr"])].append((a["j"], a["p"]))
    lettre_de, vues = {}, set()
    for a in A:
        if a["j"] < C:
            vues.add((a["k"], a["gr"]))
            lettre_de[(a["k"], a["gr"])] = a["fin"]
    apres = collections.Counter((a["k"], a["gr"]) for a in A if a["j"] >= C)
    parL = collections.defaultdict(list)
    for k in vues:
        parL[lettre_de[k]].append(apres.get(k, 0))
    lettres = {L: dict(cartes=len(v), reventes=round(sum(v) / len(v), 3)) for L, v in parL.items() if len(v) >= 200}

    def pro(seuil, pmin):
        n = ok = 0
        for a in A:
            if not (C0 <= a["j"] < C) or a["p"] < max(10, pmin) or a["s"] < seuil or a["ra"] in ("base", "lot_checklist", "junk_wax"):
                continue
            L = [p for j, p in par[(a["k"], a["gr"])] if j >= C]
            if not L:
                continue
            n += 1
            ok += st.median(L) >= 0.9 * a["p"]
        return dict(n=n, garde=round(ok / n, 3) if n else None)
    pro_now, pro_avant = pro(R["fixe"], R["prix_min"]), pro(65, 10)
    # la simulation : 400 collectionneurs, 125 $ par semaine (500 $ par mois), cartes de prix_min a 150 $, au hasard ou avec SlabIQ
    fin = {k: st.median([p for j, p in v if j >= C]) for k, v in par.items() if any(j >= C for j, p in v)}
    deb = min(a["j"] for a in A if a["j"] >= "2026-09-01")
    ventes = [(a["j"], (a["k"], a["gr"]), a["p"], a["s"], a["nom"]) for a in A if deb <= a["j"] < C]
    P = _semaines(deb, C)
    pmin_s = R["prix_min"]

    def courbes(regle, runs=400, seed=3):
        pools = {pp: [(k, p, s, j, nom) for j, k, p, s, nom in ventes if pp[0] <= j < pp[1] and pmin_s <= p <= 150 and k in fin and regle(s)] for pp in P}
        rng = random.Random(seed)
        fins = []
        for _ in range(runs):
            tenus, deja, parj, inv = [], set(), collections.Counter(), 0
            for pp in P:
                L = pools[pp][:]
                rng.shuffle(L)
                reste = 125
                for k, p, s, j, nom in L:
                    if k in deja or p > reste or parj[nom] >= 4:
                        continue
                    deja.add(k); parj[nom] += 1; tenus.append(k); reste -= p; inv += p
                    if reste < pmin_s:
                        break
            fins.append((inv, sum(fin[k] for k in tenus)))
        return fins
    fs, fa = courbes(lambda s: True), courbes(lambda s: s >= R["fixe"])
    a_ = np.array([v / i for i, v in fs if i]); b_ = np.array([v / i for i, v in fa if i])
    ea = np.array([v - i for i, v in fs]); eb = np.array([v - i for i, v in fa])
    m_ = min(len(a_), len(b_))
    sim = dict(semaines=len(P), du=deb, au=C, r_sans=round(float(np.median(a_)) - 1, 4) if len(a_) else None,
               r_avec=round(float(np.median(b_)) - 1, 4) if len(b_) else None, bat=round(float(np.mean(b_[:m_] > a_[:m_])), 3) if m_ else None,
               ecart=round(float(np.median(eb - ea))), investi_avec=round(float(np.median([i for i, v in fa]))), prix=[pmin_s, 150], seuil=R["fixe"])
    return dict(lettres=lettres, pro=pro_now, pro_avant=pro_avant, sim=sim), fin, par


PROD = [("bowman chrome", "Bowman Chrome"), ("bowman draft", "Bowman Draft"), ("bowman", "Bowman"), ("topps chrome", "Topps Chrome"),
        ("heritage", "Topps Heritage"), ("stadium club", "Stadium Club"), ("ginter", "Allen & Ginter"), ("finest", "Finest"),
        ("update", "Topps Update"), ("topps now", "Topps Now"), ("prizm", "Panini Prizm"), ("donruss", "Donruss"), ("fleer", "Fleer"),
        ("upper deck", "Upper Deck"), ("goudey", "Goudey"), ("t206", "T206"), ("topps", "Topps")]


def _etiquette(t, ra, nom, gr):
    tl = t.lower()
    an = re.search(r"\b(19\d\d|20\d\d)\b", tl)
    pr = next((n for r, n in PROD if r in tl), "")
    num = re.search(r"/\s?(\d{1,4})\b", tl)
    typ = ra.replace("_", " ")
    g = f"PSA {int(gr) if gr == int(gr) else gr}" if gr else ""
    return {"j": nom, "t": " · ".join(x for x in ((an.group(1) if an else "") + (" " + pr if pr else ""), typ + (f" /{num.group(1)}" if num else ""), g) if x.strip())}


def defi(A, fin, C):
    """Le defi : 8 manches, 8 vraies cartes vendues dans la meme tranche de prix la meme semaine, on en garde 2 ; SlabIQ ses 2 meilleures."""
    import numpy as np
    import bareme_bb as bb
    HORS = {"Shohei Ohtani", "Mike Trout", "Aaron Judge"}
    deb = min(a["j"] for a in A if a["j"] >= "2026-09-01")
    SEM = [p[0] for p in _semaines(deb, C)]
    BANDES = ((10, 25), (25, 50), (50, 100), (100, 150))
    sem_de = lambda j: max([s for s in SEM if s <= j] or [None])
    cell = collections.defaultdict(dict)
    for a in A:
        k = (a["k"], a["gr"])
        if deb <= a["j"] < C and 10 <= a["p"] <= 150 and k in fin:
            s = sem_de(a["j"])
            b = next(i for i, (x, y) in enumerate(BANDES) if x <= a["p"] < y or (i == 3 and a["p"] <= 150))
            if k not in cell[(s, b)]:
                cell[(s, b)][k] = (a["p"], a["s"], a["nom"], a["ra"], a["gr"], a["t"], a["src"])
    rng = random.Random(12)
    POOL = {}
    for (s, b), dd in cell.items():
        L = list(dd.items())
        rng.shuffle(L)
        vus, keep = set(), []
        for k, (p, sc, nom, ra, gr, t, src_) in L:
            if nom in vus or nom in HORS or src_ == "inconnu":
                continue
            vus.add(nom)
            keep.append({**_etiquette(t, ra, nom, gr), "s": round(sc), "L": bb.lettre(sc), "ok": int(fin[k] >= 0.9 * p)})
            if len(keep) >= 36:
                break
        if len(keep) >= 8:
            POOL[f"{s}|{b}"] = keep
    sems = sorted({k.split("|")[0] for k in POOL})
    if not sems:
        return {"pool": {}, "stats": None, "semaines": []}

    def partie(r):
        ms = [sems[round(i * (len(sems) - 1) / 7)] for i in range(8)]
        I = H = 0
        for m in ms:
            bs = [b for b in range(4) if f"{m}|{b}" in POOL]
            Cc = r.sample(POOL[f"{m}|{r.choice(bs)}"], 8)
            I += sum(c["ok"] for c in sorted(Cc, key=lambda c: -c["s"])[:2])
            H += sum(c["ok"] for c in r.sample(Cc, 2))
        return I, H
    r = random.Random(1)
    Rr = np.array([partie(r) for _ in range(20000)])
    return {"pool": POOL, "stats": dict(gagne=round(float(np.mean(Rr[:, 0] > Rr[:, 1])), 3), egal=round(float(np.mean(Rr[:, 0] == Rr[:, 1])), 3),
                                        perd=round(float(np.mean(Rr[:, 0] < Rr[:, 1])), 3)), "semaines": sems}


# ---------------------------------------------------------------- tout
def lancer(chemin):
    import tests_site
    os.makedirs(TRAV, exist_ok=True)
    rows, ecart = charger(chemin)
    js = sorted(r[2] for r in rows)
    C0, C = js[int(len(js) * .65)], js[int(len(js) * .80)]
    # 20 nov 2026 : le baseball n'a que quelques semaines de ventes denses (le blitz de novembre) : a 65 % / 80 % des ventes, il ne
    # reste que 2 jours de reventes. LR_BB_COUPES=AAAA-MM-JJ,AAAA-MM-JJ fixe les deux dates d'avance (jamais choisies apres coup)
    if os.environ.get("LR_BB_COUPES"):
        C0, C = os.environ["LR_BB_COUPES"].split(",")[:2]
    print(f"{len(rows)} ventes de baseball, {js[0]} -> {js[-1]} ; ecartees {dict(ecart)} ; lettres fixees avant {C0}, reventes apres {C}", flush=True)
    R = tests_site.regles()
    n_m = cote_marche(rows, C0)
    A_avant = annoter(rows, n_m)
    appris = mesurer([a for a in A_avant if a["j"] < C0])
    corr = decider(appris)
    A_main = annoter(rows, n_m, corr)
    m_av, m_ma = mesurer([a for a in A_avant if a["j"] >= C0]), mesurer([a for a in A_main if a["j"] >= C0])
    res = {}
    for nom, A in (("avant", A_avant), ("maintenant", A_main)):
        mm, fin, par = mesures(A, C0, C, R)
        df = defi(A, fin, C)
        L = mm["lettres"]
        o = dict(**mm, defi=df["stats"], defi_semaines=len(df["semaines"]))
        hautes = [L[x] for x in ("A+", "A") if L.get(x)]
        bas = L.get("E") or L.get("D")
        if hautes and bas:
            o["x_ahaut_bas"] = round(sum(x["reventes"] * x["cartes"] for x in hautes) / sum(x["cartes"] for x in hautes) / bas["reventes"], 1)
            o["bas"] = "E" if L.get("E") else "D"
        res[nom] = o
        json.dump(df, open(os.path.join(TRAV, f"defi_pool_bb_{nom}.json"), "w"), ensure_ascii=False, separators=(",", ":"))
    src = collections.Counter(v[2] for v in {a["nom"]: (0, 0, a["src"]) for a in A_main}.values())
    out = dict(le=dt.date.today().isoformat(), regles=R, coupe=C0, revente_des=C, revente_fin=js[-1], ventes_total=len(rows), ecartees=dict(ecart),
               ventes_mesurees=m_ma["ventes"], joueurs=len({a["nom"] for a in A_main}), sources_joueurs=dict(src),
               accord_avant=m_av["accord_global"], accord=m_ma["accord_global"], rho_avant=m_av["rho"], rho=m_ma["rho"],
               inversions_avant=m_av["inversions"], inversions=m_ma["inversions"], lettres_validation=m_ma["lettres"],
               accord_par_lettre=m_ma["accord"], corrections=corr, n_corrections=len(corr), avant=res["avant"], maintenant=res["maintenant"])
    json.dump(out, open(os.path.join(TRAV, "resultats_bb.json"), "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k not in ("corrections",)}, ensure_ascii=False, indent=1))
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    lancer(args[0] if args else "/mnt/user-data/uploads/Downloads/ventes_baseball (2).tsv.gz")
