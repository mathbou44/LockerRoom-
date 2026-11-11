"""11 nov 2026 (Mathieu : « es-tu sur du 94 ? » : PSA 8 de Terry Ruskowski « LOW POP /5 ») : les mots de vendeur ne comptent
pas, et un joueur inconnu de SlabIQ est plafonne par ce que la carte justifie."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import score_slab, indice_joueurs
assert score_slab.nettoyer("1985/86 OPC #33 Terry Ruskowski PSA 8 Mint LOW POP /5") == "1985/86 OPC #33 Terry Ruskowski PSA 8 Mint"
assert score_slab.nettoyer("McDavid Young Guns RC HOT INVEST pop 3 rare") == "McDavid Young Guns RC"
assert score_slab.nettoyer("2023 Bedard Gold /10 PSA 9") == "2023 Bedard Gold /10 PSA 9"          # un vrai tirage reste
I = {f"Joueur {i}": {"indice": 50} for i in range(150)}
I["Mario Lemieux"] = {"indice": 97, "pastilles": ["legende"]}
indice_joueurs.lire = lambda: {"indice": I}
c = score_slab.carte("1985/86 OPC #33 Terry Ruskowski PSA 8 Mint")
assert score_slab.plafond_inconnu(94, c, None) <= 55
assert score_slab.plafond_inconnu(94, c, {"indice": 97}) == 94                                   # joueur connu : rien ne change
s = score_slab.score("1985/86 OPC #33 Terry Ruskowski PSA 8 Mint Pittsburgh Penguins LOW POP /5")
assert s["score"] is None or s["score"] <= 55, s
x = [{"titre": "1985/86 OPC #33 Terry Ruskowski PSA 8 Mint Pittsburgh Penguins LOW POP /5"}]
score_slab._annoter_lot(x)
assert x[0]["score"] is None or x[0]["score"] <= 55, x
print("SCORE HYPE OK")
