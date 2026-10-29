"""31 oct 2026 (Mathieu : « un auto-learn pour les cartes non reconnues ») : les produits et inserts appris tout seuls
entrent dans la recherche de ventes ; un nom de joueur ne s'apprend jamais. Aucun reseau."""
import os
import sys
import tempfile
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import catalogue  # noqa: E402
catalogue.liste = lambda: []                     # sans le catalogue de la machine : seulement ce que le test apprend
import cartes_match as c  # noqa: E402
import produits_appris as P  # noqa: E402

J = ["Brady Tkachuk", "Matt Duchene", "Cale Makar", "Mark Scheifele", "Nathan MacKinnon", "Mitch Marner", "Auston Matthews"]
T = [f"2020-21 Upper Deck Tim Hortons NHL Signatures #S-{i} {j} Auto" for i, j in enumerate(J)]
T += [f"2023-24 Upper Deck Credentials Debut Ticket Access Auto {j} /{99 + i}" for i, j in enumerate(J)]
T += [f"2022 Connor Bedard Wow Amazing #{i}" for i in range(12)]             # un seul joueur : jamais appris
T += [f"2021-22 Upper Deck Zorgblat Special {j}" for j in J[:2]] * 5           # 2 joueurs seulement : pas assez
assert P.apprendre(T) >= 2
ph = P.phrases()
assert any("tim hortons" in p for p in ph) and any("debut ticket" in p for p in ph), ph
assert not any("bedard" in p or "amazing" in p for p in ph) and not any("zorgblat" in p for p in ph), ph
q = c.requete_ebay(c.cible_titre("2020-21 Upper Deck Tim Hortons NHL Signatures #S-BT Brady Tkachuk Auto Ottawa Senators"))
assert "tim" in q and "hortons" in q and "tkachuk" in q and "auto" in q, q
q = c.requete_ebay(c.cible_titre("2023-24 Upper Deck Credentials Debut Ticket Access Auto Pavel Mintyukov"))
assert "ticket" in q and len(q.split()) <= 7, q
assert c.requete_ebay(c.cible_titre("2023-24 Upper Deck Young Guns Connor Bedard #201")) == "connor bedard young guns"
assert P._nettoyer("Population Count /1000") == "population count" and P._nettoyer("2024-25 Upper Deck Hockey") is None
print("ok : produits appris")
