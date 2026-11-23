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
    """Le bloc de la page SlabIQ (francais et anglais), entre <!--bulletin--> et <!--/bulletin-->."""
    L = [x for x in B.get("lignes") or [] if (x.get("pro") or {}).get("n")]
    if len(L) < 2:
        return ""
    lo, hi = min(x["pro"]["reussi"] for x in L), max(x["pro"]["reussi"] for x in L)
    hlo, hhi = min(x["hasard"]["reussi"] for x in L), max(x["hasard"]["reussi"] for x in L)
    r = "".join(f'<tr style="border-top:1px solid rgba(255,255,255,.08)"><td style="text-align:left;white-space:nowrap;padding:9px 0"><span class="fr">{jfr(x["fin"])}</span><span class="en">{jen(x["fin"])}</span></td><td>{x["pro"]["n"]}</td>'
                f'<td><b class="holo-t">{pb(x["pro"]["reussi"])} %</b></td><td>{pc(x["hasard"]["reussi"])} %</td></tr>' for x in L)
    return (f'<!--bulletin--><div class="iq-bul" style="margin:26px 0 6px"><h3><span class="fr">Le même test, refait à {len(L)} dates</span>'
            f'<span class="en">The same test, rerun on {len(L)} dates</span></h3>'
            f'<table style="width:100%;border-collapse:collapse;text-align:right;font-variant-numeric:tabular-nums"><tr style="opacity:.6;font-size:.82em">'
            f'<th style="text-align:left;font-weight:500;padding:6px 0"><span class="fr">Test du</span><span class="en">Test of</span></th>'
            f'<th style="font-weight:500"><span class="fr">Achats du Radar Pro</span><span class="en">Pro Radar buys</span></th>'
            f'<th style="font-weight:500"><span class="fr">Gardent leur valeur</span><span class="en">Hold their value</span></th>'
            f'<th style="font-weight:500"><span class="fr">Seul</span><span class="en">On your own</span></th></tr>{r}</table>'
            f'<p class="iq-note"><span class="fr">Chaque ligne est le test tel qu’il aurait été publié ce jour-là, avec seulement les ventes connues à cette date. '
            f'À chaque fois : {pb(lo)} à {pb(hi)} % des achats du Radar Pro se sont revendus sans perdre leur valeur (seul : {pc(hlo)} à {pc(hhi)} %). '
            f'« Garde sa valeur » : la même carte s’est revendue ensuite à au moins 90 % du prix payé ; jamais revendue : ratée.</span>'
            f'<span class="en">Each row is the test as it would have been published that day, with only the sales known on that date. '
            f'Every time: {pb(lo)} to {pb(hi)}% of Pro Radar buys resold without losing value (on your own: {pc(hlo)} to {pc(hhi)}%). '
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
