"""7 nov 2026 (Mathieu : « pour les cartes a plus bas prix il faut augmenter la marge ; 8 $ sur une carte a 27 $ ce n'est
pas assez ; la Alex Bump Clear Cut, je ne voudrais pas payer plus que 20 $ avec les taxes »)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deals, watchlist

net = lambda v: v * (1 - deals.FRAIS_PCT) - deals.FRAIS_FIXE - deals.ENVOI_NET
# Alex Bump Young Guns Clear Cut : vaut 42 $, port 3 $
mise = round(deals.prix_max(42) - 3, 2)
assert 13.5 <= mise <= 14.5, mise
paye = deals.cout_achat(mise + 3)
assert paye <= 20, paye                                        # taxes comprises : 20 $ au plus
assert abs(net(42) - paye - 15) < 0.05, net(42) - paye        # 15 $ de profit (le % seul en laissait 8)
# une grosse carte : le % decide (30 % sur ce que tu paies, taxes comprises)
p = deals.cout_achat(deals.prix_max(400))
assert abs((net(400) - p) / p - 0.30) < 0.001
# sans minimum en dollars : seulement le % ; une carte trop petite : jamais un deal
assert deals.prix_max(42, 0.30, 0) > deals.prix_max(42)
assert deals.prix_max(12) == 0.0
# la watchlist : le minimum choisi par l'utilisateur
cfg = dict(watchlist.DEFAUT)
assert watchlist.mise_auto(cfg, 42, 3) == mise
assert watchlist.mise_auto(dict(cfg, profit_min_d=25), 42, 3) < mise
print("PROFIT MIN OK")
