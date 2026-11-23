"""
SLABCOACH - ecrire les resultats des tests de SlabIQ sur le site (19 nov 2026).

Chaque chiffre de SlabIQ du site vient de lrtest/ui/slabiq_tests.json (outils/tests_site.py) : la meme valeur partout
(accueil et page SlabIQ). Chaque remplacement doit trouver exactement sa place, sinon on arrete (rien a moitie ecrit).
"""
import datetime as dt
import json
import math
import os
import re

_R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI = os.path.join(_R, "lrtest", "ui") if os.path.isdir(os.path.join(_R, "lrtest", "ui")) else os.path.join(_R, "ui")
MF = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
ME = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
MFc = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
MEc = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
ORDRE = ["A+", "A", "A-", "B+", "B", "C", "D", "E"]
import sys                                     # noqa: E402
sys.path.insert(0, os.path.dirname(UI))
import iq_publie                               # noqa: E402  20 nov 2026 : les memes arrondis que l'app


def fr(n):
    return f"{n:,}".replace(",", " ")


def en(n):
    return f"{n:,}"


def pfr(x, signe=True):
    return ((f"{x:+.1f}" if signe else f"{x:.1f}").replace(".", ",")).replace("-", "−") + " %"


def pen(x, signe=True):
    return (f"{x:+.1f}%" if signe else f"{x:.1f}%").replace("-", "−")


def jour_fr(d):
    d = dt.date.fromisoformat(d)
    return f"{d.day}{'er' if d.day == 1 else ''} {MF[d.month - 1]} {d.year}"


def jour_en(d):
    d = dt.date.fromisoformat(d)
    return f"{ME[d.month - 1]} {d.day}, {d.year}"


def mois_fr(m):
    y, mo = m.split("-")
    return f"{MF[int(mo) - 1]} {y}"


def mois_en(m):
    y, mo = m.split("-")
    return f"{ME[int(mo) - 1]} {y}"


def sub1(s, motif, rempl, n=1, flags=re.S):
    """Remplace exactement n fois (sinon : erreur ; le site n'est jamais ecrit a moitie)."""
    nouveau, k = re.subn(motif, rempl, s, flags=flags)
    if k != n:
        raise SystemExit(f"site_iq : « {motif[:70]} » trouve {k} fois (attendu {n})")
    return nouveau


def graphique(sim):
    """19 nov 2026 : le PROFIT de chaque collectionneur, mois par mois (la valeur de ses cartes moins l'argent qu'il a mis). Avant :
    la valeur seule ; avec SlabIQ, il achete seulement des A et plus et depense parfois moins : sa ligne paraissait plus basse
    alors qu'il gagnait plus. Le profit se compare toujours."""
    sans = [c[1] - c[0] for c in sim["sans"]]
    avec = [c[1] - c[0] for c in sim["avec"]]
    n = len(sans)
    W, H, L, RM, T, B = 760, 320, 64, 128, 16, 36
    pas = next(p for p in (100, 200, 250, 500, 1000, 2000) if (max(sans + avec + [0]) - min(sans + avec + [0])) / p <= 6)
    lo = math.floor(min(sans + avec + [0]) / pas) * pas
    hi = math.ceil(max(sans + avec + [0]) * 1.1 / pas) * pas
    X = lambda i: L + i * (W - L - RM) / (n - 1)
    Y = lambda v: T + (1 - (v - lo) / (hi - lo)) * (H - T - B)
    pts = lambda ys: " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(ys))
    mf = [MFc[int(m[5:7]) - 1] for m in sim["mois"]]
    me = [MEc[int(m[5:7]) - 1] for m in sim["mois"]]
    sg = lambda v: ("+" if v > 0 else "−" if v < 0 else "")
    grid = "".join(f'<line x1="{L}" x2="{W - RM + 6}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="g"/><text x="{L - 10}" y="{Y(v) + 4:.1f}" class="ty">{sg(v)}{abs(v)}</text>'
                   for v in range(lo, hi + 1, pas) if v != 0)
    zero = f'<line x1="{L}" x2="{W - RM + 6}" y1="{Y(0):.1f}" y2="{Y(0):.1f}" class="l-inv"/><text x="{L - 10}" y="{Y(0) + 4:.1f}" class="ty">0</text>'
    xl = "".join(f'<text x="{X(i):.1f}" y="{H - 10}" class="tx"><tspan class="fr">{mf[i]}</tspan><tspan class="en">{me[i]}</tspan></text>'
                 for i in range(n) if i % 2 == 0 or i == n - 1)
    aire = f"{X(0):.1f},{Y(0):.1f} " + pts(avec) + f" {X(n - 1):.1f},{Y(0):.1f}"
    ya, ys = Y(avec[-1]), Y(sans[-1])
    if abs(ya - ys) < 44:
        ya, ys = (ya, ya + 44) if avec[-1] >= sans[-1] else (ys + 44, ys)
    vfr = lambda v: f"{sg(v)}{fr(abs(v))} $"
    ven = lambda v: f"{sg(v)}${en(abs(v))}"
    svg = f'''<svg class="sim-svg" viewBox="0 0 {W} {H}" role="img" aria-label="Profit over 12 months">
  <defs><linearGradient id="simP" x1="0" x2="1"><stop offset="0" stop-color="#9FE6D2"/><stop offset=".45" stop-color="#B79CF2"/><stop offset=".75" stop-color="#F2B6D2"/><stop offset="1" stop-color="#E8C77A"/></linearGradient>
  <linearGradient id="simA" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#B79CF2" stop-opacity=".30"/><stop offset="1" stop-color="#B79CF2" stop-opacity="0"/></linearGradient>
  <filter id="simG" x="-5%" y="-20%" width="110%" height="140%"><feGaussianBlur stdDeviation="5"/></filter></defs>
  {grid}{zero}{xl}
  <polygon points="{aire}" fill="url(#simA)"/>
  <polyline points="{pts(sans)}" class="l-sans"/>
  <polyline points="{pts(avec)}" stroke="url(#simP)" class="l-glow" filter="url(#simG)"/>
  <polyline points="{pts(avec)}" stroke="url(#simP)" class="l-avec"/>
  <circle cx="{X(n - 1):.1f}" cy="{Y(avec[-1]):.1f}" r="6.5" class="p-a"/><circle cx="{X(n - 1):.1f}" cy="{Y(sans[-1]):.1f}" r="5" class="p-s"/>
  <text x="{X(n - 1) + 14:.1f}" y="{ya + 2:.1f}" class="v-a"><tspan class="fr">{vfr(avec[-1])}</tspan><tspan class="en">{ven(avec[-1])}</tspan></text>
  <text x="{X(n - 1) + 14:.1f}" y="{ya + 20:.1f}" class="n"><tspan class="fr">Avec SlabIQ</tspan><tspan class="en">With SlabIQ</tspan></text>
  <text x="{X(n - 1) + 14:.1f}" y="{ys + 22:.1f}" class="v-s"><tspan class="fr">{vfr(sans[-1])}</tspan><tspan class="en">{ven(sans[-1])}</tspan></text>
  <text x="{X(n - 1) + 14:.1f}" y="{ys + 40:.1f}" class="n"><tspan class="fr">Sans SlabIQ</tspan><tspan class="en">Without SlabIQ</tspan></text>
  <line class="hl" x1="0" x2="0" y1="{T}" y2="{H - B}"/>
  <rect class="hit" x="{L}" y="{T}" width="{W - L - RM}" height="{H - T - B}"/>
</svg>'''
    serie = json.dumps({"inv": [0] * n, "sans": sans, "avec": avec, "mf": mf, "me": me, "x0": L, "dx": (W - L - RM) / (n - 1), "w": W, "profit": True})
    return svg, serie, None, sans, avec


XFR, XEN = "plus de reventes pour une carte A ou A+ que pour une E", "more resales for an A or A+ card than an E"


def majX(s, x):
    """Chaque « N× plus de reventes » du site : la meme mesure, la meme phrase."""
    motifs = (r'<b class="holo-t">(?:<span class="fr">)?[0-9]+×(?:</span><span class="en">[0-9]+×</span>)?</b><span><span class="fr">plus de reventes pour [^<]*</span><span class="en">more resales for [^<]*</span></span>',)
    nouveau, k = re.subn(motifs[0], f'<b class="holo-t">{x}×</b><span><span class="fr">{XFR}</span><span class="en">{XEN}</span></span>', s)
    if not k:
        raise SystemExit("site_iq : aucune mesure « plus de reventes » trouvee")
    return nouveau


def pente(sans_fin, avec_fin):
    """20 nov 2026 (Mathieu : « un graphique montant pour SlabIQ, descendant sans » ; puis « deux lignes droites, ca fait pas
    naturel ») : deux barres qui partent de 0 $ : celle de SlabIQ monte, l'autre descend. C'est le resultat mesure au bout de
    12 mois, sans pretendre a un chemin en ligne droite ; « Voir mois par mois » montre le vrai chemin."""
    W, H, T, B = 600, 360, 84, 84
    m = max(abs(sans_fin), abs(avec_fin), 1) * 1.02
    y0 = T + (H - T - B) / 2
    k = (H - T - B) / 2 / m
    sg = lambda v: ("+" if v > 0 else "−" if v < 0 else "")
    xs, xa, bw = 190, 410, 112
    ha, hs = avec_fin * k, sans_fin * k

    def barre(x, h, cls, fill):
        y, hh = (y0 - h, h) if h >= 0 else (y0, -h)
        r = min(14, hh / 2)
        if h >= 0:      # coins ronds en haut
            d = f"M{x - bw / 2:.1f},{y0:.1f} V{y + r:.1f} Q{x - bw / 2:.1f},{y:.1f} {x - bw / 2 + r:.1f},{y:.1f} H{x + bw / 2 - r:.1f} Q{x + bw / 2:.1f},{y:.1f} {x + bw / 2:.1f},{y + r:.1f} V{y0:.1f} Z"
        else:           # coins ronds en bas
            yb = y0 + hh
            d = f"M{x - bw / 2:.1f},{y0:.1f} V{yb - r:.1f} Q{x - bw / 2:.1f},{yb:.1f} {x - bw / 2 + r:.1f},{yb:.1f} H{x + bw / 2 - r:.1f} Q{x + bw / 2:.1f},{yb:.1f} {x + bw / 2:.1f},{yb - r:.1f} V{y0:.1f} Z"
        return f'<path d="{d}" class="{cls}" fill="{fill}"/>'

    def etiq(x, v, nom_fr, nom_en, cls):
        if v >= 0:
            yv, yn = y0 - v * k - 14, y0 - v * k - 50
        else:
            yv, yn = y0 - v * k + 38, y0 - v * k + 62
        return (f'<text x="{x}" y="{yv:.1f}" class="{cls}"><tspan class="fr">{sg(v)}{fr(abs(v))} $</tspan><tspan class="en">{sg(v)}${en(abs(v))}</tspan></text>'
                f'<text x="{x}" y="{yn:.1f}" class="n"><tspan class="fr">{nom_fr}</tspan><tspan class="en">{nom_en}</tspan></text>')
    return f'''<svg class="sim-pente" viewBox="0 0 {W} {H}" role="img" aria-label="Profit after 12 months">
  <defs><linearGradient id="peP" x1="0" x2="0" y1="1" y2="0"><stop offset="0" stop-color="#9FE6D2"/><stop offset=".55" stop-color="#B79CF2"/><stop offset="1" stop-color="#F2B6D2"/></linearGradient>
  <linearGradient id="peS" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#8f95a3" stop-opacity=".55"/><stop offset="1" stop-color="#8f95a3" stop-opacity=".2"/></linearGradient>
  <filter id="peG" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="14"/></filter></defs>
  {barre(xa, ha, "b-glow", "url(#peP)").replace('class="b-glow"', 'class="b-glow" filter="url(#peG)"')}
  {barre(xs, hs, "b-sans", "url(#peS)")}{barre(xa, ha, "b-avec", "url(#peP)")}
  <line x1="{xs - bw / 2 - 40:.1f}" x2="{xa + bw / 2 + 40:.1f}" y1="{y0:.1f}" y2="{y0:.1f}" class="l-inv"/>
  <text x="{xs - bw / 2 - 48:.1f}" y="{y0 + 4:.1f}" class="ty"><tspan class="fr">0 $</tspan><tspan class="en">$0</tspan></text>
  {etiq(xs, sans_fin, "Sans SlabIQ", "Without SlabIQ", "v-s")}{etiq(xa, avec_fin, "Avec SlabIQ", "With SlabIQ", "v-a")}
  <text x="8" y="22" class="tx tl"><tspan class="fr">Au bout de 12 mois</tspan><tspan class="en">After 12 months</tspan></text>
</svg>'''


def bloc_vs(R, page):
    """23 nov 2026 (Mathieu : « ces comparatifs sur notre site, a la Apple : leger et en surface, comme les stats de leur
    laptop ; le meilleur que l'on puisse faire ») : seul ou avec SlabCoach, 3 gros chiffres et 2 barres chacun, entre
    <!--vs--> et <!--/vs--> sur l'accueil et sur la page SlabIQ. Tout vient du test (ui/slabiq_tests.json), avec les arrondis
    d'iq_publie : rien d'ecrit a la main. « Seul » = tous les achats de la meme periode (le « hasard » du test)."""
    pro, pha = iq_publie.pro(R)
    rv, rvh = iq_publie.revendue(R)
    x = iq_publie.fois(R)
    w_e = max(4, round(100 / R["x_ahaut_e"]))
    pmin = int(R["regles"]["prix_min"])

    def col(t_fr, t_en, chiffre, a_fr, a_en, wa, s_fr, s_en, s_val, ws):
        val = f' <em><span class="fr">{s_val} %</span><span class="en">{s_val}%</span></em>' if s_val is not None else ""
        return (f'<div class="cmp-c"><h3><span class="fr">{t_fr}</span><span class="en">{t_en}</span></h3><b class="cmp-n holo-t">{chiffre}</b>'
                f'<p class="cmp-l"><span><span class="fr">{a_fr}</span><span class="en">{a_en}</span></span></p><span class="cmp-t"><i class="cmp-a" style="--w:{wa}"></i></span>'
                f'<p class="cmp-l"><span><span class="fr">{s_fr}</span><span class="en">{s_en}</span></span>{val}</p><span class="cmp-t"><i class="cmp-s" style="--w:{ws}"></i></span></div>')
    cols = (col("Ta carte garde sa valeur", "Your card holds its value", f"{pro}<small>%</small>", "Avec le Radar Pro", "With the Pro Radar", pro, "Seul", "On your own", pha, pha)
            + col("Ta carte se revend", "Your card resells", f"{rv}<small>%</small>", "Avec le Radar Pro", "With the Pro Radar", rv, "Seul", "On your own", rvh, rvh)
            + col("Une A se revend plus qu’une E", "An A resells more than an E", f'{x}<small class="x">×</small>', "Carte A ou A+", "A or A+ card", 100, "Carte E", "E card", None, w_e))
    if page == "accueil":
        faits = (f'<span><b class="holo-t">{iq_publie.ventes_k(R)}</b> <span class="fr">ventes réelles apprises</span><span class="en">real sales learned</span></span>'
                 f'<span><b class="holo-t">{fr(R["joueurs"])}</b> <span class="fr">joueurs notés chaque semaine</span><span class="en">players rated every week</span></span>')
        liens = ('<a href="/slabiq#tests"><span class="fr">Voir le test ›</span><span class="en">See the test ›</span></a>'
                 '<a href="/slabiq#defi"><span class="fr">Fais le défi ›</span><span class="en">Take the challenge ›</span></a>'
                 '<a href="/slabiq"><span class="fr">Comment SlabIQ fonctionne ›</span><span class="en">How SlabIQ works ›</span></a>')
    else:
        acc_fr, acc_en, _ = iq_publie.accord(R)
        faits = (f'<span><b class="holo-t">{fr(R["ventes"])}</b> <span class="fr">ventes de hockey testées</span><span class="en">hockey sales tested</span></span>'
                 f'<span><b class="holo-t">{acc_fr}</b> <span class="fr">d’accord avec le marché</span><span class="en">agreement with the market</span></span>')
        liens = ""
    n, nh = R["pro"]["n"], R["hasard"]["n"]
    if page == "accueil":                       # l'accueil : l'essentiel ; les definitions completes sont sur la page SlabIQ
        note_fr = (f"Test du {jour_fr(R['le'])} sur des ventes jamais vues par SlabIQ : {fr(n)} achats du Radar Pro, contre les {fr(nh)} achats de "
                   f"{pmin} $ et plus de la même période (seul). Garde sa valeur : la même carte s’est revendue ensuite à au moins 90 % du prix payé. "
                   f"Les résultats passés ne garantissent pas les résultats futurs.")
        note_en = (f"Test of {jour_en(R['le'])} on sales SlabIQ had never seen: {en(n)} Pro Radar buys, versus the {en(nh)} buys of ${pmin} and up "
                   f"from the same period (on your own). Holds its value: the same card later resold for at least 90% of the price paid. "
                   f"Past results don’t guarantee future results.")
    else:
        note_fr = (f"Radar Pro : les {fr(n)} achats qu’il aurait montrés du {jour_fr(R['coupe'])} au {jour_fr(R['revente_des'])}. Seul : tous les achats "
                   f"de {pmin} $ et plus de la même période ({fr(nh)}), sans carte de base ni lot. Garde sa valeur : la même carte s’est revendue ensuite "
                   f"à au moins 90 % du prix payé ; jamais revendue : ratée. Se revend : elle s’est revendue avant le {jour_fr(R['revente_fin'])}. "
                   f"Les résultats passés ne garantissent pas les résultats futurs.")
        note_en = (f"Pro Radar: the {en(n)} buys it would have shown from {jour_en(R['coupe'])} to {jour_en(R['revente_des'])}. On your own: every buy "
                   f"of ${pmin} and up from the same period ({en(nh)}), no base cards or lots. Holds its value: the same card later resold for at "
                   f"least 90% of the price paid; never resold: a miss. Resells: it resold before {jour_en(R['revente_fin'])}. "
                   f"Past results don’t guarantee future results.")
    return (f'<!--vs--><div class="cmp">{cols}</div><div class="cmp-bas"><p class="cmp-faits">{faits}</p>'
            + (f'<p class="cmp-liens">{liens}</p>' if liens else "")
            + f'</div><p class="cmp-note"><span class="fr">{note_fr}</span><span class="en">{note_en}</span></p><!--/vs-->')


SIM_BOUTON = ('<button class="sim-mois" type="button" aria-expanded="false"><span class="fr">Voir mois par mois</span>'
              '<span class="en">See month by month</span></button>')


def ecrire(R, defi):
    sim = R["sim"]
    svg, serie, inv, sans, avec = graphique(sim)
    r_s, r_a = sim["r_sans"] * 100, sim["r_avec"] * 100
    ecart = int(round(sim["ecart"], -1))
    bat = round(sim["bat"] * 100)
    # 20 nov 2026 : les memes arrondis que la fenetre SlabIQ de l'app (iq_publie : une seule source, toujours vers le bas)
    x_ae = iq_publie.fois(R)
    k_ventes = iq_publie.ventes_k(R)
    pmin, pmax = int(sim["prix"][0]), int(sim["prix"][1])
    m0, m1 = sim["mois"][0], sim["mois"][-1]
    # 23 nov 2026 (Mathieu : « enleve, ca va porter a confusion ») : plus de graphique des reventes par lettre sur la page. Il
    # montrait A+ sous A : une A+ est plus rare et plus chere (1 130 $ en mediane contre 280 $), il y a moins de copies, donc moins
    # de reventes de la meme carte ; le graphique comptait les copies qui circulent, pas la valeur de la lettre, et laissait
    # croire qu'une A vaut mieux qu'une A+. La mesure reste dans ui/slabiq_tests.json (« lettres ») ; le site garde A et A+ contre E.
    le_fr, le_en = jour_fr(R["le"]).replace(f" {dt.date.fromisoformat(R['le']).year}", f" {dt.date.fromisoformat(R['le']).year}"), jour_en(R["le"])
    d_le = dt.date.fromisoformat(R["le"])
    kick_fr, kick_en = f"Nos tests · {d_le.day} {MFc[d_le.month - 1]} {d_le.year}", f"Our tests · {MEc[d_le.month - 1]} {d_le.day}, {d_le.year}"
    # 20 nov 2026 : le Radar Pro se mesure sur TOUS ses achats : reussi = revendue ET au moins 90 % du prix (jamais revendue = ratee) ;
    # le point de comparaison : les memes achats au hasard. Arrondi vers le bas : jamais plus que la mesure.
    pro, pha = iq_publie.pro(R)
    # 19 nov 2026 (Mathieu : « 80 % c'est plus beau que 79 ») : jamais un chiffre plus haut que la mesure ; a moins d'un point
    # sous un chiffre rond (multiple de 5), on ecrit « ≈ » (79,4 % -> « ≈ 80 % »)
    acc = round(R["accord"] * 100)
    seuil = {95: "A+", 88: "A", 86: "A", 82: "A-"}.get(int(sim["seuil"]), "A")

    # ---- la page SlabIQ
    p = os.path.join(UI, "site_slabiq.html")
    s = open(p, encoding="utf-8").read()
    s = sub1(s, r'(<div><b class="holo-t">)[^<]*(</b><span><span class="fr">ventes réelles apprises)', rf'\g<1>{k_ventes}\g<2>')
    s = majX(s, x_ae)
    s = sub1(s, r'(<div><b class="holo-t">)[^<]*(</b><span><span class="fr">joueurs notés chaque semaine)', rf'\g<1>{fr(R["joueurs"])}\g<2>')
    s = sub1(s, r'<p class="kicker holo-t"><span class="fr">Nos tests · [^<]*</span><span class="en">Our tests · [^<]*</span></p>',
             f'<p class="kicker holo-t"><span class="fr">{kick_fr}</span><span class="en">{kick_en}</span></p>')
    # 23 nov 2026 (Mathieu : « ces comparatifs sur notre site, a la Apple ») : les 3 tuiles des tests (ventes testees, accord,
    # Radar Pro) sont devenues le comparatif « seul ou avec SlabCoach » (bloc_vs) : tout le bloc est reecrit depuis le test
    s = sub1(s, r'<!--vs-->.*?<!--/vs-->', lambda m: bloc_vs(R, "slabiq"))
    sim_html = f'''<div class="sim">
    <div class="sim-chf">
      <div><span><span class="fr">Sans SlabIQ</span><span class="en">Without SlabIQ</span></span><b class="neg"><span class="fr">{pfr(r_s)}</span><span class="en">{pen(r_s)}</span></b></div>
      <div class="pr"><span><span class="fr">Avec SlabIQ</span><span class="en">With SlabIQ</span></span><b class="holo-t"><span class="fr">{pfr(r_a)}</span><span class="en">{pen(r_a)}</span></b></div>
      <div><span><span class="fr">Écart en 1 an</span><span class="en">Gap in 1 year</span></span><b class="holo-t"><span class="fr">≈ {fr(ecart)} $</span><span class="en">≈ ${en(ecart)}</span></b></div>
    </div>
    <div class="sim-g">{pente(sans[-1], avec[-1])}{svg}<div class="sim-tip" hidden></div></div>
    {SIM_BOUTON}
    <p class="sim-leg"><i class="k-a"></i><span class="fr">Avec SlabIQ</span><span class="en">With SlabIQ</span><i class="k-s"></i><span class="fr">Sans SlabIQ</span><span class="en">Without SlabIQ</span><i class="k-i"></i><span class="fr">0 $ : ni gain ni perte</span><span class="en">$0: break-even</span></p>
    <p class="sim-leg"><span class="fr">Le profit : la valeur des cartes (leurs reventes) moins l’argent mis.</span><span class="en">Profit: the cards’ value (their resales) minus the money spent.</span></p>
  </div>
  <script type="application/json" id="sim-data">{serie}</script>'''
    s = sub1(s, r'<div class="sim">.*?<script type="application/json" id="sim-data">[^<]*</script>', sim_html.replace("\\", "\\\\"))
    s = sub1(s, r'<p class="iq-note"><span class="fr">Simulation sur de vraies ventes eBay[^<]*</span><span class="en">Simulation on real eBay sales[^<]*</span></p>',
             f'<p class="iq-note"><span class="fr">Simulation sur de vraies ventes eBay ({mois_fr(m0)} à {mois_fr(m1)}) : 400 collectionneurs virtuels achètent chacun 500 $ de cartes de {pmin} à {pmax} $ par mois, au hasard ou seulement les cartes {seuil} et plus de SlabIQ (il dépense parfois moins, faute de cartes {seuil} ; l’argent non dépensé reste dans ses poches). La valeur finale : les reventes de la même carte après le {jour_fr(R["revente_des"])}. Médianes, avant frais de revente. SlabIQ fait mieux dans {bat} % des simulations. Les résultats passés ne garantissent pas les résultats futurs : selon tes achats, l’écart peut être plus petit ou plus grand, et tu peux perdre de l’argent. SlabIQ t’aide à choisir ; il ne garantit pas de gain.</span>'
             f'<span class="en">Simulation on real eBay sales ({mois_en(m0)} to {mois_en(m1)}): 400 virtual collectors each buy $500 of ${pmin}–${pmax} cards a month, at random or only SlabIQ {seuil} and up (they sometimes spend less, for lack of {seuil} cards; unspent money stays in their pocket). Final value: resales of the same card after {jour_en(R["revente_des"])}. Medians, before resale fees. SlabIQ does better in {bat}% of simulations. Past results don’t guarantee future results: depending on what you buy, the gap can be smaller or larger, and you can lose money. SlabIQ helps you choose; it doesn’t guarantee a gain.</span></p>')
    st_ = defi["stats"]
    g = st_["gagne"] * 100
    g_fr, g_en = ("100 %", "100%") if g >= 100 else (("plus de 99 %", "over 99%") if g >= 99 else (f"{int(g)} %", f"{int(g)}%"))
    pe = defi["periode"]
    s = sub1(s, r'<p class="iq-note"><span class="fr">Vraies cartes de hockey (?:vendues|achetées) sur eBay[^<]*</span><span class="en">Real hockey cards (?:sold|bought) on eBay[^<]*</span></p>',
             f'<p class="iq-note"><span class="fr">Vraies cartes de hockey achetées sur eBay du {jour_fr(pe[0])} au {jour_fr(pe[1])}, de 30 à 500 $. Le Radar Pro : les cartes que SlabIQ t’aurait montrées cette semaine-là, dans la même gamme de prix. « Revendue, valeur gardée » : la même carte s’est revendue entre le {jour_fr(pe[1])} et le {jour_fr(R["revente_fin"])} à au moins 90 % de son prix ; une carte qui ne s’est pas revendue compte comme ratée. Sur les {fr(st_["cartes"])} cartes du test, {round(st_["ok_marche"] * 100)} % prises au hasard ont gardé leur valeur, contre {round(st_["ok_radar"] * 100)} % des cartes du Radar Pro. Sur 20 000 parties simulées, SlabIQ garde en moyenne {str(st_["iq"]).replace(".", ",")} bonnes cartes sur 16, un choix au hasard {str(st_["hasard"]).replace(".", ",")}, et SlabIQ gagne {g_fr} des parties. Les résultats passés ne garantissent pas les résultats futurs.</span>'
             f'<span class="en">Real hockey cards bought on eBay from {jour_en(pe[0])} to {jour_en(pe[1])}, $30 to $500. The Pro Radar: the cards SlabIQ would have shown you that week, in the same price range. “Resold, value kept”: the same card resold between {jour_en(pe[1])} and {jour_en(R["revente_fin"])} for at least 90% of its price; a card that didn’t resell counts as a miss. Across the test’s {en(st_["cartes"])} cards, {round(st_["ok_marche"] * 100)}% picked at random held their value, versus {round(st_["ok_radar"] * 100)}% of Pro Radar cards. Over 20,000 simulated games, SlabIQ keeps {st_["iq"]} good cards out of 16 on average, a random pick {st_["hasard"]}, and SlabIQ wins {g_en} of games. Past results don’t guarantee future results.</span></p>')
    POOL = json.dumps({"pool": defi["pool"], "bandes": defi["bandes"], "stats": {k: st_[k] for k in ("ok_marche", "ok_radar")}}, ensure_ascii=False, separators=(",", ":"))
    s = sub1(s, r'<script type="application/json" id="defi-data">.*?</script>', f'<script type="application/json" id="defi-data">{POOL}</script>'.replace("\\", "\\\\"))
    # l'infobulle : le profit avec son signe ; plus de ligne « argent investi »
    vieux = "'</span><span><i class=\"k-s\"></i>' + nf(S.sans[i]) + '</span><span><i class=\"k-i\"></i>' + nf(S.inv[i]) + '</span>';"
    if vieux in s:
        s = s.replace(vieux, "'</span><span><i class=\"k-s\"></i>' + nf(S.sans[i]) + '</span>';")
        s = re.sub(r"var nf = function\(n\)\{ return EN \? '\$' \+ n\.toLocaleString\('en-US'\) : (n\.toLocaleString\('fr-CA'\)\.replace\([^;]*\) \+ ' \$'); \};",
                   lambda m: "var nf = function(n){ var sg = S.profit && n > 0 ? '+' : n < 0 ? '−' : ''; n = Math.abs(n); return sg + (EN ? '$' + n.toLocaleString('en-US') : " + m.group(1) + "); };", s)
    open(p, "w", encoding="utf-8").write(s)

    # ---- l'accueil : les memes chiffres
    p = os.path.join(UI, "site_accueil.html")
    s = open(p, encoding="utf-8").read()
    s = majX(s, x_ae)
    # 23 nov 2026 : la section SlabIQ de l'accueil = le comparatif « seul ou avec SlabCoach » (ventes apprises et joueurs dedans)
    s = sub1(s, r'<!--vs-->.*?<!--/vs-->', lambda m: bloc_vs(R, "accueil"))
    # 19 nov 2026 (Mathieu : « 5x ici, 10x la : attention, audit tout le site ») : une seule mesure partout (A et plus contre E)
    # 19 nov 2026 (audit) : « +780 $ avec SlabIQ » laissait croire a 780 $ de profit ; c'est l'ECART avec un achat au hasard
    # 20 nov 2026 (Mathieu : « vendeur d'un coup sec ») : le chiffre du defi, le plus parlant : une carte du Radar Pro contre une au hasard
    # 20 nov 2026 (Mathieu : « valide l'info, partout ») : la FAQ disait « 5 fois » (une A seule, ancienne mesure) : la meme mesure
    s = sub1(s, r'une carte A ou A\+ se revend [0-9]+ fois plus souvent qu’une E', f'une carte A ou A+ se revend {x_ae} fois plus souvent qu’une E')
    s = sub1(s, r'an A or A\+ card resells [0-9]+ times more often than an E', f'an A or A+ card resells {x_ae} times more often than an E')
    # 22 nov 2026 (rapport du tour complet : l'accueil disait 70 % / 8 % (le defi), la page SlabIQ 71 % / 11 % (le Radar Pro),
    # pour la MEME phrase) : une seule mesure partout, celle du Radar Pro (iq_publie.pro)
    open(p, "w", encoding="utf-8").write(s)
    R2 = {k: v for k, v in R.items() if k != "sim"}
    R2["sim"] = {k: v for k, v in sim.items() if k not in ("sans", "avec")}
    json.dump(R2, open(os.path.join(UI, "slabiq_tests.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("site ecrit :", {"ventes": k_ventes, "x_aplus_e": x_ae, "joueurs": R["joueurs"], "accord": acc, "pro": pro, "hasard": pha, "defi": st_, "ecart": ecart, "bat": bat})
