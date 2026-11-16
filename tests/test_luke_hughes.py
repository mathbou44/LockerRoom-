"""16 nov 2026 (Mathieu : la Luke Hughes The Cup Honorable Numbers /43, mise max 117 $, estimee 237 $ avec des ventes de Jack
Hughes) : un prenom different n'est jamais « similaire » ; une vente de LA carte passe avant les similaires ; RPA = auto."""
import os, sys, tempfile
from datetime import datetime, timedelta
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import deals, cartes_match
jr = lambda n: (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d")
T = "2023-24 UPPER DECK THE CUP HONORABLE NUMBERS ROOKIES PATCH AUTO /43 LUKE HUGHES"
jack = [{"titre": "2023-24 Upper Deck The Cup Honorable Numbers Jack Hughes Patch Auto /19 Devils", "prix": 327, "le": jr(250), "url": "u1"},
        {"titre": "2023-24 The Cup Honorable Numbers Patch Auto Jack Hughes 12/19", "prix": 428, "le": jr(265), "url": "u2"}]
luke = [{"titre": "2023-24 The Cup Honorable Numbers Rookies Luke Hughes Auto Patch 22/43 Devils", "prix": 316, "le": jr(262), "url": "u3"}]
c = cartes_match.cible_titre(T)
# 1. Jack Hughes ne sert jamais a estimer Luke Hughes
r = deals.valeur_approx({"titre": T}, jack, c)
assert r is None, r
# 2. la vente de LA carte (Luke /43) donne la valeur, a 80 % (dans l'annee), avant les similaires
r = deals.valeur_ou_saison({"titre": T, "item_id": "1"}, jack + luke, [])
assert r and r[1] == "unique" and r[0] == round(316 * 0.80, 2), r
print("LUKE HUGHES OK", r, round(deals.prix_max(r[0]) - 15, 2))
# 16 nov 2026 (« pourquoi on l'a pas capte ») : « Micheal Brandsegg-Nygard », prenom mal ecrit, nom compose : le joueur est reconnu
assert cartes_match.cible_titre("2025-26 UD Tableau Micheal Brandsegg-Nygard Shutter Speed Rookie Auto/25 Encased")["joueur"] == "michael brandsegg-nygard"
assert cartes_match.cible_titre("2021-22 SP Authentic Hughes Future Watch Auto")["joueur"] != "jack hughes"
assert "sans autographe" not in cartes_match.raisons_refus(c, "2023-24 The Cup Honorable Numbers Rookies Luke Hughes RPA /43")
print("NOM DE FAMILLE OK")
