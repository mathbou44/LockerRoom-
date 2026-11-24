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
# 23 nov 2026 (Mathieu, devant le tableau 92, 88, 80, 81, 77 % : « on dirait qu'on s'empire... remplacer par autre chose de plus
# convaincant ») : plus de tableau par date ; les memes resultats, TOUS montres, un point par test sur une seule echelle
assert "<table" not in bloc and "Test du" not in bloc
for cle in ("pro", "hasard"):
    for x in L:
        assert f'<i style="left:{100 * x[cle]["reussi"]:.1f}%"></i>' in bloc, (cle, x["fin"])      # aucun test laisse de cote
assert bloc.count('<i style="left:') == 2 * len(L)
lo, hi = min(x["pro"]["reussi"] for x in L), max(x["pro"]["reussi"] for x in L)
assert f"{int(lo * 100 + 1e-9)} à {int(hi * 100 + 1e-9)} %" in bloc and f"{int(lo * 100 + 1e-9)} to {int(hi * 100 + 1e-9)}%" in bloc, "la fourchette part du PIRE resultat"
assert "profit" not in bloc.lower(), "aucun mot sur un profit"
# le plus recent (le plus bas aujourd'hui) reste ecrit en toutes lettres, avec son nombre d'achats
der = L[-1]
assert f'Le plus récent : {int(der["pro"]["reussi"] * 100 + 1e-9)} % ({der["pro"]["n"]} achats), contre {round(der["hasard"]["reussi"] * 100)} % seul' in bloc
# « l'emporte N fois sur N » : compte seulement les tests ou le BAS de l'intervalle bat « seul »
g = sum(1 for x in L if x["pro"]["reussi_ic95"][0] > x["hasard"]["reussi"])
assert f"l’emporte {g}&nbsp;fois&nbsp;sur&nbsp;{len(L)}" in bloc and f"wins {g}&nbsp;out&nbsp;of&nbsp;{len(L)}" in bloc
perdu = json.loads(json.dumps(B)); perdu["lignes"][0]["pro"]["reussi_ic95"] = [0.01, 0.99]
assert f"l’emporte {g - 1}&nbsp;fois&nbsp;sur&nbsp;{len(L)}" in b.rendre(perdu), "un test pas net n'est pas compte comme gagne"
assert "s’améliore" not in bloc and "improves" not in bloc, "le chiffre du Radar Pro baisse de test en test : on ne dit pas que ca s'ameliore"
for cl in (".iq-rep{", ".iq-rep-t i{", ".iq-rep-l, .iq-rep-x{"):
    assert cl in s, "le style du bloc est dans la page : " + cl
# une ligne se lit telle quelle dans un resultat de tests_site ; un bulletin d'une seule date ne s'affiche pas
l1 = b.ligne("2026-11-19", T)
assert l1["pro"]["reussi"] == T["pro"]["reussi"] and l1["hasard"]["n"] == T["hasard"]["n"] and b.rendre({"lignes": [l1]}) == ""
print("OK test_bulletin_iq (%d dates : %s %% ; hasard %s %%)" % (len(L), " ".join(str(round(x["pro"]["reussi"] * 100)) for x in L), " ".join(str(round(x["hasard"]["reussi"] * 100)) for x in L)))
