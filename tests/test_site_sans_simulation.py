"""23 nov 2026 (Mathieu, devant le graphique de la page SlabIQ, un budget de cartes par mois pendant 1 an, avec ou sans SlabIQ :
« c'est quoi, avant frais eBay ? ca vaut la peine qu'on le garde ? » ; puis « oui » a « je l'enleve ? »).
La simulation d'un an n'est plus sur le site : elle affichait un PROFIT avant frais eBay (+350 $ avec SlabIQ, -277 $ seul ; apres
frais : -412 $ et -1 048 $), avec des lettres fixees apres coup ; et la promesse de SlabCoach est « acheter et vendre au bon
moment », pas le profit de revente. A sa place, en haut de la page SlabIQ : le comparatif mesure sur des ventes jamais vues.
La mesure reste dans ui/slabiq_tests.json (« sim ») pour la recherche ; ce test interdit son retour sur le site."""
import json, os, re, sys
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ICI, "outils")); sys.path.insert(0, ICI)
ui = os.path.join(ICI, "ui")
pages = {f: open(os.path.join(ui, f), encoding="utf-8").read() for f in os.listdir(ui) if f.startswith("site_") and f.endswith(".html")}
assert len(pages) >= 3, list(pages)
INTERDITS = ("sim-data", "sim-chf", "sim-pente", "sim-svg", "500 $ de cartes", "$500 of cards", "collectionneurs virtuels", "virtual collectors",
             "Écart en 1 an", "Gap in 1 year", "Voir mois par mois", "See month by month", "Simulation sur de vraies ventes", "Simulation on real eBay sales")
for f, s in pages.items():
    for mot in INTERDITS:
        assert mot not in s, f"{f} : la simulation d'un an est revenue (« {mot} »)"
    # jamais un PROFIT de revente promis sur le site : SlabIQ aide a choisir, il ne garantit pas de gain
    assert not re.search(r'class="(?:fr|en)">\s*(?:Le profit|Profit)\s*:', s), f"{f} : un profit affiche"
# la page SlabIQ : le comparatif mesure est EN HAUT (avant le defi), une seule fois, et c'est celui du test
s = pages["site_slabiq.html"]
assert s.count("<!--vs-->") == 1 and s.index('id="toi-vs-iq"') < s.index("<!--vs-->") < s.index('id="defi"') < s.index('id="tests"')
assert "Tes chances, seul ou avec SlabIQ." in s and "Your odds, on your own or with SlabIQ." in s
assert s.index('id="tests"') < s.index("<!--bulletin-->"), "le tableau aux 5 dates reste dans « Nos tests »"
import site_iq
R = json.load(open(os.path.join(ui, "slabiq_tests.json"), encoding="utf-8"))
assert site_iq.bloc_vs(R, "slabiq") in s
# le generateur n'ecrit plus rien de la simulation, mais la mesure reste gardee pour la recherche
g = open(os.path.join(ICI, "outils", "site_iq.py"), encoding="utf-8").read()
assert "def graphique(" not in g and "def pente(" not in g and "sim-data" not in g and "SIM_BOUTON" not in g
assert 'R2["sim"]' in g and isinstance(R.get("sim"), dict) and "r_avec" in R["sim"]
print("OK test_site_sans_simulation (aucune page du site ne montre la simulation ni un profit ; le comparatif mesure est en haut de la page SlabIQ)")
