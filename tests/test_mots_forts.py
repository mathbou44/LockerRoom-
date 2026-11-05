"""4 nov 2026 (Mathieu) : « Draft » et « Beam Team » font une autre carte ; une vente 4 fois sous la mediane n'est pas la meme carte."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import cartes_match as cm, vendues

c = cm.cible_titre("Beckett Sennecke 2025-26 UD Series Extended Young Guns Rookie Draft Outburst #744")
assert cm.raisons_refus(c, "2025-26 Upper Deck Extended Series Beckett Sennecke Young Guns Outburst #744 Rookie RC")
c = cm.cible_titre("2015-16 Upper Deck Young Guns Connor McDavid #201 RC #1 Draft Pick")
assert not any("draft absent" in r for r in cm.raisons_refus(c, "2015-16 Upper Deck Young Guns Connor McDavid #201 RC"))
c = cm.cible_titre("1992-93 Topps Stadium Club Michael Jordan Members Only Beam Team #1 Bulls")
assert cm.raisons_refus(c, "1992-93 Topps Stadium Club Members Only Michael Jordan #1 Bulls")
assert not cm.raisons_refus(c, "1992-93 Stadium Club Beam Team Members Only Michael Jordan #1")
assert [v["prix"] for v in vendues._sans_aberrants([{"prix": p} for p in (24, 1979, 1504, 3, 2239)])] == [1979, 1504, 2239]
assert len(vendues._sans_aberrants([{"prix": 3}, {"prix": 2000}, {"prix": 2100}])) == 3      # moins de 4 : rien d'ecarte
print("ok mots forts")
