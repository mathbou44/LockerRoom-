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


def ecrire(R, defi):
    sim = R["sim"]
    svg, serie, inv, sans, avec = graphique(sim)
    r_s, r_a = sim["r_sans"] * 100, sim["r_avec"] * 100
    ecart = int(round(sim["ecart"], -1))
    bat = round(sim["bat"] * 100)
    x_ae = int(round(R["x_ahaut_e"]))
    k_ventes = f"{int(R['ventes_total'] // 5000 * 5)} k+"
    pmin, pmax = int(sim["prix"][0]), int(sim["prix"][1])
    m0, m1 = sim["mois"][0], sim["mois"][-1]
    L = R["lettres"]
    lets = [x for x in ORDRE if x in L]
    mx = max(L[x]["reventes"] for x in lets)
    bars = "".join(f'<div><em>{L[x]["reventes"]:.2f}'.replace(".", ",") + f'</em><s style="--h:{round(100 * L[x]["reventes"] / mx)}"></s><i>{x}</i></div>' for x in lets)
    inv_l = [(a, b) for i, a in enumerate(lets) for b in lets[i + 1:] if L[b]["reventes"] > L[a]["reventes"] * 1.03]
    if inv_l:
        ex_fr = ", ".join(f"{b} devant {a}" for a, b in inv_l[:3])
        ex_en = ", ".join(f"{b} ahead of {a}" for a, b in inv_l[:3])
        note_fr = f"Reventes de la même carte entre le {jour_fr(R['revente_des'])} et le {jour_fr(R['revente_fin'])}, par lettre (cartes vues avant). L’ordre n’est pas encore parfait ({ex_fr}) : on y travaille."
        note_en = f"Resales of the same card between {jour_en(R['revente_des'])} and {jour_en(R['revente_fin'])}, by letter (cards seen before). The order isn’t perfect yet ({ex_en}): we’re on it."
    else:
        note_fr = f"Reventes de la même carte après le {jour_fr(R['revente_des'])}, par lettre (cartes vues avant). Chaque lettre se revend plus que la suivante."
        note_en = f"Resales of the same card after {jour_en(R['revente_des'])}, by letter (cards seen before). Each letter resells more than the next."
    le_fr, le_en = jour_fr(R["le"]).replace(f" {dt.date.fromisoformat(R['le']).year}", f" {dt.date.fromisoformat(R['le']).year}"), jour_en(R["le"])
    d_le = dt.date.fromisoformat(R["le"])
    kick_fr, kick_en = f"Nos tests · {d_le.day} {MFc[d_le.month - 1]} {d_le.year}", f"Our tests · {MEc[d_le.month - 1]} {d_le.day}, {d_le.year}"
    pro, pav = round(R["pro"]["garde"] * 100), round(R["pro_avant"]["garde"] * 100)
    acc, aav = round(R["accord"] * 100), round(R["accord_avant"] * 100)
    # 19 nov 2026 (Mathieu : « 80 % c'est plus beau que 79 ») : jamais un chiffre plus haut que la mesure ; a moins d'un point
    # sous un chiffre rond (multiple de 5), on ecrit « ≈ » (79,4 % -> « ≈ 80 % »)
    rond = round(R["accord"] * 100 / 5) * 5
    acc_txt, acc_en = (f"≈ {rond} %", f"≈ {rond}%") if 0 < rond - R["accord"] * 100 < 1 else (f"{acc} %", f"{acc}%")
    seuil = {95: "A+", 88: "A", 86: "A", 82: "A-"}.get(int(sim["seuil"]), "A")

    # ---- la page SlabIQ
    p = os.path.join(UI, "site_slabiq.html")
    s = open(p, encoding="utf-8").read()
    s = sub1(s, r'(<div><b class="holo-t">)[^<]*(</b><span><span class="fr">ventes réelles apprises)', rf'\g<1>{k_ventes}\g<2>')
    s = majX(s, x_ae)
    s = sub1(s, r'(<div><b class="holo-t">)[^<]*(</b><span><span class="fr">joueurs notés chaque semaine)', rf'\g<1>{fr(R["joueurs"])}\g<2>')
    s = sub1(s, r'<p class="kicker holo-t"><span class="fr">Nos tests · [^<]*</span><span class="en">Our tests · [^<]*</span></p>',
             f'<p class="kicker holo-t"><span class="fr">{kick_fr}</span><span class="en">{kick_en}</span></p>')
    s = sub1(s, r'(<div><b class="holo-t">)[^<]*(</b><span><span class="fr">ventes de hockey testées)', rf'\g<1>{fr(R["ventes"])}\g<2>')
    s = sub1(s, r'<div><b class="holo-t">[^<]*</b><span><span class="fr">d’accord avec le marché \(avant : [^)]*\)</span><span class="en">agreement with the market \(before: [^)]*\)</span></span></div>',
             f'<div><b class="holo-t">{acc_txt}</b><span><span class="fr">d’accord avec le marché (avant : {aav} %)</span><span class="en">agreement with the market (before: {aav}%)</span></span></div>')
    s = sub1(s, r'<div><b class="holo-t">[^<]*</b><span><span class="fr">des cartes du Radar Pro gardent leur valeur \(avant : [^)]*\)</span><span class="en">of Pro Radar cards hold their value \(before: [^)]*\)</span></span></div>',
             f'<div><b class="holo-t">{pro} %</b><span><span class="fr">des cartes du Radar Pro gardent leur valeur (avant : {pav} %)</span><span class="en">of Pro Radar cards hold their value (before: {pav}%)</span></span></div>')
    s = sub1(s, r'<div class="iq-bars" role="img" aria-label="Reventes par lettre">.*?</div></div>(\s*<p class="iq-note">)',
             f'<div class="iq-bars" role="img" aria-label="Reventes par lettre">{bars}</div>\\g<1>')
    s = sub1(s, r'<p class="iq-note"><span class="fr">Reventes de la même carte (?:après|entre)[^<]*</span><span class="en">Resales of the same card (?:after|between)[^<]*</span></p>',
             f'<p class="iq-note"><span class="fr">{note_fr}</span><span class="en">{note_en}</span></p>')
    sim_html = f'''<div class="sim">
    <div class="sim-chf">
      <div><span><span class="fr">Sans SlabIQ</span><span class="en">Without SlabIQ</span></span><b class="neg"><span class="fr">{pfr(r_s)}</span><span class="en">{pen(r_s)}</span></b></div>
      <div class="pr"><span><span class="fr">Avec SlabIQ</span><span class="en">With SlabIQ</span></span><b class="holo-t"><span class="fr">{pfr(r_a)}</span><span class="en">{pen(r_a)}</span></b></div>
      <div><span><span class="fr">Écart en 1 an</span><span class="en">Gap in 1 year</span></span><b class="holo-t"><span class="fr">≈ {fr(ecart)} $</span><span class="en">≈ ${en(ecart)}</span></b></div>
    </div>
    <div class="sim-g">{svg}<div class="sim-tip" hidden></div></div>
    <p class="sim-leg"><i class="k-a"></i><span class="fr">Avec SlabIQ</span><span class="en">With SlabIQ</span><i class="k-s"></i><span class="fr">Sans SlabIQ</span><span class="en">Without SlabIQ</span><i class="k-i"></i><span class="fr">0 $ : ni gain ni perte</span><span class="en">$0: break-even</span></p>
    <p class="sim-leg"><span class="fr">Le profit : la valeur des cartes (leurs reventes) moins l’argent mis.</span><span class="en">Profit: the cards’ value (their resales) minus the money spent.</span></p>
  </div>
  <script type="application/json" id="sim-data">{serie}</script>'''
    s = sub1(s, r'<div class="sim">.*?<script type="application/json" id="sim-data">[^<]*</script>', sim_html.replace("\\", "\\\\"))
    s = sub1(s, r'<p class="iq-note"><span class="fr">Simulation sur de vraies ventes eBay[^<]*</span><span class="en">Simulation on real eBay sales[^<]*</span></p>',
             f'<p class="iq-note"><span class="fr">Simulation sur de vraies ventes eBay ({mois_fr(m0)} à {mois_fr(m1)}) : 400 collectionneurs virtuels achètent chacun 500 $ de cartes de {pmin} à {pmax} $ par mois, au hasard ou seulement les cartes {seuil} et plus de SlabIQ (la règle du Radar Pro : il dépense parfois moins, faute de cartes {seuil} ; l’argent non dépensé reste dans ses poches). La valeur finale : les reventes de la même carte après le {jour_fr(R["revente_des"])}. Médianes, avant frais de revente. SlabIQ fait mieux dans {bat} % des simulations. Les résultats passés ne garantissent pas les résultats futurs : selon tes achats, l’écart peut être plus petit ou plus grand, et tu peux perdre de l’argent. SlabIQ t’aide à choisir ; il ne garantit pas de gain.</span>'
             f'<span class="en">Simulation on real eBay sales ({mois_en(m0)} to {mois_en(m1)}): 400 virtual collectors each buy $500 of ${pmin}–${pmax} cards a month, at random or only SlabIQ {seuil} and up (the Pro Radar rule: they sometimes spend less, for lack of {seuil} cards; unspent money stays in their pocket). Final value: resales of the same card after {jour_en(R["revente_des"])}. Medians, before resale fees. SlabIQ does better in {bat}% of simulations. Past results don’t guarantee future results: depending on what you buy, the gap can be smaller or larger, and you can lose money. SlabIQ helps you choose; it doesn’t guarantee a gain.</span></p>')
    st_ = defi["stats"]
    mm = defi["mois"]
    s = sub1(s, r'<p class="iq-note"><span class="fr">Vraies cartes de hockey vendues sur eBay de[^<]*</span><span class="en">Real hockey cards sold on eBay from[^<]*</span></p>',
             f'<p class="iq-note"><span class="fr">Vraies cartes de hockey vendues sur eBay de {mois_fr(mm[0])} à {mois_fr(mm[-1])}. « A gardé sa valeur » : la même carte s’est revendue entre le {jour_fr(R["revente_des"])} et le {jour_fr(R["revente_fin"])} à au moins 90 % de son prix. Sur 20 000 parties simulées, SlabIQ garde plus de bonnes cartes qu’un choix au hasard {round(st_["gagne"] * 100)} % du temps (égalité {round(st_["egal"] * 100)} %).</span>'
             f'<span class="en">Real hockey cards sold on eBay from {mois_en(mm[0])} to {mois_en(mm[-1])}. “Held its value”: the same card resold between {jour_en(R["revente_des"])} and {jour_en(R["revente_fin"])} for at least 90% of its price. Over 20,000 simulated games, SlabIQ keeps more good cards than a random pick {round(st_["gagne"] * 100)}% of the time (tie {round(st_["egal"] * 100)}%).</span></p>')
    POOL = json.dumps({"pool": defi["pool"], "mois": defi["mois"], "bandes": defi["bandes"]}, ensure_ascii=False, separators=(",", ":"))
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
    s = sub1(s, r'(<div><b class="holo-t">)[^<]*(</b><span><span class="fr">ventes réelles apprises)', rf'\g<1>{k_ventes}\g<2>')
    s = majX(s, x_ae)
    s = sub1(s, r'(<div><b class="holo-t">)[^<]*(</b><span><span class="fr">joueurs notés chaque semaine)', rf'\g<1>{fr(R["joueurs"])}\g<2>')
    # 19 nov 2026 (Mathieu : « 5x ici, 10x la : attention, audit tout le site ») : une seule mesure partout (A et plus contre E)
    # 19 nov 2026 (audit) : « +780 $ avec SlabIQ » laissait croire a 780 $ de profit ; c'est l'ECART avec un achat au hasard
    s = sub1(s, r'<a class="iqp-test" href="/slabiq#defi"><b class="holo-t">.*?</b><span><span class="fr">[^<]*</span><span class="en">[^<]*</span></span>',
             f'<a class="iqp-test" href="/slabiq#defi"><b class="holo-t"><span class="fr">+{fr(ecart)} $</span><span class="en">+${en(ecart)}</span></b><span><span class="fr">de plus en 1 an qu’en achetant au hasard, pour un collectionneur à 500 $ par mois. Et toi, ferais-tu mieux ?</span><span class="en">more in 1 year than buying at random, for a collector spending $500 a month. Could you do better?</span></span>')
    open(p, "w", encoding="utf-8").write(s)
    R2 = {k: v for k, v in R.items() if k != "sim"}
    R2["sim"] = {k: v for k, v in sim.items() if k not in ("sans", "avec")}
    json.dump(R2, open(os.path.join(UI, "slabiq_tests.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("site ecrit :", {"ventes": k_ventes, "x_aplus_e": x_ae, "joueurs": R["joueurs"], "accord": acc, "pro": pro, "ecart": ecart, "bat": bat})
