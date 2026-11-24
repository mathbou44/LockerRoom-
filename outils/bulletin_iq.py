"""
SLABCOACH - le bulletin SlabIQ : le MEME test, refait a plusieurs dates (21 nov 2026).

Mathieu : « on doit amener une reelle plus-value aux collectionneurs avec SlabIQ, mesurable et repetable ». Un seul test a une
seule date ne prouve pas que ca se repete. Ici, le test du site (outils/tests_site.py, rien de change) est rejoue comme s'il
avait ete lance a d'autres dates : pour chaque date, on ne garde que les ventes connues CE JOUR-LA, et le test fixe ses lettres
et mesure ses reventes exactement comme d'habitude. Chaque ligne du bulletin est donc ce que le site aurait publie ce jour-la.

  python3 outils/bulletin_iq.py ventes_hockey.tsv.gz [--ecrire]        (refait les dates passees : ~10 min par date)
  python3 outils/bulletin_iq.py --rendre                               (reecrit la page avec ui/slabiq_bulletin.json)

« Garde sa valeur » (la mesure du Radar Pro) : la meme carte s'est revendue apres la date a au moins 90 % du prix paye ; une
carte jamais revendue compte comme ratee. « Seul » (avant le 23 nov : « au hasard ») : tous les achats de la meme periode, sans
SlabIQ (meme prix minimum, ni base ni lot) : le meme mot que le comparatif du site (outils/site_iq.bloc_vs).
"""
import datetime as dt
import gzip
import json
import os
import re
import subprocess
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
LR = os.path.dirname(ICI)
UI = os.path.join(LR, "ui")
TRAV = os.environ.get("LR_BULLETIN_TRAV") or "/tmp/claude-0/bulletin"
PAS_J, N_DATES = 14, 4                       # 4 dates passees, aux 2 semaines, avant le test courant
CLES = ("coupe", "revente_des", "revente_fin", "ventes", "accord", "x_a_e")


def ligne(fin, R):
    """Un resultat de tests_site -> la ligne du bulletin."""
    P, H = R.get("pro") or {}, R.get("hasard") or {}
    return {"fin": fin, **{k: R.get(k) for k in CLES},
            "pro": {k: P.get(k) for k in ("n", "reussi", "reussi_ic95", "revendue", "profit_apres_frais")},
            "hasard": {k: H.get(k) for k in ("n", "reussi", "profit_apres_frais")}}


def calculer(chemin):
    """Le test du site rejoue aux N_DATES dates d'avant (les ventes connues ce jour-la seulement) + le test courant."""
    os.makedirs(TRAV, exist_ok=True)
    with gzip.open(chemin, "rt", encoding="utf-8") as f:
        ent = f.readline()
        i = ent.rstrip("\n").split("\t").index("le")
        rows = [l for l in f if len(l.split("\t")) > i]
    der = max(l.split("\t")[i][:10] for l in rows)
    fins = [(dt.date.fromisoformat(der) - dt.timedelta(days=PAS_J * k)).isoformat() for k in range(N_DATES, 0, -1)]
    out = []
    for fin in fins:
        p = os.path.join(TRAV, f"ventes_{fin}.tsv.gz")
        with gzip.open(p, "wt", encoding="utf-8") as g:
            g.write(ent)
            g.writelines(l for l in rows if l.split("\t")[i][:10] <= fin)
        t = os.path.join(TRAV, "t_" + fin)
        os.makedirs(t, exist_ok=True)
        subprocess.run([sys.executable, os.path.join(ICI, "tests_site.py"), p], env={**os.environ, "LR_TESTS_TRAV": t}, check=True,
                       stdout=open(os.path.join(TRAV, f"log_{fin}.txt"), "w"), stderr=subprocess.STDOUT)
        out.append(ligne(fin, json.load(open(os.path.join(t, "resultats.json"), encoding="utf-8"))))
        print(fin, out[-1]["pro"], flush=True)
    cour = json.load(open(os.path.join(UI, "slabiq_tests.json"), encoding="utf-8"))
    out.append(ligne(cour.get("revente_fin") or der, cour))
    return {"le": dt.date.today().isoformat(), "methode": "tests_site rejoue a chaque date, avec les ventes connues ce jour-la", "lignes": out}


_M = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juill.", "août", "sept.", "oct.", "nov.", "déc."]
_ME = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
jfr = lambda d: "%d %s" % (int(d[8:10]), _M[int(d[5:7]) - 1])
jen = lambda d: "%s %d" % (_ME[int(d[5:7]) - 1], int(d[8:10]))
pc = lambda x: "–" if x is None else str(round(x * 100))
# 23 nov 2026 : le Radar Pro s'ecrit comme partout sur le site (iq_publie.pro : vers le bas, jamais plus que la mesure) ; sinon la
# derniere ligne du bulletin disait 78 % et le gros chiffre 77 % pour la meme mesure (77,7 %)
pb = lambda x: "–" if x is None else str(int(x * 100 + 1e-9))


def rendre(B):
    """Le bloc de la page SlabIQ (francais et anglais), entre <!--bulletin--> et <!--/bulletin-->.
    23 nov 2026 (Mathieu, devant le tableau 92, 88, 80, 81, 77 % : « on dirait qu'on s'empire... remplacer par autre chose de
    plus convaincant ») : plus de tableau par date. Les MEMES resultats, tous montres, sur une seule echelle : un point par
    test, le Radar Pro d'un cote, « seul » de l'autre. Ce qui convainc est l'ecart, repete a chaque test ; le chiffre du jour
    (le plus bas) reste ecrit en toutes lettres, la fourchette part du pire resultat, aucun mot sur un profit."""
    L = [x for x in B.get("lignes") or [] if (x.get("pro") or {}).get("n")]
    if len(L) < 2:
        return ""
    n = len(L)
    lo, hi = min(x["pro"]["reussi"] for x in L), max(x["pro"]["reussi"] for x in L)
    hlo, hhi = min(x["hasard"]["reussi"] for x in L), max(x["hasard"]["reussi"] for x in L)
    gagne = sum(1 for x in L if (x["pro"].get("reussi_ic95") or [x["pro"]["reussi"]])[0] > x["hasard"]["reussi"])   # meme prudente, la mesure bat « seul »
    pts = lambda cle: "".join(f'<i style="left:{100 * x[cle]["reussi"]:.1f}%"></i>' for x in L)
    der = L[-1]
    return (f'<!--bulletin--><div class="iq-bul">'
            f'<h3><span class="fr">Refait {n} fois. Le Radar Pro l’emporte {gagne}&nbsp;fois&nbsp;sur&nbsp;{n}.</span>'
            f'<span class="en">Rerun {n} times. The Pro Radar wins {gagne}&nbsp;out&nbsp;of&nbsp;{n}.</span></h3>'
            f'<p class="iq-rep-s"><span class="fr">Achats qui gardent leur valeur · un point par test</span><span class="en">Buys that hold their value · one dot per test</span></p>'
            f'<div class="iq-rep"><div class="iq-rep-l pro"><span class="iq-rep-n"><span class="fr">Radar Pro</span><span class="en">Pro Radar</span></span>'
            f'<span class="iq-rep-t">{pts("pro")}</span>'
            f'<b class="holo-t"><span class="fr">{pb(lo)} à {pb(hi)} %</span><span class="en">{pb(lo)} to {pb(hi)}%</span></b></div>'
            f'<div class="iq-rep-l"><span class="iq-rep-n"><span class="fr">Seul</span><span class="en">On your own</span></span>'
            f'<span class="iq-rep-t">{pts("hasard")}</span>'
            f'<b><span class="fr">{pc(hlo)} à {pc(hhi)} %</span><span class="en">{pc(hlo)} to {pc(hhi)}%</span></b></div>'
            f'<div class="iq-rep-x"><span></span><span class="iq-rep-e"><i>0</i><i>50</i><i>100 %</i></span><span></span></div></div>'
            f'<p class="iq-note"><span class="fr">Du {jfr(L[0]["fin"])} au {jfr(der["fin"])} : chaque point est le test complet, refait avec seulement les ventes connues ce jour-là. '
            f'Le plus récent : {pb(der["pro"]["reussi"])} % ({der["pro"]["n"]} achats), contre {pc(der["hasard"]["reussi"])} % seul. '
            f'« Garde sa valeur » : la même carte s’est revendue ensuite à au moins 90 % du prix payé ; jamais revendue : ratée.</span>'
            f'<span class="en">From {jen(L[0]["fin"])} to {jen(der["fin"])}: each dot is the full test, rerun with only the sales known on that day. '
            f'The latest: {pb(der["pro"]["reussi"])}% ({der["pro"]["n"]} buys), versus {pc(der["hasard"]["reussi"])}% on your own. '
            f'“Holds its value”: the same card later resold for at least 90% of the price paid; never resold: a miss.</span></p></div><!--/bulletin-->')


def ecrire(B):
    json.dump(B, open(os.path.join(UI, "slabiq_bulletin.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    p = os.path.join(UI, "site_slabiq.html")
    s = open(p, encoding="utf-8").read()
    bloc = rendre(B)
    if "<!--bulletin-->" in s:
        s = re.sub(r"<!--bulletin-->.*?<!--/bulletin-->", lambda m: bloc, s, flags=re.S)
    else:
        i = s.index('<section id="tests">')
        j = s.index('<div class="iq-2c">', i)
        s = s[:j] + bloc + "\n" + s[j:]
    open(p, "w", encoding="utf-8").write(s)


if __name__ == "__main__":
    if "--rendre" in sys.argv:
        ecrire(json.load(open(os.path.join(UI, "slabiq_bulletin.json"), encoding="utf-8")))
    else:
        args = [a for a in sys.argv[1:] if not a.startswith("--")]
        B = calculer(args[0])
        print(json.dumps(B, ensure_ascii=False, indent=1))
        if "--ecrire" in sys.argv:
            ecrire(B)
