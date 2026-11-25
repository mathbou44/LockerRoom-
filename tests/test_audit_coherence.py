"""24 nov 2026 (Mathieu : « Repasse chaque fonction et calcul. Il faut un audit intense de l'app et du site ») : ce qui est ecrit
deux fois (dans le serveur et dans l'app) doit dire la meme chose, sinon l'ecran et le serveur ne s'entendent plus sur une
lettre SlabIQ ou sur un profit. Et l'audit du site tourne avec la suite (outils/audit_site.py)."""
import json, os, re, subprocess, sys
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
for k in [k for k in os.environ if k.startswith("LR_")]:
    os.environ.pop(k)
import bareme_iq, deals, watchlist
s = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()

# 1. les lettres SlabIQ : les memes seuils dans l'app et au serveur, pour chaque note de 0 a 100
m = re.search(r"const NOTES_IQ = (\[\[.*?\]\]);", s)
notes = json.loads(m.group(1).replace("'", '"').replace("-1e9", "-1000000000"))
def lettre_app(n):
    return next(l for seuil, l in notes if n >= seuil)
for n in [x / 2 for x in range(0, 201)]:
    assert lettre_app(n) == bareme_iq.lettre(n), (n, lettre_app(n), bareme_iq.lettre(n))
assert [l for _, l in notes] == ["A+", "A", "A-", "B+", "B", "C", "D", "E"]
# 2. la revente d'un deal : les memes chiffres des deux cotes (frais, port moyen, materiel, profit minimum, taxe par defaut)
def js(nom):
    return float(re.search(r"\b" + nom + r" = ([0-9.]+)", s).group(1))
assert abs(js("FRAIS_DEAL") - deals.FRAIS_PCT) < 1e-9 and abs(js("PORT_REVENTE") - deals.PORT_REVENTE) < 1e-9
assert abs(js("ENVOI_NET") - deals.ENVOI_NET) < 1e-9 and abs(js("PROFIT_MIN_DEAL") - deals.PROFIT_MIN) < 1e-9
assert abs(js("PROFIT_MIN_D") - deals.PROFIT_MIN_D) < 1e-9 and abs(js("TAXE_ACHAT") - deals.TAXE_ACHAT) < 1e-9
assert "const portEff = (p) => p == null ? %d : (p || 0);" % deals.PORT_INCONNU in s
# la meme formule : ce qui reste d'une revente, et le plus a payer
assert "const netDeal = (valeur) => valeur > 0 ? valeur - FRAIS_DEAL * (valeur + PORT_REVENTE) - ENVOI_NET : 0;" in s
assert "return Math.max(0, Math.min(net / (1 + p), net - d) / (1 + txA(taxe)));" in s
for v in (27, 80, 400):
    net = v - js("FRAIS_DEAL") * (v + js("PORT_REVENTE")) - js("ENVOI_NET")
    pm = max(0, min(net / (1 + js("PROFIT_MIN_DEAL")), net - js("PROFIT_MIN_D")) / (1 + js("TAXE_ACHAT")))
    assert abs(net - deals.net_revente(v)) < 0.006 and abs(pm - deals.prix_max(v)) < 0.006, v
# 3. le guide du bon prix : +15 % pour la negociation, des deux cotes
assert abs(js("NEGO") - 0.15) < 1e-9
# 4. « A liquider » sous 20 $ : l'ecran dit le seuil que le serveur applique
import lockerroom
assert lockerroom.LIQUIDER_PRIX == 20.0 and "argentCourt(v.liquider_prix || 20)" in s
assert (lockerroom.LIQUIDER_J, lockerroom.LIQUIDER_TOUT_J) == (60, 90)
# 4 b. la page des tarifs dit les limites que le serveur applique, et un seul prix partout
import forfaits
tarifs = open(os.path.join(RACINE, "ui", "site_tarifs.html"), encoding="utf-8").read()
L = forfaits.LIMITES
A = lockerroom.Api
for texte in (f"{L['valeur_jour']} recherches de cartes par jour", f"{L['valeur_jour']} card searches per day",
              f"Le Radar : {A.RADAR_GRATUIT} cartes, dont ses {A.RADAR_GRATUIT_TOP} meilleures, et {L['radar_semaine']} recherches par semaine",
              f"{L['annonces_mois']} annonces par mois", f"{L['annonces_mois']} listings per month",
              f"{L['breaks_produits']} produit", f"{L['offres_jour']} par jour", f"{forfaits.ESSAI_JOURS} jours offerts", f"{forfaits.ESSAI_JOURS} days free", f"The Radar: {A.RADAR_GRATUIT} cards, including its {A.RADAR_GRATUIT_TOP} best, and {L['radar_semaine']} searches a week"):
    assert texte in tarifs, texte
P, PA = forfaits.PRIX_PRO, forfaits.PRIX_PRO_ANNUEL                     # 24 nov 2026 : 8,99 $ ; 7,19 $ avec l'engagement d'un an (−20 %)
assert (P, PA, forfaits.RABAIS_ANNUEL, forfaits.ECONOMIE_ANNUEL) == (8.99, 7.19, 0.20, 21.6)
fr = lambda v: ("%.2f" % v).replace(".", ",") + " $"
en = lambda v: "$%.2f" % v
prix = set()
for nom in ("site_accueil.html", "site_slabiq.html", "site_tarifs.html", "conditions.html", "support.html"):
    h = open(os.path.join(RACINE, "ui", nom), encoding="utf-8").read()
    prix |= set(re.findall(r"(?<![\d,.])(\d{1,2}[,.]\d{2})(?:\s?\$|\b)(?=[^<]{0,40}(?:mois|month|ann|year))", h)) | set(re.findall(r"\$(\d{1,2}\.\d{2})", h))
assert {x.replace(",", ".") for x in prix} <= {"%.2f" % P, "%.2f" % PA, "21.60"}, prix      # aucun ancien prix ne traine
for nom in ("site_accueil.html", "site_slabiq.html", "site_tarifs.html"):
    h = open(os.path.join(RACINE, "ui", nom), encoding="utf-8").read()
    assert fr(P) in h and en(P) in h and "7,99" not in h and "7.99" not in h and "5,99" not in h and "5.99" not in h, nom
assert fr(PA) in tarifs and en(PA) in tarifs and "−%d %%" % round(forfaits.RABAIS_ANNUEL * 100) in tarifs and "−%d%%" % round(forfaits.RABAIS_ANNUEL * 100) in tarifs
assert "21,60 $ d’économie sur l’année" in tarifs and "Save $21.60 over the year" in tarifs and "24 $" not in tarifs
assert abs(round(1 - PA / P, 2) - forfaits.RABAIS_ANNUEL) < 1e-9
slabiq = open(os.path.join(RACINE, "ui", "site_slabiq.html"), encoding="utf-8").read()
assert 1.9 < P * 12 / 52 < 2.2 and "Environ 2 $ par semaine." in slabiq and "About $2 a week." in slabiq and "Moins de 2 $" not in slabiq     # 2,07 $ : plus « moins de 2 $ »
cond = open(os.path.join(RACINE, "ui", "conditions.html"), encoding="utf-8").read()
assert "8,99 $ CA par mois" in cond and "CA$8.99 per month" in cond
srv = open(os.path.join(RACINE, "server.py"), encoding="utf-8").read()
assert "Pro à 8,99 $ CA par mois. 14 jours de Pro offerts" in srv and "$8.99 CAD a month" in srv
# le forfait annuel ne se montre sur le site que s'il s'achete (STRIPE_PRIX_PRO_ANNUEL) : sinon « .si-annuel » est cache
assert ".si-annuel{display:none !important}" in srv and 'class="forfait pro si-annuel"' in tarifs and '<span class="si-annuel">' in slabiq
# 4 c. SlabIQ : les chiffres du site sont ceux des tests consignes (ui/slabiq_tests.json, ui/slabiq_bulletin.json), jamais plus
T = json.load(open(os.path.join(RACINE, "ui", "slabiq_tests.json"), encoding="utf-8"))
B = json.load(open(os.path.join(RACINE, "ui", "slabiq_bulletin.json"), encoding="utf-8"))
assert T["ventes"] <= T["ventes_total"] and 0.5 < T["accord"] < 1 and 0.5 < T["rho"] <= 1 and T["accord"] >= T["accord_avant"]
MESURES = [T["accord"], T["accord_avant"], T["rho"], T["pro"]["reussi"], T["hasard"]["reussi"]]
for l in B["lignes"]:                                    # les 5 tests rejoues : chaque point du graphique est un test consigne
    MESURES += [l["accord"], l["pro"]["reussi"], l["hasard"]["reussi"]]
assert len(B["lignes"]) == 5 and all(l["pro"]["reussi"] > l["hasard"]["reussi"] for l in B["lignes"])      # « l'emporte 5 fois sur 5 »
assert abs(B["lignes"][-1]["pro"]["reussi"] - T["pro"]["reussi"]) < 1e-9 and B["lignes"][-1]["ventes"] == T["ventes"]
for nom in ("site_accueil.html", "site_slabiq.html", "site_tarifs.html", "site_apropos.html"):
    h = re.sub(r"<(script|style)\b[\s\S]*?</\1>", " ", open(os.path.join(RACINE, "ui", nom), encoding="utf-8").read())
    for m in re.finditer(r"(\d{3})[\s  ,](\d{3})\s*(?:ventes|sales)", h):     # « 213 174 ventes » : un chiffre du test, pas un autre
        n = int(m.group(1) + m.group(2))
        assert n in (T["ventes"], T["ventes_total"]), (nom, n)
    for m in re.finditer(r"(\d{2})[,.](\d)\s?%", h):                                    # un pourcentage : un resultat mesure, pas un autre
        v = float(m.group(1) + "." + m.group(2))
        assert any(abs(v - x * 100) < 0.051 for x in MESURES), (nom, v)
# 4 d. la phrase sous le titre de l'accueil (24 nov 2026, choisie par Mathieu) : le nombre de ventes TESTEES, celui du test, dans
# les deux langues, avec le lien vers la preuve ; l'outil du site le remet a jour apres chaque test
acc = open(os.path.join(RACINE, "ui", "site_accueil.html"), encoding="utf-8").read()
nfr, nen = f"{T['ventes']:,}".replace(",", " "), f"{T['ventes']:,}"
assert '<p class="punch"><b><span class="fr">Ne mise plus à l’aveugle.</span><span class="en">Never bid blind again.</span></b>' in acc
assert f'SlabIQ a testé <a href="/slabiq#tests">{nfr} ventes de hockey</a> pour noter chaque carte de A+ à E.' in acc
assert f'SlabIQ tested <a href="/slabiq#tests">{nen} hockey sales</a> to grade every card from A+ to E.' in acc
assert acc.index('class="punch"') < acc.index('class="actions"') and acc.index("</h1>") < acc.index('class="punch"')
assert 'id="tests"' in open(os.path.join(RACINE, "ui", "site_slabiq.html"), encoding="utf-8").read()
outil = open(os.path.join(RACINE, "outils", "site_iq.py"), encoding="utf-8").read()
assert "ventes de hockey</a>)', lambda m: m.group(1) + fr(R[\"ventes\"]) + m.group(2))" in outil and "hockey sales</a>)', lambda m: m.group(1) + en(R[\"ventes\"]) + m.group(2))" in outil
assert ".punch{" in open(os.path.join(RACINE, "ui", "site_base.html"), encoding="utf-8").read()
# 5. le site : liens, ancres, francais et anglais par paires, gabarits, rien d'interdit
r = subprocess.run([sys.executable, os.path.join(RACINE, "outils", "audit_site.py"), "--test"], capture_output=True, text=True, timeout=120)
sortie = (r.stdout or "") + (r.stderr or "")
assert r.returncode == 0 and " 0 ecart(s)" in sortie, sortie[-1500:]
assert int(sortie.split(" pages, ")[1].split(" ")[0]) >= 900
print("OK test_audit_coherence :", sortie.strip().splitlines()[-1])
