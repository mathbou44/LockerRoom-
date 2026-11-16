"""16 nov 2026 : le bareme SlabIQ ecrit avec l'expert (questionnaires, rondes 1 a 4) : chaque reponse de Mathieu est un test."""
import os, sys, tempfile
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import bareme_iq as b

S = lambda t: b.sorte(t)[0]
# la sorte (la carte seulement)
assert S("Lane Hutson 2024-25 Upper Deck Young Guns #201") == "A"                    # YG raw
assert S("Lane Hutson 2024-25 Upper Deck Young Guns PSA 10") == "A+"                 # YG gradee 10
for v in ("Exclusives /100", "High Gloss /10", "Canvas", "Clear Cut", "Outburst", "Deluxe", "Silver Foil", "French", "Retro",
          "Photo Variation SSP"):
    assert S("Ivan Demidov 2025-26 Upper Deck Young Guns Rookie " + v) == "A+", v    # toutes les variantes de YG
assert S("2025-26 Upper Deck Extended Series Outburst Retro Young Guns Kris Letang #OR-29") == "B"    # Retro YG d'un veteran
assert S("2024-25 Upper Deck Series 2 Young Guns Renewed Connor McDavid #201") == "B"                 # ... un insert
assert S("Macklin Celebrini 2024-25 The Cup Rookie Auto Patch RPA /249") == "A+"
assert S("Quinn Hutson 2025-26 SP Authentic Future Watch Auto Patch /100") == "A+"
assert S("Matt Duchene 2009-10 Upper Deck Victory #250") == "D"                       # une base
assert S("2023-24 Upper Deck Series 1 checklist lot Bedard") == "D"
assert S("Mathew Barzal 2017-18 SP Authentic Limited Auto /25") == "B+"              # numerotee /25-/50
assert S("2023-24 Upper Deck Kaboom Connor Bedard") != "A+"                           # pas de Kaboom au hockey
assert S("2023 Panini Kaboom Victor Wembanyama") == "A+"                              # ... mais oui ailleurs

# ronde 5 : les recrues d'avant les YG, les grosses recrues autographes
assert S("1979-80 O-Pee-Chee Wayne Gretzky #18 Rookie RC") == "A"
assert S("1985-86 O-Pee-Chee Mario Lemieux #9 RC PSA 10") == "A+"
assert S("1990-91 Upper Deck Jaromir Jagr #356 Rookie RC") == "A"
assert S("2023-24 O-Pee-Chee Rookie Logan Cooley #601 RC") != "A"                    # une recrue moderne hors YG
assert S("2024-25 Ultimate Collection Macklin Celebrini Rookie Auto Patch /99") == "A"
assert S("2023-24 SPx Rookie Auto Connor Bedard RC") == "A"
assert b.note_joueur("Marc-Andre Fleury")[1] == "A-"
assert b.note_joueur("Brandon Hagel")[1] == "B"
assert b.note_joueur("Matthew Tkachuk")[1] == "B+"

# 16 nov (« genre de carte qui devrait etre E ») : l'insert n'est pas le joueur ; un joueur sans demande donne E
import cartes_match
assert cartes_match.joueur_du_titre("2021-22 Upper Deck SPX Hockey Finite Rookies Sampo Ranta F-28 276/299") == "sampo ranta"
assert cartes_match.joueur_du_titre("2023-24 Engrained Hockey Rookie Signature Shots Vincent Iorio RSS-VI 096/299") == "vincent iorio"
assert b.lettre(b.note_finale(b.NOTE["C"], b.JOUEUR_INCONNU)) == "E"
assert b.lettre(b.note_finale(b.NOTE["B"], b.note_joueur("X", {"demande": 50, "notoriete": 13})[0])) == "E"
assert not b.recrue_recente("2021-22 Upper Deck SPX Finite Rookies Sampo Ranta", True)

# le joueur : la cote de collection de l'expert
assert b.note_joueur("Cole Caufield")[1] == "A+"
assert b.note_joueur("Jakub Dobes")[1] == "B"
assert b.note_joueur("Brendan Smith")[1] == "D"
assert b.note_joueur("Inconnu Total")[2] == "inconnu"
assert b.note_joueur("Inconnu Total", recrue=True)[1] == "B"                          # « rookie inconnu = B »
assert b.note_joueur("X", {"demande": 99, "notoriete": 99})[1] in ("A+", "A")
assert b.note_joueur("X", {"demande": 50, "notoriete": 40})[1] in ("C", "D", "E")

# la note finale : le plus faible domine
L = lambda s, j: b.lettre(b.note_finale(b.NOTE[s], b.NOTE[j]))
assert L("A", "C") == "C"            # « une YG raw d'un joueur moyen -> C »
assert L("D", "A+") == "C"           # « une base d'une superstar -> C »
assert L("A", "A+") == "A"           # Celebrini YG raw
assert L("A+", "B") == "B+"          # Quinn Hutson FW Auto Patch
assert L("A+", "B+") == "A-"         # Duchene YG PSA 10, Scheifele Cup RPA
assert L("A", "D") == "C"            # Brendan Smith YG
# en feu : un demi-cran
assert b.lettre(b.note_finale(b.NOTE["A"], b.NOTE["B+"]) + b.FEU_PTS) == "A-"   # Marner YG B+ -> A-
print("BAREME IQ OK")
