"""19 nov 2026 (Mathieu : « a chaque version significative de SlabIQ, refaire les tests et les mettre sur notre page ») : les
resultats publies sur le site (ui/slabiq_tests.json) doivent venir de la version de SlabIQ en place. Si une regle de decision
change (bareme, note, validation, vitrine, seuils du Radar), ce test echoue jusqu'a ce que les tests du site soient refaits :
  python3 outils/tests_site.py <ventes_hockey.tsv.gz> --ecrire"""
import json, os, re, sys
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ICI)
import empreinte_iq
R = json.load(open(os.path.join(ICI, "ui", "slabiq_tests.json"), encoding="utf-8"))
e = empreinte_iq.empreinte()
assert R["empreinte"] == e, (f"SlabIQ a change depuis les tests publies sur le site ({R['le']}, empreinte {R['empreinte']} -> {e}) : "
                             "refaire les tests du site (outils/tests_site.py --ecrire)")
# et le site montre bien ces chiffres-la (les memes partout)
for f in ("site_slabiq.html", "site_accueil.html"):
    s = open(os.path.join(ICI, "ui", f), encoding="utf-8").read()
    import iq_publie
    x = f"{iq_publie.fois(R)}×"          # 22 nov 2026 : le meme arrondi que le site et l'app (vers le bas)
    assert re.findall(r'>(\d+)×<', s) and set(re.findall(r'>(\d+×)<', s)) == {x}, (f, set(re.findall(r'>(\d+×)<', s)), x)
s = open(os.path.join(ICI, "ui", "site_slabiq.html"), encoding="utf-8").read()
assert (f'{round(R["accord"] * 100)} %</b>' in s or f'≈ {round(R["accord"] * 20) * 5} %</b>' in s)
# 20 nov 2026 (Mathieu : « valide l'info ; change-la partout : site, app, ordi ») : la fenetre SlabIQ de l'app prend les MEMES
# textes (iq_publie), et le site les montre tels quels
import iq_publie
P = iq_publie.publics()
assert P and P["le"] == R["le"]
acc = open(os.path.join(ICI, "ui", "site_accueil.html"), encoding="utf-8").read()
assert f'>{P["ventes"]}</b>' in acc and f'>{P["ventes"]}</b>' in s, P["ventes"]
assert f'>{P["fois"]}×<' in acc and f'>{P["fois"]}×<' in s
assert f'{P["accord_fr"]}</b>' in s
# 23 nov 2026 (Mathieu : « ces comparatifs sur notre site, a la Apple ») : le comparatif « seul ou avec SlabCoach » des deux pages
# est ecrit par outils/site_iq.bloc_vs depuis le test : le site montre exactement ce bloc (aucun chiffre retouche a la main), avec
# les arrondis d'iq_publie (le Radar Pro vers le bas ; « seul » au plus proche : jamais plus d'ecart que la mesure)
sys.path.insert(0, os.path.join(ICI, "outils"))
import site_iq
for f, page, texte in (("site_accueil.html", "accueil", acc), ("site_slabiq.html", "slabiq", s)):
    bloc = site_iq.bloc_vs(R, page)
    assert texte.count("<!--vs-->") == 1 and bloc in texte, (f, "le comparatif n'est pas celui du test : refaire outils/tests_site.py --ecrire")
    # 26 nov 2026 (Mathieu : « on est combien de fois meilleur avec SlabCoach ? on doit etre vraiment simple ») : UN gros chiffre
    # (« 6× plus de chances que ta carte garde sa valeur »), les deux pourcentages du jour dessous ; plus de 2e ni de 3e colonne
    assert f'<b class="cmp-n holo-t">{P["fois_seul"]}<small class="x">×</small></b>' in bloc and bloc.count('class="cmp-n ') == 1, "un seul gros chiffre"
    assert 'plus de chances que ta carte garde sa valeur.' in bloc and 'more likely your card holds its value.' in bloc
    assert f'<em><span class="fr">{P["pro"]} %</span>' in bloc and f'<em><span class="fr">{P["hasard"]} %</span>' in bloc
    assert f'style="--w:{P["pro"]}"' in bloc and f'style="--w:{P["hasard"]}"' in bloc and "Se revend" not in bloc and "Resells" not in bloc
    assert bloc.count('<span class="fr">') == bloc.count('<span class="en">')
assert P["pro"] <= R["pro"]["reussi"] * 100 and P["revendue"] <= R["pro"]["revendue"] * 100          # jamais plus que la mesure
# le « N× » : le PIRE des tests refaits (le test du site et chaque date du bulletin), vers le bas : vrai a CHAQUE test
B = json.load(open(os.path.join(ICI, "ui", "slabiq_bulletin.json"), encoding="utf-8"))
xs, xs_bas, xs_haut, xs_n = iq_publie.fois_seul(R)
rapports = [x["pro"]["reussi"] / x["hasard"]["reussi"] for x in B["lignes"]]
assert xs == P["fois_seul"] == int(min(rapports)) and xs_n == len(B["lignes"]) and all(r_ >= xs for r_ in rapports), (xs, rapports)
assert xs <= R["pro"]["reussi"] / R["hasard"]["reussi"] and xs <= P["pro"] / P["hasard"], "« N× » ne dit jamais plus que les deux % affiches"
assert xs_bas <= min(rapports) and xs_haut <= max(rapports) and iq_publie.fois_seul(R, {"lignes": []})[3] == 1
pire = {"lignes": B["lignes"] + [{"pro": {"n": 50, "reussi": 0.40}, "hasard": {"reussi": 0.20}}]}
assert iq_publie.fois_seul(R, pire)[0] == 2, "un test moins bon fait baisser le chiffre : il n'est jamais ecrit a la main"
assert f"« {xs}× » : à chacun de nos {xs_n} tests, le Radar Pro a fait au moins {xs} fois mieux que seul" in s and "fois mieux que seul" not in acc
app0 = open(os.path.join(ICI, "source", "src_app.html"), encoding="utf-8").read()
assert "P.fois_seul" in app0 and "plus de chances que ta carte garde sa valeur. Avec le Radar Pro : ${P.pro} %. Seul : ${P.hasard} %." in app0, "l'app dit la meme phrase que le site"
assert "se revendent sans perte" not in app0 and "Au hasard :" not in app0
# 26 nov 2026 (Mathieu : « oui » a l'intervalle plus prudent) : les achats du Radar Pro viennent de peu de joueurs ; la page SlabIQ
# dit l'intervalle calcule PAR JOUEUR (tests_site.pro_reel retire des joueurs, pas des achats), bornes arrondies vers le bas ;
# l'accueil garde l'essentiel (pas d'intervalle).
icj, nj = R["pro"]["reussi_ic95_joueurs"], R["pro"]["joueurs"]
lo, hi = int(icj[0] * 100 + 1e-9), int(icj[1] * 100 + 1e-9)
assert 0 < icj[0] <= R["pro"]["reussi"] <= icj[1] <= 1 and nj >= 10, (icj, nj)
assert f"viennent de {nj} joueurs : avec d’autres joueurs, le résultat du Radar Pro irait de {lo} % à {hi} %" in s, "la page SlabIQ dit l'intervalle par joueur"
assert f"come from {nj} players: with other players, the Pro Radar result would range from {lo}% to {hi}%" in s
assert "irait de" not in acc and "would range from" not in acc
assert icj[1] - icj[0] >= R["pro"]["reussi_ic95"][1] - R["pro"]["reussi_ic95"][0], "par joueur : au moins aussi large que par achat"
assert P["hasard"] >= int(R["hasard"]["reussi"] * 100) and P["revendue_seul"] >= R["hasard"]["revendue"] * 100 - 0.5
# 23 nov 2026 au soir : « seul » au plus proche partout sur la page (9,6 % : « 10 % » au comparatif ET au bulletin, pas 9 et 10)
assert P["hasard"] == int(R["hasard"]["reussi"] * 100 + 0.5) and P["pro"] == int(R["pro"]["reussi"] * 100 + 1e-9)
assert f'se revend {P["fois"]} fois plus souvent' in acc and not re.search(r'se revend (?!%d )[0-9]+ fois' % P["fois"], acc)
app = open(os.path.join(ICI, "source", "src_app.html"), encoding="utf-8").read()
assert "9/10" not in app and "5× plus" not in app and "5× more" not in app, "l'app ne doit plus ecrire de chiffre SlabIQ en dur"
print("OK test_site_a_jour")
