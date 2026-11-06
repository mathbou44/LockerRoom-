"""7 nov 2026 (Mathieu : « attention les inscribed valent beaucoup plus », une Frank Nazar SP Authentic Future Watch Auto
Inscribed 17/999 comparee aux Future Watch Auto ordinaires)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cartes_match as cm

T = "Frank Nazar 2024-25 SP Authentic Future Watch Auto Inscribed 17/999 Blackhawks"
c = cm.cible_titre(T)
assert c["inscr"] and "inscribed" in cm.requete_ebay(c), cm.requete_ebay(c)
ordinaire = "2024-25 SP Authentic Future Watch Auto Frank Nazar #134 355/999 RC"
assert "sans inscription" in cm.raisons_refus(c, ordinaire), cm.raisons_refus(c, ordinaire)
for t in ("2024-25 SP Authentic Frank Nazar Future Watch Auto Inscription /999", "Frank Nazar SP Authentic Future Watch Inscribed Auto 210/999 RC"):
    assert not cm.raisons_refus(c, t), (t, cm.raisons_refus(c, t))
# une carte ordinaire ne prend jamais les ventes d'une inscribed
c2 = cm.cible_titre(ordinaire)
assert not c2["inscr"] and "inscription" in cm.raisons_refus(c2, T)
assert not cm.raisons_refus(c2, "2024-25 SP Authentic Future Watch Autograph Frank Nazar 101/999")
print("INSCRIPTION OK")

# 7 nov 2026 (une Reinhart Exquisite Endorsements Relics Auto 30/50 a 19 $ chez CF31, sans valeur) : « The Cup Exquisite »
# = « Exquisite » ; la recherche n'exige plus « patch » quand la carte dit « Relics »
import deals
from datetime import datetime, timedelta
jr = lambda k: (datetime.now() - timedelta(days=k)).strftime("%Y-%m-%d")
T = "2024-25 Exquisite Endorsements Relics Sam Reinhart Auto 30/50 (MicMas)"
c = cm.cible_titre(T)
assert "patch" not in cm.requete_ebay(c).split(), cm.requete_ebay(c)
V = [("2024-25 UPPER DECK EXQUISITE ENDORSEMENTS RELICS SAM REINHART AUTO PATCH 31/50", 73, jr(57)),
     ("2024-25 Upper Deck The Cup Exquisite Endorsements Relics Sam Reinhart Auto 05/50", 40.67, jr(289)),
     ("2024-25 Upper Deck The Cup Sam Reinhart Exquisite Endorsements Relics /50 Auto", 56.07, jr(299))]
for t, _p, _d in V:
    assert not cm.raisons_refus(c, t), (t, cm.raisons_refus(c, t))
assert cm.raisons_refus(cm.cible_titre("2024-25 Upper Deck The Cup Sam Reinhart Auto Patch /99"), "2024-25 Upper Deck Sam Reinhart Auto Patch /99")
va = deals.valeur_annonce({"titre": T, "item_id": "x"}, [{"titre": t, "prix": p, "le": d} for t, p, d in V], [])
assert va and 40 <= va[0] <= 73, va
print("EXQUISITE OK")
