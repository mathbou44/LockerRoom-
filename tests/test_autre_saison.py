"""7 nov 2026 (Mathieu : la Ron Francis 2024-25 UD Clear Cut Outburst Auto 07/25, sans aucune vente ; seulement la 2023-24 :
« mettre les annees a cote pour la meme carte, montrer les cartes similaires, mais dire qu'il n'y a pas de comp »)."""
import os, sys
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deals

jr = lambda k: (datetime.now() - timedelta(days=k)).strftime("%Y-%m-%d")
T = "2024-25 UD Clear Cut Outburst Auto Ron Francis #CC-RF Auto 07/25 (MicMas)"
V = [{"titre": "2023-24 UD Clear Cut Hockey Ron Francis Auto Outburst 17/25", "prix": 122.87, "le": jr(107)},
     {"titre": "RON FRANCIS 2023/24 UD CLEAR CUT OUTBURST ON CARD AUTOGRAPH AUTO #25/25 T5042", "prix": 78.5, "le": jr(200)},
     {"titre": "2019-20 UD Clear Cut Ron Francis Auto Outburst 3/25", "prix": 300, "le": jr(30)},          # 5 saisons : trop loin
     {"titre": "2023-24 UD Clear Cut Ron Francis Base #45", "prix": 3, "le": jr(10)}]                     # autre carte
assert deals.valeur_annonce({"titre": T}, V, []) is None                       # aucune vente de SA saison
va = deals.valeur_autre_saison({"titre": T}, V)
assert va and va[1] == "autre_saison" and va[2] == 1, va                       # 25/25 (dernier numero) ecarte
assert va[0] == round(122.87 * deals.RABAIS_SAISON, 2) and va[3][0]["saison"] == "2023-24", va
assert deals.valeur_ou_saison({"titre": T}, V, [])[1] == "autre_saison"
# jamais pour une recrue (la recrue d'une autre annee est une autre carte), ni si la saison a ses propres ventes
R = "2024-25 Upper Deck Young Guns Macklin Celebrini #201 RC"
assert deals.valeur_autre_saison({"titre": R}, [{"titre": "2023-24 Upper Deck Young Guns Macklin Celebrini #201 RC", "prix": 90, "le": jr(5)}]) is None
P = [{"titre": "2024-25 UD Clear Cut Outburst Auto Ron Francis 1%d/25" % i, "prix": 60 + i, "le": jr(5 + i)} for i in range(3)]
assert deals.valeur_ou_saison({"titre": T}, P + V, [])[1] == "vendues"
assert deals.saison(2024) == "2024-25" and deals.saison(1999) == "1999-00"
# 13 nov 2026 (Mathieu : Celebrini Stature Orange 2025-26 estimee avec ses Stature RECRUE 2024-25) : jamais l'annee recrue
# pour estimer une autre annee (ni l'inverse)
import datetime as _dt
_j = lambda k: (_dt.datetime.now() - _dt.timedelta(days=k)).strftime("%Y-%m-%d")
deals._AN_RC["macklin celebrini"] = 2024
VC = [{"titre": "2024-25 Upper Deck Stature Rookie Macklin Celebrini Orange /199", "prix": 426, "le": _j(20)},
      {"titre": "2024-25 Upper Deck Stature Macklin Celebrini Orange 12/199", "prix": 214, "le": _j(40)},
      {"titre": "2025-26 Upper Deck Stature Macklin Celebrini Blue /299", "prix": 60, "le": _j(5)},
      {"titre": "2025-26 Upper Deck Stature Macklin Celebrini Red /99", "prix": 95, "le": _j(3)}]
AC = {"titre": "2025-26 UD Stature Orange Macklin Celebrini #30 057/199 (MicMas)"}
assert deals.valeur_autre_saison(AC, VC) is None
va = deals.valeur_approx(AC, VC)
assert va and all(v["titre"].startswith("2025-26") for v in va[3]) and va[0] < 120, va
print("AUTRE SAISON OK")
