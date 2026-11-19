"""19 nov 2026 (Mathieu, la Kucherov Allure 16-Bit « SSP » : « aucune vente trouvee », 130point en montre 8) : « SSP » est un
mot de vendeur : ni exige, ni refuse, ni cherche. Les autres variantes comptent toujours."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("LOCKERROOM_DONNEES", tempfile.mkdtemp())
import cartes_match as cm
c = cm.cible_titre("2023 UPPER DECK ALLURE #B-14 NIKITA KUCHEROV 16 BIT SSP")
assert "ssp" not in cm.requete_ebay(c).split(), cm.requete_ebay(c)
assert cm.raisons_refus(c, "2023-24 Upper Deck Allure 16-Bit Nikita Kucherov #B-14") == []
assert cm.raisons_refus(c, "2023-24 Upper Deck Allure Nikita Kucherov 16-Bit #B-14 SP") == []
assert cm.raisons_refus(c, "2023-24 Upper Deck Allure Nikita Kucherov Lightning")          # pas la 16-Bit
assert cm.raisons_refus(c, "2023-24 Upper Deck Allure Nikita Kucherov Rainbow #B-14 16-Bit")   # une autre variante
c2 = cm.cible_titre("2023-24 Upper Deck Allure Nikita Kucherov 16-Bit #B-14")
assert cm.raisons_refus(c2, "2023 UPPER DECK ALLURE #B-14 NIKITA KUCHEROV 16 BIT SSP") == []     # et l'inverse
print("OK test_ssp_souple")
