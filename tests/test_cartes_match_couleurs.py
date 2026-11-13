"""13 nov 2026 (Mathieu : la Marleau Stature « 3 Color Patch Auto #8/35 » : « aucune vente de cette carte », alors que 3 Green
Patch Auto /35 se sont vendues) : « 3 color patch » decrit la patch (pas une parallele « Color ») ; la meme numerotation dit
la couleur (une annonce sans couleur /35 = la vente Green /35)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cartes_match as c
cib = c.cible_titre("2025-26 Upper Deck Stature Patrick Marleau 3 Color Patch Auto #8/35")
assert not cib["paralleles"], cib["paralleles"]
for s in ["2025-26 Upper Deck Stature Patrick Marleau Relic Patch Auto Green 11/35 SP",
          "2025 UPPER DECK STATURE #61 PATRICK MARLEAU GREEN PATCH AUTO /35",
          "Upper Deck 2025-26 Stature Patrick Marleau Green Patch Auto /35 #61 Sharks"]:
    assert c.raisons_refus(cib, s) == [], (s, c.raisons_refus(cib, s))
assert c.raisons_refus(cib, "2025-26 Upper Deck Stature Patrick Marleau Patch Auto Gold /10")          # autre numerotation
assert c.raisons_refus(c.cible_titre("Stature Marleau Blue Patch Auto /35"), "Stature Marleau Green Patch Auto /35")   # couleur nommee
assert c.raisons_refus(c.cible_titre("Marleau Patch Auto"), "Marleau Green Patch Auto /35")        # sans numerotation : pas la meme
for t in ("Crosby two-color patch /99", "Crosby tri-color jersey", "Crosby 2 colour patch auto", "Crosby multi-color swatch"):
    assert "color" not in c.cible_titre(t)["paralleles"] and "colour" not in c.cible_titre(t)["paralleles"], t
assert "color blast" not in str(c.cible_titre("2020-21 Upper Deck Color Blast McDavid")["paralleles"])
print("COULEURS OK")
