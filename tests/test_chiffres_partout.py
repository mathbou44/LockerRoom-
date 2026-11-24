"""22 nov 2026 (Mathieu : « a chaque fois qu'on fait une mise a jour de SlabIQ, tout ce qui en parle doit etre mis a jour, sinon on va
avoir une discordance d'informations ») : chaque chiffre SlabIQ du site = le dernier test (ui/slabiq_tests.json), le meme que l'app
lit (iq_publie). Echoue des qu'une page affiche autre chose : on refait outils/tests_site.py --ecrire avant de pousser."""
import json, os, re, sys
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ICI)
import iq_publie

R = json.load(open(os.path.join(ICI, "ui", "slabiq_tests.json"), encoding="utf-8"))
acc_fr, acc_en, _ = iq_publie.accord(R)
pro, pha = iq_publie.pro(R)
x = iq_publie.fois(R)
k = iq_publie.ventes_k(R)
nb = f"{R['ventes']:,}".replace(",", " ")
lire = lambda f: open(os.path.join(ICI, "ui", f), encoding="utf-8").read()
acc, sl = lire("site_accueil.html"), lire("site_slabiq.html")
pub = iq_publie.publics()
erreurs = []


def doit(page, nom, motif, texte):
    if not re.search(motif, texte):
        erreurs.append(f"{page} : {nom} ne montre pas le dernier test ({motif})")


# 23 nov 2026 (Mathieu : « ces comparatifs sur notre site, a la Apple ») : le Radar Pro (garde sa valeur, se revend), « seul » et
# A contre E sont dans le comparatif des deux pages (outils/site_iq.bloc_vs) ; les ventes apprises, les joueurs, les ventes testees
# et l'accord sont juste dessous
rv, rvh = iq_publie.revendue(R)
for page, t in (("accueil", acc), ("slabiq", sl)):
    doit(page, "Radar Pro, garde sa valeur", rf'<b class="cmp-n holo-t">{pro}<small>%</small></b>.*?<span class="fr">Seul</span>.*?<span class="fr">{pha} %</span>', t)
    doit(page, "Radar Pro, se revend", rf'<b class="cmp-n holo-t">{rv}<small>%</small></b>.*?<span class="fr">Seul</span>.*?<span class="fr">{rvh} %</span>', t)
    doit(page, "A et A+ contre E (comparatif)", rf'<b class="cmp-n holo-t">{x}<small class="x">×</small></b>', t)
    for m in re.findall(r'<b class="cmp-n holo-t">([0-9]+)<small>%', t):
        if int(m) not in (pro, rv):
            erreurs.append(f"{page} : un « {m} % » dans le comparatif qui n'est pas dans le dernier test")
# l'accueil
doit("accueil", "ventes apprises", rf'<b class="holo-t">{re.escape(k)}</b> ventes réelles apprises</span><span class="en"><b class="holo-t">{re.escape(k)}</b> real sales learned', acc)
doit("accueil", "A et A+ contre E", rf'une carte A ou A\+ se revend {x} fois plus souvent', acc)
for m in re.findall(r'<b class="holo-t">([0-9]+)×</b><span><span class="fr">plus de reventes', acc + sl):
    if int(m) != x:
        erreurs.append(f"un « {m}× plus de reventes » au lieu de {x}×")
for m in re.findall(r'<b class="holo-t">([^<]*)</b>(?:<span><span class="fr">| )ventes réelles apprises', acc + sl):
    if m != k:
        erreurs.append(f"« {m} ventes réelles apprises » au lieu de {k}")
# la page SlabIQ
# 23 nov 2026 (Mathieu : « oui corrige ») : chaque chiffre dans les deux langues (« 180 519 » / « 180,519 », « 76 % » / « 76% »)
nb_en = f"{R['ventes']:,}"
doit("slabiq", "ventes testees", rf'<b class="holo-t">{re.escape(nb)}</b> ventes de hockey testées</span><span class="en"><b class="holo-t">{re.escape(nb_en)}</b> hockey sales tested', sl)
doit("slabiq", "accord", rf'<b class="holo-t">{re.escape(acc_fr)}</b> d’accord avec le marché</span><span class="en"><b class="holo-t">{re.escape(acc_en)}</b> agreement with the market', sl)
for page, t in (("accueil", acc), ("slabiq", sl)):                # jamais un nombre a la francaise dans une phrase anglaise du comparatif
    bloc = t[t.index("<!--vs-->"):t.index("<!--/vs-->")]
    for m in re.findall(r'<span class="en">((?:(?!</span>).)*)</span>', bloc):
        if re.search(r"\d \d{3}\b|\d\s%", m):
            erreurs.append(f"{page} : un nombre a la francaise en anglais : « {m[:60]} »")
if "(avant :" in sl.split("d’accord avec le marché")[1][:20]:
    erreurs.append("slabiq : l'accord montre encore « (avant : X %) »")
# l'app lit les memes chiffres
assert pub and pub.get("le") == R["le"], pub
assert not erreurs, "\n".join(erreurs)
print("CHIFFRES PARTOUT OK", {"ventes": nb, "accord": acc_fr, "pro": pro, "hasard": pha, "fois": x})
