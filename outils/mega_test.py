"""
SLABCOACH - le mega test, la mesure (22 nov 2026).

Quand la collecte du serveur (mega_test.py : 3 ans de ventes de la meme carte, CompSniper) a rempli nos archives : on telecharge
« Toutes les ventes (hockey) » de l'admin et on rejoue le test du site (outils/tests_site.py, rien de change) a une date tous les
3 mois, sur toute la periode, avec SEULEMENT les ventes connues ce jour-la (comme outils/bulletin_iq.py, mais sur 3 ans).

La question a trancher : l'acheteur fait-il de l'argent ? Pour chaque date : les achats du Radar Pro contre les memes achats au
hasard, a 3, 6 et 12 mois, sur la meme carte exacte, frais eBay compris (tests_site.mesures -> « gains »).

  python3 outils/mega_test.py ventes_hockey.tsv.gz [--pas 91] [--min-jours 365] [--dates N]

Ecrit outils/mega_test_resultats.json (jamais le site : le site n'annonce que ce que Mathieu approuve) et un resume lisible.
Verdict « prouve » a un horizon : a CHAQUE date mesuree (3 au moins), le Radar Pro a un gain net median > 0 ET un rendement du
panier > 0 ET plus de gagnants que le hasard. Sinon : « pas prouve », avec les chiffres.
"""
import datetime as dt
import gzip
import json
import os
import subprocess
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
TRAV = os.environ.get("LR_MEGA_TRAV") or "/tmp/claude-0/mega"
SORTIE = os.path.join(ICI, "mega_test_resultats.json")
HORIZONS = ("90", "180", "365")
# les lettres sont fixees avec les ventes d'avant C0 (fin - 455 jours) ; les achats juges : entre C0 et C (fin - 90 jours) ; un
# achat juge a H jours doit avoir son horizon passe (tests_site.mesures) : 12 mois -> achats des ~3 premiers mois de la fenetre
C0_J, C_J = 455, 90


def dates(premiere, derniere, pas=91, min_jours=365):
    """Les dates de test : la plus recente, puis tous les `pas` jours en reculant, tant qu'il reste `min_jours` d'historique avant."""
    d0, d1 = dt.date.fromisoformat(premiere), dt.date.fromisoformat(derniere)
    out, d = [], d1
    while (d - d0).days >= min_jours:
        out.append(d.isoformat())
        d -= dt.timedelta(days=pas)
    return sorted(out)


def verdict(L, h):
    """Prouve a l'horizon h : a chaque date mesuree (3 au moins, 30 achats au moins chacune), gain net median > 0, rendement du
    panier > 0 et plus de gagnants que le hasard."""
    ok = [x for x in L if ((x.get("gains") or {}).get("pro") or {}).get(h, {}).get("n", 0) >= 30]
    if len(ok) < 3:
        return {"prouve": False, "pourquoi": f"{len(ok)} date(s) mesurable(s) a {h} jours (il en faut 3)", "dates": len(ok)}
    rates = []
    for x in ok:
        P, H = x["gains"]["pro"][h], x["gains"]["hasard"][h]
        if not ((P.get("gain_net_median") or -1) > 0 and (P.get("rendement_panier") or -1) > 0 and (P.get("gagnants") or 0) > (H.get("gagnants") or 0)):
            rates.append(x["fin"])
    return {"prouve": not rates, "dates": len(ok), "ratees": rates,
            "pourquoi": "a chaque date" if not rates else f"rate a {len(rates)} date(s) sur {len(ok)}"}


def calculer(chemin, pas=91, min_jours=365, n_dates=None):
    os.makedirs(TRAV, exist_ok=True)
    with gzip.open(chemin, "rt", encoding="utf-8") as f:
        ent = f.readline()
        i = ent.rstrip("\n").split("\t").index("le")
        rows = [l for l in f if len(l.split("\t")) > i and l.split("\t")[i][:4].isdigit()]
    js = sorted(l.split("\t")[i][:10] for l in rows)
    fins = dates(js[0], js[-1], pas, min_jours)
    if n_dates:                                        # les N plus recentes seulement (les vieilles dates n'ont presque pas de ventes)
        fins = fins[-n_dates:]
    print(f"{len(rows)} ventes, {js[0]} -> {js[-1]} ; {len(fins)} dates : {', '.join(fins)}", flush=True)
    L = []
    for fin in fins:
        p = os.path.join(TRAV, f"ventes_{fin}.tsv.gz")
        with gzip.open(p, "wt", encoding="utf-8") as g:
            g.write(ent)
            g.writelines(l for l in rows if l.split("\t")[i][:10] <= fin)
        t = os.path.join(TRAV, "t_" + fin)
        os.makedirs(t, exist_ok=True)
        rj = os.path.join(t, "resultats.json")
        if not os.path.exists(rj):                     # reprend : une date deja faite n'est pas refaite
            subprocess.run([sys.executable, os.path.join(ICI, "tests_site.py"), p], env={**os.environ, "LR_TESTS_TRAV": t, "LR_TESTS_SANS_DEFI": "1",
                                                                   "LR_TESTS_C0_JOURS": str(C0_J), "LR_TESTS_C_JOURS": str(C_J)}, check=True,
                           stdout=open(os.path.join(TRAV, f"log_{fin}.txt"), "w"), stderr=subprocess.STDOUT)
        R = json.load(open(rj, encoding="utf-8"))
        P, H = R.get("pro") or {}, R.get("hasard") or {}
        L.append({"fin": fin, "coupe": R.get("coupe"), "revente_des": R.get("revente_des"), "ventes": R.get("ventes_total"),
                  "pro": {k: P.get(k) for k in ("n", "reussi", "reussi_ic95", "revendue", "profit_apres_frais")},
                  "hasard": {k: H.get(k) for k in ("n", "reussi", "profit_apres_frais")}, "gains": R.get("gains") or {}})
        print(fin, json.dumps(L[-1]["gains"].get("pro") or {}), flush=True)
    return {"le": dt.date.today().isoformat(), "fichier": os.path.basename(chemin), "du": js[0], "au": js[-1], "pas_jours": pas,
            "lignes": L, "verdicts": {h: verdict(L, h) for h in HORIZONS}}


def pc(x):
    return "-" if x is None else f"{x * 100:+.0f} %" if abs(x) < 10 else "-"


def resume(B):
    out = [f"MEGA TEST : {B['du']} -> {B['au']}, {len(B['lignes'])} dates", ""]
    for h in HORIZONS:
        v = B["verdicts"][h]
        out.append(f"{int(h) // 30} mois : {'PROUVE' if v['prouve'] else 'PAS PROUVE'} ({v['pourquoi']})")
        for x in B["lignes"]:
            P, H = (x["gains"].get("pro") or {}).get(h) or {}, (x["gains"].get("hasard") or {}).get(h) or {}
            if P.get("n"):
                out.append(f"  {x['fin']}  Radar Pro {P['n']} achats : gagnants {round(100 * (P.get('gagnants') or 0))} % "
                           f"(hasard {round(100 * (H.get('gagnants') or 0))} %), gain net median {pc(P.get('gain_net_median'))}, "
                           f"panier {pc(P.get('rendement_panier'))}, jamais revendus {round(100 * (P.get('pogne') or 0))} %")
    return "\n".join(out)


if __name__ == "__main__":
    a = sys.argv[1:]
    pas = int(a[a.index("--pas") + 1]) if "--pas" in a else 91
    mj = int(a[a.index("--min-jours") + 1]) if "--min-jours" in a else 365
    nd = int(a[a.index("--dates") + 1]) if "--dates" in a else None
    ch = [x for k, x in enumerate(a) if not x.startswith("--") and (k == 0 or a[k - 1] not in ("--pas", "--min-jours", "--dates"))][0]
    B = calculer(ch, pas, mj, nd)
    json.dump(B, open(SORTIE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(resume(B))
