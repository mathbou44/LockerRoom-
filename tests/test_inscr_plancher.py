"""8 nov 2026 (Mathieu : « la Poitras aurait du sortir ») : une Future Watch Auto INSCRIBED /999 sans vente avec inscription
prend la valeur de la meme carte sans inscription (un plancher), pas « sans comps »."""
import os, sys
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deals, cartes_match
j = lambda k: (datetime.now() - timedelta(days=k)).strftime("%Y-%m-%d")
T = "2023 SP AUTHENTIC #177 MATTHEW POITRAS INSCRIBED FUTURE WATCH AUTO RC /999"
ventes = [{"titre": "2023-24 SP Authentic Future Watch Auto Matthew Poitras /999 #177 RC", "prix": p, "le": j(k), "url": f"u{k}"}
          for p, k in ((260, 3), (280, 9), (300, 20), (240, 40))]
ventes += [{"titre": "2023-24 SP Authentic Future Watch Matthew Poitras RC /999", "prix": 40, "le": j(5), "url": "x1"},          # sans auto
           {"titre": "2023-24 SP Authentic Limited Future Watch Auto Matthew Poitras /100", "prix": 900, "le": j(6), "url": "x2"},  # /100
           {"titre": "2023-24 SP Authentic Future Watch Auto Logan Cooley /999", "prix": 500, "le": j(7), "url": "x3"}]            # autre joueur
cib = cartes_match.cible_titre(T)
assert deals.valeur_annonce({"titre": T, "prix_cad": 200, "port_cad": 5}, ventes, [], cib=cib) is None     # aucune vente inscrite
v = deals.valeur_inscr_plancher({"titre": T}, ventes, cib)
assert v and v[1] == "inscr_plancher" and v[2] == 4 and 255 <= v[0] <= 285, v
assert deals.valeur_approx({"titre": T}, ventes, cib)[1] == "inscr_plancher"
assert deals.valeur_ou_saison({"titre": T}, ventes, [], cib=cib)[1] == "inscr_plancher"
# une carte sans inscription n'utilise jamais ce plancher ; une seule vente : pas assez
assert deals.valeur_inscr_plancher({"titre": T.replace("INSCRIBED ", "")}, ventes) is None
assert deals.valeur_inscr_plancher({"titre": T}, ventes[:1], cib) is None
print("INSCR PLANCHER OK")
