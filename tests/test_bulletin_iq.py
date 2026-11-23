"""22 nov 2026 (Mathieu : « une reelle plus-value, mesurable et repetable ») : le bulletin SlabIQ = le test du site rejoue a
plusieurs dates. La page montre exactement ce que dit ui/slabiq_bulletin.json ; la derniere ligne est le test courant du site ;
jamais un chiffre plus beau que ce qui est mesure ; le bloc se reecrit sans doubler."""
import json, os, re, sys
ICI = os.path.dirname(os.path.abspath(__file__)); LR = os.path.dirname(ICI)
sys.path.insert(0, os.path.join(LR, "outils"))
import bulletin_iq as b
B = json.load(open(os.path.join(LR, "ui", "slabiq_bulletin.json"), encoding="utf-8"))
T = json.load(open(os.path.join(LR, "ui", "slabiq_tests.json"), encoding="utf-8"))
L = B["lignes"]
assert len(L) >= 3 and [x["fin"] for x in L] == sorted(x["fin"] for x in L), [x["fin"] for x in L]
assert L[-1]["pro"]["reussi"] == T["pro"]["reussi"] and L[-1]["pro"]["n"] == T["pro"]["n"] and L[-1]["coupe"] == T["coupe"], "la derniere ligne = le test courant du site"
for x in L:                                   # chaque date : des lettres fixees AVANT les reventes mesurees, assez d'achats, mieux que le hasard
    assert x["coupe"] < x["revente_des"] <= x["revente_fin"] <= x["fin"] and x["pro"]["n"] >= 100, x
    assert x["pro"]["reussi_ic95"][0] > x["hasard"]["reussi"], "a chaque date, le bas de l'intervalle bat le hasard : " + x["fin"]
s = open(os.path.join(LR, "ui", "site_slabiq.html"), encoding="utf-8").read()
assert s.count("<!--bulletin-->") == 1 and s.count("<!--/bulletin-->") == 1
bloc = re.search(r"<!--bulletin-->.*?<!--/bulletin-->", s, re.S).group(0)
assert bloc == b.rendre(B), "la page dit exactement ce que le fichier mesure (refaire : python3 outils/bulletin_iq.py --rendre)"
for x in L:
    assert f'{int(x["pro"]["reussi"] * 100 + 1e-9)} %</b>' in bloc and f'<td>{x["pro"]["n"]}</td>' in bloc      # 23 nov 2026 : vers le bas, comme le gros chiffre du site
lo = min(x["pro"]["reussi"] for x in L)
assert f"{int(lo * 100 + 1e-9)} à " in bloc and "profit" not in bloc.lower(), "la fourchette part du PIRE resultat ; aucun mot sur un profit"
# une ligne se lit telle quelle dans un resultat de tests_site ; un bulletin d'une seule date ne s'affiche pas
l1 = b.ligne("2026-11-19", T)
assert l1["pro"]["reussi"] == T["pro"]["reussi"] and l1["hasard"]["n"] == T["hasard"]["n"] and b.rendre({"lignes": [l1]}) == ""
print("OK test_bulletin_iq (%d dates : %s %% ; hasard %s %%)" % (len(L), " ".join(str(round(x["pro"]["reussi"] * 100)) for x in L), " ".join(str(round(x["hasard"]["reussi"] * 100)) for x in L)))
