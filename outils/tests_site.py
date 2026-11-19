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
TRAV = "/tmp/claude-0/ts"
BASE_DONNEES = os.environ.get("LR_TESTS_DONNEES") or "/tmp/claude-0/nuit/bal/d_sans"   # l'indice des joueurs (stats publiques), sans correction automatique
VENTES_DEFAUT = "/mnt/user-data/uploads/Downloads/ventes_hockey.tsv.gz"
G = re.compile(r"\b(psa|bgs|sgc|cgc)\s*(?:gem\s*(?:mint|mt)?\s*)?(\d+(?:\.\d)?)\b", re.I)
FICHIERS_DECISION = ("bareme_iq.py", "score_slab.py", "validation_iq.py", "vitrine.py", "sets_cultes.py")


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
    I = (indice_joueurs.lire() or {}).get("indice") or {}
    Il = {k.lower(): x for k, x in I.items()}
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
            connu = bool(x) or bq._legende(nom) or nom in bq.JOUEURS_EXPERT or bq._alias_expert(nom)
            memo[nom] = (*bq.note_joueur(nom, c, recrue=float(c.get("recrue") or 0) >= 90), bool(connu))
        nj, lj, src, connu = memo[nom]
        g = G.search(t)
        s_ = bq.note_finale(bq.NOTE[so], nj)
        out.append(dict(k=v.cle_carte(t), gr=float(g.group(2)) if g else 0.0, p=p, j=j, so=bq.NOTE[so], nj=nj, ra=ra, nom=nom, src=src,
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
    # le Radar Pro : achats entre C0 et C ; « garde sa valeur » = la meme carte revendue apres C a au moins 90 % du prix
    def pro(seuil, pmin):
        n = ok = 0
        for a in A:
            if not (C0 <= a["j"] < C) or a["p"] < max(10, pmin) or a["s"] < seuil or a["ra"] in ("base", "lot_checklist"):
                continue
            L = [p for j, p in par[(a["k"], a["gr"])] if j >= C]
            if not L:
                continue
            n += 1
            ok += st.median(L) >= 0.9 * a["p"]
        return dict(n=n, garde=round(ok / n, 3) if n else None)
    pro_now, pro_avant = pro(R["fixe"], R["prix_min"]), pro(65, 10)
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
    return dict(lettres=lettres, pro=pro_now, pro_avant=pro_avant, sim=sim), fin, par


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
    g = f"PSA {int(gr) if gr == int(gr) else gr}" if gr else ""
    return {"j": nom, "t": " · ".join(x for x in (an + (" " + pr if pr else ""), typ + (f" /{num.group(1)}" if num and ra not in ("yg", "base") else ""), g) if x.strip())}


def defi(A, fin, C):
    """Le defi du site : 8 manches, 8 vraies cartes vendues au meme prix, on en garde 2 ; SlabIQ prend ses 2 meilleures lettres."""
    import numpy as np
    sys.path.insert(0, LR)
    import validation_iq as v
    import bareme_iq as bq
    HORS = {'Michael Jordan', 'Lebron James', 'Kobe Bryant', 'Shohei Ohtani', 'Tom Brady', 'Patrick Mahomes', 'Mike Trout', 'Aaron Judge',
            'Victor Wembanyama', 'Caitlin Clark'}
    etiquette = lambda t, ra, nom, gr: _etiquette(v, t, ra, nom, gr)
    debut = dt.date(2025, 11, 1)
    MOIS = []
    d = debut
    while d.isoformat()[:7] < C[:7]:
        MOIS.append(d.isoformat()[:7])
        d = (d.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
    BANDES = ((10, 25), (25, 50), (50, 100), (100, 150))
    cell = collections.defaultdict(dict)
    for a in A:
        k = (a["k"], a["gr"])
        m = a["j"][:7]
        if m in MOIS and a["j"] < C and 10 <= a["p"] <= 150 and k in fin:
            b = next(i for i, (x, y) in enumerate(BANDES) if x <= a["p"] < y or (i == 3 and a["p"] <= 150))
            if k not in cell[(m, b)]:
                cell[(m, b)][k] = (a["p"], a["s"], a["nom"], a["ra"], a["gr"], a["t"], a["src"])
    rng = random.Random(12)
    POOL = {}
    for (m, b), dd in cell.items():
        L = list(dd.items())
        rng.shuffle(L)
        vus, keep = set(), []
        for k, (p, s, nom, ra, gr, t, src_) in L:
            if nom in vus or nom in HORS or src_ == "inconnu" or (bq._legende(nom) and ra in ("yg", "yg10", "yg_variante")):
                continue
            vus.add(nom)
            keep.append({**etiquette(t, ra, nom, gr), "s": round(s), "L": bq.lettre(s), "ok": int(fin[k] >= 0.9 * p)})
            if len(keep) >= 36:
                break
        if len(keep) >= 8:
            POOL[f"{m}|{b}"] = keep

    def partie(r):
        ms = [MOIS[round(i * (len(MOIS) - 1) / 7)] for i in range(8)]
        I = H = 0
        for m in ms:
            bs = [b for b in range(4) if f"{m}|{b}" in POOL]
            if not bs:
                continue
            Cc = r.sample(POOL[f"{m}|{r.choice(bs)}"], 8)
            I += sum(c["ok"] for c in sorted(Cc, key=lambda c: -c["s"])[:2])
            H += sum(c["ok"] for c in r.sample(Cc, 2))
        return I, H
    r = random.Random(1)
    Rr = np.array([partie(r) for _ in range(20000)])
    stats = dict(gagne=round(float(np.mean(Rr[:, 0] > Rr[:, 1])), 3), egal=round(float(np.mean(Rr[:, 0] == Rr[:, 1])), 3))
    return {"pool": POOL, "stats": stats, "mois": MOIS, "bandes": BANDES}


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
    m, fin, par = mesures(A, C0, C, R)
    df = defi(A, fin, C)
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
