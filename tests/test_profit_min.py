"""7 nov 2026 (Mathieu : « pour les cartes a plus bas prix il faut augmenter la marge ; 8 $ sur une carte a 27 $ ce n'est
pas assez ; la Alex Bump Clear Cut, je ne voudrais pas payer plus que 20 $ avec les taxes ») et sa vraie vente : 35 $ + 17 $
de port + 3,89 $ de taxe -> frais de transaction 6,67 $ + pub 1,08 $, gains 44,25 $."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deals, watchlist

# 1. la vraie vente : les frais de revente sur prix + port
assert abs(deals.frais_revente(35, 17) - 7.75) < 0.05, deals.frais_revente(35, 17)
assert abs((35 + 17 - deals.frais_revente(35, 17)) - 44.25) < 0.05
assert deals.PORT_REVENTE == 15.0                              # 10 $ au Canada, 20 $ aux USA : la moyenne
# 2. la Alex Bump (vaut 42 $, port 3 $) : 15 $ de profit au moins, taxes de l'achat comprises
mise = round(deals.prix_max(42) - 3, 2)
paye = deals.cout_achat(mise + 3)
assert paye <= 20, paye
assert abs(deals.net_revente(42) - paye - 15) < 0.05, deals.net_revente(42) - paye
# 3. une grosse carte : le % decide (30 % sur ce que tu paies, taxes comprises)
p = deals.cout_achat(deals.prix_max(400))
assert abs((deals.net_revente(400) - p) / p - 0.30) < 0.001
# sans minimum en dollars : seulement le % ; une carte trop petite : jamais un deal
assert deals.prix_max(42, 0.30, 0) > deals.prix_max(42)
assert deals.prix_max(15) == 0.0
# 4. la watchlist : le minimum choisi par l'utilisateur
cfg = dict(watchlist.DEFAUT)
assert watchlist.mise_auto(cfg, 42, 3) == mise
assert watchlist.mise_auto(dict(cfg, profit_min_d=25), 42, 3) < mise
print("PROFIT MIN OK")
