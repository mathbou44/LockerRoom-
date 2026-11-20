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
    x = f"{int(round(R['x_ahaut_e']))}×"
    assert re.findall(r'>(\d+)×<', s) and set(re.findall(r'>(\d+×)<', s)) == {x}, (f, set(re.findall(r'>(\d+×)<', s)), x)
s = open(os.path.join(ICI, "ui", "site_slabiq.html"), encoding="utf-8").read()
assert (f'{round(R["accord"] * 100)} %</b>' in s or f'≈ {round(R["accord"] * 20) * 5} %</b>' in s) and f'{int(R["pro"]["reussi"] * 100 + 1e-9)} %</b>' in s \
    and f'(au hasard : {int(R["hasard"]["reussi"] * 100 + 1e-9)} %)' in s
print("OK test_site_a_jour")
