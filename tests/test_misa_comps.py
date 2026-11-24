"""23 nov 2026 (Mathieu, son annonce « 2025-26 SP Hockey Rookie Authentics Patch RC - Michael Misa #122 » a 55 $, dite « marche
10 $ »). Rejoue sur nos ventes : 6 ventes retenues dans les 90 jours, dont 5 d'un AUTRE produit et d'une AUTRE carte
(« SP Game Used - Authentic Rookies #AR-MM »), de 1,43 $ a 143 $. Une vente qui porte un autre code de carte, ou qui est du
produit SP Game Used, n'est plus une vente de la carte."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cartes_match as cm
T = "2025-26 SP Hockey Rookie Authentics Patch RC - Michael Misa  #122"
cib = cm.cible_titre(T, "Michael Misa")
R = lambda v, c=cib: cm.raisons_refus(c, v)
# 1. les ventes d'un autre produit / d'une autre carte sont refusees
for v in ("2025-26 Upper Deck Sp Game Used Edition - Authentic Rookies Michael Misa #AR-MM", "Upper Deck 2025-26 SP Game Used Authentic Rookies Michael Misa Sharks #AR-MM",
          "2025-26 SP Game Used - #AR-MM Michael Misa Authentic Rookies Patch Jersey", "2025 Upper Deck Sp Game Used Edition - Authentic Rookies Michael Misa (RC)"):
    assert R(v), v
assert "autre numéro" in R("2025-26 SP Game Used - #AR-MM Michael Misa Authentic Rookies Patch Jersey")
assert any("sp game used" in x for x in R("2025 Upper Deck Sp Game Used Edition - Authentic Rookies Michael Misa (RC)"))
# 2. les ventes de LA carte restent
for v in ("2025-26 UD SP ROOKIE AUTHENTICS JERSEY #122 MICHAEL MISA RC SAN JOSE SHARKS", "2025-26 SP Hockey - Michael Misa #122 ROOKIE AUTHENTICS JERSEY PATCH (RC)",
          "2025-26 SP Michael Misa #122 Rookie Authentics Jersey Patch"):
    assert not R(v), (v, R(v))
# 3. « Game Used Patch » est un type de carte, pas le produit SP Game Used : la version Gold garde sa vente
cg = cm.cible_titre("2025-26 SP Hockey Rookie Authentics Gold Patch RC - Michael Misa  #122", "Michael Misa")
assert not R("2025-26 SP - Rookie Authentics Michael Misa Game Used Patch #122 Gold (RC)", cg)
assert R("2025-26 SP - Rookie Authentics Michael Misa Game Used Patch #122 Gold (RC)") == ["variante gold"]       # sans « Gold » dans le titre : refusee
# 4. un code sans diese n'est pas un code (« Pee-Chee », « Game-Used ») ; le meme code reste la meme carte
assert cm._code_diese("2023-24 O-Pee-Chee Platinum Game-Used") is None and cm._code_diese("Kopitar #BA-AK Auto") == "BA-AK"
ck = cm.cible_titre("2023-24 O-Pee-Chee Platinum Blue Rainbow Anze Kopitar Auto #BA-AK", "Anze Kopitar")
assert "autre numéro" not in R("2023-24 O-Pee-Chee Platinum Blue Rainbow Anze Kopitar #BA-AK Auto", ck)
assert "autre numéro" in R("2023-24 O-Pee-Chee Platinum Blue Rainbow Anze Kopitar #RA-AK Auto", ck)
# 5. « SP » seul (short print, ou le produit) ne tranche rien
assert not cm._sp_game_used("2025-26 Upper Deck Series 2 SP #201") and cm._sp_game_used("2025-26 SP Game Used Supreme Patch")
print("OK test_misa_comps")
