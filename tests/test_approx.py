"""7 nov 2026 (Mathieu : « regarde tous les no sales : on doit analyser les cartes similaires et donner un prix approx »)."""
import os, sys
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deals, cartes_match as cm

jr = lambda k: (datetime.now() - timedelta(days=k)).strftime("%Y-%m-%d")
T = "2024-25 UD SPx Finite Spectrum Auto Jesper Wallstedt RC 12/99 (MicMas)"
c = cm.cible_titre(T)
assert cm.requete_ebay(deals.cible_large(c)) == "jesper wallstedt spx auto", cm.requete_ebay(deals.cible_large(c))
V = [{"titre": "2024-25 SPx Finite Auto Jesper Wallstedt /199", "prix": 60, "le": jr(10)},
     {"titre": "2024-25 Upper Deck SPx Finite Rookie Auto Jesper Wallstedt 101/199", "prix": 70, "le": jr(20)},
     {"titre": "2024-25 SPx Jesper Wallstedt Rookie Jersey", "prix": 15, "le": jr(5)},                # sans auto
     {"titre": "2024-25 SPx Finite Spectrum Auto Logan Stankoven 5/99", "prix": 90, "le": jr(5)},    # autre joueur
     {"titre": "2024-25 SP Authentic Future Watch Auto Jesper Wallstedt /999", "prix": 40, "le": jr(5)}]  # autre produit
assert deals.valeur_annonce({"titre": T}, V, []) is None
va = deals.valeur_approx({"titre": T}, V, c)
assert va and va[1] == "approx" and va[2] == 2, va
f = (199 / 99) ** 0.3
assert abs(va[0] - round(65 * f * deals.RABAIS_APPROX, 2)) < 0.6, (va[0], 65 * f * deals.RABAIS_APPROX)
assert all(v["note"] == "/199" for v in va[3])
assert deals.valeur_ou_saison({"titre": T}, V, [])[1] == "approx"
# une seule vente similaire : rien ; une carte de base : jamais
assert deals.valeur_approx({"titre": T}, V[:1], c) is None
B = "2024-25 Upper Deck Jesper Wallstedt Base #45"
assert deals.valeur_approx({"titre": B}, [{"titre": "2023-24 Upper Deck Jesper Wallstedt Base #12", "prix": 2, "le": jr(3)}] * 3) is None
print("APPROX OK")
