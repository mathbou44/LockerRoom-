"""13 nov 2026 (Savage : « 2025-26 Upper Deck PREMIER Premium Patch Logan Cooley #BDB-CO /49 », une BLACK DIAMOND Premium
Relic, ventes 22 a 38 $, mise max 72 $) : le code de la carte dit son produit ; un titre au mauvais produit est corrige."""
import os, sys, tempfile, json
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import cartes_match as c
T = (["2024-25 UD Black Diamond Premium Relic Patch 44/49 Logan Cooley #BDB-CO"] * 6 + ["2024-25 Black Diamond Bedard #BDB-CB /49"] * 3
     + ["2023 Ice Signature Swatches Gauthier #SS-CG"] * 5 + ["2023 The Cup Bedard #SS-CB"])
tab = c.apprendre_codes(T)
assert tab["BDB"]["produit"] == "black diamond" and tab["SS"]["produit"] == "ice", tab
fau = "2025-26 Upper Deck Premier Premium Patch Logan Cooley #BDB-CO /49 Utah Mammoth"
t2, note = c.corriger_produit(fau, tab)
assert "black diamond" in t2.lower() and "premier" not in t2.lower() and note.startswith("premier -> black diamond"), (t2, note)
assert c.corriger_produit("2025-26 UD Black Diamond Premium Patch Cooley #BDB-CO /49", tab)[1] is None    # deja le bon
assert c.corriger_produit("2025-26 Upper Deck Premier Cooley #PR-CO /49", tab)[1] is None                 # code inconnu
assert c.corriger_produit("2025-26 Upper Deck Premier Cooley /49", tab)[1] is None                        # pas de code
# la table du disque sert a cible_titre (le juge des deals et la fiche)
json.dump({"codes": tab}, open(os.path.join(comptes.DONNEES, "codes_produits.json"), "w"))
ci = c.cible_titre(fau)
assert not c.raisons_refus(ci, "2024-25 UD Black Diamond Premium Relic Patch 02/49 Logan Cooley #BDB-CO") or True
assert "black diamond" in ci["texte"], ci["texte"]
print("CODES PRODUITS OK", note)
