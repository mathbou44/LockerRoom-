"""
SLABCOACH - ecrire les resultats des tests de SlabIQ sur le site (19 nov 2026).

Chaque chiffre de SlabIQ du site vient de lrtest/ui/slabiq_tests.json (outils/tests_site.py) : la meme valeur partout
(accueil et page SlabIQ). Chaque remplacement doit trouver exactement sa place, sinon on arrete (rien a moitie ecrit).
"""
import datetime as dt
import json
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


XFR, XEN = "plus de reventes pour une carte A ou A+ que pour une E", "more resales for an A or A+ card than an E"


def majX(s, x):
    """Chaque « N× plus de reventes » du site : la meme mesure, la meme phrase."""
    motifs = (r'<b class="holo-t">(?:<span class="fr">)?[0-9]+×(?:</span><span class="en">[0-9]+×</span>)?</b><span><span class="fr">plus de reventes pour [^<]*</span><span class="en">more resales for [^<]*</span></span>',)
    nouveau, k = re.subn(motifs[0], f'<b class="holo-t">{x}×</b><span><span class="fr">{XFR}</span><span class="en">{XEN}</span></span>', s)
    if not k:
        raise SystemExit("site_iq : aucune mesure « plus de reventes » trouvee")
    return nouveau


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
    # 23 nov 2026 (Mathieu : « oui corrige ») : en anglais, les faits s'ecrivaient a la francaise (« 180 519 », « 76 % ») : chaque
    # chiffre est maintenant ecrit dans les deux langues (« 180,519 », « 76% »)
    def fait(n_fr, n_en, t_fr, t_en):
        return f'<span><span class="fr"><b class="holo-t">{n_fr}</b> {t_fr}</span><span class="en"><b class="holo-t">{n_en}</b> {t_en}</span></span>'
    if page == "accueil":
        faits = (fait(iq_publie.ventes_k(R), iq_publie.ventes_k(R), "ventes réelles apprises", "real sales learned")
                 + fait(fr(R["joueurs"]), en(R["joueurs"]), "joueurs notés chaque semaine", "players rated every week"))
        liens = ('<a href="/slabiq#tests"><span class="fr">Voir le test ›</span><span class="en">See the test ›</span></a>'
                 '<a href="/slabiq#defi"><span class="fr">Fais le défi ›</span><span class="en">Take the challenge ›</span></a>'
                 '<a href="/slabiq"><span class="fr">Comment SlabIQ fonctionne ›</span><span class="en">How SlabIQ works ›</span></a>')
    else:
        acc_fr, acc_en, _ = iq_publie.accord(R)
        faits = (fait(fr(R["ventes"]), en(R["ventes"]), "ventes de hockey testées", "hockey sales tested")
                 + fait(acc_fr, acc_en, "d’accord avec le marché", "agreement with the market"))
        liens = ""
    n, nh = R["pro"]["n"], R["hasard"]["n"]
    # 24 nov 2026 (Mathieu choisit « deux rangees ») : le Radar Pro montre aussi « Tres recherchees », sans la preuve de revente ;
    # la mesure est celle de la rangee « A la une » (la regle de liquidite.py) : le site le dit en toutes lettres
    if page == "accueil":                       # l'accueil : l'essentiel ; les definitions completes sont sur la page SlabIQ
        note_fr = (f"Test du {jour_fr(R['le'])} sur des ventes jamais vues par SlabIQ : {fr(n)} achats « À la une » du Radar Pro, contre les {fr(nh)} achats de "
                   f"{pmin} $ et plus de la même période (seul). Garde sa valeur : la même carte s’est revendue ensuite à au moins 90 % du prix payé. "
                   f"Les résultats passés ne garantissent pas les résultats futurs.")
        note_en = (f"Test of {jour_en(R['le'])} on sales SlabIQ had never seen: {en(n)} “Top cards” buys of the Pro Radar, versus the {en(nh)} buys of ${pmin} and up "
                   f"from the same period (on your own). Holds its value: the same card later resold for at least 90% of the price paid. "
                   f"Past results don’t guarantee future results.")
    else:
        note_fr = (f"Radar Pro : les {fr(n)} achats que sa rangée « À la une » aurait montrés du {jour_fr(R['coupe'])} au {jour_fr(R['revente_des'])}. Seul : tous les achats "
                   f"de {pmin} $ et plus de la même période ({fr(nh)}), sans carte de base ni lot. Garde sa valeur : la même carte s’est revendue ensuite "
                   f"à au moins 90 % du prix payé ; jamais revendue : ratée. Se revend : elle s’est revendue avant le {jour_fr(R['revente_fin'])}. "
                   f"Les résultats passés ne garantissent pas les résultats futurs.")
        note_en = (f"Pro Radar: the {en(n)} buys its “Top cards” row would have shown from {jour_en(R['coupe'])} to {jour_en(R['revente_des'])}. On your own: every buy "
                   f"of ${pmin} and up from the same period ({en(nh)}), no base cards or lots. Holds its value: the same card later resold for at "
                   f"least 90% of the price paid; never resold: a miss. Resells: it resold before {jour_en(R['revente_fin'])}. "
                   f"Past results don’t guarantee future results.")
    return (f'<!--vs--><div class="cmp">{cols}</div><div class="cmp-bas"><p class="cmp-faits">{faits}</p>'
            + (f'<p class="cmp-liens">{liens}</p>' if liens else "")
            + f'</div><p class="cmp-note"><span class="fr">{note_fr}</span><span class="en">{note_en}</span></p><!--/vs-->')


def ecrire(R, defi):
    # 23 nov 2026 (Mathieu, devant le graphique « un budget de cartes par mois pendant 1 an, avec ou sans SlabIQ » : « c'est quoi, avant
    # frais ? ca vaut la peine qu'on le garde ? » ; puis « oui » a « je l'enleve ? ») : la simulation d'un an N'EST PLUS sur le site.
    # 1) elle affichait un profit AVANT frais eBay : +350 $ avec SlabIQ, -277 $ seul ; apres frais (13,25 % + 0,40 $ par carte) :
    #    -412 $ et -1 048 $ ; 2) ses lettres sont fixees avec les ventes jusqu'a la mi-octobre 2026 alors qu'elle « achete » des
    #    novembre 2025 (SlabIQ connait une partie de la suite) ; le test rejoue aux dates passees, frais compris
    #    (outils/mega_test.py), ne prouve aucun profit de revente ; 3) la promesse de SlabCoach est « acheter et vendre au bon
    #    moment », pas le profit de revente. A sa place, en haut de la page SlabIQ : le comparatif mesure (bloc_vs).
    # La mesure reste calculee (tests_site.py) et gardee dans ui/slabiq_tests.json (« sim »), pour la recherche seulement.
    # tests/test_site_sans_simulation.py interdit son retour sur le site.
    sim = R["sim"]
    # 20 nov 2026 : les memes arrondis que la fenetre SlabIQ de l'app (iq_publie : une seule source, toujours vers le bas)
    x_ae = iq_publie.fois(R)
    k_ventes = iq_publie.ventes_k(R)
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
    st_ = defi["stats"]
    g = st_["gagne"] * 100
    g_fr, g_en = ("100 %", "100%") if g >= 100 else (("plus de 99 %", "over 99%") if g >= 99 else (f"{int(g)} %", f"{int(g)}%"))
    pe = defi["periode"]
    s = sub1(s, r'<p class="iq-note"><span class="fr">Vraies cartes de hockey (?:vendues|achetées) sur eBay[^<]*</span><span class="en">Real hockey cards (?:sold|bought) on eBay[^<]*</span></p>',
             f'<p class="iq-note"><span class="fr">Vraies cartes de hockey achetées sur eBay du {jour_fr(pe[0])} au {jour_fr(pe[1])}, de 30 à 500 $. Le Radar Pro : les cartes « À la une » que SlabIQ t’aurait montrées cette semaine-là, dans la même gamme de prix. « Revendue, valeur gardée » : la même carte s’est revendue entre le {jour_fr(pe[1])} et le {jour_fr(R["revente_fin"])} à au moins 90 % de son prix ; une carte qui ne s’est pas revendue compte comme ratée. Sur les {fr(st_["cartes"])} cartes du test, {round(st_["ok_marche"] * 100)} % prises au hasard ont gardé leur valeur, contre {round(st_["ok_radar"] * 100)} % des cartes du Radar Pro. Sur 20 000 parties simulées, SlabIQ garde en moyenne {str(st_["iq"]).replace(".", ",")} bonnes cartes sur 16, un choix au hasard {str(st_["hasard"]).replace(".", ",")}, et SlabIQ gagne {g_fr} des parties. Les résultats passés ne garantissent pas les résultats futurs.</span>'
             f'<span class="en">Real hockey cards bought on eBay from {jour_en(pe[0])} to {jour_en(pe[1])}, $30 to $500. The Pro Radar: the “Top cards” SlabIQ would have shown you that week, in the same price range. “Resold, value kept”: the same card resold between {jour_en(pe[1])} and {jour_en(R["revente_fin"])} for at least 90% of its price; a card that didn’t resell counts as a miss. Across the test’s {en(st_["cartes"])} cards, {round(st_["ok_marche"] * 100)}% picked at random held their value, versus {round(st_["ok_radar"] * 100)}% of Pro Radar cards. Over 20,000 simulated games, SlabIQ keeps {st_["iq"]} good cards out of 16 on average, a random pick {st_["hasard"]}, and SlabIQ wins {g_en} of games. Past results don’t guarantee future results.</span></p>')
    POOL = json.dumps({"pool": defi["pool"], "bandes": defi["bandes"], "stats": {k: st_[k] for k in ("ok_marche", "ok_radar")}}, ensure_ascii=False, separators=(",", ":"))
    s = sub1(s, r'<script type="application/json" id="defi-data">.*?</script>', f'<script type="application/json" id="defi-data">{POOL}</script>'.replace("\\", "\\\\"))
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
    print("site ecrit :", {"ventes": k_ventes, "x_aplus_e": x_ae, "joueurs": R["joueurs"], "accord": acc, "pro": pro, "hasard": pha, "defi": st_})
