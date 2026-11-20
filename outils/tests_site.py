"""
SLABCOACH - refaire les tests publies sur le site (19 nov 2026).

Mathieu : « a chaque version significative de SlabIQ (sa methode de recherche Pro), il faut refaire les resultats des tests et
les mettre sur notre page : ils vont toujours s'ameliorer ».

  python3 outils/tests_site.py [ventes_hockey.tsv.gz] [--ecrire]

Une seule methode, la meme a chaque fois (rien d'ajuste a la main) :
  1. les ventes de hockey (le fichier « Telecharger toutes les ventes » de l'admin), dedoublonnees ;
  2. deux dates : C0 (65 % des ventes) et C (80 %). Les lettres sont FIXEES avec les ventes d'avant C0 : les corrections
     automatiques du marche (validation_iq) sont apprises seulement sur ces ventes. Tout ce qui est mesure ensuite vient de
     ventes que SlabIQ n'a jamais vues ;
  3. les regles sont lues dans le code (lockerroom.Api : RADAR_FIXE_MIN, RADAR_PRIX_MIN ; vitrine) : le test suit l'app ;
  4. on mesure : l'accord avec le marche (ventes d'apres C0), les reventes par lettre (cartes vues avant C, revendues apres),
     le Radar Pro (achats entre C0 et C, revendus apres C a au moins 90 % du prix), la simulation d'un an (500 $ par mois) et
     le defi ;
  5. --ecrire : ui/slabiq_tests.json et chaque chiffre du site (balises data-iq) ; l'empreinte du code de decision est gardee
     (tests/test_site_a_jour.py echoue si SlabIQ change sans que les tests soient refaits).
"""
import collections
import gzip
import hashlib
import json
import os
import pickle
import random
import re
import shutil
import statistics as st
import subprocess
import sys
import datetime as dt

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LR = os.path.join(RACINE, "lrtest") if os.path.exists(os.path.join(RACINE, "lrtest", "bareme_iq.py")) else RACINE   # le bac a sable ou le depot
TRAV = os.environ.get("LR_TESTS_TRAV") or "/tmp/claude-0/ts"
# 20 nov 2026 (passation) : l'indice des joueurs du test est aussi dans le depot (outils/donnees_tests_site)
_D_DEPOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "donnees_tests_site")
BASE_DONNEES = os.environ.get("LR_TESTS_DONNEES") or ("/tmp/claude-0/nuit/bal/d_sans" if os.path.isdir("/tmp/claude-0/nuit/bal/d_sans") else _D_DEPOT)   # l'indice des joueurs (stats publiques), sans correction automatique
VENTES_DEFAUT = "/mnt/user-data/uploads/Downloads/ventes_hockey.tsv.gz"
# 19 nov 2026 : toutes les compagnies (une KSA 10 n'est plus melangee avec la meme carte non gradee)
G = re.compile(r"\b(psa|bgs|sgc|cgc|tag|ksa|hga|beckett|bccg|csg|gma|isa|ags|mnt)\s*-?\s*(?:gem\s*(?:mint|mt)?\s*|mint\s*|pristine\s*)?(\d+(?:\.\d)?)\b", re.I)


_VAL = r"(?:int\(os\.environ\.get\([^)]*\)\s*or\s*)?([0-9.]+)"


def empreinte():
    sys.path.insert(0, LR)
    import empreinte_iq
    return empreinte_iq.empreinte()


def regles():
    src = open(os.path.join(LR, "lockerroom.py"), encoding="utf-8").read()
    g = lambda k: float(re.search(r"\b" + k + r"\s*=\s*" + _VAL, src).group(1))
    return {"fixe": g("RADAR_FIXE_MIN"), "encan": g("RADAR_SCORE_MIN"), "prix_min": g("RADAR_PRIX_MIN")}


# ---------------------------------------------------------------- etape 1 : les ventes
def charger(chemin):
    os.makedirs(TRAV, exist_ok=True)
    cache = os.path.join(TRAV, "rows_%d.pkl" % int(os.path.getmtime(chemin)))
    if os.path.exists(cache):
        return pickle.load(open(cache, "rb"))
    sys.path.insert(0, LR)
    import validation_iq as v
    import score_slab
    vus, out = set(), []
    with gzip.open(chemin, "rt", encoding="utf-8") as f:
        next(f)
        for l in f:
            p = l.rstrip("\n").split("\t")
            if len(p) < 3 or not p[2]:
                continue
            try:
                pr = float(p[1])
            except ValueError:
                continue
            r = (p[0], pr, p[2][:10])
            if pr < 3 or r in vus:
                continue
            vus.add(r)
            if not score_slab.sport_autre(p[0]) and (v._RE_HOCKEY_SUR.search(p[0]) or v._equipe_lnh(p[0])):
                out.append(r)
    pickle.dump(out, open(cache, "wb"))
    return out


# ---------------------------------------------------------------- etape 2 : les lettres (dans un processus a part)
def _annoter_sous(rows_pkl, donnees, sortie, apprendre_avant=None, mesurer_des=None):
    """Lance ce fichier en mode « annoter » avec ses propres donnees (LOCKERROOM_DONNEES)."""
    env = dict(os.environ, LOCKERROOM_DONNEES=donnees)
    a = [sys.executable, os.path.abspath(__file__), "--annoter", rows_pkl, sortie]
    if apprendre_avant:
        a += ["--apprendre", apprendre_avant]
    if mesurer_des:
        a += ["--mesurer", mesurer_des]
    subprocess.run(a, check=True, env=env, cwd=LR)
    return pickle.load(open(sortie, "rb"))


def _annoter_ici(rows_pkl, sortie, apprendre=None, mesurer=None):
    sys.path.insert(0, LR)
    import validation_iq as v
    import bareme_iq as bq
    rows = pickle.load(open(rows_pkl, "rb"))
    v.time.sleep = lambda s: None                 # pas de pause (c'est pour le serveur)
    info = {}
    if apprendre:
        r = v.iterer([x for x in rows if x[2] < apprendre])
        info["appris"] = {k: r.get(k) for k in ("ventes", "accord", "auto")}
    if mesurer:
        m = v.mesurer([x for x in rows if x[2] >= mesurer])
        info["mesure"] = {k: m[k] for k in ("ventes", "rho", "accord_global", "inversions")}
    import cartes_match
    import indice_joueurs
    import score_slab
    I = (indice_joueurs.lire() or {}).get("indice") or {}
    Il = {k.lower(): x for k, x in I.items()}
    # 20 nov 2026 (revue des bancs) : mesurer la FUITE. L'indice du test est une photo de novembre (demande apprise sur nos ventes,
    # notoriete et buzz de Wikipedia des 20-60 derniers jours) et les cotes de l'expert ont ete ecrites le 16 nov : des
    # informations d'APRES la coupe. LR_TS_SANS_INSTANTANE=1 : sans ces criteres ; LR_TS_SANS_EXPERT=1 : sans les cotes de l'expert.
    sans_inst, sans_exp = os.environ.get("LR_TS_SANS_INSTANTANE") == "1", os.environ.get("LR_TS_SANS_EXPERT") == "1"
    if sans_exp:
        bq.JOUEURS_EXPERT = {}
        bq.cotes_apprises = lambda: {}
        bq._alias_expert = lambda nom: None
    info["variante"] = {"sans_instantane": sans_inst, "sans_expert": sans_exp}
    memo, out = {}, []
    for t, p, j in rows:                          # comme validation_iq._annoter, en gardant la note du joueur (0-100)
        so, ra = bq.sorte(t)
        if ra == "lot_checklist":
            continue
        nom = cartes_match.joueur_du_titre(t)
        if not nom:
            continue
        nom = " ".join(w.capitalize() for w in nom.split())
        if nom not in memo:
            x = indice_joueurs.indice(nom) or Il.get(nom.lower()) or {}
            c = x.get("criteres") or {}
            if sans_inst:
                c = {k_: v_ for k_, v_ in c.items() if k_ not in ("demande", "notoriete", "buzz")}
            connu = bool(x) or bq._legende(nom) or nom in bq.JOUEURS_EXPERT or bq._alias_expert(nom)
            memo[nom] = (*bq.note_joueur(nom, c, recrue=float(c.get("recrue") or 0) >= 90), bool(connu))
        nj, lj, src, connu = memo[nom]
        g = G.search(t)
        s_ = bq.note_finale(bq.NOTE[so], nj)
        # 19 nov 2026 : comme l'app (score_slab.plafond_grade) : une carte gradee ne depasse pas la lettre de sa compagnie
        gd = cartes_match._decoder_memo(t).get("grade")
        pg = score_slab.plafond_grade(gd["cie"]) if gd else None
        if pg is not None and s_ > pg:
            s_ = float(pg)
        # 20 nov 2026 : la compagnie aussi (une PSA 10 et une SGC 10 ne sont pas la meme carte : avant, seule la note comptait)
        out.append(dict(k=v.cle_carte(t) + ("|" + g.group(1).lower().replace("beckett", "bgs") if g else ""), gr=float(g.group(2)) if g else 0.0,
                        cie=g.group(1).upper().replace("BECKETT", "BGS") if g else "", p=p, j=j, so=bq.NOTE[so], nj=nj, ra=ra, nom=nom, src=src,
                        t=t[:120], fin=bq.lettre(s_), s=s_, connu=connu))
    info["joueurs"] = len({x["nom"] for x in out if x["connu"]})
    pickle.dump({"A": out, "info": info}, open(sortie, "wb"))


# ---------------------------------------------------------------- etape 3 : les mesures
def mesures(A, C0, C, R):
    import numpy as np
    par = collections.defaultdict(list)
    for a in A:
        par[(a["k"], a["gr"])].append((a["j"], a["p"]))
    # les reventes par lettre : les cartes vues avant C (leur lettre), combien de fois revendues apres C
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
    # 20 nov 2026 (Mathieu : « il ne faut pas que l'acheteur reste pogne avec sa carte ») : la mesure publiee du Radar Pro est
    # celle de sa vraie regle (liquidite.py : A- et mieux, 5 ventes de la meme carte en 60 jours, pas plus de 10 % au-dessus de
    # ce qu'elle se vend). Un achat entre C0 et C est REUSSI si la meme carte se revend apres C (elle est liquide) ET a au moins
    # 90 % du prix (elle garde sa valeur). Les achats jamais revendus comptent comme rates (avant : ils ne comptaient pas).
    # Le point de comparaison : les memes achats au hasard (meme prix minimum, ni base ni lot). Intervalle a 95 % (bootstrap).
    sys.path.insert(0, LR)
    import liquidite
    import bisect
    idx = {k: ([j for j, _ in sorted(v)], [p for _, p in sorted(v)]) for k, v in par.items()}

    def signaux(a):
        js, ps = idx[(a["k"], a["gr"])]
        i = bisect.bisect_left(js, a["j"])
        j60 = (dt.date.fromisoformat(a["j"]) - dt.timedelta(days=liquidite.LIQ_JOURS)).isoformat()
        j90 = (dt.date.fromisoformat(a["j"]) - dt.timedelta(days=liquidite.MED_JOURS)).isoformat()
        i90 = bisect.bisect_left(js, j90)
        return i - bisect.bisect_left(js, j60), liquidite.mediane_recente(list(zip(js[i90:i], ps[i90:i])), a["j"], avant=True)

    def radar(a):
        return a["s"] >= liquidite.NOTE_MIN and liquidite.passe(*signaux(a), a["p"])
    FRAIS, FIXE = 0.1325, 0.40

    def pro_reel(regle, pmin, runs=1000, seed=5):
        L_ = []
        for a in A:
            if not (C0 <= a["j"] < C) or a["p"] < max(10, pmin) or a["ra"] in ("base", "lot_checklist") or not regle(a):
                continue
            L = [p for j, p in par[(a["k"], a["gr"])] if j >= C]
            m_ = st.median(L) if L else None
            L_.append((m_ is not None, m_ is not None and m_ >= 0.9 * a["p"], m_ is not None and m_ * (1 - FRAIS) - FIXE >= a["p"]))
        if not L_:
            return dict(n=0)
        n, rev = len(L_), sum(x[0] for x in L_)
        rng = random.Random(seed)
        bs = sorted(sum(x[1] for x in rng.choices(L_, k=n)) / n for _ in range(runs))
        return dict(n=n, reussi=round(sum(x[1] for x in L_) / n, 3), reussi_ic95=[round(bs[int(.025 * runs)], 3), round(bs[int(.975 * runs)], 3)],
                    revendue=round(rev / n, 3), garde=round(sum(x[1] for x in L_) / rev, 3) if rev else None,
                    profit_apres_frais=round(sum(x[2] for x in L_) / n, 3))
    pro_now = pro_reel(radar, R["prix_min"])
    pro_avant = pro_reel(lambda a: a["s"] >= R["fixe"], R["prix_min"])          # le Radar Pro jusqu'au 19 nov : A et A+ seulement
    hasard = pro_reel(lambda a: True, R["prix_min"])
    realisme = {"frais": [FRAIS, FIXE]}
    # la simulation d'un an : 400 collectionneurs, 500 $ par mois, cartes de R prix_min a 150 $, au hasard ou avec SlabIQ
    fin = {k: st.median([p for j, p in v if j >= C]) for k, v in par.items() if any(j >= C for j, p in v)}
    ventes = [(a["j"], (a["k"], a["gr"]), a["p"], a["s"], a["nom"]) for a in A if "2025-11-01" <= a["j"] < C]
    d = dt.date(2025, 11, 1)
    P = []
    while d.isoformat() < C:
        n_ = (d.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
        P.append((d.isoformat(), min(n_.isoformat(), C)))
        d = n_
    mens = collections.defaultdict(dict)
    for k, v in par.items():
        dd = collections.defaultdict(list)
        for j, p in v:
            dd[j[:7]].append(p)
        for mo, l in dd.items():
            mens[k][mo] = st.median(l)
    pmin_s = R["prix_min"]

    def courbes(regle, runs=400, seed=3):
        pools = {pp: [(k, p, s, j, nom) for j, k, p, s, nom in ventes if pp[0] <= j < pp[1] and pmin_s <= p <= 150 and k in fin and regle(s)] for pp in P}
        rng = random.Random(seed)
        Cs = []
        for _ in range(runs):
            tenus, deja, parj, cur, inv = [], set(), collections.Counter(), [], 0
            for pp in P:
                L = pools[pp][:]
                rng.shuffle(L)
                reste = 500
                for k, p, s, j, nom in L:
                    if k in deja or p > reste or parj[nom] >= 4:
                        continue
                    deja.add(k); parj[nom] += 1; tenus.append((k, p, j)); reste -= p; inv += p
                    if reste < pmin_s:
                        break
                mo = pp[0][:7]
                v = 0
                for k, p, j in tenus:
                    last = p
                    for m2 in sorted(mens[k]):
                        if j[:7] <= m2 <= mo:
                            last = mens[k][m2]
                    v += last
                cur.append((inv, v))
            cur[-1] = (inv, sum(fin[k] for k, _, _ in tenus))
            Cs.append(cur)
        med = [[round(float(np.median([c[i][0] for c in Cs]))), round(float(np.median([c[i][1] for c in Cs])))] for i in range(len(P))]
        return med, [c[-1] for c in Cs]
    ms, fs = courbes(lambda s: True)
    ma, fa = courbes(lambda s: s >= R["fixe"])
    a_ = np.array([v / i for i, v in fs]); b_ = np.array([v / i for i, v in fa])
    ea = np.array([v - i for i, v in fs]); eb = np.array([v - i for i, v in fa])
    sim = dict(sans=ms, avec=ma, r_sans=round(float(np.median(a_)) - 1, 4), r_avec=round(float(np.median(b_)) - 1, 4), bat=round(float(np.mean(b_ > a_)), 3),
               ecart=round(float(np.median(eb - ea))), p10=round(float(np.percentile(eb - ea, 10))), p90=round(float(np.percentile(eb - ea, 90))),
               mois=[pp[0][:7] for pp in P], prix=[pmin_s, 150], seuil=R["fixe"])
    return dict(lettres=lettres, pro=pro_now, pro_avant=pro_avant, hasard=hasard, sim=sim, realisme=realisme), fin, par, radar


PROD = [("the cup", "The Cup"), ("sp authentic", "SP Authentic"), ("sp game used", "SP Game Used"), ("spx", "SPx"), ("ultimate", "Ultimate"),
        ("trilogy", "Trilogy"), ("black diamond", "Black Diamond"), ("premier", "Premier"), ("stature", "Stature"), ("artifacts", "Artifacts"),
        ("synergy", "Synergy"), ("allure", "Allure"), ("chronology", "Chronology"), ("credentials", "Credentials"), ("metal universe", "Metal Universe"),
        ("o-pee-chee platinum|opc platinum", "OPC Platinum"), ("o-pee-chee|\\bopc\\b", "O-Pee-Chee"), ("\\bice\\b", "Ice"), ("mvp", "MVP"),
        ("tim hortons", "Tim Hortons"), ("parkhurst", "Parkhurst"), ("extended", "Upper Deck Extended"), ("series (?:2|two|ii)\\b", "Upper Deck Series 2"),
        ("series (?:1|one|i)\\b", "Upper Deck Series 1"), ("upper deck|\\bud\\b", "Upper Deck")]


def _etiquette(v, t, ra, nom, gr):
    """Ce que le defi montre d'une carte : le joueur, l'annee et le produit, la sorte, la gradation (jamais le titre eBay)."""
    tl = t.lower()
    an = re.search(r"\b(20\d\d|19\d\d)[-/](\d{2,4})\b", tl) or re.search(r"\b(20\d\d|19\d\d)\b", tl)
    an = (an.group(1) + "-" + an.group(2)[-2:]) if an and an.lastindex == 2 else (an.group(1) if an else "")
    pr = next((n for r, n in PROD if re.search(r, tl)), "")
    num = re.search(r"/\s?(\d{1,4})\b", tl)
    typ = v.LIBELLES.get(ra, (ra.replace("_", " ").title(),))[0]
    if ra == "yg10":
        typ = "Young Guns"
    cie = (G.search(t).group(1).upper().replace("BECKETT", "BGS") if gr and G.search(t) else "PSA")
    g = f"{cie} {int(gr) if gr == int(gr) else gr}" if gr else ""
    return {"j": nom, "t": " · ".join(x for x in (an + (" " + pr if pr else ""), typ + (f" /{num.group(1)}" if num and ra not in ("yg", "base") else ""), g) if x.strip())}


def defi(A, par, C0, C, radar, n_marche=80):
    """Le defi du site (20 nov 2026, Mathieu : « une bataille contre SlabIQ, plus robuste ; montrer le vrai gain ») : 8 manches.
    A chaque manche, 8 vraies cartes achetees sur eBay entre C0 et C dans la meme gamme de prix (le marche : ce qu'on voit en
    cherchant soi-meme) ; on en garde 2. SlabIQ, lui, prend 2 cartes de son Radar Pro de la meme gamme et de la meme periode (la
    regle de liquidite.py : ce que le Radar t'aurait montre). « A garde sa valeur » : la meme carte s'est REVENDUE apres C a au
    moins 90 % du prix ; une carte jamais revendue (on reste pogne avec) est ratee. C'est la mesure du Radar Pro."""
    import numpy as np
    sys.path.insert(0, LR)
    import validation_iq as v
    import bareme_iq as bq
    HORS = {'Michael Jordan', 'Lebron James', 'Kobe Bryant', 'Shohei Ohtani', 'Tom Brady', 'Patrick Mahomes', 'Mike Trout', 'Aaron Judge',
            'Victor Wembanyama', 'Caitlin Clark'}
    BANDES = ((30, 50), (50, 100), (100, 200), (200, 500))
    cell = [dict() for _ in BANDES]
    for a in A:
        if not (C0 <= a["j"] < C) or not (BANDES[0][0] <= a["p"] < BANDES[-1][1]) or a["ra"] == "lot_checklist":
            continue
        if a["nom"] in HORS or a["src"] == "inconnu":
            continue
        k = (a["k"], a["gr"])
        b = next(i for i, (x, y) in enumerate(BANDES) if x <= a["p"] < y)
        if k in cell[b]:
            continue
        L = [p for j, p in par[k] if j >= C]
        cell[b][k] = {**_etiquette(v, a["t"], a["ra"], a["nom"], a["gr"]), "L": bq.lettre(a["s"]), "r": int(radar(a)),
                      "ok": int(bool(L) and st.median(L) >= 0.9 * a["p"])}
    rng = random.Random(12)
    POOL, stats_b = [], []
    for b, d in enumerate(cell):
        marche = list(d.values())
        rad = [c for c in marche if c["r"]]
        if len(marche) < 8 or len(rad) < 2:
            raise SystemExit(f"defi : la gamme {BANDES[b]} n'a pas assez de cartes ({len(marche)}, Radar {len(rad)})")
        stats_b.append((marche, rad))
        POOL.append({"m": [{k_: c[k_] for k_ in ("j", "t", "L", "ok")} for c in rng.sample(marche, min(n_marche, len(marche)))],
                     "r": [{k_: c[k_] for k_ in ("j", "t", "L", "ok")} for c in rad]})

    def partie(r):
        I = H = 0
        for _ in range(8):
            marche, rad = stats_b[r.randrange(len(BANDES))]
            H += sum(c["ok"] for c in r.sample(r.sample(marche, 8), 2))
            I += sum(c["ok"] for c in r.sample(rad, 2))
        return I, H
    r = random.Random(1)
    Rr = np.array([partie(r) for _ in range(20000)])
    tm = [c["ok"] for m_, _ in stats_b for c in m_]
    tr = [c["ok"] for _, rd in stats_b for c in rd]
    stats = dict(gagne=round(float(np.mean(Rr[:, 0] > Rr[:, 1])), 4), egal=round(float(np.mean(Rr[:, 0] == Rr[:, 1])), 3),
                 iq=round(float(np.mean(Rr[:, 0])), 1), hasard=round(float(np.mean(Rr[:, 1])), 1),
                 ok_marche=round(sum(tm) / len(tm), 3), ok_radar=round(sum(tr) / len(tr), 3), cartes=len(tm), cartes_radar=len(tr))
    return {"pool": POOL, "stats": stats, "bandes": BANDES, "periode": [C0, C]}


# ---------------------------------------------------------------- tout
def lancer(chemin, ecrire=False):
    rows = charger(chemin)
    js = sorted(r[2] for r in rows)
    C0, C = js[int(len(js) * .65)], js[int(len(js) * .80)]
    print(f"{len(rows)} ventes de hockey, {js[0]} -> {js[-1]} ; lettres fixees avant {C0}, reventes apres {C}", flush=True)
    rp = os.path.join(TRAV, "rows_courant.pkl")
    pickle.dump(rows, open(rp, "wb"))
    R = regles()
    res = {}
    for nom, apprendre in (("avant", None), ("maintenant", C0)):
        dd = os.path.join(TRAV, "donnees_" + nom)
        shutil.rmtree(dd, ignore_errors=True)
        shutil.copytree(BASE_DONNEES, dd)
        res[nom] = _annoter_sous(rp, dd, os.path.join(TRAV, f"A_{nom}.pkl"), apprendre, C0)
        print(nom, res[nom]["info"], flush=True)
    A = res["maintenant"]["A"]
    m, fin, par, radar = mesures(A, C0, C, R)
    df = defi(A, par, C0, C, radar)
    L = m["lettres"]
    out = dict(le=dt.date.today().isoformat(), empreinte=empreinte(), regles=R, coupe=C0, revente_des=C, revente_fin=js[-1],
               ventes=res["maintenant"]["info"]["mesure"]["ventes"], ventes_total=len(rows), joueurs=res["maintenant"]["info"]["joueurs"],
               accord=res["maintenant"]["info"]["mesure"]["accord_global"], accord_avant=res["avant"]["info"]["mesure"]["accord_global"],
               rho=res["maintenant"]["info"]["mesure"]["rho"], inversions=res["maintenant"]["info"]["mesure"]["inversions"],
               corrections=res["maintenant"]["info"]["appris"]["auto"], **m, defi=df["stats"])
    # la mesure publiee : les cartes A et plus (la regle du Radar Pro) contre les E
    hautes = [L[x] for x in ("A+", "A") if L.get(x)]
    if hautes and L.get("E"):
        out["x_ahaut_e"] = round(sum(x["reventes"] * x["cartes"] for x in hautes) / sum(x["cartes"] for x in hautes) / L["E"]["reventes"], 1)
    if L.get("A+") and L.get("E"):
        out["x_aplus_e"] = round(L["A+"]["reventes"] / L["E"]["reventes"], 1)
    if L.get("A") and L.get("E"):
        out["x_a_e"] = round(L["A"]["reventes"] / L["E"]["reventes"], 1)
    print(json.dumps({k: v for k, v in out.items() if k not in ("sim",)}, ensure_ascii=False, indent=1))
    print("simulation", {k: v for k, v in out["sim"].items() if k not in ("sans", "avec", "mois")})
    json.dump(out, open(os.path.join(TRAV, "resultats.json"), "w"), ensure_ascii=False, indent=1)
    json.dump(df, open(os.path.join(TRAV, "defi_pool.json"), "w"), ensure_ascii=False, separators=(",", ":"))
    if ecrire:
        import site_iq
        site_iq.ecrire(out, df)
    return out


if __name__ == "__main__":
    if "--annoter" in sys.argv:
        i = sys.argv.index("--annoter")
        ap = sys.argv[sys.argv.index("--apprendre") + 1] if "--apprendre" in sys.argv else None
        me = sys.argv[sys.argv.index("--mesurer") + 1] if "--mesurer" in sys.argv else None
        _annoter_ici(sys.argv[i + 1], sys.argv[i + 2], ap, me)
    else:
        args = [a for a in sys.argv[1:] if not a.startswith("--")]
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        lancer(args[0] if args else VENTES_DEFAUT, "--ecrire" in sys.argv)
